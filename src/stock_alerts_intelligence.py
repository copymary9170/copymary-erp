"""Ciclo de vida, SLA y escalamiento para alertas de inventario."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import csv
import io

import streamlit as st

from src import app_shell, session_backup, stock_alerts_plus as base
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("inventory_alert_cases", "Casos de alertas de inventario"),
        ("inventory_alert_escalations", "Escalamientos de alertas de inventario"),
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


def _case_key(alert: dict) -> str:
    return f"{alert.get('item_id', '')}::{alert.get('type', '')}"


def _sla_hours(severity: str) -> int:
    return {"Crítica": 8, "Alta": 24, "Media": 72, "Baja": 168}.get(severity, 72)


def _sync_cases(alerts: list[dict]) -> list[dict]:
    cases = _rows("inventory_alert_cases")
    by_key = {str(case.get("case_key", "")): dict(case) for case in cases}
    current_keys = set()
    now = datetime.now()

    for alert in alerts:
        key = _case_key(alert)
        current_keys.add(key)
        severity = str(alert.get("severity", "Media"))
        case = by_key.get(key)
        if case is None:
            case = {
                "case_key": key,
                "item_id": str(alert.get("item_id", "")),
                "alert_type": str(alert.get("type", "")),
                "severity": severity,
                "status": "Abierta",
                "owner": "Sin asignar",
                "first_seen_at_utc": _now(),
                "last_seen_at_utc": _now(),
                "occurrences": 1,
                "sla_due_at_utc": (now + timedelta(hours=_sla_hours(severity))).replace(tzinfo=timezone.utc).isoformat(),
                "detail": str(alert.get("detail", "")),
                "suggested": _num(alert.get("suggested")),
                "value": _num(alert.get("value")),
            }
        else:
            snoozed_until = _dt(case.get("snoozed_until"))
            if case.get("status") == "Pausada" and snoozed_until and snoozed_until <= now:
                case["status"] = "Abierta"
                case["snoozed_until"] = ""
            if case.get("status") == "Resuelta":
                case["status"] = "Reabierta"
                case["reopened_at_utc"] = _now()
            case["severity"] = severity
            case["last_seen_at_utc"] = _now()
            case["occurrences"] = int(_num(case.get("occurrences"), 0)) + 1
            case["detail"] = str(alert.get("detail", ""))
            case["suggested"] = _num(alert.get("suggested"))
            case["value"] = _num(alert.get("value"))
        by_key[key] = case

    for key, case in list(by_key.items()):
        if key not in current_keys and case.get("status") not in {"Resuelta", "Cerrada automáticamente"}:
            case["status"] = "Cerrada automáticamente"
            case["resolved_at_utc"] = _now()
            case["resolution_note"] = "La condición dejó de estar activa."

    synced = list(by_key.values())
    _save("inventory_alert_cases", synced)
    return synced


def _update_case(case_key: str, updates: dict) -> None:
    cases = _rows("inventory_alert_cases")
    changed = []
    for case in cases:
        row = dict(case)
        if str(row.get("case_key", "")) == case_key:
            row.update(updates)
            row["updated_at_utc"] = _now()
        changed.append(row)
    _save("inventory_alert_cases", changed)


def _record_escalation(case: dict, reason: str, escalated_to: str) -> None:
    rows = _rows("inventory_alert_escalations")
    rows.append({
        "case_key": str(case.get("case_key", "")),
        "item_id": str(case.get("item_id", "")),
        "alert_type": str(case.get("alert_type", "")),
        "severity": str(case.get("severity", "")),
        "reason": reason.strip(),
        "escalated_to": escalated_to.strip() or "Gerencia",
        "created_at_utc": _now(),
    })
    _save("inventory_alert_escalations", rows)


def _stockout_date(item_id: str, alerts: list[dict], movements: list[dict]) -> date | None:
    alert = next((row for row in alerts if str(row.get("item_id", "")) == item_id), None)
    if not alert:
        return None
    free = _num(alert.get("free"))
    daily, _ = base._daily_use(item_id, movements)
    if daily <= 0 or free <= 0:
        return date.today() if free <= 0 else None
    return date.today() + timedelta(days=max(int(free / daily), 0))


def _export(cases: list[dict], items: list[dict]) -> bytes:
    names = {str(item.get("item_id", "")): str(item.get("name", "Material")) for item in items}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Material", "Tipo", "Prioridad", "Estado", "Responsable", "Primera detección",
        "Última detección", "Repeticiones", "Vence SLA", "Compra sugerida", "Valor afectado",
    ])
    for case in cases:
        writer.writerow([
            names.get(str(case.get("item_id", "")), "Material"),
            case.get("alert_type", ""),
            case.get("severity", ""),
            case.get("status", ""),
            case.get("owner", ""),
            case.get("first_seen_at_utc", ""),
            case.get("last_seen_at_utc", ""),
            case.get("occurrences", 0),
            case.get("sla_due_at_utc", ""),
            case.get("suggested", 0),
            case.get("value", 0),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_stock_alerts_intelligence() -> None:
    render_page_header(
        "Alertas de inventario",
        "Convierte cada alerta en un caso con responsable, SLA, pausa, escalamiento y cierre verificable.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_stock_alerts_plus()
    finally:
        base.render_page_header = original_header

    items = _rows("inventory_registry")
    reservations = _rows("inventory_reservations")
    movements = _rows("inventory_movements")
    lots = _rows("inventory_lots")
    policies = _rows("inventory_policies")
    rules = base._rules()
    alerts = base._build_alerts(items, reservations, movements, lots, policies, rules)
    cases = _sync_cases(alerts)
    escalations = _rows("inventory_alert_escalations")
    now = datetime.now()

    open_cases = [case for case in cases if case.get("status") in {"Abierta", "Reabierta", "Reconocida", "Pausada"}]
    overdue = [
        case for case in open_cases
        if case.get("status") != "Pausada"
        and (due := _dt(case.get("sla_due_at_utc"))) is not None
        and due < now
    ]
    unassigned = [case for case in open_cases if str(case.get("owner", "Sin asignar")) == "Sin asignar"]
    recurring = [case for case in open_cases if int(_num(case.get("occurrences"))) >= 3]

    st.divider()
    st.markdown("### Centro de atención de alertas")
    metrics = st.columns(5)
    metrics[0].metric("Casos abiertos", str(len(open_cases)))
    metrics[1].metric("SLA vencido", str(len(overdue)))
    metrics[2].metric("Sin responsable", str(len(unassigned)))
    metrics[3].metric("Recurrentes", str(len(recurring)))
    metrics[4].metric("Escalamientos", str(len(escalations)))

    if overdue:
        st.error(f"Hay {len(overdue)} caso(s) con SLA vencido.")
    if unassigned:
        st.warning(f"Hay {len(unassigned)} caso(s) sin responsable asignado.")

    cases_tab, forecast_tab, escalation_tab, history_tab = st.tabs(
        ("Casos", "Agotamiento estimado", "Escalamiento", "Historial")
    )

    names = {str(item.get("item_id", "")): str(item.get("name", "Material")) for item in items}

    with cases_tab:
        filters = st.columns(4)
        status_filter = filters[0].selectbox("Estado", ("Todos", "Abierta", "Reabierta", "Reconocida", "Pausada", "Resuelta", "Cerrada automáticamente"))
        owner_filter = filters[1].text_input("Responsable").strip().casefold()
        severity_filter = filters[2].selectbox("Prioridad", ("Todas", "Crítica", "Alta", "Media"))
        only_overdue = filters[3].checkbox("Solo SLA vencido", value=False)

        visible = []
        for case in cases:
            if status_filter != "Todos" and case.get("status") != status_filter:
                continue
            if owner_filter and owner_filter not in str(case.get("owner", "")).casefold():
                continue
            if severity_filter != "Todas" and case.get("severity") != severity_filter:
                continue
            due = _dt(case.get("sla_due_at_utc"))
            if only_overdue and (due is None or due >= now or case.get("status") == "Pausada"):
                continue
            visible.append(case)

        st.download_button(
            "Descargar casos CSV",
            data=_export(visible, items),
            file_name=f"casos_alertas_inventario_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not visible,
        )

        for case in visible:
            case_key = str(case.get("case_key", ""))
            due = _dt(case.get("sla_due_at_utc"))
            is_overdue = due is not None and due < now and case.get("status") != "Pausada"
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{names.get(str(case.get('item_id', '')), 'Material')} · {case.get('alert_type', '')}**")
                cols[0].caption(str(case.get("detail", "")))
                cols[1].metric("Estado", str(case.get("status", "")))
                cols[2].metric("Prioridad", str(case.get("severity", "")))
                cols[3].metric("Repeticiones", str(case.get("occurrences", 0)))
                st.caption(f"Responsable: {case.get('owner', 'Sin asignar')} · SLA: {case.get('sla_due_at_utc', '')}{' · VENCIDO' if is_overdue else ''}")

                with st.expander("Gestionar caso"):
                    with st.form(f"manage_alert_case_{case_key}"):
                        action = st.selectbox("Acción", ("Asignar y reconocer", "Pausar 3 días", "Pausar 7 días", "Resolver", "Escalar"), key=f"action_{case_key}")
                        owner = st.text_input("Responsable", value=str(case.get("owner", "")) if case.get("owner") != "Sin asignar" else "", key=f"owner_{case_key}")
                        note = st.text_area("Nota", max_chars=500, key=f"note_{case_key}")
                        submitted = st.form_submit_button("Guardar", type="primary", use_container_width=True)
                    if submitted:
                        if action in {"Asignar y reconocer", "Resolver", "Escalar"} and not owner.strip():
                            st.error("Indica un responsable.")
                        elif action == "Resolver" and not note.strip():
                            st.error("Indica cómo se resolvió el caso.")
                        else:
                            updates = {"owner": owner.strip() or str(case.get("owner", "Sin asignar")), "last_note": note.strip()}
                            if action == "Asignar y reconocer":
                                updates.update({"status": "Reconocida", "acknowledged_at_utc": _now()})
                            elif action.startswith("Pausar"):
                                days = 3 if "3" in action else 7
                                updates.update({"status": "Pausada", "snoozed_until": (now + timedelta(days=days)).replace(tzinfo=timezone.utc).isoformat()})
                            elif action == "Resolver":
                                updates.update({"status": "Resuelta", "resolved_at_utc": _now(), "resolution_note": note.strip()})
                            else:
                                updates.update({"status": "Escalada", "escalated_at_utc": _now()})
                                _record_escalation(case, note or "Escalamiento manual", owner)
                            _update_case(case_key, updates)
                            st.rerun()

    with forecast_tab:
        candidates = []
        for item in items:
            item_id = str(item.get("item_id", ""))
            forecast = _stockout_date(item_id, alerts, movements)
            if forecast:
                candidates.append((forecast, item))
        if not candidates:
            st.info("No hay materiales con fecha de agotamiento calculable.")
        for forecast, item in sorted(candidates, key=lambda row: row[0]):
            days_left = (forecast - date.today()).days
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{item.get('name', 'Material')}**")
                cols[0].caption(f"ID {item.get('item_id', '')} · existencia {_num(item.get('available_quantity')):,.2f}")
                cols[1].metric("Agotamiento estimado", forecast.isoformat())
                cols[2].metric("Días restantes", str(days_left))

    with escalation_tab:
        candidates = [case for case in open_cases if case in overdue or int(_num(case.get("occurrences"))) >= 3 or case.get("severity") == "Crítica"]
        if not candidates:
            st.success("No hay casos que requieran escalamiento automático.")
        for case in candidates:
            reason = "SLA vencido" if case in overdue else "Alerta recurrente" if int(_num(case.get("occurrences"))) >= 3 else "Prioridad crítica"
            with st.container(border=True):
                st.markdown(f"**{names.get(str(case.get('item_id', '')), 'Material')} · {case.get('alert_type', '')}**")
                st.caption(reason)
                if st.button("Escalar a gerencia", key=f"escalate_case_{case.get('case_key')}", use_container_width=True):
                    _record_escalation(case, reason, "Gerencia")
                    _update_case(str(case.get("case_key", "")), {"status": "Escalada", "escalated_at_utc": _now()})
                    st.rerun()

    with history_tab:
        if not escalations:
            st.info("No hay escalamientos registrados.")
        for entry in reversed(escalations[-100:]):
            with st.container(border=True):
                st.markdown(f"**{names.get(str(entry.get('item_id', '')), 'Material')} · {entry.get('alert_type', '')}**")
                st.write(str(entry.get("reason", "")))
                st.caption(f"Escalado a {entry.get('escalated_to', 'Gerencia')} · {entry.get('created_at_utc', '')}")

    render_info_card(
        "Alertas con seguimiento",
        "Cada alerta conserva responsable, vencimiento, recurrencia, pausas, resolución y escalamiento.",
        "GESTIÓN PREVENTIVA",
    )


app_shell.FUNCTIONAL_MODULES["Alertas de inventario"] = render_stock_alerts_intelligence
