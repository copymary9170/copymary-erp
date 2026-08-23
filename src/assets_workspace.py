"""Workspace ejecutivo para Activos y mantenimiento.

No reemplaza el registro histórico existente: lo organiza y añade una capa de
lectura gerencial sobre `src.assets` y `src.machine_maintenance`.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from src import assets as legacy_assets
from src import machine_maintenance
from src import creative_equipment_knowledge as equipment_knowledge
from src.components import render_info_card, render_page_header
from src.money import format_money
from src.session_utils import now_iso, read_list, save_list

ELECTRICAL_AUDIT_KEY = "asset_electrical_audit"


def _maintenance_cost_by_asset() -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in read_list("asset_maintenance_log"):
        asset_id = str(row.get("asset_id") or "")
        totals[asset_id] = totals.get(asset_id, 0.0) + float(row.get("cost", 0.0) or 0.0)
    return totals


def _replacement_priority(asset) -> str:
    if asset.status in ("Fuera de servicio", "Dado de baja"):
        return "Crítica"
    if asset.usage_percent >= 90:
        return "Alta"
    if asset.usage_percent >= 75 or asset.warranty_status == "Vencida":
        return "Media"
    return "Normal"


def _asset_health(asset) -> int:
    score = 100
    if asset.status == "En mantenimiento":
        score -= 25
    elif asset.status == "Fuera de servicio":
        score -= 60
    elif asset.status in ("Dado de baja", "Vendido"):
        score -= 100
    if asset.usage_percent >= 90:
        score -= 30
    elif asset.usage_percent >= 75:
        score -= 15
    if asset.warranty_status == "Vencida":
        score -= 10
    elif asset.warranty_status == "Por vencer":
        score -= 5
    return max(score, 0)


def _dashboard() -> None:
    assets = legacy_assets._get_assets()
    maintenance_costs = _maintenance_cost_by_asset()
    total_cost = sum(a.acquisition_cost for a in assets)
    book_value = sum(a.remaining_value for a in assets)
    maintenance_total = sum(maintenance_costs.values())
    available = sum(a.available_for_quoting for a in assets)

    render_page_header(
        "Centro de Activos",
        "Estado, valor, vida útil, garantías, mantenimiento, electricidad y reemplazo en una sola vista.",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equipos registrados", len(assets))
    c2.metric("Disponibles para cotizar", available)
    c3.metric("Valor en libros", format_money(book_value))
    c4.metric("Mantenimiento acumulado", format_money(maintenance_total))

    electrical_rows = read_list(ELECTRICAL_AUDIT_KEY)
    if electrical_rows:
        incomplete = sum(not row.get("plate_verified") for row in electrical_rows)
        high_power = sum(float(row.get("watts", 0) or 0) >= 1000 for row in electrical_rows)
        if incomplete:
            st.warning(f"⚡ {incomplete} equipo(s) eléctrico(s) todavía no tienen la placa verificada.")
        if high_power:
            st.info(f"Hay {high_power} carga(s) de 1000 W o más registradas. Revísalas en Equipos y electricidad antes de trabajar varias a la vez.")

    if not assets:
        st.info("Todavía no hay activos registrados. Entra en Registro para agregar el primero.")
        return

    high_risk = [a for a in assets if _replacement_priority(a) in ("Crítica", "Alta")]
    expiring = [a for a in assets if a.warranty_status == "Por vencer"]
    unavailable = [a for a in assets if a.status not in ("Activo",)]
    if high_risk or expiring or unavailable:
        st.markdown("### Alertas")
        if high_risk:
            st.error("Reemplazo prioritario: " + ", ".join(a.name for a in high_risk))
        if expiring:
            st.warning("Garantía por vencer: " + ", ".join(a.name for a in expiring))
        if unavailable:
            st.warning("Equipos no operativos: " + ", ".join(f"{a.name} ({a.status})" for a in unavailable))

    st.markdown("### Salud del parque de equipos")
    rows = []
    for asset in sorted(assets, key=lambda x: (_asset_health(x), -x.usage_percent)):
        rows.append({
            "Equipo": asset.name,
            "Categoría": asset.category,
            "Estado": asset.status,
            "Salud": f"{_asset_health(asset)}%",
            "Uso": f"{asset.usage_percent:.1f}%",
            "Valor pendiente": asset.remaining_value,
            "Mantenimiento": maintenance_costs.get(asset.asset_id, 0.0),
            "Garantía": asset.warranty_status,
            "Reemplazo": _replacement_priority(asset),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("### Lectura financiera")
    depreciated = max(total_cost - book_value, 0.0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Inversión histórica", format_money(total_cost))
    c2.metric("Depreciación acumulada", format_money(depreciated))
    c3.metric("Valor recuperable pendiente", format_money(book_value))
    render_info_card(
        "Qué mirar primero",
        "Prioriza equipos con uso alto, garantía vencida, mantenimiento creciente o estado fuera de servicio. "
        "El objetivo no es reemplazar por antigüedad solamente, sino evitar que una falla detenga producción.",
        "DECISIÓN OPERATIVA",
    )


def _replacement_plan() -> None:
    assets = legacy_assets._get_assets()
    maintenance_costs = _maintenance_cost_by_asset()
    st.subheader("Plan de reemplazo")
    st.caption("Ordena los equipos por riesgo operativo y valor pendiente sin borrar su historial.")
    if not assets:
        st.info("No hay activos registrados.")
        return

    rows = []
    for asset in assets:
        remaining_units = max(asset.lifetime_units - asset.current_units, 0)
        rows.append({
            "Equipo": asset.name,
            "Prioridad": _replacement_priority(asset),
            "Estado": asset.status,
            "Uso %": round(asset.usage_percent, 1),
            "Unidades restantes": remaining_units,
            "Valor pendiente": round(asset.remaining_value, 2),
            "Mantenimiento acumulado": round(maintenance_costs.get(asset.asset_id, 0.0), 2),
            "Garantía": asset.warranty_status,
        })
    priority_order = {"Crítica": 0, "Alta": 1, "Media": 2, "Normal": 3}
    rows.sort(key=lambda r: (priority_order.get(r["Prioridad"], 9), -r["Uso %"]))
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("#### Reserva orientativa de reposición")
    replacement_horizon_months = st.number_input("Meses para formar la reserva", min_value=1, max_value=120, value=24, step=1)
    candidates = [a for a in assets if _replacement_priority(a) in ("Crítica", "Alta", "Media") and a.status != "Vendido"]
    target = sum(max(a.remaining_value, 0.0) for a in candidates)
    monthly = target / int(replacement_horizon_months) if replacement_horizon_months else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric("Equipos a vigilar", len(candidates))
    c2.metric("Valor pendiente considerado", format_money(target))
    c3.metric("Reserva mensual orientativa", format_money(monthly))
    st.caption("Es una referencia de planificación, no un asiento contable ni una obligación automática.")


def _maintenance_summary() -> None:
    st.subheader("Mantenimiento y garantías")
    assets = legacy_assets._get_assets()
    logs = read_list("asset_maintenance_log")
    costs = _maintenance_cost_by_asset()
    if assets:
        rows = []
        for asset in assets:
            asset_logs = [x for x in logs if x.get("asset_id") == asset.asset_id]
            last_event = max((str(x.get("event_date") or x.get("recorded_at_utc", "")) for x in asset_logs), default="")
            rows.append({
                "Equipo": asset.name,
                "Estado": asset.status,
                "Garantía": asset.warranty_status,
                "Último mantenimiento": last_event[:10] if last_event else "—",
                "Eventos": len(asset_logs),
                "Costo acumulado": round(costs.get(asset.asset_id, 0.0), 2),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No hay activos registrados.")

    st.divider()
    st.markdown("#### Planes preventivos")
    st.caption("Debajo sigue disponible el módulo completo de mantenimiento preventivo, incluidos planes por fecha o por uso.")
    machine_maintenance.render_machine_maintenance()


def _equipment_and_electrical() -> None:
    st.subheader("Equipos de papelería creativa, sublimación y soporte eléctrico")
    st.caption("Base técnica de referencia + ficha eléctrica real de tus equipos. Los valores de placa y el manual del fabricante siempre tienen prioridad.")

    family = st.selectbox("Familia", ("Todas", "Papelería creativa", "Sublimación", "Soporte", "Soporte eléctrico"))
    profiles = [p for p in equipment_knowledge.PROFILES if family == "Todas" or p.family == family]
    for profile in profiles:
        with st.expander(f"{profile.equipment} · {profile.electrical_level}"):
            st.write(profile.role)
            st.markdown("**Trabajos:** " + " · ".join(profile.typical_jobs))
            st.markdown("**Métrica de desgaste:** " + profile.usage_metric)
            st.markdown("**Repuestos/elementos de desgaste:** " + " · ".join(profile.wear_parts))
            st.markdown("**Mantenimiento:** " + " · ".join(profile.maintenance_focus))
            st.markdown("**Electricidad:** " + profile.voltage_note)
            if profile.watts_reference:
                cols = st.columns(2)
                cols[0].metric("Potencia de referencia", f"{profile.watts_reference:,.0f} W")
                cols[1].metric("Corriente publicada", f"{profile.amps_reference:,.2f} A" if profile.amps_reference else "—")
            for note in profile.electrical_notes:
                st.caption("• " + note)
            for note in profile.environment_notes:
                st.caption("Ambiente: " + note)
            st.caption("Fuente: " + profile.source_label)

    st.divider()
    st.markdown("### Ficha eléctrica real del taller")
    assets = legacy_assets._get_assets()
    asset_options = {f"{a.name} · {a.asset_id}": a for a in assets}
    rows = read_list(ELECTRICAL_AUDIT_KEY)
    with st.form("asset_electrical_profile", clear_on_submit=True):
        c1, c2 = st.columns(2)
        asset_label = c1.selectbox("Activo", ("Equipo no registrado en Activos", *asset_options.keys()))
        custom_name = c2.text_input("Nombre", disabled=asset_label != "Equipo no registrado en Activos")
        c1, c2, c3, c4 = st.columns(4)
        voltage = c1.number_input("Voltaje nominal (V)", min_value=0.0, value=120.0, step=1.0)
        watts = c2.number_input("Potencia nominal (W)", min_value=0.0, value=0.0, step=10.0)
        amps_plate = c3.number_input("Corriente de placa (A)", min_value=0.0, value=0.0, step=0.1)
        circuit_amps = c4.number_input("Circuito/disyuntor identificado (A)", min_value=0.0, value=0.0, step=1.0)
        c1, c2, c3 = st.columns(3)
        plate_verified = c1.checkbox("Verifiqué la placa/manual")
        grounded = c2.checkbox("Toma con puesta a tierra")
        protector = c3.selectbox("Protección", ("Sin registrar", "Protector de sobretensión", "Regulador AVR", "UPS", "Circuito dedicado / protección indicada por fabricante", "Otra"))
        dedicated = st.checkbox("Circuito dedicado o separado para esta carga")
        notes = st.text_area("Notas eléctricas", placeholder="Tipo de enchufe, calibre/circuito verificado por electricista, ubicación, extractor/chiller asociado, etc.")
        submitted = st.form_submit_button("Guardar ficha eléctrica", type="primary", use_container_width=True)
    if submitted:
        if asset_label == "Equipo no registrado en Activos":
            name = custom_name.strip()
            asset_id = ""
        else:
            selected_asset = asset_options[asset_label]
            name = selected_asset.name
            asset_id = selected_asset.asset_id
        if not name:
            st.error("Indica el equipo.")
        elif voltage <= 0:
            st.error("El voltaje debe ser mayor a cero.")
        else:
            calculated_amps = equipment_knowledge.electrical_current(float(watts), float(voltage))
            save_list(ELECTRICAL_AUDIT_KEY, [*rows, {
                "asset_id": asset_id, "equipment": name, "voltage": float(voltage), "watts": float(watts),
                "amps_plate": float(amps_plate), "amps_estimated": round(calculated_amps, 3),
                "circuit_amps": float(circuit_amps), "load_percent": round(equipment_knowledge.load_percent(float(amps_plate or calculated_amps), float(circuit_amps)), 1),
                "plate_verified": bool(plate_verified), "grounded": bool(grounded), "protection": protector,
                "dedicated": bool(dedicated), "notes": notes.strip(), "recorded_at_utc": now_iso(),
            }])
            st.rerun()

    rows = read_list(ELECTRICAL_AUDIT_KEY)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        total_watts = sum(float(x.get("watts", 0) or 0) for x in rows)
        thermal = [x for x in rows if float(x.get("watts", 0) or 0) >= 1000]
        c1, c2, c3 = st.columns(3)
        c1.metric("Potencia nominal registrada", f"{total_watts:,.0f} W")
        c2.metric("Cargas ≥1000 W", len(thermal))
        c3.metric("Placas verificadas", f"{sum(bool(x.get('plate_verified')) for x in rows)}/{len(rows)}")
        for row in rows:
            load = float(row.get("load_percent", 0) or 0)
            if row.get("circuit_amps") and load >= 100:
                st.error(f"{row.get('equipment')}: la corriente registrada/estimada alcanza o supera la capacidad del circuito indicada. No lo uses como validación de instalación; requiere revisión técnica.")
            elif row.get("circuit_amps") and load >= 80:
                st.warning(f"{row.get('equipment')}: la carga calculada ocupa {load:.0f}% del circuito registrado. Verifica manual, simultaneidad y código local con un profesional.")

    st.divider()
    render_info_card(
        "Reglas del taller eléctrico",
        "Separa las cargas térmicas grandes (prensas, hornos, laminadoras potentes) de la electrónica sensible; "
        "registra la placa real de cada equipo; evita regletas/extensiones sobrecargadas; conserva puesta a tierra "
        "y no uses un UPS como si automáticamente pudiera alimentar una prensa térmica.",
        "SEGURIDAD + CONTINUIDAD",
    )
    st.info("La ficha eléctrica del ERP es de control y planificación. No sustituye el dimensionamiento de circuitos, protecciones o cableado realizado según el manual del equipo y la normativa eléctrica aplicable.")


def render_assets_workspace() -> None:
    section = st.radio(
        "Área de Activos",
        ("Resumen", "Registro y ficha", "Equipos y electricidad", "Mantenimiento", "Reemplazo"),
        horizontal=True,
        label_visibility="collapsed",
        key="assets_workspace_section",
    )
    st.divider()
    if section == "Resumen":
        _dashboard()
    elif section == "Registro y ficha":
        legacy_assets.render_assets()
    elif section == "Equipos y electricidad":
        _equipment_and_electrical()
    elif section == "Mantenimiento":
        _maintenance_summary()
    else:
        _replacement_plan()
