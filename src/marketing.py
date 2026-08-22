"""Módulo de marketing y contenido para CopyMary ERP.

Gestiona campañas, calendario de publicaciones y métricas con persistencia
write-through usando session_store. La primera versión está pensada para
Instagram, TikTok, WhatsApp y acciones locales, pero admite otros canales.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import streamlit as st

from src import auth
from src.components import render_info_card, render_page_header
from src.erp_database import record_audit_event
from src.session_utils import now_iso, read_list, save_list

CAMPAIGNS_KEY = "marketing_campaigns"
CONTENT_KEY = "marketing_content"
METRICS_KEY = "marketing_metrics"

CHANNELS = ("Instagram", "TikTok", "WhatsApp", "Facebook", "Tienda física", "Otro")
CAMPAIGN_STATUSES = ("Planificada", "Activa", "Pausada", "Finalizada")
CONTENT_STATUSES = ("Idea", "Por diseñar", "En revisión", "Aprobado", "Programado", "Publicado")
CONTENT_TYPES = ("Post", "Reel", "Historia", "Carrusel", "Video", "Promoción", "Otro")


def _actor_id() -> str:
    user = auth.current_user()
    return user.user_id if user else ""


def _audit(entity: str, entity_id: str, action: str, after: dict | None = None) -> None:
    record_audit_event(
        "Marketing",
        entity,
        entity_id,
        action,
        after=after or {},
        actor_user_id=_actor_id(),
    )


def marketing_summary(
    campaigns: list[dict] | None = None,
    content: list[dict] | None = None,
    metrics: list[dict] | None = None,
) -> dict:
    campaigns = campaigns if campaigns is not None else read_list(CAMPAIGNS_KEY)
    content = content if content is not None else read_list(CONTENT_KEY)
    metrics = metrics if metrics is not None else read_list(METRICS_KEY)

    active_campaigns = sum(1 for row in campaigns if row.get("status") == "Activa")
    pending_content = sum(1 for row in content if row.get("status") not in {"Publicado"})
    published_content = sum(1 for row in content if row.get("status") == "Publicado")
    spend = sum(float(row.get("spend", 0) or 0) for row in metrics)
    revenue = sum(float(row.get("revenue", 0) or 0) for row in metrics)
    leads = sum(int(row.get("leads", 0) or 0) for row in metrics)
    clicks = sum(int(row.get("clicks", 0) or 0) for row in metrics)
    impressions = sum(int(row.get("impressions", 0) or 0) for row in metrics)
    ctr = (clicks / impressions * 100) if impressions else 0.0
    cpl = (spend / leads) if leads else 0.0
    roas = (revenue / spend) if spend else 0.0
    return {
        "active_campaigns": active_campaigns,
        "pending_content": pending_content,
        "published_content": published_content,
        "spend": spend,
        "revenue": revenue,
        "leads": leads,
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "cpl": cpl,
        "roas": roas,
    }


def _campaign_name(campaign_id: str, campaigns: list[dict]) -> str:
    for row in campaigns:
        if row.get("campaign_id") == campaign_id:
            return str(row.get("name") or campaign_id)
    return "Sin campaña"


def _campaign_options(campaigns: list[dict]) -> dict[str, str]:
    options = {"Sin campaña": ""}
    for row in campaigns:
        options[str(row.get("name") or row.get("campaign_id"))] = str(row.get("campaign_id", ""))
    return options


def _render_summary(campaigns: list[dict], content: list[dict], metrics: list[dict]) -> None:
    summary = marketing_summary(campaigns, content, metrics)
    cols = st.columns(4)
    cols[0].metric("Campañas activas", str(summary["active_campaigns"]))
    cols[1].metric("Contenido pendiente", str(summary["pending_content"]))
    cols[2].metric("Contenido publicado", str(summary["published_content"]))
    cols[3].metric("Leads / consultas", str(summary["leads"]))

    cols = st.columns(4)
    cols[0].metric("Inversión", f"${summary['spend']:,.2f}")
    cols[1].metric("Ventas atribuidas", f"${summary['revenue']:,.2f}")
    cols[2].metric("CTR", f"{summary['ctr']:.2f}%")
    cols[3].metric("ROAS", f"{summary['roas']:.2f}x")

    if summary["spend"] > 0 and summary["leads"] > 0:
        st.caption(f"Costo promedio por lead: ${summary['cpl']:,.2f}")

    upcoming = sorted(
        [row for row in content if row.get("publish_date") and row.get("status") != "Publicado"],
        key=lambda row: str(row.get("publish_date")),
    )[:5]
    st.markdown("### Próximas publicaciones")
    if not upcoming:
        st.caption("No hay publicaciones programadas todavía.")
    for row in upcoming:
        with st.container(border=True):
            st.write(f"**{row.get('title', 'Contenido')}** · {row.get('channel', '')} · {row.get('publish_date', '')}")
            st.caption(f"{row.get('content_type', '')} · {row.get('status', '')}")


def _render_campaigns(campaigns: list[dict]) -> None:
    st.subheader("Campañas")
    with st.form("marketing_campaign_form", clear_on_submit=True):
        name = st.text_input("Nombre de la campaña", placeholder="Ej. Regreso a clases agosto")
        objective = st.text_input("Objetivo", placeholder="Ej. generar consultas y ventas")
        audience = st.text_input("Público objetivo", placeholder="Ej. padres con niños en edad escolar")
        channel = st.selectbox("Canal principal", CHANNELS)
        cols = st.columns(2)
        start_date = cols[0].date_input("Fecha de inicio", value=date.today())
        end_date = cols[1].date_input("Fecha de cierre", value=date.today())
        budget = st.number_input("Presupuesto previsto (USD)", min_value=0.0, step=1.0)
        status = st.selectbox("Estado", CAMPAIGN_STATUSES)
        notes = st.text_area("Notas")
        submitted = st.form_submit_button("Crear campaña", type="primary", use_container_width=True)
    if submitted:
        if not name.strip():
            st.error("El nombre de la campaña es obligatorio.")
        elif end_date < start_date:
            st.error("La fecha de cierre no puede ser anterior al inicio.")
        else:
            campaign = {
                "campaign_id": f"MKT-CMP-{uuid4().hex[:8].upper()}",
                "name": name.strip(),
                "objective": objective.strip(),
                "audience": audience.strip(),
                "channel": channel,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "budget": float(budget),
                "status": status,
                "notes": notes.strip(),
                "created_at_utc": now_iso(),
            }
            save_list(CAMPAIGNS_KEY, [*campaigns, campaign])
            _audit("marketing_campaign", campaign["campaign_id"], "create", campaign)
            st.success("Campaña creada.")
            st.rerun()

    st.divider()
    if not campaigns:
        st.caption("Todavía no hay campañas registradas.")
        return
    for row in reversed(campaigns):
        with st.container(border=True):
            cols = st.columns([4, 2, 1])
            cols[0].write(f"**{row.get('name', 'Campaña')}**")
            cols[0].caption(f"{row.get('objective', '')} · Público: {row.get('audience', 'No definido')}")
            cols[1].write(f"{row.get('status', '')} · {row.get('channel', '')}")
            cols[1].caption(f"{row.get('start_date', '')} → {row.get('end_date', '')} · Presupuesto ${float(row.get('budget', 0) or 0):,.2f}")
            if cols[2].button("Eliminar", key=f"del_campaign_{row.get('campaign_id')}", use_container_width=True):
                updated = [item for item in campaigns if item.get("campaign_id") != row.get("campaign_id")]
                save_list(CAMPAIGNS_KEY, updated)
                _audit("marketing_campaign", str(row.get("campaign_id")), "delete")
                st.rerun()


def _render_content(campaigns: list[dict], content: list[dict]) -> None:
    st.subheader("Calendario de contenido")
    campaign_options = _campaign_options(campaigns)
    with st.form("marketing_content_form", clear_on_submit=True):
        title = st.text_input("Título / idea", placeholder="Ej. 3 razones para imprimir tus fotos")
        cols = st.columns(3)
        content_type = cols[0].selectbox("Formato", CONTENT_TYPES)
        channel = cols[1].selectbox("Canal", CHANNELS)
        status = cols[2].selectbox("Estado", CONTENT_STATUSES)
        publish_date = st.date_input("Fecha prevista", value=date.today())
        campaign_label = st.selectbox("Campaña relacionada", tuple(campaign_options.keys()))
        copy = st.text_area("Copy / mensaje principal")
        cta = st.text_input("Llamado a la acción", placeholder="Ej. Escríbenos por WhatsApp")
        links = st.columns(2)
        canva_url = links[0].text_input("Enlace de Canva")
        folder_path = links[1].text_input("Ruta de archivo/carpeta")
        submitted = st.form_submit_button("Agregar al calendario", type="primary", use_container_width=True)
    if submitted:
        if not title.strip():
            st.error("El título o idea es obligatorio.")
        else:
            row = {
                "content_id": f"MKT-CNT-{uuid4().hex[:8].upper()}",
                "title": title.strip(),
                "content_type": content_type,
                "channel": channel,
                "status": status,
                "publish_date": publish_date.isoformat(),
                "campaign_id": campaign_options[campaign_label],
                "copy": copy.strip(),
                "cta": cta.strip(),
                "canva_url": canva_url.strip(),
                "folder_path": folder_path.strip(),
                "created_at_utc": now_iso(),
            }
            save_list(CONTENT_KEY, [*content, row])
            _audit("marketing_content", row["content_id"], "create", row)
            st.success("Contenido agregado al calendario.")
            st.rerun()

    st.divider()
    filters = st.columns(3)
    channel_filter = filters[0].selectbox("Filtrar canal", ("Todos", *CHANNELS), key="mkt_channel_filter")
    status_filter = filters[1].selectbox("Filtrar estado", ("Todos", *CONTENT_STATUSES), key="mkt_status_filter")
    type_filter = filters[2].selectbox("Filtrar formato", ("Todos", *CONTENT_TYPES), key="mkt_type_filter")
    rows = content
    if channel_filter != "Todos":
        rows = [row for row in rows if row.get("channel") == channel_filter]
    if status_filter != "Todos":
        rows = [row for row in rows if row.get("status") == status_filter]
    if type_filter != "Todos":
        rows = [row for row in rows if row.get("content_type") == type_filter]
    rows = sorted(rows, key=lambda row: str(row.get("publish_date", "")))

    if not rows:
        st.caption("No hay contenido para los filtros seleccionados.")
    for row in rows:
        with st.container(border=True):
            cols = st.columns([4, 2, 1])
            cols[0].write(f"**{row.get('title', 'Contenido')}**")
            cols[0].caption(
                f"{row.get('content_type', '')} · {row.get('channel', '')} · "
                f"Campaña: {_campaign_name(str(row.get('campaign_id', '')), campaigns)}"
            )
            cols[1].write(str(row.get("publish_date", "")))
            cols[1].caption(str(row.get("status", "")))
            if cols[2].button("Eliminar", key=f"del_content_{row.get('content_id')}", use_container_width=True):
                updated = [item for item in content if item.get("content_id") != row.get("content_id")]
                save_list(CONTENT_KEY, updated)
                _audit("marketing_content", str(row.get("content_id")), "delete")
                st.rerun()
            if row.get("copy"):
                st.caption(str(row.get("copy")))
            link_bits = []
            if row.get("canva_url"):
                link_bits.append(f"Canva: {row['canva_url']}")
            if row.get("folder_path"):
                link_bits.append(f"Ruta: {row['folder_path']}")
            if link_bits:
                st.caption(" · ".join(link_bits))


def _render_metrics(campaigns: list[dict], metrics: list[dict]) -> None:
    st.subheader("Resultados y métricas")
    campaign_options = _campaign_options(campaigns)
    with st.form("marketing_metrics_form", clear_on_submit=True):
        campaign_label = st.selectbox("Campaña", tuple(campaign_options.keys()), key="metric_campaign")
        metric_date = st.date_input("Fecha", value=date.today(), key="metric_date")
        cols = st.columns(4)
        impressions = cols[0].number_input("Impresiones", min_value=0, step=1)
        reach = cols[1].number_input("Alcance", min_value=0, step=1)
        clicks = cols[2].number_input("Clics", min_value=0, step=1)
        leads = cols[3].number_input("Leads / consultas", min_value=0, step=1)
        cols = st.columns(3)
        sales = cols[0].number_input("Ventas", min_value=0, step=1)
        spend = cols[1].number_input("Inversión USD", min_value=0.0, step=1.0)
        revenue = cols[2].number_input("Ingresos atribuidos USD", min_value=0.0, step=1.0)
        notes = st.text_input("Notas")
        submitted = st.form_submit_button("Registrar métricas", type="primary", use_container_width=True)
    if submitted:
        row = {
            "metric_id": f"MKT-MET-{uuid4().hex[:8].upper()}",
            "campaign_id": campaign_options[campaign_label],
            "date": metric_date.isoformat(),
            "impressions": int(impressions),
            "reach": int(reach),
            "clicks": int(clicks),
            "leads": int(leads),
            "sales": int(sales),
            "spend": float(spend),
            "revenue": float(revenue),
            "notes": notes.strip(),
            "created_at_utc": now_iso(),
        }
        save_list(METRICS_KEY, [*metrics, row])
        _audit("marketing_metric", row["metric_id"], "create", row)
        st.success("Métricas registradas.")
        st.rerun()

    st.divider()
    summary = marketing_summary([], [], metrics)
    cols = st.columns(4)
    cols[0].metric("Impresiones", f"{summary['impressions']:,}")
    cols[1].metric("Clics", f"{summary['clicks']:,}")
    cols[2].metric("CTR", f"{summary['ctr']:.2f}%")
    cols[3].metric("ROAS", f"{summary['roas']:.2f}x")

    if not metrics:
        st.caption("Todavía no hay métricas registradas.")
        return
    for row in reversed(metrics):
        with st.container(border=True):
            campaign = _campaign_name(str(row.get("campaign_id", "")), campaigns)
            st.write(f"**{row.get('date', '')} · {campaign}**")
            st.caption(
                f"Impresiones {int(row.get('impressions', 0) or 0):,} · Clics {int(row.get('clicks', 0) or 0):,} · "
                f"Leads {int(row.get('leads', 0) or 0):,} · Ventas {int(row.get('sales', 0) or 0):,} · "
                f"Inversión ${float(row.get('spend', 0) or 0):,.2f} · Ingresos ${float(row.get('revenue', 0) or 0):,.2f}"
            )


def render_marketing() -> None:
    render_page_header(
        "Marketing",
        "Planifica campañas, organiza contenido y mide qué acciones generan consultas y ventas.",
    )
    st.caption("Pensado para redes sociales, WhatsApp y promociones locales. Los datos se guardan en la persistencia del ERP.")

    campaigns = read_list(CAMPAIGNS_KEY)
    content = read_list(CONTENT_KEY)
    metrics = read_list(METRICS_KEY)

    summary_tab, campaigns_tab, content_tab, metrics_tab = st.tabs(
        ("Resumen", "Campañas", "Calendario de contenido", "Métricas")
    )
    with summary_tab:
        _render_summary(campaigns, content, metrics)
    with campaigns_tab:
        _render_campaigns(campaigns)
    with content_tab:
        _render_content(campaigns, content)
    with metrics_tab:
        _render_metrics(campaigns, metrics)

    render_info_card(
        "Qué mide esta primera versión",
        "Campañas, presupuesto, publicaciones, estado creativo, impresiones, alcance, clics, consultas, ventas, inversión, CTR, costo por lead y ROAS.",
        "MARKETING",
    )
