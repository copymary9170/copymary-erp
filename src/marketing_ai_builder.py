"""AI Builder para Marketing Pro.

Convierte el contexto estratégico ya guardado en prompts reutilizables sin ejecutar
IA externa ni inventar datos. Sigue la disciplina de contexto, estructura fija,
restricciones y QA de los materiales de formación.
"""
from __future__ import annotations

import json

import streamlit as st

from src.session_utils import now_iso, read_list, save_list

BRIEF_KEY = "marketing_brand_brief"
PERSONALITY_KEY = "marketing_brand_personality"
AI_PROMPTS_KEY = "marketing_ai_builder_prompts"
AI_PROJECTS_KEY = "marketing_ai_builder_projects"

ASSET_TYPES = (
    "Contenido para redes", "Campaña", "Email", "Landing page", "Web informativa",
    "Guion de video", "Storyboard", "Brief creativo", "Análisis / investigación",
)


def build_brand_context() -> dict:
    brief = (read_list(BRIEF_KEY) or [{}])[-1]
    personality = (read_list(PERSONALITY_KEY) or [{}])[-1]
    return {
        "marca": brief.get("brand", ""),
        "mercado": brief.get("city", ""),
        "proposito": brief.get("purpose", ""),
        "propuesta_valor": brief.get("value_proposition", ""),
        "posicionamiento": brief.get("positioning", ""),
        "audiencia_demografica": brief.get("demographics", ""),
        "audiencia_psicografica": brief.get("psychographics", ""),
        "objeciones": brief.get("objections", ""),
        "arquetipo_primario": personality.get("primary", ""),
        "arquetipo_secundario": personality.get("secondary", ""),
        "tono": personality.get("tone", ""),
        "si_dice": personality.get("says", ""),
        "no_dice": personality.get("avoids", ""),
    }


def prompt_completeness(row: dict) -> float:
    required = ("role", "objective", "deliverable", "context", "structure", "restrictions", "qa")
    return round(sum(bool(str(row.get(k, "")).strip()) for k in required) / len(required) * 100, 1)


def compose_master_prompt(row: dict) -> str:
    blocks = (
        ("ROL", row.get("role", "")),
        ("OBJETIVO", row.get("objective", "")),
        ("ENTREGABLE", row.get("deliverable", "")),
        ("CONTEXTO", row.get("context", "")),
        ("DESIGN KEY TOKEN SYSTEM", row.get("design_tokens", "")),
        ("ESTRUCTURA", row.get("structure", "")),
        ("COMPORTAMIENTO", row.get("behavior", "")),
        ("RESTRICCIONES", row.get("restrictions", "")),
        ("CONTROL DE CALIDAD", row.get("qa", "")),
    )
    return "\n\n".join(f"## {title}\n{value.strip()}" for title, value in blocks if str(value).strip())


def _context_text() -> str:
    context = build_brand_context()
    useful = {k: v for k, v in context.items() if v}
    return json.dumps(useful, ensure_ascii=False, indent=2) if useful else ""


def _render_context() -> None:
    st.subheader("Contexto automático de marca")
    st.caption("Reutiliza el Briefing y la Personalidad ya guardados. La IA no debería recibir una marca sin contexto.")
    context = build_brand_context()
    filled = sum(bool(v) for v in context.values())
    cols = st.columns(3)
    cols[0].metric("Campos disponibles", filled)
    cols[1].metric("Campos esperados", len(context))
    cols[2].metric("Contexto listo", f"{filled / len(context) * 100:.0f}%")
    if filled:
        st.code(_context_text(), language="json")
    else:
        st.warning("Completa primero Briefing y Marca para que el constructor pueda reutilizar contexto real.")


def _render_prompt_studio() -> None:
    st.subheader("Prompt Studio · Maestro")
    st.caption("Estructura estable: cambia el contenido, no improvises la arquitectura del prompt.")
    rows = read_list(AI_PROMPTS_KEY)
    auto_context = _context_text()
    with st.form("marketing_ai_master_prompt", clear_on_submit=True):
        cols = st.columns(2)
        name = cols[0].text_input("Nombre del prompt")
        asset_type = cols[1].selectbox("Activo / uso", ASSET_TYPES)
        role = st.text_area("1 · Rol", placeholder="Ej. Experto en estrategia de contenido y marketing digital")
        objective = st.text_area("2 · Objetivo", placeholder="Qué debe conseguir la IA, de forma específica")
        deliverable = st.text_area("3 · Entregable / formato", placeholder="Tabla, guion, carrusel, blueprint, checklist...")
        context = st.text_area("4 · Contexto", value=auto_context, height=180)
        design_tokens = st.text_area("5 · Design Key Token System", placeholder="Colores, tipografías, escala, radios, espaciado. Déjalo vacío si no aplica.")
        structure = st.text_area("6 · Estructura", placeholder="Secciones, orden, longitud, jerarquía y componentes obligatorios")
        behavior = st.text_area("7 · Comportamiento", placeholder="Cómo debe razonar/iterar: preguntar si falta un dato, conservar lo aprobado, cambiar una sola cosa...")
        restrictions = st.text_area("8 · Restricciones", placeholder="Qué NO debe inventar, claims prohibidos, límites de tono, plataforma, longitud...")
        qa = st.text_area("9 · QA / criterios de aceptación", placeholder="Checklist verificable antes de considerar terminado el resultado")
        if st.form_submit_button("Guardar prompt maestro", type="primary", use_container_width=True) and name.strip():
            row = {
                "name": name.strip(), "asset_type": asset_type, "role": role.strip(), "objective": objective.strip(),
                "deliverable": deliverable.strip(), "context": context.strip(), "design_tokens": design_tokens.strip(),
                "structure": structure.strip(), "behavior": behavior.strip(), "restrictions": restrictions.strip(),
                "qa": qa.strip(), "created_at_utc": now_iso(),
            }
            row["completeness"] = prompt_completeness(row)
            row["prompt"] = compose_master_prompt(row)
            save_list(AI_PROMPTS_KEY, [*rows, row])
            st.success("Prompt maestro guardado.")
            st.rerun()

    if rows:
        for row in reversed(rows[-10:]):
            with st.expander(f"{row.get('name')} · {row.get('asset_type')} · {row.get('completeness', 0)}%"):
                st.code(row.get("prompt", compose_master_prompt(row)), language="markdown")
                st.download_button(
                    "Descargar prompt .md", row.get("prompt", compose_master_prompt(row)),
                    file_name=f"{row.get('name','prompt').replace(' ', '_')}.md", mime="text/markdown",
                    key=f"download_ai_prompt_{row.get('created_at_utc','')}_{row.get('name','')}",
                )


def _render_builder_projects() -> None:
    st.subheader("AI Builder · Activos digitales")
    st.caption("Planifica antes de generar. Permite iterar de forma quirúrgica y conservar lo que ya fue aprobado.")
    rows = read_list(AI_PROJECTS_KEY)
    with st.form("marketing_ai_project", clear_on_submit=True):
        cols = st.columns(2)
        name = cols[0].text_input("Proyecto / activo")
        asset_type = cols[1].selectbox("Tipo", ("Web informativa", "Landing de promoción", "Panel / herramienta", "Otro"), key="ai_project_type")
        objective = st.text_area("Objetivo del activo")
        conversion = st.text_input("Conversión principal", placeholder="WhatsApp, formulario, compra, reserva...")
        approved = st.text_area("Qué ya está aprobado y NO debe cambiar")
        next_change = st.text_area("Próximo cambio quirúrgico", placeholder="Una modificación concreta por iteración")
        qa = st.multiselect("QA", ("Marca", "Contenido", "Responsive/móvil", "Funcionalidad", "Conversión/CTA"))
        status = st.selectbox("Estado", ("Idea", "Contexto listo", "En construcción", "QA", "Aprobado", "Publicado"))
        if st.form_submit_button("Guardar proyecto", type="primary", use_container_width=True) and name.strip():
            save_list(AI_PROJECTS_KEY, [*rows, {
                "name": name.strip(), "asset_type": asset_type, "objective": objective.strip(),
                "conversion": conversion.strip(), "approved": approved.strip(), "next_change": next_change.strip(),
                "qa": qa, "status": status, "updated_at_utc": now_iso(),
            }])
            st.rerun()
    for row in reversed(rows[-10:]):
        with st.container(border=True):
            st.write(f"**{row.get('name')}** · {row.get('asset_type')} · {row.get('status')}")
            st.caption(f"Conversión: {row.get('conversion') or '—'} · Próximo cambio: {row.get('next_change') or '—'}")
            if row.get("approved"):
                st.info(f"Conservar: {row.get('approved')}")


def render_ai_builder() -> None:
    st.markdown("## IA & AI Builder")
    st.caption("Contexto primero. Después prompt, construcción, iteración y QA.")
    tabs = st.tabs(("Contexto", "Prompt Studio", "AI Builder"))
    with tabs[0]:
        _render_context()
    with tabs[1]:
        _render_prompt_studio()
    with tabs[2]:
        _render_builder_projects()
