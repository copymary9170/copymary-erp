"""Costeo avanzado con escenarios, punto de equilibrio y trazabilidad."""

from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import costing as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("costing_scenarios", "Escenarios de costeo"),
        ("costing_history", "Historial de costeo"),
        ("costing_material_lines", "Líneas de materiales de costeo"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = (
        "general_settings",
        *session_backup.LIST_SECTIONS,
        *session_backup.DICT_SECTIONS,
    )


_activate_backup()


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _inventory_unit_cost(item: dict) -> float:
    return _num(item.get("purchase_cost")) / max(_num(item.get("purchased_quantity"), 1.0), 0.01)


def _asset_unit_cost(asset: dict) -> float:
    return _num(asset.get("acquisition_cost")) / max(_num(asset.get("lifetime_units"), 1.0), 1.0)


def _price_from_margin(cost: float, margin_percent: float) -> float:
    margin = min(max(margin_percent / 100.0, 0.0), 0.95)
    return cost / max(1.0 - margin, 0.05)


def _price_from_markup(cost: float, markup_percent: float) -> float:
    return cost * (1.0 + max(markup_percent, 0.0) / 100.0)


def _effective_margin(price: float, cost: float) -> float:
    return ((price - cost) / price * 100.0) if price > 0 else 0.0


def _material_total(lines: list[dict]) -> float:
    return sum(_num(line.get("quantity")) * _num(line.get("unit_cost")) * (1.0 + _num(line.get("waste_percent")) / 100.0) for line in lines)


def _export_history(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Fecha", "Producto", "Cantidad", "Costo unitario", "Precio unitario",
        "Margen efectivo", "Ganancia total", "Moneda", "Responsable",
    ])
    for row in rows:
        writer.writerow([
            row.get("costing_id", ""), row.get("created_at_utc", ""), row.get("name", ""),
            row.get("quantity", 0), row.get("unit_cost", 0), row.get("unit_price", 0),
            row.get("effective_margin", 0), row.get("total_profit", 0), row.get("currency", ""),
            row.get("responsible", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_costing_plus() -> None:
    render_page_header(
        "Costeo",
        "Calcula costos completos, compara escenarios y protege el margen antes de fijar precios.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_costing()
    finally:
        base.render_page_header = original_header

    inventory = _rows("inventory_registry")
    assets = _rows("assets_registry")
    scenarios = _rows("costing_scenarios")
    history = _rows("costing_history")
    material_lines = _rows("costing_material_lines")
    currency = get_currency()

    st.divider()
    st.markdown("### Costeo avanzado")
    total_models = len(history)
    avg_margin = sum(_num(row.get("effective_margin")) for row in history) / max(total_models, 1)
    low_margin = [row for row in history if _num(row.get("effective_margin")) < 20]
    total_projected_profit = sum(_num(row.get("total_profit")) for row in history)
    metrics = st.columns(5)
    metrics[0].metric("Costeos guardados", str(total_models))
    metrics[1].metric("Escenarios", str(len(scenarios)))
    metrics[2].metric("Margen promedio", f"{avg_margin:,.1f}%")
    metrics[3].metric("Margen bajo", str(len(low_margin)))
    metrics[4].metric("Ganancia proyectada", format_money(total_projected_profit, currency))

    materials_tab, calculator_tab, scenarios_tab, breakeven_tab, history_tab = st.tabs(
        ("Materiales", "Calculadora avanzada", "Escenarios", "Punto de equilibrio", "Historial")
    )

    with materials_tab:
        st.caption("Construye una lista de materiales para incluir varios insumos en el mismo producto.")
        options = {f"{item.get('name', 'Material')} · {item.get('item_id', '')}": item for item in inventory}
        if not options:
            st.info("No hay materiales registrados. Puedes usar líneas manuales.")
        with st.form("costing_material_line_form", clear_on_submit=True):
            source = st.selectbox("Origen", ("Inventario", "Manual"))
            selected_label = st.selectbox("Material", tuple(options.keys()) if options else ("Sin materiales",), disabled=source == "Manual")
            columns = st.columns(4)
            manual_name = columns[0].text_input("Nombre manual", disabled=source == "Inventario")
            quantity = columns[1].number_input("Cantidad por unidad de venta", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
            manual_cost = columns[2].number_input("Costo unitario manual", min_value=0.0, value=0.0, step=0.01, disabled=source == "Inventario")
            waste_percent = columns[3].number_input("Merma %", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
            submitted = st.form_submit_button("Agregar material", type="primary", use_container_width=True)
        if submitted:
            if source == "Inventario" and options:
                item = options[selected_label]
                name = str(item.get("name", "Material"))
                item_id = str(item.get("item_id", ""))
                unit_cost = _inventory_unit_cost(item)
            else:
                name = manual_name.strip()
                item_id = ""
                unit_cost = float(manual_cost)
            if not name or unit_cost <= 0:
                st.error("El material debe tener nombre y costo mayor que cero.")
            else:
                material_lines.append({
                    "line_id": uuid4().hex[:8],
                    "item_id": item_id,
                    "name": name,
                    "quantity": float(quantity),
                    "unit_cost": float(unit_cost),
                    "waste_percent": float(waste_percent),
                    "created_at_utc": _now(),
                })
                _save("costing_material_lines", material_lines)
                st.rerun()

        for line in material_lines:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{line.get('name', 'Material')}**")
                cols[0].caption(f"Costo unitario {format_money(_num(line.get('unit_cost')), currency)}")
                cols[1].metric("Cantidad", f"{_num(line.get('quantity')):,.4f}")
                cols[2].metric("Merma", f"{_num(line.get('waste_percent')):,.1f}%")
                total = _num(line.get("quantity")) * _num(line.get("unit_cost")) * (1 + _num(line.get("waste_percent")) / 100)
                cols[3].metric("Costo", format_money(total, currency))
                if st.button("Eliminar línea", key=f"delete_cost_line_{line.get('line_id')}", use_container_width=True):
                    _save("costing_material_lines", [row for row in material_lines if row.get("line_id") != line.get("line_id")])
                    st.rerun()

    with calculator_tab:
        with st.form("advanced_costing_form"):
            first = st.columns(4)
            name = first[0].text_input("Producto o servicio")
            quantity = first[1].number_input("Cantidad a producir", min_value=1, value=1, step=1)
            pricing_method = first[2].selectbox("Método de precio", ("Margen sobre venta", "Markup sobre costo"))
            target_percent = first[3].number_input("Porcentaje objetivo", min_value=0.0, max_value=500.0, value=40.0, step=1.0)

            material_cost = _material_total(material_lines)
            second = st.columns(4)
            ink_cost = second[0].number_input("Tinta por unidad", min_value=0.0, value=0.0, step=0.01)
            labor_minutes = second[1].number_input("Minutos de trabajo", min_value=0.0, value=0.0, step=1.0)
            hourly_rate = second[2].number_input("Costo por hora", min_value=0.0, value=0.0, step=0.5)
            indirect_cost = second[3].number_input("Indirectos por unidad", min_value=0.0, value=0.0, step=0.01)

            asset_options = {f"{asset.get('name', 'Equipo')} · {asset.get('asset_id', '')}": asset for asset in assets}
            third = st.columns(4)
            selected_asset_label = third[0].selectbox("Equipo", ("Sin equipo", *asset_options.keys()))
            payment_fee = third[1].number_input("Comisión de cobro %", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
            tax_percent = third[2].number_input("Impuesto %", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
            contingency_percent = third[3].number_input("Contingencia %", min_value=0.0, max_value=100.0, value=5.0, step=1.0)

            responsible = st.text_input("Responsable del cálculo")
            submitted = st.form_submit_button("Calcular costeo completo", type="primary", use_container_width=True)

        if submitted:
            labor_cost = (float(labor_minutes) / 60.0) * float(hourly_rate)
            asset_cost = 0.0 if selected_asset_label == "Sin equipo" else _asset_unit_cost(asset_options[selected_asset_label])
            direct_cost = material_cost + float(ink_cost) + labor_cost + float(indirect_cost) + asset_cost
            contingency = direct_cost * float(contingency_percent) / 100.0
            base_cost = direct_cost + contingency
            raw_price = _price_from_margin(base_cost, float(target_percent)) if pricing_method == "Margen sobre venta" else _price_from_markup(base_cost, float(target_percent))
            grossed_price = raw_price / max(1.0 - float(payment_fee) / 100.0 - float(tax_percent) / 100.0, 0.01)
            effective_margin = _effective_margin(grossed_price, base_cost)
            total_profit = (grossed_price - base_cost) * int(quantity)
            result = {
                "costing_id": f"CST-{uuid4().hex[:8].upper()}",
                "name": name.strip() or "Producto sin nombre",
                "quantity": int(quantity),
                "material_cost": material_cost,
                "ink_cost": float(ink_cost),
                "labor_cost": labor_cost,
                "indirect_cost": float(indirect_cost),
                "asset_cost": asset_cost,
                "contingency_cost": contingency,
                "unit_cost": base_cost,
                "unit_price": grossed_price,
                "effective_margin": effective_margin,
                "total_profit": total_profit,
                "pricing_method": pricing_method,
                "target_percent": float(target_percent),
                "payment_fee": float(payment_fee),
                "tax_percent": float(tax_percent),
                "responsible": responsible.strip() or "Sin asignar",
                "currency": currency,
                "created_at_utc": _now(),
            }
            st.session_state["advanced_costing_result"] = result

        result = st.session_state.get("advanced_costing_result")
        if isinstance(result, dict):
            cols = st.columns(5)
            cols[0].metric("Costo unitario", format_money(_num(result.get("unit_cost")), currency))
            cols[1].metric("Precio sugerido", format_money(_num(result.get("unit_price")), currency))
            cols[2].metric("Margen efectivo", f"{_num(result.get('effective_margin')):,.1f}%")
            cols[3].metric("Ganancia total", format_money(_num(result.get("total_profit")), currency))
            cols[4].metric("Venta total", format_money(_num(result.get("unit_price")) * int(_num(result.get("quantity"), 1)), currency))

            if _num(result.get("effective_margin")) < 20:
                st.error("El margen efectivo es inferior a 20%. Revisa costos, comisiones o precio.")
            elif _num(result.get("effective_margin")) < 35:
                st.warning("El margen efectivo es moderado. Conviene validar el riesgo y la competencia.")
            else:
                st.success("El margen efectivo está dentro de un rango saludable.")

            if st.button("Guardar costeo en historial", type="primary", use_container_width=True):
                history.append(dict(result))
                _save("costing_history", history)
                st.success("Costeo guardado.")
                st.rerun()

    with scenarios_tab:
        st.caption("Compara cómo cambia la rentabilidad cuando suben los costos o cambia el precio.")
        base_result = st.session_state.get("advanced_costing_result")
        if not isinstance(base_result, dict):
            st.info("Primero calcula un costeo completo.")
        else:
            with st.form("costing_scenario_form", clear_on_submit=True):
                cols = st.columns(4)
                scenario_name = cols[0].text_input("Nombre del escenario")
                cost_change = cols[1].number_input("Variación de costos %", min_value=-90.0, max_value=500.0, value=0.0, step=1.0)
                price_change = cols[2].number_input("Variación de precio %", min_value=-90.0, max_value=500.0, value=0.0, step=1.0)
                scenario_quantity = cols[3].number_input("Cantidad", min_value=1, value=int(_num(base_result.get("quantity"), 1)), step=1)
                submitted = st.form_submit_button("Guardar escenario", type="primary", use_container_width=True)
            if submitted:
                cost = _num(base_result.get("unit_cost")) * (1 + float(cost_change) / 100)
                price = _num(base_result.get("unit_price")) * (1 + float(price_change) / 100)
                scenarios.append({
                    "scenario_id": f"ESC-{uuid4().hex[:8].upper()}",
                    "name": scenario_name.strip() or "Escenario",
                    "product_name": str(base_result.get("name", "Producto")),
                    "unit_cost": cost,
                    "unit_price": price,
                    "quantity": int(scenario_quantity),
                    "effective_margin": _effective_margin(price, cost),
                    "total_profit": (price - cost) * int(scenario_quantity),
                    "created_at_utc": _now(),
                })
                _save("costing_scenarios", scenarios)
                st.rerun()

        for scenario in scenarios:
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{scenario.get('name', 'Escenario')} · {scenario.get('product_name', '')}**")
                cols[1].metric("Costo", format_money(_num(scenario.get("unit_cost")), currency))
                cols[2].metric("Precio", format_money(_num(scenario.get("unit_price")), currency))
                cols[3].metric("Margen", f"{_num(scenario.get('effective_margin')):,.1f}%")

    with breakeven_tab:
        with st.form("breakeven_form"):
            cols = st.columns(3)
            fixed_monthly = cols[0].number_input("Costos fijos mensuales", min_value=0.0, value=0.0, step=1.0)
            unit_price = cols[1].number_input("Precio unitario", min_value=0.0, value=0.0, step=0.1)
            variable_cost = cols[2].number_input("Costo variable unitario", min_value=0.0, value=0.0, step=0.1)
            submitted = st.form_submit_button("Calcular punto de equilibrio", type="primary", use_container_width=True)
        if submitted:
            contribution = float(unit_price) - float(variable_cost)
            if contribution <= 0:
                st.error("El precio debe superar el costo variable.")
            else:
                units = float(fixed_monthly) / contribution
                sales_value = units * float(unit_price)
                cols = st.columns(3)
                cols[0].metric("Contribución unitaria", format_money(contribution, currency))
                cols[1].metric("Unidades para equilibrio", f"{units:,.2f}")
                cols[2].metric("Ventas para equilibrio", format_money(sales_value, currency))

    with history_tab:
        st.download_button(
            "Descargar historial CSV",
            data=_export_history(history),
            file_name=f"historial_costeo_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not history,
        )
        by_product: dict[str, list[dict]] = defaultdict(list)
        for row in history:
            by_product[str(row.get("name", "Producto"))].append(row)
        for product, rows in by_product.items():
            latest = rows[-1]
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1])
                cols[0].markdown(f"**{product}**")
                cols[0].caption(f"Último cálculo: {latest.get('created_at_utc', '')} · {latest.get('responsible', '')}")
                cols[1].metric("Costo", format_money(_num(latest.get("unit_cost")), currency))
                cols[2].metric("Precio", format_money(_num(latest.get("unit_price")), currency))
                cols[3].metric("Margen", f"{_num(latest.get('effective_margin')):,.1f}%")

    render_info_card(
        "Precio con respaldo",
        "El costeo avanzado separa margen de markup, incluye comisiones, impuestos, merma, equipo y escenarios.",
        "RENTABILIDAD",
    )
