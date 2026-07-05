"""Conciliación entre pagos registrados y movimientos de Caja."""

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _cash_by_reference(cash: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for movement in cash:
        reference = str(movement.get("reference", ""))
        if reference:
            grouped.setdefault(reference, []).append(movement)
    return grouped


def _expected_records() -> list[dict]:
    expected: list[dict] = []
    for payment in _rows("payment_records"):
        payment_id = str(payment.get("payment_id", ""))
        if not payment_id:
            continue
        expected.append({
            "kind": "Cobro de cliente",
            "payment_id": payment_id,
            "amount": float(payment.get("amount", 0.0)),
            "payment_method": str(payment.get("payment_method", "Otro")),
            "movement_type": "Ingreso",
            "reversed": bool(payment.get("reversed")),
            "reversal_type": "Egreso",
        })
    for payment in _rows("supplier_payment_records"):
        payment_id = str(payment.get("payment_id", ""))
        if not payment_id:
            continue
        expected.append({
            "kind": "Pago a proveedor",
            "payment_id": payment_id,
            "amount": float(payment.get("amount", 0.0)),
            "payment_method": str(payment.get("payment_method", "Otro")),
            "movement_type": "Egreso",
            "reversed": bool(payment.get("reversed")),
            "reversal_type": "Ingreso",
        })
    for payment in _rows("team_payments"):
        payment_id = str(payment.get("payment_id", ""))
        if not payment_id:
            continue
        expected.append({
            "kind": "Pago al equipo",
            "payment_id": payment_id,
            "amount": float(payment.get("amount", 0.0)),
            "payment_method": str(payment.get("payment_method", "Otro")),
            "movement_type": "Egreso",
            "reversed": bool(payment.get("reversed")),
            "reversal_type": "Ingreso",
        })
    return expected


def _check_record(record: dict, cash_map: dict[str, list[dict]]) -> list[str]:
    issues: list[str] = []
    payment_id = str(record.get("payment_id", ""))
    amount = float(record.get("amount", 0.0))
    method = str(record.get("payment_method", "Otro"))
    original = cash_map.get(payment_id, [])

    if not original:
        issues.append("No tiene movimiento original en Caja.")
    else:
        if len(original) > 1:
            issues.append(f"Tiene {len(original)} movimientos originales en Caja.")
        matching_type = [item for item in original if item.get("movement_type") == record.get("movement_type")]
        if not matching_type:
            issues.append(f"El movimiento original no es de tipo {record.get('movement_type')}.")
        if not any(abs(float(item.get("amount", 0.0)) - amount) <= 0.0001 for item in original):
            issues.append("El monto del pago no coincide con Caja.")
        if not any(str(item.get("payment_method", "Otro")) == method for item in original):
            issues.append("El método de pago no coincide con Caja.")

    reversal_reference = f"REV-{payment_id}"
    reversals = cash_map.get(reversal_reference, [])
    if record.get("reversed"):
        if not reversals:
            issues.append("Está marcado como revertido pero no tiene movimiento contrario en Caja.")
        else:
            if len(reversals) > 1:
                issues.append(f"Tiene {len(reversals)} movimientos de reverso en Caja.")
            if not any(item.get("movement_type") == record.get("reversal_type") for item in reversals):
                issues.append(f"El reverso no es de tipo {record.get('reversal_type')}.")
            if not any(abs(float(item.get("amount", 0.0)) - amount) <= 0.0001 for item in reversals):
                issues.append("El monto del reverso no coincide con el pago.")
    elif reversals:
        issues.append("Tiene movimiento de reverso, pero el pago no está marcado como revertido.")

    return issues


def render_financial_reconciliation() -> None:
    with st.container(border=True):
        render_page_header(
            "Conciliación financiera",
            "Compara pagos, abonos y reversos contra los movimientos reales de Caja.",
        )
        st.caption("La revisión no modifica información; señala diferencias antes del cierre.")

    cash = _rows("cash_movements")
    cash_map = _cash_by_reference(cash)
    expected = _expected_records()
    findings: list[tuple[dict, list[str]]] = []

    for record in expected:
        issues = _check_record(record, cash_map)
        if issues:
            findings.append((record, issues))

    payment_references = {str(item.get("payment_id", "")) for item in expected}
    orphan_cash = [
        item
        for item in cash
        if str(item.get("reference", ""))
        and str(item.get("reference", "")) not in payment_references
        and not str(item.get("reference", "")).startswith("REV-")
        and item.get("category") in {
            "Cobro de venta",
            "Pago a proveedor",
            "Pago al personal",
            "Reverso de cobro",
            "Reverso de pago a proveedor",
            "Reverso de pago al personal",
        }
    ]

    metrics = st.columns(4)
    metrics[0].metric("Pagos revisados", str(len(expected)))
    metrics[1].metric("Con diferencias", str(len(findings)))
    metrics[2].metric("Movimientos huérfanos", str(len(orphan_cash)))
    metrics[3].metric("Estado", "Conciliado" if not findings and not orphan_cash else "Revisar")

    if not findings and not orphan_cash:
        st.success("Los pagos y reversos coinciden con Caja.")
    else:
        for record, issues in findings:
            with st.container(border=True):
                columns = st.columns([3, 1])
                columns[0].markdown(f"### {record.get('kind', 'Pago')} · {record.get('payment_id', '')}")
                columns[0].caption(str(record.get("payment_method", "Otro")))
                columns[1].metric("Monto", format_money(float(record.get("amount", 0.0))))
                for issue in issues:
                    st.warning(issue)

        if orphan_cash:
            st.subheader("Movimientos de Caja sin registro relacionado")
            for movement in orphan_cash:
                st.write(
                    f"- {movement.get('category', '')} · Ref. {movement.get('reference', '')} · "
                    f"{format_money(float(movement.get('amount', 0.0)))}"
                )

    render_info_card(
        "Uso recomendado",
        "Realiza esta revisión antes de guardar un cierre de caja o restaurar un respaldo.",
        "CONTROL FINANCIERO",
    )
