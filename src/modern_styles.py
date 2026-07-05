import streamlit as st
from src.config import COLORS


def apply_modern_styles():
    st.markdown(f'''<style>
    :root{{--p:{COLORS['primary']};--a:{COLORS['accent']};--bg:{COLORS['background']};--text:{COLORS['text']};--muted:{COLORS['muted']};--border:{COLORS['border']}}}
    html,body,[class*="css"]{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
    .stApp{{background:radial-gradient(circle at 85% 5%,rgba(109,74,255,.08),transparent 28%),radial-gradient(circle at 8% 95%,rgba(34,166,161,.08),transparent 24%),var(--bg)}}
    .block-container{{padding-top:1rem;padding-bottom:2.5rem;max-width:1440px}}
    [data-testid="stHeader"]{{background:transparent}}
    [data-testid="stSidebar"]{{background:linear-gradient(180deg,#fff,#f7f8ff);border-right:1px solid var(--border)}}
    [data-testid="stSidebar"]>div:first-child{{padding:1.1rem 1rem 1.5rem}}
    [data-testid="stSidebar"] [role="radiogroup"]{{gap:.2rem}}
    [data-testid="stSidebar"] [role="radiogroup"] label{{padding:.45rem .55rem;border-radius:11px}}
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{{background:rgba(109,74,255,.07)}}
    h1,h2,h3,h4{{color:var(--text);letter-spacing:-.025em}}
    [data-testid="stMetric"]{{background:rgba(255,255,255,.95);border:1px solid var(--border);border-radius:18px;padding:1rem;box-shadow:0 6px 20px rgba(31,41,55,.07)}}
    [data-testid="stVerticalBlockBorderWrapper"]{{border-radius:18px;border-color:var(--border)!important;background:rgba(255,255,255,.92);box-shadow:0 5px 18px rgba(31,41,55,.06)}}
    .stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{{border-radius:12px;min-height:2.7rem;font-weight:700}}
    button[kind="primary"]{{background:linear-gradient(135deg,var(--p),var(--a))!important;border:none!important;color:#fff!important}}
    input,textarea,[data-baseweb="select"]>div{{border-radius:12px!important}}
    [data-baseweb="tab-list"]{{gap:.4rem;background:#fff;border:1px solid var(--border);border-radius:14px;padding:.35rem}}
    [data-baseweb="tab"]{{border-radius:10px;font-weight:700}}
    [data-testid="stAlert"]{{border-radius:14px}}
    .cm-card{{background:rgba(255,255,255,.96)!important;border-radius:18px!important;box-shadow:0 6px 20px rgba(31,41,55,.07)!important}}
    .cm-brand{{display:flex;align-items:center;gap:.7rem;padding:.75rem;margin-bottom:1rem;border-radius:16px;background:linear-gradient(135deg,rgba(109,74,255,.12),rgba(34,166,161,.1));border:1px solid rgba(109,74,255,.12)}}
    .cm-brand-mark{{width:42px;height:42px;display:grid;place-items:center;border-radius:14px;background:linear-gradient(135deg,var(--p),var(--a));color:#fff;font-weight:900}}
    .cm-brand-name{{font-weight:800;color:var(--text)}}
    .cm-brand-sub{{font-size:.76rem;color:var(--muted)}}
    .cm-hero{{position:relative;overflow:hidden;padding:1.6rem 1.7rem;border-radius:24px;background:linear-gradient(135deg,#fff,#f5f3ff 55%,#eefcf9);border:1px solid rgba(109,74,255,.14);box-shadow:0 14px 38px rgba(31,41,55,.09);margin-bottom:1rem}}
    .cm-hero:after{{content:"";position:absolute;width:220px;height:220px;border-radius:50%;right:-65px;top:-90px;background:linear-gradient(135deg,rgba(109,74,255,.22),rgba(34,166,161,.16))}}
    .cm-hero-kicker{{position:relative;z-index:1;color:var(--p);font-weight:800;font-size:.74rem;letter-spacing:.08em}}
    .cm-hero h1{{position:relative;z-index:1;font-size:clamp(2rem,3.3vw,3.35rem);margin:.45rem 0 .55rem}}
    .cm-hero p{{position:relative;z-index:1;color:var(--muted);font-size:1rem;max-width:760px;line-height:1.6;margin:0}}
    .cm-badges{{position:relative;z-index:1;display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1rem}}
    .cm-badge{{padding:.4rem .7rem;border-radius:999px;background:rgba(255,255,255,.8);border:1px solid rgba(109,74,255,.14);font-size:.78rem;font-weight:700}}
    @media(max-width:768px){{.block-container{{padding:.75rem .85rem 2rem}}.cm-hero{{padding:1.15rem;border-radius:18px}}}}
    </style>''',unsafe_allow_html=True)
