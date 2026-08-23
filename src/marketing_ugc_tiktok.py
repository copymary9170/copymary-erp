"""UGC profesional y laboratorio TikTok para Marketing Pro."""
from __future__ import annotations

import streamlit as st

from src.session_utils import now_iso, read_list, save_list

UGC_DEALS_KEY = "marketing_ugc_deals"
TIKTOK_TESTS_KEY = "marketing_tiktok_tests"


def tiktok_engagement_rate(row: dict) -> float:
    views = float(row.get("views", 0) or 0)
    if views <= 0:
        return 0.0
    interactions = sum(float(row.get(k, 0) or 0) for k in ("likes", "comments", "shares", "saves"))
    return interactions / views * 100


def render_marketing_ugc_tiktok() -> None:
    st.markdown("## UGC profesional · TikTok Testing")
    tabs = st.tabs(("UGC profesional", "TikTok Lab"))

    with tabs[0]:
        st.subheader("Gestión comercial de UGC")
        st.caption("Separa creación de contenido, alcance y derechos de uso; los seguidores son una variable, no el único criterio.")
        rows = read_list(UGC_DEALS_KEY)
        with st.form("ugc_deal", clear_on_submit=True):
            cols = st.columns(3)
            creator = cols[0].text_input("Creador / cliente")
            niche = cols[1].text_input("Nicho")
            followers = cols[2].number_input("Seguidores", min_value=0, step=100)
            cols = st.columns(3)
            platform = cols[0].selectbox("Plataforma", ("TikTok", "Instagram", "YouTube", "Mixto"))
            format_ = cols[1].selectbox("Entregable", ("Video UGC", "Story", "Foto", "Pack", "Raw footage"))
            qty = cols[2].number_input("Cantidad", min_value=1, step=1)
            cols = st.columns(3)
            base_rate = cols[0].number_input("Tarifa base USD", min_value=0.0)
            usage = cols[1].selectbox("Derechos de uso", ("Orgánico", "30 días Ads", "90 días Ads", "Perpetuo"))
            exclusivity = cols[2].checkbox("Exclusividad")
            raw = st.checkbox("Incluye material bruto / raw footage")
            revisions = st.number_input("Revisiones incluidas", min_value=0, max_value=10, value=1)
            notes = st.text_area("Condiciones / notas")
            if st.form_submit_button("Guardar acuerdo UGC", type="primary", use_container_width=True) and creator.strip():
                row = {"creator": creator.strip(), "niche": niche.strip(), "followers": int(followers), "platform": platform,
                       "format": format_, "qty": int(qty), "rate": float(base_rate), "usage": usage,
                       "exclusivity": exclusivity, "raw": raw, "revisions": int(revisions), "notes": notes.strip(),
                       "created_at_utc": now_iso()}
                save_list(UGC_DEALS_KEY, [*rows, row]); st.rerun()
        rows = read_list(UGC_DEALS_KEY)
        if rows:
            st.metric("Acuerdos registrados", len(rows))
            for row in reversed(rows[-10:]):
                st.write(f"**{row.get('creator')}** · {row.get('platform')} · {row.get('format')} × {row.get('qty')} · ${row.get('rate',0):,.2f} · {row.get('usage')}")

    with tabs[1]:
        st.subheader("Laboratorio de pruebas TikTok")
        st.caption("Registra hipótesis y primeras señales para aprender qué formato merece una segunda iteración.")
        rows = read_list(TIKTOK_TESTS_KEY)
        with st.form("tiktok_test", clear_on_submit=True):
            hypothesis = st.text_input("Hipótesis", placeholder="Un hook de contraste retendrá mejor que uno informativo")
            cols = st.columns(4)
            hook = cols[0].text_input("Hook")
            topic = cols[1].text_input("Tema")
            duration = cols[2].number_input("Duración seg", min_value=1, max_value=600, value=15)
            cta = cols[3].text_input("CTA")
            cols = st.columns(4)
            views = cols[0].number_input("Vistas", min_value=0, step=1)
            likes = cols[1].number_input("Likes", min_value=0, step=1)
            comments = cols[2].number_input("Comentarios", min_value=0, step=1)
            shares = cols[3].number_input("Compartidos", min_value=0, step=1)
            cols = st.columns(3)
            saves = cols[0].number_input("Guardados", min_value=0, step=1)
            avg_watch = cols[1].number_input("Tiempo medio visto (s)", min_value=0.0)
            retention = cols[2].number_input("Retención %", min_value=0.0, max_value=100.0)
            stage = st.selectbox("Etapa", ("Prueba inicial", "Análisis de interacción", "Expansión"))
            learning = st.text_area("Aprendizaje / próxima variante")
            if st.form_submit_button("Guardar prueba", type="primary", use_container_width=True):
                row = {"hypothesis": hypothesis.strip(), "hook": hook.strip(), "topic": topic.strip(), "duration": int(duration),
                       "cta": cta.strip(), "views": int(views), "likes": int(likes), "comments": int(comments),
                       "shares": int(shares), "saves": int(saves), "avg_watch": float(avg_watch), "retention": float(retention),
                       "stage": stage, "learning": learning.strip(), "created_at_utc": now_iso()}
                save_list(TIKTOK_TESTS_KEY, [*rows, row]); st.rerun()
        rows = read_list(TIKTOK_TESTS_KEY)
        for row in reversed(rows[-10:]):
            er = tiktok_engagement_rate(row)
            st.write(f"**{row.get('topic') or row.get('hypothesis') or 'Prueba'}** · {row.get('stage')} · ER {er:.2f}% · Retención {row.get('retention',0):.1f}%")
            if row.get('learning'): st.caption(row.get('learning'))
