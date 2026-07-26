"""Analítica ejecutiva de solo lectura para Inicio fase 5.

Añade comparativos por periodo, rankings y señales operativas usando únicamente
colecciones existentes en ``st.session_state``. No modifica registros.
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
        "purchase_date",
        "movement_date",
        "accepted_at_utc",
        "updated_at_utc",
    ):
        parsed = _date_value(row.get(key))
        if parsed:
            return parsed
    return None


def _amount(row: dict) -> float:
    return _num(
        row.get(
            "total",
            row.get(
                "grand_total",
                row.get("amount", row.get("value", row.get("net_total", 0.0))),
            ),
        )
    )


def _period_rows(rows: Iterable[dict], start: date, end: date) -> list[dict]:
    return [row for row in rows if (row_date := _row_date(row)) and start <= row_date <= end]


def _comparison(rows: list[dict], days: int) -> tuple[float, float, float | None]:
    end = date.today()
    current_start = end - timedelta(days=days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    current_total = sum(_amount(row) for row in _period_rows(rows, current_start, end))
    previous_total = sum(_amount(row) for row in _period_rows(rows, previous_start, previous_end))
    if previous_total == 0:
        return current_total, previous_total, None
    return current_total, previous_total, (current_total - previous_total) / previous_total * 100


def _ranking(rows: list[dict], label_keys: tuple[str, ...], days: int = 30, limit: int = 5) -> list[tuple[str, float]]:
    start = date.today() - timedelta(days=days - 1)
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        row_date = _row_date(row)
        if not row_date or row_date < start:
            continue
        label = ""
        for key in label_keys:
            candidate = str(row.get(key) or "").strip()
            if candidate:
                label = candidate
                break
        if not label:
            label = "Sin identificar"
        totals[label] += _amount(row)
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]


def _inventory_signals() -> tuple[int, int, int]:
    stagnant = 0
    low_cover = 0
    healthy = 0
    movements = read_list("inventory_movements")
    last_movement: dict[str, date] = {}
    for row in movements:
        item_id = str(row.get("item_id") or row.get("catalog_item_id") or "")
        row_date = _row_date(row)
        if item_id and row_date and (item_id not in last_movement or row_date > last_movement[item_id]):
            last_movement[item_id] = row_date

    today = date.today()
    for row in read_list("inventory_registry"):
        if not row.get("active", True):
            continue
        item_id = str(row.get("item_id") or row.get("catalog_item_id") or "")
        available = _num(row.get("available_quantity", row.get("quantity", row.get("stock", 0.0))))
        minimum = _num(row.get("minimum_stock", row.get("reorder_point", 0.0)))
        moved = last_movement.get(item_id)
        if available > 0 and (not moved or (today - moved).days >= 60):
            stagnant += 1
        elif minimum > 0 and available <= minimum:
            low_cover += 1
        else:
            healthy += 1
    return stagnant, low_cover, healthy


def _overdue_balance(key: str) -> float:
    today = date.today()
    total = 0.0
    for row in read_list(key):
        status = str(row.get("status", "Pendiente")).casefold()
        if status in {"pagado", "pagada", "cerrado", "cerrada"}:
            continue
        due = _date_value(row.get("due_date") or row.get("payment_due_date") or row.get("expected_date"))
        if due and due < today:
            total += max(_num(row.get("balance", row.get("pending_amount", row.get("amount_due", 0.0)))), 0.0)
    return total


def _render_delta_metric(column: Any, label: str, current: float, delta: float | None) -> None:
    delta_text = "Sin base comparable" if delta is None else f"{delta:+.1f}%"
    column.metric(label, f"${current:,.2f}", delta_text)


def render_phase5_sections(period_days: int = 30) -> None:
    """Renderiza analítica ejecutiva sin escribir datos operativos."""
    period_days = period_days if period_days in {7, 14, 30} else 30
    sales = read_list("sales_registry")
    purchases = read_list("catalog_purchase_orders")

    st.markdown("### Analítica ejecutiva")
    st.caption(f"Comparación del periodo actual de {period_days} días contra los {period_days} días anteriores.")
    sales_current, _, sales_delta = _comparison(sales, period_days)
    purchases_current, _, purchases_delta = _comparison(purchases, period_days)
    receivables_overdue = _overdue_balance("receivables_registry")
    payables_overdue = _overdue_balance("payables_registry")
    metrics = st.columns(4)
    _render_delta_metric(metrics[0], "Ventas del periodo", sales_current, sales_delta)
    _render_delta_metric(metrics[1], "Compras del periodo", purchases_current, purchases_delta)
    metrics[2].metric("Cobros vencidos", f"${receivables_overdue:,.2f}")
    metrics[3].metric("Pagos vencidos", f"${payables_overdue:,.2f}")

    ranking_columns = st.columns(3)
    rankings = (
        ("Productos con mayor facturación", _ranking(sales, ("item_name", "product_name", "description"), period_days)),
        ("Clientes por facturación", _ranking(sales, ("customer_name", "customer", "client_name"), period_days)),
        ("Proveedores por compras", _ranking(purchases, ("supplier", "supplier_name", "vendor_name"), period_days)),
    )
    for column, (title, rows) in zip(ranking_columns, rankings, strict=True):
        with column:
            with st.container(border=True):
                st.markdown(f"#### {title}")
                if not rows:
                    st.info("No hay datos suficientes en el periodo seleccionado.")
                for index, (label, total) in enumerate(rows, start=1):
                    st.markdown(f"**{index}. {label}**")
                    st.caption(f"${total:,.2f}")

    stagnant, low_cover, healthy = _inventory_signals()
    st.markdown("### Señales de inventario y cartera")
    signal_columns = st.columns(3)
    signal_columns[0].metric("Inventario sin movimiento", stagnant, "60 días o más")
    signal_columns[1].metric("Cobertura baja", low_cover, "En mínimo o por debajo")
    signal_columns[2].metric("Inventario saludable", healthy)

    with st.container(border=True):
        st.markdown("#### Lectura ejecutiva")
        messages: list[str] = []
        if sales_delta is None:
            messages.append("No existe una base anterior suficiente para calcular la variación de ventas.")
        elif sales_delta >= 0:
            messages.append(f"Las ventas crecieron {sales_delta:.1f}% frente al periodo anterior.")
        else:
            messages.append(f"Las ventas disminuyeron {abs(sales_delta):.1f}% frente al periodo anterior.")
        if purchases_delta is not None and purchases_delta > 25:
            messages.append("Las compras aumentaron con fuerza; conviene revisar si el incremento responde a demanda real o acumulación de inventario.")
        if stagnant:
            messages.append(f"Hay {stagnant} artículo(s) con existencia y sin movimiento reciente.")
        if receivables_overdue > 0:
            messages.append(f"Existen ${receivables_overdue:,.2f} vencidos por cobrar.")
        if payables_overdue > 0:
            messages.append(f"Existen ${payables_overdue:,.2f} vencidos por pagar.")
        for message in messages:
            st.markdown(f"- {message}")
        st.caption("Análisis determinista de solo lectura. No utiliza predicciones ni modifica registros.")
