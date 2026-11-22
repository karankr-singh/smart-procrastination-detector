"""Design tokens and CSS for the app.

Design language: deep indigo ink surfaces, one iris accent for action, aqua for focus/progress,
apricot for caution, rose for risk. Sora for numerals and headings, Figtree for reading text.
"""
from __future__ import annotations

import streamlit as st

PALETTES = {
    "dark": {"bg": "#0D0F1E", "surface": "#151833", "raised": "#1C2040", "line": "#2A2F58", "text": "#ECEEFF",
             "muted": "#9AA0C8", "iris": "#8B7CFF", "aqua": "#3DDBC0", "apricot": "#FFB86B", "rose": "#FF6F91",
             "sky": "#5AB8FF", "glow": "rgba(139,124,255,.16)", "shadow": "0 12px 36px rgba(3,4,16,.45)",
             "track": "#262B52", "on_accent": "#0D0F1E"},
    "light": {"bg": "#F6F5FF", "surface": "#FFFFFF", "raised": "#F0EEFF", "line": "#DCDAF5", "text": "#1A1B3A",
              "muted": "#62668F", "iris": "#5B4CE6", "aqua": "#0E9F85", "apricot": "#C9731B", "rose": "#D93F66",
              "sky": "#2F7FD8", "glow": "rgba(91,76,230,.10)", "shadow": "0 10px 30px rgba(70,60,160,.12)",
              "track": "#E4E1FA", "on_accent": "#FFFFFF"},
}


def theme_type() -> str:
    try:
        t = st.context.theme.type
        return t if t in PALETTES else "dark"
    except Exception:
        return "dark"


def palette() -> dict:
    return PALETTES[theme_type()]


def _css(p: dict) -> str:
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Sora:wght@500;600;700&display=swap');
:root {{
  --bg:{p['bg']}; --surface:{p['surface']}; --raised:{p['raised']}; --line:{p['line']}; --text:{p['text']};
  --muted:{p['muted']}; --iris:{p['iris']}; --aqua:{p['aqua']}; --apricot:{p['apricot']}; --rose:{p['rose']};
  --sky:{p['sky']}; --track:{p['track']}; --shadow:{p['shadow']}; --on-accent:{p['on_accent']};
  --display:'Sora','Segoe UI',system-ui,sans-serif; --body:'Figtree','Segoe UI',system-ui,sans-serif;
}}
html, body, .stApp, [class*="css"] {{ font-family: var(--body); }}
.stApp {{ background: radial-gradient(1100px 520px at 8% -8%, {p['glow']}, transparent 60%), var(--bg); color: var(--text); }}
[data-testid="stHeader"] {{ background: transparent; }}
footer, #MainMenu {{ visibility: hidden; }}
.block-container {{ max-width: 1240px; padding-top: 2.2rem; padding-bottom: 4rem; }}
h1, h2, h3, h4 {{ font-family: var(--display) !important; letter-spacing: -0.01em; color: var(--text); }}
h1 {{ font-size: 2rem !important; font-weight: 700 !important; }}
h3 {{ font-size: 1.05rem !important; font-weight: 600 !important; }}
p, li, label, .stMarkdown {{ color: var(--text); }}
small, .stCaption, [data-testid="stCaptionContainer"] {{ color: var(--muted) !important; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: var(--surface); border-right: 1px solid var(--line); }}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {{
  border-radius: 12px; margin: 2px 0; padding: .45rem .75rem; color: var(--muted); font-weight: 500; transition: background .15s, color .15s; }}
[data-testid="stSidebarNavLink"]:hover {{ background: var(--raised); color: var(--text); }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: var(--raised); color: var(--text); box-shadow: inset 3px 0 0 var(--iris); font-weight: 600; }}

/* panels (st.container(key="panel_*")) */
[class*="st-key-panel"] {{ background: var(--surface); border: 1px solid var(--line); border-radius: 22px;
  padding: 1.25rem 1.35rem; box-shadow: var(--shadow); }}
[class*="st-key-flat"] {{ background: transparent; border: 1px solid var(--line); border-radius: 18px; padding: .9rem 1.1rem; }}

/* buttons */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
  border-radius: 12px; border: 1px solid var(--line); background: var(--raised); color: var(--text);
  font-weight: 600; padding: .5rem 1rem; transition: transform .12s ease, border-color .15s, background .15s; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color: var(--iris); color: var(--text); }}
.stButton > button:active {{ transform: scale(.98); }}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"],
.stDownloadButton > button[kind="primary"] {{ background: var(--iris); border-color: var(--iris); color: var(--on-accent); }}
.stButton > button[kind="primary"]:hover {{ filter: brightness(1.08); color: var(--on-accent); }}
.stButton > button:focus-visible {{ outline: 2px solid var(--aqua); outline-offset: 2px; }}

/* inputs */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], .stDateInput > div > div, .stTimeInput > div > div {{
  border-radius: 12px !important; border-color: var(--line) !important; background: var(--raised) !important; }}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea {{ color: var(--text); }}
.stTabs [data-baseweb="tab-list"] {{ gap: .25rem; border-bottom: 1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{ border-radius: 10px 10px 0 0; color: var(--muted); font-weight: 600; padding: .55rem 1rem; }}
.stTabs [aria-selected="true"] {{ color: var(--text); }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--iris); height: 3px; border-radius: 3px; }}
[data-testid="stExpander"] {{ border: 1px solid var(--line); border-radius: 16px; background: transparent; }}
[data-testid="stDataFrame"] {{ border-radius: 14px; overflow: hidden; border: 1px solid var(--line); }}
[data-testid="stAlert"] {{ border-radius: 14px; }}
.stProgress > div > div > div > div {{ background: linear-gradient(90deg, var(--iris), var(--aqua)); }}

/* custom components */
.spd-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; margin-bottom:1.4rem; flex-wrap:wrap; }}
.spd-head h1 {{ margin:0; padding:0; line-height:1.1; }}
.spd-sub {{ color: var(--muted); margin-top:.35rem; font-size:1rem; max-width:62ch; }}
.spd-title {{ font-family: var(--display); font-weight:600; font-size:1.02rem; margin:0 0 .15rem 0; color:var(--text); }}
.spd-note {{ color: var(--muted); font-size:.86rem; margin:0 0 .8rem 0; }}
.spd-stat {{ background: var(--surface); border:1px solid var(--line); border-radius:20px; padding:1.05rem 1.2rem; height:100%;
  box-shadow: var(--shadow); position:relative; overflow:hidden; }}
.spd-stat::before {{ content:""; position:absolute; left:0; top:18%; bottom:18%; width:3px; border-radius:0 3px 3px 0; background:var(--accent, var(--iris)); }}
.spd-stat .l {{ color:var(--muted); font-size:.86rem; font-weight:500; }}
.spd-stat .v {{ font-family:var(--display); font-size:1.85rem; font-weight:700; line-height:1.15; margin-top:.2rem; color:var(--text); }}
.spd-stat .s {{ color:var(--muted); font-size:.82rem; margin-top:.15rem; }}
.spd-pill {{ display:inline-flex; align-items:center; gap:.4rem; padding:.18rem .65rem; border-radius:999px; font-size:.78rem; font-weight:600;
  background: color-mix(in srgb, var(--tone, var(--muted)) 16%, transparent); color: var(--tone, var(--muted));
  border:1px solid color-mix(in srgb, var(--tone, var(--muted)) 35%, transparent); white-space:nowrap; }}
.spd-dot {{ width:.6rem; height:.6rem; border-radius:50%; display:inline-block; background:var(--c, var(--iris)); flex:none; }}
.spd-row {{ display:flex; align-items:center; gap:.85rem; padding:.7rem .2rem; border-bottom:1px solid var(--line); }}
.spd-row:last-child {{ border-bottom:none; }}
.spd-row .main {{ flex:1; min-width:0; }}
.spd-row .t {{ font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.spd-row .m {{ color:var(--muted); font-size:.84rem; }}
.spd-row .r {{ text-align:right; font-family:var(--display); font-weight:600; font-size:.95rem; }}
.spd-bar {{ height:8px; background:var(--track); border-radius:999px; overflow:hidden; }}
.spd-bar > i {{ display:block; height:100%; border-radius:999px; background:var(--c, var(--iris)); }}
.spd-comp {{ margin:.7rem 0 0 0; }}
.spd-comp .h {{ display:flex; justify-content:space-between; font-size:.88rem; font-weight:600; margin-bottom:.3rem; }}
.spd-comp .h span:last-child {{ color:var(--muted); font-weight:500; }}
.spd-comp .e {{ color:var(--muted); font-size:.8rem; margin-top:.25rem; line-height:1.35; }}
.spd-empty {{ text-align:center; padding:2.2rem 1rem; border:1px dashed var(--line); border-radius:20px; color:var(--muted); }}
.spd-empty .i {{ font-size:1.8rem; }}
.spd-empty .t {{ font-family:var(--display); color:var(--text); font-weight:600; margin:.4rem 0 .2rem; }}
.spd-banner {{ border:1px solid color-mix(in srgb, var(--apricot) 45%, transparent); background: color-mix(in srgb, var(--apricot) 11%, transparent);
  color:var(--text); border-radius:14px; padding:.6rem 1rem; margin-bottom:1rem; font-size:.9rem; }}
.spd-insight {{ border-left:3px solid var(--tone, var(--iris)); padding:.15rem 0 .15rem .9rem; margin:.2rem 0 .1rem; }}
.spd-insight .t {{ font-weight:700; }}
.spd-insight .b {{ margin-top:.15rem; }}
.spd-insight .w {{ color:var(--muted); font-size:.82rem; margin-top:.3rem; }}
.spd-kv {{ display:grid; grid-template-columns:max-content 1fr; gap:.15rem .9rem; font-size:.86rem; margin-top:.4rem; }}
.spd-kv dt {{ color:var(--muted); }} .spd-kv dd {{ margin:0; font-weight:600; }}
.spd-cycle {{ display:flex; gap:.45rem; justify-content:center; margin-top:.9rem; }}
.spd-cycle i {{ width:.7rem; height:.7rem; border-radius:50%; background:var(--track); display:block; }}
.spd-cycle i.on {{ background:var(--aqua); }}
.spd-timer {{ position:relative; display:flex; justify-content:center; }}
.spd-timer .c {{ position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
.spd-timer .clock {{ font-family:var(--display); font-weight:700; font-size:3.4rem; letter-spacing:-.02em; }}
.spd-timer .phase {{ color:var(--muted); font-weight:600; margin-top:.1rem; }}
@media (max-width: 760px) {{ .block-container {{ padding: 1.2rem .9rem 3rem; }} h1 {{ font-size:1.6rem !important; }}
  .spd-timer .clock {{ font-size:2.6rem; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; animation:none !important; }} }}
"""


def inject() -> None:
    st.markdown(f"<style>{_css(palette())}</style>", unsafe_allow_html=True)
