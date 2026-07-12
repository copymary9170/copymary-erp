"""Tema visual del shell empresarial de CopyMary ERP."""

import streamlit as st


def apply_enterprise_theme() -> None:
    st.markdown(
        """
        <style>
        :root{--cm-purple:#6D4AFF;--cm-violet:#8B5CF6;--cm-teal:#22A6A1;--cm-blue:#2F80ED;--cm-ink:#172033;--cm-muted:#6F7890;--cm-border:rgba(109,74,255,.14)}
        [data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important}
        .stApp{background:radial-gradient(circle at 0 0,rgba(109,74,255,.08),transparent 28rem),radial-gradient(circle at 100% 0,rgba(34,166,161,.08),transparent 30rem),#F6F8FC}
        .block-container{padding:1.1rem 1.6rem 3.5rem;max-width:1720px}
        .cm-shell{background:rgba(255,255,255,.88);border:1px solid rgba(255,255,255,.72);border-radius:28px;padding:1rem 1.1rem;box-shadow:0 24px 65px rgba(34,40,65,.10);backdrop-filter:blur(18px);margin-bottom:1rem}
        .cm-topline{display:flex;align-items:center;justify-content:space-between;gap:1rem}
        .cm-brand{display:flex;align-items:center;gap:.9rem}.cm-logo{width:54px;height:54px;border-radius:18px;display:grid;place-items:center;color:white;font-weight:950;letter-spacing:-.06em;background:linear-gradient(145deg,var(--cm-purple),var(--cm-violet) 55%,var(--cm-teal));box-shadow:0 15px 34px rgba(109,74,255,.28)}
        .cm-brand-title{font-size:1.22rem;font-weight:900;color:var(--cm-ink);letter-spacing:-.025em}.cm-brand-subtitle{font-size:.79rem;color:#7B849A;margin-top:.12rem}
        .cm-account{display:flex;align-items:center;gap:.7rem;padding:.58rem .72rem;border:1px solid var(--cm-border);background:white;border-radius:16px}.cm-account-dot{width:10px;height:10px;border-radius:50%;background:var(--cm-teal);box-shadow:0 0 0 5px rgba(34,166,161,.12)}.cm-account-name{font-size:.78rem;font-weight:800;color:#344057}.cm-account-role{font-size:.68rem;color:#8A93A7}
        .cm-nav-label{margin:.95rem 0 .4rem;font-size:.68rem;text-transform:uppercase;letter-spacing:.13em;font-weight:900;color:#929AAF}
        div[data-testid="stRadio"]>div{gap:.42rem;flex-wrap:wrap}div[data-testid="stRadio"] label{background:#fff;border:1px solid rgba(109,74,255,.13);border-radius:14px;padding:.5rem .78rem;box-shadow:0 4px 12px rgba(31,41,55,.035);transition:.18s ease}div[data-testid="stRadio"] label:hover{transform:translateY(-1px);border-color:rgba(109,74,255,.32);box-shadow:0 9px 20px rgba(109,74,255,.09)}
        .cm-workspace{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1rem;align-items:end;margin:1rem 0 .9rem}.cm-eyebrow{font-size:.68rem;text-transform:uppercase;letter-spacing:.13em;font-weight:900;color:var(--cm-purple)}.cm-workspace-title{font-size:1.75rem;line-height:1.05;font-weight:950;letter-spacing:-.04em;color:var(--cm-ink);margin:.2rem 0 .35rem}.cm-workspace-copy{font-size:.88rem;color:var(--cm-muted);max-width:760px}.cm-workspace-icon{width:68px;height:68px;border-radius:22px;display:grid;place-items:center;font-size:1.8rem;color:var(--cm-purple);background:linear-gradient(145deg,rgba(109,74,255,.12),rgba(34,166,161,.10));border:1px solid var(--cm-border)}
        .cm-section-head{display:flex;justify-content:space-between;align-items:center;gap:1rem;margin:1rem 0 .7rem}.cm-section-title{font-size:1rem;font-weight:900;color:#2A354C}.cm-section-meta{font-size:.72rem;color:#8A93A7}
        div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:22px!important;border:1px solid rgba(109,74,255,.12)!important;background:linear-gradient(180deg,#fff,#FCFBFF)!important;box-shadow:0 10px 28px rgba(31,41,55,.055)!important;transition:.2s ease}div[data-testid="stVerticalBlockBorderWrapper"]:hover{transform:translateY(-2px);box-shadow:0 16px 35px rgba(109,74,255,.10)!important;border-color:rgba(109,74,255,.24)!important}
        .cm-card-top{display:flex;justify-content:space-between;align-items:center;gap:.7rem}.cm-card-badge{font-size:.64rem;text-transform:uppercase;letter-spacing:.09em;font-weight:900;color:var(--cm-purple);background:rgba(109,74,255,.08);padding:.26rem .45rem;border-radius:999px}.cm-card-active{color:#0F766E;background:rgba(34,166,161,.10)}.cm-card-title{font-size:.98rem;font-weight:900;color:#263149;margin:.55rem 0 .28rem}.cm-card-copy{font-size:.78rem;color:#727C91;line-height:1.48;min-height:2.45rem}.cm-card-arrow{font-size:1rem;color:#9AA2B5}
        div[data-testid="stButton"] button{min-height:2.65rem;border-radius:13px;font-weight:800;border-width:1px}.stButton>button[kind="primary"]{background:linear-gradient(135deg,var(--cm-purple),var(--cm-violet));border:none;box-shadow:0 9px 20px rgba(109,74,255,.20)}
        .cm-content-frame{margin-top:1rem;padding:1rem 1.05rem 1.4rem;background:rgba(255,255,255,.82);border:1px solid rgba(109,74,255,.10);border-radius:24px;box-shadow:0 18px 44px rgba(31,41,55,.06)}
        .cm-footer{margin-top:1rem;padding-top:.7rem;border-top:1px solid rgba(109,74,255,.09);font-size:.72rem;color:#929AAF;text-align:center}
        @media(max-width:900px){.block-container{padding:.7rem .75rem 2rem}.cm-topline,.cm-workspace{display:flex;flex-direction:column;align-items:flex-start}.cm-account{width:100%;box-sizing:border-box}.cm-workspace-icon{width:54px;height:54px;border-radius:18px}.cm-workspace-title{font-size:1.45rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )
