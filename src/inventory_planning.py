"""Planeación de reposición y análisis de inventario."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import inventory_plus as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("inventory_restock_suggestions", "Sugerencias de reposición"),
        ("inventory_policies", "Políticas de inventario"),
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


def _unit_cost(item: dict) -> float:
    return _num(item.get("purchase_cost")) / max(_num(item.get("purchased_quantity"), 1.0), 0.01)


def _available(item: dict) -> float:
    return _num(item.get("available_quantity", item.get("quantity")))


def _reserved(item_id: str, rows: list[dict]) -> float:
    return sum(_num(row.get("quantity")) for row in rows if str(row.get("item_id", "")) == item_id and row.get("status", "Activa") == "Activa")


def _consumption(item_id: str, movements: list[dict]) -> tuple[float, datetime | None]:
    cutoff = datetime.now() - timedelta(days=90)
    total = 0.0
    last = None
    for movement in movements:
        if str(movement.get("item_id", "")) != item_id or str(movement.get("movement_type", "")) != "Salida":
            continue
        created = _dt(movement.get("created_at_utc", movement.get("date")))
        if created and created >= cutoff:
            total += _num(movement.get("quantity"))
        if created and (last is None or created > last):
            last = created
    return total / 90.0, last


def _policy(item_id: str, rows: list[dict]) -> dict:
    return next((row for row in rows if str(row.get("item_id", "")) == item_id), {})


def _save_policy(item_id: str, values: dict) -> None:
    rows = _rows("inventory_policies")
    found = False
    updated = []
    for row in rows:
        current = dict(row)
        if str(current.get("item_id", "")) == item_id:
            current.update(values)
            current["updated_at_utc"] = _now()
            found = True
        updated.append(current)
    if not found:
        updated.append({"item_id": item_id, **values, "created_at_utc": _now()})
    _save("inventory_policies", updated)


def _analysis(items: list[dict], reservations: list[dict], movements: list[dict], policies: list[dict]) -> list[dict]:
    result = []
    for item in items:
        item_id = str(item.get("item_id", ""))
        free = max(_available(item) - _reserved(item_id, reservations), 0.0)
        daily, last = _consumption(item_id, movements)
        policy = _policy(item_id, policies)
        lead = max(int(_num(policy.get("lead_time_days"), 7)), 0)
        safety = max(int(_num(policy.get("safety_days"), 7)), 0)
        review = max(int(_num(policy.get("review_period_days"), 14)), 1)
        reorder = max(_num(item.get("reorder_point")), daily * (lead + safety))
        target = daily * (lead + safety + review)
        suggested = max(target - free, 0.0) if free <= reorder else 0.0
        result.append({
            "item": item,
            "item_id": item_id,
            "free": free,
            "daily": daily,
            "last": last,
            "lead": lead,
            "reorder": reorder,
            "target": target,
            "suggested": suggested,
            "coverage": free / daily if daily > 0 else None,
            "value": _available(item) * _unit_cost(item),
            "supplier": str(policy.get("preferred_supplier", "")),
        })
    return result


def _abc(rows: list[dict]) -> dict[str, str]:
    total = sum(row["value"] for row in rows)
    running = 0.0
    output = {}
    for row in sorted(rows, key=lambda item: item["value"], reverse=True):
        running += row["value"]
        ratio = running / total if total else 0.0
        output[row["item_id"]] = "A" if ratio <= 0.80 else "B" if ratio <= 0.95 else "C"
    return output


def _csv(rows: list[dict], classes: dict[str, str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Material", "ABC", "Libre", "Consumo diario", "Cobertura", "Reposición", "Compra sugerida", "Proveedor", "Valor"])
    for row in rows:
        writer.writerow([row["item_id"], row["item"].get("name", ""), classes.get(row["item_id"], "C"), row["free"], row["daily"], row["coverage"] if row["coverage"] is not None else "", row["reorder"], row["suggested"], row["supplier"], row["value"]])
    return buffer.getvalue().encode("utf-8-sig")


def render_inventory_planning() -> None:
    render_page_header("Inventario", "Planifica compras, clasifica materiales y detecta existencias sin movimiento.")
    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_inventory_plus()
    finally:
        base.render_page_header = original_header

    items = _rows("inventory_registry")
    reservations = _rows("inventory_reservations")
    movements = _rows("inventory_movements")
    policies = _rows("inventory_policies")
    suggestions = _rows("inventory_restock_suggestions")
    rows = _analysis(items, reservations, movements, policies)
    classes = _abc(rows)
    pending = [row for row in rows if row["suggested"] > 0]
    slow = [row for row in rows if row["value"] > 0 and (row["last"] is None or (datetime.now() - row["last"]).days > 90)]
    excess = [row for row in rows if row["coverage"] is not None and row["coverage"] > 180]

    st.divider()
    metrics = st.columns(5)
    metrics[0].metric("Reposiciones", str(len(pending)))
    metrics[1].metric("Sin movimiento", str(len(slow)))
    metrics[2].metric("Exceso >180 días", str(len(excess)))
    metrics[3].metric("Capital inmóvil", format_money(sum(row["value"] for row in slow)))
    metrics[4].metric("Materiales A", str(sum(1 for value in classes.values() if value == "A")))

    restock_tab, abc_tab, slow_tab, policy_tab, request_tab = st.tabs(("Reposición", "ABC", "Sin movimiento", "Políticas", "Solicitudes"))

    with restock_tab:
        if not pending:
            st.success("No hay compras sugeridas.")
        for row in sorted(pending, key=lambda item: item["coverage"] if item["coverage"] is not None else 999999):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1, 1])
                cols[0].markdown(f"**{row['item'].get('name', 'Material')}**")
                cols[0].caption(f"Proveedor: {row['supplier'] or 'Sin definir'} · entrega {row['lead']} día(s)")
                cols[1].metric("Libre", f"{row['free']:,.2f}")
                cols[2].metric("Consumo/día", f"{row['daily']:,.2f}")
                cols[3].metric("Cobertura", f"{row['coverage']:,.1f} días" if row["coverage"] is not None else "Sin consumo")
                cols[4].metric("Comprar", f"{row['suggested']:,.2f}")
                if st.button("Crear solicitud", key=f"restock_{row['item_id']}", use_container_width=True):
                    duplicate = any(str(item.get("item_id", "")) == row["item_id"] and item.get("status") == "Pendiente" for item in suggestions)
                    if duplicate:
                        st.warning("Ya existe una solicitud pendiente.")
                    else:
                        suggestions.append({
                            "suggestion_id": f"REP-{uuid4().hex[:8].upper()}",
                            "item_id": row["item_id"],
                            "item_name": str(row["item"].get("name", "Material")),
                            "quantity": round(row["suggested"], 4),
                            "preferred_supplier": row["supplier"],
                            "estimated_cost": round(row["suggested"] * _unit_cost(row["item"]), 4),
                            "status": "Pendiente",
                            "created_at_utc": _now(),
                        })
                        _save("inventory_restock_suggestions", suggestions)
                        st.rerun()

    with abc_tab:
        st.caption("A concentra cerca del 80% del valor, B el siguiente 15% y C el resto.")
        for class_name in ("A", "B", "C"):
            st.markdown(f"#### Clase {class_name}")
            group = [row for row in rows if classes.get(row["item_id"]) == class_name]
            if not group:
                st.info("Sin materiales.")
            for row in sorted(group, key=lambda item: item["value"], reverse=True):
                st.write(f"**{row['item'].get('name', 'Material')}** · {format_money(row['value'])} · libre {row['free']:,.2f}")

    with slow_tab:
        display = slow + [row for row in excess if row not in slow]
        if not display:
            st.success("No se detectan existencias inmovilizadas o excesivas.")
        for row in display:
            last = row["last"].date().isoformat() if row["last"] else "Nunca"
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{row['item'].get('name', 'Material')}**")
                cols[0].caption(f"Última salida: {last}")
                cols[1].metric("Valor", format_money(row["value"]))
                cols[2].metric("Libre", f"{row['free']:,.2f}")
                cols[3].metric("Cobertura", f"{row['coverage']:,.1f} días" if row["coverage"] is not None else "Sin consumo")

    with policy_tab:
        options = {f"{item.get('name', 'Material')} · {item.get('item_id', '')}": str(item.get("item_id", "")) for item in items}
        if not options:
            st.info("No hay materiales.")
        else:
            selected = st.selectbox("Material", tuple(options.keys()))
            item_id = options[selected]
            current = _policy(item_id, policies)
            with st.form("inventory_policy_form"):
                cols = st.columns(4)
                supplier = cols[0].text_input("Proveedor preferido", value=str(current.get("preferred_supplier", "")))
                lead = cols[1].number_input("Entrega (días)", min_value=0, value=int(_num(current.get("lead_time_days"), 7)), step=1)
                safety = cols[2].number_input("Seguridad (días)", min_value=0, value=int(_num(current.get("safety_days"), 7)), step=1)
                review = cols[3].number_input("Revisión (días)", min_value=1, value=int(_num(current.get("review_period_days"), 14)), step=1)
                responsible = st.text_input("Responsable")
                submitted = st.form_submit_button("Guardar política", type="primary", use_container_width=True)
            if submitted:
                _save_policy(item_id, {"preferred_supplier": supplier.strip(), "lead_time_days": int(lead), "safety_days": int(safety), "review_period_days": int(review), "responsible": responsible.strip() or "Sin asignar"})
                st.rerun()

    with request_tab:
        if not suggestions:
            st.info("No hay solicitudes.")
        for suggestion in reversed(suggestions[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{suggestion.get('suggestion_id', '')} · {suggestion.get('item_name', '')}**")
                cols[0].caption(str(suggestion.get("preferred_supplier") or "Sin proveedor"))
                cols[1].metric("Cantidad", f"{_num(suggestion.get('quantity')):,.2f}")
                cols[2].metric("Estimado", format_money(_num(suggestion.get("estimated_cost"))))
                cols[3].metric("Estado", str(suggestion.get("status", "Pendiente")))
                if suggestion.get("status") == "Pendiente" and st.button("Marcar gestionada", key=f"manage_{suggestion.get('suggestion_id')}", use_container_width=True):
                    changed = []
                    for current in suggestions:
                        row = dict(current)
                        if row.get("suggestion_id") == suggestion.get("suggestion_id"):
                            row["status"] = "Gestionada"
                            row["managed_at_utc"] = _now()
                        changed.append(row)
                    _save("inventory_restock_suggestions", changed)
                    st.rerun()

    if rows:
        st.download_button("Descargar planeación CSV", data=_csv(rows, classes), file_name=f"planeacion_inventario_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True)

    render_info_card("Comprar con criterio", "La reposición usa consumo, reservas, plazo de entrega, revisión y stock de seguridad.", "PLANEACIÓN")
