"""Storytelling y producción de video para Marketing Pro."""
from __future__ import annotations

import streamlit as st

from src.session_utils import now_iso, read_list, save_list

STORY_KEY = "marketing_storytelling_lab"
VIDEO_KEY = "marketing_video_production"

STORY_TYPES = (
    "Quién soy yo", "Aristotélico", "Por qué estoy aquí", "In media res",
    "Relato visionario", "Valores en acción", "Educativo", "Lo que estás pensando",
)
VIDEO_PHASES = ("Preproducción", "Producción", "Postproducción")


def video_readiness_score(row: dict) -> float:
    required = ("strategy", "intention", "narrative", "structure", "retention", "editing")
    return sum(bool(str(row.get(k, "")).strip()) for k in required) / len(required) * 100


def _render_storytelling() -> None:
    st.subheader("Laboratorio de Storytelling")
    rows = read_list(STORY_KEY)
    with st.form("mkt_storytelling", clear_on_submit=True):
        cols = st.columns(2)
        title = cols[0].text_input("Historia / pieza")
        story_type = cols[1].selectbox("Tipo de storytelling", STORY_TYPES)
        audience = st.text_input("Audiencia y contexto")
        cols = st.columns(2)
        conflict = cols[0].text_area("Situación / conflicto")
        transformation = cols[1].text_area("Cambio / transformación")
        message = st.text_area("Mensaje central")
        proof = st.text_area("Prueba, escena o experiencia que lo hace creíble")
        cta = st.text_input("CTA / siguiente acción")
        channels = st.multiselect("Variantes para redes", ("Reel", "Historia", "Carrusel", "Post", "TikTok", "YouTube", "Email", "WhatsApp"))
        if st.form_submit_button("Guardar historia", type="primary", use_container_width=True) and title.strip():
            row = {"title": title.strip(), "story_type": story_type, "audience": audience.strip(), "conflict": conflict.strip(),
                   "transformation": transformation.strip(), "message": message.strip(), "proof": proof.strip(),
                   "cta": cta.strip(), "channels": channels, "created_at_utc": now_iso()}
            save_list(STORY_KEY, [*rows, row]); st.rerun()
    for row in reversed(rows[-8:]):
        with st.expander(f"{row.get('title')} · {row.get('story_type')}"):
            st.write(row.get("message", ""))
            st.caption("Variantes: " + ", ".join(row.get("channels", [])))


def _render_video_pipeline() -> None:
    st.subheader("Pipeline de Video · Preproducción → Producción → Postproducción")
    st.caption("El video no es solo grabar: necesita estrategia, intención, narrativa, estructura, retención y edición.")
    rows = read_list(VIDEO_KEY)
    with st.form("mkt_video_pipeline", clear_on_submit=True):
        title = st.text_input("Video / campaña")
        cols = st.columns(3)
        platform = cols[0].text_input("Plataforma")
        ratio = cols[1].selectbox("Formato", ("9:16", "1:1", "16:9"))
        duration = cols[2].text_input("Duración objetivo", placeholder="30 s")
        strategy = st.text_area("Estrategia · qué debe lograr")
        intention = st.text_area("Intención · qué debe sentir/entender la audiencia")
        narrative = st.text_area("Narrativa · historia o hilo conductor")
        structure = st.text_area("Estructura · hook, desarrollo, prueba, CTA")
        retention = st.text_area("Retención · cambios de plano, ritmo, curiosidad, texto, cortes")
        st.markdown("**Producción**")
        production = st.multiselect("Checklist de grabación", ("Guion técnico", "Lista de planos", "Audio", "Iluminación", "Movimiento de cámara", "Encuadre", "Estabilidad", "B-roll"))
        st.markdown("**Postproducción**")
        editing = st.text_area("Edición · ritmo, cortes, sonido, color, textos/subtítulos y exportación")
        post = st.multiselect("Checklist de post", ("Edición", "Sonido", "Corrección de color", "Subtítulos", "CTA visible", "Portada", "Exportación", "Revisión móvil"))
        if st.form_submit_button("Guardar producción", type="primary", use_container_width=True) and title.strip():
            row = {"title": title.strip(), "platform": platform.strip(), "ratio": ratio, "duration": duration.strip(),
                   "strategy": strategy.strip(), "intention": intention.strip(), "narrative": narrative.strip(),
                   "structure": structure.strip(), "retention": retention.strip(), "production": production,
                   "editing": editing.strip(), "post": post, "created_at_utc": now_iso()}
            save_list(VIDEO_KEY, [*rows, row]); st.rerun()
    if rows:
        latest = rows[-1]
        st.metric("Preparación estratégica del último video", f"{video_readiness_score(latest):.0f}%")
        for row in reversed(rows[-6:]):
            with st.container(border=True):
                st.write(f"**{row.get('title')}** · {row.get('platform')} · {row.get('ratio')}")
                st.caption(f"Producción: {len(row.get('production', []))} checks · Post: {len(row.get('post', []))} checks")


def render_marketing_story_video() -> None:
    st.markdown("## Storytelling & Video")
    tabs = st.tabs(("Storytelling", "Producción de video"))
    with tabs[0]: _render_storytelling()
    with tabs[1]: _render_video_pipeline()
