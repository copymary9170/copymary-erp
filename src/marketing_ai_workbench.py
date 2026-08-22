"""Capa de Marketing basada en la Clase 1: mercado, criterio IA y prompts estructurados."""
from __future__ import annotations

import streamlit as st

from src import marketing as base
from src.session_utils import now_iso, read_list, save_list

MARKET_KEY = "marketing_market_canvas"
PROMPTS_KEY = "marketing_prompt_library"


def build_marketing_prompt(role: str, task: str, output_format: str, context: str) -> str:
    """Construye el prompt con la estructura Rol → Tarea → Formato → Contexto."""
    return (
        f"ROL:\n{role.strip()}\n\n"
        f"TAREA:\n{task.strip()}\n\n"
        f"FORMATO:\n{output_format.strip()}\n\n"
        f"CONTEXTO:\n{context.strip()}"
    )


def ai_use_recommendation(error_cost: str, human_judgment: str) -> tuple[str, str]:
    """Guía operativa inspirada en la matriz vista en la clase."""
    high_error = error_cost == "Alto"
    high_human = human_judgment == "Alto"
    if high_error and high_human:
        return "Criterio humano primero", "Usa IA solo como apoyo. Revisa, valida y decide manualmente antes de publicar o actuar."
    if high_error and not high_human:
        return "IA con verificación obligatoria", "La IA puede acelerar el trabajo, pero toda salida debe verificarse antes de usarse."
    if not high_error and high_human:
        return "IA como copiloto", "Delegar borradores y variaciones a IA, manteniendo la decisión creativa y estratégica en una persona."
    return "Automatizable con IA", "Adecuado para ideación, reformulación, variaciones, resúmenes y tareas repetitivas de bajo riesgo."


def _render_market_canvas() -> None:
    st.subheader("Canvas de mercado")
    st.caption("Antes de crear contenido o campañas, define qué problema existe, para quién y frente a qué alternativas compites.")
    rows = read_list(MARKET_KEY)
    current = rows[-1] if rows else {}
    with st.form("marketing_market_canvas"):
        cols = st.columns(2)
        market = cols[0].text_area("Mercado / categoría", value=current.get("market", ""), placeholder="Ej. impresiones, papelería y personalizados locales")
        customer = cols[1].text_area("Cliente y situación", value=current.get("customer", ""), placeholder="Quién compra y en qué momento necesita resolver")
        cols = st.columns(2)
        problem = cols[0].text_area("Problema principal", value=current.get("problem", ""), placeholder="Qué frustración o necesidad concreta existe")
        alternatives = cols[1].text_area("Alternativas actuales", value=current.get("alternatives", ""), placeholder="Qué hace hoy el cliente si no te compra")
        cols = st.columns(2)
        opportunity = cols[0].text_area("Oportunidad", value=current.get("opportunity", ""), placeholder="Qué puedes hacer mejor, más claro o más conveniente")
        evidence = cols[1].text_area("Evidencia / señales", value=current.get("evidence", ""), placeholder="Preguntas frecuentes, ventas, comentarios, búsquedas, objeciones")
        if st.form_submit_button("Guardar canvas", type="primary", use_container_width=True):
            row = {"market": market.strip(), "customer": customer.strip(), "problem": problem.strip(), "alternatives": alternatives.strip(), "opportunity": opportunity.strip(), "evidence": evidence.strip(), "updated_at_utc": now_iso()}
            save_list(MARKET_KEY, [row])
            st.success("Canvas de mercado guardado.")
            st.rerun()


def _render_ai_matrix() -> None:
    st.subheader("¿IA o criterio humano?")
    st.caption("Evalúa el costo del error y cuánto criterio humano requiere la tarea antes de delegarla.")
    cols = st.columns(2)
    error_cost = cols[0].selectbox("Costo de equivocarse", ("Bajo", "Alto"), key="mkt_ai_error")
    human = cols[1].selectbox("Criterio humano necesario", ("Bajo", "Alto"), key="mkt_ai_human")
    label, explanation = ai_use_recommendation(error_cost, human)
    st.info(f"**{label}** — {explanation}")
    st.markdown("**Ejemplos de bajo riesgo:** ideas de contenido, reformular copies, resumir información, generar variantes.  \n**Ejemplos de alto riesgo:** precios, promesas comerciales, datos legales, decisiones financieras o afirmaciones que puedan afectar al cliente.")


def _render_prompt_builder() -> None:
    st.subheader("Constructor de prompts")
    st.caption("Estructura de la clase: Rol → Tarea → Formato → Contexto.")
    saved = read_list(PROMPTS_KEY)
    with st.form("marketing_prompt_builder"):
        name = st.text_input("Nombre del prompt", placeholder="Ej. plan mensual de Instagram")
        role = st.text_area("1. Rol", placeholder="Actúa como estratega de marketing digital para un pequeño negocio venezolano...")
        task = st.text_area("2. Tarea", placeholder="Crea un plan de marketing digital para redes sociales...")
        output_format = st.text_area("3. Formato", placeholder="Entrega 10 ideas en una tabla con objetivo, gancho, formato, CTA y etapa del embudo...")
        context = st.text_area("4. Contexto", placeholder="Negocio, público, productos, restricciones, tono, presupuesto y canales disponibles...")
        submitted = st.form_submit_button("Construir prompt", type="primary", use_container_width=True)
    if submitted:
        prompt = build_marketing_prompt(role, task, output_format, context)
        st.session_state["marketing_last_prompt"] = prompt
        if name.strip():
            row = {"name": name.strip(), "role": role.strip(), "task": task.strip(), "format": output_format.strip(), "context": context.strip(), "prompt": prompt, "created_at_utc": now_iso()}
            save_list(PROMPTS_KEY, [*saved, row])
    prompt = st.session_state.get("marketing_last_prompt", "")
    if prompt:
        st.text_area("Prompt listo para copiar", value=prompt, height=300)
    if saved:
        st.markdown("### Biblioteca de prompts")
        for row in reversed(saved[-10:]):
            with st.expander(row.get("name", "Prompt guardado")):
                st.code(row.get("prompt", ""), language=None)


def render_marketing() -> None:
    base.render_marketing()
    st.divider()
    st.markdown("## Laboratorio de Marketing con IA")
    st.caption("Herramientas incorporadas a partir de la Clase 1 para investigar antes de crear y usar IA con mejor criterio.")
    market_tab, matrix_tab, prompt_tab = st.tabs(("Mercado", "IA vs criterio humano", "Prompts"))
    with market_tab:
        _render_market_canvas()
    with matrix_tab:
        _render_ai_matrix()
    with prompt_tab:
        _render_prompt_builder()
