"""Biblioteca de Skills reutilizables para Marketing Pro.

Basado en IA1: un Skill es una carpeta/instrucción reutilizable que enseña a Claude
cómo trabajar una tarea. El ERP documenta el Skill; no intenta controlar servicios externos.
"""
from __future__ import annotations

import streamlit as st
from src.session_utils import now_iso, read_list, save_list

SKILLS_KEY = "marketing_ai_skills"
SKILL_RUNS_KEY = "marketing_ai_skill_runs"


def skill_readiness(data: dict) -> float:
    required = ("objective", "skill_md", "assets", "activation")
    return sum(bool(str(data.get(k, "")).strip()) for k in required) / len(required) * 100


def render_marketing_ai_skills() -> None:
    st.markdown("### AI Skills · procedimientos reutilizables")
    st.caption("Define una vez cómo debe trabajar la IA y reutiliza ese estándar en tareas repetitivas.")
    tabs = st.tabs(["Biblioteca", "Crear Skill", "Activaciones", "Usos recomendados"])

    with tabs[0]:
        rows = read_list(SKILLS_KEY)
        if not rows:
            st.info("Aún no hay Skills documentados.")
        for row in reversed(rows[-20:]):
            with st.expander(f"{row.get('name','Skill')} · {row.get('status','Borrador')}"):
                st.write(row.get("objective", ""))
                st.metric("Preparación", f"{skill_readiness(row):.0f}%")
                st.code(row.get("skill_md", ""), language="markdown")
                if row.get("assets"):
                    st.caption("Assets / referencias: " + row["assets"])
                if row.get("activation"):
                    st.caption("Cuándo usarlo: " + row["activation"])

    with tabs[1]:
        with st.form("marketing_skill_form"):
            name = st.text_input("Nombre del Skill", placeholder="Copy de Instagram · Kairoforia")
            objective = st.text_area("1 · Define el objetivo", placeholder="Qué tarea repetitiva debe estandarizar")
            skill_md = st.text_area("2 · Escribe el SKILL.md", height=180, placeholder="Instrucciones, proceso, criterios y reglas de trabajo...")
            assets = st.text_area("3 · Añade assets", placeholder="Guía de marca, ejemplos aprobados, plantillas, checklist, referencias...")
            activation = st.text_area("4 · Actívalo", placeholder="Cuándo debe usarse y qué solicitud lo dispara")
            status = st.selectbox("Estado", ["Borrador", "Probando", "Aprobado", "Obsoleto"])
            if st.form_submit_button("Guardar Skill", type="primary", use_container_width=True):
                rows = read_list(SKILLS_KEY)
                row = {"name": name.strip() or "Skill sin nombre", "objective": objective.strip(), "skill_md": skill_md.strip(), "assets": assets.strip(), "activation": activation.strip(), "status": status, "created_at_utc": now_iso()}
                save_list(SKILLS_KEY, [*rows, row])
                st.success(f"Skill guardado · preparación {skill_readiness(row):.0f}%")

    with tabs[2]:
        skills = [r for r in read_list(SKILLS_KEY) if r.get("status") != "Obsoleto"]
        if not skills:
            st.info("Crea un Skill antes de registrar activaciones.")
        else:
            with st.form("marketing_skill_run"):
                selected = st.selectbox("Skill", [r.get("name", "Skill") for r in skills])
                request = st.text_area("Tarea solicitada")
                result = st.text_area("Resultado / enlace / referencia")
                qa = st.selectbox("QA humano", ["Pendiente", "Aprobado", "Requiere corrección"])
                lesson = st.text_area("Aprendizaje para mejorar el Skill")
                if st.form_submit_button("Registrar uso", use_container_width=True):
                    runs = read_list(SKILL_RUNS_KEY)
                    save_list(SKILL_RUNS_KEY, [*runs, {"skill": selected, "request": request.strip(), "result": result.strip(), "qa": qa, "lesson": lesson.strip(), "created_at_utc": now_iso()}])
                    st.success("Uso registrado.")
            runs = read_list(SKILL_RUNS_KEY)
            if runs:
                approved = sum(r.get("qa") == "Aprobado" for r in runs)
                st.metric("Tasa de aprobación", f"{approved / len(runs) * 100:.0f}%")

    with tabs[3]:
        st.markdown("**Documentos con tu branding** — facturas, propuestas, cotizaciones o piezas que deban respetar logo, colores y tipografía.")
        st.markdown("**Metodologías para informes** — estructura fija, secciones, conclusiones y recomendaciones para reportes repetitivos.")
        st.markdown("**Configuración de tu suite** — documentar cómo trabajas con tus herramientas y qué reglas debe respetar la IA.")
        st.info("El ERP guarda la metodología y su QA. La conexión técnica con Claude, Gmail u otras herramientas requiere sus integraciones correspondientes.")
