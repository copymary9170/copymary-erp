"""Cotización, producción y control de plastificación para CopyMary ERP."""
from __future__ import annotations

import math

import streamlit as st

from src.components import render_info_card, render_page_header
from src.finishing_jobs import (
    STAGE_LAMINATING,
    assets_by_keyword,
    create_job,
    material_options,
)
from src.finishing_view import render_finishing_stage
from src.print_cost_data_bridge import business_defaults


LAMINATION_PROFILES = {
    "Bolsa térmica carta": {"passes": 1, "speed_ppm": 1.5, "warmup": 5.0, "waste": 5.0, "material_tokens": ("bolsa carta", "mica carta", "plastificar carta")},
    "Bolsa térmica oficio": {"passes": 1, "speed_ppm": 1.2, "warmup": 5.0, "waste": 5.0, "material_tokens": ("bolsa oficio", "mica oficio", "plastificar oficio")},
    "Bolsa térmica A4": {"passes": 1, "speed_ppm": 1.5, "warmup": 5.0, "waste": 5.0, "material_tokens": ("bolsa a4", "mica a4", "plastificar a4")},
    "Bolsa térmica A3": {"passes": 1, "speed_ppm": 0.8, "warmup": 7.0, "waste": 7.0, "material_tokens": ("bolsa a3", "mica a3", "plastificar a3")},
    "Carnet / credencial": {"passes": 1, "speed_ppm": 3.0, "warmup": 4.0, "waste": 8.0, "material_tokens": ("carnet", "credencial", "mica carnet")},
    "Laminado en frío": {"passes": 1, "speed_ppm": 2.0, "warmup": 0.0, "waste": 10.0, "material_tokens": ("laminado frio", "laminado frío", "vinil transparente")},
    "Laminado por rollo": {"passes": 1, "speed_ppm": 1.0, "warmup": 8.0, "waste": 10.0, "material_tokens": ("rollo laminado", "laminado rollo", "film laminado")},
    "Encapsulado doble": {"passes": 2, "speed_ppm": 1.0, "warmup": 6.0, "waste": 8.0, "material_tokens": ("encapsulado", "bolsa termica", "bolsa térmica", "mica")},
    "Personalizado": {"passes": 1, "speed_ppm": 1.5, "warmup": 5.0, "waste": 5.0, "material_tokens": ("laminad", "plastific", "mica", "film")},
}

MATERIAL_KEYWORDS = (
    "laminad", "plastific", "bolsa termica", "bolsa térmica", "mica", "film",
    "encapsulado", "vinil transparente",
)


def _money(value: float) -> str:
    return f"${value:,.4f}"


def _render_quote() -> None:
    render_page_header(
        "Cotizador de plastificación",
        "Calcula material, merma, precalentamiento, pasadas, recorte, energía, mano de obra, desgaste y precio de venta.",
    )

    materials = [item for item in material_options(*MATERIAL_KEYWORDS) if item["valid_cost"] and item["available"]]
    machines = assets_by_keyword("plastificad", "laminad", "encapsulad")
    defaults = business_defaults()

    metrics = st.columns(4)
    metrics[0].metric("Materiales disponibles", len(materials))
    metrics[1].metric("Equipos registrados", len(machines))
    metrics[2].metric("Origen material", "Inventario")
    metrics[3].metric("Modo", "Costeo técnico")

    if not materials:
        st.error("No hay bolsas, micas, film o laminado con costo y stock válidos en Inventario.")
        return

    material_labels = {
        f"{item['name']} · stock {item['stock']:,.2f} {item['unit']}": item
        for item in materials
    }
    machine_labels = {
        f"{item.get('name', 'Plastificadora')} · {item.get('asset_id', '')}": item
        for item in machines
    }

    with st.expander("1. Trabajo y material", expanded=True):
        a, b, c, d = st.columns(4)
        profile_name = a.selectbox("Tipo de plastificación", tuple(LAMINATION_PROFILES))
        quantity = b.number_input("Unidades terminadas", min_value=1, max_value=100000, value=1)
        pieces_per_material = c.number_input("Piezas por bolsa/metro", min_value=0.01, value=1.0, step=0.25)
        extra_tests = d.number_input("Pruebas / unidades extra", min_value=0, value=1)

        selected_material_label = st.selectbox("Material desde Inventario", tuple(material_labels))
        material = material_labels[selected_material_label]
        a, b, c = st.columns(3)
        a.metric("Costo unitario", f"${material['unit_cost']:,.4f} / {material['unit']}")
        b.metric("Stock", f"{material['stock']:,.2f} {material['unit']}")
        c.caption(f"ID/SKU: {material['item_id']} · Categoría: {material['category']}")

        profile = LAMINATION_PROFILES[profile_name]
        a, b, c = st.columns(3)
        waste_pct = a.number_input("Merma (%)", min_value=0.0, max_value=100.0, value=float(profile["waste"]))
        trim_minutes_unit = b.number_input("Recorte/acabado por unidad (min)", min_value=0.0, value=0.5)
        packaging_unit = c.number_input("Empaque por unidad ($)", min_value=0.0, value=0.0, format="%.4f")

    with st.expander("2. Parámetros técnicos", expanded=True):
        a, b, c, d = st.columns(4)
        passes = a.number_input("Pasadas", min_value=1, max_value=10, value=int(profile["passes"]))
        speed_ppm = b.number_input("Velocidad real (piezas/min)", min_value=0.1, value=float(profile["speed_ppm"]))
        warmup_minutes = c.number_input("Precalentamiento (min)", min_value=0.0, value=float(profile["warmup"]))
        setup_minutes = d.number_input("Preparación total (min)", min_value=0.0, value=3.0)

        a, b, c, d = st.columns(4)
        temperature = a.number_input("Temperatura (°C)", min_value=0, max_value=250, value=110 if "frío" not in profile_name.casefold() else 0)
        thickness_microns = b.number_input("Espesor (micras)", min_value=20, max_value=500, value=125)
        cooling_minutes = c.number_input("Enfriado/estabilización (min)", min_value=0.0, value=1.0)
        edge_seal_mm = d.number_input("Borde de sellado (mm)", min_value=0.0, max_value=30.0, value=3.0)

        st.caption("Temperatura, velocidad y pasadas deben calibrarse según el espesor del material y las instrucciones del fabricante.")

    with st.expander("3. Equipo y política comercial", expanded=True):
        selected_machine_label = st.selectbox(
            "Plastificadora desde Activos",
            ("Sin equipo registrado", *machine_labels.keys()),
        )
        machine = machine_labels.get(selected_machine_label)

        a, b, c, d = st.columns(4)
        watts = a.number_input("Consumo del equipo (W)", min_value=0.1, value=400.0)
        electricity = b.number_input("Electricidad ($/kWh)", min_value=0.0, value=float(defaults["electricity_kwh"]), format="%.4f")
        labor_hour = c.number_input("Mano de obra/hora ($)", min_value=0.0, value=float(defaults["labor_hour"]))
        machine_reserve = d.number_input("Reserva del equipo por pasada ($)", min_value=0.0, value=0.005, format="%.4f")

        a, b, c = st.columns(3)
        overhead_pct = a.number_input("Gastos indirectos (%)", min_value=0.0, max_value=300.0, value=float(defaults["overhead_pct"]))
        margin_pct = b.number_input("Margen sobre venta (%)", min_value=0.0, max_value=95.0, value=float(defaults["margin_pct"]))
        complexity_pct = c.number_input("Recargo por complejidad (%)", min_value=0.0, max_value=300.0, value=0.0)

    if not st.button("Calcular plastificación", type="primary", use_container_width=True):
        return

    base_material_units = quantity / max(0.01, pieces_per_material)
    material_units = math.ceil(base_material_units * (1 + waste_pct / 100) + extra_tests)
    if material_units > material["stock"]:
        st.error(
            f"Stock insuficiente: se requieren {material_units} {material['unit']} y hay {material['stock']:,.2f}."
        )
        return

    processing_minutes = quantity * passes / max(0.1, speed_ppm)
    trimming_minutes = quantity * trim_minutes_unit
    total_minutes = warmup_minutes + setup_minutes + processing_minutes + trimming_minutes + cooling_minutes
    total_passes = quantity * passes

    material_cost = material_units * material["unit_cost"]
    energy_cost = watts / 1000 * total_minutes / 60 * electricity
    labor_cost = total_minutes / 60 * labor_hour
    machine_wear = total_passes * machine_reserve
    packaging_cost = quantity * packaging_unit
    direct = material_cost + energy_cost + labor_cost + machine_wear + packaging_cost
    complexity = direct * complexity_pct / 100
    overhead = (direct + complexity) * overhead_pct / 100
    total_cost = direct + complexity + overhead
    suggested_price = total_cost / max(0.05, 1 - margin_pct / 100)
    unit_cost = total_cost / quantity
    unit_price = suggested_price / quantity

    if temperature > 140:
        st.warning("Temperatura alta: aumenta el riesgo de burbujas, ondulación, decoloración o daño del impreso.")
    if thickness_microns >= 250 and passes == 1:
        st.info("Material grueso: puede requerir menor velocidad o una segunda pasada según el equipo.")
    if edge_seal_mm < 2 and "Bolsa" in profile_name:
        st.warning("Borde de sellado pequeño: aumenta el riesgo de que la bolsa se abra al recortar.")
    if "frío" in profile_name.casefold() and temperature > 0:
        st.warning("El laminado en frío normalmente no requiere temperatura. Revisa el material seleccionado.")

    st.subheader("Resultado del costeo")
    result_cols = st.columns(6)
    result_cols[0].metric("Material usado", material_units)
    result_cols[1].metric("Pasadas", total_passes)
    result_cols[2].metric("Tiempo", f"{total_minutes:,.1f} min")
    result_cols[3].metric("Costo total", _money(total_cost))
    result_cols[4].metric("Costo/unidad", _money(unit_cost))
    result_cols[5].metric("Precio/unidad", f"${unit_price:,.2f}")

    breakdown = {
        "Material de Inventario": material_cost,
        "Electricidad": energy_cost,
        "Preparación, plastificado y recorte": labor_cost,
        "Reserva del equipo": machine_wear,
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
        f"Stock proyectado: {material['stock'] - material_units:,.2f} {material['unit']} de {material['name']}."
    )

    quote = {
        "profile": profile_name,
        "quantity": quantity,
        "material_item_id": material["item_id"],
        "material_name": material["name"],
        "material_quantity": material_units,
        "machine_asset_id": machine.get("asset_id", "") if machine else "",
        "machine_units": total_passes,
        "passes": passes,
        "temperature": temperature,
        "thickness_microns": thickness_microns,
        "edge_seal_mm": edge_seal_mm,
        "total_minutes": total_minutes,
        "total_cost": total_cost,
        "suggested_price": suggested_price,
        "unit_price": unit_price,
        "breakdown": breakdown,
    }
    st.session_state["laminating_last_quote"] = quote

    description = st.text_input("Descripción para producción", value=f"{quantity} × {profile_name} con {material['name']}")
    requested_by = st.text_input("Solicitado por", value="Sistema")
    if st.button("Enviar a cola de Plastificado", use_container_width=True):
        job = create_job(
            STAGE_LAMINATING,
            description=description,
            quantity=quantity,
            requested_by=requested_by,
        )
        st.success(f"Trabajo {job['finishing_id']} enviado a producción.")


def _render_guide() -> None:
    render_page_header(
        "Guía técnica de plastificación",
        "Referencias operativas para evitar burbujas, aperturas, ondulación, manchas y desperdicio.",
    )
    st.markdown(
        """
### Controles antes de producir

1. Confirma que la tinta esté completamente seca antes de aplicar calor.
2. Limpia polvo, fibras y huellas del impreso y del material.
3. Verifica tamaño, espesor, temperatura y sentido de entrada de la bolsa.
4. Realiza una prueba cuando cambie el proveedor, lote o gramaje.
5. Introduce primero el borde sellado de la bolsa térmica.

### Problemas frecuentes

- **Burbujas:** exceso de temperatura, humedad, polvo o tinta sin secar.
- **Ondulación:** temperatura alta, material delgado o demasiadas pasadas.
- **Bolsa abierta:** borde de sellado insuficiente o recorte demasiado cercano.
- **Zonas opacas:** presión o temperatura irregular, rodillos sucios o material defectuoso.
- **Atasco:** introducir el lado abierto primero, bolsa torcida o espesor incompatible.

### Control de calidad

Revisa sellado uniforme, ausencia de burbujas, alineación, bordes seguros, limpieza y que el documento no se haya deformado.
        """
    )
    render_info_card(
        "Calibración obligatoria",
        "Los parámetros del sistema son orientativos. La ficha del fabricante y una prueba real tienen prioridad.",
        "CALIDAD",
    )


def render_finishing_laminating() -> None:
    st.title("Plastificación")
    st.caption("Cotización técnica, cola de producción, consumo real de Inventario y control del equipo.")
    quote_tab, queue_tab, guide_tab = st.tabs(("Cotizador", "Cola de producción", "Guía técnica"))
    with quote_tab:
        _render_quote()
    with queue_tab:
        render_finishing_stage(
            stage=STAGE_LAMINATING,
            title="Cola de Plastificado",
            subtitle="Completa trabajos, descuenta material real de Inventario y registra uso de la plastificadora.",
            material_keywords=MATERIAL_KEYWORDS,
            material_label="Laminado / bolsa usada",
            asset_keywords=("plastificad", "laminad", "encapsulad"),
            asset_label="Máquina de plastificar",
            footer_note="El material se descuenta de Inventario y el uso se suma al activo seleccionado al completar el trabajo.",
        )
    with guide_tab:
        _render_guide()
