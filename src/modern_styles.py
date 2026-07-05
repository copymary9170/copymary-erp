import streamlit as st
from src.config import COLORS

def apply_modern_styles():
    st.markdown(f'''<style>
    :root {{ --p:{COLORS['primary']}; --a:{COLORS['accent']}; --bg:{COLORS['background']}; --surface:{COLORS['surface']}; --text:{COLORS['text']}; --muted:{COLORS['muted']}; --border:{COLORS['border']}; }}
    html,body,[class*="css"]{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
    .stApp{{background:radial-gradient(circle at top right,rgba(109,74,255,.08),transparent 32%),radial-gradient(circle at bottom left,rgba(34,166,161,.07),transparent 28%),var(--bg);color:var(--text)}}
    .block-container{{padding-top:1.25rem;padding-bottom:2.5rem;max-width:1440px}}
    [data-testid="stHeader"]{{background:transparent}}
    [data-testid="stSidebar"]{{background:linear-gradient(180deg,#fff 0%,#f5f7ff 100%);border-right:1px solid var(--border)}}
    [data-testid="stSidebar"] h1{{font-size:1.25rem;letter-spacing:-.02em}}
    h1,h2,h3,h4{{color:var(--text);letter-spacing:-.025em}}
    h1{{font-weight:800;line-height:1.08}}
    [data-testid="stMetric"]{{background:rgba(255,255,255,.92);border:1px solid var(--border);border-radius:18px;padding:1rem 1.1rem;min-height:116px;box-shadow:0 6px 20px rgba(31,41,55,.07);transition:.18s ease}}
    [data-testid="stMetric"]:hover{{transform:translateY(-2px);box-shadow:0 12px 30px rgba(31,41,55,.1)}}
    [data-testid="stMetricLabel"]{{color:var(--muted);font-weight:650}}
    [data-testid="stMetricValue"]{{font-size:clamp(1.45rem,2vw,2.15rem);font-weight:800;color:var(--text)}}
    [data-testid="stVerticalBlockBorderWrapper"]{{border-radius:18px;border-color:var(--border)!important;background:rgba(255,255,255,.9);box-shadow:0 5px 18px rgba(31,41,55,.06)}}
    .stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{{border-radius:12px;min-height:2.7rem;font-weight:700;transition:.16s ease}}
    .stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover{{transform:translateY(-1px);box-shadow:0 8px 18px rgba(109,74,255,.16)}}
    button[kind="primary"]{{background:linear-gradient(135deg,var(--p),var(--a))!important;border:none!important;color:#fff!important;box-shadow:0 8px 20px rgba(109,74,255,.22)}}
    input,textarea,[data-baseweb="select"]>div{{border-radius:12px!important}}
    [data-baseweb="tab-list"]{{gap:.4rem;background:rgba(255,255,255,.75);border:1px solid var(--border);border-radius:14px;padding:.35rem;box-shadow:0 5px 18px rgba(31,41,55,.05)}}
    [data-baseweb="tab"]{{border-radius:10px;font-weight:700}}
    [data-baseweb="tab"][aria-selected="true"]{{background:linear-gradient(135deg,rgba(109,74,255,.12),rgba(34,166,161,.12));color:var(--p)}}
    [data-testid="stAlert"]{{border-radius:14px;box-shadow:0 4px 14px rgba(31,41,55,.05)}}
    .cm-card{{background:rgba(255,255,255,.94)!important;border-radius:18px!important;box-shadow:0 6px 20px rgba(31,41,55,.07)!important;transition:.18s ease}}
    .cm-card:hover{{transform:translateY(-2px);box-shadow:0 12px 30px rgba(31,41,55,.1)!important}}
    .cm-eyebrow{{display:inline-flex;background:rgba(109,74,255,.09);border:1px solid rgba(109,74,255,.14);border-radius:999px;padding:.3rem .55rem;font-size:.7rem!important;text-transform:uppercase}}
    @media(max-width:768px){{.block-container{{padding:.75rem .85rem 2rem}}[data-testid="stMetric"]{{min-height:auto}}}}
    </style>''',unsafe_allow_html=True)
