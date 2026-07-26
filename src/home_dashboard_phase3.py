"""Extensiones de solo lectura para Inicio fase 3.

Añade centros financiero, comercial y logístico, gráficos simples con datos
históricos disponibles y un resumen explicativo basado en reglas. No modifica
registros ni requiere migraciones.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable

import streamlit as st

from src.session_utils import read_list


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _row_date(row: dict) -> date | None:
    for key in (
        "created_at_utc",
        "created_at",
        "date",
        "sale_date",
        "movement_date",
        "accepted_at_utc",
        "updated_at_utc",
    ):
        parsed = _date_value(row.get(key))
        if parsed:
            return parsed
    return None


def _sum_amount(rows: Iterable[dict]) -> float:
    return sum(
        _num(
            row.get(
                "total",
                row.get(
                    "grand_total",
                    row.get("amount", row.get("value", row.get("net_total", 0.0))),
                ),
            )
        )
        for row in rows
    )


def _daily_series(rows: list[dict], days: int = 7) -> dict[str, float]:
    start = date.today() - timedelta(days=days - 1)
    totals: dict[date, float] = defaultdict(float)
    for row in rows:
        row_date = _row_date(row)
        if row_date and row_date >= start:
            totals[row_date] += _sum_amount([row])
    return {
        (start + timedelta(days=index)).strftime("%d/%m"): totals.get(start + timedelta(days=index), 0.0)
        for index in range(days)
    }


def _today_rows(key: str) -> list[dict]:
    today = date.today()
    return [row for row in read_list(key) if _row_date(row) == today]


def _new_customers_today() -> int:
    return len(_today_rows("customers_registry"))


def _active_quotes() -> int:
    terminal = {"aceptada", "aceptado", "rechazada", "rechazado", "vencida", "vencido", "cancelada", "cancelado"}
    return sum(
        1
        for row in read_list("quotes_registry")
        if str(row.get("status", "Pendiente")).strip().casefold() not in terminal
    )


def _conversion_rate() -> float:
    quotes = read_list("quotes_registry")
    if not quotes:
        return 0.0
    accepted = sum(
        str(row.get("status", "")).strip().casefold() in {"aceptada", "aceptado", "convertida", "convertido"}
        for row in quotes
    )
    return accepted / len(quotes) * 100


def _cash_summary() -> tuple[float, float, float]:
    rows = _today_rows("cash_movements")
    income = 0.0
    expense = 0.0
    for row in rows:
        amount = abs(_num(row.get("amount", row.get("value", 0.0))))
        movement_type = str(row.get("movement_type", row.get("type", ""))).strip().casefold()
        if movement_type in {"ingreso", "entrada", "cobro", "venta", "income"}:
            income += amount
        elif movement_type in {"egreso", "salida", "pago", "gasto", "expense"}:
            expense += amount
    return income, expense, income - expense


def _logistics_summary() -> tuple[int, int, int]:
    pending_receipts = sum(
        1
        for row in read_list("catalog_purchase_orders")
        if str(row.get("purchase_status", "Ordenada")).strip().casefold()
        not in {"recibida", "cerrada", "cancelada"}
        and _num(row.get("received_quantity")) < _num(row.get("ordered_quantity"))
    )
    today = date.today()
    dispatches = 0
    delays = 0
    for row in read_list("sales_registry"):
        status = str(row.get("order_status", "Pendiente")).strip().casefold()
        due = _date_value(row.get("delivery_date") or row.get("due_date") or row.get("expected_date"))
        if due == today and status not in {"entregado", "entregada", "cancelado", "cancelada"}:
            dispatches += 1
        if due and due < today and status not in {"entregado", "entregada", "cancelado", "cancelada"}:
            delays += 1
    return pending_receipts, dispatches, delays


def _summary_sentences(
    sales_today: float,
    pending_purchases: int,
    low_stock: int,
    out_of_stock: int,
    deliveries_today: int,
    receivables: float,
    payables: float,
) -> list[str]:
    sentences: list[str] = []
    sales_rows = read_list("sales_registry")
    today = date.today()
    previous = today - timedelta(days=7)
    previous_total = _sum_amount([row for row in sales_rows if _row_date(row) == previous])
    if previous_total > 0:
        delta = (sales_today - previous_total) / previous_total * 100
        direction = "aumentaron" if delta >= 0 else "disminuyeron"
        sentences.append(f"Las ventas de hoy {direction} {abs(delta):.1f}% frente al mismo día de la semana pasada.")
    elif sales_today > 0:
        sentences.append(f"Hoy se han registrado ventas por ${sales_today:,.2f}.")
    else:
        sentences.append("Todavía no se registran ventas hoy.")

    if out_of_stock:
        sentences.append(f"Hay {out_of_stock} artículo(s) agotado(s) que requieren atención inmediata.")
    elif low_stock:
        sentences.append(f"Hay {low_stock} artículo(s) en nivel mínimo de inventario.")
    else:
        sentences.append("No hay alertas críticas de inventario con los datos disponibles.")

    if pending_purchases:
        sentences.append(f"Existen {pending_purchases} compra(s) pendientes de recepción.")
    if deliveries_today:
        sentences.append(f"Hoy deben entregarse {deliveries_today} pedido(s).")
    if receivables > 0 or payables > 0:
        sentences.append(
            f"El saldo pendiente es de ${receivables:,.2f} por cobrar y ${payables:,.2f} por pagar."
        )
    else:
        sentences.append("No hay saldos pendientes registrados en cuentas por cobrar o por pagar.")
    return sentences


def render_phase3_sections(
    *,
    sales_today: float,
    pending_purchases: int,
    low_stock: int,
    out_of_stock: int,
    deliveries_today: int,
    receivables: float,
    payables: float,
) -> None:
    """Renderiza secciones ejecutivas adicionales sin escribir datos."""
    st.markdown("### Tendencia operativa")
    chart_columns = st.columns(2)
    with chart_columns[0]:
        st.caption("Ventas · últimos 7 días")
        st.line_chart(_daily_series(read_list("sales_registry")), height=220)
    with chart_columns[1]:
        st.caption("Compras · últimos 7 días")
        st.bar_chart(_daily_series(read_list("catalog_purchase_orders")), height=220)

    st.markdown("### Centros de operación")
    financial, commercial, logistics = st.columns(3)
    income, expense, net = _cash_summary()
    with financial:
        with st.container(border=True):
            st.markdown("#### Centro financiero")
            st.metric("Ingresos de hoy", f"${income:,.2f}")
            st.metric("Egresos de hoy", f"${expense:,.2f}")
            st.metric("Flujo neto", f"${net:,.2f}")
            st.caption(f"Por cobrar: ${receivables:,.2f} · Por pagar: ${payables:,.2f}")

    with commercial:
        with st.container(border=True):
            st.markdown("#### Centro comercial")
            st.metric("Clientes nuevos", _new_customers_today())
            st.metric("Cotizaciones activas", _active_quotes())
            st.metric("Conversión", f"{_conversion_rate():.1f}%")
            st.caption(f"Ventas de hoy: ${sales_today:,.2f}")

    pending_receipts, dispatches, delays = _logistics_summary()
    with logistics:
        with st.container(border=True):
            st.markdown("#### Centro logístico")
            st.metric("Recepciones pendientes", pending_receipts)
            st.metric("Despachos de hoy", dispatches)
            st.metric("Pedidos retrasados", delays)
            st.caption(f"Stock bajo: {low_stock} · Agotados: {out_of_stock}")

    st.markdown("### Resumen inteligente")
    with st.container(border=True):
        for sentence in _summary_sentences(
            sales_today,
            pending_purchases,
            low_stock,
            out_of_stock,
            deliveries_today,
            receivables,
            payables,
        ):
            st.markdown(f"- {sentence}")
        st.caption("Resumen determinista basado en reglas y datos disponibles. No utiliza predicciones ni IA generativa.")
