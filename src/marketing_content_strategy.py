"""Estrategia de contenido basada en investigación y modelo de negocio."""
from __future__ import annotations

import streamlit as st

from src.session_utils import now_iso, read_list, save_list

RESEARCH_KEY = "marketing_external_research"
CONTENT_MODEL_KEY = "marketing_content_models"

BUSINESS_MODELS = ["Producto físico", "Servicio", "Negocio digital", "Negocio híbrido", "E-commerce"]
RESEARCH_SOURCES = ["Competidores", "Tendencias", "Contenido del sector", "Redes sociales", "Google My Business", "Conversaciones del mercado", "Otra"]


def content_angles(model: str) -> list[str]:
    if model == "Producto físico":
        return ["Beneficios", "Uso", "Duración", "Resultado", "Demostración"]
    if model == "Servicio":
        return ["Experiencia", "Atención", "Confianza", "Transformación", "Seguridad"]
    if model in {"Negocio digital", "E-commerce"}:
        return ["Beneficio posterior a la compra", "Solución del problema", "Facilidad de contacto", "Conversión por WhatsApp o DM", "Resultado del producto o servicio"]
    return ["Beneficio", "Experiencia", "Confianza", "Resultado", "Conversión"]


def render_marketing_content_strategy() -> None:
    st.markdown("### Investigación + estrategia de contenido")
    st.caption("Primero estrategia e investigación; después IA. El contenido debe adaptarse al modelo de negocio y responder dudas reales del cliente.")
    tab1, tab2, tab3 = st.tabs(["Investigación externa", "Modelo de negocio", "Criterio IA"])

    with tab1:
        st.subheader("Investigación externa de mercado")
        st.write("Registra evidencia antes de convertir una idea en contenido.")
        with st.form("marketing_research_form"):
            source = st.selectbox("Fuente", RESEARCH_SOURCES)
            topic = st.text_input("Tema / búsqueda")
            finding = st.text_area("Hallazgo verificable")
            pattern = st.text_area("Patrón, tendencia u oportunidad detectada")
            implication = st.text_area("¿Qué cambia en nuestra estrategia o contenido?")
            reference = st.text_input("Referencia o enlace")
            if st.form_submit_button("Guardar investigación", type="primary"):
                rows = read_list(RESEARCH_KEY)
                save_list(RESEARCH_KEY, [*rows, {"source": source, "topic": topic, "finding": finding, "pattern": pattern, "implication": implication, "reference": reference, "created_at_utc": now_iso()}])
                st.rerun()
        rows = read_list(RESEARCH_KEY)
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay investigación registrada.")

    with tab2:
        st.subheader("Contenido según el modelo de negocio")
        model = st.selectbox("Modelo", BUSINESS_MODELS)
        angles = content_angles(model)
        st.info("Ángulos recomendados: " + " · ".join(angles))
        with st.form("marketing_business_content_form"):
            client_question = st.text_area("Duda real del cliente", placeholder="¿Qué necesita saber antes o después de comprar?")
            selected = st.multiselect("Ángulos que responderá la pieza", angles)
            promise = st.text_area("Promesa / idea central")
            proof = st.text_area("Prueba, demostración o evidencia")
            experience = st.text_area("Experiencia que queremos transmitir")
            conversion = st.text_input("Siguiente acción", placeholder="WhatsApp, DM, compra, guardar, visitar...")
            if st.form_submit_button("Guardar enfoque de contenido", type="primary"):
                rows = read_list(CONTENT_MODEL_KEY)
                save_list(CONTENT_MODEL_KEY, [*rows, {"model": model, "client_question": client_question, "angles": selected, "promise": promise, "proof": proof, "experience": experience, "conversion": conversion, "created_at_utc": now_iso()}])
                st.rerun()
        rows = read_list(CONTENT_MODEL_KEY)
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("IA como apoyo, no como estrategia")
        st.write("La IA puede ayudar a generar ideas, crear copies, estructurar guiones, organizar contenido, optimizar tiempos y multiplicar producción.")
        st.warning("No delegues a la IA el criterio, la creatividad estratégica, el entendimiento del cliente, el branding ni la comunicación humana.")
        st.markdown("**Checklist antes de enviar a AI Builder**")
        st.checkbox("Tengo investigación o evidencia suficiente", key="mkt_ai_ready_research")
        st.checkbox("Sé qué duda real del cliente quiero responder", key="mkt_ai_ready_question")
        st.checkbox("Definí el modelo de negocio y el ángulo correcto", key="mkt_ai_ready_model")
        st.checkbox("Tengo clara la experiencia o resultado que debe comunicar", key="mkt_ai_ready_experience")
        st.checkbox("Sé qué acción quiero provocar", key="mkt_ai_ready_conversion")
