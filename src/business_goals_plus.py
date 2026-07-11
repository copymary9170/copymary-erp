"""Plan de acciones, visión trimestral y exportación para Metas del negocio."""

from datetime import date, datetime
import csv
import io
import uuid

import streamlit as st

from src import business_goals as base
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import read_list as _rows


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _record_month(record: dict) -> str:
    raw = str(record.get("created_at_utc", record.get("created_at", record.get("date", ""))))
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return raw[:7] if len(raw) >= 7 else ""


def _month_options() -> list[str]:
    current = date.today().strftime("%Y-%m")
    goals = st.session_state.get("business_goals", {})
    actions = st.session_state.get("business_goal_actions", [])
    months = {current}
    if isinstance(goals, dict):
        months.update(str(month) for month in goals.keys())
    months.update(str(item.get("month", "")) for item in actions if isinstance(item, dict) and item.get("month"))
    months.update(filter(None, (_record_month(sale) for sale in _rows("sales_registry"))))
    return sorted(months, reverse=True)


def _quarter_months(month: str) -> list[str]:
    year, number = (int(part) for part in month.split("-"))
    start = ((number - 1) // 3) * 3 + 1
    return [f"{year}-{value:02d}" for value in range(start, start + 3)]


def _month_results(month: str) -> tuple[float, float, int]:
    cancelled = {"Cancelado", "Cancelada", "Anulado", "Anulada"}
    sales = [
        sale for sale in _rows("sales_registry")
        if sale.get("order_status") not in cancelled and _record_month(sale) == month
    ]
    total_sales = sum(_number(item.get("total")) for item in sales)
    profit = sum(_number(item.get("total")) - _number(item.get("estimated_cost")) for item in sales)
    return total_sales, profit, len(sales)


def _goals_for(month: str) -> dict:
    raw = st.session_state.get("business_goals", {})
    if not isinstance(raw, dict):
        return {}
    values = raw.get(month, {})
    return dict(values) if isinstance(values, dict) else {}


def _actions() -> list[dict]:
    return _rows("business_goal_actions")


def _save_actions(actions: list[dict]) -> None:
    st.session_state["business_goal_actions"] = actions


def _action_progress(actions: list[dict]) -> tuple[int, int, int]:
    total = len(actions)
    completed = sum(1 for item in actions if item.get("status") == "Completada")
    overdue = sum(
        1 for item in actions
        if item.get("status") != "Completada"
        and item.get("due_date")
        and str(item.get("due_date")) < date.today().isoformat()
    )
    return total, completed, overdue


def _export_csv(month: str, actions: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    goals = _goals_for(month)
    sales, profit, orders = _month_results(month)
    writer.writerow(["Metas CopyMary ERP", month])
    writer.writerow(["Generado", datetime.now().isoformat(timespec="seconds")])
    writer.writerow([])
    writer.writerow(["Indicador", "Meta", "Resultado"])
    writer.writerow(["Ventas", goals.get("sales_goal", 0), sales])
    writer.writerow(["Ganancia", goals.get("profit_goal", 0), profit])
    writer.writerow(["Pedidos", goals.get("orders_goal", 0), orders])
    writer.writerow([])
    writer.writerow(["Acción", "Meta relacionada", "Responsable", "Fecha límite", "Estado"])
    for item in actions:
        writer.writerow([
            item.get("title", ""),
            item.get("goal_type", ""),
            item.get("owner", ""),
            item.get("due_date", ""),
            item.get("status", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def _render_action_plan(month: str) -> None:
    st.markdown("### Plan de acciones")
    all_actions = _actions()
    month_actions = [item for item in all_actions if item.get("month") == month]
    total, completed, overdue = _action_progress(month_actions)

    metrics = st.columns(4)
    metrics[0].metric("Acciones", str(total))
    metrics[1].metric("Completadas", str(completed))
    metrics[2].metric("Pendientes", str(max(total - completed, 0)))
    metrics[3].metric("Vencidas", str(overdue))

    with st.expander("Agregar acción", expanded=not month_actions):
        with st.form("goal_action_form", clear_on_submit=True):
            title = st.text_input("Acción concreta", placeholder="Ejemplo: contactar 10 clientes antiguos")
            columns = st.columns(3)
            goal_type = columns[0].selectbox("Meta relacionada", ("Ventas", "Ganancia", "Pedidos", "General"))
            owner = columns[1].text_input("Responsable", placeholder="Mary")
            due_date = columns[2].date_input("Fecha límite", value=date.today())
            notes = st.text_area("Detalle o criterio de éxito", placeholder="Qué debe ocurrir para considerar esta acción completada")
            submitted = st.form_submit_button("Agregar al plan", type="primary", use_container_width=True)
        if submitted:
            if not title.strip():
                st.error("Escribe una acción concreta.")
            else:
                all_actions.append({
                    "action_id": uuid.uuid4().hex[:12],
                    "month": month,
                    "title": title.strip(),
                    "goal_type": goal_type,
                    "owner": owner.strip() or "Sin asignar",
                    "due_date": due_date.isoformat(),
                    "notes": notes.strip(),
                    "status": "Pendiente",
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                })
                _save_actions(all_actions)
                st.success("Acción agregada al plan.")
                st.rerun()

    if not month_actions:
        st.info("Todavía no hay acciones definidas para este mes.")
        return

    status_options = ("Pendiente", "En progreso", "Completada", "Bloqueada")
    for index, action in enumerate(month_actions):
        action_id = str(action.get("action_id", ""))
        with st.container(border=True):
            columns = st.columns([3, 1, 1, 1])
            with columns[0]:
                st.markdown(f"#### {action.get('title', 'Acción')}")
                st.caption(
                    f"{action.get('goal_type', 'General')} · Responsable: {action.get('owner', 'Sin asignar')} · "
                    f"Fecha límite: {action.get('due_date', 'Sin fecha')}"
                )
                if action.get("notes"):
                    st.write(action["notes"])
            current_status = str(action.get("status", "Pendiente"))
            if current_status not in status_options:
                current_status = "Pendiente"
            new_status = columns[1].selectbox(
                "Estado",
                status_options,
                index=status_options.index(current_status),
                key=f"goal_action_status_{action_id}_{index}",
            )
            if columns[2].button("Guardar", key=f"goal_action_save_{action_id}_{index}", use_container_width=True):
                for stored in all_actions:
                    if str(stored.get("action_id", "")) == action_id:
                        stored["status"] = new_status
                        stored["updated_at"] = datetime.now().isoformat(timespec="seconds")
                        break
                _save_actions(all_actions)
                st.success("Estado actualizado.")
                st.rerun()
            if columns[3].button("Eliminar", key=f"goal_action_delete_{action_id}_{index}", use_container_width=True):
                _save_actions([item for item in all_actions if str(item.get("action_id", "")) != action_id])
                st.rerun()


def _render_quarter(month: str) -> None:
    st.markdown("### Visión trimestral")
    quarter = _quarter_months(month)
    total_sales = total_profit = 0.0
    total_orders = 0
    target_sales = target_profit = 0.0
    target_orders = 0
    for quarter_month in quarter:
        sales, profit, orders = _month_results(quarter_month)
        goals = _goals_for(quarter_month)
        total_sales += sales
        total_profit += profit
        total_orders += orders
        target_sales += _number(goals.get("sales_goal"))
        target_profit += _number(goals.get("profit_goal"))
        target_orders += int(_number(goals.get("orders_goal")))

    metrics = st.columns(3)
    metrics[0].metric("Ventas trimestrales", format_money(total_sales), f"Meta {format_money(target_sales)}")
    metrics[1].metric("Ganancia trimestral", format_money(total_profit), f"Meta {format_money(target_profit)}")
    metrics[2].metric("Pedidos trimestrales", str(total_orders), f"Meta {target_orders}")

    for quarter_month in quarter:
        sales, profit, orders = _month_results(quarter_month)
        goals = _goals_for(quarter_month)
        with st.expander(quarter_month, expanded=quarter_month == month):
            columns = st.columns(3)
            columns[0].metric("Ventas", format_money(sales), f"Meta {format_money(_number(goals.get('sales_goal')))}")
            columns[1].metric("Ganancia", format_money(profit), f"Meta {format_money(_number(goals.get('profit_goal')))}")
            columns[2].metric("Pedidos", str(orders), f"Meta {int(_number(goals.get('orders_goal')))}")


def render_business_goals_plus() -> None:
    render_page_header(
        "Metas del negocio",
        "Objetivos, acciones, responsables y visión trimestral para convertir las metas en ejecución real.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_business_goals()
    finally:
        base.render_page_header = original_header

    st.divider()
    month = st.selectbox("Mes del plan de acciones", _month_options(), key="goal_action_month")
    _render_action_plan(month)
    _render_quarter(month)

    month_actions = [item for item in _actions() if item.get("month") == month]
    st.download_button(
        "Descargar seguimiento del mes",
        data=_export_csv(month, month_actions),
        file_name=f"metas_copymary_{month}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    render_info_card(
        "Ejecución de metas",
        "Las metas se respaldan junto con sus acciones, responsables, fechas y estados.",
        "PLAN DE CRECIMIENTO",
    )
