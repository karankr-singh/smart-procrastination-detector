"""Dashboard: the at-a-glance view."""
from __future__ import annotations

from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from analytics import metrics, scoring, service as svc
from components import insights, widgets as w
from components.theme import palette
from database import repositories as repo
from utils import state
from utils.formatting import fmt_clock, fmt_minutes


def _greeting() -> str:
    h = datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


def render() -> None:
    uid = state.user_id()
    snap = svc.load_snapshot(uid)
    user, settings, today = snap.user, snap.settings, snap.today
    p = palette()

    if st.session_state.get("_daily_cached") != today:
        svc.persist_daily(snap)
        st.session_state["_daily_cached"] = today

    w.page_header(f"{_greeting()}, {user['username']}", f"{today:%A, %d %B}. Here is how your study is going.")
    if settings["is_synthetic"]:
        w.banner("You are viewing synthetic demo data generated for demonstration – it is not real activity.")

    score = svc.current_score(snap)
    daily7 = metrics.daily_minutes(snap.sessions, today - timedelta(days=6), today)
    today_min, week_min = float(daily7.iloc[-1]), float(daily7.sum())
    tasks = snap.tasks
    done_week = int((tasks["completed_at"] >= datetime.combine(today - timedelta(days=6), datetime.min.time())).sum()) if not tasks.empty else 0
    done_all = int((tasks["status"] == "Completed").sum()) if not tasks.empty else 0
    open_n = int((tasks["status"] != "Completed").sum()) if not tasks.empty else 0
    overdue_n = int((tasks["status"] == "Overdue").sum()) if not tasks.empty else 0
    goal = user["daily_goal_minutes"]

    # ---- row 1: score + stats
    c1, c2 = st.columns([5, 7], gap="medium")
    with c1, w.panel("score"):
        w.section("Productivity score", "Your last 7 days, from your own records")
        w.html(w.score_ring(score.score))
        w.html(w.component_bars(score.components))
        for note in score.notes:
            st.caption(note)
        with st.expander("How is this calculated?"):
            st.markdown("Four parts, each turned into a 0–100% value and weighted: **task completion 35**, **focus 30**, "
                        "**goal progress 20**, **consistency 15**. Parts with no data are left out and the rest are rescaled, "
                        "so missing data never counts as zero.")
            st.caption(scoring.DISCLAIMER)
    with c2:
        a, b = st.columns(2, gap="medium")
        a.markdown(w.stat_card("Studied today", fmt_minutes(today_min),
                               f"{max(goal - today_min, 0):.0f} min to reach your {goal}-min goal" if today_min < goal else "Daily goal reached", "aqua"),
                   unsafe_allow_html=True)
        b.markdown(w.stat_card("This week", fmt_minutes(week_min), f"{week_min / 7:.0f} min per day on average", "brand"), unsafe_allow_html=True)
        st.write("")
        a, b = st.columns(2, gap="medium")
        a.markdown(w.stat_card("Tasks completed", str(done_week), f"this week · {done_all} in total", "good"), unsafe_allow_html=True)
        b.markdown(w.stat_card("Tasks pending", str(open_n), f"{overdue_n} overdue" if overdue_n else "none overdue",
                               "bad" if overdue_n else "warn"), unsafe_allow_html=True)
        st.write("")
        with w.panel("focus_now"):
            mgr = state.peek_manager()
            if mgr and mgr.active:
                running = mgr.timer.state.value == "running"
                w.section("Current focus session", "")
                w.html(f'<div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">'
                       f'<div style="font-family:var(--display);font-size:2rem;font-weight:700">{fmt_clock(mgr.timer.remaining())}</div>'
                       f'<div>{w.pill(mgr.timer.phase.value, "good" if running else "warn")} {w.pill("Running" if running else "Paused", "good" if running else "warn")}</div></div>')
                st.progress(mgr.timer.progress())
                state.page_link("focus", "Open Focus Workspace", ":material/timer:")
            else:
                w.section("Current focus session", "Nothing running right now.")
                cc1, cc2 = st.columns([3, 2], vertical_alignment="center")
                cc1.markdown(f"Ready for a {settings['focus_minutes']}-minute block?")
                with cc2:
                    state.page_link("focus", "Start a session", ":material/play_arrow:")
        st.progress(min(today_min / goal, 1.0) if goal else 0.0, text=f"Today's goal · {today_min:.0f} of {goal} min")

    st.write("")
    # ---- row 2: trend + subjects
    c1, c2 = st.columns([7, 5], gap="medium")
    with c1, w.panel("trend"):
        w.section("Weekly productivity trend", "Study minutes per day, with your rolling 7-day score")
        tr = svc.trend(snap, 7)
        if tr["minutes"].sum() == 0 and tr["score"].isna().all():
            w.empty_state("📈", "Your trend starts with your first session", "Run a focus session or log one manually to see it here.")
        else:
            fig = go.Figure()
            fig.add_bar(x=[d.strftime("%a %d") for d in tr["date"]], y=tr["minutes"], name="Study minutes",
                        marker=dict(color=p["iris"], cornerradius=8), hovertemplate="%{y:.0f} min<extra></extra>")
            fig.add_scatter(x=[d.strftime("%a %d") for d in tr["date"]], y=tr["score"], name="Score", yaxis="y2", mode="lines+markers",
                            line=dict(color=p["aqua"], width=3), marker=dict(size=8), connectgaps=False, hovertemplate="Score %{y}<extra></extra>")
            fig.add_hline(y=goal, line_dash="dot", line_color=p["apricot"], annotation_text="daily goal", annotation_font_color=p["apricot"])
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 100], showgrid=False), yaxis=dict(title=None, rangemode="tozero"))
            w.show(w.style_fig(fig, 290, legend=True))
    with c2, w.panel("subjects"):
        w.section("Where your time went", "Last 7 days by subject")
        summ = metrics.subject_summary(snap.sessions, snap.subjects, today - timedelta(days=6), today)
        summ = summ[summ["minutes"] > 0]
        if summ.empty:
            w.empty_state("🥧", "No study time this week", "Add subjects and log sessions to see how your time splits.")
        else:
            fig = go.Figure(go.Pie(labels=summ["subject"], values=summ["minutes"], hole=0.68, sort=False,
                                   marker=dict(colors=list(summ["color"]), line=dict(color=p["surface"], width=3)),
                                   textinfo="none", hovertemplate="%{label}<br>%{value:.0f} min · %{percent}<extra></extra>"))
            fig.add_annotation(text=f"<b>{fmt_minutes(summ['minutes'].sum())}</b>", showarrow=False, font=dict(size=22, color=p["text"], family="Sora"))
            fig.update_layout(showlegend=True, legend=dict(orientation="v", x=1.0, y=0.5, font=dict(color=p["text"])))
            w.show(w.style_fig(fig, 290, legend=True))

    st.write("")
    c1, c2 = st.columns([5, 7], gap="medium")
    with c1, w.panel("recent"):
        w.section("Recent study sessions", "")
        recent = snap.sessions
        if recent.empty:
            w.empty_state("⏱️", "No sessions yet", "Your finished focus sessions will be listed here.")
        else:
            w.html(w.session_rows(recent, 6))
    with c2, w.panel("insights"):
        w.section("Personalised insights", "Based on your recorded data. Each one explains why it is shown.")
        recs = svc.recs(snap, repo.dismissed_recommendations(uid))
        insights.recommendations(recs, uid, "dash", limit=3)
        n_ind = len(svc.indicators(snap))
        if n_ind:
            state.page_link("analytics", f"{n_ind} procrastination indicator(s) in Analytics", ":material/insights:")
