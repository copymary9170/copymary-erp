"""Marketing Workspace: capa operativa unificada sobre las herramientas existentes.

No reemplaza los módulos especializados: los organiza por flujo de trabajo, evita
renderizarlos todos a la vez y añade dashboard, campañas padre y Content Studio.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from src.session_utils import now_iso, read_list, save_list
from src import marketing_guided_plan as guided
from src import marketing_strategy_suite as strategy
from src import marketing_content_strategy as content_strategy
from src import marketing_story_video as story_video
from src import marketing_ugc_tiktok as ugc_tiktok
from src import marketing_insights_meta as insights_meta
from src import marketing_academy_tools as academy
from src import marketing_ai_skills as ai_skills
from src import marketing_ai_builder as ai_builder

CAMPAIGNS_KEY = "marketing_workspace_campaigns"
CONTENT_KEY = "marketing_workspace_content"
LEARNINGS_KEY = "marketing_workspace_learnings"

SECTIONS = ("Inicio", "Estrategia", "Investigación", "Contenido", "Campañas", "IA", "Analítica")
CONTENT_STATUSES = ("Idea", "Guion", "Producción", "Revisión", "Aprobado", "Programado", "Publicado", "Medido")
CONTENT_FORMATS = ("Reel", "Historia", "Carrusel", "Post", "TikTok", "YouTube", "Email", "WhatsApp")
FUNNEL_STAGES = ("Descubrimiento", "Interés", "Consideración", "Conversión", "Fidelización")


def _latest_plan() -> dict:
    rows = read_list(guided.PLAN_KEY)
    return dict(rows[-1]) if rows else {str(i): {} for i in range(1, 11)}


def marketing_health() -> dict[str, float]:
    plan = _latest_plan()
    strategy_score = guided.completion_score(plan)
    research_items = len(read_list("marketing_consumer_insights")) + len(read_list("marketing_benchmarking"))
    research_score = min(100.0, research_items * 20.0)
    content = read_list(CONTENT_KEY)
    content_score = min(100.0, len(content) * 12.5)
    campaigns = read_list(CAMPAIGNS_KEY)
    campaign_score = min(100.0, len(campaigns) * 25.0)
    measured = sum(x.get("status") == "Medido" for x in content)
    analytics_score = min(100.0, measured * 25.0 + len(read_list("marketing_meta_tests")) * 10.0)
    total = (strategy_score + research_score + content_score + campaign_score + analytics_score) / 5
    return {
        "total": total, "strategy": strategy_score, "research": research_score,
        "content": content_score, "campaigns": campaign_score, "analytics": analytics_score,
    }


def next_action() -> tuple[str, str]:
    health = marketing_health()
    if health["strategy"] < 70:
        return "🔴", "Completa primero el Plan de Marketing guiado antes de producir más piezas."
    if health["research"] < 40:
        return "🟡", "Registra voz del consumidor y benchmarking para reducir decisiones basadas en supuestos."
    if health["content"] < 40:
        return "🟡", "Convierte la estrategia en piezas dentro de Content Studio."
    if health["campaigns"] < 25:
        return "🟡", "Agrupa las piezas bajo una campaña con objetivo, meta y presupuesto."
    if health["analytics"] < 40:
        return "🟡", "Mide las piezas publicadas y documenta qué debes repetir, cambiar o detener."
    return "🟢", "La base está lista. Prioriza ejecutar, medir y convertir resultados en aprendizajes reutilizables."


def _dashboard() -> None:
    health = marketing_health()
    campaigns = read_list(CAMPAIGNS_KEY)
    content = read_list(CONTENT_KEY)
    meta = read_list("marketing_meta_tests")
    st.markdown("## Marketing Workspace")
    st.caption("Estrategia → investigación → producción → campañas → IA → aprendizaje.")
    cols = st.columns(4)
    cols[0].metric("Marketing Score", f"{health['total']:.0f}%")
    cols[1].metric("Campañas", len(campaigns))
    cols[2].metric("Piezas activas", sum(x.get("status") not in ("Publicado", "Medido") for x in content))
    cols[3].metric("Pruebas Meta", len(meta))
    st.progress(health["total"] / 100)

    st.markdown("### Estado del sistema")
    names = (("Estrategia", "strategy"), ("Investigación", "research"), ("Contenido", "content"), ("Campañas", "campaigns"), ("Medición", "analytics"))
    for label, key in names:
        c1, c2 = st.columns((1, 4))
        c1.write(f"**{label}**")
        c2.progress(health[key] / 100, text=f"{health[key]:.0f}%")

    icon, action = next_action()
    st.markdown("### Siguiente acción recomendada")
    st.info(f"{icon} {action}")

    if content:
        st.markdown("### Próximo trabajo")
        pending = [x for x in content if x.get("status") not in ("Publicado", "Medido")]
        for row in pending[-5:]:
            st.write(f"**{row.get('title','Sin título')}** · {row.get('channel','')} / {row.get('format','')} · {row.get('status','Idea')}")


def _content_studio() -> None:
    st.subheader("Content Studio")
    st.caption("Una sola ficha acompaña la pieza desde la idea hasta la medición.")
    rows = read_list(CONTENT_KEY)
    campaigns = read_list(CAMPAIGNS_KEY)
    campaign_names = [x.get("name", "") for x in campaigns if x.get("name")]
    with st.form("workspace_content", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        title = c1.text_input("Título interno")
        campaign = c2.selectbox("Campaña", ["Sin campaña", *campaign_names])
        status = c3.selectbox("Estado", CONTENT_STATUSES)
        c1, c2, c3, c4 = st.columns(4)
        channel = c1.selectbox("Canal", ("Instagram", "TikTok", "Facebook", "YouTube", "Email", "WhatsApp", "Otro"))
        format_ = c2.selectbox("Formato", CONTENT_FORMATS)
        funnel = c3.selectbox("Etapa del embudo", FUNNEL_STAGES)
        objective = c4.text_input("Objetivo", placeholder="Ventas, leads, alcance...")
        customer_question = st.text_area("Duda / problema real del cliente")
        hook = st.text_input("Hook")
        structure = st.selectbox("Estructura", ("AIDA", "PAS", "PASTOR", "Storytelling", "Demostración", "Testimonio", "Otra"))
        script = st.text_area("Guion / copy")
        cta = st.text_input("CTA")
        c1, c2 = st.columns(2)
        canva = c1.text_input("Enlace Canva / recurso")
        path = c2.text_input("Ruta del archivo")
        if st.form_submit_button("Guardar pieza", type="primary", use_container_width=True) and title.strip():
            save_list(CONTENT_KEY, [*rows, {
                "title": title.strip(), "campaign": campaign, "status": status, "channel": channel,
                "format": format_, "funnel": funnel, "objective": objective.strip(),
                "customer_question": customer_question.strip(), "hook": hook.strip(), "structure": structure,
                "script": script.strip(), "cta": cta.strip(), "canva": canva.strip(), "path": path.strip(),
                "created_at_utc": now_iso(),
            }])
            st.rerun()
    rows = read_list(CONTENT_KEY)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("#### Registrar resultado de una pieza")
    if rows:
        choices = [f"{i+1}. {x.get('title','Sin título')}" for i, x in enumerate(rows)]
        selected = st.selectbox("Pieza", choices)
        idx = choices.index(selected)
        c1, c2, c3, c4 = st.columns(4)
        views = c1.number_input("Vistas / alcance", min_value=0, step=1)
        interactions = c2.number_input("Interacciones", min_value=0, step=1)
        leads = c3.number_input("Leads", min_value=0, step=1)
        sales = c4.number_input("Ventas", min_value=0, step=1)
        learning = st.text_area("Aprendizaje", placeholder="Qué funcionó, qué no y qué cambiarás")
        if st.button("Guardar medición", type="primary", use_container_width=True):
            updated = [dict(x) for x in rows]
            updated[idx].update({"views": int(views), "interactions": int(interactions), "leads": int(leads), "sales": int(sales), "learning": learning.strip(), "status": "Medido", "measured_at_utc": now_iso()})
            save_list(CONTENT_KEY, updated)
            if learning.strip():
                learns = read_list(LEARNINGS_KEY)
                save_list(LEARNINGS_KEY, [*learns, {"source": updated[idx].get("title"), "learning": learning.strip(), "created_at_utc": now_iso()}])
            st.rerun()


def _campaign_center() -> None:
    st.subheader("Campaign Center")
    st.caption("Agrupa contenido, Paid Media y resultados bajo un mismo objetivo.")
    rows = read_list(CAMPAIGNS_KEY)
    with st.form("workspace_campaign", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Campaña")
        objective = c2.text_input("Objetivo")
        c1, c2, c3 = st.columns(3)
        budget = c1.number_input("Presupuesto USD", min_value=0.0)
        target = c2.text_input("Meta", placeholder="40 pedidos / 100 leads")
        due = c3.date_input("Fecha objetivo", date.today())
        audience = st.text_area("Audiencia / segmento")
        offer = st.text_area("Oferta / mensaje principal")
        if st.form_submit_button("Crear campaña", type="primary", use_container_width=True) and name.strip():
            save_list(CAMPAIGNS_KEY, [*rows, {"name": name.strip(), "objective": objective.strip(), "budget": budget, "target": target.strip(), "due": due.isoformat(), "audience": audience.strip(), "offer": offer.strip(), "status": "Activa", "created_at_utc": now_iso()}])
            st.rerun()
    rows = read_list(CAMPAIGNS_KEY)
    content = read_list(CONTENT_KEY)
    for row in reversed(rows):
        linked = [x for x in content if x.get("campaign") == row.get("name")]
        with st.expander(f"{row.get('name')} · {row.get('status','Activa')}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Presupuesto", f"${float(row.get('budget',0) or 0):,.2f}")
            c2.metric("Piezas", len(linked))
            c3.metric("Ventas registradas", sum(int(x.get("sales",0) or 0) for x in linked))
            st.write(f"**Objetivo:** {row.get('objective','—')} · **Meta:** {row.get('target','—')}")
            st.caption(f"Audiencia: {row.get('audience','')} | Oferta: {row.get('offer','')}")

    st.divider()
    tabs = st.tabs(("Meta Ads Lab", "Email Marketing", "Preparación Ads", "QA creativo"))
    with tabs[0]: insights_meta.render_meta_ads_lab()
    with tabs[1]: academy._render_email_marketing()
    with tabs[2]: academy._render_meta_readiness()
    with tabs[3]: academy._render_creative_qa()


def _analytics() -> None:
    st.subheader("Analítica + Biblioteca de aprendizajes")
    content = read_list(CONTENT_KEY)
    measured = [x for x in content if x.get("status") == "Medido"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Piezas medidas", len(measured))
    c2.metric("Vistas / alcance", sum(int(x.get("views",0) or 0) for x in measured))
    c3.metric("Leads", sum(int(x.get("leads",0) or 0) for x in measured))
    c4.metric("Ventas", sum(int(x.get("sales",0) or 0) for x in measured))
    if measured:
        st.dataframe(measured, use_container_width=True, hide_index=True)
    st.markdown("#### Aprendizajes")
    learns = read_list(LEARNINGS_KEY)
    if learns:
        for row in reversed(learns[-20:]):
            st.write(f"**{row.get('source','Marketing')}** — {row.get('learning','')}")
    else:
        st.info("Cuando midas contenido y registres conclusiones, aparecerán aquí.")


def render_marketing_workspace() -> None:
    st.markdown("# Marketing")
    section = st.radio("Área de trabajo", SECTIONS, horizontal=True, label_visibility="collapsed")
    st.divider()
    if section == "Inicio":
        _dashboard()
    elif section == "Estrategia":
        guided.render_marketing_guided_plan()
        with st.expander("Herramientas estratégicas avanzadas"):
            strategy.render_marketing()
    elif section == "Investigación":
        insights_meta.render_consumer_voice()
        st.divider()
        content_strategy.render_marketing_content_strategy()
    elif section == "Contenido":
        _content_studio()
        st.divider()
        with st.expander("Storytelling, video, UGC y TikTok"):
            story_video.render_marketing_story_video()
            ugc_tiktok.render_marketing_ugc_tiktok()
    elif section == "Campañas":
        _campaign_center()
    elif section == "IA":
        tabs = st.tabs(("AI Skills", "AI Builder"))
        with tabs[0]: ai_skills.render_marketing_ai_skills()
        with tabs[1]: ai_builder.render_marketing_ai_builder()
    else:
        _analytics()
