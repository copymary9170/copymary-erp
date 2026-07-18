"""Costeo por recetas BOM (materiales, máquinas, consumibles, sublimación, área/anidado)."""

from datetime import date
from uuid import uuid4
import json

import streamlit as st

from src import app_shell, machine_maintenance
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database, latest_exchange_rate
from src.money import format_money, get_currency


TABLES = {
    "materials": "production_materials",
    "machines": "production_machines",
    "consumables": "machine_consumables",
    "recipes": "product_recipes",
    "steps": "recipe_steps",
    "jobs": "costed_jobs",
}

RECOMMENDED_MATERIAL_TYPES = ("vinil_fino", "vinil_grueso", "cartulina", "carton", "otro")
SUBSTRATES = ("tela_poliester", "taza_ceramica", "gorra", "metal", "otro")
PRESSURE_LEVELS = ("baja", "media", "alta")

# Márgenes sugeridos por defecto al crear un material, según su uso. Son solo
# un punto de partida editable por material (campo `resale_margin_percent`),
# no una regla fija: cada negocio puede ajustar el margen real que le
# convenga. La idea de partida es que un material de reventa (se vende tal
# cual) suele manejar un margen menor que un producto terminado con trabajo
# agregado, que es lo que ya cubre `target_margin_percent` de cada receta.
DEFAULT_RESALE_MARGIN_PERCENT = {"reventa": 25.0, "mixto": 30.0, "insumo": 0.0}


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


def _material_unit_cost(material: dict, print_mode: str) -> float:
    """Devuelve el costo unitario del material según el modo de impresión.

    Si las columnas nuevas (unit_cost_color / unit_cost_bw) todavía no tienen
    valor para una fila antigua, se cae al `unit_cost` original para no romper
    materiales ya cargados antes de esta migración.
    """
    legacy_cost = float(material.get("unit_cost") or 0)
    color_cost = material.get("unit_cost_color")
    bw_cost = material.get("unit_cost_bw")
    if print_mode == "bn":
        return float(bw_cost) if bw_cost not in (None, "") else legacy_cost
    return float(color_cost) if color_cost not in (None, "") else legacy_cost


def resale_price(material: dict) -> float:
    """Precio de venta sugerido para un material marcado como reventa/mixto.

    Solo tiene sentido para materiales que se venden tal cual (`use_type` en
    "reventa" o "mixto"): usa el costo base (`unit_cost`) y el margen propio
    del material (`resale_margin_percent`), independiente del margen de
    cualquier receta. Para materiales de uso puramente "insumo" devuelve 0.0,
    ya que esos no se venden directamente — su costo se diluye dentro del
    producto final vía la receta que los use.
    """
    if material.get("use_type") not in ("reventa", "mixto"):
        return 0.0
    cost = float(material.get("unit_cost") or 0)
    margin = float(material.get("resale_margin_percent") or 0)
    return cost * (1 + margin / 100.0)


def suggested_pieces_per_sheet(design_area_cm2: float, sheet_area_cm2: float) -> int:
    """Estima cuántas piezas caben en una hoja/rollo a partir del área.

    Es una estimación simple por área (hoja // diseño), no un anidado real
    con rotación de piezas: para diseños muy irregulares el anidado real
    puede caber un poco más. Sirve como sugerencia inicial, no como valor
    definitivo — el usuario puede ajustarlo manualmente en el formulario.
    """
    if design_area_cm2 <= 0 or sheet_area_cm2 <= 0:
        return 1
    return max(int(sheet_area_cm2 // design_area_cm2), 1)


def _step_total(step: dict, materials: dict, machines: dict, consumables: list[dict]) -> dict:
    material_cost = 0.0
    material_id = str(step.get("material_id") or "")
    if material_id in materials:
        material = materials[material_id]
        waste = float(material.get("waste_percent") or 0) / 100.0
        print_mode = str(step.get("print_mode") or "color")
        unit_cost = _material_unit_cost(material, print_mode)
        raw_cost = float(step.get("material_quantity") or 0) * unit_cost * (1 + waste)
        pieces_per_sheet = max(float(step.get("pieces_per_sheet") or 1), 1)
        material_cost = raw_cost / pieces_per_sheet

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
        detail = {"process": step.get("process_type"), **cost}
        if step.get("process_type") == "Sublimación":
            detail["substrate"] = step.get("substrate")
            detail["temperature_c"] = step.get("temperature_c")
            detail["time_seconds"] = step.get("time_seconds")
            detail["pressure_level"] = step.get("pressure_level")
        details.append(detail)
    return total, details


def _accumulate_machine_usage_from_job(recipe_id: str, quantity: float) -> None:
    """Alimenta el contador de uso del Mantenimiento preventivo con las horas
    de máquina de un trabajo REAL confirmado ('Guardar trabajo costeado').

    Antes había que actualizar la lectura del contador a mano en Mantenimiento
    preventivo; ahora cada trabajo costeado que usa una máquina con horas
    (`machine_minutes`) suma esas horas automáticamente a cualquier plan
    activo de esa máquina con disparador 'Horas de uso' — el mismo criterio
    con el que el reparador del taller decide cuándo toca un servicio: por lo
    que realmente se trabajó, no por una lectura que alguien tuvo que anotar.

    Silencioso si la máquina del paso no tiene ningún plan con ese disparador
    (no todo el mundo usa horas — muchos planes van por metros o páginas).
    """
    steps = [row for row in _rows(TABLES["steps"]) if row.get("recipe_id") == recipe_id]
    for step in steps:
        machine_id = str(step.get("machine_id") or "")
        minutes = float(step.get("machine_minutes") or 0)
        if not machine_id or minutes <= 0:
            continue
        hours = minutes / 60.0 * float(quantity)
        machine_maintenance.accumulate_usage_for_machine(machine_id, "Horas de uso", hours)


def _duplicate_recipe_as_new_version(recipe: dict) -> None:
    new_recipe_id = f"REC-{uuid4().hex[:8].upper()}"
    _insert(
        TABLES["recipes"],
        {
            "recipe_id": new_recipe_id,
            "name": recipe.get("name"),
            "category": recipe.get("category"),
            "target_margin_percent": float(recipe.get("target_margin_percent") or 0),
            "version": int(recipe.get("version") or 1) + 1,
            "parent_recipe_id": recipe.get("recipe_id"),
            "active": 1,
            "created_at_utc": date.today().isoformat(),
        },
    )
    steps = [row for row in _rows(TABLES["steps"]) if row.get("recipe_id") == recipe.get("recipe_id")]
    for step in steps:
        _insert(
            TABLES["steps"],
            {
                "step_id": f"STP-{uuid4().hex[:8].upper()}",
                "recipe_id": new_recipe_id,
                "step_order": step.get("step_order"),
                "process_type": step.get("process_type"),
                "material_id": step.get("material_id"),
                "material_quantity": step.get("material_quantity"),
                "machine_id": step.get("machine_id"),
                "machine_minutes": step.get("machine_minutes"),
                "labor_minutes": step.get("labor_minutes"),
                "labor_rate_per_hour": step.get("labor_rate_per_hour"),
                "electricity_rate_per_kwh": step.get("electricity_rate_per_kwh"),
                "notes": step.get("notes"),
                "print_mode": step.get("print_mode") or "color",
                "substrate": step.get("substrate") or "",
                "temperature_c": step.get("temperature_c"),
                "time_seconds": step.get("time_seconds"),
                "pressure_level": step.get("pressure_level") or "",
                "design_area_cm2": step.get("design_area_cm2"),
                "sheet_area_cm2": step.get("sheet_area_cm2"),
                "pieces_per_sheet": step.get("pieces_per_sheet") or 1,
                "created_at_utc": date.today().isoformat(),
            },
        )


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
        use_type_preview = st.selectbox("Uso", ("insumo", "reventa", "mixto"), key="bom_material_use_type_preview")
        with st.form("bom_material_form", clear_on_submit=True):
            name = st.text_input("Material")
            category = st.text_input("Categoría", value="Papel")
            unit = st.selectbox("Unidad", ("hoja", "unidad", "cm2", "m2", "metro", "ml", "gramo"))
            cost_cols = st.columns(2)
            with cost_cols[0]:
                unit_cost_color = st.number_input("Costo unitario a color", min_value=0.0, value=0.0, step=0.1)
            with cost_cols[1]:
                unit_cost_bw = st.number_input("Costo unitario blanco y negro", min_value=0.0, value=0.0, step=0.1)
            waste = st.number_input("Merma %", min_value=0.0, value=0.0, step=0.5)
            resale_margin = 0.0
            if use_type_preview in ("reventa", "mixto"):
                resale_margin = st.number_input(
                    "Margen de reventa %",
                    min_value=0.0,
                    max_value=500.0,
                    value=DEFAULT_RESALE_MARGIN_PERCENT.get(use_type_preview, 25.0),
                    step=1.0,
                    help="Margen propio de este material cuando se vende tal cual, independiente del margen de cualquier receta que lo use como insumo.",
                )
            submitted = st.form_submit_button("Guardar material", type="primary", use_container_width=True)
        if submitted:
            if not name.strip() or unit_cost_color <= 0:
                st.error("Material y costo a color son obligatorios.")
            else:
                effective_bw = unit_cost_bw if unit_cost_bw > 0 else unit_cost_color
                _insert(TABLES["materials"], {"material_id": f"MAT-{uuid4().hex[:8].upper()}", "name": name.strip(), "category": category.strip(), "unit": unit, "unit_cost": float(unit_cost_color), "unit_cost_color": float(unit_cost_color), "unit_cost_bw": float(effective_bw), "currency": get_currency(), "waste_percent": float(waste), "use_type": use_type_preview, "resale_margin_percent": float(resale_margin), "active": 1, "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in materials[:60]:
            color_cost = row.get("unit_cost_color") or row.get("unit_cost")
            bw_cost = row.get("unit_cost_bw") or row.get("unit_cost")
            line = f"**{row.get('name')}** · color {_money(color_cost)}/{row.get('unit')} · B/N {_money(bw_cost)}/{row.get('unit')} · merma {row.get('waste_percent')}%"
            if row.get("use_type") in ("reventa", "mixto"):
                line += f" · reventa {_money(resale_price(row))} (margen {float(row.get('resale_margin_percent') or 0):.0f}%)"
            st.write(line)

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
                recommended_type = st.selectbox("Tipo de material recomendado", RECOMMENDED_MATERIAL_TYPES)
                submitted = st.form_submit_button("Guardar consumible", type="primary", use_container_width=True)
            if submitted:
                machine = machine_options[selected]
                _insert(TABLES["consumables"], {"consumable_id": f"CON-{uuid4().hex[:8].upper()}", "machine_id": machine.get("machine_id"), "name": name.strip(), "unit": unit, "replacement_cost": float(cost), "useful_life_units": float(life), "recommended_material_type": recommended_type, "active": 1, "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in consumables[:60]:
            per_use = float(row.get("replacement_cost") or 0) / max(float(row.get("useful_life_units") or 1), 1)
            recommended = row.get("recommended_material_type") or "sin especificar"
            st.write(f"**{row.get('name')}** · costo por uso {_money(per_use)} · recomendado para {recommended}")

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
                _insert(TABLES["recipes"], {"recipe_id": f"REC-{uuid4().hex[:8].upper()}", "name": name.strip(), "category": category.strip(), "target_margin_percent": float(margin), "version": 1, "parent_recipe_id": None, "active": 1, "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in recipes[:60]:
            total, _details = _recipe_total(row.get("recipe_id"))
            price = total * (1 + float(row.get("target_margin_percent") or 0) / 100.0)
            info_col, action_col = st.columns([4, 1])
            with info_col:
                st.write(f"**{row.get('name')}** (v{row.get('version') or 1}) · costo {_money(total)} · precio {_money(price)}")
            with action_col:
                if st.button("Nueva versión", key=f"dup_{row.get('recipe_id')}", use_container_width=True):
                    _duplicate_recipe_as_new_version(row)
                    st.rerun()

    with step_tab:
        if not recipes:
            st.info("Primero registra una receta.")
        else:
            recipe_options = {f"{row.get('name')} (v{row.get('version') or 1}) · {row.get('recipe_id')}": row for row in recipes}
            material_options = {"Sin material": {"material_id": ""}, **{f"{row.get('name')} · {row.get('material_id')}": row for row in materials}}
            machine_options = {"Sin máquina": {"machine_id": ""}, **{f"{row.get('name')} · {row.get('machine_id')}": row for row in machines}}
            process_choice = st.selectbox("Proceso", ("Impresión", "Corte", "Foil", "Sublimación", "Encuadernado", "Armado", "Empaque", "Otro"), key="bom_step_process_preview")
            area_cols = st.columns(2)
            design_area_preview = area_cols[0].number_input("Área diseño (cm²)", min_value=0.0, value=0.0, step=1.0, key="bom_step_design_area_preview")
            sheet_area_preview = area_cols[1].number_input("Área hoja/rollo (cm²)", min_value=0.0, value=0.0, step=1.0, key="bom_step_sheet_area_preview")
            suggested_pieces = suggested_pieces_per_sheet(design_area_preview, sheet_area_preview)
            if design_area_preview > 0 and sheet_area_preview > 0:
                st.caption(f"Sugerencia por área: ~{suggested_pieces} pieza(s) por hoja (estimación simple, no anidado real — ajústalo abajo si tu diseño encaja distinto).")
            with st.form("bom_step_form", clear_on_submit=True):
                rec = st.selectbox("Receta", tuple(recipe_options.keys()))
                order = st.number_input("Orden", min_value=1, value=1, step=1)
                mat = st.selectbox("Material", tuple(material_options.keys()))
                print_mode_label = st.selectbox("Modo de impresión del material", ("Color", "Blanco y negro"))
                mat_qty = st.number_input("Cantidad material", min_value=0.0, value=0.0, step=0.1)
                design_area = st.number_input("Área diseño (cm²)", min_value=0.0, value=design_area_preview, step=1.0)
                sheet_area = st.number_input("Área hoja/rollo (cm²)", min_value=0.0, value=sheet_area_preview, step=1.0)
                pieces_per_sheet = st.number_input("Piezas por hoja", min_value=1.0, value=float(suggested_pieces), step=1.0)
                mac = st.selectbox("Máquina", tuple(machine_options.keys()))
                mac_minutes = st.number_input("Minutos máquina", min_value=0.0, value=0.0, step=0.5)
                labor_minutes = st.number_input("Minutos mano de obra", min_value=0.0, value=0.0, step=0.5)
                labor_rate = st.number_input("Tarifa hora mano de obra", min_value=0.0, value=0.0, step=1.0)
                energy_rate = st.number_input("Tarifa kWh", min_value=0.0, value=0.0, step=0.01)
                substrate = st.selectbox("Sustrato", SUBSTRATES)
                temperature_c = st.number_input("Temperatura (°C)", min_value=0.0, value=0.0, step=1.0)
                time_seconds = st.number_input("Tiempo (segundos)", min_value=0.0, value=0.0, step=5.0)
                pressure_level = st.selectbox("Presión", PRESSURE_LEVELS)
                notes = st.text_input("Notas")
                submitted = st.form_submit_button("Guardar paso", type="primary", use_container_width=True)
            if submitted:
                recipe = recipe_options[rec]
                material = material_options[mat]
                machine = machine_options[mac]
                is_sublimation = process_choice == "Sublimación"
                _insert(TABLES["steps"], {"step_id": f"STP-{uuid4().hex[:8].upper()}", "recipe_id": recipe.get("recipe_id"), "step_order": int(order), "process_type": process_choice, "material_id": material.get("material_id"), "material_quantity": float(mat_qty), "machine_id": machine.get("machine_id"), "machine_minutes": float(mac_minutes), "labor_minutes": float(labor_minutes), "labor_rate_per_hour": float(labor_rate), "electricity_rate_per_kwh": float(energy_rate), "notes": notes.strip(), "print_mode": "bn" if print_mode_label == "Blanco y negro" else "color", "substrate": substrate if is_sublimation else "", "temperature_c": float(temperature_c) if is_sublimation and temperature_c > 0 else None, "time_seconds": float(time_seconds) if is_sublimation and time_seconds > 0 else None, "pressure_level": pressure_level if is_sublimation else "", "design_area_cm2": float(design_area) if design_area > 0 else None, "sheet_area_cm2": float(sheet_area) if sheet_area > 0 else None, "pieces_per_sheet": float(pieces_per_sheet), "created_at_utc": date.today().isoformat()})
                st.rerun()
        for row in steps[:100]:
            st.write(f"**{row.get('process_type')}** · receta {row.get('recipe_id')} · orden {row.get('step_order')}")

    with quote_tab:
        if not recipes:
            st.info("No hay recetas.")
        else:
            recipe_options = {f"{row.get('name')} (v{row.get('version') or 1}) · {row.get('recipe_id')}": row for row in recipes}
            selected = st.selectbox("Receta", tuple(recipe_options.keys()))
            qty = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
            recipe = recipe_options[selected]
            unit_cost, details = _recipe_total(recipe.get("recipe_id"))
            total_cost = unit_cost * float(qty)
            price = total_cost * (1 + float(recipe.get("target_margin_percent") or 0) / 100.0)
            currency = get_currency()
            rate = latest_exchange_rate(currency) if currency != "USD" else None
            m = st.columns(3)
            m[0].metric("Costo unidad", _money(unit_cost))
            m[1].metric("Costo total", _money(total_cost))
            m[2].metric("Precio sugerido", _money(price))
            for item in details:
                st.write(f"**{item['process']}** · total {_money(item['total'])} · material {_money(item['material'])} · máquina {_money(item['machine'])} · consumible {_money(item['consumable'])} · mano de obra {_money(item['labor'])} · luz {_money(item['energy'])}")
            if st.button("Guardar trabajo costeado", type="primary", use_container_width=True, disabled=unit_cost <= 0):
                _insert(TABLES["jobs"], {"job_id": f"JOB-{uuid4().hex[:8].upper()}", "recipe_id": recipe.get("recipe_id"), "job_date": date.today().isoformat(), "quantity": float(qty), "currency": currency, "cost_total": float(total_cost), "price_total": float(price), "details_json": json.dumps(details, ensure_ascii=False), "exchange_rate_id": rate.get("rate_id") if rate else None, "created_at_utc": date.today().isoformat()})
                _accumulate_machine_usage_from_job(recipe.get("recipe_id"), float(qty))
                st.success("Trabajo costeado guardado. El uso de máquina se sumó a Mantenimiento preventivo.")

    render_info_card("Costeo por receta", "El costo final sale de pasos acumulados: material, máquina, consumible, mano de obra y electricidad.", "BOM")


app_shell.FUNCTIONAL_MODULES["Costeo por procesos"] = render_bom_costing
