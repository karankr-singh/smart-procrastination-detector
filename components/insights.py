"""Render recommendations and procrastination indicators."""
from __future__ import annotations

import streamlit as st

from analytics.procrastination import NOTE
from components import widgets as w
from database import repositories as repo
from utils.formatting import esc

CAT_TONE = {"Tasks": "var(--rose)", "Goals": "var(--sky)", "Focus": "var(--aqua)", "Subjects": "var(--apricot)", "Weekly": "var(--iris)"}


def recommendations(recs, uid: int, prefix: str, limit: int = 4) -> None:
    if not recs:
        w.empty_state("✨", "No suggestions right now",
                      "Suggestions appear when your records show something worth acting on. Log a few sessions and tasks to get started.")
        return
    for r in recs[:limit]:
        with w.flat_box(f"{prefix}_{r.key}"):
            left, right = st.columns([6, 1.2], vertical_alignment="center")
            with left:
                w.html(f'<div class="spd-insight" style="--tone:{CAT_TONE.get(r.category, "var(--iris)")}">'
                       f'<div class="t">{esc(r.title)}</div><div class="b">{esc(r.body)}</div>'
                       f'<div class="w">Why you see this: {esc(r.reason)}</div></div>')
            with right:
                if st.button("Dismiss", key=f"dis_{prefix}_{r.key}", use_container_width=True):
                    repo.dismiss_recommendation(uid, r.key)
                    st.rerun()


def indicators(items) -> None:
    if not items:
        w.empty_state("🌤️", "No procrastination patterns detected",
                      "Nothing in your recent records stands out. Indicators appear only when your data shows a clear pattern.")
    for it in items:
        tone = "var(--rose)" if it.severity == "notable" else "var(--apricot)"
        with w.flat_box(f"ind_{it.key}"):
            data = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in it.data.items())
            w.html(f'<div class="spd-insight" style="--tone:{tone}"><div class="t">{esc(it.title)} '
                   f'{w.pill("Notable" if it.severity == "notable" else "Worth watching", "bad" if it.severity == "notable" else "warn")}</div>'
                   f'<div class="b"><b>Observed:</b> {esc(it.observed)}</div>'
                   f'<dl class="spd-kv">{data}</dl>'
                   f'<div class="b" style="margin-top:.5rem"><b>Possible explanation:</b> {esc(it.explanation)}</div>'
                   f'<div class="b"><b>Suggested improvement:</b> {esc(it.suggestion)}</div></div>')
    st.caption(NOTE)
