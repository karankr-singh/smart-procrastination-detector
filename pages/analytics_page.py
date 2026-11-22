"""Analytics: trends, subjects, tasks, focus patterns, procrastination indicators, experimental ML."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import metrics, scoring, service as svc
from components import insights, widgets as w
from components.theme import palette
from database import repositories as repo
from ml import procrastination_model as ml
from utils import state
from utils.formatting import fmt_minutes, fmt_pct


def _heatmap(snap, weeks: int = 17):
    p = palette()
    end = snap.today
    start = end - timedelta(days=end.weekday() + (weeks - 1) * 7)
    daily = metrics.daily_minutes(snap.sessions, start, end)
    hm = metrics.heatmap_matrix(daily)
    z = [[None] * weeks for _ in range(7)]
    txt = [[""] * weeks for _ in range(7)]
    for _, r in hm.iterrows():
        z[int(r["weekday"])][int(r["week"])] = float(r["minutes"])
        txt[int(r["weekday"])][int(r["week"])] = f"{r['date']:%a %d %b %Y}: {fmt_minutes(r['minutes'])}"
    labels = [(start + timedelta(weeks=i)).strftime("%d %b") for i in range(weeks)]
    fig = go.Figure(go.Heatmap(z=z, x=labels, y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], text=txt, hoverinfo="text",
                               xgap=4, ygap=4, showscale=False, zmin=0, zmax=max(float(snap.user["daily_goal_minutes"]), 1.0),
                               colorscale=[[0, p["track"]], [0.5, p["iris"]], [1, p["aqua"]]]))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, tickangle=0, nticks=9)
    return w.style_fig(fig, 250)


def _overview(snap, days: int):
    p = palette()
    start = snap.today - timedelta(days=days - 1)
    tr = svc.trend(snap, days)
    c1, c2 = st.columns(2, gap="medium")
    with c1, w.panel("an_time"):
        w.section("Study time", f"Minutes per day over the last {days} days")
        if tr["minutes"].sum() == 0:
            w.empty_state("📊", "No study time in this range", "Try a longer range or log a session.")
        else:
            fig = go.Figure(go.Bar(x=tr["date"], y=tr["minutes"], marker=dict(color=p["iris"], cornerradius=6), hovertemplate="%{x|%a %d %b}: %{y:.0f} min<extra></extra>"))
            fig.add_hline(y=snap.user["daily_goal_minutes"], line_dash="dot", line_color=p["apricot"], annotation_text="goal", annotation_font_color=p["apricot"])
            w.show(w.style_fig(fig, 280))
    with c2, w.panel("an_score"):
        w.section("Productivity score", "Rolling 7-day score ending on each day")
        if tr["score"].isna().all():
            w.empty_state("📈", "No score yet", "The score appears after you log study time or finish tasks.")
        else:
            fig = go.Figure(go.Scatter(x=tr["date"], y=tr["score"], mode="lines", line=dict(color=p["aqua"], width=3, shape="spline"),
                                       fill="tozeroy", fillcolor="rgba(61,219,192,.10)", connectgaps=False, hovertemplate="%{x|%d %b}: %{y}<extra></extra>"))
            fig.update_yaxes(range=[0, 100])
            w.show(w.style_fig(fig, 280))
    st.write("")
    with w.panel("an_heat"):
        w.section("Productivity calendar", "Each square is a day; brighter means closer to or above your daily goal")
        w.show(_heatmap(snap))


def _subjects(snap, days: int):
    p = palette()
    summ = metrics.subject_summary(snap.sessions, snap.subjects, snap.today - timedelta(days=days - 1), snap.today)
    with w.panel("an_sub"):
        w.section("Subject comparison", f"Last {days} days")
        if summ.empty or summ["minutes"].sum() == 0:
            w.empty_state("📚", "No subject data in this range", "Study sessions linked to a subject appear here.")
            return
        c1, c2 = st.columns([5, 7], gap="medium")
        with c1:
            fig = go.Figure(go.Bar(x=summ["minutes"], y=summ["subject"], orientation="h", marker=dict(color=list(summ["color"]), cornerradius=6),
                                   hovertemplate="%{y}: %{x:.0f} min<extra></extra>"))
            fig.update_yaxes(autorange="reversed")
            w.show(w.style_fig(fig, 80 + 44 * len(summ)))
        with c2:
            show = pd.DataFrame({"Subject": summ["subject"], "Time": summ["minutes"].map(fmt_minutes), "Sessions": summ["sessions"],
                                 "Avg session": summ["avg_session"].map(fmt_minutes), "Focus": summ["focus_ratio"].map(fmt_pct),
                                 "Goal progress": summ["progress"].map(fmt_pct)})
            st.dataframe(show, hide_index=True, use_container_width=True)


def _tasks(snap):
    p = palette()
    t = snap.tasks
    if t.empty:
        w.empty_state("✅", "No tasks yet", "Task completion charts appear once you add tasks.")
        return
    c1, c2 = st.columns([4, 8], gap="medium")
    with c1, w.panel("an_status"):
        w.section("Task status", "")
        vc = t["status"].value_counts()
        cmap = {"Completed": p["aqua"], "Overdue": p["rose"], "In Progress": p["sky"], "Pending": p["muted"]}
        fig = go.Figure(go.Pie(labels=vc.index, values=vc.values, hole=0.65, sort=False, marker=dict(colors=[cmap[s] for s in vc.index], line=dict(color=p["surface"], width=3)), textinfo="value"))
        w.show(w.style_fig(fig, 270, legend=True))
    with c2, w.panel("an_weekly"):
        w.section("Tasks completed per week", "")
        done = t[t["completed_at"].notna()].copy()
        if done.empty:
            w.empty_state("📅", "Nothing completed yet", "Completed tasks are counted here by week.")
        else:
            done["week"] = done["completed_at"].dt.to_period("W").dt.start_time
            wk = done.groupby("week").size()
            fig = go.Figure(go.Bar(x=wk.index, y=wk.values, marker=dict(color=p["aqua"], cornerradius=6), hovertemplate="Week of %{x|%d %b}: %{y}<extra></extra>"))
            w.show(w.style_fig(fig, 270))
    fin = t[(t["status"] == "Completed") & t["estimated_minutes"].notna() & (t["actual_minutes"] > 0)]
    if not fin.empty:
        with w.panel("an_est"):
            w.section("Estimated vs actual time", "Finished tasks only")
            ratio = fin["actual_minutes"].sum() / fin["estimated_minutes"].sum()
            st.markdown(f"Across **{len(fin)}** finished tasks you used **{ratio:.0%}** of the time you estimated.")


def _focus(snap, days: int):
    p = palette()
    start = snap.today - timedelta(days=days - 1)
    s = metrics.in_window(snap.sessions, start, snap.today)
    if s.empty:
        w.empty_state("⏱️", "No sessions in this range", "Focus patterns appear after a few sessions.")
        return
    ist, pa, fr = metrics.interruption_stats(s), metrics.planned_vs_actual(s), metrics.focus_ratio(s)[0]
    ai = metrics.active_idle_totals(s)
    cols = st.columns(4, gap="medium")
    cols[0].markdown(w.stat_card("Focus ratio", fmt_pct(fr), "active vs idle, or planned vs kept", "aqua"), unsafe_allow_html=True)
    cols[1].markdown(w.stat_card("Interruptions", str(ist["total"]), f"{ist['per_session']:.1f} per session" if ist["per_session"] is not None else "", "warn"), unsafe_allow_html=True)
    cols[2].markdown(w.stat_card("Planned vs actual", fmt_pct(pa["ratio"]), f"{fmt_minutes(pa['actual'])} of {fmt_minutes(pa['planned'])}", "brand"), unsafe_allow_html=True)
    cols[3].markdown(w.stat_card("Idle time", fmt_minutes(ai["idle"]) if ai["idle"] is not None else "–", "tracked sessions only" if ai["idle"] is not None else "idle tracking was off", "info"), unsafe_allow_html=True)
    st.write("")
    hours = metrics.low_focus_hours(s)
    with w.panel("an_hours"):
        w.section("Focus by time of day", "Hours flagged in rose are clearly below your own average (3+ sessions needed)")
        colors = [p["rose"] if r["low_focus"] else p["iris"] for _, r in hours.iterrows()]
        fig = go.Figure()
        fig.add_bar(x=hours["hour"], y=hours["minutes"], marker=dict(color=colors, cornerradius=6), name="Minutes", hovertemplate="%{x}:00 · %{y:.0f} min<extra></extra>")
        fig.add_scatter(x=hours["hour"], y=hours["focus_ratio"] * 100, yaxis="y2", mode="lines+markers", name="Focus %", line=dict(color=p["aqua"], width=3), hovertemplate="Focus %{y:.0f}%<extra></extra>")
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 100], showgrid=False), xaxis=dict(dtick=1, title="Hour of day"))
        w.show(w.style_fig(fig, 300, legend=True))
        low = hours[hours["low_focus"]]
        if not low.empty:
            st.info("Lower-focus hours: " + ", ".join(f"{int(h):02d}:00" for h in low["hour"]) + ". Consider scheduling lighter tasks then.")
    st.write("")
    with w.panel("an_hist"):
        w.section("Focus-session history", "")
        hist = s.sort_values("start_time", ascending=False).head(200)
        st.dataframe(pd.DataFrame({"Start": hist["start_time"].dt.strftime("%d %b %Y %H:%M"), "Subject": hist["subject_name"], "Task": hist["task_title"],
                                   "Planned": hist["planned_minutes"].map(fmt_minutes), "Actual": hist["actual_minutes"].map(fmt_minutes),
                                   "Interruptions": hist["interruption_count"], "Status": hist["session_status"]}), hide_index=True, use_container_width=True)


def _ml(snap):
    uid = snap.user["id"]
    w.section("Experimental risk model", "Predicts which open tasks may end up late. Optional; nothing else in the app depends on it.")
    st.warning("Experimental. Predictions are shown only if the model beats a simple baseline on held-out, newer tasks. "
               "Results describe patterns in your past data, not facts about you.")
    if st.button("Run experiment", type="primary", icon=":material/science:"):
        with st.spinner("Training and evaluating on your task history…"):
            ds = ml.build_dataset(snap.tasks, snap.sessions)
            st.session_state["ml_report"] = (uid, ml.train_and_evaluate(ds))
    cached = st.session_state.get("ml_report")
    if not cached or cached[0] != uid:
        st.caption("Click “Run experiment” to evaluate.")
        return
    rep = cached[1]
    tone = {"validated": "good", "not_validated": "warn", "insufficient_data": "muted"}[rep.status]
    w.html(w.pill({"validated": "Validated vs baseline", "not_validated": "Not validated", "insufficient_data": "Not enough data"}[rep.status], tone))
    st.write(rep.message)
    if rep.imbalance_warning:
        st.caption(rep.imbalance_warning)
    if rep.status == "insufficient_data":
        return
    st.caption(f"Time-based split: trained on tasks due up to {rep.split['train_until']} ({rep.split['train']} tasks), tested on newer ones from {rep.split['test_from']} ({rep.split['test']} tasks, {rep.split['test_late']} late).")
    if rep.metrics:
        m = pd.DataFrame({"Precision": [rep.metrics["precision"], rep.baseline["precision"]], "Recall": [rep.metrics["recall"], rep.baseline["recall"]],
                          "F1": [rep.metrics["f1"], rep.baseline["f1"]]}, index=[rep.model_name, "Baseline (always predict majority)"]).round(2)
        c1, c2 = st.columns([6, 4], gap="medium")
        c1.dataframe(m, use_container_width=True)
        cm = pd.DataFrame(rep.confusion, index=["Actual on time", "Actual late"], columns=["Predicted on time", "Predicted late"])
        c2.dataframe(cm, use_container_width=True)
        p = palette()
        imp = rep.importances[:6]
        fig = go.Figure(go.Bar(x=[v for _, v in imp], y=[f.replace("_", " ") for f, _ in imp], orientation="h", marker=dict(color=p["iris"], cornerradius=6)))
        fig.update_yaxes(autorange="reversed")
        w.section("Most influential features", "Relative importance inside this model, not proof of cause")
        w.show(w.style_fig(fig, 260))
    if rep.status == "validated" and rep.predictions is not None and not rep.predictions.empty:
        w.section("Experimental risk for open tasks", "")
        pr = rep.predictions.copy()
        pr["deadline"] = pr["deadline"].dt.strftime("%d %b %Y")
        pr["risk_score"] = (pr["risk_score"] * 100).round(0).astype(int).astype(str) + "%"
        st.dataframe(pr.rename(columns={"title": "Task", "deadline": "Deadline", "risk": "Experimental risk", "risk_score": "Model score"}).drop(columns="task_id"), hide_index=True, use_container_width=True)
    with st.expander("Limitations"):
        for lim in rep.limitations:
            st.markdown(f"- {lim}")


def render() -> None:
    uid = state.user_id()
    snap = svc.load_snapshot(uid)
    w.page_header("Analytics", "Patterns in your study habits, calculated from your stored records.")
    if snap.settings["is_synthetic"]:
        w.banner("You are viewing synthetic demo data generated for demonstration – it is not real activity.")
    days = st.segmented_control("Range", [7, 14, 30, 90], default=30, format_func=lambda d: f"{d} days", label_visibility="collapsed") or 30
    tabs = st.tabs(["Overview", "Subjects", "Tasks", "Focus patterns", "Procrastination", "Experimental ML"])
    with tabs[0]: _overview(snap, days)
    with tabs[1]: _subjects(snap, days)
    with tabs[2]: _tasks(snap)
    with tabs[3]: _focus(snap, days)
    with tabs[4]:
        w.section("Procrastination indicators", "Observed patterns from the last 3 weeks, each with the data behind it")
        insights.indicators(svc.indicators(snap))
        st.write("")
        w.section("Suggestions", "")
        insights.recommendations(svc.recs(snap, repo.dismissed_recommendations(uid)), uid, "an", limit=6)
        if st.button("Restore dismissed suggestions"):
            repo.restore_recommendations(uid)
            st.rerun()
    with tabs[5]:
        _ml(snap)
