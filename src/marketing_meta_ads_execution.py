"""Matriz operativa Campaña → Conjuntos → Anuncios para Meta Ads.

Complementa el planificador previo con la jerarquía práctica observada en Ads Manager:
una campaña puede probar varios conjuntos de anuncios y cada conjunto varios creativos.
"""
from __future__ import annotations

from uuid import uuid4
import streamlit as st

from src.session_utils import now_iso, read_list, save_list
from src.marketing_meta_ads_planner import PLANS_KEY

ADSETS_KEY = "marketing_meta_ads_adsets"
ADS_KEY = "marketing_meta_ads_ads"

PLACEMENTS = ("Advantage+", "Instagram Feed", "Instagram Reels", "Instagram Stories", "Facebook Feed", "Messenger", "Manual / mixto")
OPTIMIZATIONS = ("Alcance", "Impresiones", "Clics", "Visitas al perfil", "Conversaciones", "Leads", "Conversiones / ventas")
CREATIVE_TYPES = ("Reel / video", "Imagen", "Carrusel", "Historia", "Publicación existente", "Otro")


def campaign_structure(plan_id: str, adsets: list[dict], ads: list[dict]) -> dict[str, int]:
    linked_sets = [row for row in adsets if row.get("plan_id") == plan_id]
    set_ids = {row.get("adset_id") for row in linked_sets}
    linked_ads = [row for row in ads if row.get("adset_id") in set_ids]
    return {"adsets": len(linked_sets), "ads": len(linked_ads)}


def structure_diagnostics(plan_id: str, adsets: list[dict], ads: list[dict]) -> list[str]:
    linked_sets = [row for row in adsets if row.get("plan_id") == plan_id]
    set_ids = {row.get("adset_id") for row in linked_sets}
    linked_ads = [row for row in ads if row.get("adset_id") in set_ids]
    messages: list[str] = []
    if len(linked_sets) < 2:
        messages.append("Hay menos de 2 conjuntos de anuncios; tendrás poca capacidad para comparar públicos.")
    for adset in linked_sets:
        count = sum(ad.get("adset_id") == adset.get("adset_id") for ad in linked_ads)
        if count < 2:
            messages.append(f"El conjunto '{adset.get('name','Sin nombre')}' tiene menos de 2 creativos para comparar.")
    if linked_sets:
        budgets = [float(row.get("budget", 0) or 0) for row in linked_sets]
        if any(value <= 0 for value in budgets):
            messages.append("Hay conjuntos sin presupuesto asignado.")
    return messages or ["La campaña tiene una estructura mínima útil para comparar públicos y creativos."]


def winner_score(row: dict) -> float:
    """Score simple para ordenar anuncios cuando se registran resultados comparables."""
    ctr = float(row.get("ctr", 0) or 0)
    leads = float(row.get("leads", 0) or 0)
    sales = float(row.get("sales", 0) or 0)
    cpc = float(row.get("cpc", 0) or 0)
    efficiency = 1 / cpc if cpc > 0 else 0
    return ctr * 2 + leads * 3 + sales * 8 + efficiency


def _plan_options() -> tuple[list[dict], dict[str, str]]:
    plans = read_list(PLANS_KEY)
    labels = {f"{row.get('name','Sin nombre')} · {row.get('objective','')}": str(row.get('plan_id','')) for row in plans}
    return plans, labels


def _adset_builder() -> None:
    plans, labels = _plan_options()
    st.subheader("Conjuntos de anuncios")
    if not labels:
        st.info("Primero crea una campaña en Meta Ads → Planificador.")
        return
    rows = read_list(ADSETS_KEY)
    with st.form("meta_execution_adset", clear_on_submit=True):
        plan_label = st.selectbox("Campaña", tuple(labels))
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nombre del conjunto", placeholder="P1 | Público amplio Caracas")
        budget = c2.number_input("Presupuesto diario USD", min_value=0.0, step=1.0)
        placement = c3.selectbox("Ubicaciones", PLACEMENTS)
        c1, c2, c3 = st.columns(3)
        age = c1.text_input("Edades", placeholder="18–45")
        location = c2.text_input("Ubicación", placeholder="Caracas, Venezuela")
        optimization = c3.selectbox("Optimización", OPTIMIZATIONS)
        audience = st.text_area("Audiencia / intereses / criterio", placeholder="Público amplio, intereses, lookalike, remarketing...")
        exclusions = st.text_input("Exclusiones", placeholder="Opcional")
        hypothesis = st.text_area("Hipótesis del conjunto", placeholder="Qué quieres comprobar con este público")
        if st.form_submit_button("Agregar conjunto", type="primary", use_container_width=True) and name.strip():
            save_list(ADSETS_KEY, [*rows, {
                "adset_id": f"ADSET-{uuid4().hex[:8].upper()}", "plan_id": labels[plan_label], "name": name.strip(),
                "budget": float(budget), "placement": placement, "age": age.strip(), "location": location.strip(),
                "optimization": optimization, "audience": audience.strip(), "exclusions": exclusions.strip(),
                "hypothesis": hypothesis.strip(), "created_at_utc": now_iso(),
            }]); st.rerun()
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _ad_builder() -> None:
    adsets = read_list(ADSETS_KEY)
    st.subheader("Anuncios / creativos")
    if not adsets:
        st.info("Primero agrega al menos un conjunto de anuncios.")
        return
    labels = {str(row.get("name", row.get("adset_id"))): str(row.get("adset_id", "")) for row in adsets}
    rows = read_list(ADS_KEY)
    with st.form("meta_execution_ad", clear_on_submit=True):
        adset_label = st.selectbox("Conjunto", tuple(labels))
        c1, c2 = st.columns(2)
        name = c1.text_input("Nombre del anuncio", placeholder="A1 | Reel | Beneficio")
        creative_type = c2.selectbox("Tipo de creativo", CREATIVE_TYPES)
        hook = st.text_input("Hook / apertura")
        creative = st.text_input("Archivo / enlace del creativo")
        copy = st.text_area("Copy")
        c1, c2 = st.columns(2)
        headline = c1.text_input("Título")
        cta = c2.text_input("CTA")
        variable = st.text_input("Variable que prueba", placeholder="Ej. hook, formato, oferta, miniatura")
        if st.form_submit_button("Agregar anuncio", type="primary", use_container_width=True) and name.strip():
            save_list(ADS_KEY, [*rows, {
                "ad_id": f"AD-{uuid4().hex[:8].upper()}", "adset_id": labels[adset_label], "name": name.strip(),
                "creative_type": creative_type, "hook": hook.strip(), "creative": creative.strip(), "copy": copy.strip(),
                "headline": headline.strip(), "cta": cta.strip(), "test_variable": variable.strip(), "status": "Planificado",
                "created_at_utc": now_iso(),
            }]); st.rerun()
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _results() -> None:
    ads = read_list(ADS_KEY)
    st.subheader("Resultados y ganador")
    if not ads:
        st.info("Todavía no hay anuncios registrados.")
        return
    labels = [f"{i+1}. {row.get('name','Sin nombre')}" for i, row in enumerate(ads)]
    chosen = st.selectbox("Anuncio a medir", labels)
    idx = labels.index(chosen)
    c1, c2, c3, c4 = st.columns(4)
    impressions = c1.number_input("Impresiones", min_value=0, step=1)
    clicks = c2.number_input("Clics", min_value=0, step=1)
    leads = c3.number_input("Leads", min_value=0, step=1)
    sales = c4.number_input("Ventas", min_value=0, step=1)
    c1, c2 = st.columns(2)
    spend = c1.number_input("Gasto USD", min_value=0.0, step=1.0)
    revenue = c2.number_input("Ingresos USD", min_value=0.0, step=1.0)
    if st.button("Guardar resultado", type="primary", use_container_width=True):
        updated = [dict(row) for row in ads]
        ctr = clicks / impressions * 100 if impressions else 0.0
        cpc = spend / clicks if clicks else 0.0
        cpl = spend / leads if leads else 0.0
        roas = revenue / spend if spend else 0.0
        updated[idx].update({"impressions": int(impressions), "clicks": int(clicks), "leads": int(leads), "sales": int(sales),
                             "spend": float(spend), "revenue": float(revenue), "ctr": ctr, "cpc": cpc, "cpl": cpl,
                             "roas": roas, "status": "Medido", "measured_at_utc": now_iso()})
        save_list(ADS_KEY, updated); st.rerun()
    measured = [row for row in ads if row.get("status") == "Medido"]
    if measured:
        ranked = sorted(measured, key=winner_score, reverse=True)
        st.markdown("#### Ranking orientativo")
        for pos, row in enumerate(ranked, 1):
            st.write(f"**{pos}. {row.get('name')}** · CTR {float(row.get('ctr',0) or 0):.2f}% · CPC ${float(row.get('cpc',0) or 0):.2f} · Leads {int(row.get('leads',0) or 0)} · Ventas {int(row.get('sales',0) or 0)} · ROAS {float(row.get('roas',0) or 0):.2f}x")


def _architecture() -> None:
    plans = read_list(PLANS_KEY); adsets = read_list(ADSETS_KEY); ads = read_list(ADS_KEY)
    st.subheader("Arquitectura de campañas")
    if not plans:
        st.info("No hay campañas planificadas.")
        return
    for plan in reversed(plans):
        plan_id = str(plan.get("plan_id", "")); counts = campaign_structure(plan_id, adsets, ads)
        with st.expander(f"{plan.get('name','Sin nombre')} · {counts['adsets']} conjuntos · {counts['ads']} anuncios"):
            linked_sets = [row for row in adsets if row.get("plan_id") == plan_id]
            for adset in linked_sets:
                linked_ads = [row for row in ads if row.get("adset_id") == adset.get("adset_id")]
                st.write(f"**{adset.get('name')}** · ${float(adset.get('budget',0) or 0):.2f}/día · {adset.get('optimization','')}")
                for ad in linked_ads:
                    st.caption(f"↳ {ad.get('name')} · {ad.get('creative_type')} · prueba: {ad.get('test_variable') or 'sin variable definida'}")
            for message in structure_diagnostics(plan_id, adsets, ads): st.info(message)


def render_meta_ads_execution() -> None:
    st.markdown("## Estructura y pruebas Meta Ads")
    st.caption("Organiza la jerarquía Campaña → Conjunto de anuncios → Anuncio y documenta qué variable estás probando.")
    tabs = st.tabs(("Arquitectura", "Conjuntos", "Anuncios", "Resultados"))
    with tabs[0]: _architecture()
    with tabs[1]: _adset_builder()
    with tabs[2]: _ad_builder()
    with tabs[3]: _results()
