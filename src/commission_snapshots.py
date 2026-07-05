"""Protege el historial de comisiones con valores congelados por asignación."""

import streamlit as st

from src import team_commission_control


def _ensure_snapshots(members: list[dict], assignments: list[dict]) -> list[dict]:
    member_map = {
        str(member.get("member_id", "")): member
        for member in members
        if member.get("member_id")
    }
    changed = False
    updated: list[dict] = []
    for assignment in assignments:
        current = dict(assignment)
        if "commission_mode_snapshot" not in current or "commission_value_snapshot" not in current:
            member = member_map.get(str(current.get("member_id", "")), {})
            current["commission_mode_snapshot"] = str(
                member.get("commission_mode", "Porcentaje")
            )
            current["commission_value_snapshot"] = float(
                member.get("commission_value", 0.0)
            )
            changed = True
        updated.append(current)
    if changed:
        st.session_state["commission_assignments"] = updated
    return updated


def _earned_with_snapshot(member: dict, assignments: list[dict], sales: list[dict]) -> float:
    members = [
        dict(item)
        for item in st.session_state.get("team_members", [])
        if isinstance(item, dict)
    ]
    assignments = _ensure_snapshots(members, assignments)
    member_id = str(member.get("member_id", ""))
    sale_map = {
        str(sale.get("sale_id", "")): sale
        for sale in sales
        if sale.get("sale_id")
    }
    total = 0.0
    for assignment in assignments:
        if str(assignment.get("member_id", "")) != member_id:
            continue
        if not assignment.get("active", True):
            continue
        sale = sale_map.get(str(assignment.get("sale_id", "")))
        if not sale:
            continue
        if sale.get("payment_status") != "Pagado" or sale.get("order_status") == "Cancelado":
            continue
        mode = str(assignment.get("commission_mode_snapshot", "Porcentaje"))
        value = float(assignment.get("commission_value_snapshot", 0.0))
        if mode == "Monto por venta":
            total += value
        else:
            total += float(sale.get("total", 0.0)) * value / 100
    return total


def activate_commission_snapshots() -> None:
    """Congela valores actuales y aplica el cálculo histórico protegido."""
    members = [
        dict(item)
        for item in st.session_state.get("team_members", [])
        if isinstance(item, dict)
    ]
    assignments = [
        dict(item)
        for item in st.session_state.get("commission_assignments", [])
        if isinstance(item, dict)
    ]
    _ensure_snapshots(members, assignments)
    team_commission_control._earned = _earned_with_snapshot
