"""Suite estratégica de Marketing para CopyMary ERP.

Extiende Marketing Pro con briefing, sistema Objetivo → Estrategia → Táctica,
benchmarking, personalidad de marca, social listening, UGC, hooks/copy y video.
La estructura se mantiene por capas para no duplicar las herramientas existentes.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

import streamlit as st

from src import marketing_academy_tools as base
from src.session_utils import now_iso, read_list, save_list

BRIEF_KEY = "marketing_brand_brief"
STRATEGY_TABLE_KEY = "marketing_strategy_table"
BENCHMARK_KEY = "marketing_benchmarking"
BRAND_PERSONALITY_KEY = "marketing_brand_personality"
SOCIAL_LISTENING_KEY = "marketing_social_listening"
UGC_KEY = "marketing_ugc"
HOOK_LIBRARY_KEY = "marketing_hook_library"
VIDEO_PLAN_KEY = "marketing_video_plan"

CONTENT_OBJECTIVES = (
    "Branding", "Alcance", "Interacción", "Leads", "Conversaciones", "Ventas", "Fidelización"
)
CONTENT_TYPES = (
    "Educativo", "Entretenimiento", "Autoridad", "Conversacional", "Conversión", "Experiencial", "Testimonial"
)
HOOK_TYPES = (
    "Beneficio", "Curiosidad", "Contraste", "Errores", "Falsas creencias", "Números + beneficio", "Números + errores"
)
COPY_FRAMEWORKS = ("AIDA", "PAS", "PASTOR", "Storytelling")
ARCHETYPES = (
    "Inocente", "Sabio", "Explorador", "Mago", "Héroe", "Rebelde", "Amante", "Bufón",
    "Hombre común", "Cuidador", "Gobernante", "Creador"
)
VIDEO_RATIOS = ("9:16 Vertical", "1:1 Cuadrado", "16:9 Horizontal")
VIDEO_SHOTS = ("Plano general", "Plano medio", "Primer plano", "Plano detalle", "Plano cenital", "Contrapicado")
VIDEO_MOVEMENTS = ("Estático", "Paneo", "Tilt", "Travelling", "Zoom in", "Zoom out", "Cámara en mano", "Seguimiento")
SENTIMENTS = ("Positivo", "Neutral", "Negativo")
UGC_IDEAS = (
    "Storytime + producto", "POV divertido/emocional", "Mini reseña / haul", "Transformación antes/después", "Reacción directa"
)
TOUCHPOINTS = (
    "Instagram", "Facebook", "TikTok", "LinkedIn", "YouTube", "WhatsApp Business", "Página web",
    "Blog", "Email Marketing", "Google Business Profile", "Marketplace", "Tienda física", "Eventos", "Referidos"
)


def content_strategy_completeness(row: dict) -> float:
    """Mide si una fila conserva la cadena estratégica mínima del material."""
    required = ("objective", "strategy", "tactic", "content_type", "kpi")
    completed = sum(bool(str(row.get(key, "")).strip()) for key in required)
    return completed / len(required) * 100


def social_listening_summary(rows: list[dict]) -> dict[str, int]:
    """Resume el sentimiento registrado sin inventar inferencias automáticas."""
    counts = Counter(str(row.get("sentiment", "")) for row in rows)
    return {sentiment: counts.get(sentiment, 0) for sentiment in SENTIMENTS}


def copy_framework_template(framework: str) -> tuple[str, ...]:
    """Devuelve los bloques de las estructuras de copy estudiadas."""
    structures = {
        "AIDA": ("Atención", "Interés", "Deseo", "Acción"),
        "PAS": ("Problema", "Agitación", "Solución"),
        "PASTOR": ("Problema", "Amplificación", "Story", "Transformación", "Oferta", "Respuesta"),
        "Storytelling": ("Situación", "Conflicto", "Cambio", "Resultado", "Aprendizaje / CTA"),
    }
    return structures[framework]


def _render_briefing() -> None:
    st.subheader("Briefing estratégico de marca")
    st.caption("Centraliza la información que marketing debe entender antes de crear contenido o campañas.")
    current = (read_list(BRIEF_KEY) or [{}])[-1]
    with st.form("mkt_strategy_brief"):
        cols = st.columns(2)
        brand = cols[0].text_input("Marca / empresa", value=current.get("brand", ""))
        city = cols[1].text_input("Ciudad / país", value=current.get("city", ""))
        cols = st.columns(2)
        purpose = cols[0].text_area("Propósito / misión", value=current.get("purpose", ""))
        value = cols[1].text_area("Propuesta de valor", value=current.get("value_proposition", ""))
        positioning = st.text_area("Posicionamiento y diferenciadores", value=current.get("positioning", ""))
        cols = st.columns(2)
        profitable = cols[0].text_area("Productos/servicios más rentables o prioritarios", value=current.get("profitable", ""))
        launches = cols[1].text_area("Lanzamientos / promociones próximas", value=current.get("launches", ""))
        st.markdown("**Cliente ideal**")
        cols = st.columns(2)
        demographics = cols[0].text_area("Datos demográficos", value=current.get("demographics", ""), placeholder="Edad, ubicación, profesión, nivel socioeconómico...")
        psychographics = cols[1].text_area("Psicografía", value=current.get("psychographics", ""), placeholder="Preocupaciones, aspiraciones, problemas, frustraciones...")
        cols = st.columns(2)
        objections = cols[0].text_area("Objeciones / factores de decisión", value=current.get("objections", ""))
        content_consumed = cols[1].text_area("Contenido y marcas que consume/admirra", value=current.get("content_consumed", ""))
        cols = st.columns(3)
        avg_ticket = cols[0].number_input("Ticket promedio USD", min_value=0.0, value=float(current.get("avg_ticket", 0) or 0))
        purchase_cycle = cols[1].text_input("Ciclo promedio de compra", value=current.get("purchase_cycle", ""))
        close_rate = cols[2].number_input("Tasa de cierre %", min_value=0.0, max_value=100.0, value=float(current.get("close_rate", 0) or 0))
        touchpoints = st.multiselect("Puntos de contacto actuales", TOUCHPOINTS, default=[x for x in current.get("touchpoints", []) if x in TOUCHPOINTS])
        best_content = st.text_area("Qué contenido/campañas han funcionado mejor y peor", value=current.get("best_content", ""))
        if st.form_submit_button("Guardar briefing", type="primary", use_container_width=True):
            row = {
                "brand": brand.strip(), "city": city.strip(), "purpose": purpose.strip(),
                "value_proposition": value.strip(), "positioning": positioning.strip(), "profitable": profitable.strip(),
                "launches": launches.strip(), "demographics": demographics.strip(), "psychographics": psychographics.strip(),
                "objections": objections.strip(), "content_consumed": content_consumed.strip(), "avg_ticket": avg_ticket,
                "purchase_cycle": purchase_cycle.strip(), "close_rate": close_rate, "touchpoints": touchpoints,
                "best_content": best_content.strip(), "updated_at_utc": now_iso(),
            }
            save_list(BRIEF_KEY, [row])
            st.success("Briefing guardado.")
            st.rerun()


def _render_strategy_table() -> None:
    st.subheader("Sistema Objetivo → Estrategia → Táctica → Contenido → KPI")
    st.caption("El calendario se construye después de esta cadena, no al revés.")
    rows = read_list(STRATEGY_TABLE_KEY)
    with st.form("mkt_strategy_row", clear_on_submit=True):
        cols = st.columns(2)
        objective = cols[0].selectbox("Objetivo de contenido", CONTENT_OBJECTIVES)
        smart = cols[1].text_input("Objetivo SMART", placeholder="Resultado + métrica + fecha")
        strategy = st.text_area("Estrategia (qué y por qué)", placeholder="Enfoque general para lograr el objetivo")
        tactic = st.text_area("Táctica (cómo, cuándo y con qué)", placeholder="Acción específica ejecutable")
        cols = st.columns(3)
        content_type = cols[0].selectbox("Tipo de contenido", CONTENT_TYPES)
        channel = cols[1].text_input("Canal / formato")
        frequency = cols[2].text_input("Frecuencia")
        cols = st.columns(4)
        kpi = cols[0].text_input("KPI")
        target = cols[1].text_input("Meta KPI")
        owner = cols[2].text_input("Responsable")
        budget = cols[3].number_input("Presupuesto USD", min_value=0.0)
        due = st.date_input("Fecha objetivo", date.today())
        if st.form_submit_button("Agregar a la estrategia", type="primary", use_container_width=True):
            row = {
                "objective": objective, "smart": smart.strip(), "strategy": strategy.strip(), "tactic": tactic.strip(),
                "content_type": content_type, "channel": channel.strip(), "frequency": frequency.strip(), "kpi": kpi.strip(),
                "target": target.strip(), "owner": owner.strip(), "budget": budget, "due_date": due.isoformat(),
                "created_at_utc": now_iso(),
            }
            save_list(STRATEGY_TABLE_KEY, [*rows, row])
            st.rerun()
    if rows:
        complete = sum(content_strategy_completeness(row) == 100 for row in rows)
        cols = st.columns(3)
        cols[0].metric("Líneas estratégicas", len(rows))
        cols[1].metric("Cadena completa", complete)
        cols[2].metric("Presupuesto planificado", f"${sum(float(x.get('budget', 0) or 0) for x in rows):,.2f}")
        for row in reversed(rows[-12:]):
            with st.container(border=True):
                st.write(f"**{row.get('objective')}** → {row.get('strategy') or 'Estrategia pendiente'}")
                st.caption(f"Táctica: {row.get('tactic','')} · {row.get('content_type')} · KPI: {row.get('kpi') or 'Pendiente'} · Meta: {row.get('target') or '—'}")


def _render_benchmarking() -> None:
    st.subheader("Benchmarking de competencia")
    st.caption("Distingue competidores directos e indirectos y registra dónde existe una oportunidad real.")
    rows = read_list(BENCHMARK_KEY)
    with st.form("mkt_benchmark", clear_on_submit=True):
        cols = st.columns(2)
        name = cols[0].text_input("Competidor")
        competitor_type = cols[1].selectbox("Tipo", ("Directo", "Indirecto"))
        cols = st.columns(2)
        prices = cols[0].text_area("Precios y modelo de negocio")
        trajectory = cols[1].text_area("Trayectoria / experiencia")
        cols = st.columns(2)
        location = cols[0].text_area("Ubicación / cobertura")
        social = cols[1].text_area("Redes sociales y cómo las usan")
        cols = st.columns(2)
        web = cols[0].text_area("Web y estrategia de contenido")
        reputation = cols[1].text_area("Reputación online/física")
        cols = st.columns(2)
        customer = cols[0].text_area("Consumidor / cliente")
        service = cols[1].text_area("Atención al cliente y comunicación")
        gap = st.text_area("Dónde gana, dónde pierde y oportunidad que deja libre")
        if st.form_submit_button("Guardar competidor", type="primary", use_container_width=True) and name.strip():
            row = {
                "name": name.strip(), "type": competitor_type, "prices": prices.strip(), "trajectory": trajectory.strip(),
                "location": location.strip(), "social": social.strip(), "web": web.strip(), "reputation": reputation.strip(),
                "customer": customer.strip(), "service": service.strip(), "gap": gap.strip(), "created_at_utc": now_iso(),
            }
            save_list(BENCHMARK_KEY, [*rows, row])
            st.rerun()
    if rows:
        direct = sum(x.get("type") == "Directo" for x in rows)
        indirect = sum(x.get("type") == "Indirecto" for x in rows)
        cols = st.columns(3)
        cols[0].metric("Competidores", len(rows)); cols[1].metric("Directos", direct); cols[2].metric("Indirectos", indirect)
        for row in reversed(rows[-8:]):
            with st.expander(f"{row.get('name')} · {row.get('type')}"):
                st.write(f"**Oportunidad:** {row.get('gap') or 'Sin definir'}")
                st.caption(f"Redes: {row.get('social','')} · Atención: {row.get('service','')}")


def _render_brand_personality() -> None:
    st.subheader("Personalidad y voz de marca")
    st.caption("Branding incluye cómo habla la marca y la experiencia que entrega, no solo su apariencia.")
    current = (read_list(BRAND_PERSONALITY_KEY) or [{}])[-1]
    with st.form("mkt_brand_personality"):
        cols = st.columns(2)
        primary = cols[0].selectbox("Arquetipo primario", ARCHETYPES, index=ARCHETYPES.index(current.get("primary")) if current.get("primary") in ARCHETYPES else 0)
        secondary = cols[1].selectbox("Arquetipo secundario", ARCHETYPES, index=ARCHETYPES.index(current.get("secondary")) if current.get("secondary") in ARCHETYPES else 0)
        adjectives = st.text_input("Personalidad en adjetivos", value=current.get("adjectives", ""), placeholder="Ej. clara, cálida, resolutiva, elegante")
        tone = st.text_area("Tono de comunicación", value=current.get("tone", ""))
        cols = st.columns(2)
        says = cols[0].text_area("SÍ dice", value=current.get("says", ""), placeholder="Palabras, expresiones y enfoques propios")
        avoids = cols[1].text_area("NO dice", value=current.get("avoids", ""), placeholder="Términos, promesas o tonos que no representan la marca")
        experience = st.text_area("Cómo debe sentirse la experiencia de marca y atención", value=current.get("experience", ""))
        if st.form_submit_button("Guardar personalidad", type="primary", use_container_width=True):
            save_list(BRAND_PERSONALITY_KEY, [{
                "primary": primary, "secondary": secondary, "adjectives": adjectives.strip(), "tone": tone.strip(),
                "says": says.strip(), "avoids": avoids.strip(), "experience": experience.strip(), "updated_at_utc": now_iso(),
            }])
            st.rerun()


def _render_social_listening() -> None:
    st.subheader("Social Listening")
    st.caption("Registra señales reales del mercado y sigue el ciclo Monitorear → Analizar → Actuar.")
    rows = read_list(SOCIAL_LISTENING_KEY)
    with st.form("mkt_social_listening", clear_on_submit=True):
        cols = st.columns(3)
        source = cols[0].text_input("Plataforma / fuente", placeholder="TikTok, Instagram, reseña, competencia...")
        topic = cols[1].text_input("Tema / hashtag / palabra clave")
        sentiment = cols[2].selectbox("Sentimiento", SENTIMENTS)
        mention = st.text_area("Qué está diciendo la audiencia", placeholder="Resume la conversación sin alterar el sentido")
        cols = st.columns(2)
        insight = cols[0].text_area("Insight / patrón detectado")
        action = cols[1].text_area("Acción estratégica", placeholder="Ajustar calendario, atención, oferta, posicionamiento...")
        trend = st.checkbox("Señal de tendencia o conversación emergente")
        if st.form_submit_button("Registrar escucha", type="primary", use_container_width=True) and (topic.strip() or mention.strip()):
            row = {
                "source": source.strip(), "topic": topic.strip(), "sentiment": sentiment, "mention": mention.strip(),
                "insight": insight.strip(), "action": action.strip(), "trend": trend, "created_at_utc": now_iso(),
            }
            save_list(SOCIAL_LISTENING_KEY, [*rows, row]); st.rerun()
    summary = social_listening_summary(rows)
    cols = st.columns(4)
    cols[0].metric("Señales", len(rows)); cols[1].metric("Positivas", summary["Positivo"]); cols[2].metric("Neutrales", summary["Neutral"]); cols[3].metric("Negativas", summary["Negativo"])
    for row in reversed(rows[-10:]):
        with st.container(border=True):
            st.write(f"**{row.get('topic') or 'Señal'}** · {row.get('sentiment')} · {row.get('source','')}")
            st.caption(f"Insight: {row.get('insight','')} · Acción: {row.get('action','')}")


def _render_ugc() -> None:
    st.subheader("UGC y prueba social")
    st.caption("Organiza contenido auténtico creado por clientes o creadores UGC y su reutilización.")
    rows = read_list(UGC_KEY)
    with st.form("mkt_ugc", clear_on_submit=True):
        cols = st.columns(3)
        creator = cols[0].text_input("Cliente / creador")
        creator_type = cols[1].selectbox("Origen", ("Cliente real", "Creador UGC"))
        concept = cols[2].selectbox("Concepto", UGC_IDEAS)
        product = st.text_input("Producto / servicio")
        reference = st.text_input("Enlace / referencia del contenido")
        cols = st.columns(2)
        status = cols[0].selectbox("Estado", ("Idea", "Solicitado", "Recibido", "Aprobado", "Publicado", "Reutilizado"))
        channel = cols[1].text_input("Canal de publicación")
        permission = st.checkbox("Permiso de uso/republicación documentado")
        notes = st.text_area("Notas / resultado / aprendizaje")
        if st.form_submit_button("Guardar UGC", type="primary", use_container_width=True) and (creator.strip() or product.strip()):
            row = {
                "creator": creator.strip(), "creator_type": creator_type, "concept": concept, "product": product.strip(),
                "reference": reference.strip(), "status": status, "channel": channel.strip(), "permission": permission,
                "notes": notes.strip(), "created_at_utc": now_iso(),
            }
            save_list(UGC_KEY, [*rows, row]); st.rerun()
    if rows:
        cols = st.columns(3)
        cols[0].metric("Piezas UGC", len(rows))
        cols[1].metric("Publicadas/reutilizadas", sum(x.get("status") in {"Publicado", "Reutilizado"} for x in rows))
        cols[2].metric("Permiso documentado", sum(bool(x.get("permission")) for x in rows))
        for row in reversed(rows[-8:]):
            with st.container(border=True):
                st.write(f"**{row.get('concept')}** · {row.get('product','')} · {row.get('status')}")
                st.caption(f"{row.get('creator_type')} · {row.get('creator','')} · Permiso: {'Sí' if row.get('permission') else 'Pendiente'}")


def _render_hooks_copy() -> None:
    st.subheader("Hooks, copywriting y storytelling")
    st.caption("El hook parte del problema; después el mensaje guía a la persona hacia una acción.")
    rows = read_list(HOOK_LIBRARY_KEY)
    with st.form("mkt_hook_copy", clear_on_submit=True):
        cols = st.columns(2)
        hook_type = cols[0].selectbox("Tipo de gancho", HOOK_TYPES)
        framework = cols[1].selectbox("Estructura de copy", COPY_FRAMEWORKS)
        problem = st.text_area("Problema / necesidad real")
        hook = st.text_input("Gancho", placeholder="Primera idea que hace que la persona se detenga")
        message = st.text_area("Desarrollo del mensaje")
        cta = st.text_input("CTA")
        if st.form_submit_button("Guardar fórmula", type="primary", use_container_width=True) and hook.strip():
            row = {
                "hook_type": hook_type, "framework": framework, "problem": problem.strip(), "hook": hook.strip(),
                "message": message.strip(), "cta": cta.strip(), "created_at_utc": now_iso(),
            }
            save_list(HOOK_LIBRARY_KEY, [*rows, row]); st.rerun()
    framework = st.selectbox("Ver estructura rápida", COPY_FRAMEWORKS, key="mkt_copy_structure")
    st.info(" → ".join(copy_framework_template(framework)))
    for row in reversed(rows[-8:]):
        with st.expander(f"{row.get('hook_type')} · {row.get('hook')}"):
            st.write(row.get("message", "")); st.caption(f"{row.get('framework')} · CTA: {row.get('cta','')}")


def _render_video_planner() -> None:
    st.subheader("Planificador de videomarketing")
    st.caption("Un video efectivo necesita intención, narrativa, estructura, retención y ejecución visual.")
    rows = read_list(VIDEO_PLAN_KEY)
    with st.form("mkt_video_plan", clear_on_submit=True):
        title = st.text_input("Idea / título del video")
        cols = st.columns(4)
        platform = cols[0].text_input("Plataforma", placeholder="Instagram, TikTok...")
        ratio = cols[1].selectbox("Formato", VIDEO_RATIOS)
        objective = cols[2].selectbox("Objetivo", CONTENT_OBJECTIVES)
        content_type = cols[3].selectbox("Tipo", CONTENT_TYPES)
        hook = st.text_input("Gancho")
        cols = st.columns(2)
        intention = cols[0].text_area("Intención y narrativa")
        structure = cols[1].text_area("Estructura / guion / retención")
        cols = st.columns(2)
        shot = cols[0].selectbox("Plano principal", VIDEO_SHOTS)
        movement = cols[1].selectbox("Movimiento principal", VIDEO_MOVEMENTS)
        production = st.multiselect("Checklist técnico", ("Audio", "Iluminación", "Encuadre", "Estabilidad", "Composición", "Ritmo visual"))
        notes = st.text_area("Notas de edición / CTA / producción")
        if st.form_submit_button("Guardar plan de video", type="primary", use_container_width=True) and title.strip():
            row = {
                "title": title.strip(), "platform": platform.strip(), "ratio": ratio, "objective": objective,
                "content_type": content_type, "hook": hook.strip(), "intention": intention.strip(), "structure": structure.strip(),
                "shot": shot, "movement": movement, "production": production, "notes": notes.strip(), "created_at_utc": now_iso(),
            }
            save_list(VIDEO_PLAN_KEY, [*rows, row]); st.rerun()
    for row in reversed(rows[-8:]):
        with st.container(border=True):
            st.write(f"**{row.get('title')}** · {row.get('platform')} · {row.get('ratio')}")
            st.caption(f"{row.get('objective')} · {row.get('shot')} · {row.get('movement')} · Hook: {row.get('hook','')}")


def render_marketing() -> None:
    base.render_marketing()
    st.divider()
    st.markdown("## Marketing estratégico · Sistema de contenidos")
    st.caption("Del contexto de marca a la ejecución: brief, estrategia, mercado, conversación, copy y video.")
    tabs = st.tabs(("Briefing", "Estrategia", "Benchmark", "Marca", "Listening", "UGC", "Hooks & Copy", "Video"))
    renderers = (
        _render_briefing, _render_strategy_table, _render_benchmarking, _render_brand_personality,
        _render_social_listening, _render_ugc, _render_hooks_copy, _render_video_planner,
    )
    for tab, renderer in zip(tabs, renderers):
        with tab:
            renderer()
