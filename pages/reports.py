"""Reports: daily / weekly / monthly summaries with CSV and PDF export."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import service as svc
from components import widgets as w
from components.theme import palette
from services import export_service as ex
from utils import state
from utils.formatting import fmt_minutes, fmt_pct


def period_bounds(kind: str, anchor: date) -> tuple[date, date]:
    if kind == "Daily":
        return anchor, anchor
    if kind == "Weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    return anchor.replace(day=1), anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])


def render() -> None:
    uid = state.user_id()
    snap = svc.load_snapshot(uid)
    p = palette()
    w.page_header("Reports", "A summary for any day, week or month, ready to download.")
    c1, c2 = st.columns([2, 2], vertical_alignment="bottom")
    kind = c1.segmented_control("Report", ["Daily", "Weekly", "Monthly"], default="Weekly", label_visibility="collapsed") or "Weekly"
    anchor = c2.date_input("Date in period", snap.today, max_value=snap.today)
    start, end = period_bounds(kind, anchor)
    summ = svc.period_summary(snap, start, end)
    title = f"{kind} productivity report"
    if snap.settings["is_synthetic"]:
        w.banner("Synthetic demo data: this report does not describe real activity.")
    st.caption(f"{start:%d %b %Y} – {end:%d %b %Y}")

    if summ["sessions"] == 0 and summ["score"].score is None:
        w.empty_state("🗒️", "Nothing recorded in this period", "Pick another date, or log study sessions and tasks.")
        return

    cols = st.columns(4, gap="medium")
    sc = summ["score"]
    cols[0].markdown(w.stat_card("Study time", fmt_minutes(summ["total_minutes"]), f"{summ['study_days']} of {summ['days']} days · {summ['sessions']} sessions", "brand"), unsafe_allow_html=True)
    cols[1].markdown(w.stat_card("Goal", fmt_pct(summ["total_minutes"] / summ["goal_minutes"] if summ["goal_minutes"] else None), f"{fmt_minutes(summ['goal_minutes'])} target", "aqua"), unsafe_allow_html=True)
    tc = summ["task_completion"]
    cols[2].markdown(w.stat_card("Task completion", fmt_pct(tc), f"{summ['tasks_info']['completed']} of {summ['tasks_info']['relevant']} tasks" if tc is not None else "no tasks due", "good"), unsafe_allow_html=True)
    cols[3].markdown(w.stat_card("Productivity score", f"{sc.score}" if sc.score is not None else "–", "out of 100", "warn"), unsafe_allow_html=True)
    st.write("")

    a, b = st.columns([7, 5], gap="medium")
    with a, w.panel("rp_days"):
        w.section("Study time by day", "")
        d = summ["daily"]
        fig = go.Figure(go.Bar(x=[x.strftime("%d %b") for x in d.index], y=d.values, marker=dict(color=p["iris"], cornerradius=6), hovertemplate="%{x}: %{y:.0f} min<extra></extra>"))
        fig.add_hline(y=snap.user["daily_goal_minutes"], line_dash="dot", line_color=p["apricot"])
        w.show(w.style_fig(fig, 260))
    with b, w.panel("rp_comp"):
        w.section("Score breakdown", "")
        w.html(w.component_bars(sc.components))
    st.write("")
    with w.panel("rp_sub"):
        w.section("By subject", "")
        sub = summ["subjects"]
        if sub.empty or sub["minutes"].sum() == 0:
            st.caption("No subject time in this period.")
        else:
            st.dataframe(pd.DataFrame({"Subject": sub["subject"], "Time": sub["minutes"].map(fmt_minutes), "Sessions": sub["sessions"],
                                       "Focus": sub["focus_ratio"].map(fmt_pct)}), hide_index=True, use_container_width=True)

    st.write("")
    with w.panel("rp_dl"):
        w.section("Export", "Exports contain exactly the records shown in this report.")
        sdf = summ["sessions_df"]
        csv_df = sdf[ex.EXPORT_SESSION_COLS] if not sdf.empty else pd.DataFrame(columns=ex.EXPORT_SESSION_COLS)
        d1, d2 = st.columns(2)
        d1.download_button("Download sessions (CSV)", ex.to_csv_bytes(csv_df), f"sessions_{start}_{end}.csv", "text/csv", use_container_width=True, icon=":material/table:")
        try:
            pdf = ex.report_pdf(summ, snap.user, title, snap.settings["is_synthetic"])
            d2.download_button("Download report (PDF)", pdf, f"{kind.lower()}_report_{start}.pdf", "application/pdf", type="primary", use_container_width=True, icon=":material/picture_as_pdf:")
        except Exception as exc:  # report generation must never break the page
            d2.error(f"Couldn't build the PDF: {exc}")
