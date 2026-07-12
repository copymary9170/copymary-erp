"""Gestión y costeo empresarial de sublimación para CopyMary ERP."""

from __future__ import annotations

import math

import streamlit as st

from src.components import render_info_card, render_page_header
from src.finishing_jobs import (
    STAGE_SUBLIMATION,
    assets_by_keyword,
    complete_job,
    jobs_for_stage,
    material_options,
    start_job,
)
from src.print_cost_data_bridge import business_defaults

PRODUCT_PROFILES = {
    "Taza 11 oz": {"temp": 190, "seconds": 180, "pressure": "Media", "blank_tokens": ("taza", "mug"), "paper_units": 1.0, "tape_cm": 25.0, "press_cycles": 1},
    "Taza 15 oz": {"temp": 190, "seconds": 210, "pressure": "Media", "blank_tokens": ("taza 15", "mug 15"), "paper_units": 1.0, "tape_cm": 28.0, "press_cycles": 1},
    "Franela / camiseta": {"temp": 195, "seconds": 55, "pressure": "Media", "blank_tokens": ("franela", "camisa", "camiseta", "playera", "textil"), "paper_units": 1.0, "tape_cm": 35.0, "press_cycles": 1},
    "Gorra": {"temp": 190, "seconds": 50, "pressure": "Media-alta", "blank_tokens": ("gorra", "cap"), "paper_units": 1.0, "tape_cm": 22.0, "press_cycles": 1},
    "Cojín": {"temp": 195, "seconds": 60, "pressure": "Media", "blank_tokens": ("cojin", "almohada"), "paper_units": 1.0, "tape_cm": 38.0, "press_cycles": 1},
    "Llavero / MDF": {"temp": 190, "seconds": 70, "pressure": "Media", "blank_tokens": ("llavero", "mdf"), "paper_units": 0.5, "tape_cm": 14.0, "press_cycles": 1},
    "Mouse pad": {"temp": 200, "seconds": 45, "pressure": "Media", "blank_tokens": ("mouse", "pad"), "paper_units": 1.0, "tape_cm": 30.0, "press_cycles": 1},
    "Placa de aluminio": {"temp": 195, "seconds": 60, "pressure": "Media", "blank_tokens": ("aluminio", "placa"), "paper_units": 1.0, "tape_cm": 26.0, "press_cycles": 1},
    "Personalizado": {"temp": 190, "seconds": 60, "pressure": "Media", "blank_tokens": ("sublim",), "paper_units": 1.0, "tape_cm": 25.0, "press_cycles": 1},
}


def _money(value: float) -> str:
    return f"${value:,.4f}"


def _valid_materials(*keywords: str) -> list[dict]:
    return [item for item in material_options(*keywords) if item["valid_cost"] and item["available"]]


def _select_inventory_item(label: str, items: list[dict], key: str) -> dict | None:
    if not items:
        st.error(f"No hay {label.lower()} con costo y stock válido en Inventario.")
        return None
    labels = {f"{item['name']} · stock {item['stock']:,.2f} {item['unit']} · ${item['unit_cost']:,.4f}": item for item in items}
    return labels[st.selectbox(label, tuple(labels), key=key)]


def _render_costing_tab() -> None:
    defaults = business_defaults()
    st.markdown("### Cotizador técnico de sublimación")
    st.caption("Todos los blancos y consumibles deben existir en Inventario. Los equipos deben estar registrados en Activos.")

    a, b, c, d = st.columns(4)
    product_type = a.selectbox("Producto", tuple(PRODUCT_PROFILES))
    quantity = b.number_input("Cantidad", min_value=1, max_value=10000, value=1)
    waste_pct = c.number_input("Merma / pruebas (%)", min_value=0.0, max_value=100.0, value=5.0)
    margin_pct = d.number_input("Margen sobre venta (%)", min_value=0.0, max_value=95.0, value=float(defaults["margin_pct"]))
    profile = PRODUCT_PROFILES[product_type]

    blank = _select_inventory_item("Blanco sublimable", _valid_materials(*profile["blank_tokens"]), "sub_blank")
    paper = _select_inventory_item("Papel de sublimación", _valid_materials("papel sublim", "sublimacion", "sublimación"), "sub_paper")
    tape = _select_inventory_item("Cinta térmica", _valid_materials("cinta term", "cinta sublim", "heat tape"), "sub_tape")
    protection = _select_inventory_item("Protección / papel siliconado", _valid_materials("siliconado", "teflon", "teflón", "proteccion sublim", "protección sublim"), "sub_protection")

    machines = assets_by_keyword("prensa", "sublimac", "sublimación")
    machine_labels = {f"{m.get('name', 'Equipo')} · {m.get('asset_id', '')}": m for m in machines}
    selected_machine = machine_labels.get(st.selectbox("Prensa / equipo", ("Sin equipo registrado", *machine_labels), key="sub_machine"))

    with st.expander("Parámetros técnicos", expanded=True):
        a, b, c, d = st.columns(4)
        temperature = a.number_input("Temperatura (°C)", min_value=80, max_value=250, value=int(profile["temp"]))
        seconds = b.number_input("Tiempo por ciclo (s)", min_value=5, max_value=1200, value=int(profile["seconds"]))
        pressure = c.selectbox("Presión", ("Baja", "Media", "Media-alta", "Alta"), index=("Baja", "Media", "Media-alta", "Alta").index(profile["pressure"]))
        cycles_per_item = d.number_input("Ciclos por unidad", min_value=1, max_value=10, value=int(profile["press_cycles"]))
        a, b, c, d = st.columns(4)
        press_watts = a.number_input("Potencia de prensa (W)", min_value=1.0, value=1200.0)
        warmup_minutes = b.number_input("Precalentamiento (min)", min_value=0.0, value=8.0)
        prep_minutes = c.number_input("Preparación total (min)", min_value=0.0, value=5.0)
        labor_hour = d.number_input("Mano de obra/hora ($)", min_value=0.0, value=float(defaults["labor_hour"]))
        a, b, c = st.columns(3)
        electricity_kwh = a.number_input("Electricidad ($/kWh)", min_value=0.0, value=float(defaults["electricity_kwh"]), format="%.4f")
        overhead_pct = b.number_input("Gastos indirectos (%)", min_value=0.0, max_value=300.0, value=float(defaults["overhead_pct"]))
        machine_reserve = c.number_input("Reserva de prensa por ciclo ($)", min_value=0.0, value=0.0100, format="%.4f")

    if not st.button("Calcular sublimación", type="primary", use_container_width=True):
        return
    if not blank or not paper:
        st.error("El blanco y el papel de sublimación son obligatorios y deben salir de Inventario.")
        return

    production_units = math.ceil(quantity * (1 + waste_pct / 100))
    blank_qty = production_units
    paper_qty = math.ceil(production_units * float(profile["paper_units"]))
    tape_qty = production_units * float(profile["tape_cm"]) / 100.0 if tape else 0.0
    protection_qty = production_units if protection else 0.0

    requirements = [(blank, blank_qty), (paper, paper_qty), (tape, tape_qty), (protection, protection_qty)]
    shortages = [(item, qty) for item, qty in requirements if item and qty > item["stock"]]
    if shortages:
        for item, qty in shortages:
            st.error(f"Stock insuficiente de {item['name']}: se requieren {qty:,.2f} {item['unit']} y hay {item['stock']:,.2f}.")
        return

    blank_cost = blank_qty * blank["unit_cost"]
    paper_cost = paper_qty * paper["unit_cost"]
    tape_cost = tape_qty * tape["unit_cost"] if tape else 0.0
    protection_cost = protection_qty * protection["unit_cost"] if protection else 0.0
    cycles = production_units * cycles_per_item
    active_minutes = cycles * seconds / 60
    total_minutes = warmup_minutes + prep_minutes + active_minutes
    electricity = press_watts / 1000 * total_minutes / 60 * electricity_kwh
    labor = total_minutes / 60 * labor_hour
    machine_cost = cycles * machine_reserve
    direct = blank_cost + paper_cost + tape_cost + protection_cost + electricity + labor + machine_cost
    overhead = direct * overhead_pct / 100
    total = direct + overhead
    price = total / max(0.05, 1 - margin_pct / 100)

    cols = st.columns(6)
    cols[0].metric("Unidades vendibles", f"{quantity:,}")
    cols[1].metric("Unidades con merma", f"{production_units:,}")
    cols[2].metric("Ciclos", f"{cycles:,}")
    cols[3].metric("Tiempo", f"{total_minutes:.1f} min")
    cols[4].metric("Costo total", _money(total))
    cols[5].metric("Precio sugerido", f"${price:,.2f}")
    st.caption(f"Parámetros: {temperature} °C · {seconds} s · presión {pressure}. Deben validarse con el proveedor del blanco.")

    breakdown = {
        "Blancos y merma": blank_cost,
        "Papel de sublimación": paper_cost,
        "Cinta térmica": tape_cost,
        "Protección térmica": protection_cost,
        "Electricidad": electricity,
        "Mano de obra": labor,
        "Reserva de prensa": machine_cost,
        "Gastos indirectos": overhead,
    }
    st.dataframe(
        [{"Concepto": name, "Costo ($)": round(cost, 5), "%": round(cost / max(total, 0.00001) * 100, 2)} for name, cost in breakdown.items()],
        use_container_width=True,
        hide_index=True,
    )
    st.success(f"Costo unitario: {total / quantity:,.4f} · precio unitario sugerido: ${price / quantity:,.2f}.")
    if temperature >= 200 or seconds >= 240:
        st.warning("Parámetros altos: aumenta el riesgo de amarillamiento, marcas de prensa o deformación. Realiza una prueba.")
    if product_type == "Franela / camiseta":
        st.info("Verifica que la prenda sea poliéster o tenga recubrimiento apto para sublimación; algodón puro no fija sublimación convencional.")


def _render_queue_tab() -> None:
    pending = jobs_for_stage(STAGE_SUBLIMATION)
    all_jobs = jobs_for_stage(STAGE_SUBLIMATION, include_done=True)
    completed = [job for job in all_jobs if job.get("status") == "Completado"]
    metrics = st.columns(3)
    metrics[0].metric("Pendientes", len(pending))
    metrics[1].metric("Completados", len(completed))
    metrics[2].metric("Total", len(all_jobs))
    if not pending:
        st.info("No hay trabajos pendientes de sublimación.")
        return

    blanks = _valid_materials("sublim", "taza", "franela", "camisa", "camiseta", "gorra", "cojin", "cojín", "mdf", "mouse")
    machines = assets_by_keyword("prensa", "sublimac", "sublimación")
    blank_labels = {f"{item['name']} · stock {item['stock']:,.2f}": item for item in blanks}
    machine_labels = {f"{m.get('name', 'Equipo')}": m for m in machines}

    for job in pending:
        with st.container(border=True):
            st.markdown(f"**{job.get('finishing_id')} · {job.get('description') or 'Trabajo de sublimación'}**")
            st.caption(f"Origen: {job.get('source_job_id') or 'independiente'} · cantidad {job.get('quantity', 1)} · estado {job.get('status')}")
            if job.get("status") == "Pendiente" and st.button("Iniciar", key=f"sub_start_{job['finishing_id']}"):
                start_job(job["finishing_id"])
                st.rerun()
            with st.form(f"sub_complete_{job['finishing_id']}"):
                selected_blank = st.selectbox("Blanco consumido", ("Sin descuento", *blank_labels), key=f"sub_blank_{job['finishing_id']}")
                blank_qty = st.number_input("Cantidad consumida", min_value=0.0, value=float(job.get("quantity", 1) or 0), key=f"sub_qty_{job['finishing_id']}")
                selected_machine = st.selectbox("Prensa utilizada", ("Sin registrar uso", *machine_labels), key=f"sub_mac_{job['finishing_id']}")
                cycles = st.number_input("Ciclos de prensa", min_value=0.0, value=float(job.get("quantity", 1) or 0), key=f"sub_cycles_{job['finishing_id']}")
                quality = st.selectbox("Control de calidad", ("Aprobado", "Reproceso", "Rechazado"), key=f"sub_quality_{job['finishing_id']}")
                note = st.text_input("Observación", key=f"sub_note_{job['finishing_id']}")
                submitted = st.form_submit_button("Completar sublimación", type="primary", use_container_width=True)
            if submitted:
                blank = blank_labels.get(selected_blank)
                machine = machine_labels.get(selected_machine)
                complete_job(
                    job["finishing_id"],
                    material_item_id=blank["item_id"] if blank else "",
                    material_quantity=blank_qty if blank else 0.0,
                    asset_id=machine.get("asset_id", "") if machine else "",
                    machine_units=cycles if machine else 0.0,
                    note=f"QC: {quality}. {note}".strip(),
                )
                st.success("Trabajo de sublimación completado.")
                st.rerun()


def render_finishing_sublimation() -> None:
    render_page_header("Sublimación", "Cotiza, controla parámetros, consume Inventario, registra uso de prensa y gestiona calidad.")
    costing_tab, queue_tab, guide_tab = st.tabs(("Cotizar", "Cola de producción", "Guía técnica"))
    with costing_tab:
        _render_costing_tab()
    with queue_tab:
        _render_queue_tab()
    with guide_tab:
        st.markdown("### Validaciones antes de producir")
        st.markdown("- Confirmar que el blanco sea sublimable y esté sin grasa, polvo o humedad.\n- Imprimir el diseño espejado cuando corresponda.\n- Verificar perfil de color, tamaño y orientación.\n- Preprensar textiles para retirar humedad y arrugas.\n- Usar papel protector para evitar transferencia a la prensa.\n- Registrar temperatura, tiempo, presión, lote y resultado de la prueba.")
        render_info_card("Control de calidad", "Revisa centrado, color, definición, ghosting, manchas, marcas de prensa y adherencia. Los parámetros sugeridos son orientativos; manda siempre la ficha del proveedor del blanco.", "SUBLIMACIÓN")
