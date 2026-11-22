"""Subjects: manage subjects, colours and weekly goals; see progress."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

import config
from analytics import metrics
from components import widgets as w
from database import repositories as repo
from database.db import DatabaseError
from utils import state
from utils.formatting import esc, fmt_minutes, fmt_pct
from utils.validation import ValidationError


@st.dialog("Subject")
def subject_dialog(uid: int, sub: dict | None = None, suggested: str = "#8B7CFF") -> None:
    with st.form("subject_form"):
        name = st.text_input("Name", value=sub["name"] if sub else "", max_chars=60)
        c1, c2 = st.columns([1, 2])
        color = c1.color_picker("Colour", value=sub["color"] if sub else suggested)
        goal = c2.number_input("Weekly goal (minutes, 0 for none)", 0, 10000, int(sub["target_minutes"]) if sub else 120, 15)
        if st.form_submit_button("Save subject", type="primary", use_container_width=True):
            try:
                if sub:
                    repo.update_subject(int(sub["id"]), uid, name=name, color=color, target_minutes=goal)
                else:
                    repo.add_subject(uid, name, color, goal)
                st.toast("Subject saved", icon=":material/check:")
                st.rerun()
            except (ValidationError, DatabaseError) as exc:
                st.error(str(exc))


@st.dialog("Delete subject")
def delete_dialog(uid: int, sub: dict) -> None:
    st.write(f"Delete **{sub['name']}**? Its tasks and sessions are kept but become “No subject”.")
    c1, c2 = st.columns(2)
    if c1.button("Delete subject", type="primary", use_container_width=True):
        try:
            repo.delete_subject(int(sub["id"]), uid)
            st.toast("Subject deleted", icon=":material/delete:")
            st.rerun()
        except (ValidationError, DatabaseError) as exc:
            st.error(str(exc))
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def render() -> None:
    uid = state.user_id()
    subjects = repo.list_subjects_df(uid)
    sessions, tasks = repo.list_sessions_df(uid), repo.list_tasks_df(uid)
    today = date.today()
    w.page_header("Subjects", "Give each subject a colour and a weekly goal to see where your effort goes.")
    if st.button("Add subject", type="primary", icon=":material/add:"):
        subject_dialog(uid, suggested=config.SUBJECT_COLORS[len(subjects) % len(config.SUBJECT_COLORS)])
    st.write("")
    if subjects.empty:
        w.empty_state("📚", "No subjects yet", "Add the courses or topics you study. Tasks and sessions can then be grouped by subject.")
        return

    week = metrics.subject_summary(sessions, subjects, today - timedelta(days=6), today).set_index("subject")
    alltime = metrics.subject_summary(sessions, subjects, today - timedelta(days=3650), today).set_index("subject")
    cols = st.columns(3, gap="medium")
    for i, (_, s) in enumerate(subjects.iterrows()):
        wk, tot = week.loc[s["name"]], alltime.loc[s["name"]]
        open_n = int(((tasks["subject_id"] == s["id"]) & (tasks["status"] != "Completed")).sum()) if not tasks.empty else 0
        with cols[i % 3], w.panel(f"sub_{s['id']}"):
            w.html(f'<div style="display:flex;align-items:center;gap:.6rem">{w.dot(s["color"])}<div class="spd-title" style="margin:0">{esc(s["name"])}</div></div>')
            goal = int(s["target_minutes"])
            if goal:
                w.html(f'<div class="spd-note" style="margin:.7rem 0 .35rem">{fmt_minutes(wk["minutes"])} of {fmt_minutes(goal)} this week · {fmt_pct(wk["progress"])}</div>'
                       + w.bar(wk["progress"], esc(s["color"])))
            else:
                w.html(f'<div class="spd-note" style="margin:.7rem 0 .35rem">{fmt_minutes(wk["minutes"])} this week · no weekly goal</div>' + w.bar(0))
            w.html(f'<div class="spd-note" style="margin-top:.7rem">{int(tot["sessions"])} sessions all-time · {fmt_minutes(tot["minutes"])} · {open_n} open task(s) · focus {fmt_pct(tot["focus_ratio"])}</div>')
            a, b = st.columns(2)
            if a.button("Edit", key=f"se_{s['id']}", use_container_width=True, icon=":material/edit:"):
                subject_dialog(uid, s.to_dict())
            if b.button("Delete", key=f"sd_{s['id']}", use_container_width=True, icon=":material/delete:"):
                delete_dialog(uid, s.to_dict())
        st.write("")
