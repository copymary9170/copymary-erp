"""Voz del consumidor, benchmarking y laboratorio operativo de Meta Ads."""
from __future__ import annotations

import streamlit as st
from src.session_utils import now_iso, read_list, save_list

INSIGHTS_KEY = "marketing_consumer_insights"
META_TESTS_KEY = "marketing_meta_tests"


def lead_rate(leads: float, clicks: float) -> float:
    return (leads / clicks * 100) if clicks else 0.0


def cost_per_lead(spend: float, leads: float) -> float:
    return (spend / leads) if leads else 0.0


def render_consumer_voice() -> None:
    st.subheader("Voz del consumidor · Social Listening + Benchmarking")
    st.caption("Convierte conversaciones y señales reales del mercado en decisiones de contenido, oferta y campaña.")
    rows = read_list(INSIGHTS_KEY)
    with st.form("consumer_voice_form"):
        c1, c2 = st.columns(2)
        source = c1.selectbox("Fuente", ["TikTok", "Instagram", "Comentarios", "Reseñas", "WhatsApp", "Competidor", "Google", "Otra"])
        sentiment = c2.selectbox("Sentimiento", ["Positivo", "Neutral", "Negativo", "Mixto"])
        voice = st.text_area("¿Qué está diciendo/pidiendo el consumidor?", placeholder="Pregunta, objeción, deseo, frase repetida o necesidad observada")
        pattern = st.text_area("Patrón / tema repetido")
        competitor = st.text_input("Marca o competidor relacionado (opcional)")
        action = st.text_area("Acción recomendada", placeholder="Contenido, mejora de oferta, respuesta, experimento o campaña")
        if st.form_submit_button("Guardar insight", type="primary", use_container_width=True):
            save_list(INSIGHTS_KEY, [*rows, {"source": source, "sentiment": sentiment, "voice": voice.strip(), "pattern": pattern.strip(), "competitor": competitor.strip(), "action": action.strip(), "created_at_utc": now_iso()}])
            st.rerun()
    rows = read_list(INSIGHTS_KEY)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_meta_ads_lab() -> None:
    st.subheader("Meta Ads Lab · Públicos, creativos y leads")
    st.caption("Documenta cada conjunto como una hipótesis: público + creativo + hook + presupuesto + resultado.")
    tests = read_list(META_TESTS_KEY)
    with st.form("meta_ads_test"):
        c1, c2, c3 = st.columns(3)
        campaign = c1.text_input("Campaña")
        objective = c2.selectbox("Objetivo", ["Leads", "Mensajes", "Ventas", "Tráfico", "Reconocimiento"])
        audience_type = c3.selectbox("Tipo de público", ["Frío", "Intereses", "Remarketing", "Similar", "Personalizado"])
        audience = st.text_area("Definición del público", placeholder="Ubicación, edad, género si aplica, intereses/intención y exclusiones")
        hook = st.text_input("Hook / ángulo creativo")
        creative = st.text_input("Creativo / variante")
        form_notes = st.text_area("Formulario / preguntas / destino", placeholder="Preguntas frecuentes, datos solicitados, WhatsApp, landing, etc.")
        m1, m2, m3, m4 = st.columns(4)
        spend = m1.number_input("Gasto", min_value=0.0, step=1.0)
        impressions = m2.number_input("Impresiones", min_value=0, step=1)
        clicks = m3.number_input("Clics", min_value=0, step=1)
        leads = m4.number_input("Leads", min_value=0, step=1)
        learning = st.text_area("Aprendizaje / siguiente decisión", placeholder="Mantener, pausar, cambiar público, hook, formulario o presupuesto")
        if st.form_submit_button("Guardar prueba Meta Ads", type="primary", use_container_width=True):
            ctr = (clicks / impressions * 100) if impressions else 0.0
            row = {"campaign": campaign.strip(), "objective": objective, "audience_type": audience_type, "audience": audience.strip(), "hook": hook.strip(), "creative": creative.strip(), "form_notes": form_notes.strip(), "spend": spend, "impressions": impressions, "clicks": clicks, "leads": leads, "ctr_pct": round(ctr, 2), "lead_rate_pct": round(lead_rate(leads, clicks), 2), "cpl": round(cost_per_lead(spend, leads), 2), "learning": learning.strip(), "created_at_utc": now_iso()}
            save_list(META_TESTS_KEY, [*tests, row])
            st.rerun()
    tests = read_list(META_TESTS_KEY)
    if tests:
        latest = tests[-1]
        a, b, c = st.columns(3)
        a.metric("CTR", f"{latest.get('ctr_pct', 0):.2f}%")
        b.metric("Conversión clic → lead", f"{latest.get('lead_rate_pct', 0):.2f}%")
        c.metric("Costo por lead", f"{latest.get('cpl', 0):.2f}")
        st.dataframe(tests, use_container_width=True, hide_index=True)


def render_marketing_insights_meta() -> None:
    st.markdown("### Mercado + Paid Media")
    tabs = st.tabs(["Voz del consumidor", "Meta Ads Lab"])
    with tabs[0]:
        render_consumer_voice()
    with tabs[1]:
        render_meta_ads_lab()
