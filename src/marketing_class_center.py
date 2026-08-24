"""Centro de Marketing basado en estrategia, contenido y embudo de conversión."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import streamlit as st

from src import marketing_guided_plan as guided
from src import marketing_strategy_suite as strategy
from src import marketing_content_calendar as content_calendar
from src import marketing_workspace as legacy
from src.session_utils import now_iso, read_list, save_list

PERSONAS_KEY = "marketing_workspace_personas"
PILLARS_KEY = "marketing_workspace_pillars"
LEADS_KEY = "marketing_workspace_leads"
CONTENT_KEY = legacy.CONTENT_KEY
CAMPAIGNS_KEY = legacy.CAMPAIGNS_KEY
LEARNINGS_KEY = legacy.LEARNINGS_KEY

SECTIONS = ("Estrategia", "Buyer persona", "Pilares", "Contenido", "Calendario", "Embudo", "Campañas", "Métricas")
CHANNELS = ("Instagram", "TikTok", "Facebook", "YouTube", "Email", "WhatsApp", "Tienda física", "Otro")
CONTENT_FORMATS = legacy.CONTENT_FORMATS
CONTENT_STATUSES = legacy.CONTENT_STATUSES
FUNNEL_STAGES = ("Reconocimiento", "Necesidad", "Solución", "Demostración", "Confianza", "CTA", "Lead", "Cliente")
LEGACY_FUNNEL_MAP = {"Descubrimiento": "Reconocimiento", "Interés": "Necesidad", "Consideración": "Solución", "Conversión": "CTA", "Fidelización": "Cliente"}
DEFAULT_PILLARS = (
    ("Educativo", "Enseña algo útil y reduce dudas antes de comprar."),
    ("Productos y servicios", "Muestra qué resuelve el negocio y para quién."),
    ("Demostración / proceso", "Enseña materiales, preparación, acabado y resultado."),
    ("Confianza / prueba social", "Testimonios, resultados y evidencias."),
    ("Promociones", "Ofertas, temporadas, combos y llamados directos a comprar."),
    ("Comunidad", "Contenido que genera conversación, identificación y cercanía."),
)


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def normalized_stage(row: dict) -> str:
    stage = str(row.get("funnel_stage") or row.get("funnel") or "").strip()
    return LEGACY_FUNNEL_MAP.get(stage, stage)


def funnel_stage_counts(content: list[dict], leads: list[dict] | None = None) -> dict[str, int]:
    counts = {stage: 0 for stage in FUNNEL_STAGES}
    for row in content:
        stage = normalized_stage(row)
        if stage in counts:
            counts[stage] += 1
    for row in leads or []:
        stage = LEGACY_FUNNEL_MAP.get(str(row.get("stage", "")).strip(), str(row.get("stage", "")).strip())
        if stage in ("Lead", "Cliente"):
            counts[stage] += 1
    return counts


def content_metrics(content: list[dict]) -> dict[str, float]:
    measured = [row for row in content if row.get("status") in ("Publicado", "Medido")]
    reach = sum(_number(row.get("views", row.get("reach"))) for row in measured)
    interactions = sum(_number(row.get("interactions")) for row in measured)
    clicks = sum(_number(row.get("clicks")) for row in measured)
    leads = sum(_number(row.get("leads")) for row in measured)
    sales = sum(_number(row.get("sales")) for row in measured)
    revenue = sum(_number(row.get("revenue")) for row in measured)
    spend = sum(_number(row.get("spend")) for row in measured)
    return {
        "published": len(measured), "reach": reach, "interactions": interactions, "clicks": clicks,
        "leads": leads, "sales": sales, "revenue": revenue, "spend": spend,
        "engagement": interactions / reach * 100 if reach else 0.0,
        "lead_conversion": leads / clicks * 100 if clicks else 0.0,
        "sales_conversion": sales / leads * 100 if leads else 0.0,
        "roas": revenue / spend if spend else 0.0,
    }


def marketing_diagnosis(content: list[dict], leads: list[dict] | None = None) -> list[str]:
    counts = funnel_stage_counts(content, leads)
    content_total = sum(counts[stage] for stage in FUNNEL_STAGES[:-2])
    if not content_total:
        return ["Todavía no hay suficiente contenido clasificado para diagnosticar el embudo."]
    messages = []
    missing = [stage for stage in FUNNEL_STAGES[:-2] if counts[stage] == 0]
    if missing:
        messages.append("Faltan etapas de contenido: " + ", ".join(missing) + ".")
    if counts["Reconocimiento"] + counts["Necesidad"] >= 3 and counts["CTA"] + counts["Lead"] + counts["Cliente"] == 0:
        messages.append("Hay contenido para atraer, pero falta conducir la audiencia hacia CTA, leads o clientes.")
    if counts["CTA"] and not counts["Demostración"] and not counts["Confianza"]:
        messages.append("Estás pidiendo acción sin suficiente demostración o confianza previa.")
    metrics = content_metrics(content)
    if metrics["published"] >= 3 and not metrics["leads"]:
        messages.append("Hay varias piezas publicadas pero no registran leads. Revisa oferta, CTA y captura de consultas.")
    return messages or ["El embudo está razonablemente equilibrado. Sigue midiendo qué etapas generan consultas y ventas."]


def _pillar_rows() -> list[dict]:
    rows = read_list(PILLARS_KEY)
    if rows:
        return rows
    return [{"pillar_id": f"DEFAULT-{i}", "name": name, "purpose": purpose} for i, (name, purpose) in enumerate(DEFAULT_PILLARS, 1)]


def _strategy() -> None:
    st.subheader("Estrategia")
    st.caption("Primero define objetivo, propuesta de valor, audiencia y mensaje; después crea contenido.")
    guided.render_marketing_guided_plan()
    with st.expander("Herramientas estratégicas avanzadas"):
        strategy.render_marketing()


def _personas() -> None:
    st.subheader("Buyer persona")
    rows = read_list(PERSONAS_KEY)
    with st.form("class_persona", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nombre del perfil", placeholder="Ej. Estudiante con entrega urgente")
        segment = c2.text_input("Segmento / contexto")
        c1, c2 = st.columns(2)
        needs = c1.text_area("Necesidades / deseos")
        problems = c2.text_area("Problemas / frustraciones")
        c1, c2 = st.columns(2)
        interests = c1.text_area("Intereses / qué valora")
        objections = c2.text_area("Objeciones antes de comprar")
        channels = st.multiselect("Dónde podemos alcanzarlo", CHANNELS)
        services = st.text_input("Productos o servicios relacionados")
        trigger = st.text_input("Qué lo impulsa a actuar")
        if st.form_submit_button("Guardar buyer persona", type="primary", use_container_width=True) and name.strip():
            save_list(PERSONAS_KEY, [*rows, {"persona_id": f"MKT-PER-{uuid4().hex[:8].upper()}", "name": name.strip(), "segment": segment.strip(), "needs": needs.strip(), "problems": problems.strip(), "interests": interests.strip(), "objections": objections.strip(), "channels": channels, "services": services.strip(), "trigger": trigger.strip(), "created_at_utc": now_iso()}])
            st.rerun()
    for row in reversed(rows):
        with st.expander(row.get("name", "Buyer persona")):
            st.write(f"**Necesidades:** {row.get('needs') or row.get('need') or '—'}")
            st.write(f"**Problemas:** {row.get('problems') or row.get('pain') or '—'}")
            st.write(f"**Intereses:** {row.get('interests') or '—'}")
            st.write(f"**Objeciones:** {row.get('objections') or '—'}")


def _pillars() -> None:
    st.subheader("Pilares de contenido")
    stored = read_list(PILLARS_KEY)
    rows = _pillar_rows()
    if not stored:
        st.info("Tienes seis pilares sugeridos listos para usar. Puedes personalizarlos creando los tuyos.")
    with st.form("class_pillar", clear_on_submit=True):
        c1, c2 = st.columns((1, 2))
        name = c1.text_input("Nombre del pilar")
        purpose = c2.text_input("Función del pilar")
        if st.form_submit_button("Agregar pilar", type="primary", use_container_width=True) and name.strip():
            base = stored or [dict(row) for row in rows]
            base = [row for row in base if str(row.get("name", "")).casefold() != name.strip().casefold()]
            base.append({"pillar_id": f"MKT-PIL-{uuid4().hex[:8].upper()}", "name": name.strip(), "purpose": purpose.strip(), "created_at_utc": now_iso()})
            save_list(PILLARS_KEY, base)
            st.rerun()
    content = read_list(CONTENT_KEY)
    for row in rows:
        with st.container(border=True):
            c1, c2 = st.columns((3, 1))
            c1.write(f"**{row.get('name')}**")
            c1.caption(row.get("purpose", ""))
            c2.metric("Piezas", sum(x.get("pillar") == row.get("name") for x in content))


def _content() -> None:
    st.subheader("Contenido")
    rows = read_list(CONTENT_KEY)
    campaigns = [x.get("name") for x in read_list(CAMPAIGNS_KEY) if x.get("name")]
    personas = [x.get("name") for x in read_list(PERSONAS_KEY) if x.get("name")]
    pillars = [x.get("name") for x in _pillar_rows() if x.get("name")]
    with st.form("class_content", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        title = c1.text_input("Título interno")
        campaign = c2.selectbox("Campaña", ["Sin campaña", *campaigns])
        status = c3.selectbox("Estado", CONTENT_STATUSES)
        c1, c2, c3, c4 = st.columns(4)
        channel = c1.selectbox("Canal", CHANNELS)
        format_ = c2.selectbox("Formato", CONTENT_FORMATS)
        pillar = c3.selectbox("Pilar", pillars)
        stage = c4.selectbox("Etapa del embudo", FUNNEL_STAGES[:-2])
        c1, c2 = st.columns(2)
        persona = c1.selectbox("Buyer persona", ["Sin asignar", *personas])
        objective = c2.text_input("Objetivo de la pieza")
        problem = st.text_area("Problema / duda real que aborda")
        hook = st.text_input("Gancho / primera frase")
        script = st.text_area("Guion / copy")
        cta = st.text_input("CTA")
        c1, c2 = st.columns(2)
        canva = c1.text_input("Enlace Canva / recurso")
        path = c2.text_input("Ruta del archivo")
        if st.form_submit_button("Guardar pieza", type="primary", use_container_width=True) and title.strip():
            save_list(CONTENT_KEY, [*rows, {"content_id": f"MKT-CNT-{uuid4().hex[:8].upper()}", "title": title.strip(), "campaign": campaign, "status": status, "channel": channel, "format": format_, "pillar": pillar, "funnel": stage, "funnel_stage": stage, "persona": persona, "objective": objective.strip(), "customer_question": problem.strip(), "hook": hook.strip(), "script": script.strip(), "cta": cta.strip(), "canva": canva.strip(), "path": path.strip(), "created_at_utc": now_iso()}])
            st.rerun()
    rows = read_list(CONTENT_KEY)
    if rows:
        st.dataframe([{"Título": x.get("title"), "Canal": x.get("channel"), "Formato": x.get("format"), "Pilar": x.get("pillar", "—"), "Embudo": normalized_stage(x), "Persona": x.get("persona", "—"), "Estado": x.get("status")} for x in rows], use_container_width=True, hide_index=True)
        selected = st.selectbox("Medir pieza", range(len(rows)), format_func=lambda i: rows[i].get("title", f"Pieza {i+1}"))
        c1, c2, c3, c4 = st.columns(4)
        reach = c1.number_input("Alcance", min_value=0, key="mkt_reach")
        interactions = c2.number_input("Interacciones", min_value=0, key="mkt_interactions")
        clicks = c3.number_input("Clics / acciones", min_value=0, key="mkt_clicks")
        leads = c4.number_input("Leads", min_value=0, key="mkt_leads")
        c1, c2, c3 = st.columns(3)
        sales = c1.number_input("Ventas", min_value=0, key="mkt_sales")
        revenue = c2.number_input("Ingresos USD", min_value=0.0, key="mkt_revenue")
        spend = c3.number_input("Inversión USD", min_value=0.0, key="mkt_spend")
        learning = st.text_area("Aprendizaje")
        if st.button("Guardar medición", type="primary", use_container_width=True):
            updated = [dict(x) for x in rows]
            updated[selected].update({"views": reach, "interactions": interactions, "clicks": clicks, "leads": leads, "sales": sales, "revenue": revenue, "spend": spend, "learning": learning.strip(), "status": "Medido", "measured_at_utc": now_iso()})
            save_list(CONTENT_KEY, updated)
            if learning.strip():
                save_list(LEARNINGS_KEY, [*read_list(LEARNINGS_KEY), {"source": updated[selected].get("title"), "learning": learning.strip(), "created_at_utc": now_iso()}])
            st.rerun()


def _calendar() -> None:
    st.subheader("Calendario editorial")
    content_calendar.render_content_calendar(read_list(CONTENT_KEY))


def _funnel() -> None:
    st.subheader("Embudo")
    st.caption("Reconocimiento → Necesidad → Solución → Demostración → Confianza → CTA → Lead → Cliente")
    content = read_list(CONTENT_KEY)
    leads = read_list(LEADS_KEY)
    counts = funnel_stage_counts(content, leads)
    cols = st.columns(4)
    for i, stage in enumerate(FUNNEL_STAGES):
        cols[i % 4].metric(stage, counts[stage])
    st.markdown("#### Diagnóstico automático")
    for message in marketing_diagnosis(content, leads):
        st.info(message)
    with st.form("class_lead", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        contact = c1.text_input("Contacto / referencia")
        source = c2.selectbox("Origen", CHANNELS)
        stage = c3.selectbox("Estado", ("Lead", "Cliente"))
        c1, c2 = st.columns(2)
        interest = c1.text_input("Interés / servicio")
        value = c2.number_input("Valor potencial / venta USD", min_value=0.0)
        notes = st.text_area("Notas")
        if st.form_submit_button("Registrar oportunidad", type="primary", use_container_width=True) and contact.strip():
            save_list(LEADS_KEY, [*leads, {"lead_id": f"MKT-LEAD-{uuid4().hex[:8].upper()}", "contact": contact.strip(), "source": source, "stage": stage, "interest": interest.strip(), "value": value, "notes": notes.strip(), "created_at_utc": now_iso()}])
            st.rerun()
    if leads:
        st.dataframe(leads, use_container_width=True, hide_index=True)


def _campaigns() -> None:
    st.subheader("Campañas")
    st.caption("Las campañas siguen usando el centro existente, ahora alimentadas por contenido clasificado.")
    legacy._campaign_center()


def _metrics() -> None:
    st.subheader("Métricas")
    content = read_list(CONTENT_KEY)
    metrics = content_metrics(content)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Alcance", int(metrics["reach"]))
    c2.metric("Interacciones", int(metrics["interactions"]))
    c3.metric("Leads", int(metrics["leads"]))
    c4.metric("Ventas", int(metrics["sales"]))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Engagement", f"{metrics['engagement']:.1f}%")
    c2.metric("Clic → lead", f"{metrics['lead_conversion']:.1f}%")
    c3.metric("Lead → venta", f"{metrics['sales_conversion']:.1f}%")
    c4.metric("ROAS", f"{metrics['roas']:.2f}x")
    c1, c2 = st.columns(2)
    c1.metric("Ingreso atribuido", f"${metrics['revenue']:,.2f}")
    c2.metric("Inversión atribuida", f"${metrics['spend']:,.2f}")
    st.markdown("#### Aprendizajes")
    learns = read_list(LEARNINGS_KEY)
    if learns:
        for row in reversed(learns[-20:]):
            st.write(f"**{row.get('source', 'Marketing')}** — {row.get('learning', '')}")
    else:
        st.info("Cuando midas contenido y registres conclusiones, aparecerán aquí.")


def render_marketing_class_center() -> None:
    st.markdown("# Centro de Marketing")
    st.caption("De la estrategia a la venta: buyer persona, pilares, contenido, embudo y resultados.")
    content = read_list(CONTENT_KEY)
    metrics = content_metrics(content)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Piezas", len(content))
    c2.metric("Leads medidos", int(metrics["leads"]))
    c3.metric("Ventas atribuidas", int(metrics["sales"]))
    c4.metric("ROAS", f"{metrics['roas']:.2f}x")
    section = st.radio("Área de trabajo", SECTIONS, horizontal=True, label_visibility="collapsed")
    st.divider()
    renderers = {"Estrategia": _strategy, "Buyer persona": _personas, "Pilares": _pillars, "Contenido": _content, "Calendario": _calendar, "Embudo": _funnel, "Campañas": _campaigns, "Métricas": _metrics}
    renderers[section]()
