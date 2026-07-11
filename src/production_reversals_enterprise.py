"""Controles enterprise para reversos de producción."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import production_reversals as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("production_rework_orders", "Órdenes de retrabajo"),
        ("production_reversal_reports", "Reportes de reversos"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = (
        "general_settings",
        *session_backup.LIST_SECTIONS,
        *session_backup.DICT_SECTIONS,
    )


_activate_backup()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_datetime(value) -> datetime | None:
    raw = str(value or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10])
        except ValueError:
            return None


def _production_name(production_id: str, productions: list[dict]) -> str:
    for production in productions:
        if str(production.get("production_id", "")) == production_id:
            return str(production.get("product_name", "Producción"))
    return "Producción no disponible"


def _blocked_reasons(production: dict, sales: list[dict], batches: list[dict], closings: list[dict]) -> list[str]:
    reasons = []
    production_id = str(production.get("production_id", ""))
    product_id = str(production.get("product_id", ""))
    batch_id = str(production.get("batch_id", ""))
    batch_code = str(production.get("batch_code", ""))
    sold = [
        sale for sale in sales
        if str(sale.get("order_status", "")).strip() not in {"Cancelado", "Anulado"}
        and (
            str(sale.get("production_id", "")) == production_id
            or (product_id and str(sale.get("product_id", "")) == product_id)
            or (batch_id and str(sale.get("batch_id", "")) == batch_id)
            or (batch_code and str(sale.get("batch_code", "")) == batch_code)
        )
    ]
    if sold:
        reasons.append(f"Tiene {len(sold)} venta(s), pedido(s) o despacho(s) vinculados.")
    committed_batch = [
        item for item in batches
        if str(item.get("production_id", "")) == production_id
        and _num(item.get("accepted_quantity")) > 0
        and str(item.get("commercial_status", "Disponible")) in {"Vendido", "Despachado", "Facturado", "Reservado"}
    ]
    if committed_batch:
        reasons.append("El lote tiene unidades vendidas, reservadas, facturadas o despachadas.")
    closed_after = []
    created = _as_datetime(production.get("created_at_utc"))
    for closing in closings:
        closed_at = _as_datetime(closing.get("closed_at_utc", closing.get("created_at_utc")))
        if created and closed_at and closed_at >= created and str(closing.get("status", "Cerrado")) == "Cerrado":
            closed_after.append(closing)
    if closed_after:
        reasons.append("Existe un cierre posterior a la producción.")
    return reasons


def _create_rework(request: dict, production: dict) -> None:
    orders = _rows("production_rework_orders")
    plans = _rows("production_plans")
    order_id = f"RW-{uuid4().hex[:8].upper()}"
    due_date = (date.today() + timedelta(days=3)).isoformat()
    order = {
        "rework_id": order_id,
        "request_id": str(request.get("request_id", "")),
        "source_production_id": str(production.get("production_id", "")),
        "product_id": str(production.get("product_id", "")),
        "product_name": str(production.get("product_name", "Producción")),
        "quantity": _num(request.get("quantity")),
        "reason": str(request.get("reason", "")),
        "priority": str(request.get("priority", "Alta")),
        "responsible": str(request.get("approved_by") or request.get("requested_by") or "Sin asignar"),
        "due_date": due_date,
        "additional_cost": _num(request.get("lost_cost")),
        "status": "Pendiente",
        "created_at_utc": _now(),
    }
    orders.append(order)
    plans.append({
        "plan_id": order_id,
        "product_id": order["product_id"],
        "product_name": order["product_name"],
        "quantity": order["quantity"],
        "due_date": due_date,
        "priority": order["priority"],
        "responsible": order["responsible"],
        "note": f"Retrabajo generado desde reverso {order['request_id']}",
        "status": "Pendiente",
        "created_at_utc": _now(),
    })
    _save("production_rework_orders", orders)
    _save("production_plans", plans)


def _export(requests: list[dict], productions: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Solicitud", "Producción", "Producto", "Tipo", "Cantidad", "Estado", "Prioridad", "Solicitado por", "Aprobado por", "Costo recuperado", "Costo perdido", "Motivo"])
    for request in requests:
        production_id = str(request.get("production_id", ""))
        writer.writerow([
            request.get("request_id", ""),
            production_id,
            _production_name(production_id, productions),
            request.get("reversal_type", ""),
            request.get("quantity", 0),
            request.get("status", ""),
            request.get("priority", ""),
            request.get("requested_by", ""),
            request.get("approved_by", ""),
            request.get("recovered_cost", 0),
            request.get("lost_cost", 0),
            request.get("reason", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_production_reversals_enterprise() -> None:
    render_page_header(
        "Reversos de producción",
        "Bloquea reversos riesgosos, genera retrabajo y analiza patrones de fallas.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_production_reversals()
    finally:
        base.render_page_header = original_header

    productions = _rows("production_log")
    requests = _rows("production_reversal_requests")
    sales = _rows("sales_registry")
    batches = _rows("production_batches")
    closings = _rows("cash_closings") + _rows("financial_closings")
    reworks = _rows("production_rework_orders")

    executed = [item for item in requests if item.get("status") == "Ejecutado"]
    blocked = [(production, _blocked_reasons(production, sales, batches, closings)) for production in productions if _blocked_reasons(production, sales, batches, closings)]
    rework_candidates = [item for item in executed if str(item.get("destination", "")) == "Retrabajo" or str(item.get("reversal_type", "")) == "Retrabajo"]

    st.divider()
    st.markdown("### Control enterprise")
    metrics = st.columns(5)
    metrics[0].metric("Bloqueados por riesgo", str(len(blocked)))
    metrics[1].metric("Retrabajos abiertos", str(sum(1 for item in reworks if item.get("status") != "Completado")))
    metrics[2].metric("Reversos ejecutados", str(len(executed)))
    total_recovered = sum(_num(item.get("recovered_cost")) for item in executed)
    total_lost = sum(_num(item.get("lost_cost")) for item in executed)
    metrics[3].metric("Recuperación", f"{(total_recovered / max(total_recovered + total_lost, 1)) * 100:,.1f}%")
    metrics[4].metric("Costo perdido", format_money(total_lost))

    if blocked:
        st.error(f"Hay {len(blocked)} producción(es) que no deberían reversarse sin autorización superior.")

    block_tab, rework_tab, report_tab, alerts_tab = st.tabs(("Bloqueos", "Retrabajo", "Reportes", "Alertas"))

    with block_tab:
        if not blocked:
            st.success("No se detectan producciones bloqueadas por ventas, lotes comprometidos o cierres.")
        for production, reasons in blocked:
            with st.container(border=True):
                st.markdown(f"**{production.get('product_name', 'Producción')} · {production.get('production_id', '')}**")
                for reason in reasons:
                    st.warning(reason)
                st.caption("Recomendación: hacer nota de crédito, ajuste autorizado o revisión gerencial antes de reversar.")

    with rework_tab:
        if not rework_candidates:
            st.info("No hay reversos ejecutados marcados para retrabajo.")
        for request in rework_candidates:
            already = any(str(item.get("request_id", "")) == str(request.get("request_id", "")) for item in reworks)
            production = next((item for item in productions if str(item.get("production_id", "")) == str(request.get("production_id", ""))), {})
            with st.container(border=True):
                st.markdown(f"**{request.get('request_id', '')} · {request.get('product_name', _production_name(str(request.get('production_id', '')), productions))}**")
                st.write(str(request.get("reason", "")))
                st.metric("Cantidad", f"{_num(request.get('quantity')):,.2f}")
                if st.button("Crear orden de retrabajo", key=f"create_rework_{request.get('request_id')}", disabled=already, use_container_width=True):
                    _create_rework(request, production)
                    st.rerun()
        st.markdown("#### Órdenes de retrabajo")
        for order in reversed(reworks[-50:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{order.get('rework_id', '')} · {order.get('product_name', '')}**")
                cols[0].caption(f"Origen: {order.get('source_production_id', '')} · Reverso: {order.get('request_id', '')}")
                cols[1].metric("Cantidad", f"{_num(order.get('quantity')):,.2f}")
                cols[2].metric("Fecha límite", str(order.get("due_date", "")))
                cols[3].metric("Estado", str(order.get("status", "Pendiente")))

    with report_tab:
        st.download_button(
            "Descargar reporte de reversos CSV",
            data=_export(requests, productions),
            file_name=f"reversos_produccion_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not requests,
        )
        by_product: dict[str, float] = defaultdict(float)
        by_owner: Counter[str] = Counter()
        by_reason: Counter[str] = Counter()
        for request in executed:
            by_product[str(request.get("product_name") or _production_name(str(request.get("production_id", "")), productions))] += _num(request.get("quantity"))
            by_owner[str(request.get("approved_by") or request.get("requested_by") or "Sin asignar")] += 1
            by_reason[str(request.get("reason", "Sin motivo"))[:60]] += 1
        cols = st.columns(3)
        with cols[0]:
            st.markdown("#### Por producto")
            for name, qty in sorted(by_product.items(), key=lambda item: item[1], reverse=True)[:10]:
                st.write(f"**{name}:** {qty:,.2f}")
        with cols[1]:
            st.markdown("#### Por responsable")
            for owner, count in by_owner.most_common(10):
                st.write(f"**{owner}:** {count}")
        with cols[2]:
            st.markdown("#### Por motivo")
            for reason, count in by_reason.most_common(10):
                st.write(f"**{reason}:** {count}")

    with alerts_tab:
        product_counts: Counter[str] = Counter(str(item.get("product_name") or _production_name(str(item.get("production_id", "")), productions)) for item in executed)
        owner_counts: Counter[str] = Counter(str(item.get("approved_by") or item.get("requested_by") or "Sin asignar") for item in executed)
        reason_counts: Counter[str] = Counter(str(item.get("reason", "Sin motivo"))[:60] for item in executed)
        alerts = []
        alerts.extend([f"El producto {name} acumula {count} reversos. Revisar proceso, material o diseño." for name, count in product_counts.items() if count >= 3])
        alerts.extend([f"El responsable {name} aparece en {count} reversos. Revisar capacitación o flujo de aprobación." for name, count in owner_counts.items() if count >= 5])
        alerts.extend([f"Motivo repetido: {reason} ({count} veces). Crear acción correctiva." for reason, count in reason_counts.items() if count >= 3])
        if not alerts:
            st.success("No hay patrones repetitivos que requieran alerta.")
        for alert in alerts:
            st.warning(alert)

    render_info_card(
        "Reversos con gobierno",
        "Los bloqueos, retrabajos y reportes reducen errores operativos y pérdidas por reversos mal ejecutados.",
        "CONTROL ENTERPRISE",
    )
