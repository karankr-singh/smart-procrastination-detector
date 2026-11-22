"""Focus Workspace: Pomodoro timer, session controls, optional tracking status, manual logging."""
from __future__ import annotations

from datetime import date, datetime, time as dtime

import streamlit as st
import streamlit.components.v1 as components

from components import widgets as w
from database import repositories as repo
from database.db import DatabaseError
from services.timer import Phase, State
from tracking import consent
from utils import state
from utils.formatting import fmt_clock, fmt_minutes
from utils.validation import ValidationError

BEEP_JS = """<script>try{const c=new (window.AudioContext||window.webkitAudioContext)();
[0,.25,.5].forEach((t,i)=>{const o=c.createOscillator(),g=c.createGain();o.frequency.value=660+i*110;o.connect(g);g.connect(c.destination);
g.gain.setValueAtTime(.0001,c.currentTime+t);g.gain.exponentialRampToValueAtTime(.2,c.currentTime+t+.02);g.gain.exponentialRampToValueAtTime(.0001,c.currentTime+t+.22);
o.start(c.currentTime+t);o.stop(c.currentTime+t+.25);});}catch(e){}</script>"""


def _notify(settings: dict, message: str, icon: str) -> None:
    if settings.get("notify_toast"):
        st.toast(message, icon=icon)
    if settings.get("notify_sound"):
        try:
            components.html(BEEP_JS, height=0)
        except Exception:
            pass


def _timer_view(uid: int) -> None:
    mgr = state.peek_manager()
    settings = mgr.settings
    events = mgr.tick()
    if events:
        if "phase_complete" in events:
            _notify(settings, "Focus session complete. Nice work!", ":material/check_circle:")
        if "break_over" in events:
            _notify(settings, "Break over. Ready for the next session?", ":material/timer:")
        if "auto_paused" in events:
            st.toast("Paused: no activity detected. Resume when you are back.", icon=":material/pause_circle:")
        st.rerun()

    t = mgr.timer
    focus = t.phase == Phase.FOCUS
    tone = "var(--apricot)" if t.state == State.PAUSED else ("var(--iris)" if focus else "var(--aqua)")
    seconds = t.remaining() if mgr.active else t.planned_seconds
    label = t.phase.value + (" · paused" if t.state == State.PAUSED else "")
    w.html(w.timer_ring(t.progress() if mgr.active else 0.0, fmt_clock(seconds), label, tone))
    dots = "".join(f'<i class="{"on" if i < t.cycle_position() else ""}"></i>' for i in range(t.sessions_before_long_break))
    w.html(f'<div class="spd-cycle" title="Focus sessions before a long break">{dots}</div>')
    st.write("")

    if mgr.auto_paused:
        st.warning("Auto-paused after no activity. Resume when you are back.")

    if t.state == State.IDLE:
        label = "Start focus session" if focus else f"Start {t.phase.value.lower()}"
        if st.button(label, type="primary", use_container_width=True, icon=":material/play_arrow:", key="btn_start"):
            _start(mgr)
    elif t.state == State.RUNNING:
        if focus:
            c1, c2, c3 = st.columns(3)
            if c1.button("Pause", use_container_width=True, icon=":material/pause:", key="btn_pause"):
                mgr.pause(); st.rerun()
            if c2.button("Stop", use_container_width=True, icon=":material/stop:", key="btn_stop"):
                _stop(mgr)
            if c3.button("Interrupted", use_container_width=True, icon=":material/notifications_paused:", key="btn_int",
                         help="Log an interruption (notification, person, phone…)"):
                mgr.log_interruption(); st.toast("Interruption logged", icon=":material/check:")
        else:
            c1, c2 = st.columns(2)
            if c1.button("Pause", use_container_width=True, icon=":material/pause:", key="btn_pause_b"):
                mgr.pause(); st.rerun()
            if c2.button("Skip break", use_container_width=True, icon=":material/skip_next:", key="btn_skip"):
                mgr.stop(); st.rerun()
    else:
        c1, c2 = st.columns(2)
        if c1.button("Resume", type="primary", use_container_width=True, icon=":material/play_arrow:", key="btn_resume"):
            mgr.resume(); st.rerun()
        if c2.button("Stop", use_container_width=True, icon=":material/stop:", key="btn_stop_p"):
            _stop(mgr)

    if mgr.active and focus:
        st.caption(f"{mgr.interruptions} interruption(s) logged this session.")


def _start(mgr) -> None:
    ss = st.session_state
    task_id = ss.get("focus_task_id")
    subject_id = ss.get("focus_subject_id")
    if task_id:
        tasks = repo.list_tasks_df(mgr.user_id)
        row = tasks[tasks["id"] == task_id]
        if not row.empty and row.iloc[0]["subject_id"] == row.iloc[0]["subject_id"]:
            subject_id = int(row.iloc[0]["subject_id"])
    t = mgr.timer
    t.short_break_minutes = ss.get("focus_short", t.short_break_minutes)
    t.long_break_minutes = ss.get("focus_long", t.long_break_minutes)
    try:
        mgr.start(subject_id, task_id, ss.get("focus_planned") if t.phase == Phase.FOCUS else None)
        st.rerun()
    except (ValidationError, DatabaseError) as exc:
        st.error(str(exc))


def _stop(mgr) -> None:
    try:
        rec = mgr.stop()
        st.toast(f"Session saved: {fmt_minutes(rec['actual_minutes'])}" if rec else "Session discarded (under 10 seconds).",
                 icon=":material/save:")
    except (ValidationError, DatabaseError) as exc:
        st.error(str(exc))
    st.rerun()


def render() -> None:
    uid = state.user_id()
    settings = repo.get_settings(uid)
    mgr = state.manager(uid, settings)
    subjects = repo.list_subjects_df(uid)
    tasks = repo.list_tasks_df(uid)
    open_tasks = tasks[tasks["status"] != "Completed"] if not tasks.empty else tasks

    w.page_header("Focus Workspace", "Pick what you are working on, then start the timer. Sessions are saved when they end.")
    left, right = st.columns([6, 5], gap="medium")

    with left, w.panel("timer"):
        run_every = 1 if mgr.timer.state == State.RUNNING else None
        st.fragment(run_every=run_every)(_timer_view)(uid)

    with right:
        with w.panel("setup"):
            w.section("This session", "Choose what you are studying")
            locked = mgr.active
            sub_opts = [None] + list(subjects["id"]) if not subjects.empty else [None]
            names = dict(zip(subjects["id"], subjects["name"])) if not subjects.empty else {}
            st.selectbox("Subject", sub_opts, key="focus_subject_id", disabled=locked,
                         format_func=lambda i: names.get(i, "No subject"))
            task_ids = [None] + (list(open_tasks["id"]) if not open_tasks.empty else [])
            labels = {r["id"]: f"{r['title']} · {r['subject_name']}" for _, r in open_tasks.iterrows()} if not open_tasks.empty else {}
            st.selectbox("Task", task_ids, key="focus_task_id", disabled=locked,
                         format_func=lambda i: labels.get(i, "No specific task"))
            with st.expander("Custom lengths", expanded=False):
                c1, c2, c3 = st.columns(3)
                c1.number_input("Focus (min)", 1, 240, int(settings["focus_minutes"]), key="focus_planned", disabled=locked)
                c2.number_input("Short break", 1, 60, int(settings["short_break_minutes"]), key="focus_short", disabled=locked)
                c3.number_input("Long break", 1, 90, int(settings["long_break_minutes"]), key="focus_long", disabled=locked)
                st.caption("These apply to the next session only. Change defaults in Settings.")
            if subjects.empty:
                st.caption("Tip: add subjects in the Subjects page to see where your time goes.")

        st.write("")
        with w.panel("tracking"):
            w.section("Activity tracking", "Optional and consent-based")
            idle_on, apps_on = consent.effective_flags(settings)
            if not (idle_on or apps_on):
                w.html(f'{w.pill("Off", "muted")} <span class="spd-note">Only the timer is recording. Turn tracking on in Settings → Privacy.</span>')
            else:
                tr = mgr.tracker
                paused = bool(tr and tr.paused_by_user)
                w.html(w.pill("Paused by you" if paused else "On", "warn" if paused else "good") +
                       f' <span class="spd-note">{"idle time" if idle_on else ""}{" + " if idle_on and apps_on else ""}{"app categories" if apps_on else ""}</span>')
                if tr is not None:
                    act, idl = tr.active_seconds / 60, tr.idle_seconds / 60
                    st.caption(f"Active {act:.1f} min · Idle {idl:.1f} min" if tr.measures_activity else
                               ("Idle detection isn't available on this system." if tr.idle_supported is False else "Measuring…"))
                    if st.button("Resume tracking" if paused else "Pause tracking", key="btn_trk", use_container_width=True):
                        tr.paused_by_user = not paused
                        st.rerun()
                else:
                    st.caption("Tracking will start with your next focus session.")

    st.write("")
    c1, c2 = st.columns([6, 5], gap="medium")
    with c1, w.panel("today"):
        w.section("Today's sessions", "")
        sess = repo.list_sessions_df(uid, date.today(), date.today())
        if sess.empty:
            w.empty_state("🌱", "Nothing logged today", "Start the timer above. Your finished sessions appear here.")
        else:
            w.html(w.session_rows(sess, 8))
            st.caption(f"Total today: {fmt_minutes(sess['actual_minutes'].sum())}")
    with c2, w.panel("manual"):
        w.section("Log a session manually", "Forgot to start the timer? Add it here.")
        with st.form("manual_form", clear_on_submit=True):
            m_sub = st.selectbox("Subject", sub_opts, format_func=lambda i: names.get(i, "No subject"), key="m_sub")
            m_date = st.date_input("Date", date.today(), max_value=date.today())
            m_time = st.time_input("Start time", value=dtime(18, 0))
            c1, c2 = st.columns(2)
            m_min = c1.number_input("Minutes studied", 1, 600, 25)
            m_int = c2.number_input("Interruptions", 0, 100, 0)
            if st.form_submit_button("Save session", use_container_width=True):
                try:
                    repo.add_manual_session(uid, m_sub, None, datetime.combine(m_date, m_time), m_min, interruption_count=m_int)
                    st.toast("Session saved", icon=":material/check:")
                    st.rerun()
                except (ValidationError, DatabaseError) as exc:
                    st.error(str(exc))
