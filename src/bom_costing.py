"""Costeo inicial por recetas BOM."""

from datetime import date
from uuid import uuid4
import json

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database
from src.money import format_money, get_currency


TABLES = {
    "materials": "production_materials",
    "machines": "production_machines",
    "consumables": "machine_consumables",
    "recipes": "product_recipes",
    "steps": "recipe_steps",
    "jobs": "costed_jobs",
}


def _rows(table_name: str) -> list[dict]:
    initialize_database()
    query = "SELECT * FROM " + table_name + " ORDER BY created_at_utc DESC"
    with connect() as conn:
        rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def _insert(table_name: str, values: dict) -> None:
    initialize_database()
    columns = list(values.keys())
    sql = "INSERT INTO " + table_name + " (" + ", ".join(columns) + ") VALUES (" + ", ".join("?" for _ in columns) + ")"
    with connect() as conn:
        conn.execute(sql, tuple(values[col] for col in columns))


def _money(value) -> str:
    return format_money(float(value or 0), get_currency())


def _step_total(step: dict, materials: dict, machines: dict, consumables: list[dict]) -> dict:
    material_cost = 0.0
    material_id = str(step.get("material_id") or "")
    if material_id in materials:
        material = materials[material_id]
        waste = float(material.get("waste_percent") or 0) / 100.0
        material_cost = float(step.get("material_quantity") or 0) * float(material.get("unit_cost") or 0) * (1 + waste)

    machine_cost = 0.0
    energy_cost = 0.0
    consumable_cost = 0.0
    machine_id = str(step.get("machine_id") or "")
    minutes = float(step.get("machine_minutes") or 0)
    if machine_id in machines:
        machine = machines[machine_id]
        hours = minutes / 60.0
        useful_hours = max(float(machine.get("useful_life_hours") or 1), 1)
        hourly = float(machine.get("acquisition_cost") or 0) / useful_hours + float(machine.get("maintenance_cost_per_hour") or 0)
        machine_cost = hours * hourly
        energy_cost = hours * float(machine.get("power_kw") or 0) * float(step.get("electricity_rate_per_kwh") or 0)
        for item in consumables:
            if str(item.get("machine_id") or "") == machine_id and item.get("active", 1):
                consumable_cost += float(item.get("replacement_cost") or 0) / max(float(item.get("useful_life_units") or 1), 1)

    labor_cost = float(step.get("labor_minutes") or 0) / 60.0 * float(step.get("labor_rate_per_hour") or 0)
    total = material_cost + machine_cost + energy_cost + consumable_cost + labor_cost
    return {"material": material_cost, "machine": machine_cost, "energy": energy_cost, "consumable": consumable_cost, "labor": labor_cost, "total": total}


def _recipe_total(recipe_id: str) -> tuple[float, list[dict]]:
    materials = {row["material_id"]: row for row in _rows(TABLES["materials"])}
    machines = {row["machine_id"]: row for row in _rows(TABLES["machines"])}
    consumables = _rows(TABLES["consumables"])
    steps = [row for row in _rows(TABLES["steps"]) if row.get("recipe_id") == recipe_id]
    details = []
    total = 0.0
    for step in sorted(steps, key=lambda row: int(row.get("step_order") or 0)):
        cost = _step_total(step, materials, machines, consumables)
        total += cost["total"]
        details.append({"process": step.get("process_type"), **cost})
    return total, details


def render_bom_costing() -> None:
    render_page_header("Costeo por procesos", "Recetas con materiales, máquinas, consumibles, electricidad y mano de obra.")
    initialize_database()

    materials = _rows(TABLES["materials"])
    machines = _rows(TABLES["machines"])
    consumables = _rows(TABLES["consumables"])
    recipes = _rows(TABLES["recipes"])
    steps = _rows(TABLES["steps"])

    cols = st.columns(5)
    cols[0].metric("Materiales", str(len(materials)))
    cols[1].metric("Máquinas", str(len(machines)))
    cols[2].metric("Consumibles", str(len(consumables)))
    cols[3].metric("Recetas", str(len(recipes)))
    cols[4].metric("Pasos", str(len(steps)))

    mat_tab, mac_tab, con_tab, rec_tab, step_tab, quote_tab = st.tabs(("Materiales", "Máquinas", "Consumibles", "Recetas", "Pasos", "Cotizar"))

    with mat_tab:
        with st.form("bom_material_form", clear_on_submit=True):
            name = st.text_input("Material")
            category = st.text_input("Categoría", value="Papel")
            unit = st.selectbox("Unidad", ("hoja", "unidad", "cm2", "m2", "metro", "ml", "gramo"))
            unit_cost = st.number_input("Costo unitario", min_value=0.0, value=0.0, step=0.1)
            waste = st.number_input("Merma %", min_value=0.0, value=0.0, step=0.5)
            use_type = st.selectbox("Uso", ("insumo", "reventa", "mixto"))
            submitted = st.form_submit_button("Guardar material", type="primary", use_container_width=True)
        if submitted:
            if not name.strip() or unit_cost <= 0:
                st.error("Material y costo son obligatorios.")
            else:
                _insert(TABLES["materials"], {"material_id": f"MAT-{uuid4().hex[:8].upper()}", "name": name.strip(), "category": category.strip(), "unit": unit, "unit_cost": float(unit_cost), "currency": get_currency(), "waste_percent": float(waste), "use_type": use_type, "active": 1, "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in materials[:60]:
            st.write(f"**{row.get('name')}** · {_money(row.get('unit_cost'))}/{row.get('unit')} · merma {row.get('waste_percent')}%")

    with mac_tab:
        with st.form("bom_machine_form", clear_on_submit=True):
            name = st.text_input("Máquina")
            category = st.text_input("Tipo", value="Impresora")
            acquisition = st.number_input("Costo adquisición", min_value=0.0, value=0.0, step=10.0)
            hours = st.number_input("Vida útil horas", min_value=1.0, value=1000.0, step=10.0)
            power = st.number_input("Consumo kW", min_value=0.0, value=0.0, step=0.1)
            maintenance = st.number_input("Mantenimiento por hora", min_value=0.0, value=0.0, step=0.1)
            submitted = st.form_submit_button("Guardar máquina", type="primary", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("Nombre obligatorio.")
            else:
                _insert(TABLES["machines"], {"machine_id": f"MAC-{uuid4().hex[:8].upper()}", "name": name.strip(), "category": category.strip(), "acquisition_cost": float(acquisition), "useful_life_hours": float(hours), "power_kw": float(power), "maintenance_cost_per_hour": float(maintenance), "active": 1, "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in machines[:60]:
            hourly = float(row.get("acquisition_cost") or 0) / max(float(row.get("useful_life_hours") or 1), 1) + float(row.get("maintenance_cost_per_hour") or 0)
            st.write(f"**{row.get('name')}** · costo hora {_money(hourly)} · {row.get('power_kw')} kW")

    with con_tab:
        if not machines:
            st.info("Primero registra máquinas.")
        else:
            machine_options = {f"{row.get('name')} · {row.get('machine_id')}": row for row in machines}
            with st.form("bom_consumable_form", clear_on_submit=True):
                selected = st.selectbox("Máquina", tuple(machine_options.keys()))
                name = st.text_input("Consumible")
                unit = st.selectbox("Unidad de vida", ("corte", "metro", "hora", "unidad"))
                cost = st.number_input("Costo reposición", min_value=0.0, value=0.0, step=1.0)
                life = st.number_input("Vida útil", min_value=1.0, value=100.0, step=1.0)
                submitted = st.form_submit_button("Guardar consumible", type="primary", use_container_width=True)
            if submitted:
                machine = machine_options[selected]
                _insert(TABLES["consumables"], {"consumable_id": f"CON-{uuid4().hex[:8].upper()}", "machine_id": machine.get("machine_id"), "name": name.strip(), "unit": unit, "replacement_cost": float(cost), "useful_life_units": float(life), "active": 1, "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in consumables[:60]:
            per_use = float(row.get("replacement_cost") or 0) / max(float(row.get("useful_life_units") or 1), 1)
            st.write(f"**{row.get('name')}** · costo por uso {_money(per_use)}")

    with rec_tab:
        with st.form("bom_recipe_form", clear_on_submit=True):
            name = st.text_input("Producto / receta")
            category = st.text_input("Categoría", value="Papelería creativa")
            margin = st.number_input("Margen %", min_value=0.0, value=40.0, step=1.0)
            submitted = st.form_submit_button("Guardar receta", type="primary", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("Nombre obligatorio.")
            else:
                _insert(TABLES["recipes"], {"recipe_id": f"REC-{uuid4().hex[:8].upper()}", "name": name.strip(), "category": category.strip(), "target_margin_percent": float(margin), "active": 1, "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in recipes[:60]:
            total, _details = _recipe_total(row.get("recipe_id"))
            price = total * (1 + float(row.get("target_margin_percent") or 0) / 100.0)
            st.write(f"**{row.get('name')}** · costo {_money(total)} · precio {_money(price)}")

    with step_tab:
        if not recipes:
            st.info("Primero registra una receta.")
        else:
            recipe_options = {f"{row.get('name')} · {row.get('recipe_id')}": row for row in recipes}
            material_options = {"Sin material": {"material_id": ""}, **{f"{row.get('name')} · {row.get('material_id')}": row for row in materials}}
            machine_options = {"Sin máquina": {"machine_id": ""}, **{f"{row.get('name')} · {row.get('machine_id')}": row for row in machines}}
            with st.form("bom_step_form", clear_on_submit=True):
                rec = st.selectbox("Receta", tuple(recipe_options.keys()))
                order = st.number_input("Orden", min_value=1, value=1, step=1)
                process = st.selectbox("Proceso", ("Impresión", "Corte", "Foil", "Sublimación", "Encuadernado", "Armado", "Empaque", "Otro"))
                mat = st.selectbox("Material", tuple(material_options.keys()))
                mat_qty = st.number_input("Cantidad material", min_value=0.0, value=0.0, step=0.1)
                mac = st.selectbox("Máquina", tuple(machine_options.keys()))
                mac_minutes = st.number_input("Minutos máquina", min_value=0.0, value=0.0, step=0.5)
                labor_minutes = st.number_input("Minutos mano de obra", min_value=0.0, value=0.0, step=0.5)
                labor_rate = st.number_input("Tarifa hora mano de obra", min_value=0.0, value=0.0, step=1.0)
                energy_rate = st.number_input("Tarifa kWh", min_value=0.0, value=0.0, step=0.01)
                notes = st.text_input("Notas")
                submitted = st.form_submit_button("Guardar paso", type="primary", use_container_width=True)
            if submitted:
                recipe = recipe_options[rec]
                material = material_options[mat]
                machine = machine_options[mac]
                _insert(TABLES["steps"], {"step_id": f"STP-{uuid4().hex[:8].upper()}", "recipe_id": recipe.get("recipe_id"), "step_order": int(order), "process_type": process, "material_id": material.get("material_id"), "material_quantity": float(mat_qty), "machine_id": machine.get("machine_id"), "machine_minutes": float(mac_minutes), "labor_minutes": float(labor_minutes), "labor_rate_per_hour": float(labor_rate), "electricity_rate_per_kwh": float(energy_rate), "notes": notes.strip(), "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in steps[:100]:
            st.write(f"**{row.get('process_type')}** · receta {row.get('recipe_id')} · orden {row.get('step_order')}")

    with quote_tab:
        if not recipes:
            st.info("No hay recetas.")
        else:
            recipe_options = {f"{row.get('name')} · {row.get('recipe_id')}": row for row in recipes}
            selected = st.selectbox("Receta", tuple(recipe_options.keys()))
            qty = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
            recipe = recipe_options[selected]
            unit_cost, details = _recipe_total(recipe.get("recipe_id"))
            total_cost = unit_cost * float(qty)
            price = total_cost * (1 + float(recipe.get("target_margin_percent") or 0) / 100.0)
            m = st.columns(3)
            m[0].metric("Costo unidad", _money(unit_cost))
            m[1].metric("Costo total", _money(total_cost))
            m[2].metric("Precio sugerido", _money(price))
            for item in details:
                st.write(f"**{item['process']}** · total {_money(item['total'])} · material {_money(item['material'])} · máquina {_money(item['machine'])} · consumible {_money(item['consumable'])} · mano de obra {_money(item['labor'])} · luz {_money(item['energy'])}")
            if st.button("Guardar trabajo costeado", type="primary", use_container_width=True, disabled=unit_cost <= 0):
                _insert(TABLES["jobs"], {"job_id": f"JOB-{uuid4().hex[:8].upper()}", "recipe_id": recipe.get("recipe_id"), "job_date": date.today().isoformat(), "quantity": float(qty), "currency": get_currency(), "cost_total": float(total_cost), "price_total": float(price), "details_json": json.dumps(details, ensure_ascii=False), "created_at_utc": date.today().isoformat()})
                st.success("Trabajo costeado guardado.")

    render_info_card("Costeo por receta", "El costo final sale de pasos acumulados: material, máquina, consumible, mano de obra y electricidad.", "BOM")


app_shell.FUNCTIONAL_MODULES["Costeo por procesos"] = render_bom_costing
