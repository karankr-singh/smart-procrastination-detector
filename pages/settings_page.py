"""Settings: profile, targets, timer, privacy, notifications, data management."""
from __future__ import annotations

from datetime import datetime, time as dtime

import pandas as pd
import streamlit as st

from components import widgets as w
from database import db, repositories as repo
from database.db import DatabaseError
from services import export_service as ex
from tracking import apps, consent, idle
from utils import state
from utils.validation import ValidationError


def _t(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def _try(fn, ok: str) -> bool:
    try:
        fn()
        st.toast(ok, icon=":material/check:")
        return True
    except (ValidationError, DatabaseError) as exc:
        st.error(str(exc))
        return False


def _profile(uid, user):
    with w.panel("set_profile"):
        w.section("Your profile", "Stored only on this computer")
        with st.form("profile_form"):
            name = st.text_input("Name", user["username"], max_chars=40)
            goal = st.number_input("Daily study target (minutes)", 10, 1000, int(user["daily_goal_minutes"]), 10)
            c1, c2 = st.columns(2)
            s1 = c1.time_input("Preferred study start", _t(user["preferred_study_start"]))
            s2 = c2.time_input("Preferred study end", _t(user["preferred_study_end"]))
            if st.form_submit_button("Save profile", type="primary"):
                if _try(lambda: repo.update_user(uid, username=name, daily_goal_minutes=goal, preferred_study_start=s1.strftime("%H:%M"),
                                                 preferred_study_end=s2.strftime("%H:%M")), "Profile saved"):
                    st.rerun()
    st.write("")
    with w.panel("set_newprof"):
        w.section("Add another profile", "Each profile keeps its own tasks, sessions and settings.")
        with st.form("newprof"):
            n = st.text_input("New profile name", max_chars=40)
            if st.form_submit_button("Create and switch"):
                try:
                    state.set_user(repo.create_user(n))
                    st.rerun()
                except (ValidationError, DatabaseError) as exc:
                    st.error(str(exc))


def _timer(uid, s):
    with w.panel("set_timer"):
        w.section("Timer", "Defaults for new focus sessions (Pomodoro)")
        with st.form("timer_form"):
            c1, c2, c3, c4 = st.columns(4)
            f = c1.number_input("Focus (min)", 1, 240, int(s["focus_minutes"]))
            sb = c2.number_input("Short break", 1, 60, int(s["short_break_minutes"]))
            lb = c3.number_input("Long break", 1, 90, int(s["long_break_minutes"]))
            n = c4.number_input("Sessions before long break", 2, 10, int(s["sessions_before_long_break"]))
            if st.form_submit_button("Save timer settings", type="primary"):
                if _try(lambda: repo.set_settings(uid, {"focus_minutes": f, "short_break_minutes": sb, "long_break_minutes": lb,
                                                        "sessions_before_long_break": n}), "Timer settings saved"):
                    st.rerun()


def _privacy(uid, s):
    with w.panel("set_privacy"):
        w.section("Activity tracking & privacy", "Off by default. You decide what, if anything, is measured.")
        for line in consent.PRIVACY_PROMISES:
            st.markdown(f"- {line}")
        st.write("")
        if not consent.has_consent(s):
            idle_on = st.checkbox("Measure idle time (seconds since last keyboard or mouse input)")
            apps_on = st.checkbox("Record the category of the active app (name is never stored)")
            agree = st.checkbox("I understand what is measured and I consent to tracking during focus sessions.")
            if st.button("Turn tracking on", type="primary", disabled=not (agree and (idle_on or apps_on))):
                consent.grant_consent(uid, idle=idle_on, apps=apps_on)
                st.toast("Tracking is on. It only runs during focus sessions.", icon=":material/shield:")
                st.rerun()
            if not (idle_on or apps_on) and agree:
                st.caption("Choose at least one thing to measure.")
        else:
            w.html(w.pill("Tracking on", "warn") + f' <span class="spd-note">since {s["tracking_consent_at"]}</span>')
            with st.form("trk_form"):
                i = st.checkbox("Measure idle time", s["track_idle"])
                a = st.checkbox("Record active-app category", s["track_apps"])
                th = st.number_input("Auto-pause after inactivity (minutes)", 1, 60, int(s["idle_threshold_minutes"]))
                if st.form_submit_button("Save tracking options"):
                    if _try(lambda: repo.set_settings(uid, {"track_idle": i, "track_apps": a, "idle_threshold_minutes": th}), "Tracking options saved"):
                        st.rerun()
            if st.button("Turn tracking off", icon=":material/block:"):
                consent.revoke_consent(uid)
                st.toast("Tracking turned off", icon=":material/check:")
                st.rerun()
    st.write("")
    with w.panel("set_detect"):
        w.section("Check what this computer supports", "Runs once when you click; nothing is stored.")
        if st.button("Test detection"):
            sec = idle.get_idle_seconds()
            st.write("Idle detection: " + (f"works (idle for {sec:.0f}s)" if sec is not None else "not available on this system"))
            name = apps.get_foreground_process_name()
            st.write("App category: " + (f"works (current category: **{apps.categorize(name)}**)" if name else "not available on this system"))
        st.divider()
        w.section("Delete recorded activity", "Removes activity events and the active/idle split from every session. Session times are kept.")
        sure = st.checkbox("Yes, delete recorded activity")
        if st.button("Delete activity data", disabled=not sure):
            n = repo.delete_activity_events(uid)
            st.toast(f"Deleted {n} activity record(s)", icon=":material/delete:")


def _notifications(uid, s):
    with w.panel("set_notif"):
        w.section("Notifications", "")
        with st.form("notif"):
            t = st.toggle("Show a message when a session or break ends", s["notify_toast"])
            snd = st.toggle("Play a short sound", s["notify_sound"], help="Your browser may block sound until you have interacted with the page.")
            ab = st.toggle("Start breaks automatically after a focus session", s["auto_start_breaks"])
            if st.form_submit_button("Save", type="primary"):
                if _try(lambda: repo.set_settings(uid, {"notify_toast": t, "notify_sound": snd, "auto_start_breaks": ab}), "Saved"):
                    st.rerun()


@st.dialog("Delete session")
def _del_session(uid, sid):
    st.write("Delete this session permanently?")
    c1, c2 = st.columns(2)
    if c1.button("Delete", type="primary", use_container_width=True):
        if _try(lambda: repo.delete_session(sid, uid), "Session deleted"):
            st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def _data(uid, user, s):
    frames = {"Sessions": repo.list_sessions_df(uid, include_running=True), "Tasks": repo.list_tasks_df(uid), "Subjects": repo.list_subjects_df(uid),
              "Activity events": repo.list_events_df(uid), "Daily analytics": repo.list_daily_df(uid)}
    with w.panel("set_view"):
        w.section("Stored records", "Everything the app has saved about you")
        pick = st.selectbox("Table", list(frames), label_visibility="collapsed")
        df = frames[pick]
        st.dataframe(df.drop(columns=[c for c in ("user_id",) if c in df.columns]), hide_index=True, use_container_width=True, height=280)
    st.write("")
    sessions = frames["Sessions"]
    sessions = sessions[sessions["session_status"] != "Running"]
    with w.panel("set_edit"):
        w.section("Correct or delete a session", "Fix a wrong duration, subject or start time")
        if sessions.empty:
            st.caption("No sessions to edit yet.")
        else:
            recent = sessions.sort_values("start_time", ascending=False).head(100)
            labels = {r["id"]: f"{r['start_time']:%d %b %H:%M} · {r['subject_name']} · {r['actual_minutes']:.0f} min" for _, r in recent.iterrows()}
            sid = st.selectbox("Session", list(labels), format_func=labels.get)
            r = recent[recent["id"] == sid].iloc[0]
            subs = repo.list_subjects_df(uid)
            ids = [None] + list(subs["id"])
            names = dict(zip(subs["id"], subs["name"]))
            with st.form("edit_session"):
                c1, c2 = st.columns(2)
                sub = c1.selectbox("Subject", ids, index=ids.index(r["subject_id"]) if r["subject_id"] in ids else 0, format_func=lambda i: names.get(i, "No subject"))
                start = c2.datetime_input("Start", r["start_time"].to_pydatetime())
                c1, c2, c3 = st.columns(3)
                act = c1.number_input("Actual minutes", 0.0, 1000.0, float(r["actual_minutes"]), 1.0)
                pl = c2.number_input("Planned minutes", 1.0, 1000.0, float(r["planned_minutes"]), 1.0)
                it = c3.number_input("Interruptions", 0, 500, int(r["interruption_count"]))
                if st.form_submit_button("Save correction", type="primary"):
                    if _try(lambda: repo.update_session(int(sid), uid, subject_id=sub, start_time=start, actual_minutes=act, planned_minutes=pl, interruption_count=it), "Session updated"):
                        st.rerun()
            if st.button("Delete this session", icon=":material/delete:"):
                _del_session(uid, int(sid))
    st.write("")
    with w.panel("set_export"):
        w.section("Export and back up", "")
        c1, c2 = st.columns(2)
        c1.download_button("Export my data (ZIP of CSVs)", ex.personal_data_zip(uid), "spd_personal_data.zip", "application/zip", use_container_width=True, icon=":material/download:")
        if c2.button("Create database backup", use_container_width=True, icon=":material/backup:"):
            path = db.backup_database()
            st.session_state["last_backup"] = str(path)
        if st.session_state.get("last_backup"):
            path = st.session_state["last_backup"]
            st.success(f"Backup saved to {path}")
            with open(path, "rb") as fh:
                st.download_button("Download backup file", fh.read(), path.split("/")[-1].split("\\")[-1], "application/octet-stream")
            st.caption(db.restore_hint())
    st.write("")
    with w.panel("set_danger"):
        w.section("Delete all personal records", "Removes sessions, tasks, subjects, analytics, suggestions state and tracking consent. This cannot be undone.")
        also = st.checkbox("Also delete my profile")
        typed = st.text_input("Type DELETE to confirm", key="del_confirm")
        if st.button("Delete everything", type="primary", disabled=typed != "DELETE", icon=":material/delete_forever:"):
            if _try(lambda: repo.delete_all_records(uid, include_profile=also), "All personal records deleted"):
                st.session_state.pop("manager", None)
                if also:
                    st.session_state.pop("user_id", None)
                st.session_state["del_confirm"] = ""
                st.rerun()
    if not any(u["username"] == "demo_student" for u in repo.list_users()):
        st.write("")
        with w.panel("set_demo"):
            w.section("Synthetic demo data", "Adds a separate, clearly labelled demo profile with generated data. It never mixes with your records.")
            if st.button("Add synthetic demo profile"):
                from scripts.seed_demo import seed
                _try(lambda: seed(), "Demo profile added. Switch to it from the sidebar.")
                st.rerun()


def render() -> None:
    uid = state.user_id()
    user, s = repo.get_user(uid), repo.get_settings(uid)
    w.page_header("Settings", "Targets, timer, privacy and your data.")
    tabs = st.tabs(["Profile", "Timer", "Privacy", "Notifications", "Data", "About"])
    with tabs[0]: _profile(uid, user)
    with tabs[1]: _timer(uid, s)
    with tabs[2]: _privacy(uid, s)
    with tabs[3]: _notifications(uid, s)
    with tabs[4]: _data(uid, user, s)
    with tabs[5]:
        import config
        with w.panel("set_about"):
            w.section(f"{config.APP_NAME} {config.APP_VERSION}", "")
            st.write(f"Database: `{db.db_path()}`")
            st.caption("The productivity score and procrastination indicators are self-reflection aids built from your own records. "
                       "They are not scientific, medical or psychological assessments.")
            if st.button("Reset all preferences to defaults"):
                repo.reset_settings(uid)
                st.toast("Preferences reset", icon=":material/restart_alt:")
                st.rerun()
