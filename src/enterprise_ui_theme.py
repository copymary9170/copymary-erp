"""Tema visual del shell empresarial de CopyMary ERP."""

import streamlit as st


def apply_enterprise_theme() -> None:
    st.markdown(
        """
        <style>
        :root{--cm-purple:#6D4AFF;--cm-violet:#8B5CF6;--cm-teal:#22A6A1;--cm-blue:#2F80ED;--cm-ink:#172033;--cm-muted:#6F7890;--cm-border:rgba(109,74,255,.14)}
        [data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important}
        .stApp{background:radial-gradient(circle at 0 0,rgba(109,74,255,.08),transparent 28rem),radial-gradient(circle at 100% 0,rgba(34,166,161,.08),transparent 30rem),#F6F8FC}
        .block-container{padding:1rem 1.45rem 3.2rem;max-width:1720px}
        .cm-shell{background:rgba(255,255,255,.9);border:1px solid rgba(255,255,255,.72);border-radius:24px;padding:.85rem 1rem;box-shadow:0 18px 48px rgba(34,40,65,.09);backdrop-filter:blur(18px);margin-bottom:.8rem}
        .cm-topline{display:flex;align-items:center;justify-content:space-between;gap:1rem}.cm-brand{display:flex;align-items:center;gap:.75rem}.cm-logo{width:46px;height:46px;border-radius:15px;display:grid;place-items:center;color:white;font-weight:950;background:linear-gradient(145deg,var(--cm-purple),var(--cm-violet) 55%,var(--cm-teal));box-shadow:0 12px 26px rgba(109,74,255,.25)}
        .cm-brand-title{font-size:1.08rem;font-weight:900;color:var(--cm-ink)}.cm-brand-subtitle{font-size:.72rem;color:#7B849A}.cm-account{display:flex;align-items:center;gap:.6rem;padding:.48rem .65rem;border:1px solid var(--cm-border);background:white;border-radius:14px}.cm-account-dot{width:8px;height:8px;border-radius:50%;background:var(--cm-teal)}.cm-account-name{font-size:.72rem;font-weight:800;color:#344057}.cm-account-role{font-size:.62rem;color:#8A93A7}
        .cm-nav-label{margin:.75rem 0 .3rem;font-size:.62rem;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#929AAF}
        div[data-testid="stRadio"]>div{display:flex!important;flex-wrap:wrap!important;overflow:visible!important;gap:.32rem!important;padding:.08rem 0 .18rem}
        div[data-testid="stRadio"] label{flex:0 0 auto!important;white-space:nowrap!important;background:#fff;border:1px solid rgba(109,74,255,.13);border-radius:10px;padding:.32rem .58rem!important;box-shadow:0 2px 7px rgba(31,41,55,.03);transition:.15s ease;font-size:.72rem!important}
        div[data-testid="stRadio"] label:hover{transform:translateY(-1px);border-color:rgba(109,74,255,.32);box-shadow:0 6px 14px rgba(109,74,255,.08)}
        div[data-testid="stRadio"] label[data-checked="true"]{background:linear-gradient(135deg,rgba(109,74,255,.12),rgba(34,166,161,.09));border-color:rgba(109,74,255,.35)}
        div[data-testid="stRadio"] label p{font-size:.72rem!important;font-weight:750!important;margin:0!important}div[data-testid="stRadio"] input{display:none!important}
        .cm-workspace{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.8rem;align-items:center;margin:.65rem 0 .55rem}.cm-eyebrow{font-size:.6rem;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:var(--cm-purple)}.cm-workspace-title{font-size:1.3rem;line-height:1.05;font-weight:950;color:var(--cm-ink);margin:.12rem 0 .2rem}.cm-workspace-copy{font-size:.73rem;color:var(--cm-muted)}.cm-workspace-icon{width:46px;height:46px;border-radius:15px;display:grid;place-items:center;font-size:1.25rem;color:var(--cm-purple);background:linear-gradient(145deg,rgba(109,74,255,.12),rgba(34,166,161,.10));border:1px solid var(--cm-border)}
        .cm-selected-module{display:flex;align-items:baseline;gap:.5rem;margin:.1rem 0 .55rem;padding:.28rem .15rem;border-bottom:1px solid rgba(109,74,255,.09)}.cm-selected-module strong{font-size:.72rem;color:#303A50}.cm-selected-module span{font-size:.58rem;color:#8A93A7;line-height:1.25}
        div[data-testid="stButton"] button{min-height:2.35rem;border-radius:11px;font-weight:800;border-width:1px}.stButton>button[kind="primary"]{background:linear-gradient(135deg,var(--cm-purple),var(--cm-violet));border:none;box-shadow:0 7px 16px rgba(109,74,255,.18)}
        .cm-content-frame{margin-top:.55rem;padding:.85rem .95rem 1.2rem;background:rgba(255,255,255,.84);border:1px solid rgba(109,74,255,.10);border-radius:20px;box-shadow:0 14px 34px rgba(31,41,55,.05)}
        .cm-footer{margin-top:.8rem;padding-top:.6rem;border-top:1px solid rgba(109,74,255,.09);font-size:.65rem;color:#929AAF;text-align:center}
        @media(max-width:900px){.block-container{padding:.65rem .7rem 1.8rem}.cm-topline,.cm-workspace{display:flex;flex-direction:column;align-items:flex-start}.cm-account{width:100%;box-sizing:border-box}.cm-workspace-icon{display:none}.cm-workspace-title{font-size:1.15rem}.cm-selected-module{align-items:flex-start;flex-direction:column;gap:.1rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )
