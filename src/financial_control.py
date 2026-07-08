"""Panel financiero con cierres de caja seguros por método de pago."""

from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.financial import _build_financial_csv, _cash_totals, _filter_by_period, _sales_totals
from src.money import format_money

METHODS = ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro")


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _amount(value) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _cash_by_reference(cash: list[dict]) -> dict[str, dict]:
    """Devuelve movimientos de caja por referencia para validar cierres.

    Antes este helper vivía en `financial_reconciliation`; se mantiene aquí para que
    el panel financiero no dependa de helpers internos que pueden cambiar.
    """
    result: dict[str, dict] = {}
    for item in cash:
        for key in ("reference", "payment_id", "sale_id", "source_payment_id"):
            value = str(item.get(key, "")).strip()
            if value:
                result[value] = item
    return result


def _expected_records() -> list[dict]:
    records: list[dict] = []
    for payment in _rows("payment_records"):
        records.append({
            "kind": "Cobro",
            "payment_id": str(payment.get("payment_id", "")),
            "amount": _amount(payment.get("amount")),
            "payment_method": str(payment.get("payment_method", "Otro")),
        })
    for payment in _rows("supplier_payment_records"):
        records.append({
            "kind": "Pago proveedor",
            "payment_id": str(payment.get("payment_id", "")),
            "amount": _amount(payment.get("amount")),
            "payment_method": str(payment.get("payment_method", "Otro")),
            "expected_type": "Egreso",
        })
    return records


def _check_record(record: dict, cash_map: dict[str, dict]) -> list[str]:
    issues: list[str] = []
    payment_id = str(record.get("payment_id", "")).strip()
    if not payment_id:
        return issues
    cash = cash_map.get(payment_id)
    if cash is None:
        issues.append("no tiene movimiento de caja relacionado")
        return issues
    expected_amount = _amount(record.get("amount"))
    cash_amount = _amount(cash.get("amount"))
    if abs(expected_amount - cash_amount) > 0.01:
        issues.append("el monto no coincide con caja")
    expected_method = str(record.get("payment_method", "Otro"))
    cash_method = str(cash.get("payment_method", "Otro"))
    if expected_method and cash_method and expected_method != cash_method:
        issues.append("el método de pago no coincide")
    expected_type = str(record.get("expected_type", "Ingreso"))
    cash_type = str(cash.get("movement_type", "Ingreso"))
    if expected_type and cash_type and expected_type != cash_type:
        issues.append("el tipo de movimiento no coincide")
    return issues


def _method(item: dict) -> str:
    value = str(item.get("payment_method", "Otro")).strip()
    return value if value in METHODS else "Otro"


def _movement_id(item: dict, index: int) -> str:
    return str(item.get("movement_id") or f"legacy-{index}")


def _closed_ids(closings: list[dict]) -> set[str]:
    result: set[str] = set()
    for closing in closings:
        for movement_id in closing.get("movement_ids", []):
            result.add(str(movement_id))
    return result


def _opening_by_method(closings: list[dict]) -> dict[str, float]:
    opening = {method: 0.0 for method in METHODS}
    for closing in closings:
        counted = closing.get("counted_by_method", {})
        if isinstance(counted, dict):
            for method in METHODS:
                if method in counted:
                    opening[method] = float(counted.get(method, 0.0))
    return opening


def _pending_movements(cash: list[dict], closings: list[dict], scope: tuple[str, ...]) -> list[dict]:
    closed = _closed_ids(closings)
    pending: list[dict] = []
    for index, item in enumerate(cash):
        movement_id = _movement_id(item, index)
        if movement_id in closed:
            continue
        if _method(item) in scope:
            current = dict(item)
            current["_closing_movement_id"] = movement_id
            pending.append(current)
    return pending


def _expected_by_method(cash: list[dict], closings: list[dict], scope: tuple[str, ...]) -> tuple[dict[str, float], list[dict]]:
    opening = _opening_by_method(closings)
    pending = _pending_movements(cash, closings, scope)
    expected = {method: opening[method] for method in scope}
    for item in pending:
        method = _method(item)
        amount = float(item.get("amount", 0.0))
        sign = 1 if item.get("movement_type") == "Ingreso" else -1
        expected[method] = expected.get(method, 0.0) + sign * amount
    return expected, pending


def _closing_blockers(cash: list[dict], pending: list[dict]) -> list[str]:
    blockers: list[str] = []
    cash_map = _cash_by_reference(cash)
    for record in _expected_records():
        issues = _check_record(record, cash_map)
        if issues:
            blockers.append(f"{record.get('kind', 'Pago')} {record.get('payment_id', '')}: {issues[0]}")

    movement_ids = [str(item.get("_closing_movement_id", "")) for item in pending]
    duplicates = sorted({movement_id for movement_id in movement_ids if movement_id and movement_ids.count(movement_id) > 1})
    if duplicates:
        blockers.append(f"Hay movimientos repetidos en el cierre: {', '.join(duplicates)}")

    for item in pending:
        if not item.get("movement_id"):
            blockers.append("Hay movimientos antiguos sin ID único; revísalos antes de cerrar.")
            break
        if float(item.get("amount", 0.0)) <= 0:
            blockers.append(f"Movimiento {item.get('movement_id', '')} tiene monto igual o menor que cero.")

    return blockers


def render_financial_control() -> None:
    with st.container(border=True):
        render_page_header("Panel financiero y cierres", "Analiza resultados y realiza cierres seguros por método de pago.")
        st.caption("Cada movimiento se incluye una sola vez y la conciliación debe estar correcta antes de cerrar.")

    cash = _rows("cash_movements")
    sales = _rows("sales_registry")
    purchases = _rows("purchases_registry")
    closings = _rows("cash_closings")

    today = date.today()
    period = st.columns(2)
    start_date = period[0].date_input("Desde", value=today.replace(day=1), key="fc_start")
    end_date = period[1].date_input("Hasta", value=today, key="fc_end")
    if start_date > end_date:
        st.error("La fecha inicial no puede ser posterior a la fecha final.")
        return

    period_cash = _filter_by_period(cash, start_date, end_date)
    period_sales = _filter_by_period(sales, start_date, end_date)
    period_purchases = _filter_by_period(purchases, start_date, end_date)
    income, expenses, balance = _cash_totals(period_cash)
    billed, estimated_costs, estimated_profit = _sales_totals(period_sales)
    purchases_total = sum(float(item.get("total", 0.0)) for item in period_purchases if item.get("receipt_status") != "Cancelada")

    first = st.columns(4)
    first[0].metric("Ingresos", format_money(income))
    first[1].metric("Egresos", format_money(expenses))
    first[2].metric("Saldo del período", format_money(balance))
    first[3].metric("Compras", format_money(purchases_total))
    second = st.columns(3)
    second[0].metric("Ventas facturadas", format_money(billed))
    second[1].metric("Costos estimados", format_money(estimated_costs))
    second[2].metric("Utilidad estimada", format_money(estimated_profit))

    st.download_button("Descargar reporte financiero CSV", data=_build_financial_csv(period_cash, period_sales, period_purchases, start_date, end_date), file_name=f"copymary_finanzas_{start_date}_{end_date}.csv", mime="text/csv", use_container_width=True)

    st.divider()
    st.subheader("Saldos por método")
    method_columns = st.columns(len(METHODS))
    for column, method in zip(method_columns, METHODS, strict=True):
        method_items = [item for item in period_cash if _method(item) == method]
        _, _, method_balance = _cash_totals(method_items)
        column.metric(method, format_money(method_balance))

    st.divider()
    st.subheader("Registrar cierre")
    scope_label = st.radio("Alcance", ("Solo efectivo", "Todos los métodos"), horizontal=True)
    scope = ("Efectivo",) if scope_label == "Solo efectivo" else METHODS
    expected, pending = _expected_by_method(cash, closings, scope)
    blockers = _closing_blockers(cash, pending)

    if blockers:
        st.error("El cierre está bloqueado hasta corregir la conciliación financiera.")
        for blocker in blockers[:8]:
            st.warning(blocker)
    else:
        st.success("Conciliación correcta: el cierre puede registrarse.")

    with st.form("cash_closing_by_method"):
        top = st.columns(3)
        closing_date = top[0].date_input("Fecha del cierre", value=today)
        responsible = top[1].text_input("Responsable", max_chars=80)
        notes = top[2].text_input("Observaciones", max_chars=180)
        counted: dict[str, float] = {}
        for method in scope:
            counted[method] = st.number_input(f"Contado o conciliado · {method}", min_value=0.0, value=max(float(expected.get(method, 0.0)), 0.0), step=1.0, key=f"counted_{method}")
        submitted = st.form_submit_button("Guardar cierre", type="primary", use_container_width=True, disabled=bool(blockers))

    if submitted:
        differences = {method: float(counted[method]) - float(expected.get(method, 0.0)) for method in scope}
        closings.append({
            "closing_id": uuid4().hex[:10],
            "created_at_utc": _now(),
            "closing_date": closing_date.isoformat(),
            "responsible": responsible.strip(),
            "notes": notes.strip(),
            "method_scope": scope_label,
            "methods": list(scope),
            "expected_by_method": expected,
            "counted_by_method": counted,
            "difference_by_method": differences,
            "expected_balance": sum(expected.values()),
            "counted_cash": sum(counted.values()),
            "difference": sum(differences.values()),
            "movement_ids": [str(item.get("_closing_movement_id", "")) for item in pending],
            "movement_count": len(pending),
            "reconciliation_status": "Conciliado",
        })
        st.session_state["cash_closings"] = closings
        st.success("Cierre conciliado guardado sin repetir movimientos anteriores.")
        st.rerun()

    pending_total = sum(float(item.get("amount", 0.0)) * (1 if item.get("movement_type") == "Ingreso" else -1) for item in pending)
    info = st.columns(3)
    info[0].metric("Movimientos pendientes", str(len(pending)))
    info[1].metric("Apertura heredada", format_money(sum(_opening_by_method(closings).get(method, 0.0) for method in scope)))
    info[2].metric("Variación pendiente", format_money(pending_total))

    st.divider()
    st.subheader("Historial de cierres")
    if not closings:
        st.info("Todavía no hay cierres registrados.")
    for closing in reversed(closings):
        with st.container(border=True):
            st.markdown(f"### Cierre {closing.get('closing_date', '')}")
            st.caption(f"ID {closing.get('closing_id', '')} · Responsable: {closing.get('responsible') or 'No indicado'} · Movimientos: {closing.get('movement_count', 'Sin detalle')}")
            columns = st.columns(4)
            columns[0].metric("Esperado", format_money(float(closing.get("expected_balance", 0.0))))
            columns[1].metric("Contado", format_money(float(closing.get("counted_cash", 0.0))))
            columns[2].metric("Diferencia", format_money(float(closing.get("difference", 0.0))))
            columns[3].metric("Alcance", str(closing.get("method_scope", "Cierre anterior")))
            expected_detail = closing.get("expected_by_method", {})
            counted_detail = closing.get("counted_by_method", {})
            if isinstance(expected_detail, dict) and expected_detail:
                for method in closing.get("methods", expected_detail.keys()):
                    st.write(f"**{method}:** esperado {format_money(float(expected_detail.get(method, 0.0)))} · contado {format_money(float(counted_detail.get(method, 0.0)))}")

    render_info_card("Conciliación", "El cierre se bloquea cuando existen diferencias entre pagos, reversos y movimientos de Caja.", "CIERRE SEGURO")
