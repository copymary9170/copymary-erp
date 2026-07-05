import streamlit as st
from src.config import COLORS


def apply_modern_styles():
    st.markdown(f'''<style>
    :root {{ --p:{COLORS['primary']}; --a:{COLORS['accent']}; --bg:{COLORS['background']}; --surface:{COLORS['surface']}; --text:{COLORS['text']}; --muted:{COLORS['muted']}; --border:{COLORS['border']}; }}
    html,body,[class*="css"]{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
    .stApp{{background:radial-gradient(circle at top right,rgba(109,74,255,.09),transparent 30%),radial-gradient(circle at bottom left,rgba(34,166,161,.08),transparent 26%),var(--bg);color:var(--text)}}
    .block-container{{padding-top:1rem;padding-bottom:2.8rem;max-width:1440px}}
    [data-testid="stHeader"]{{background:transparent}}
    [data-testid="stSidebar"]{{background:linear-gradient(180deg,#fff 0%,#f7f8ff 100%);border-right:1px solid var(--border)}}
    [data-testid="stSidebar"]>div:first-child{{padding:1.35rem 1rem 1rem}}
    [data-testid="stSidebar"] h1{{font-size:1.25rem;letter-spacing:-.02em;margin-bottom:.2rem}}
    [data-testid="stSidebar"] [role="radiogroup"]{{gap:.25rem}}
    [data-testid="stSidebar"] [role="radiogroup"] label{{padding:.45rem .55rem;border-radius:11px;transition:.16s ease}}
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{{background:rgba(109,74,255,.07)}}
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){{background:linear-gradient(135deg,rgba(109,74,255,.12),rgba(34,166,161,.10));box-shadow:inset 0 0 0 1px rgba(109,74,255,.12)}}
    h1,h2,h3,h4{{color:var(--text);letter-spacing:-.025em}}
    h1{{font-weight:800;line-height:1.08}}
    .cm-hero{{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:space-between;min-height:230px;padding:2rem 2.25rem;border-radius:26px;background:linear-gradient(135deg,#ffffff 0%,#f8f7ff 52%,#edfdfb 100%);border:1px solid rgba(109,74,255,.12);box-shadow:0 20px 45px rgba(31,41,55,.09);margin-bottom:1rem}}
    .cm-hero:before{{content:"";position:absolute;width:300px;height:300px;border-radius:50%;right:-100px;top:-150px;background:linear-gradient(135deg,rgba(109,74,255,.22),rgba(34,166,161,.18))}}
    .cm-hero__content{{position:relative;z-index:2;max-width:850px}}
    .cm-hero__brand{{display:inline-flex;align-items:center;gap:.55rem;font-size:.72rem;font-weight:800;letter-spacing:.09em;color:var(--p);text-transform:uppercase;margin-bottom:1rem}}
    .cm-hero__brand span{{display:grid;place-items:center;width:30px;height:30px;border-radius:10px;background:linear-gradient(135deg,var(--p),var(--a));color:#fff;letter-spacing:0;box-shadow:0 8px 18px rgba(109,74,255,.25)}}
    .cm-hero h1{{font-size:clamp(2.3rem,4vw,4.2rem);margin:0 0 .7rem;line-height:1.02}}
    .cm-hero p{{font-size:1.06rem;line-height:1.65;color:var(--muted);margin:0;max-width:760px}}
    .cm-hero__mark{{position:relative;z-index:1;display:grid;place-items:center;width:150px;height:150px;border-radius:38px;background:linear-gradient(135deg,var(--p),var(--a));color:#fff;font-size:3.2rem;font-weight:900;letter-spacing:-.08em;box-shadow:0 22px 42px rgba(109,74,255,.28);transform:rotate(7deg);margin-right:2rem}}
    [data-testid="stMetric"]{{background:rgba(255,255,255,.94);border:1px solid var(--border);border-radius:18px;padding:1rem 1.1rem;min-height:116px;box-shadow:0 6px 20px rgba(31,41,55,.07);transition:.18s ease}}
    [data-testid="stMetric"]:hover{{transform:translateY(-2px);box-shadow:0 12px 30px rgba(31,41,55,.1)}}
    [data-testid="stMetricLabel"]{{color:var(--muted);font-weight:650}}
    [data-testid="stMetricValue"]{{font-size:clamp(1.45rem,2vw,2.15rem);font-weight:800;color:var(--text)}}
    [data-testid="stVerticalBlockBorderWrapper"]{{border-radius:20px;border-color:var(--border)!important;background:rgba(255,255,255,.92);box-shadow:0 8px 24px rgba(31,41,55,.06)}}
    .stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{{border-radius:12px;min-height:2.7rem;font-weight:700;transition:.16s ease}}
    .stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover{{transform:translateY(-1px);box-shadow:0 8px 18px rgba(109,74,255,.16)}}
    button[kind="primary"]{{background:linear-gradient(135deg,var(--p),var(--a))!important;border:none!important;color:#fff!important;box-shadow:0 8px 20px rgba(109,74,255,.22)}}
    input,textarea,[data-baseweb="select"]>div{{border-radius:12px!important}}
    [data-baseweb="tab-list"]{{gap:.4rem;background:rgba(255,255,255,.8);border:1px solid var(--border);border-radius:14px;padding:.35rem;box-shadow:0 5px 18px rgba(31,41,55,.05)}}
    [data-baseweb="tab"]{{border-radius:10px;font-weight:700}}
    [data-baseweb="tab"][aria-selected="true"]{{background:linear-gradient(135deg,rgba(109,74,255,.12),rgba(34,166,161,.12));color:var(--p)}}
    [data-testid="stAlert"]{{border-radius:16px;box-shadow:0 5px 16px rgba(31,41,55,.05)}}
    .cm-card{{background:rgba(255,255,255,.96)!important;border-radius:20px!important;box-shadow:0 8px 24px rgba(31,41,55,.07)!important;transition:.18s ease;border:1px solid rgba(109,74,255,.08)!important}}
    .cm-card:hover{{transform:translateY(-3px);box-shadow:0 16px 34px rgba(31,41,55,.11)!important}}
    .cm-eyebrow{{display:inline-flex;background:rgba(109,74,255,.09);border:1px solid rgba(109,74,255,.14);border-radius:999px;padding:.3rem .55rem;font-size:.7rem!important;text-transform:uppercase}}
    @media(max-width:900px){{.cm-hero__mark{{display:none}}.cm-hero{{min-height:auto}}}}
    @media(max-width:768px){{.block-container{{padding:.7rem .8rem 2rem}}.cm-hero{{padding:1.35rem;border-radius:20px}}.cm-hero h1{{font-size:2.25rem}}[data-testid="stMetric"]{{min-height:auto}}}}
    </style>''',unsafe_allow_html=True)
