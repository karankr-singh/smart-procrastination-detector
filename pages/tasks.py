"""Tasks: create, edit, complete, postpone, delete, filter and sort."""
from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta

import pandas as pd
import streamlit as st

from components import widgets as w
from config import PRIORITIES, TASK_STATUSES
from database import repositories as repo
from database.db import DatabaseError
from utils import state
from utils.formatting import esc, fmt_minutes
from utils.validation import ValidationError

PRIORITY_TONE = {"Urgent": "bad", "High": "warn", "Medium": "info", "Low": "muted"}
STATUS_TONE = {"Completed": "good", "Overdue": "bad", "In Progress": "info", "Pending": "muted"}
PRIORITY_RANK = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}


def _safe(fn, *args, ok: str = "", **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
        if ok:
            st.toast(ok, icon=":material/check:")
        return True
    except (ValidationError, DatabaseError) as exc:
        st.error(str(exc))
        return False


@st.dialog("Task", width="large")
def task_dialog(uid: int, task: dict | None = None) -> None:
    subjects = repo.list_subjects_df(uid)
    ids = [None] + list(subjects["id"])
    names = dict(zip(subjects["id"], subjects["name"]))
    editing = task is not None
    with st.form("task_form"):
        title = st.text_input("Title", value=task["title"] if editing else "", max_chars=120)
        c1, c2 = st.columns(2)
        subject = c1.selectbox("Subject", ids, index=ids.index(task["subject_id"]) if editing and task["subject_id"] in ids else 0,
                               format_func=lambda i: names.get(i, "No subject"))
        priority = c2.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(task["priority"]) if editing else 1)
        has_deadline = st.checkbox("Has a deadline", value=(task["deadline"] is not pd.NaT and pd.notna(task["deadline"])) if editing else True)
        d_default = task["deadline"].to_pydatetime() if editing and pd.notna(task["deadline"]) else datetime.now() + timedelta(days=3)
        c1, c2 = st.columns(2)
        d_date = c1.date_input("Deadline date", d_default.date())
        d_time = c2.time_input("Deadline time", d_default.time().replace(second=0, microsecond=0))
        est = st.number_input("Estimated time (minutes)", 0, 10000, int(task["estimated_minutes"]) if editing and pd.notna(task["estimated_minutes"]) else 60, 15,
                              help="0 means no estimate")
        desc = st.text_area("Notes", value=task["description"] if editing else "", max_chars=2000, height=90)
        if editing:
            st.caption("Moving the deadline later counts as an extension and is used in procrastination indicators.")
        if st.form_submit_button("Save changes" if editing else "Create task", type="primary", use_container_width=True):
            deadline = datetime.combine(d_date, d_time) if has_deadline else None
            fields = dict(title=title, description=desc, priority=priority, deadline=deadline, estimated_minutes=est or None)
            if editing:
                ok = _safe(repo.update_task, int(task["id"]), uid, subject_id=subject, **fields)
            else:
                ok = _safe(repo.add_task, uid, title, subject, desc, priority, deadline, est or None)
            if ok:
                st.toast("Task saved", icon=":material/check:")
                st.rerun()


@st.dialog("Postpone task")
def postpone_dialog(uid: int, task: dict) -> None:
    st.write(f"Move the deadline for **{task['title']}**.")
    base = task["deadline"].to_pydatetime() if pd.notna(task["deadline"]) else datetime.now()
    new_date = st.date_input("New deadline", max(base.date(), date.today()) + timedelta(days=1))
    new_time = st.time_input("Time", base.time().replace(second=0, microsecond=0))
    st.caption("Postponements are counted so you can see which tasks keep slipping.")
    if st.button("Postpone", type="primary", use_container_width=True):
        if _safe(repo.postpone_task, int(task["id"]), uid, datetime.combine(new_date, new_time), ok="Task postponed"):
            st.rerun()


@st.dialog("Delete task")
def delete_dialog(uid: int, task: dict) -> None:
    st.write(f"Delete **{task['title']}**? Study sessions linked to it are kept but will no longer show a task.")
    c1, c2 = st.columns(2)
    if c1.button("Delete task", type="primary", use_container_width=True):
        if _safe(repo.delete_task, int(task["id"]), uid, ok="Task deleted"):
            st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def _deadline_text(r) -> str:
    if pd.isna(r["deadline"]):
        return "No deadline"
    d = r["deadline"]
    delta = (d.date() - date.today()).days
    rel = "today" if delta == 0 else f"in {delta}d" if delta > 0 else f"{-delta}d ago"
    return f"Due {d:%d %b, %H:%M} ({rel})"


def render() -> None:
    uid = state.user_id()
    tasks = repo.list_tasks_df(uid)
    w.page_header("Tasks", "Everything you need to do, with deadlines, priorities and how often it slips.")
    top = st.columns([1, 1, 1, 1, 1.2], gap="small", vertical_alignment="center")
    counts = tasks["status"].value_counts().to_dict() if not tasks.empty else {}
    top[0].markdown(w.stat_card("Pending", str(counts.get("Pending", 0)), "", "muted"), unsafe_allow_html=True)
    top[1].markdown(w.stat_card("In progress", str(counts.get("In Progress", 0)), "", "info"), unsafe_allow_html=True)
    top[2].markdown(w.stat_card("Overdue", str(counts.get("Overdue", 0)), "", "bad"), unsafe_allow_html=True)
    top[3].markdown(w.stat_card("Completed", str(counts.get("Completed", 0)), "", "good"), unsafe_allow_html=True)
    if top[4].button("New task", type="primary", icon=":material/add:", use_container_width=True):
        task_dialog(uid)
    st.write("")

    if tasks.empty:
        w.empty_state("✅", "No tasks yet", "Create your first task to start tracking deadlines and progress.")
        return

    f1, f2, f3, f4 = st.columns([1.6, 1.4, 1.4, 1.6])
    status_sel = f1.multiselect("Status", TASK_STATUSES, default=["Pending", "In Progress", "Overdue"])
    subj_opts = sorted(tasks["subject_name"].unique())
    subj_sel = f2.multiselect("Subject", subj_opts)
    prio_sel = f3.multiselect("Priority", PRIORITIES)
    sort = f4.selectbox("Sort by", ["Deadline (soonest)", "Priority (highest)", "Most postponed", "Newest"])
    s1, s2 = st.columns([3, 1], vertical_alignment="bottom")
    query = s1.text_input("Search", placeholder="Search titles…", label_visibility="collapsed")
    only_postponed = s2.toggle("Repeatedly postponed", help="Postponed or extended at least twice")

    df = tasks.copy()
    if status_sel: df = df[df["status"].isin(status_sel)]
    if subj_sel: df = df[df["subject_name"].isin(subj_sel)]
    if prio_sel: df = df[df["priority"].isin(prio_sel)]
    if query: df = df[df["title"].str.contains(query, case=False, na=False)]
    if only_postponed: df = df[(df["postponement_count"] >= 2) | (df["extension_count"] >= 2)]
    if sort.startswith("Deadline"): df = df.sort_values("deadline", na_position="last")
    elif sort.startswith("Priority"): df = df.assign(_r=df["priority"].map(PRIORITY_RANK)).sort_values(["_r", "deadline"])
    elif sort.startswith("Most"): df = df.sort_values(["postponement_count", "extension_count"], ascending=False)
    else: df = df.sort_values("created_at", ascending=False)

    if df.empty:
        w.empty_state("🔍", "No tasks match these filters", "Clear a filter or change the search.")
        return

    limit = st.session_state.get("task_limit", 20)
    st.caption(f"{len(df)} task(s)")
    for _, r in df.head(limit).iterrows():
        done = r["status"] == "Completed"
        with w.flat_box(f"task_{r['id']}"):
            c0, c1, c2 = st.columns([0.6, 6, 2.2], vertical_alignment="center")
            if c0.button("", icon=":material/undo:" if done else ":material/check_circle:", key=f"done_{r['id']}",
                         help="Reopen" if done else "Mark completed"):
                if done:
                    repo.reopen_task(int(r["id"]), uid)
                else:
                    repo.complete_task(int(r["id"]), uid)
                st.rerun()
            slip = ""
            if r["postponement_count"]: slip += f" · postponed {int(r['postponement_count'])}×"
            if r["extension_count"]: slip += f" · extended {int(r['extension_count'])}×"
            est = f" · est. {fmt_minutes(r['estimated_minutes'])}" if pd.notna(r["estimated_minutes"]) else ""
            title_style = "text-decoration:line-through;opacity:.6" if done else ""
            c1.markdown(w.flat(f'<div class="spd-row" style="border:none;padding:0">{w.dot(r["subject_color"])}<div class="main">'
                                f'<div class="t" style="{title_style}">{esc(r["title"])}</div>'
                                f'<div class="m">{esc(r["subject_name"])} · {_deadline_text(r)}{est} · logged {fmt_minutes(r["actual_minutes"])}{slip}</div></div>'
                                f'{w.pill(r["priority"], PRIORITY_TONE[r["priority"]])} {w.pill(r["status"], STATUS_TONE[r["status"]])}</div>'),
                        unsafe_allow_html=True)
            a, b, c = c2.columns(3)
            task = r.to_dict()
            if a.button("", icon=":material/edit:", key=f"edit_{r['id']}", help="Edit"):
                task_dialog(uid, task)
            if b.button("", icon=":material/event_repeat:", key=f"post_{r['id']}", help="Postpone", disabled=done):
                postpone_dialog(uid, task)
            if c.button("", icon=":material/delete:", key=f"del_{r['id']}", help="Delete"):
                delete_dialog(uid, task)
    if len(df) > limit and st.button("Show more"):
        st.session_state["task_limit"] = limit + 20
        st.rerun()
