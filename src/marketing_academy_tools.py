"""Herramientas avanzadas de Marketing basadas en los materiales del diplomado.

Extiende el centro existente sin duplicar estrategia, campañas, contenido, embudo
ni el laboratorio de IA. Añade Email Marketing, preparación de Meta Ads, QA
creativo y un cotizador orientativo de servicios de Community Management.
"""
from __future__ import annotations

from functools import reduce
from operator import mul

import streamlit as st

from src import marketing_ai_workbench as base
from src.session_utils import now_iso, read_list, save_list

EMAIL_KEY = "marketing_email_campaigns"
META_KEY = "marketing_meta_readiness"
CREATIVE_QA_KEY = "marketing_creative_qa"

EMAIL_TYPES = ("Newsletter", "Promocional", "Estacional", "Informativa")
EMAIL_STAGES = ("Captar", "Diseñar", "Enviar", "Medir", "Optimizar")

META_CHECKS = (
    ("facebook_page", "Página de Facebook empresarial completa"),
    ("instagram_connected", "Instagram conectado"),
    ("whatsapp_connected", "WhatsApp Business integrado"),
    ("business_portfolio", "Portafolio Comercial configurado"),
    ("ad_account", "Cuenta publicitaria profesional activa"),
    ("payment_method", "Método de pago validado"),
    ("backup_payment", "Método de pago de respaldo"),
    ("base_content", "Presencia base publicada antes de pautar"),
)

CREATIVE_CHECKS = (
    ("balance_contrast", "Equilibrio y contraste dirigen la atención"),
    ("negative_space", "Hay espacio negativo suficiente para respirar"),
    ("visual_hierarchy", "La jerarquía visual se entiende rápido"),
    ("brand_consistency", "Colores, tipografías y tono respetan la marca"),
    ("real_copy", "El copy es real y no usa contenido de relleno"),
    ("clear_value", "La propuesta de valor es clara"),
    ("clear_cta", "El CTA indica exactamente qué hacer"),
    ("mobile_first", "La pieza fue revisada en móvil"),
    ("claims_verified", "Cifras, testimonios y promesas están verificadas"),
    ("accessibility", "Contraste y legibilidad son adecuados"),
)

CM_RATES = {
    "Gestión mensual · 1 marca / 1 red": {
        "Principiante": (180.0, 350.0), "Intermedio": (350.0, 700.0), "Senior": (700.0, 1500.0),
    },
    "Gestión mensual · 2–3 redes": {
        "Principiante": (260.0, 480.0), "Intermedio": (520.0, 980.0), "Senior": (1000.0, 2200.0),
    },
    "Calendario de contenido mensual": {
        "Principiante": (40.0, 90.0), "Intermedio": (90.0, 180.0), "Senior": (180.0, 350.0),
    },
    "Diseño Post/Carrusel": {
        "Principiante": (10.0, 25.0), "Intermedio": (25.0, 45.0), "Senior": (45.0, 90.0),
    },
    "Paquete Stories · 5 unidades": {
        "Principiante": (20.0, 45.0), "Intermedio": (45.0, 90.0), "Senior": (90.0, 180.0),
    },
    "Moderación adicional · hora": {
        "Principiante": (6.0, 10.0), "Intermedio": (10.0, 18.0), "Senior": (18.0, 35.0),
    },
    "Reporte mensual": {
        "Principiante": (20.0, 40.0), "Intermedio": (40.0, 80.0), "Senior": (80.0, 160.0),
    },
    "Crisis Management · hora": {
        "Principiante": (20.0, 35.0), "Intermedio": (35.0, 60.0), "Senior": (60.0, 120.0),
    },
}

CM_ADJUSTMENTS = {
    "Industria regulada": (0.15, 0.35),
    "Volumen alto de publicaciones": (0.10, 0.40),
    "Red/cuenta adicional": (0.10, 0.25),
    "Bilingüe": (0.10, 0.20),
    "Ads avanzada": (0.10, 0.30),
    "Entrega urgente": (0.10, 0.30),
    "Entrega de editables/fuentes": (0.10, 0.25),
    "Exclusividad por categoría": (0.15, 0.40),
    "Coordinación presencial / plaza": (0.05, 0.15),
}

ADS_RATES = {
    "Principiante": (0.10, 0.15, 50.0),
    "Intermedio": (0.12, 0.18, 100.0),
    "Senior": (0.15, 0.20, 200.0),
}


def email_kpis(delivered: int, opened: int, clicks: int, conversions: int) -> dict[str, float]:
    """Calcula tasas operativas de una campaña de email."""
    delivered = max(int(delivered or 0), 0)
    opened = max(int(opened or 0), 0)
    clicks = max(int(clicks or 0), 0)
    conversions = max(int(conversions or 0), 0)
    return {
        "open_rate": opened / delivered * 100 if delivered else 0.0,
        "ctr": clicks / delivered * 100 if delivered else 0.0,
        "ctor": clicks / opened * 100 if opened else 0.0,
        "conversion_rate": conversions / delivered * 100 if delivered else 0.0,
    }


def readiness_score(values: dict[str, bool], checklist=META_CHECKS) -> float:
    """Devuelve porcentaje de preparación para una lista de control."""
    keys = [key for key, _label in checklist]
    if not keys:
        return 0.0
    completed = sum(bool(values.get(key)) for key in keys)
    return completed / len(keys) * 100


def community_quote_range(service: str, level: str, adjustments: list[str] | tuple[str, ...] = ()) -> tuple[float, float]:
    """Aplica rangos acumulativos del talonario a una tarifa base."""
    low, high = CM_RATES[service][level]
    selected = [CM_ADJUSTMENTS[item] for item in adjustments if item in CM_ADJUSTMENTS]
    low_factor = reduce(mul, (1 + item[0] for item in selected), 1.0)
    high_factor = reduce(mul, (1 + item[1] for item in selected), 1.0)
    return low * low_factor, high * high_factor


def ads_management_quote(ad_spend: float, level: str) -> tuple[float, float]:
    """Calcula el rango orientativo para gestión de Meta Ads."""
    low_pct, high_pct, minimum = ADS_RATES[level]
    spend = max(float(ad_spend or 0), 0.0)
    return max(minimum, spend * low_pct), max(minimum, spend * high_pct)


def _render_email_marketing() -> None:
    st.subheader("Email Marketing")
    st.caption("Flujo operativo: Captar → Diseñar → Enviar → Medir → Optimizar.")
    rows = read_list(EMAIL_KEY)
    with st.form("mkt_email_campaign", clear_on_submit=True):
        cols = st.columns(3)
        name = cols[0].text_input("Nombre de campaña")
        campaign_type = cols[1].selectbox("Tipo", EMAIL_TYPES)
        stage = cols[2].selectbox("Etapa", EMAIL_STAGES)
        objective = st.text_input("Objetivo", placeholder="Fidelizar, generar tráfico, conversiones, comunicar novedades...")
        cols = st.columns(2)
        segment = cols[0].text_input("Lista / segmento")
        subject = cols[1].text_input("Asunto")
        preheader = st.text_input("Preencabezado", placeholder="Completa el asunto y aporta contexto sin repetirlo")
        value = st.text_area("Propuesta de valor / mensaje central")
        cta = st.text_input("CTA", placeholder="Imperativo claro: Compra, Reserva, Descubre, Escríbenos...")
        cols = st.columns(4)
        delivered = cols[0].number_input("Entregados", min_value=0, step=1)
        opened = cols[1].number_input("Abiertos", min_value=0, step=1)
        clicks = cols[2].number_input("Clics", min_value=0, step=1)
        conversions = cols[3].number_input("Conversiones", min_value=0, step=1)
        submitted = st.form_submit_button("Guardar campaña de email", type="primary", use_container_width=True)
    if submitted and name.strip():
        kpis = email_kpis(delivered, opened, clicks, conversions)
        row = {
            "name": name.strip(), "campaign_type": campaign_type, "stage": stage,
            "objective": objective.strip(), "segment": segment.strip(), "subject": subject.strip(),
            "preheader": preheader.strip(), "value": value.strip(), "cta": cta.strip(),
            "delivered": int(delivered), "opened": int(opened), "clicks": int(clicks),
            "conversions": int(conversions), **kpis, "created_at_utc": now_iso(),
        }
        save_list(EMAIL_KEY, [*rows, row])
        st.success("Campaña de email guardada.")
        st.rerun()

    if rows:
        latest = rows[-1]
        cols = st.columns(4)
        cols[0].metric("Apertura", f"{float(latest.get('open_rate', 0)):.2f}%")
        cols[1].metric("CTR", f"{float(latest.get('ctr', 0)):.2f}%")
        cols[2].metric("CTOR", f"{float(latest.get('ctor', 0)):.2f}%")
        cols[3].metric("Conversión", f"{float(latest.get('conversion_rate', 0)):.2f}%")
        for row in reversed(rows[-8:]):
            with st.container(border=True):
                st.write(f"**{row.get('name', 'Campaña')}** · {row.get('campaign_type', '')} · {row.get('stage', '')}")
                st.caption(f"Segmento: {row.get('segment', 'Sin definir')} · Asunto: {row.get('subject', '')}")
    else:
        st.info("Todavía no hay campañas de email registradas.")

    st.markdown("**QA antes de enviar:** asunto + preencabezado coherentes, contenido responsive, propuesta clara, CTA visible y enlace de remoción disponible.")


def _render_meta_readiness() -> None:
    st.subheader("Preparación para Meta Ads")
    st.caption("Verifica el ecosistema antes de invertir presupuesto.")
    saved = (read_list(META_KEY) or [{}])[-1]
    values: dict[str, bool] = {}
    for key, label in META_CHECKS:
        values[key] = st.checkbox(label, value=bool(saved.get(key, False)), key=f"meta_ready_{key}")
    score = readiness_score(values)
    st.progress(score / 100)
    st.metric("Preparación", f"{score:.0f}%")
    if score < 75:
        st.warning("Conviene completar la configuración antes de aumentar inversión publicitaria.")
    elif score < 100:
        st.info("La base está casi lista. Revisa especialmente pagos y activos conectados.")
    else:
        st.success("Ecosistema publicitario completo según este checklist.")
    if st.button("Guardar checklist Meta", use_container_width=True):
        save_list(META_KEY, [{**values, "updated_at_utc": now_iso()}])
        st.success("Checklist guardado.")


def _render_creative_qa() -> None:
    st.subheader("Control de calidad creativo")
    st.caption("Revisa la pieza con criterio de diseño y conversión antes de aprobarla.")
    saved = (read_list(CREATIVE_QA_KEY) or [{}])[-1]
    values: dict[str, bool] = {}
    for key, label in CREATIVE_CHECKS:
        values[key] = st.checkbox(label, value=bool(saved.get(key, False)), key=f"creative_qa_{key}")
    score = readiness_score(values, CREATIVE_CHECKS)
    st.progress(score / 100)
    st.metric("QA creativo", f"{score:.0f}%")
    if score < 80:
        st.warning("La pieza todavía tiene puntos críticos por revisar antes de publicar.")
    else:
        st.success("La pieza supera el umbral de revisión creativa configurado.")
    if st.button("Guardar QA creativo", use_container_width=True):
        save_list(CREATIVE_QA_KEY, [{**values, "updated_at_utc": now_iso()}])
        st.success("QA guardado.")


def _render_pricing() -> None:
    st.subheader("Cotizador de Community Manager")
    st.caption("Referencia orientativa basada en el talonario aportado. Ajusta el precio final a alcance, mercado y responsabilidad real.")
    cols = st.columns(2)
    level = cols[0].selectbox("Nivel", ("Principiante", "Intermedio", "Senior"))
    mode = cols[1].radio("Tipo de servicio", ("Servicios", "Gestión de Ads"), horizontal=True)
    if mode == "Gestión de Ads":
        spend = st.number_input("Inversión publicitaria del cliente (USD)", min_value=0.0, step=10.0)
        low, high = ads_management_quote(spend, level)
        st.metric("Rango orientativo de gestión", f"${low:,.2f} – ${high:,.2f}")
        st.caption("El cálculo respeta el porcentaje por nivel y el mínimo indicado en el talonario.")
        return

    service = st.selectbox("Servicio", tuple(CM_RATES.keys()))
    adjustments = st.multiselect("Ajustadores aplicables", tuple(CM_ADJUSTMENTS.keys()))
    low, high = community_quote_range(service, level, adjustments)
    st.metric("Rango orientativo", f"${low:,.2f} – ${high:,.2f}")
    base_low, base_high = CM_RATES[service][level]
    st.caption(f"Base: ${base_low:,.2f} – ${base_high:,.2f}. Los extras se aplican como rangos acumulativos, no como un precio obligatorio.")


def render_marketing() -> None:
    base.render_marketing()
    st.divider()
    st.markdown("## Marketing operativo · Academia")
    st.caption("Herramientas añadidas desde los materiales aportados: email, pauta, control creativo y cotización.")
    email_tab, meta_tab, qa_tab, pricing_tab = st.tabs(("Email Marketing", "Meta Ads", "QA creativo", "Cotizador CM"))
    with email_tab:
        _render_email_marketing()
    with meta_tab:
        _render_meta_readiness()
    with qa_tab:
        _render_creative_qa()
    with pricing_tab:
        _render_pricing()
