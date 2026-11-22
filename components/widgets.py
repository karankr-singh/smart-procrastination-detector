"""Reusable UI building blocks."""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.theme import palette
from utils.formatting import esc, fmt_minutes

TONES = {"good": "var(--aqua)", "warn": "var(--apricot)", "bad": "var(--rose)", "info": "var(--sky)",
         "brand": "var(--iris)", "muted": "var(--muted)"}


def flat(s: str) -> str:
    """Collapse indentation so markdown doesn't treat the HTML as a code block."""
    return "".join(line.strip() for line in s.strip().splitlines())


def html(s: str) -> None:
    st.markdown(flat(s), unsafe_allow_html=True)


def panel(name: str):
    return st.container(key=f"panel_{name}")


def flat_box(name: str):
    return st.container(key=f"flat_{name}")


def page_header(title: str, subtitle: str = "", right: str = "") -> None:
    html(f'<div class="spd-head"><div><h1>{esc(title)}</h1>'
         f'{f"<div class=spd-sub>{esc(subtitle)}</div>" if subtitle else ""}</div><div>{right}</div></div>')


def section(title: str, note: str = "") -> None:
    html(f'<div class="spd-title">{esc(title)}</div>' + (f'<div class="spd-note">{esc(note)}</div>' if note else ""))


def pill(text: str, tone: str = "muted") -> str:
    return f'<span class="spd-pill" style="--tone:{TONES.get(tone, tone)}">{esc(text)}</span>'


def dot(color: str) -> str:
    return f'<span class="spd-dot" style="--c:{esc(color)}"></span>'


def stat_card(label: str, value: str, sub: str = "", accent: str = "brand") -> str:
    return flat(f'<div class="spd-stat" style="--accent:{TONES.get(accent, accent)}"><div class="l">{esc(label)}</div>'
                f'<div class="v">{esc(value)}</div><div class="s">{esc(sub)}</div></div>')


def bar(fraction: Optional[float], color: str = "var(--iris)") -> str:
    pct = 0 if fraction is None else max(0.0, min(1.0, fraction)) * 100
    return f'<div class="spd-bar"><i style="width:{pct:.1f}%;--c:{color}"></i></div>'


def empty_state(icon: str, title: str, body: str) -> None:
    html(f'<div class="spd-empty"><div class="i">{icon}</div><div class="t">{esc(title)}</div><div>{esc(body)}</div></div>')


def banner(text: str) -> None:
    html(f'<div class="spd-banner">{esc(text)}</div>')


def score_ring(score: Optional[int], size: int = 220, caption: str = "out of 100") -> str:
    r, c = 84, 2 * math.pi * 84
    pct = 0 if score is None else max(0, min(score, 100)) / 100
    center = "–" if score is None else str(score)
    sub = "no data yet" if score is None else caption
    return flat(f'''<div style="display:flex;justify-content:center"><svg width="{size}" height="{size}" viewBox="0 0 200 200" role="img" aria-label="Productivity score {center}">
<defs><linearGradient id="ringg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--iris)"/><stop offset="1" style="stop-color:var(--aqua)"/></linearGradient></defs>
<circle cx="100" cy="100" r="{r}" fill="none" style="stroke:var(--track)" stroke-width="14"/>
<circle cx="100" cy="100" r="{r}" fill="none" stroke="url(#ringg)" stroke-width="14" stroke-linecap="round" stroke-dasharray="{c * pct:.2f} {c:.2f}" transform="rotate(-90 100 100)"/>
<text x="100" y="108" text-anchor="middle" style="font-family:var(--display);font-weight:700;font-size:58px;fill:var(--text)">{center}</text>
<text x="100" y="132" text-anchor="middle" style="font-family:var(--body);font-size:13px;fill:var(--muted)">{sub}</text></svg></div>''')


def timer_ring(progress: float, clock: str, phase: str, tone: str = "var(--iris)", size: int = 300) -> str:
    r, c = 108, 2 * math.pi * 108
    return flat(f'''<div class="spd-timer" style="height:{size}px"><svg width="{size}" height="{size}" viewBox="0 0 260 260">
<circle cx="130" cy="130" r="{r}" fill="none" style="stroke:var(--track)" stroke-width="12"/>
<circle cx="130" cy="130" r="{r}" fill="none" style="stroke:{tone}" stroke-width="12" stroke-linecap="round" stroke-dasharray="{c * max(0.0, min(progress, 1.0)):.2f} {c:.2f}" transform="rotate(-90 130 130)"/></svg>
<div class="c"><div class="clock">{clock}</div><div class="phase">{esc(phase)}</div></div></div>''')


def component_bars(components) -> str:
    out = []
    for comp in components:
        if comp.available:
            head = f'<span>{esc(comp.label)}</span><span>{comp.value * 100:.0f}% · counts for {comp.effective_weight:.0f}</span>'
            body = bar(comp.value, "var(--aqua)" if comp.value >= 0.66 else "var(--apricot)" if comp.value >= 0.33 else "var(--rose)")
        else:
            head = f'<span>{esc(comp.label)}</span><span>no data</span>'
            body = bar(0)
        out.append(f'<div class="spd-comp"><div class="h">{head}</div>{body}<div class="e">{esc(comp.explanation)}</div></div>')
    return flat("".join(out))


def session_rows(df: pd.DataFrame, limit: int = 6) -> str:
    rows = []
    tone = {"Completed": "good", "Stopped Early": "warn", "Manual": "info", "Abandoned": "bad"}
    for _, r in df.sort_values("start_time", ascending=False).head(limit).iterrows():
        what = r["task_title"] or r["subject_name"]
        rows.append(f'<div class="spd-row">{dot(r["subject_color"])}<div class="main"><div class="t">{esc(what)}</div>'
                    f'<div class="m">{esc(r["subject_name"])} · {r["start_time"]:%a %d %b, %H:%M}</div></div>'
                    f'<div>{pill(r["session_status"], tone.get(r["session_status"], "muted"))}</div>'
                    f'<div class="r">{fmt_minutes(r["actual_minutes"])}</div></div>')
    return flat("".join(rows))


def style_fig(fig: go.Figure, height: int = 300, legend: bool = False) -> go.Figure:
    p = palette()
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=10, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Figtree, Segoe UI, sans-serif", color=p["muted"], size=12),
                      showlegend=legend, legend=dict(orientation="h", y=1.12, x=0, font=dict(color=p["text"])),
                      hoverlabel=dict(bgcolor=p["raised"], bordercolor=p["line"], font=dict(color=p["text"], family="Figtree")),
                      colorway=[p["iris"], p["aqua"], p["apricot"], p["rose"], p["sky"]])
    fig.update_xaxes(gridcolor=p["line"], zeroline=False, linecolor=p["line"], showgrid=False)
    fig.update_yaxes(gridcolor=p["line"], zeroline=False, linecolor="rgba(0,0,0,0)")
    return fig


def show(fig: go.Figure, key: Optional[str] = None) -> None:
    st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False}, key=key)
