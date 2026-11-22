"""Smart Procrastination Detector – application entry point and navigation.

Run with:  streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import config
from components import theme, widgets as w
from database import db, repositories as repo
from database.db import DatabaseError
from tracking import consent
from utils import state
from utils.validation import ValidationError

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(page_title=config.APP_NAME, page_icon=str(ASSETS / "icon.svg"), layout="wide",
                   initial_sidebar_state="expanded")


def onboarding() -> None:
    from scripts.seed_demo import seed
    left, mid, right = st.columns([1, 1.5, 1])
    with mid:
        w.html('<div style="text-align:center;margin:2.5rem 0 1.2rem"><div class="spd-sub" style="margin:0 auto">Welcome to</div>'
               '<h1 style="margin:.2rem 0">Smart Procrastination Detector</h1>'
               '<div class="spd-sub" style="margin:.6rem auto 0">Understand how you study, spot what slows you down, '
               'and plan around it. Everything stays on this computer.</div></div>')
        with w.panel("onboard"):
            w.section("Create your local profile", "You can change all of this later in Settings.")
            with st.form("onboard_form"):
                name = st.text_input("Your name", max_chars=40, placeholder="e.g. Aarav")
                goal = st.number_input("Daily study target (minutes)", 10, 1000, 120, 10)
                c1, c2 = st.columns(2)
                start = c1.time_input("Preferred study start", value=__import__("datetime").time(18, 0))
                end = c2.time_input("Preferred study end", value=__import__("datetime").time(21, 0))
                submitted = st.form_submit_button("Create profile", type="primary", use_container_width=True)
            if submitted:
                try:
                    uid = repo.create_user(name, goal, start.strftime("%H:%M"), end.strftime("%H:%M"))
                    state.set_user(uid)
                    st.rerun()
                except (ValidationError, DatabaseError) as exc:
                    st.error(str(exc))
            st.divider()
            st.caption("Just exploring? Load a clearly-labelled synthetic demo profile (12 weeks of generated data).")
            if st.button("Load synthetic demo profile", use_container_width=True):
                try:
                    state.set_user(seed())
                    st.rerun()
                except (ValidationError, DatabaseError) as exc:
                    st.error(str(exc))


def sidebar_status(uid: int, user: dict, settings: dict) -> None:
    mgr = state.peek_manager()
    with st.sidebar:
        st.divider()
        idle_on, apps_on = consent.effective_flags(settings)
        if idle_on or apps_on:
            what = " + ".join(x for x, f in (("idle", idle_on), ("app categories", apps_on)) if f)
            tracking = w.pill(f"Tracking on · {what}", "warn")
        else:
            tracking = w.pill("Tracking off", "muted")
        timer_pill = ""
        if mgr and mgr.active:
            from utils.formatting import fmt_clock
            label = f"{mgr.timer.phase.value} · {fmt_clock(mgr.timer.remaining())}" + (" · paused" if mgr.timer.state.value == "paused" else "")
            timer_pill = w.pill(label, "good")
        w.html(f'<div style="display:flex;flex-direction:column;align-items:flex-start;gap:.55rem">'
               f'<div style="font-weight:700;font-family:var(--display)">{w.esc(user["username"])}</div>{tracking}{timer_pill}</div>')
        if len(repo.list_users()) > 1:
            users = repo.list_users()
            names = {u["id"]: u["username"] for u in users}
            pick = st.selectbox("Profile", list(names), index=list(names).index(uid), format_func=names.get,
                                label_visibility="collapsed")
            if pick != uid:
                state.set_user(pick)
                st.rerun()


def main() -> None:
    try:
        db.get_engine()
    except Exception as exc:  # pragma: no cover - startup failure path
        st.error(f"Couldn't open the database at {config.DB_PATH}: {exc}")
        st.stop()
    theme.inject()
    st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icon.svg"), size="large")

    uid = state.user_id()
    users = repo.list_users()
    if uid is None or not any(u["id"] == uid for u in users):
        if users:
            state.set_user(users[0]["id"])
            uid = users[0]["id"]
        else:
            onboarding()
            return
    user, settings = repo.get_user(uid), repo.get_settings(uid)
    state.manager(uid, settings)

    from pages import analytics_page, dashboard, focus, reports, settings_page, subjects, tasks
    pages = {
        "dashboard": st.Page(dashboard.render, title="Dashboard", icon=":material/space_dashboard:", url_path="dashboard", default=True),
        "focus": st.Page(focus.render, title="Focus Workspace", icon=":material/timer:", url_path="focus"),
        "tasks": st.Page(tasks.render, title="Tasks", icon=":material/checklist:", url_path="tasks"),
        "subjects": st.Page(subjects.render, title="Subjects", icon=":material/menu_book:", url_path="subjects"),
        "analytics": st.Page(analytics_page.render, title="Analytics", icon=":material/insights:", url_path="analytics"),
        "reports": st.Page(reports.render, title="Reports", icon=":material/description:", url_path="reports"),
        "settings": st.Page(settings_page.render, title="Settings", icon=":material/tune:", url_path="settings"),
    }
    state.register_pages(pages)
    nav = st.navigation(list(pages.values()))
    sidebar_status(uid, user, settings)
    try:
        nav.run()
    except DatabaseError as exc:
        st.error(str(exc))


main()
