"""Historial de comisiones con trazabilidad, filtros y auditoría."""

from collections import defaultdict
from datetime import date
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("commission_history_reviews", "Revisiones del historial de comisiones"),
        ("commission_history_exports", "Exportaciones del historial de comisiones"),
        ("commission_history_flags", "Marcas del historial de comisiones"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _period(value: str) -> str:
    return str(value or "")[:7] or "Sin fecha"


def _member_name(member_id: str, members: list[dict]) -> str:
    for member in members:
        if str(member.get("member_id", "")) == str(member_id):
            return str(member.get("name", "Colaborador"))
    return "Colaborador"


def _assignment_commission(item: dict) -> float:
    value = _num(item.get("commission_value_snapshot"))
    if item.get("commission_mode_snapshot") == "Monto por venta":
        return value
    return _num(item.get("sale_total_snapshot")) * value / 100.0


def _history_rows() -> list[dict]:
    members = _rows("team_members")
    sales = {str(row.get("sale_id", "")): row for row in _rows("sales_registry")}
    output: list[dict] = []

    for item in _rows("commission_assignments"):
        sale = sales.get(str(item.get("sale_id", "")), {})
        created = str(sale.get("created_at_utc", item.get("created_at_utc", "")))
        output.append({
            "id": str(item.get("assignment_id", uuid4().hex[:8])),
            "kind": "Comisión generada",
            "period": _period(created),
            "date": created[:10],
            "member_id": str(item.get("member_id", "")),
            "member": _member_name(str(item.get("member_id", "")), members),
            "amount": _assignment_commission(item),
            "source": str(item.get("sale_description_snapshot", sale.get("description", "Venta"))),
            "reference": str(item.get("sale_id", "")),
            "status": "Activa" if item.get("active", True) else "Anulada",
            "notes": str(item.get("commission_mode_snapshot", "")),
        })

    for payment in _rows("team_payments"):
        created = str(payment.get("payment_date", payment.get("created_at_utc", "")))
        output.append({
            "id": str(payment.get("payment_id", uuid4().hex[:8])),
            "kind": "Pago de comisión",
            "period": _period(created),
            "date": created[:10],
            "member_id": str(payment.get("member_id", "")),
            "member": _member_name(str(payment.get("member_id", "")), members),
            "amount": -_num(payment.get("amount")),
            "source": str(payment.get("payment_method", "")),
            "reference": str(payment.get("reference", "")),
            "status": "Reversado" if payment.get("reversed") else "Pagado",
            "notes": "Salida de comisión",
        })

    for key, kind, amount_key in (("commission_receipts", "Recibo emitido", "net"), ("commission_advances", "Anticipo", "amount"), ("commission_adjustments", "Ajuste / penalización", "amount")):
        for row in _rows(key):
            created = str(row.get("created_at_utc", ""))
            amount = _num(row.get(amount_key, row.get("net_pending", 0)))
            if kind in {"Anticipo", "Ajuste / penalización"}:
                amount = -amount
            output.append({
                "id": str(row.get("receipt_id", row.get("advance_id", row.get("adjustment_id", uuid4().hex[:8])))),
                "kind": kind,
                "period": str(row.get("period", _period(created))),
                "date": created[:10],
                "member_id": str(row.get("member_id", "")),
                "member": str(row.get("member_name", _member_name(str(row.get("member_id", "")), members))),
                "amount": amount,
                "source": kind,
                "reference": str(row.get("receipt_id", row.get("advance_id", row.get("adjustment_id", "")))),
                "status": str(row.get("status", "Activo")),
                "notes": str(row.get("reason", row.get("note", ""))),
            })

    return sorted(output, key=lambda row: (row.get("period", ""), row.get("date", ""), row.get("kind", "")), reverse=True)


def _export(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Periodo", "Fecha", "Tipo", "Colaborador", "Monto", "Origen", "Referencia", "Estado", "Notas"])
    for row in rows:
        writer.writerow([row.get("period", ""), row.get("date", ""), row.get("kind", ""), row.get("member", ""), row.get("amount", 0), row.get("source", ""), row.get("reference", ""), row.get("status", ""), row.get("notes", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_commission_history_plus() -> None:
    render_page_header("Historial de comisiones", "Consulta generación, pagos, recibos, anticipos, ajustes y revisiones por periodo.")
    rows = _history_rows()
    reviews = _rows("commission_history_reviews")
    flags = _rows("commission_history_flags")
    exports = _rows("commission_history_exports")
    periods = sorted({str(row.get("period", "Sin fecha")) for row in rows}, reverse=True)
    members = sorted({str(row.get("member", "Colaborador")) for row in rows})

    metrics = st.columns(5)
    metrics[0].metric("Movimientos", str(len(rows)))
    metrics[1].metric("Generado", format_money(sum(_num(row.get("amount")) for row in rows if row.get("kind") == "Comisión generada"), get_currency()))
    metrics[2].metric("Pagado", format_money(sum(abs(_num(row.get("amount"))) for row in rows if row.get("kind") == "Pago de comisión"), get_currency()))
    metrics[3].metric("Ajustes", format_money(sum(abs(_num(row.get("amount"))) for row in rows if row.get("kind") in {"Anticipo", "Ajuste / penalización"}), get_currency()))
    metrics[4].metric("Marcas", str(len(flags)))

    history_tab, summary_tab, review_tab, flags_tab = st.tabs(("Historial", "Resumen", "Revisión", "Marcas"))

    with history_tab:
        filters = st.columns(4)
        period_filter = filters[0].selectbox("Periodo", ("Todos", *periods))
        member_filter = filters[1].selectbox("Colaborador", ("Todos", *members))
        type_filter = filters[2].selectbox("Tipo", ("Todos", "Comisión generada", "Pago de comisión", "Recibo emitido", "Anticipo", "Ajuste / penalización"))
        query = filters[3].text_input("Buscar").strip().casefold()
        visible = []
        for row in rows:
            text = " ".join(str(row.get(field, "")) for field in ("source", "reference", "notes", "status")).casefold()
            if period_filter != "Todos" and row.get("period") != period_filter:
                continue
            if member_filter != "Todos" and row.get("member") != member_filter:
                continue
            if type_filter != "Todos" and row.get("kind") != type_filter:
                continue
            if query and query not in text:
                continue
            visible.append(row)
        if st.download_button("Descargar historial CSV", data=_export(visible), file_name=f"historial_comisiones_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not visible):
            exports.append({"export_id": f"CHE-{uuid4().hex[:8].upper()}", "rows": len(visible), "period": period_filter, "member": member_filter, "created_at_utc": _now()})
            _save("commission_history_exports", exports)
        for row in visible[:200]:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row.get('kind', '')}: {row.get('member', '')}**")
                cols[0].caption(f"{row.get('date', '')} · {row.get('source', '')} · Ref. {row.get('reference', '')}")
                cols[1].metric("Monto", format_money(_num(row.get("amount")), get_currency()))
                cols[2].metric("Periodo", str(row.get("period", "")))
                cols[3].metric("Estado", str(row.get("status", "")))

    with summary_tab:
        grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"generated": 0.0, "paid": 0.0, "adjustments": 0.0, "balance": 0.0})
        latest = periods[0] if periods else ""
        for row in [item for item in rows if not latest or item.get("period") == latest]:
            name = str(row.get("member", "Colaborador"))
            amount = _num(row.get("amount"))
            if row.get("kind") == "Comisión generada":
                grouped[name]["generated"] += amount
            elif row.get("kind") == "Pago de comisión":
                grouped[name]["paid"] += abs(amount)
            elif row.get("kind") in {"Anticipo", "Ajuste / penalización"}:
                grouped[name]["adjustments"] += abs(amount)
            grouped[name]["balance"] += amount
        st.caption(f"Resumen del periodo {latest or 'actual'}.")
        for name, data in grouped.items():
            cols = st.columns([3, 1, 1, 1, 1])
            cols[0].markdown(f"**{name}**")
            cols[1].metric("Generado", format_money(data["generated"], get_currency()))
            cols[2].metric("Pagado", format_money(data["paid"], get_currency()))
            cols[3].metric("Ajustes", format_money(data["adjustments"], get_currency()))
            cols[4].metric("Saldo", format_money(data["balance"], get_currency()))

    with review_tab:
        with st.form("commission_history_review_form", clear_on_submit=True):
            reviewer = st.text_input("Revisado por")
            result = st.selectbox("Resultado", ("Correcto", "Requiere ajuste", "Pendiente por pagar", "Diferencia detectada"))
            note = st.text_area("Conclusión", max_chars=700)
            submitted = st.form_submit_button("Guardar revisión", type="primary", use_container_width=True)
        if submitted:
            if not reviewer.strip() or not note.strip():
                st.error("Revisor y conclusión son obligatorios.")
            else:
                reviews.append({"review_id": f"CHR-{uuid4().hex[:8].upper()}", "period": periods[0] if periods else _period(date.today().isoformat()), "result": result, "reviewer": reviewer.strip(), "note": note.strip(), "movement_count": len(rows), "created_at_utc": _now()})
                _save("commission_history_reviews", reviews)
                st.rerun()
        for review in reversed(reviews[-50:]):
            st.write(f"**{review.get('review_id', '')} · {review.get('period', '')} · {review.get('result', '')}** — {review.get('reviewer', '')}: {review.get('note', '')}")

    with flags_tab:
        if rows:
            options = {f"{row.get('kind')} · {row.get('member')} · {row.get('reference')} · {format_money(_num(row.get('amount')), get_currency())}": row for row in rows[:300]}
            with st.form("commission_history_flag_form", clear_on_submit=True):
                selected = st.selectbox("Movimiento", tuple(options.keys()))
                flag_type = st.selectbox("Marca", ("Revisar", "Posible doble pago", "Falta soporte", "Monto inusual", "Corregido"))
                responsible = st.text_input("Responsable")
                note = st.text_area("Nota", max_chars=500)
                submitted = st.form_submit_button("Guardar marca", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not note.strip():
                    st.error("Responsable y nota son obligatorios.")
                else:
                    row = options[selected]
                    flags.append({"flag_id": f"CHF-{uuid4().hex[:8].upper()}", "history_id": row.get("id", ""), "flag_type": flag_type, "responsible": responsible.strip(), "note": note.strip(), "status": "Abierta" if flag_type != "Corregido" else "Cerrada", "created_at_utc": _now()})
                    _save("commission_history_flags", flags)
                    st.rerun()
        for flag in reversed(flags[-100:]):
            st.write(f"**{flag.get('flag_type', '')} · {flag.get('status', '')}** — {flag.get('responsible', '')}: {flag.get('note', '')}")

    render_info_card("Trazabilidad completa", "El historial consolida generación, pago, recibos, anticipos y ajustes para revisar comisiones.", "HISTORIAL")


app_shell.FUNCTIONAL_MODULES["Historial de comisiones"] = render_commission_history_plus
