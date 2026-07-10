"""BOM multinivel para recetas dentro de recetas."""

from datetime import date
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database
from src.money import format_money, get_currency


def _ensure_tables() -> None:
    initialize_database()
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS recipe_components (
                component_id TEXT PRIMARY KEY,
                parent_recipe_id TEXT NOT NULL,
                child_recipe_id TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                waste_percent REAL NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recipe_versions (
                version_id TEXT PRIMARY KEY,
                recipe_id TEXT NOT NULL,
                version_name TEXT NOT NULL,
                change_note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Borrador',
                created_at_utc TEXT NOT NULL
            );
            """
        )


def _rows(table: str) -> list[dict]:
    _ensure_tables()
    with connect() as conn:
        result = conn.execute("SELECT * FROM " + table + " ORDER BY created_at_utc DESC").fetchall()
    return [dict(row) for row in result]


def _insert(table: str, values: dict) -> None:
    _ensure_tables()
    cols = list(values.keys())
    sql = "INSERT INTO " + table + " (" + ", ".join(cols) + ") VALUES (" + ", ".join("?" for _ in cols) + ")"
    with connect() as conn:
        conn.execute(sql, tuple(values[col] for col in cols))


def _money(value: float) -> str:
    return format_money(float(value or 0), get_currency())


def _step_cost(recipe_id: str) -> float:
    materials = {row["material_id"]: row for row in _rows("production_materials")}
    machines = {row["machine_id"]: row for row in _rows("production_machines")}
    consumables = _rows("machine_consumables")
    total = 0.0
    for step in [row for row in _rows("recipe_steps") if row.get("recipe_id") == recipe_id]:
        material_id = str(step.get("material_id") or "")
        if material_id in materials:
            material = materials[material_id]
            total += float(step.get("material_quantity") or 0) * float(material.get("unit_cost") or 0) * (1 + float(material.get("waste_percent") or 0) / 100.0)
        machine_id = str(step.get("machine_id") or "")
        minutes = float(step.get("machine_minutes") or 0)
        if machine_id in machines and minutes:
            machine = machines[machine_id]
            hours = minutes / 60.0
            hourly = float(machine.get("acquisition_cost") or 0) / max(float(machine.get("useful_life_hours") or 1), 1) + float(machine.get("maintenance_cost_per_hour") or 0)
            total += hours * hourly
            total += hours * float(machine.get("power_kw") or 0) * float(step.get("electricity_rate_per_kwh") or 0)
            for item in consumables:
                if str(item.get("machine_id") or "") == machine_id and item.get("active", 1):
                    total += float(item.get("replacement_cost") or 0) / max(float(item.get("useful_life_units") or 1), 1)
        total += float(step.get("labor_minutes") or 0) / 60.0 * float(step.get("labor_rate_per_hour") or 0)
    return total


def _recipe_total(recipe_id: str, depth: int = 0, path: tuple[str, ...] = ()) -> tuple[float, list[str]]:
    if depth > 8:
        return 0.0, ["Profundidad máxima alcanzada"]
    if recipe_id in path:
        return 0.0, ["Ciclo detectado: " + " > ".join((*path, recipe_id))]
    total = _step_cost(recipe_id)
    warnings: list[str] = []
    for component in [row for row in _rows("recipe_components") if row.get("parent_recipe_id") == recipe_id and row.get("active", 1)]:
        child_total, child_warnings = _recipe_total(str(component.get("child_recipe_id")), depth + 1, (*path, recipe_id))
        total += child_total * float(component.get("quantity") or 1) * (1 + float(component.get("waste_percent") or 0) / 100.0)
        warnings.extend(child_warnings)
    return total, warnings


def _recipe_name(recipe_id: str, recipes: list[dict]) -> str:
    for recipe in recipes:
        if str(recipe.get("recipe_id")) == str(recipe_id):
            return str(recipe.get("name", "Receta"))
    return "Receta"


def _export_components(components: list[dict], recipes: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Padre", "Componente", "Cantidad", "Merma %", "Notas", "Activo"])
    for row in components:
        writer.writerow([
            _recipe_name(str(row.get("parent_recipe_id", "")), recipes),
            _recipe_name(str(row.get("child_recipe_id", "")), recipes),
            row.get("quantity", 0),
            row.get("waste_percent", 0),
            row.get("notes", ""),
            row.get("active", 1),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_bom_multilevel() -> None:
    render_page_header("BOM multinivel", "Permite que una receta use otras recetas como subensambles.")
    _ensure_tables()

    recipes = _rows("product_recipes")
    components = _rows("recipe_components")
    versions = _rows("recipe_versions")
    active_components = [row for row in components if row.get("active", 1)]

    cols = st.columns(5)
    cols[0].metric("Recetas", str(len(recipes)))
    cols[1].metric("Componentes", str(len(active_components)))
    cols[2].metric("Versiones", str(len(versions)))
    totals = [_recipe_total(str(row.get("recipe_id")))[0] for row in recipes]
    cols[3].metric("Costo promedio", _money(sum(totals) / len(totals) if totals else 0))
    cycles = sum(1 for recipe in recipes if _recipe_total(str(recipe.get("recipe_id")))[1])
    cols[4].metric("Alertas", str(cycles))

    link_tab, tree_tab, version_tab, export_tab = st.tabs(("Componentes", "Árbol y costos", "Versiones", "Exportar"))

    with link_tab:
        if len(recipes) < 2:
            st.info("Necesitas al menos dos recetas para crear un BOM multinivel.")
        else:
            options = {f"{row.get('name')} · {row.get('recipe_id')}": row for row in recipes}
            with st.form("bom_component_form", clear_on_submit=True):
                parent_label = st.selectbox("Receta padre", tuple(options.keys()))
                child_label = st.selectbox("Subreceta / componente", tuple(options.keys()))
                quantity = st.number_input("Cantidad", min_value=0.01, value=1.0, step=1.0)
                waste = st.number_input("Merma %", min_value=0.0, value=0.0, step=0.5)
                notes = st.text_input("Notas")
                submitted = st.form_submit_button("Agregar componente", type="primary", use_container_width=True)
            if submitted:
                parent = options[parent_label]
                child = options[child_label]
                if parent.get("recipe_id") == child.get("recipe_id"):
                    st.error("Una receta no puede contenerse a sí misma.")
                else:
                    _insert("recipe_components", {
                        "component_id": f"CMP-{uuid4().hex[:8].upper()}",
                        "parent_recipe_id": parent.get("recipe_id"),
                        "child_recipe_id": child.get("recipe_id"),
                        "quantity": float(quantity),
                        "waste_percent": float(waste),
                        "notes": notes.strip(),
                        "active": 1,
                        "created_at_utc": date.today().isoformat(),
                    })
                    st.rerun()
        for row in active_components[:100]:
            st.write(f"**{_recipe_name(row.get('parent_recipe_id', ''), recipes)}** contiene **{_recipe_name(row.get('child_recipe_id', ''), recipes)}** · x{row.get('quantity')} · merma {row.get('waste_percent')}%")

    with tree_tab:
        if not recipes:
            st.info("No hay recetas registradas.")
        else:
            options = {f"{row.get('name')} · {row.get('recipe_id')}": row for row in recipes}
            selected = st.selectbox("Receta", tuple(options.keys()))
            recipe = options[selected]
            recipe_id = str(recipe.get("recipe_id"))
            total, warnings = _recipe_total(recipe_id)
            price = total * (1 + float(recipe.get("target_margin_percent") or 0) / 100.0)
            m = st.columns(3)
            m[0].metric("Costo total", _money(total))
            m[1].metric("Margen", f"{float(recipe.get('target_margin_percent') or 0):,.1f}%")
            m[2].metric("Precio sugerido", _money(price))
            if warnings:
                for warning in warnings:
                    st.error(warning)
            st.markdown("#### Componentes directos")
            direct = [row for row in active_components if row.get("parent_recipe_id") == recipe_id]
            if not direct:
                st.info("Esta receta no tiene subrecetas directas.")
            for row in direct:
                child_id = str(row.get("child_recipe_id"))
                child_total, child_warnings = _recipe_total(child_id)
                subtotal = child_total * float(row.get("quantity") or 1) * (1 + float(row.get("waste_percent") or 0) / 100.0)
                st.write(f"**{_recipe_name(child_id, recipes)}** · costo unidad {_money(child_total)} · subtotal {_money(subtotal)}")
                for warning in child_warnings:
                    st.warning(warning)

    with version_tab:
        if not recipes:
            st.info("No hay recetas para versionar.")
        else:
            options = {f"{row.get('name')} · {row.get('recipe_id')}": row for row in recipes}
            with st.form("recipe_version_form", clear_on_submit=True):
                selected = st.selectbox("Receta", tuple(options.keys()), key="version_recipe")
                version_name = st.text_input("Versión", placeholder="v1, regreso a clases, premium")
                status = st.selectbox("Estado", ("Borrador", "Aprobada", "Obsoleta"))
                note = st.text_area("Cambio realizado", max_chars=500)
                submitted = st.form_submit_button("Guardar versión", type="primary", use_container_width=True)
            if submitted:
                if not version_name.strip():
                    st.error("Nombre de versión obligatorio.")
                else:
                    recipe = options[selected]
                    _insert("recipe_versions", {
                        "version_id": f"VER-{uuid4().hex[:8].upper()}",
                        "recipe_id": recipe.get("recipe_id"),
                        "version_name": version_name.strip(),
                        "change_note": note.strip(),
                        "status": status,
                        "created_at_utc": date.today().isoformat(),
                    })
                    st.rerun()
        for row in versions[:100]:
            st.write(f"**{_recipe_name(row.get('recipe_id', ''), recipes)} · {row.get('version_name')}** · {row.get('status')} — {row.get('change_note', '')}")

    with export_tab:
        st.download_button("Descargar componentes CSV", data=_export_components(active_components, recipes), file_name="bom_multinivel.csv", mime="text/csv", use_container_width=True, disabled=not active_components)
        render_info_card("Uso recomendado", "Crea subrecetas como impresión base, corte, foil o empaque y reutilízalas dentro de productos más complejos.", "BOM")

    render_info_card("Recetas dentro de recetas", "El costo ahora puede sumar subensambles completos sin duplicar pasos productivos.", "FASE 3")


app_shell.FUNCTIONAL_MODULES["BOM multinivel"] = render_bom_multilevel
