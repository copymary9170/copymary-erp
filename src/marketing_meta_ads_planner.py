"""Planificador práctico de Meta Ads para Marketing.

Convierte la configuración enseñada en Ads Manager en una ficha reutilizable
antes de publicar: objetivo, presupuesto, público, formato y control de calidad.
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import streamlit as st

from src.session_utils import now_iso, read_list, save_list

PLANS_KEY = "marketing_meta_ads_plans"
OBJECTIVES = (
    "Reconocimiento",
    "Tráfico",
    "Interacción",
    "Clientes potenciales",
    "Promoción de la app",
    "Ventas",
)
BUY_TYPES = ("Subasta",)
BUDGET_TYPES = ("Diario", "Total")
BID_STRATEGIES = ("Volumen más alto", "Costo por resultado", "ROAS objetivo", "Manual / otra")
AUDIENCE_WIDTHS = ("Amplio", "Intermedio", "Acotado")
AD_FORMATS = ("Una imagen o video", "Secuencia / carrusel", "Colección", "Anuncio existente")
SPECIAL_CATEGORIES = ("Ninguna", "Crédito", "Empleo", "Vivienda", "Temas sociales, elecciones o política")

OBJECTIVE_GUIDE = {
    "Reconocimiento": "Úsalo cuando la prioridad sea alcance, recuerdo de marca o reproducciones de video.",
    "Tráfico": "Úsalo para llevar personas a un sitio, perfil, WhatsApp, Messenger, llamada u otro destino.",
    "Interacción": "Úsalo cuando la meta principal sea conseguir mensajes, reproducciones, reacciones o interacción.",
    "Clientes potenciales": "Úsalo cuando quieras captar datos o consultas de personas interesadas.",
    "Promoción de la app": "Úsalo para instalaciones o acciones dentro de una aplicación.",
    "Ventas": "Úsalo cuando puedas medir compras, conversiones o ventas atribuibles a la campaña.",
}

FUNNEL_OBJECTIVE = {
    "Reconocimiento": "Reconocimiento",
    "Necesidad": "Interacción",
    "Solución": "Tráfico",
    "Demostración": "Interacción",
    "Confianza": "Interacción",
    "CTA": "Clientes potenciales",
    "Lead": "Clientes potenciales",
    "Cliente": "Ventas",
}


def recommended_objective(funnel_stage: str) -> str:
    """Sugiere el objetivo de Meta más coherente con la etapa del embudo."""
    return FUNNEL_OBJECTIVE.get(str(funnel_stage or "").strip(), "Interacción")


def estimated_budget(budget_type: str, amount: float, days: int) -> float:
    """Calcula inversión prevista sin asumir gasto real de Meta."""
    value = max(float(amount or 0), 0.0)
    safe_days = max(int(days or 0), 1)
    return value * safe_days if budget_type == "Diario" else value


def preflight_score(plan: dict) -> tuple[int, list[str]]:
    """Puntúa la preparación de una campaña antes de llevarla a Ads Manager."""
    checks = [
        (bool(str(plan.get("name", "")).strip()), "Define un nombre de campaña."),
        (plan.get("objective") in OBJECTIVES, "Selecciona un objetivo válido."),
        (float(plan.get("budget", 0) or 0) > 0, "Asigna un presupuesto mayor que cero."),
        (bool(str(plan.get("location_include", "")).strip()), "Define al menos una ubicación incluida."),
        (bool(str(plan.get("audience", "")).strip()), "Describe el público o la lógica de segmentación."),
        (bool(str(plan.get("creative", "")).strip()), "Define la pieza creativa que vas a usar."),
        (bool(str(plan.get("copy", "")).strip()), "Escribe el texto principal del anuncio."),
        (bool(str(plan.get("cta", "")).strip()), "Define el llamado a la acción."),
        (bool(str(plan.get("destination", "")).strip()), "Indica el destino de la campaña."),
        (bool(str(plan.get("success_metric", "")).strip()), "Define la métrica que determinará si funcionó."),
    ]
    failures = [message for ok, message in checks if not ok]
    score = round((len(checks) - len(failures)) / len(checks) * 100)
    return score, failures


def plan_diagnostics(plan: dict) -> list[str]:
    """Genera alertas de configuración comunes antes de publicar."""
    messages: list[str] = []
    objective = plan.get("objective")
    audience_width = plan.get("audience_width")
    if objective == "Ventas" and not str(plan.get("tracking", "")).strip():
        messages.append("Para una campaña de Ventas conviene definir cómo se atribuirá o medirá la conversión.")
    if objective in ("Clientes potenciales", "Ventas") and not str(plan.get("offer", "")).strip():
        messages.append("La campaña busca conversión pero todavía no tiene una oferta claramente definida.")
    if audience_width == "Acotado" and not str(plan.get("audience_reason", "")).strip():
        messages.append("El público está acotado; documenta por qué necesitas limitarlo para evitar segmentar por intuición.")
    if plan.get("ab_test") and not str(plan.get("ab_variable", "")).strip():
        messages.append("Activaste una prueba A/B pero no indicaste qué única variable vas a comparar.")
    if plan.get("special_category") not in (None, "", "Ninguna"):
        messages.append("Marcaste una categoría especial: revisa las restricciones de segmentación aplicables antes de publicar.")
    return messages


def _plan_form() -> None:
    rows = read_list(PLANS_KEY)
    st.subheader("Planificador Meta Ads")
    st.caption("Prepara la campaña en el ERP antes de tocar Ads Manager. El ERP no publica anuncios: organiza la decisión y reduce errores.")
    with st.form("meta_ads_plan", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nombre de campaña")
        objective = c2.selectbox("Objetivo Meta", OBJECTIVES)
        buy_type = c3.selectbox("Tipo de compra", BUY_TYPES)
        st.info(OBJECTIVE_GUIDE[objective])

        c1, c2, c3, c4 = st.columns(4)
        budget_type = c1.selectbox("Tipo de presupuesto", BUDGET_TYPES)
        budget = c2.number_input("Presupuesto USD", min_value=0.0, step=1.0)
        days = c3.number_input("Días previstos", min_value=1, value=7, step=1)
        advantage_budget = c4.checkbox("Presupuesto Advantage+", value=True)
        st.caption(f"Inversión prevista: ${estimated_budget(budget_type, budget, int(days)):,.2f}")

        c1, c2, c3 = st.columns(3)
        bid = c1.selectbox("Estrategia de puja", BID_STRATEGIES)
        ab_test = c2.checkbox("Prueba A/B")
        special = c3.selectbox("Categoría especial", SPECIAL_CATEGORIES)
        ab_variable = st.text_input("Variable de la prueba A/B", placeholder="Ej. creativo, copy o audiencia; cambia una sola variable") if ab_test else ""

        st.markdown("#### Conjunto de anuncios / público")
        c1, c2 = st.columns(2)
        location_include = c1.text_input("Ubicaciones incluidas", placeholder="Ej. Caracas, Venezuela")
        location_exclude = c2.text_input("Ubicaciones excluidas", placeholder="Opcional")
        c1, c2 = st.columns(2)
        audience_width = c1.selectbox("Amplitud del público", AUDIENCE_WIDTHS)
        audience = c2.text_input("Público / criterio", placeholder="Ej. público amplio local; clientes similares; intereses...")
        audience_reason = st.text_area("Razón de la segmentación", placeholder="Qué evidencia o aprendizaje justifica esta selección")

        st.markdown("#### Anuncio")
        c1, c2 = st.columns(2)
        ad_format = c1.selectbox("Formato", AD_FORMATS)
        destination = c2.text_input("Destino", placeholder="WhatsApp, Instagram, web, formulario, tienda...")
        creative = st.text_input("Creativo / pieza", placeholder="Nombre o enlace de la imagen, video o carrusel")
        copy = st.text_area("Texto principal")
        c1, c2 = st.columns(2)
        headline = c1.text_input("Título / headline")
        cta = c2.text_input("CTA", placeholder="Enviar mensaje, Comprar, Más información...")

        st.markdown("#### Resultado esperado")
        c1, c2 = st.columns(2)
        offer = c1.text_area("Oferta", placeholder="Qué obtiene el cliente y por qué debería actuar ahora")
        success_metric = c2.text_area("Métrica de éxito", placeholder="Ej. costo por conversación <= $X; 20 leads; ROAS >= 2")
        tracking = st.text_input("Medición / atribución", placeholder="Pixel, mensajes recibidos, CRM, ventas registradas, UTM...")
        notes = st.text_area("Notas")

        submitted = st.form_submit_button("Guardar plan de Meta Ads", type="primary", use_container_width=True)
    if submitted:
        row = {
            "plan_id": f"META-{uuid4().hex[:8].upper()}", "name": name.strip(), "objective": objective,
            "buy_type": buy_type, "budget_type": budget_type, "budget": float(budget), "days": int(days),
            "estimated_spend": estimated_budget(budget_type, budget, int(days)), "advantage_budget": advantage_budget,
            "bid_strategy": bid, "ab_test": ab_test, "ab_variable": ab_variable.strip(), "special_category": special,
            "location_include": location_include.strip(), "location_exclude": location_exclude.strip(),
            "audience_width": audience_width, "audience": audience.strip(), "audience_reason": audience_reason.strip(),
            "ad_format": ad_format, "destination": destination.strip(), "creative": creative.strip(), "copy": copy.strip(),
            "headline": headline.strip(), "cta": cta.strip(), "offer": offer.strip(), "success_metric": success_metric.strip(),
            "tracking": tracking.strip(), "notes": notes.strip(), "created_at_utc": now_iso(), "status": "Planificada",
        }
        save_list(PLANS_KEY, [*rows, row])
        st.rerun()


def _saved_plans() -> None:
    rows = read_list(PLANS_KEY)
    st.subheader("Auditor de campañas")
    if not rows:
        st.info("Todavía no hay planes de Meta Ads guardados.")
        return
    choices = [f"{row.get('name','Sin nombre')} · {row.get('objective','')}" for row in rows]
    selected = st.selectbox("Plan a revisar", choices)
    plan = rows[choices.index(selected)]
    score, failures = preflight_score(plan)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Preflight", f"{score}%")
    c2.metric("Objetivo", str(plan.get("objective", "—")))
    c3.metric("Presupuesto", f"${float(plan.get('estimated_spend', 0) or 0):,.2f}")
    c4.metric("Público", str(plan.get("audience_width", "—")))
    st.progress(score / 100)
    if failures:
        for message in failures:
            st.warning(message)
    else:
        st.success("La ficha está completa para llevar la configuración a Ads Manager.")
    for message in plan_diagnostics(plan):
        st.info(message)
    st.markdown("#### Resumen para configurar en Meta")
    st.write({
        "Campaña": plan.get("name"), "Objetivo": plan.get("objective"), "Compra": plan.get("buy_type"),
        "Presupuesto": f"{plan.get('budget_type')} ${float(plan.get('budget',0) or 0):,.2f}",
        "Advantage+ presupuesto": "Sí" if plan.get("advantage_budget") else "No",
        "Puja": plan.get("bid_strategy"), "Ubicación": plan.get("location_include"),
        "Excluir": plan.get("location_exclude") or "—", "Público": plan.get("audience"),
        "Formato": plan.get("ad_format"), "Destino": plan.get("destination"), "CTA": plan.get("cta"),
        "Métrica de éxito": plan.get("success_metric"),
    })


def render_meta_ads_planner() -> None:
    """Renderiza planificación, auditoría y guía de objetivos de Meta Ads."""
    st.markdown("## Meta Ads")
    st.caption("De la estrategia a una configuración lista para replicar en el Administrador de anuncios.")
    tab1, tab2, tab3 = st.tabs(("Planificar", "Auditar", "Guía de objetivos"))
    with tab1:
        _plan_form()
    with tab2:
        _saved_plans()
    with tab3:
        for objective in OBJECTIVES:
            with st.container(border=True):
                st.write(f"**{objective}**")
                st.caption(OBJECTIVE_GUIDE[objective])
        st.markdown("#### Puente desde el embudo")
        for stage, objective in FUNNEL_OBJECTIVE.items():
            st.write(f"**{stage}** → {objective}")
