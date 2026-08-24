"""Laboratorio de crecimiento: comunidad, objetivos SMART y método de acción."""
from __future__ import annotations
from datetime import date
from uuid import uuid4
import streamlit as st
from src.session_utils import now_iso, read_list, save_list

GOALS_KEY = "marketing_smart_goals"
COMMUNITY_KEY = "marketing_community_actions"
AWARENESS_LEVELS = ("Desconoce", "Consciente del problema", "Consciente de la solución", "Consciente del producto", "Totalmente consciente")
COMMUNITY_STAGES = ("Audiencia", "Comunidad", "Seguidores", "Leads", "Prospectos", "Clientes", "Promotores")
ACTION_METHOD = ("Atención", "Interés", "Deseo", "Acción")


def smart_score(goal: dict) -> tuple[int, list[str]]:
    checks = [
        (bool(str(goal.get("specific", "")).strip()), "Haz el objetivo específico."),
        (float(goal.get("target", 0) or 0) > 0, "Define una meta medible."),
        (bool(str(goal.get("achievable", "")).strip()), "Explica por qué es alcanzable."),
        (bool(str(goal.get("relevant", "")).strip()), "Relaciona la meta con el negocio."),
        (bool(str(goal.get("deadline", "")).strip()), "Asigna una fecha límite."),
    ]
    failures=[m for ok,m in checks if not ok]
    return round((len(checks)-len(failures))/len(checks)*100), failures


def community_diagnosis(actions: list[dict]) -> list[str]:
    if not actions:
        return ["Todavía no has registrado acciones para construir comunidad."]
    stages={str(x.get("stage", "")) for x in actions}
    messages=[]
    if "Audiencia" in stages and "Comunidad" not in stages:
        messages.append("Estás trabajando alcance, pero falta una acción explícita para convertir audiencia en comunidad.")
    if "Seguidores" in stages and not ({"Leads", "Prospectos", "Clientes"} & stages):
        messages.append("Hay acciones para conseguir seguidores, pero ninguna conduce todavía a una oportunidad comercial.")
    if "Clientes" in stages and "Promotores" not in stages:
        messages.append("Ya trabajas clientes; agrega fidelización, recomendación o contenido generado por clientes para crear promotores.")
    return messages or ["El recorrido de comunidad cubre varias etapas. Mide qué acciones hacen avanzar a las personas."]


def render_growth_lab() -> None:
    st.header("Crecimiento y comunidad")
    st.caption("Convierte los conceptos de comunidad, niveles de conciencia, objetivos SMART y método de acción en tareas medibles.")
    tab1,tab2,tab3=st.tabs(["Objetivos SMART","Comunidad","Método de acción"])
    with tab1:
        goals=read_list(GOALS_KEY)
        with st.form("smart_goal", clear_on_submit=True):
            name=st.text_input("Objetivo")
            specific=st.text_area("Específico: ¿qué quieres lograr exactamente?")
            c1,c2=st.columns(2)
            target=c1.number_input("Meta numérica",min_value=0.0,step=1.0)
            metric=c2.text_input("Métrica",placeholder="ventas, leads, seguidores, alcance...")
            achievable=st.text_area("Alcanzable: ¿por qué es realista?")
            relevant=st.text_area("Relevante: ¿cómo ayuda al negocio?")
            deadline=st.date_input("Fecha límite",value=date.today())
            if st.form_submit_button("Guardar objetivo",type="primary") and name.strip():
                row={"goal_id":uuid4().hex,"name":name.strip(),"specific":specific.strip(),"target":target,"metric":metric.strip(),"achievable":achievable.strip(),"relevant":relevant.strip(),"deadline":deadline.isoformat(),"created_at":now_iso()}
                row["score"]=smart_score(row)[0]; save_list(GOALS_KEY,goals+[row]); st.success("Objetivo SMART guardado."); st.rerun()
        for g in goals:
            st.markdown(f"**{g.get('name','Objetivo')}** · {g.get('target',0):g} {g.get('metric','')} · vence {g.get('deadline','—')} · SMART {g.get('score', smart_score(g)[0])}%")
    with tab2:
        actions=read_list(COMMUNITY_KEY)
        with st.form("community_action",clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            stage=c1.selectbox("Etapa",COMMUNITY_STAGES)
            awareness=c2.selectbox("Nivel de conciencia",AWARENESS_LEVELS)
            channel=c3.text_input("Canal",placeholder="Instagram, TikTok, WhatsApp...")
            action=st.text_area("Acción concreta",placeholder="Ej.: responder comentarios con una pregunta para abrir conversación")
            signal=st.text_input("Señal de avance",placeholder="Ej.: respuestas, mensajes, guardados, consultas")
            if st.form_submit_button("Guardar acción",type="primary") and action.strip():
                save_list(COMMUNITY_KEY,actions+[{"action_id":uuid4().hex,"stage":stage,"awareness":awareness,"channel":channel.strip(),"action":action.strip(),"signal":signal.strip(),"created_at":now_iso()}]); st.success("Acción guardada."); st.rerun()
        for msg in community_diagnosis(actions): st.info(msg)
        for a in actions[-12:]: st.markdown(f"**{a.get('stage')} · {a.get('awareness')}** — {a.get('action')}  \nSeñal: {a.get('signal') or 'sin definir'}")
    with tab3:
        st.write("Diseña una pieza o acción siguiendo cuatro pasos: captar atención, sostener interés, construir deseo y pedir una acción clara.")
        c1,c2=st.columns(2)
        with c1:
            attention=st.text_area("1. Atención",key="growth_attention")
            interest=st.text_area("2. Interés",key="growth_interest")
        with c2:
            desire=st.text_area("3. Deseo",key="growth_desire")
            action=st.text_area("4. Acción / CTA",key="growth_action")
        completed=sum(bool(x.strip()) for x in (attention,interest,desire,action))
        st.progress(completed/4,text=f"Estructura completada: {completed}/4")
