"""Alertas avanzadas de inventario con prioridades y acciones."""

from collections import Counter
from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save, item_name as _item_name


def _activate_backup() -> None:
    for section, label in (
        ("inventory_alert_actions", "Acciones de alertas de inventario"),
        ("inventory_alert_rules", "Reglas de alertas de inventario"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


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


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _unit_cost(item: dict) -> float:
    return _num(item.get("purchase_cost")) / max(_num(item.get("purchased_quantity"), 1.0), 0.01)


def _available(item: dict) -> float:
    return _num(item.get("available_quantity", item.get("quantity")))


def _reserved(item_id: str, reservations: list[dict]) -> float:
    return sum(
        _num(row.get("quantity"))
        for row in reservations
        if str(row.get("item_id", "")) == item_id and row.get("status", "Activa") == "Activa"
    )


def _daily_use(item_id: str, movements: list[dict], days: int = 90) -> tuple[float, datetime | None]:
    cutoff = datetime.now() - timedelta(days=days)
    total = 0.0
    last = None
    for movement in movements:
        if str(movement.get("item_id", "")) != item_id:
            continue
        created = _dt(movement.get("created_at_utc", movement.get("date")))
        if str(movement.get("movement_type", "")) == "Salida":
            if created and created >= cutoff:
                total += _num(movement.get("quantity"))
            if created and (last is None or created > last):
                last = created
    return total / max(days, 1), last


def _policy(item_id: str, policies: list[dict]) -> dict:
    return next((row for row in policies if str(row.get("item_id", "")) == item_id), {})


def _rules() -> dict:
    defaults = {
        "critical_coverage_days": 7,
        "warning_coverage_days": 21,
        "expiry_warning_days": 30,
        "dead_stock_days": 90,
        "high_value_threshold": 20.0,
    }
    rows = _rows("inventory_alert_rules")
    if rows:
        defaults.update(rows[0])
    return defaults


def _build_alerts(items: list[dict], reservations: list[dict], movements: list[dict], lots: list[dict], policies: list[dict], rules: dict) -> list[dict]:
    alerts: list[dict] = []
    today = date.today()
    for item in items:
        item_id = str(item.get("item_id", ""))
        available = _available(item)
        reserved = _reserved(item_id, reservations)
        free = available - reserved
        minimum = _num(item.get("minimum_stock"))
        reorder = _num(item.get("reorder_point", minimum))
        daily, last_exit = _daily_use(item_id, movements)
        coverage = free / daily if daily > 0 else None
        policy = _policy(item_id, policies)
        lead = int(_num(policy.get("lead_time_days"), 7))
        safety = int(_num(policy.get("safety_days"), 7))
        target = max(reorder, daily * (lead + safety + 14), minimum * 2)
        suggested = max(target - free, 0.0)
        value = available * _unit_cost(item)

        if free < 0:
            alerts.append({"type": "Reserva excedida", "severity": "Crítica", "item_id": item_id, "item": item, "detail": f"Las reservas superan la existencia en {abs(free):,.2f}.", "free": free, "coverage": coverage, "suggested": suggested, "value": value})
        elif free <= 0:
            alerts.append({"type": "Agotado", "severity": "Crítica", "item_id": item_id, "item": item, "detail": "No hay existencia libre disponible.", "free": free, "coverage": coverage, "suggested": suggested, "value": value})
        elif coverage is not None and coverage <= int(rules["critical_coverage_days"]):
            alerts.append({"type": "Cobertura crítica", "severity": "Crítica", "item_id": item_id, "item": item, "detail": f"Quedan aproximadamente {coverage:,.1f} días de cobertura.", "free": free, "coverage": coverage, "suggested": suggested, "value": value})
        elif free <= minimum:
            alerts.append({"type": "Stock mínimo", "severity": "Alta", "item_id": item_id, "item": item, "detail": "La existencia libre está en el mínimo o por debajo.", "free": free, "coverage": coverage, "suggested": suggested, "value": value})
        elif coverage is not None and coverage <= int(rules["warning_coverage_days"]):
            alerts.append({"type": "Cobertura baja", "severity": "Alta", "item_id": item_id, "item": item, "detail": f"La cobertura estimada es de {coverage:,.1f} días.", "free": free, "coverage": coverage, "suggested": suggested, "value": value})
        elif free <= reorder:
            alerts.append({"type": "Reposición", "severity": "Media", "item_id": item_id, "item": item, "detail": "Se alcanzó el punto de reposición.", "free": free, "coverage": coverage, "suggested": suggested, "value": value})

        if value >= _num(rules["high_value_threshold"]) and (last_exit is None or (datetime.now() - last_exit).days >= int(rules["dead_stock_days"])):
            days_text = "sin salidas registradas" if last_exit is None else f"sin salidas durante {(datetime.now() - last_exit).days} días"
            alerts.append({"type": "Capital inmovilizado", "severity": "Media", "item_id": item_id, "item": item, "detail": f"{format_money(value)} {days_text}.", "free": free, "coverage": coverage, "suggested": 0.0, "value": value})

    for lot in lots:
        expiry = _as_date(lot.get("expiry_date"))
        if not expiry:
            continue
        item_id = str(lot.get("item_id", ""))
        item = next((row for row in items if str(row.get("item_id", "")) == item_id), {"name": "Material", "item_id": item_id})
        days_left = (expiry - today).days
        if days_left < 0:
            alerts.append({"type": "Lote vencido", "severity": "Crítica", "item_id": item_id, "item": item, "detail": f"Lote {lot.get('lot_code', '')} vencido hace {abs(days_left)} día(s).", "free": _available(item), "coverage": None, "suggested": 0.0, "value": _num(lot.get("quantity")) * _unit_cost(item)})
        elif days_left <= int(rules["expiry_warning_days"]):
            alerts.append({"type": "Lote próximo a vencer", "severity": "Alta", "item_id": item_id, "item": item, "detail": f"Lote {lot.get('lot_code', '')} vence en {days_left} día(s).", "free": _available(item), "coverage": None, "suggested": 0.0, "value": _num(lot.get("quantity")) * _unit_cost(item)})

    order = {"Crítica": 0, "Alta": 1, "Media": 2, "Baja": 3}
    return sorted(alerts, key=lambda row: (order.get(str(row.get("severity")), 9), str(row.get("item", {}).get("name", ""))))


def _create_restock(alert: dict) -> bool:
    suggestions = _rows("inventory_restock_suggestions")
    item_id = str(alert.get("item_id", ""))
    exists = any(str(row.get("item_id", "")) == item_id and row.get("status") == "Pendiente" for row in suggestions)
    if exists:
        return False
    item = dict(alert.get("item", {}))
    suggestions.append({
        "suggestion_id": f"REP-{uuid4().hex[:8].upper()}",
        "item_id": item_id,
        "item_name": str(item.get("name", "Material")),
        "quantity": round(_num(alert.get("suggested")), 4),
        "estimated_cost": round(_num(alert.get("suggested")) * _unit_cost(item), 4),
        "reason": f"Generada desde alerta: {alert.get('type', '')}",
        "status": "Pendiente",
        "created_at_utc": _now(),
    })
    _save("inventory_restock_suggestions", suggestions)
    return True


def _export(alerts: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Prioridad", "Tipo", "Material", "ID", "Detalle", "Existencia libre", "Cobertura días", "Compra sugerida", "Valor afectado"])
    for alert in alerts:
        writer.writerow([
            alert.get("severity", ""), alert.get("type", ""), alert.get("item", {}).get("name", ""), alert.get("item_id", ""),
            alert.get("detail", ""), alert.get("free", 0), alert.get("coverage") if alert.get("coverage") is not None else "",
            alert.get("suggested", 0), alert.get("value", 0),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_stock_alerts_plus() -> None:
    render_page_header(
        "Alertas de inventario",
        "Prioriza riesgos reales de existencias, reservas, cobertura, vencimientos y capital inmovilizado.",
    )

    items = _rows("inventory_registry")
    reservations = _rows("inventory_reservations")
    movements = _rows("inventory_movements")
    lots = _rows("inventory_lots")
    policies = _rows("inventory_policies")
    actions = _rows("inventory_alert_actions")
    rules = _rules()
    alerts = _build_alerts(items, reservations, movements, lots, policies, rules)
    currency = get_currency()

    if not items:
        st.info("No hay materiales registrados. Primero agrega o importa inventario.")
        return

    critical = [row for row in alerts if row.get("severity") == "Crítica"]
    high = [row for row in alerts if row.get("severity") == "Alta"]
    reorder_cost = sum(_num(row.get("suggested")) * _unit_cost(dict(row.get("item", {}))) for row in alerts if _num(row.get("suggested")) > 0)
    affected_value = sum(_num(row.get("value")) for row in alerts)

    metrics = st.columns(5)
    metrics[0].metric("Alertas activas", str(len(alerts)))
    metrics[1].metric("Críticas", str(len(critical)))
    metrics[2].metric("Altas", str(len(high)))
    metrics[3].metric("Reposición estimada", format_money(reorder_cost, currency))
    metrics[4].metric("Valor afectado", format_money(affected_value, currency))

    if critical:
        st.error(f"Hay {len(critical)} alerta(s) crítica(s) que requieren atención inmediata.")
    elif high:
        st.warning(f"Hay {len(high)} alerta(s) de prioridad alta.")
    elif alerts:
        st.info("Hay alertas preventivas, pero ninguna crítica.")
    else:
        st.success("El inventario no presenta alertas con las reglas actuales.")

    active_tab, dashboard_tab, actions_tab, rules_tab = st.tabs(("Alertas activas", "Resumen", "Seguimiento", "Reglas"))

    with active_tab:
        filters = st.columns(4)
        severity_filter = filters[0].selectbox("Prioridad", ("Todas", "Crítica", "Alta", "Media"))
        type_filter = filters[1].selectbox("Tipo", ("Todos", *sorted({str(row.get('type', '')) for row in alerts})))
        query = filters[2].text_input("Buscar material").strip().casefold()
        only_actionable = filters[3].checkbox("Solo con compra sugerida", value=False)
        visible = []
        for alert in alerts:
            if severity_filter != "Todas" and alert.get("severity") != severity_filter:
                continue
            if type_filter != "Todos" and alert.get("type") != type_filter:
                continue
            if query and query not in str(alert.get("item", {}).get("name", "")).casefold():
                continue
            if only_actionable and _num(alert.get("suggested")) <= 0:
                continue
            visible.append(alert)

        st.download_button(
            "Descargar alertas CSV",
            data=_export(visible),
            file_name=f"alertas_inventario_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not visible,
        )

        for index, alert in enumerate(visible):
            item = dict(alert.get("item", {}))
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{item.get('name', 'Material')} · {alert.get('type', '')}**")
                cols[0].caption(str(alert.get("detail", "")))
                cols[1].metric("Prioridad", str(alert.get("severity", "")))
                cols[2].metric("Libre", f"{_num(alert.get('free')):,.2f}")
                cols[3].metric("Comprar", f"{_num(alert.get('suggested')):,.2f}")
                action_cols = st.columns(2)
                if _num(alert.get("suggested")) > 0 and action_cols[0].button("Crear reposición", key=f"restock_alert_{index}_{alert.get('item_id')}", use_container_width=True):
                    if _create_restock(alert):
                        st.success("Solicitud de reposición creada.")
                    else:
                        st.warning("Ya existe una reposición pendiente para este material.")
                if action_cols[1].button("Registrar seguimiento", key=f"follow_alert_{index}_{alert.get('item_id')}", use_container_width=True):
                    st.session_state["selected_inventory_alert"] = {
                        "item_id": alert.get("item_id", ""),
                        "type": alert.get("type", ""),
                        "severity": alert.get("severity", ""),
                    }
                    st.rerun()

    with dashboard_tab:
        by_type = Counter(str(row.get("type", "")) for row in alerts)
        by_category = Counter(str(row.get("item", {}).get("category", "Otro")) for row in alerts)
        columns = st.columns(2)
        with columns[0]:
            st.markdown("#### Alertas por tipo")
            for name, count in by_type.most_common():
                st.write(f"**{name}:** {count}")
        with columns[1]:
            st.markdown("#### Alertas por categoría")
            for name, count in by_category.most_common():
                st.write(f"**{name}:** {count}")
        render_info_card(
            "Lectura gerencial",
            "Las alertas combinan existencia libre, reservas, consumo reciente, cobertura, lotes y valor inmovilizado.",
            "PREVENCIÓN",
        )

    with actions_tab:
        selected = st.session_state.get("selected_inventory_alert", {})
        if selected:
            with st.form("inventory_alert_followup_form", clear_on_submit=True):
                st.markdown(f"**{selected.get('type', '')} · {_item_name(str(selected.get('item_id', '')), items)}**")
                responsible = st.text_input("Responsable")
                status = st.selectbox("Estado", ("En revisión", "Compra solicitada", "Resuelto", "Descartado"))
                due_date = st.date_input("Fecha compromiso", value=date.today() + timedelta(days=3))
                note = st.text_area("Acción tomada", max_chars=500)
                submitted = st.form_submit_button("Guardar seguimiento", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not note.strip():
                    st.error("Responsable y acción tomada son obligatorios.")
                else:
                    actions.append({
                        "action_id": f"ALT-{uuid4().hex[:8].upper()}",
                        **selected,
                        "responsible": responsible.strip(),
                        "status": status,
                        "due_date": due_date.isoformat(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("inventory_alert_actions", actions)
                    st.session_state.pop("selected_inventory_alert", None)
                    st.rerun()
        if not actions:
            st.info("No hay seguimientos registrados.")
        for action in reversed(actions[-100:]):
            with st.container(border=True):
                st.markdown(f"**{action.get('action_id', '')} · {_item_name(str(action.get('item_id', '')), items)}**")
                st.write(str(action.get("note", "")))
                st.caption(f"{action.get('status', '')} · {action.get('responsible', '')} · compromiso {action.get('due_date', '')}")

    with rules_tab:
        with st.form("inventory_alert_rules_form"):
            cols = st.columns(5)
            critical_days = cols[0].number_input("Cobertura crítica", min_value=1, value=int(_num(rules.get("critical_coverage_days"), 7)), step=1)
            warning_days = cols[1].number_input("Cobertura baja", min_value=1, value=int(_num(rules.get("warning_coverage_days"), 21)), step=1)
            expiry_days = cols[2].number_input("Aviso vencimiento", min_value=1, value=int(_num(rules.get("expiry_warning_days"), 30)), step=1)
            dead_days = cols[3].number_input("Sin movimiento", min_value=1, value=int(_num(rules.get("dead_stock_days"), 90)), step=1)
            high_value = cols[4].number_input("Valor mínimo inmóvil", min_value=0.0, value=_num(rules.get("high_value_threshold"), 20.0), step=1.0)
            submitted = st.form_submit_button("Guardar reglas", type="primary", use_container_width=True)
        if submitted:
            _save("inventory_alert_rules", [{
                "critical_coverage_days": int(critical_days),
                "warning_coverage_days": int(warning_days),
                "expiry_warning_days": int(expiry_days),
                "dead_stock_days": int(dead_days),
                "high_value_threshold": float(high_value),
                "updated_at_utc": _now(),
            }])
            st.rerun()


app_shell.FUNCTIONAL_MODULES["Alertas de inventario"] = render_stock_alerts_plus
