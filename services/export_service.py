"""CSV / ZIP / PDF exports. Everything exported comes straight from stored records."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

import pandas as pd

import config
from database import repositories as repo

EXPORT_SESSION_COLS = ["id", "start_time", "end_time", "subject_name", "task_title", "planned_minutes",
                       "actual_minutes", "active_minutes", "idle_minutes", "interruption_count", "session_status"]
EXPORT_TASK_COLS = ["id", "title", "subject_name", "priority", "status", "deadline", "estimated_minutes",
                    "actual_minutes", "postponement_count", "extension_count", "created_at", "completed_at"]


def export_frames(user_id: int) -> dict[str, pd.DataFrame]:
    sessions = repo.list_sessions_df(user_id, include_running=True)
    tasks = repo.list_tasks_df(user_id)
    return {"profile": pd.DataFrame([repo.get_user(user_id)]),
            "subjects": repo.list_subjects_df(user_id),
            "tasks": tasks[EXPORT_TASK_COLS],
            "sessions": sessions[EXPORT_SESSION_COLS],
            "activity_events": repo.list_events_df(user_id),
            "daily_analytics": repo.list_daily_df(user_id)}


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def personal_data_zip(user_id: int) -> bytes:
    """Every personal record as a ZIP of CSV files plus a short README."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, df in export_frames(user_id).items():
            z.writestr(f"{name}.csv", to_csv_bytes(df))
        z.writestr("README.txt", f"{config.APP_NAME} personal data export\nCreated: {datetime.now():%Y-%m-%d %H:%M}\n"
                                 "One CSV per table. Times are local time.\n")
    return buf.getvalue()


def report_pdf(summary: dict, user: dict, title: str, synthetic: bool = False) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from analytics.scoring import DISCLAIMER
    from utils.formatting import fmt_minutes, fmt_pct

    ink, iris = colors.HexColor("#1A1B3A"), colors.HexColor("#5B4CE6")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=ink, fontSize=22, alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=iris, fontSize=13, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("b", parent=ss["BodyText"], textColor=ink, fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#6B6F94"))

    def table(rows, widths, header=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F2FF")]),
                 ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DCDAF5")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), iris), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                      ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        t.setStyle(TableStyle(style))
        return t

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm,
                            bottomMargin=1.6 * cm, title=title, author=config.APP_NAME)
    sc = summary["score"]
    story = [Paragraph(escape(title), h1),
             Paragraph(f"{escape(user['username'])} · {summary['start']:%d %b %Y} – {summary['end']:%d %b %Y}", body)]
    if synthetic:
        story.append(Paragraph("<b>Synthetic demo data</b> – generated for demonstration, not real activity.", small))
    story += [Spacer(1, 8), Paragraph("Summary", h2)]
    ai = summary["active_idle"]
    kpis = [["Measure", "Value"],
            ["Total study time", fmt_minutes(summary["total_minutes"])],
            ["Study days", f"{summary['study_days']} of {summary['days']}"],
            ["Average per day", fmt_minutes(summary["avg_per_day"])],
            ["Target for the period", fmt_minutes(summary["goal_minutes"])],
            ["Sessions", str(summary["sessions"])],
            ["Task completion", f"{fmt_pct(summary['task_completion'])} ({summary['tasks_info']['completed']} of {summary['tasks_info']['relevant']})"
             if summary["task_completion"] is not None else "No tasks due"],
            ["Focus ratio", fmt_pct(summary["focus_ratio"])],
            ["Active / idle (tracked)", f"{fmt_minutes(ai['active'])} / {fmt_minutes(ai['idle'])}" if ai["active"] is not None else "Tracking was off"],
            ["Interruptions", str(summary["interruptions"]["total"])],
            ["Productivity score", f"{sc.score}/100" if sc.score is not None else "Not enough data"]]
    story.append(table(kpis, [7 * cm, 9.5 * cm]))
    story += [Spacer(1, 4), Paragraph(escape(DISCLAIMER), small), Paragraph("Score components", h2)]
    rows = [["Component", "Weight", "Value", "How it was measured"]]
    for c in sc.components:
        rows.append([c.label, f"{c.effective_weight:.0f}%" if c.available else "–", fmt_pct(c.value),
                     Paragraph(escape(c.explanation), small)])
    story.append(table(rows, [3.2 * cm, 1.8 * cm, 1.8 * cm, 9.7 * cm]))
    subj = summary["subjects"]
    if not subj.empty:
        story.append(Paragraph("By subject", h2))
        rows = [["Subject", "Time", "Sessions", "Focus", "Weekly goal"]]
        for _, r in subj.iterrows():
            rows.append([r["subject"], fmt_minutes(r["minutes"]), str(r["sessions"]), fmt_pct(r["focus_ratio"]),
                         fmt_minutes(r["target_minutes"]) if r["target_minutes"] else "–"])
        story.append(table(rows, [5.5 * cm, 3 * cm, 2.5 * cm, 2.5 * cm, 3 * cm]))
    sdf = summary["sessions_df"]
    if not sdf.empty:
        story.append(Paragraph(f"Sessions ({min(len(sdf), 40)} most recent of {len(sdf)})", h2))
        rows = [["Start", "Subject", "Planned", "Actual", "Status"]]
        for _, r in sdf.sort_values("start_time", ascending=False).head(40).iterrows():
            rows.append([r["start_time"].strftime("%d %b %H:%M"), r["subject_name"], fmt_minutes(r["planned_minutes"]),
                         fmt_minutes(r["actual_minutes"]), r["session_status"]])
        story.append(table(rows, [3.5 * cm, 5 * cm, 2.6 * cm, 2.6 * cm, 3.3 * cm]))
    story += [Spacer(1, 10), Paragraph(f"Generated by {config.APP_NAME} on {datetime.now():%d %b %Y, %H:%M}. "
                                       "All figures are calculated from your locally stored records.", small)]
    doc.build(story)
    return buf.getvalue()
