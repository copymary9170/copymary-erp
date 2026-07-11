"""Gobierno adicional para conciliación financiera."""

from collections import Counter, defaultdict
from datetime import date, datetime
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, financial_reconciliation as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("financial_reconciliation_rules", "Reglas de conciliación financiera"),
        ("financial_manual_matches", "Conciliaciones manuales financieras"),
        ("financial_reconciliation_reviews", "Revisiones gerenciales de conciliación"),
        ("financial_bank_duplicates", "Duplicados bancarios detectados"),
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


def _dt(value) -> datetime | None:
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


def _rules() -> dict:
    defaults = {
        "amount_tolerance": 0.01,
        "day_tolerance": 2,
        "stale_days": 7,
        "large_difference": 20.0,
        "review_required_amount": 50.0,
    }
    rows = _rows("financial_reconciliation_rules")
    if rows:
        defaults.update(rows[0])
    return defaults


def _expected_entries() -> list[dict]:
    return base._expected_entries()


def _entry_key(row: dict) -> str:
    return base._entry_key(row)


def _bank_key(row: dict) -> str:
    return base._bank_key(row)


def _matched_keys(matches: list[dict]) -> tuple[set[str], set[str]]:
    return base._matched_keys(matches)


def _pending(expected: list[dict], bank_lines: list[dict], matches: list[dict]) -> tuple[list[dict], list[dict]]:
    matched_expected, matched_bank = _matched_keys(matches)
    return (
        [row for row in expected if _entry_key(row) not in matched_expected],
        [row for row in bank_lines if _bank_key(row) not in matched_bank],
    )


def _age_days(value) -> int:
    created = _dt(value)
    if created is None:
        return 999
    return max((datetime.now() - created).days, 0)


def _duplicate_bank_lines(bank_lines: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, float, str], list[dict]] = defaultdict(list)
    for line in bank_lines:
        key = (str(line.get("date", "")), round(_num(line.get("amount")), 2), str(line.get("reference", "")).strip())
        grouped[key].append(line)
    duplicates: list[dict] = []
    for key, lines in grouped.items():
        if len(lines) > 1:
            duplicates.append({
                "duplicate_id": f"DUP-{uuid4().hex[:8].upper()}",
                "date": key[0],
                "amount": key[1],
                "reference": key[2],
                "count": len(lines),
                "bank_line_ids": ", ".join(str(line.get("bank_line_id", "")) for line in lines),
                "created_at_utc": _now(),
            })
    return duplicates


def _export_pending(expected: list[dict], bank_lines: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Tipo", "Origen", "ID", "Fecha", "Descripción", "Monto", "Método", "Referencia", "Antigüedad"])
    for row in expected:
        writer.writerow(["ERP", row.get("source", ""), row.get("source_id", ""), row.get("date", ""), row.get("description", ""), row.get("amount", 0), row.get("method", ""), row.get("reference", ""), _age_days(row.get("created_at_utc", row.get("date")))])
    for row in bank_lines:
        writer.writerow(["Banco", row.get("account", "Banco"), row.get("bank_line_id", ""), row.get("date", ""), row.get("description", ""), row.get("amount", 0), "Banco", row.get("reference", ""), _age_days(row.get("date"))])
    return buffer.getvalue().encode("utf-8-sig")


def _append_manual_match(expected_row: dict, bank_row: dict, responsible: str, note: str) -> None:
    candidate = {
        "expected_key": _entry_key(expected_row),
        "bank_line_id": _bank_key(bank_row),
        "expected": expected_row,
        "bank_line": bank_row,
        "score": 0,
    }
    base._append_match(candidate, responsible, note, "Manual")
    manual = _rows("financial_manual_matches")
    manual.append({
        "manual_match_id": f"MRC-{uuid4().hex[:8].upper()}",
        "expected_key": _entry_key(expected_row),
        "bank_line_id": _bank_key(bank_row),
        "difference": _num(bank_row.get("amount")) - _num(expected_row.get("amount")),
        "responsible": responsible.strip() or "Sin asignar",
        "note": note.strip(),
        "created_at_utc": _now(),
    })
    _save("financial_manual_matches", manual)


def render_financial_reconciliation_control() -> None:
    render_page_header(
        "Conciliación financiera",
        "Agrega reglas, conciliación manual, antigüedad de pendientes, duplicados y revisión gerencial.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_financial_reconciliation()
    finally:
        base.render_page_header = original_header

    expected = _expected_entries()
    bank_lines = _rows("financial_bank_lines")
    matches = _rows("financial_reconciliation_matches")
    cases = _rows("financial_reconciliation_cases")
    reviews = _rows("financial_reconciliation_reviews")
    rules = _rules()
    pending_expected, pending_bank = _pending(expected, bank_lines, matches)
    stale_expected = [row for row in pending_expected if _age_days(row.get("created_at_utc", row.get("date"))) >= int(_num(rules.get("stale_days"), 7))]
    stale_bank = [row for row in pending_bank if _age_days(row.get("date")) >= int(_num(rules.get("stale_days"), 7))]
    duplicate_bank = _duplicate_bank_lines(bank_lines)
    open_cases = [row for row in cases if row.get("status") != "Resuelto"]
    total_pending_value = sum(abs(_num(row.get("amount"))) for row in pending_expected) + sum(abs(_num(row.get("amount"))) for row in pending_bank)

    st.divider()
    st.markdown("### Gobierno de conciliación")
    metrics = st.columns(5)
    metrics[0].metric("Pendientes ERP", str(len(pending_expected)))
    metrics[1].metric("Pendientes banco", str(len(pending_bank)))
    metrics[2].metric("Vencidos", str(len(stale_expected) + len(stale_bank)))
    metrics[3].metric("Duplicados banco", str(len(duplicate_bank)))
    metrics[4].metric("Valor pendiente", format_money(total_pending_value, get_currency()))

    if duplicate_bank:
        st.warning(f"Hay {len(duplicate_bank)} posible(s) duplicado(s) bancario(s).")
    if stale_expected or stale_bank:
        st.error("Hay partidas pendientes con antigüedad superior a la regla definida.")

    manual_tab, aging_tab, duplicate_tab, rules_tab, review_tab = st.tabs(("Manual", "Antigüedad", "Duplicados", "Reglas", "Revisión"))

    with manual_tab:
        st.caption("Usa conciliación manual cuando el banco y el ERP coinciden por criterio humano, aunque no pasen el score automático.")
        if not pending_expected or not pending_bank:
            st.info("No hay suficientes pendientes para conciliar manualmente.")
        else:
            expected_options = {f"{row.get('source')} · {row.get('description')} · {format_money(_num(row.get('amount')), get_currency())} · {row.get('date')}": row for row in pending_expected[:200]}
            bank_options = {f"{row.get('description')} · {format_money(_num(row.get('amount')), get_currency())} · {row.get('date')} · {row.get('reference')}": row for row in pending_bank[:200]}
            with st.form("manual_financial_match_form", clear_on_submit=True):
                selected_expected = st.selectbox("Partida ERP", tuple(expected_options.keys()))
                selected_bank = st.selectbox("Partida banco", tuple(bank_options.keys()))
                responsible = st.text_input("Responsable")
                note = st.text_area("Justificación", max_chars=500)
                confirmed = st.checkbox("Confirmo que estas partidas corresponden entre sí")
                submitted = st.form_submit_button("Conciliar manualmente", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not note.strip() or not confirmed:
                    st.error("Responsable, justificación y confirmación son obligatorios.")
                else:
                    _append_manual_match(expected_options[selected_expected], bank_options[selected_bank], responsible, note)
                    st.rerun()

    with aging_tab:
        st.download_button(
            "Descargar pendientes CSV",
            data=_export_pending(pending_expected, pending_bank),
            file_name=f"pendientes_conciliacion_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not pending_expected and not pending_bank,
        )
        st.markdown("#### Pendientes vencidos ERP")
        for row in stale_expected[:100]:
            st.warning(f"{row.get('source')} · {row.get('description')} · {format_money(_num(row.get('amount')), get_currency())} · {_age_days(row.get('created_at_utc', row.get('date')))} días")
        st.markdown("#### Pendientes vencidos banco")
        for row in stale_bank[:100]:
            st.warning(f"{row.get('description')} · {format_money(_num(row.get('amount')), get_currency())} · {_age_days(row.get('date'))} días")

    with duplicate_tab:
        saved_duplicates = _rows("financial_bank_duplicates")
        if not duplicate_bank:
            st.success("No se detectan duplicados bancarios por fecha, monto y referencia.")
        for duplicate in duplicate_bank:
            with st.container(border=True):
                st.markdown(f"**{duplicate.get('date')} · {format_money(_num(duplicate.get('amount')), get_currency())} · {duplicate.get('reference') or 'Sin referencia'}**")
                st.caption(f"{duplicate.get('count')} líneas: {duplicate.get('bank_line_ids')}")
        if duplicate_bank and st.button("Guardar duplicados detectados", use_container_width=True):
            saved_duplicates.extend(duplicate_bank)
            _save("financial_bank_duplicates", saved_duplicates)
            st.rerun()

    with rules_tab:
        with st.form("financial_reconciliation_rules_form"):
            cols = st.columns(5)
            amount_tolerance = cols[0].number_input("Tolerancia monto", min_value=0.0, value=_num(rules.get("amount_tolerance"), 0.01), step=0.01)
            day_tolerance = cols[1].number_input("Tolerancia días", min_value=0, value=int(_num(rules.get("day_tolerance"), 2)), step=1)
            stale_days = cols[2].number_input("Pendiente vencido", min_value=1, value=int(_num(rules.get("stale_days"), 7)), step=1)
            large_difference = cols[3].number_input("Diferencia alta", min_value=0.0, value=_num(rules.get("large_difference"), 20.0), step=1.0)
            review_amount = cols[4].number_input("Revisión desde", min_value=0.0, value=_num(rules.get("review_required_amount"), 50.0), step=1.0)
            submitted = st.form_submit_button("Guardar reglas", type="primary", use_container_width=True)
        if submitted:
            _save("financial_reconciliation_rules", [{
                "amount_tolerance": float(amount_tolerance),
                "day_tolerance": int(day_tolerance),
                "stale_days": int(stale_days),
                "large_difference": float(large_difference),
                "review_required_amount": float(review_amount),
                "updated_at_utc": _now(),
            }])
            st.rerun()

    with review_tab:
        needs_review = abs(sum(_num(row.get("difference")) for row in matches)) >= _num(rules.get("review_required_amount"), 50.0) or bool(open_cases)
        if needs_review:
            st.warning("La conciliación requiere revisión gerencial por casos abiertos o diferencias acumuladas.")
        else:
            st.success("No hay señales fuertes que obliguen revisión gerencial.")
        with st.form("financial_reconciliation_review_form", clear_on_submit=True):
            reviewer = st.text_input("Revisado por")
            status = st.selectbox("Resultado", ("Aprobado", "Aprobado con observaciones", "Requiere corrección"))
            note = st.text_area("Conclusión", max_chars=700)
            submitted = st.form_submit_button("Guardar revisión", type="primary", use_container_width=True)
        if submitted:
            if not reviewer.strip() or not note.strip():
                st.error("Revisor y conclusión son obligatorios.")
            else:
                reviews.append({
                    "review_id": f"FRV-{uuid4().hex[:8].upper()}",
                    "expected_pending": len(pending_expected),
                    "bank_pending": len(pending_bank),
                    "open_cases": len(open_cases),
                    "total_pending_value": total_pending_value,
                    "status": status,
                    "reviewer": reviewer.strip(),
                    "note": note.strip(),
                    "created_at_utc": _now(),
                })
                _save("financial_reconciliation_reviews", reviews)
                st.rerun()
        for review in reversed(reviews[-50:]):
            st.write(f"**{review.get('review_id', '')} · {review.get('status', '')}** · {review.get('reviewer', '')} · pendientes {review.get('expected_pending', 0)}/{review.get('bank_pending', 0)}")

    render_info_card(
        "Conciliación supervisada",
        "Las partidas pendientes se pueden medir por antigüedad, conciliar manualmente, revisar por reglas y aprobar con evidencia.",
        "GOBIERNO FINANCIERO",
    )


app_shell.FUNCTIONAL_MODULES["Conciliación financiera"] = render_financial_reconciliation_control
