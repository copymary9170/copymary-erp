"""BOM multinivel para producción.

Permite declarar subrecetas, versiones y explosión de necesidades sin tocar
la lógica existente de costeo por procesos.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


STATUSES = ("Borrador", "Activa", "Obsoleta")


def _activate_backup() -> None:
    for section, label in (
        ("bom_recipe_versions", "Versiones de recetas BOM"),
        ("bom_subrecipes", "Subrecetas BOM multinivel"),
        ("bom_explosions", "Explosiones BOM"),
        ("bom_change_logs", "Cambios de BOM"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _recipe_rows() -> list[dict]:
    recipes = _rows("product_recipes")
    if recipes:
        return recipes
    return _rows("production_recipes")


def _recipe_label(recipe: dict) -> str:
    return f"{recipe.get('name', 'Receta')} · {recipe.get('recipe_id', '')}"


def _recipe_name(recipe_id: str, recipes: list[dict]) -> str:
    for recipe in recipes:
        if str(recipe.get("recipe_id", "")) == recipe_id:
            return str(recipe.get("name", "Receta"))
    return "Receta"


def _unit_cost(recipe_id: str) -> float:
    jobs = [row for row in _rows("costed_jobs") if str(row.get("recipe_id", "")) == recipe_id]
    if jobs:
        latest = sorted(jobs, key=lambda row: str(row.get("created_at_utc", "")), reverse=True)[0]
        qty = max(_num(latest.get("quantity"), 1.0), 1.0)
        return _num(latest.get("cost_total")) / qty
    for recipe in _recipe_rows():
        if str(recipe.get("recipe_id", "")) == recipe_id:
            return _num(recipe.get("estimated_unit_cost"), 0.0)
    return 0.0


def _children(parent_id: str, links: list[dict]) -> list[dict]:
    return [row for row in links if row.get("parent_recipe_id") == parent_id and row.get("active", True)]


def _has_cycle(parent_id: str, child_id: str, links: list[dict]) -> bool:
    if parent_id == child_id:
        return True
    stack = [child_id]
    seen = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for link in _children(current, links):
            next_child = str(link.get("child_recipe_id", ""))
            if next_child == parent_id:
                return True
            stack.append(next_child)
    return False


def _explode(recipe_id: str, quantity: float, links: list[dict], level: int = 0, path: tuple[str, ...] = ()) -> list[dict]:
    if recipe_id in path or level > 10:
        return [{"level": level, "recipe_id": recipe_id, "quantity": quantity, "warning": "Ciclo o profundidad excesiva", "unit_cost": 0.0, "total_cost": 0.0}]
    output = []
    children = _children(recipe_id, links)
    if not children:
        unit_cost = _unit_cost(recipe_id)
        return [{"level": level, "recipe_id": recipe_id, "quantity": quantity, "warning": "", "unit_cost": unit_cost, "total_cost": unit_cost * quantity}]
    for child in children:
        child_id = str(child.get("child_recipe_id", ""))
        child_qty = quantity * _num(child.get("quantity"), 1.0)
        output.append({"level": level + 1, "recipe_id": child_id, "quantity": child_qty, "warning": str(child.get("note", "")), "unit_cost": _unit_cost(child_id), "total_cost": _unit_cost(child_id) * child_qty})
        output.extend(_explode(child_id, child_qty, links, level + 1, (*path, recipe_id)))
    return output


def _export(rows: list[dict], recipes: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Nivel", "Receta", "ID", "Cantidad", "Costo unitario", "Costo total", "Nota"])
    for row in rows:
        writer.writerow([row.get("level", 0), _recipe_name(str(row.get("recipe_id", "")), recipes), row.get("recipe_id", ""), row.get("quantity", 0), row.get("unit_cost", 0), row.get("total_cost", 0), row.get("warning", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_bom_multilevel() -> None:
    render_page_header("BOM multinivel", "Recetas dentro de recetas, versiones, subensambles y explosión de necesidades.")

    recipes = _recipe_rows()
    versions = _rows("bom_recipe_versions")
    links = _rows("bom_subrecipes")
    explosions = _rows("bom_explosions")
    changes = _rows("bom_change_logs")
    active_links = [row for row in links if row.get("active", True)]
    parents = {row.get("parent_recipe_id") for row in active_links}
    children = {row.get("child_recipe_id") for row in active_links}

    metrics = st.columns(5)
    metrics[0].metric("Recetas", str(len(recipes)))
    metrics[1].metric("Versiones", str(len(versions)))
    metrics[2].metric("Subrecetas", str(len(active_links)))
    metrics[3].metric("Padres", str(len(parents)))
    metrics[4].metric("Subensambles", str(len(children)))

    version_tab, link_tab, explosion_tab, change_tab = st.tabs(("Versiones", "Subrecetas", "Explosión", "Cambios"))

    with version_tab:
        if not recipes:
            st.info("Primero registra recetas en Costeo por procesos.")
        else:
            recipe_options = {_recipe_label(row): row for row in recipes}
            with st.form("bom_version_form", clear_on_submit=True):
                selected = st.selectbox("Receta", tuple(recipe_options.keys()))
                version_name = st.text_input("Versión", placeholder="v1, v2, escolar 2026...")
                status = st.selectbox("Estado", STATUSES)
                responsible = st.text_input("Responsable")
                notes = st.text_area("Cambios / motivo", max_chars=700)
                submitted = st.form_submit_button("Guardar versión", type="primary", use_container_width=True)
            if submitted:
                if not version_name.strip() or not responsible.strip():
                    st.error("Versión y responsable son obligatorios.")
                else:
                    recipe = recipe_options[selected]
                    if status == "Activa":
                        for item in versions:
                            if item.get("recipe_id") == recipe.get("recipe_id"):
                                item["status"] = "Obsoleta"
                    versions.append({"version_id": f"BOV-{uuid4().hex[:8].upper()}", "recipe_id": recipe.get("recipe_id"), "version_name": version_name.strip(), "status": status, "responsible": responsible.strip(), "notes": notes.strip(), "created_at_utc": _now()})
                    changes.append({"change_id": f"BOC-{uuid4().hex[:8].upper()}", "recipe_id": recipe.get("recipe_id"), "action": f"Versión {version_name} creada", "responsible": responsible.strip(), "note": notes.strip(), "created_at_utc": _now()})
                    _save("bom_recipe_versions", versions)
                    _save("bom_change_logs", changes)
                    st.rerun()
        for item in reversed(versions[-100:]):
            st.write(f"**{_recipe_name(str(item.get('recipe_id', '')), recipes)} · {item.get('version_name')}** · {item.get('status')} · {item.get('responsible')}")

    with link_tab:
        if len(recipes) < 2:
            st.info("Necesitas al menos dos recetas para crear BOM multinivel.")
        else:
            recipe_options = {_recipe_label(row): row for row in recipes}
            with st.form("bom_subrecipe_form", clear_on_submit=True):
                parent_label = st.selectbox("Receta padre", tuple(recipe_options.keys()))
                child_label = st.selectbox("Subreceta / componente", tuple(recipe_options.keys()))
                quantity = st.number_input("Cantidad requerida", min_value=0.0001, value=1.0, step=1.0)
                responsible = st.text_input("Responsable")
                note = st.text_input("Nota")
                submitted = st.form_submit_button("Agregar subreceta", type="primary", use_container_width=True)
            if submitted:
                parent = recipe_options[parent_label]
                child = recipe_options[child_label]
                parent_id = str(parent.get("recipe_id", ""))
                child_id = str(child.get("recipe_id", ""))
                if not responsible.strip():
                    st.error("Responsable obligatorio.")
                elif _has_cycle(parent_id, child_id, links):
                    st.error("No se puede crear: generaría un ciclo en el BOM.")
                else:
                    links.append({"link_id": f"BOL-{uuid4().hex[:8].upper()}", "parent_recipe_id": parent_id, "child_recipe_id": child_id, "quantity": float(quantity), "responsible": responsible.strip(), "note": note.strip(), "active": True, "created_at_utc": _now()})
                    changes.append({"change_id": f"BOC-{uuid4().hex[:8].upper()}", "recipe_id": parent_id, "action": f"Subreceta agregada: {child_id}", "responsible": responsible.strip(), "note": note.strip(), "created_at_utc": _now()})
                    _save("bom_subrecipes", links)
                    _save("bom_change_logs", changes)
                    st.rerun()
        for link in reversed(active_links[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{_recipe_name(str(link.get('parent_recipe_id', '')), recipes)}** usa **{_recipe_name(str(link.get('child_recipe_id', '')), recipes)}**")
                cols[0].caption(f"Cantidad {link.get('quantity')} · {link.get('responsible')} · {link.get('note', '')}")
                cols[1].metric("Costo comp.", format_money(_unit_cost(str(link.get("child_recipe_id", ""))), get_currency()))
                if cols[2].button("Desactivar", key=f"disable_bom_link_{link.get('link_id')}", use_container_width=True):
                    changed = []
                    for row in links:
                        current = dict(row)
                        if current.get("link_id") == link.get("link_id"):
                            current["active"] = False
                            current["ended_at_utc"] = _now()
                        changed.append(current)
                    _save("bom_subrecipes", changed)
                    st.rerun()

    with explosion_tab:
        if not recipes:
            st.info("No hay recetas.")
        else:
            recipe_options = {_recipe_label(row): row for row in recipes}
            selected = st.selectbox("Receta a explotar", tuple(recipe_options.keys()))
            quantity = st.number_input("Cantidad final", min_value=1.0, value=1.0, step=1.0)
            recipe = recipe_options[selected]
            explosion = _explode(str(recipe.get("recipe_id", "")), float(quantity), links)
            total = sum(_num(row.get("total_cost")) for row in explosion if not row.get("warning", "").startswith("Ciclo"))
            st.metric("Costo multinivel estimado", format_money(total, get_currency()))
            st.download_button("Descargar explosión CSV", data=_export(explosion, recipes), file_name="explosion_bom.csv", mime="text/csv", use_container_width=True)
            if st.button("Guardar explosión", type="primary", use_container_width=True):
                explosions.append({"explosion_id": f"BOX-{uuid4().hex[:8].upper()}", "recipe_id": recipe.get("recipe_id"), "quantity": float(quantity), "estimated_cost": float(total), "lines": explosion, "created_at_utc": _now()})
                _save("bom_explosions", explosions)
                st.rerun()
            for row in explosion:
                indent = " " * int(row.get("level", 0))
                st.write(f"{indent}**{_recipe_name(str(row.get('recipe_id', '')), recipes)}** · cant. {row.get('quantity')} · costo {format_money(_num(row.get('total_cost')), get_currency())} {row.get('warning', '')}")

    with change_tab:
        for item in reversed(changes[-150:]):
            st.write(f"**{item.get('action')}** · {_recipe_name(str(item.get('recipe_id', '')), recipes)} · {item.get('responsible')} · {item.get('created_at_utc')}")

    render_info_card("BOM multinivel", "Ahora una receta puede contener otras recetas. Esto prepara consumo de inventario, subensambles y costo real.", "PRODUCCIÓN")


app_shell.FUNCTIONAL_MODULES["BOM multinivel"] = render_bom_multilevel
