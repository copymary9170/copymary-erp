"""Conciliación financiera entre caja, ventas, comprobantes y bancos."""

from datetime import date, datetime
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
        ("financial_bank_lines", "Movimientos bancarios para conciliación"),
        ("financial_reconciliation_matches", "Partidas conciliadas"),
        ("financial_reconciliation_cases", "Casos de diferencias financieras"),
        ("financial_reconciliation_snapshots", "Cortes de conciliación financiera"),
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


def _signed_cash(row: dict) -> float:
    amount = _num(row.get("amount"))
    return amount if row.get("movement_type") == "Ingreso" else -amount


def _expected_entries() -> list[dict]:
    entries: list[dict] = []
    for movement in _rows("cash_movements"):
        entries.append({
            "source": "Caja",
            "source_id": str(movement.get("movement_id", "")),
            "date": str(movement.get("created_at_utc", ""))[:10],
            "created_at_utc": movement.get("created_at_utc", ""),
            "description": f"{movement.get('movement_type', '')}: {movement.get('category', '')}",
            "amount": _signed_cash(movement),
            "method": str(movement.get("payment_method", "Otro")),
            "reference": str(movement.get("reference", "")),
            "notes": str(movement.get("notes", "")),
        })
    for sale in _rows("sales_registry"):
        if sale.get("payment_status") in {"Pagado", "Abono"}:
            entries.append({
                "source": "Venta",
                "source_id": str(sale.get("sale_id", "")),
                "date": str(sale.get("created_at_utc", ""))[:10],
                "created_at_utc": sale.get("created_at_utc", ""),
                "description": str(sale.get("description", "Venta")),
                "amount": _num(sale.get("total")),
                "method": str(sale.get("payment_method", "Otro")),
                "reference": str(sale.get("sale_id", "")),
                "notes": str(sale.get("notes", "")),
            })
    for payment in _rows("payment_records"):
        entries.append({
            "source": "Cobro",
            "source_id": str(payment.get("payment_id", "")),
            "date": str(payment.get("created_at_utc", ""))[:10],
            "created_at_utc": payment.get("created_at_utc", ""),
            "description": "Cobro de cliente",
            "amount": _num(payment.get("amount")),
            "method": str(payment.get("payment_method", "Otro")),
            "reference": str(payment.get("payment_id", "")),
            "notes": str(payment.get("notes", "")),
        })
    for payment in _rows("supplier_payment_records"):
        entries.append({
            "source": "Pago proveedor",
            "source_id": str(payment.get("payment_id", "")),
            "date": str(payment.get("created_at_utc", ""))[:10],
            "created_at_utc": payment.get("created_at_utc", ""),
            "description": "Pago a proveedor",
            "amount": -_num(payment.get("amount")),
            "method": str(payment.get("payment_method", "Otro")),
            "reference": str(payment.get("payment_id", "")),
            "notes": str(payment.get("notes", "")),
        })
    return entries


def _bank_key(row: dict) -> str:
    return str(row.get("bank_line_id", ""))


def _entry_key(row: dict) -> str:
    return f"{row.get('source', '')}::{row.get('source_id', '')}"


def _matched_keys(matches: list[dict]) -> tuple[set[str], set[str]]:
    return (
        {str(row.get("expected_key", "")) for row in matches if row.get("status") == "Conciliado"},
        {str(row.get("bank_line_id", "")) for row in matches if row.get("status") == "Conciliado"},
    )


def _auto_candidates(expected: list[dict], bank_lines: list[dict], matches: list[dict], tolerance: float, days: int) -> list[dict]:
    matched_expected, matched_bank = _matched_keys(matches)
    candidates = []
    for entry in expected:
        key = _entry_key(entry)
        if key in matched_expected:
            continue
        entry_date = _dt(entry.get("created_at_utc", entry.get("date")))
        for line in bank_lines:
            line_id = _bank_key(line)
            if line_id in matched_bank:
                continue
            amount_diff = abs(_num(entry.get("amount")) - _num(line.get("amount")))
            bank_date = _dt(line.get("date"))
            date_diff = abs((bank_date.date() - entry_date.date()).days) if bank_date and entry_date else 999
            reference_hit = bool(str(entry.get("reference", "")).strip() and str(entry.get("reference", "")).strip() in str(line.get("reference", "")))
            if amount_diff <= tolerance and date_diff <= days:
                score = 100 - amount_diff - (date_diff * 5) + (15 if reference_hit else 0)
                candidates.append({
                    "expected_key": key,
                    "bank_line_id": line_id,
                    "expected": entry,
                    "bank_line": line,
                    "amount_difference": amount_diff,
                    "date_difference": date_diff,
                    "score": round(score, 2),
                    "reference_hit": reference_hit,
                })
    return sorted(candidates, key=lambda row: row.get("score", 0), reverse=True)


def _append_match(candidate: dict, responsible: str, note: str, mode: str = "Manual") -> None:
    rows = _rows("financial_reconciliation_matches")
    rows.append({
        "match_id": f"RCN-{uuid4().hex[:8].upper()}",
        "expected_key": str(candidate.get("expected_key", "")),
        "bank_line_id": str(candidate.get("bank_line_id", "")),
        "expected_amount": _num(candidate.get("expected", {}).get("amount")),
        "bank_amount": _num(candidate.get("bank_line", {}).get("amount")),
        "difference": _num(candidate.get("bank_line", {}).get("amount")) - _num(candidate.get("expected", {}).get("amount")),
        "score": _num(candidate.get("score")),
        "mode": mode,
        "responsible": responsible.strip() or "Sin asignar",
        "note": note.strip(),
        "status": "Conciliado",
        "created_at_utc": _now(),
    })
    _save("financial_reconciliation_matches", rows)


def _export_rows(rows: list[dict], headers: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(header, "") for header in headers])
    return buffer.getvalue().encode("utf-8-sig")


def _parse_bank_csv(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = file_bytes.decode("latin-1")
    sample = decoded.splitlines()[0] if decoded.splitlines() else ""
    delimiter = ";" if ";" in sample else ","
    reader = csv.DictReader(io.StringIO(decoded), delimiter=delimiter)
    fieldnames = reader.fieldnames or []
    required = {"fecha", "descripcion", "monto"}
    normalized = {name.strip().casefold(): name for name in fieldnames}
    missing = [name for name in required if name not in normalized]
    if missing:
        raise ValueError("El CSV debe tener columnas: fecha, descripcion y monto.")
    errors: list[str] = []
    rows: list[dict] = []
    for index, row in enumerate(reader, start=2):
        raw_date = str(row.get(normalized["fecha"], "")).strip()
        description = str(row.get(normalized["descripcion"], "")).strip()
        amount = _num(row.get(normalized["monto"]), 0.0)
        reference = str(row.get(normalized.get("referencia", ""), "")).strip() if "referencia" in normalized else ""
        account = str(row.get(normalized.get("cuenta", ""), "")).strip() if "cuenta" in normalized else "Banco"
        try:
            parsed_date = date.fromisoformat(raw_date[:10]).isoformat()
        except ValueError:
            errors.append(f"Fila {index}: fecha inválida.")
            parsed_date = raw_date
        if amount == 0:
            errors.append(f"Fila {index}: monto vacío o cero.")
        if not description:
            errors.append(f"Fila {index}: descripción vacía.")
        rows.append({
            "bank_line_id": f"BNK-{uuid4().hex[:8].upper()}",
            "date": parsed_date,
            "description": description or "Movimiento bancario",
            "amount": float(amount),
            "reference": reference,
            "account": account or "Banco",
            "status": "Pendiente",
            "imported_at_utc": _now(),
        })
    return rows, errors


def render_financial_reconciliation() -> None:
    render_page_header(
        "Conciliación financiera",
        "Cruza caja, ventas, cobros, pagos y movimientos bancarios para detectar diferencias antes del cierre.",
    )

    expected = _expected_entries()
    bank_lines = _rows("financial_bank_lines")
    matches = _rows("financial_reconciliation_matches")
    cases = _rows("financial_reconciliation_cases")
    snapshots = _rows("financial_reconciliation_snapshots")
    matched_expected, matched_bank = _matched_keys(matches)
    pending_expected = [row for row in expected if _entry_key(row) not in matched_expected]
    pending_bank = [row for row in bank_lines if _bank_key(row) not in matched_bank]
    expected_total = sum(_num(row.get("amount")) for row in expected)
    bank_total = sum(_num(row.get("amount")) for row in bank_lines)
    difference = bank_total - expected_total

    metrics = st.columns(5)
    metrics[0].metric("Esperado ERP", format_money(expected_total, get_currency()))
    metrics[1].metric("Banco importado", format_money(bank_total, get_currency()))
    metrics[2].metric("Diferencia", format_money(difference, get_currency()))
    metrics[3].metric("Conciliados", str(len(matches)))
    metrics[4].metric("Casos abiertos", str(sum(1 for row in cases if row.get("status") != "Resuelto")))

    if abs(difference) > 0.01:
        st.warning("La suma bancaria no coincide con el total esperado del ERP. Revisa pendientes y casos.")
    else:
        st.success("El total importado coincide con el esperado, sujeto a revisión de partidas.")

    import_tab, match_tab, pending_tab, cases_tab, snapshot_tab = st.tabs(("Importar banco", "Conciliar", "Pendientes", "Diferencias", "Cortes"))

    with import_tab:
        st.caption("Formato esperado: fecha, descripcion, monto. Opcional: referencia, cuenta.")
        uploaded = st.file_uploader("Archivo CSV bancario", type=("csv",), accept_multiple_files=False)
        if uploaded is not None and st.button("Validar e importar banco", type="primary", use_container_width=True):
            try:
                imported, errors = _parse_bank_csv(uploaded.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                for error in errors[:20]:
                    st.error(error)
                if not errors:
                    bank_lines.extend(imported)
                    _save("financial_bank_lines", bank_lines)
                    st.success(f"Se importaron {len(imported)} movimiento(s) bancario(s).")
                    st.rerun()
        st.download_button(
            "Descargar plantilla banco CSV",
            data=_export_rows([
                {"fecha": date.today().isoformat(), "descripcion": "Pago móvil cliente", "monto": "10.00", "referencia": "REF123", "cuenta": "Banco"}
            ], ["fecha", "descripcion", "monto", "referencia", "cuenta"]),
            file_name="plantilla_banco_conciliacion.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with match_tab:
        controls = st.columns(3)
        tolerance = controls[0].number_input("Tolerancia de monto", min_value=0.0, value=0.01, step=0.01)
        days = controls[1].number_input("Tolerancia días", min_value=0, value=2, step=1)
        responsible = controls[2].text_input("Responsable")
        note = st.text_input("Nota de conciliación")
        candidates = _auto_candidates(expected, bank_lines, matches, float(tolerance), int(days))
        if not candidates:
            st.info("No hay candidatos automáticos con los criterios actuales.")
        for candidate in candidates[:50]:
            entry = candidate.get("expected", {})
            bank = candidate.get("bank_line", {})
            with st.container(border=True):
                cols = st.columns([3, 3, 1])
                cols[0].markdown(f"**ERP:** {entry.get('description', '')}")
                cols[0].caption(f"{entry.get('source')} · {entry.get('date')} · {format_money(_num(entry.get('amount')), get_currency())}")
                cols[1].markdown(f"**Banco:** {bank.get('description', '')}")
                cols[1].caption(f"{bank.get('date')} · {bank.get('reference', '')} · {format_money(_num(bank.get('amount')), get_currency())}")
                cols[2].metric("Score", str(candidate.get("score", 0)))
                if st.button("Conciliar partida", key=f"match_{candidate.get('expected_key')}_{candidate.get('bank_line_id')}", use_container_width=True):
                    if not responsible.strip():
                        st.error("Indica responsable.")
                    else:
                        _append_match(candidate, responsible, note, "Automática asistida")
                        st.rerun()

    with pending_tab:
        st.markdown("#### Pendientes del ERP")
        for row in pending_expected[:100]:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{row.get('description', '')}**")
                cols[0].caption(f"{row.get('source')} · {row.get('date')} · {row.get('reference')}")
                cols[1].metric("Monto", format_money(_num(row.get("amount")), get_currency()))
                if cols[2].button("Abrir caso", key=f"case_expected_{_entry_key(row)}", use_container_width=True):
                    cases.append({
                        "case_id": f"FRC-{uuid4().hex[:8].upper()}",
                        "case_type": "ERP sin banco",
                        "source_key": _entry_key(row),
                        "amount": _num(row.get("amount")),
                        "description": str(row.get("description", "")),
                        "status": "Abierto",
                        "created_at_utc": _now(),
                    })
                    _save("financial_reconciliation_cases", cases)
                    st.rerun()
        st.markdown("#### Pendientes del banco")
        for row in pending_bank[:100]:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{row.get('description', '')}**")
                cols[0].caption(f"{row.get('date')} · {row.get('reference')} · {row.get('account')}")
                cols[1].metric("Monto", format_money(_num(row.get("amount")), get_currency()))
                if cols[2].button("Abrir caso", key=f"case_bank_{_bank_key(row)}", use_container_width=True):
                    cases.append({
                        "case_id": f"FRC-{uuid4().hex[:8].upper()}",
                        "case_type": "Banco sin ERP",
                        "bank_line_id": _bank_key(row),
                        "amount": _num(row.get("amount")),
                        "description": str(row.get("description", "")),
                        "status": "Abierto",
                        "created_at_utc": _now(),
                    })
                    _save("financial_reconciliation_cases", cases)
                    st.rerun()

    with cases_tab:
        st.download_button(
            "Descargar casos CSV",
            data=_export_rows(cases, ["case_id", "case_type", "description", "amount", "status", "responsible", "resolution", "created_at_utc"]),
            file_name=f"casos_conciliacion_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not cases,
        )
        if not cases:
            st.info("No hay casos de conciliación.")
        for case in reversed(cases[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{case.get('case_id', '')} · {case.get('case_type', '')}**")
                cols[0].caption(str(case.get("description", "")))
                cols[1].metric("Monto", format_money(_num(case.get("amount")), get_currency()))
                cols[2].metric("Estado", str(case.get("status", "Abierto")))
                if case.get("status") != "Resuelto":
                    with st.form(f"resolve_financial_case_{case.get('case_id')}"):
                        responsible = st.text_input("Responsable", key=f"fr_resp_{case.get('case_id')}")
                        resolution = st.text_area("Resolución", max_chars=500, key=f"fr_res_{case.get('case_id')}")
                        submitted = st.form_submit_button("Resolver caso", type="primary", use_container_width=True)
                    if submitted:
                        if not responsible.strip() or not resolution.strip():
                            st.error("Responsable y resolución son obligatorios.")
                        else:
                            changed = []
                            for row in cases:
                                current = dict(row)
                                if current.get("case_id") == case.get("case_id"):
                                    current["status"] = "Resuelto"
                                    current["responsible"] = responsible.strip()
                                    current["resolution"] = resolution.strip()
                                    current["resolved_at_utc"] = _now()
                                changed.append(current)
                            _save("financial_reconciliation_cases", changed)
                            st.rerun()

    with snapshot_tab:
        if st.button("Crear corte de conciliación", type="primary", use_container_width=True):
            snapshots.append({
                "snapshot_id": f"FCS-{uuid4().hex[:8].upper()}",
                "expected_total": expected_total,
                "bank_total": bank_total,
                "difference": difference,
                "expected_pending": len(pending_expected),
                "bank_pending": len(pending_bank),
                "matches": len(matches),
                "open_cases": sum(1 for row in cases if row.get("status") != "Resuelto"),
                "created_at_utc": _now(),
            })
            _save("financial_reconciliation_snapshots", snapshots)
            st.rerun()
        for snapshot in reversed(snapshots[-50:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**Corte {snapshot.get('snapshot_id', '')}**")
                cols[0].caption(str(snapshot.get("created_at_utc", "")))
                cols[1].metric("Diferencia", format_money(_num(snapshot.get("difference")), get_currency()))
                cols[2].metric("Conciliados", str(snapshot.get("matches", 0)))
                cols[3].metric("Casos abiertos", str(snapshot.get("open_cases", 0)))

    render_info_card(
        "Cierre con evidencia",
        "La conciliación separa lo esperado por el ERP, lo importado del banco, las partidas conciliadas y los casos por resolver.",
        "CONTROL FINANCIERO",
    )


app_shell.FUNCTIONAL_MODULES["Conciliación financiera"] = render_financial_reconciliation
