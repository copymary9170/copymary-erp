"""AI Builder para Marketing Pro.

Convierte el contexto estratégico ya guardado en el ERP en prompts estructurados,
conserva versiones e incorpora QA antes de usar la salida de una IA.
"""
from __future__ import annotations

import re
import streamlit as st

from src.session_utils import now_iso, read_list, save_list

AI_BUILDER_KEY = "marketing_ai_builder_projects"
PROMPT_VERSIONS_KEY = "marketing_ai_prompt_versions"
AI_QA_KEY = "marketing_ai_qa"

PROMPT_BLOCKS = (
    "Rol y criterio",
    "Objetivo",
    "Entregable",
    "Contexto de marca",
    "Estructura",
    "Comportamiento",
    "Restricciones y QA",
)

AI_FULL_STACK_STAGES = (
    "1. Planteamiento de la idea",
    "2. Desarrollo de producto / activo",
    "3. Ventas y automatización",
    "4. Creación de contenido",
    "5. Publicidad pagada",
)


def unresolved_placeholders(text: str) -> list[str]:
    """Devuelve placeholders [PENDIENTES] para evitar prompts incompletos."""
    return sorted(set(re.findall(r"\[[^\[\]]+\]", text or "")))


def build_master_prompt(data: dict) -> str:
    """Construye un prompt maestro estable en siete bloques."""
    sections = [
        ("1. ROL Y CRITERIO", data.get("role", "")),
        ("2. OBJETIVO", data.get("objective", "")),
        ("3. ENTREGABLE", data.get("deliverable", "")),
        ("4. CONTEXTO DE MARCA", data.get("context", "")),
        ("5. ESTRUCTURA", data.get("structure", "")),
        ("6. COMPORTAMIENTO", data.get("behavior", "")),
        ("7. RESTRICCIONES Y QA", data.get("constraints", "")),
    ]
    return "\n\n".join(f"## {title}\n{str(value).strip()}" for title, value in sections)


def ai_qa_score(checks: dict[str, bool]) -> float:
    """Porcentaje simple de control humano completado."""
    if not checks:
        return 0.0
    return sum(bool(value) for value in checks.values()) / len(checks) * 100


def _brand_context() -> str:
    brief = (read_list("marketing_brand_brief") or [{}])[-1]
    personality = (read_list("marketing_brand_personality") or [{}])[-1]
    parts = [
        f"Marca: {brief.get('brand', '')}",
        f"Propósito: {brief.get('purpose', '')}",
        f"Propuesta de valor: {brief.get('value_proposition', '')}",
        f"Posicionamiento: {brief.get('positioning', '')}",
        f"Audiencia demográfica: {brief.get('demographics', '')}",
        f"Audiencia psicográfica: {brief.get('psychographics', '')}",
        f"Objeciones: {brief.get('objections', '')}",
        f"Arquetipo: {personality.get('primary', '')} + {personality.get('secondary', '')}",
        f"Tono: {personality.get('tone', '')}",
        f"La marca SÍ dice: {personality.get('says', '')}",
        f"La marca NO dice: {personality.get('avoids', '')}",
    ]
    return "\n".join(part for part in parts if part.split(":", 1)[-1].strip())


def _render_prompt_studio() -> None:
    st.subheader("AI Builder · Prompt Studio")
    st.caption("La IA ejecuta; el ERP conserva el contexto, la estructura, las restricciones y el criterio humano.")
    projects = read_list(AI_BUILDER_KEY)
    default_context = _brand_context()

    with st.form("marketing_ai_master_prompt"):
        cols = st.columns(2)
        name = cols[0].text_input("Nombre del trabajo", placeholder="Landing regreso a clases")
        stage = cols[1].selectbox("Etapa AI Full Stack", AI_FULL_STACK_STAGES)
        role = st.text_area("1 · Rol y criterio", placeholder="Actúa como estratega de marketing y director creativo...")
        objective = st.text_area("2 · Objetivo", placeholder="Qué resultado concreto debe conseguir")
        deliverable = st.text_area("3 · Entregable", placeholder="Qué debe devolver exactamente y en qué formato")
        context = st.text_area("4 · Contexto de marca", value=default_context, height=190)
        structure = st.text_area("5 · Estructura", placeholder="Secciones, jerarquía, orden, componentes obligatorios...")
        behavior = st.text_area("6 · Comportamiento", placeholder="Cómo debe responder, priorizar, validar o iterar")
        constraints = st.text_area("7 · Restricciones y QA", placeholder="Qué no debe inventar, límites, requisitos de marca, móvil, CTA, claims verificables...")
        if st.form_submit_button("Guardar y construir prompt", type="primary", use_container_width=True):
            data = {
                "name": name.strip() or "Prompt sin nombre", "stage": stage, "role": role.strip(),
                "objective": objective.strip(), "deliverable": deliverable.strip(), "context": context.strip(),
                "structure": structure.strip(), "behavior": behavior.strip(), "constraints": constraints.strip(),
            }
            prompt = build_master_prompt(data)
            data.update({"prompt": prompt, "created_at_utc": now_iso()})
            save_list(AI_BUILDER_KEY, [*projects, data])
            versions = read_list(PROMPT_VERSIONS_KEY)
            save_list(PROMPT_VERSIONS_KEY, [*versions, {"name": data["name"], "prompt": prompt, "created_at_utc": data["created_at_utc"]}])
            st.rerun()

    projects = read_list(AI_BUILDER_KEY)
    if projects:
        latest = projects[-1]
        st.markdown("#### Prompt maestro más reciente")
        placeholders = unresolved_placeholders(latest.get("prompt", ""))
        if placeholders:
            st.warning("Completa estos campos antes de usar el prompt: " + ", ".join(placeholders))
        else:
            st.success("Prompt sin placeholders pendientes.")
        st.code(latest.get("prompt", ""), language="markdown")
        st.download_button("Descargar prompt .md", latest.get("prompt", ""), file_name="marketing_prompt_maestro.md", mime="text/markdown", use_container_width=True)


def _render_ai_qa() -> None:
    st.subheader("QA humano antes de aprobar IA")
    st.caption("No se aprueba una salida solo porque se vea bien: se revisa estrategia, marca, exactitud y conversión.")
    checks = {}
    checks["strategy"] = st.checkbox("Responde al objetivo y a la etapa del embudo")
    checks["brand"] = st.checkbox("Respeta voz, personalidad y sistema visual de la marca")
    checks["facts"] = st.checkbox("Precios, características, claims y datos fueron verificados")
    checks["audience"] = st.checkbox("Está adaptado al buyer persona y sus objeciones")
    checks["cta"] = st.checkbox("Tiene una acción siguiente clara cuando corresponde")
    checks["mobile"] = st.checkbox("La pieza fue revisada para el formato/plataforma final")
    checks["human"] = st.checkbox("Una persona revisó y decidió qué conservar o corregir")
    score = ai_qa_score(checks)
    st.progress(score / 100)
    st.metric("QA completado", f"{score:.0f}%")
    if st.button("Guardar revisión QA", use_container_width=True):
        rows = read_list(AI_QA_KEY)
        save_list(AI_QA_KEY, [*rows, {"checks": checks, "score": score, "created_at_utc": now_iso()}])
        st.success("Revisión guardada.")


def _render_versions() -> None:
    st.subheader("Versiones e iteración quirúrgica")
    st.caption("Conserva lo que funciona. Para corregir, pide un cambio concreto en vez de regenerar todo.")
    versions = read_list(PROMPT_VERSIONS_KEY)
    if not versions:
        st.info("Aún no hay versiones de prompts.")
        return
    for idx, row in enumerate(reversed(versions[-15:]), 1):
        with st.expander(f"{row.get('name', 'Prompt')} · {row.get('created_at_utc', '')}"):
            st.code(row.get("prompt", ""), language="markdown")
            st.caption("Sugerencia de iteración: indica qué único bloque debe cambiar y declara explícitamente qué debe permanecer intacto.")


def render_marketing_ai_builder() -> None:
    st.markdown("### IA & AI Builder")
    tabs = st.tabs(["Prompt Studio", "QA humano", "Versiones", "Método"])
    with tabs[0]:
        _render_prompt_studio()
    with tabs[1]:
        _render_ai_qa()
    with tabs[2]:
        _render_versions()
    with tabs[3]:
        st.markdown("#### Método de trabajo")
        st.write("1. Completa estrategia y contexto de marca antes de pedir una salida a IA.")
        st.write("2. Define los siete bloques del prompt maestro; cambia el contenido, no la estructura.")
        st.write("3. Ejecuta, revisa con criterio humano y valida datos/claims.")
        st.write("4. Itera con cambios pequeños y conserva versiones anteriores.")
        st.write("5. Lleva el resultado aprobado al calendario, campaña, email, Ads o activo digital correspondiente.")
