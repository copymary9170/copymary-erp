"""Capacidad, bloques horarios y reprogramación para la agenda operativa."""

from collections import defaultdict
from datetime import date, time, timedelta

import streamlit as st

from src import order_planning_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    section = "production_capacity_settings"
    if section not in session_backup.DICT_SECTIONS:
        session_backup.DICT_SECTIONS = (*session_backup.DICT_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Capacidad de producción"
        session_backup.SESSION_KEYS = (
            "general_settings",
            *session_backup.LIST_SECTIONS,
            *session_backup.DICT_SECTIONS,
        )


_activate_backup()


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _as_time(value, fallback: time) -> time:
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        return fallback


def _plan_for(sale_id: str, plans: list[dict]) -> dict:
    for plan in plans:
        if str(plan.get("sale_id", "")) == sale_id:
            return dict(plan)
    return {}


def _update_plan(sale_id: str, updates: dict) -> None:
    plans = _rows("order_plans")
    found = False
    changed = []
    for plan in plans:
        current = dict(plan)
        if str(current.get("sale_id", "")) == sale_id:
            current.update(updates)
            current["updated_at_utc"] = _now()
            found = True
        changed.append(current)
    if not found:
        changed.append({
            "plan_id": f"capacity-{sale_id}",
            "sale_id": sale_id,
            "delivery_date": updates.get("delivery_date", ""),
            "priority": updates.get("priority", "Normal"),
            "assigned_to": updates.get("assigned_to", ""),
            "progress": 0,
            "production_status": "Sin iniciar",
            "delivery_method": "Retiro",
            "checklist": [],
            "notes": "Plan creado desde la gestión de capacidad.",
            "updated_at_utc": _now(),
            **updates,
        })
    _save("order_plans", changed)


def _capacity_settings() -> dict:
    raw = st.session_state.get("production_capacity_settings", {})
    settings = dict(raw) if isinstance(raw, dict) else {}
    settings.setdefault("daily_hours", 8.0)
    settings.setdefault("start_time", "08:00")
    settings.setdefault("warning_threshold", 0.85)
    return settings


def _duration(plan: dict) -> float:
    try:
        return max(float(plan.get("estimated_hours", 1.0)), 0.25)
    except (TypeError, ValueError):
        return 1.0


def _effective_date(sale: dict, plan: dict) -> date | None:
    return _as_date(plan.get("delivery_date") or sale.get("due_date"))


def render_order_planning_capacity() -> None:
    render_page_header(
        "Agenda de producción y entregas",
        "Distribuye horas, bloques de trabajo y entregas sin sobrecargar la capacidad diaria.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_order_planning_plus()
    finally:
        base.render_page_header = original_header

    sales = [sale for sale in _rows("sales_registry") if sale.get("order_status") not in {"Entregado", "Cancelado"}]
    plans = _rows("order_plans")
    settings = _capacity_settings()
    today = date.today()

    st.divider()
    st.markdown("### Configuración de capacidad")
    with st.form("production_capacity_form"):
        columns = st.columns(3)
        daily_hours = columns[0].number_input("Horas disponibles por día", min_value=1.0, max_value=24.0, value=float(settings["daily_hours"]), step=0.5)
        start_time = columns[1].time_input("Inicio de jornada", value=_as_time(settings["start_time"], time(8, 0)))
        warning_percent = columns[2].number_input("Avisar desde % de ocupación", min_value=50, max_value=100, value=int(float(settings["warning_threshold"]) * 100), step=5)
        save_capacity = st.form_submit_button("Guardar capacidad", use_container_width=True)
    if save_capacity:
        _save("production_capacity_settings", {
            "daily_hours": float(daily_hours),
            "start_time": start_time.isoformat(timespec="minutes"),
            "warning_threshold": float(warning_percent) / 100,
        })
        st.rerun()

    st.markdown("### Estimar duración y reprogramar")
    options = {
        f"{sale.get('description', 'Pedido')} · {sale.get('sale_id', '')}": str(sale.get("sale_id", ""))
        for sale in sales
    }
    if options:
        selected = st.selectbox("Pedido", tuple(options.keys()), key="capacity_order")
        sale_id = options[selected]
        sale = next(item for item in sales if str(item.get("sale_id", "")) == sale_id)
        plan = _plan_for(sale_id, plans)
        current_date = _effective_date(sale, plan) or today
        with st.form("capacity_order_form"):
            columns = st.columns(4)
            estimated_hours = columns[0].number_input("Duración estimada", min_value=0.25, max_value=48.0, value=_duration(plan), step=0.25)
            work_date = columns[1].date_input("Fecha de producción", value=_as_date(plan.get("production_date")) or current_date)
            slot = columns[2].selectbox("Bloque", ("Mañana", "Mediodía", "Tarde", "Flexible"), index=("Mañana", "Mediodía", "Tarde", "Flexible").index(str(plan.get("time_block", "Flexible"))) if str(plan.get("time_block", "Flexible")) in ("Mañana", "Mediodía", "Tarde", "Flexible") else 3)
            delivery_date = columns[3].date_input("Fecha de entrega", value=current_date)
            reason = st.text_input("Motivo de reprogramación", value=str(plan.get("reschedule_reason", "")))
            save_plan = st.form_submit_button("Guardar asignación", type="primary", use_container_width=True)
        if save_plan:
            _update_plan(sale_id, {
                "estimated_hours": float(estimated_hours),
                "production_date": work_date.isoformat(),
                "time_block": slot,
                "delivery_date": delivery_date.isoformat(),
                "reschedule_reason": reason.strip(),
            })
            st.rerun()

    st.markdown("### Ocupación de los próximos 7 días")
    scheduled: dict[date, list[tuple[dict, dict]]] = defaultdict(list)
    for sale in sales:
        plan = _plan_for(str(sale.get("sale_id", "")), plans)
        production_date = _as_date(plan.get("production_date")) or _effective_date(sale, plan)
        if production_date:
            scheduled[production_date].append((sale, plan))

    capacity = float(settings["daily_hours"])
    threshold = float(settings["warning_threshold"])
    for offset in range(8):
        day = today + timedelta(days=offset)
        items = scheduled.get(day, [])
        used = sum(_duration(plan) for _, plan in items)
        occupancy = used / capacity if capacity else 0.0
        with st.container(border=True):
            columns = st.columns([2, 1, 1, 1])
            columns[0].markdown(f"#### {day.isoformat()}")
            columns[1].metric("Pedidos", str(len(items)))
            columns[2].metric("Horas asignadas", f"{used:,.1f} h")
            columns[3].metric("Ocupación", f"{occupancy * 100:,.0f}%")
            st.progress(min(occupancy, 1.0))
            if occupancy > 1:
                st.error(f"Sobrecarga de {used - capacity:,.1f} hora(s). Reprograma pedidos.")
            elif occupancy >= threshold:
                st.warning("La jornada está cerca de su capacidad máxima.")
            for sale, plan in sorted(items, key=lambda item: str(item[1].get("time_block", "Flexible"))):
                st.write(f"**{plan.get('time_block', 'Flexible')}** · {sale.get('description', 'Pedido')} · {_duration(plan):,.1f} h · {plan.get('assigned_to') or sale.get('responsible') or 'Sin asignar'}")

    st.markdown("### Agrupación de entregas")
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for sale in sales:
        plan = _plan_for(str(sale.get("sale_id", "")), plans)
        delivery = _effective_date(sale, plan)
        method = str(plan.get("delivery_method") or sale.get("delivery_method") or "Retiro")
        if delivery:
            grouped[(delivery.isoformat(), method)].append(sale)
    if not grouped:
        st.info("No hay entregas programadas para agrupar.")
    else:
        for (delivery, method), items in sorted(grouped.items()):
            if len(items) >= 2:
                st.info(f"{delivery} · {method}: {len(items)} pedidos pueden coordinarse juntos.")

    render_info_card(
        "Capacidad respaldada",
        "La capacidad diaria y los bloques de cada pedido se incluyen en el respaldo general.",
        "PLANIFICACIÓN DE CARGA",
    )
