"""Asistente guiado del Plan de Marketing.

Organiza la metodología de las clases como un flujo acumulativo: auditoría, FODA,
audiencia, buyer persona, benchmarking, personalidad, objetivos, estrategia,
contenido y medición. Cada paso queda persistido para reutilizarlo en AI Builder.
"""
from __future__ import annotations

import streamlit as st

from src.session_utils import now_iso, read_list, save_list

PLAN_KEY = "marketing_guided_plan"

STEPS = (
    "1 · Auditoría",
    "2 · FODA",
    "3 · Audiencia",
    "4 · Buyer Persona",
    "5 · Benchmarking",
    "6 · Personalidad",
    "7 · Objetivos",
    "8 · Estrategia y tácticas",
    "9 · Contenido",
    "10 · KPI y optimización",
)


def completion_score(plan: dict) -> float:
    done = sum(bool(plan.get(str(i), {}).get("complete")) for i in range(1, 11))
    return done / 10 * 100


def _latest() -> dict:
    rows = read_list(PLAN_KEY)
    return dict(rows[-1]) if rows else {str(i): {} for i in range(1, 11)}


def _save(plan: dict) -> None:
    plan["updated_at_utc"] = now_iso()
    rows = read_list(PLAN_KEY)
    save_list(PLAN_KEY, [*rows[:-1], plan] if rows else [plan])


def plan_context(plan: dict) -> str:
    labels = {
        "1": "Auditoría", "2": "FODA", "3": "Audiencia", "4": "Buyer Persona",
        "5": "Benchmarking", "6": "Personalidad", "7": "Objetivos",
        "8": "Estrategia y tácticas", "9": "Contenido", "10": "KPI y optimización",
    }
    blocks = []
    for key, label in labels.items():
        data = plan.get(key, {})
        text = data.get("summary", "").strip()
        if text:
            blocks.append(f"## {label}\n{text}")
    return "\n\n".join(blocks)


def _editor(plan: dict, step: int, title: str, help_text: str, fields: list[tuple[str, str]]) -> None:
    current = plan.get(str(step), {})
    st.subheader(title)
    st.caption(help_text)
    with st.form(f"guided_marketing_{step}"):
        values = {}
        for key, label in fields:
            values[key] = st.text_area(label, value=current.get(key, ""), height=100)
        complete = st.checkbox("Marcar este paso como completado", value=bool(current.get("complete")))
        if st.form_submit_button("Guardar paso", type="primary", use_container_width=True):
            summary = "\n".join(f"{label}: {values[key].strip()}" for key, label in fields if values[key].strip())
            plan[str(step)] = {**values, "summary": summary, "complete": complete, "updated_at_utc": now_iso()}
            _save(plan)
            st.rerun()


def render_marketing_guided_plan() -> None:
    plan = _latest()
    score = completion_score(plan)
    st.markdown("### Plan de Marketing guiado")
    st.caption("Completa el plan en orden. La información se conserva y luego puede reutilizarse como contexto para IA, campañas y contenido.")
    st.progress(score / 100)
    c1, c2 = st.columns(2)
    c1.metric("Avance del plan", f"{score:.0f}%")
    c2.metric("Pasos completados", f"{int(score / 10)} / 10")

    selected = st.selectbox("Paso de trabajo", STEPS)
    step = STEPS.index(selected) + 1

    if step == 1:
        _editor(plan, 1, "Auditoría inicial", "Registra primero lo que existe hoy. No diseñes la estrategia sobre supuestos.", [
            ("brand_state", "Estado actual de la marca"), ("channels", "Canales y activos existentes"),
            ("results", "Resultados actuales"), ("problems", "Problemas y brechas detectadas"),
        ])
    elif step == 2:
        _editor(plan, 2, "Matriz FODA", "Separa factores internos y externos antes de decidir acciones.", [
            ("strengths", "Fortalezas"), ("opportunities", "Oportunidades"),
            ("weaknesses", "Debilidades"), ("threats", "Amenazas"),
        ])
    elif step == 3:
        _editor(plan, 3, "Audiencia", "Define a quién deseas alcanzar antes de describir una persona individual.", [
            ("segments", "Segmentos principales"), ("demographics", "Datos demográficos"),
            ("psychographics", "Datos psicográficos"), ("needs", "Necesidades y problemas"),
        ])
    elif step == 4:
        _editor(plan, 4, "Buyer Persona", "Convierte la audiencia en un perfil accionable para mensajes, ofertas y contenido.", [
            ("profile", "Perfil / historia"), ("goals", "Objetivos y deseos"),
            ("pains", "Dolores y objeciones"), ("journey", "Cómo compra y dónde busca información"),
        ])
    elif step == 5:
        _editor(plan, 5, "Benchmarking", "Compara competidores con los mismos criterios y registra oportunidades, no solo inspiración.", [
            ("direct", "Competidores directos"), ("indirect", "Competidores indirectos"),
            ("criteria", "Criterios comparados"), ("gaps", "Vacíos y oportunidades detectadas"),
        ])
    elif step == 6:
        _editor(plan, 6, "Personalidad y arquetipo", "Define cómo debe sentirse y expresarse la marca para mantener consistencia.", [
            ("archetype", "Arquetipo principal y secundario"), ("personality", "Rasgos de personalidad"),
            ("tone", "Tono de voz"), ("rules", "La marca SÍ / NO dice o hace"),
        ])
    elif step == 7:
        _editor(plan, 7, "Objetivos", "Define aquello que deseas lograr y relaciónalo con presupuesto, plazo y una meta medible.", [
            ("business", "Objetivo de negocio"), ("marketing", "Objetivo de marketing / SMART"),
            ("budget", "Presupuesto disponible"), ("target", "Meta y plazo"),
        ])
    elif step == 8:
        _editor(plan, 8, "Estrategia y tácticas", "Diferencia la dirección estratégica de las acciones concretas que la ejecutan.", [
            ("strategy", "Estrategia"), ("tactics", "Tácticas"),
            ("channels", "Canales"), ("offer", "Oferta / propuesta que se comunicará"),
        ])
    elif step == 9:
        _editor(plan, 9, "Sistema de contenido", "Planifica contenido por canal y formato, no como publicaciones aisladas.", [
            ("pillars", "Pilares de contenido"), ("formats", "Formatos: historias, reels, imágenes, etc."),
            ("calendar", "Frecuencia / calendario"), ("cta", "CTA y recorrido esperado"),
        ])
    else:
        _editor(plan, 10, "KPI y optimización", "Mide contra el objetivo. Registrar números sin una decisión posterior no es optimizar.", [
            ("kpis", "KPI principales"), ("baseline", "Línea base / resultado actual"),
            ("target", "Meta"), ("optimization", "Qué decisión tomarás según el resultado"),
        ])

    st.divider()
    st.markdown("#### Contexto consolidado")
    context = plan_context(plan)
    if context:
        st.code(context, language="markdown")
        st.download_button("Descargar plan .md", context, file_name="plan_marketing.md", mime="text/markdown", use_container_width=True)
    else:
        st.info("Completa al menos un paso para generar el contexto consolidado.")
