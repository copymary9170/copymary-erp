"""Cotización, producción y control de corte en Silhouette Cameo."""
from __future__ import annotations

import math

import streamlit as st

from src.components import render_info_card, render_page_header
from src.finishing_jobs import (
    STAGE_CUTTING,
    assets_by_keyword,
    create_job,
    material_options,
)
from src.finishing_view import render_finishing_stage
from src.print_cost_data_bridge import business_defaults


CUT_PROFILES = {
    "Sticker troquelado": {"force": 14, "speed": 5, "passes": 1, "blade": 3, "minutes_sheet": 4.0, "weeding": 2.0},
    "Sticker medio corte": {"force": 10, "speed": 6, "passes": 1, "blade": 2, "minutes_sheet": 3.0, "weeding": 0.5},
    "Vinil adhesivo": {"force": 10, "speed": 5, "passes": 1, "blade": 2, "minutes_sheet": 4.0, "weeding": 5.0},
    "Vinil textil": {"force": 14, "speed": 4, "passes": 1, "blade": 3, "minutes_sheet": 5.0, "weeding": 7.0},
    "Cartulina ligera": {"force": 20, "speed": 4, "passes": 1, "blade": 4, "minutes_sheet": 4.0, "weeding": 1.0},
    "Cartulina gruesa": {"force": 28, "speed": 3, "passes": 2, "blade": 6, "minutes_sheet": 7.0, "weeding": 1.5},
    "Papel fotográfico": {"force": 18, "speed": 4, "passes": 1, "blade": 4, "minutes_sheet": 4.0, "weeding": 0.5},
    "Acetato": {"force": 30, "speed": 2, "passes": 2, "blade": 8, "minutes_sheet": 8.0, "weeding": 1.0},
    "Papel imantado": {"force": 30, "speed": 2, "passes": 2, "blade": 9, "minutes_sheet": 10.0, "weeding": 1.0},
    "Personalizado": {"force": 10, "speed": 5, "passes": 1, "blade": 3, "minutes_sheet": 5.0, "weeding": 2.0},
}

MATERIAL_KEYWORDS = (
    "vinil", "vinilo", "sticker", "adhesivo", "cartulina", "papel", "acetato",
    "imantado", "foami", "goma eva", "transfer", "cameo",
)


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value: float) -> str:
    return f"${value:,.4f}"


def _render_quote() -> None:
    render_page_header(
        "Cotizador de corte en Cameo",
        "Calcula material, merma, preparación, corte, depilado, cuchilla, tapete, energía y precio de venta.",
    )

    materials = [item for item in material_options(*MATERIAL_KEYWORDS) if item["valid_cost"] and item["available"]]
    machines = assets_by_keyword("cameo", "silhouette")
    defaults = business_defaults()

    metrics = st.columns(4)
    metrics[0].metric("Materiales disponibles", len(materials))
    metrics[1].metric("Equipos Cameo", len(machines))
    metrics[2].metric("Origen material", "Inventario")
    metrics[3].metric("Modo", "Costeo técnico")

    if not materials:
        st.error("No hay materiales de corte con costo y stock válidos en Inventario. Registra el material antes de cotizar.")
        return

    material_labels = {
        f"{item['name']} · stock {item['stock']:,.2f} {item['unit']}": item for item in materials
    }
    machine_labels = {
        f"{item.get('name', 'Silhouette Cameo')} · {item.get('asset_id', '')}": item for item in machines
    }

    with st.expander("1. Trabajo y material", expanded=True):
        a, b, c, d = st.columns(4)
        profile_name = a.selectbox("Tipo de corte", tuple(CUT_PROFILES))
        quantity = b.number_input("Unidades terminadas", min_value=1, max_value=100000, value=1)
        pieces_sheet = c.number_input("Piezas por hoja/tramo", min_value=1, value=1)
        test_sheets = d.number_input("Pruebas / hojas extra", min_value=0, value=1)

        selected_material_label = st.selectbox("Material desde Inventario", tuple(material_labels))
        material = material_labels[selected_material_label]
        a, b, c = st.columns(3)
        a.metric("Costo unitario", f"${material['unit_cost']:,.4f} / {material['unit']}")
        b.metric("Stock", f"{material['stock']:,.2f} {material['unit']}")
        c.caption(f"ID/SKU: {material['item_id']} · Categoría: {material['category']}")

        a, b, c = st.columns(3)
        waste_pct = a.number_input("Merma de material (%)", min_value=0.0, max_value=50.0, value=5.0)
        setup_minutes = b.number_input("Preparación del archivo y tapete (min)", min_value=0.0, value=8.0)
        packaging_unit = c.number_input("Empaque por unidad ($)", min_value=0.0, value=0.0, format="%.4f")

    profile = CUT_PROFILES[profile_name]
    with st.expander("2. Parámetros de corte", expanded=True):
        a, b, c, d = st.columns(4)
        force = a.number_input("Fuerza", min_value=1, max_value=33, value=int(profile["force"]))
        speed = b.number_input("Velocidad", min_value=1, max_value=30, value=int(profile["speed"]))
        passes = c.number_input("Pasadas", min_value=1, max_value=10, value=int(profile["passes"]))
        blade = d.number_input("Profundidad de cuchilla", min_value=1, max_value=10, value=int(profile["blade"]))

        a, b, c = st.columns(3)
        minutes_sheet = a.number_input("Minutos de corte por hoja", min_value=0.1, value=float(profile["minutes_sheet"]))
        weeding_unit = b.number_input("Depilado/acabado por unidad (min)", min_value=0.0, value=float(profile["weeding"]))
        registration_marks = c.checkbox("Usa marcas de registro", value="Sticker" in profile_name)

        st.caption("Los parámetros son orientativos. Deben calibrarse con una prueba real según cuchilla, tapete, marca y lote del material.")

    with st.expander("3. Equipo, herramientas y política comercial", expanded=True):
        selected_machine_label = st.selectbox(
            "Equipo desde Activos",
            ("Sin equipo registrado", *machine_labels.keys()),
        )
        machine = machine_labels.get(selected_machine_label)
        a, b, c, d = st.columns(4)
        blade_cost = a.number_input("Costo de cuchilla ($)", min_value=0.0, value=18.0)
        blade_life = b.number_input("Vida útil cuchilla (hojas/pasadas)", min_value=1, value=500)
        mat_cost = c.number_input("Costo del tapete ($)", min_value=0.0, value=15.0)
        mat_life = d.number_input("Vida útil tapete (usos)", min_value=1, value=150)

        a, b, c, d = st.columns(4)
        watts = a.number_input("Consumo del equipo (W)", min_value=0.1, value=12.0)
        electricity = b.number_input("Electricidad ($/kWh)", min_value=0.0, value=float(defaults["electricity_kwh"]), format="%.4f")
        labor_hour = c.number_input("Mano de obra/hora ($)", min_value=0.0, value=float(defaults["labor_hour"]))
        machine_reserve = d.number_input("Reserva máquina por uso ($)", min_value=0.0, value=0.01, format="%.4f")

        a, b, c = st.columns(3)
        overhead_pct = a.number_input("Gastos indirectos (%)", min_value=0.0, max_value=300.0, value=float(defaults["overhead_pct"]))
        margin_pct = b.number_input("Margen sobre venta (%)", min_value=0.0, max_value=95.0, value=float(defaults["margin_pct"]))
        complexity_pct = c.number_input("Recargo por complejidad (%)", min_value=0.0, max_value=300.0, value=0.0)

    if not st.button("Calcular corte", type="primary", use_container_width=True):
        return

    base_sheets = math.ceil(quantity / max(1, pieces_sheet))
    sheets_with_waste = math.ceil(base_sheets * (1 + waste_pct / 100)) + int(test_sheets)
    if sheets_with_waste > material["stock"]:
        st.error(
            f"Stock insuficiente: se requieren {sheets_with_waste} {material['unit']} y hay {material['stock']:,.2f}."
        )
        return

    cutting_minutes = sheets_with_waste * minutes_sheet * passes
    weeding_minutes = quantity * weeding_unit
    registration_minutes = sheets_with_waste * 0.5 if registration_marks else 0.0
    total_minutes = setup_minutes + cutting_minutes + weeding_minutes + registration_minutes

    material_cost = sheets_with_waste * material["unit_cost"]
    blade_wear = sheets_with_waste * passes * blade_cost / max(1, blade_life)
    mat_wear = sheets_with_waste * mat_cost / max(1, mat_life)
    equipment_wear = sheets_with_waste * machine_reserve
    energy_cost = watts / 1000 * total_minutes / 60 * electricity
    labor_cost = total_minutes / 60 * labor_hour
    packaging_cost = quantity * packaging_unit

    direct = material_cost + blade_wear + mat_wear + equipment_wear + energy_cost + labor_cost + packaging_cost
    complexity = direct * complexity_pct / 100
    overhead = (direct + complexity) * overhead_pct / 100
    total_cost = direct + complexity + overhead
    suggested_price = total_cost / max(0.05, 1 - margin_pct / 100)
    unit_cost = total_cost / quantity
    unit_price = suggested_price / quantity

    if force >= 30 or blade >= 9 or passes >= 3:
        st.warning("Configuración exigente: aumenta el riesgo de dañar cuchilla, tapete o material. Realiza prueba antes del lote.")
    if weeding_unit >= 5:
        st.info("El depilado representa una parte importante del tiempo. Conviene cobrar la complejidad del diseño, no solo el material.")
    if registration_marks:
        st.info("Verifica calibración, contraste de marcas, iluminación y margen imprimible antes del corte.")

    st.subheader("Resultado del costeo")
    result_cols = st.columns(6)
    result_cols[0].metric("Hojas/tramos", sheets_with_waste)
    result_cols[1].metric("Pasadas", sheets_with_waste * passes)
    result_cols[2].metric("Tiempo", f"{total_minutes:,.1f} min")
    result_cols[3].metric("Costo total", _money(total_cost))
    result_cols[4].metric("Costo/unidad", _money(unit_cost))
    result_cols[5].metric("Precio/unidad", f"${unit_price:,.2f}")

    breakdown = {
        "Material de Inventario": material_cost,
        "Desgaste de cuchilla": blade_wear,
        "Desgaste de tapete": mat_wear,
        "Reserva del equipo": equipment_wear,
        "Electricidad": energy_cost,
        "Preparación, corte y depilado": labor_cost,
        "Empaque": packaging_cost,
        "Complejidad": complexity,
        "Gastos indirectos": overhead,
    }
    st.dataframe(
        [
            {"Concepto": name, "Costo ($)": round(value, 5), "%": round(value / max(total_cost, 0.00001) * 100, 2)}
            for name, value in breakdown.items()
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.success(
        f"Stock proyectado: {material['stock'] - sheets_with_waste:,.2f} {material['unit']} de {material['name']}."
    )

    quote = {
        "profile": profile_name,
        "quantity": quantity,
        "material_item_id": material["item_id"],
        "material_name": material["name"],
        "material_quantity": sheets_with_waste,
        "machine_asset_id": machine.get("asset_id", "") if machine else "",
        "machine_units": sheets_with_waste * passes,
        "force": force,
        "speed": speed,
        "passes": passes,
        "blade": blade,
        "total_minutes": total_minutes,
        "total_cost": total_cost,
        "suggested_price": suggested_price,
        "unit_price": unit_price,
        "breakdown": breakdown,
    }
    st.session_state["cameo_last_quote"] = quote

    description = st.text_input("Descripción para producción", value=f"{quantity} × {profile_name} en {material['name']}")
    requested_by = st.text_input("Solicitado por", value="Sistema")
    if st.button("Enviar a cola de Corte en Cameo", use_container_width=True):
        job = create_job(
            STAGE_CUTTING,
            description=description,
            quantity=quantity,
            requested_by=requested_by,
        )
        st.success(f"Trabajo {job['finishing_id']} enviado a producción.")


def _render_guide() -> None:
    render_page_header("Guía técnica de Cameo", "Parámetros orientativos, riesgos y controles antes de cortar.")
    st.warning("Nunca uses un parámetro como definitivo sin hacer corte de prueba. El mismo material puede variar por marca, lote, humedad, cuchilla y estado del tapete.")
    guide = [
        {"Material": name, "Fuerza": data["force"], "Velocidad": data["speed"], "Pasadas": data["passes"], "Cuchilla": data["blade"]}
        for name, data in CUT_PROFILES.items() if name != "Personalizado"
    ]
    st.dataframe(guide, use_container_width=True, hide_index=True)
    render_info_card("Antes del corte", "Limpia la zona, revisa la cuchilla, fija bien el material, verifica tamaño y orientación, y ejecuta una prueba pequeña.", "PREPARACIÓN")
    render_info_card("Marcas de registro", "Deja márgenes suficientes, evita laminado brillante sobre las marcas y calibra la lectura cuando el contorno se desplace.", "PRINT & CUT")
    render_info_card("Tapete", "Un tapete con poca adherencia puede repararse temporalmente, pero debe registrarse su desgaste y reemplazarse cuando afecte precisión o seguridad.", "MANTENIMIENTO")


def render_finishing_cutting_cameo() -> None:
    quote_tab, queue_tab, guide_tab = st.tabs(("Cotizador", "Producción", "Guía técnica"))
    with quote_tab:
        _render_quote()
    with queue_tab:
        render_finishing_stage(
            stage=STAGE_CUTTING,
            title="Producción de corte en Cameo",
            subtitle="Inicia, completa y registra consumo real de material y uso de la Silhouette Cameo.",
            material_keywords=MATERIAL_KEYWORDS,
            material_label="Material realmente consumido",
            asset_keywords=("cameo", "silhouette"),
            asset_label="Silhouette Cameo",
            footer_note="Al completar, descuenta el material real de Inventario y suma pasadas/usos al activo seleccionado.",
        )
    with guide_tab:
        _render_guide()
