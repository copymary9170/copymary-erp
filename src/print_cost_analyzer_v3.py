"""Costeo de impresión integrado con Activos, Inventario y Configuración."""
from __future__ import annotations

import math
import streamlit as st

from src.print_cost_analyzer import MAX_FILE_MB, SUPPORTED, analyze_file
from src.print_cost_analyzer_v2 import QUALITY_FACTORS, _download_report, _money
from src.print_cost_data_bridge import business_defaults, paper_inventory, printer_assets


def _consumable_costs(p: dict, pages: int, coverages: dict[str, float], ink_factor: float) -> tuple[dict[str, float], dict[str, float]]:
    """Calcula consumibles según la tecnología real del equipo."""
    tech = p["technology"]
    costs: dict[str, float] = {}
    components: dict[str, float] = {}

    if tech == "Inyección con cartuchos" and p["cartridge_layout"] == "tricolor":
        costs["Cartucho negro"] = pages * (coverages["K"] / 5) * ink_factor / max(1, p["black_yield"]) * p["black_cost"]
        dominant_color = max(coverages["C"], coverages["M"], coverages["Y"])
        costs["Cartucho tricolor"] = pages * (dominant_color / 5) * ink_factor / max(1, p["color_yield"]) * p["color_cost"]
    elif tech == "Láser monocromática":
        grayscale = max(coverages["K"], (coverages["C"] + coverages["M"] + coverages["Y"]) / 3)
        costs["Tóner negro"] = pages * (grayscale / 5) * ink_factor / max(1, p["black_yield"]) * p["black_cost"]
    else:
        prefix = "Tóner" if tech == "Láser color" else ("Cartucho" if tech == "Inyección con cartuchos" else "Tinta")
        channel_data = {
            "C": (p["c_cost"], p["c_yield"]),
            "M": (p["m_cost"], p["m_yield"]),
            "Y": (p["y_cost"], p["y_yield"]),
            "K": (p["black_cost"], p["black_yield"]),
        }
        for channel, coverage in coverages.items():
            cost, yield_pages = channel_data[channel]
            costs[f"{prefix} {channel}"] = pages * (coverage / 5) * ink_factor / max(1, yield_pages) * cost

    if tech.startswith("Inyección") and p["head_cost"] > 0:
        components["Desgaste de cabezales"] = pages * p["head_cost"] / max(1, p["head_life"])
    if tech.startswith("Láser"):
        components["Desgaste de tambor"] = pages * p["drum_cost"] / max(1, p["drum_life"])
        components["Desgaste de fusor"] = pages * p["fuser_cost"] / max(1, p["fuser_life"])
    return costs, components


def render_print_cost_analyzer_v3() -> None:
    st.title("Análisis y costeo de impresión")
    st.caption("Costea botellas de tinta, cartuchos y tóner según la tecnología registrada en Activos.")

    printers = printer_assets()
    papers = paper_inventory()
    defaults = business_defaults()
    valid_papers = [paper for paper in papers if paper["valid_cost"] and paper["available"]]

    source_cols = st.columns(4)
    source_cols[0].metric("Impresoras ERP", len(printers))
    source_cols[1].metric("Papeles en Inventario", len(papers))
    source_cols[2].metric("Papeles utilizables", len(valid_papers))
    source_cols[3].metric("Consumibles", "Tinta · Cartucho · Tóner")

    if not printers:
        st.warning("No hay impresoras registradas en Activos. Registra una impresora y completa su ficha técnica.")
        return
    if not papers:
        st.error("No hay papeles registrados en Inventario. Registra el papel, costo unitario y existencia antes de cotizar.")
        return
    if not valid_papers:
        st.error("Ningún papel de Inventario posee costo válido y stock disponible.")
        st.dataframe([{"Papel": p["name"], "Costo": p["unit_cost"], "Stock": p["stock"], "Unidad": p["unit"]} for p in papers], use_container_width=True, hide_index=True)
        return

    labels = {f"{p['name']} · {p['technology']} · {p['remaining_pages']:,} pág. restantes": p for p in printers}
    selected_label = st.selectbox("Impresora registrada", tuple(labels))
    p = labels[selected_label]
    if p["complete"]:
        st.success(f"Ficha cargada: {p['technology']}.")
    else:
        st.error("La impresora no tiene ficha técnica. Debes indicar si usa botellas, cartuchos o tóner antes de cotizar.")
        return
    if p["remaining_pages"] <= max(500, p["life_pages"] * .05):
        st.error("La impresora está cerca del final de su vida útil registrada.")

    uploaded = st.file_uploader("Archivo para analizar", type=SUPPORTED, help=f"Máximo recomendado: {MAX_FILE_MB} MB")
    if uploaded is None:
        st.info("Carga un PDF, JPG, PNG, DOCX, XLSX o PPTX.")
        return
    if uploaded.size > MAX_FILE_MB * 1024 * 1024:
        st.error(f"El archivo supera {MAX_FILE_MB} MB.")
        return

    paper_labels = {f"{paper['name']} · stock {paper['stock']:,.2f} {paper['unit']}": paper for paper in valid_papers}
    with st.expander("1. Datos variables del trabajo", expanded=True):
        a, b, c, d = st.columns(4)
        copies = a.number_input("Copias", 1, 10000, 1)
        sides = b.selectbox("Caras", ["Una cara", "Doble cara"])
        quality = c.selectbox("Calidad", list(QUALITY_FACTORS))
        allowed_modes = ["Automático", "Solo negro"] if p["technology"] == "Láser monocromática" else ["Automático", "Solo negro", "Color"]
        color_mode = d.selectbox("Modo", allowed_modes)
        a, b, c = st.columns(3)
        selected_paper_label = a.selectbox("Papel de Inventario", tuple(paper_labels))
        selected_paper = paper_labels[selected_paper_label]
        b.metric("Costo desde Inventario", f"${selected_paper['unit_cost']:,.4f} / {selected_paper['unit']}")
        c.metric("Stock disponible", f"{selected_paper['stock']:,.2f} {selected_paper['unit']}")
        a, b = st.columns(2)
        waste_pct = a.number_input("Merma (%)", 0.0, 50.0, 3.0)
        setup_minutes = b.number_input("Preparación (min)", 0.0, value=3.0)

    with st.expander("2. Equipo y consumibles automáticos", expanded=True):
        st.caption("Se editan únicamente desde Activos y Ficha técnica de impresoras.")
        a, b, c, d = st.columns(4)
        a.metric("Tecnología", p["technology"])
        b.metric("Costo activo", f"${p['printer_cost']:,.2f}")
        c.metric("Depreciación/pág.", _money(p["depreciation_per_page"]))
        d.metric("Consumo", f"{p['watts']:.1f} W")
        a, b, c, d = st.columns(4)
        a.metric("Consumible negro", f"${p['black_cost']:,.2f}")
        b.metric("Rendimiento negro", f"{p['black_yield']:,}")
        c.metric("Velocidad", f"{p['ppm']:.1f} ppm")
        d.metric("Vida restante", f"{p['remaining_pages']:,} pág.")

    with st.expander("3. Política comercial"):
        a, b, c, d = st.columns(4)
        electricity_kwh = a.number_input("Electricidad ($/kWh)", 0.0, value=float(defaults["electricity_kwh"]), format="%.4f")
        labor_hour = b.number_input("Mano de obra/hora ($)", 0.0, value=float(defaults["labor_hour"]))
        overhead_pct = c.number_input("Gastos indirectos (%)", 0.0, 300.0, float(defaults["overhead_pct"]))
        margin_pct = d.number_input("Margen sobre venta (%)", 0.0, 95.0, float(defaults["margin_pct"]))
        cleaning_pct = 0.0
        if p["technology"].startswith("Inyección"):
            cleaning_pct = st.number_input("Reserva de limpiezas y purgas (%)", 0.0, 50.0, 5.0)
        else:
            st.caption("En tecnología láser no se aplica reserva de purgas; se costean tambor y fusor.")

    if not st.button("Analizar y calcular", type="primary", use_container_width=True):
        return
    try:
        with st.spinner("Analizando cobertura y calculando consumibles..."):
            coverage = analyze_file(uploaded.name, uploaded.getvalue())
    except Exception as exc:
        st.error(f"No se pudo analizar el archivo: {exc}")
        return

    ink_factor, speed_factor = QUALITY_FACTORS[quality]
    c_cov, m_cov, y_cov, k_cov = coverage.cyan, coverage.magenta, coverage.yellow, coverage.black
    if color_mode == "Solo negro" or p["technology"] == "Láser monocromática":
        k_cov = max(k_cov, min(100.0, (c_cov + m_cov + y_cov) / 3))
        c_cov = m_cov = y_cov = 0.0
    printed_pages = int(coverage.pages * copies)
    sheets = math.ceil(printed_pages / 2) if sides == "Doble cara" else printed_pages
    billed_sheets = math.ceil(sheets * (1 + waste_pct / 100))
    if billed_sheets > selected_paper["stock"]:
        shortage = billed_sheets - selected_paper["stock"]
        st.error(f"Stock insuficiente: se requieren {billed_sheets:,} {selected_paper['unit']}; faltan {shortage:,.2f}.")
        return

    coverages = {"C": c_cov, "M": m_cov, "Y": y_cov, "K": k_cov}
    consumable_costs, component_costs = _consumable_costs(p, printed_pages, coverages, ink_factor)
    paper_total = billed_sheets * selected_paper["unit_cost"]
    consumables_total = sum(consumable_costs.values())
    cleaning = consumables_total * cleaning_pct / 100
    printer_dep = printed_pages * p["depreciation_per_page"]
    maintenance = printed_pages * p["maintenance_page"]
    minutes = setup_minutes + printed_pages / max(.1, p["ppm"] * speed_factor)
    electricity = p["watts"] / 1000 * minutes / 60 * electricity_kwh
    labor = minutes / 60 * labor_hour
    direct = paper_total + consumables_total + cleaning + printer_dep + sum(component_costs.values()) + maintenance + electricity + labor
    overhead = direct * overhead_pct / 100
    total = direct + overhead
    price = total / max(.05, 1 - margin_pct / 100)

    st.subheader("Resultado integrado")
    cols = st.columns(6)
    for col, label, value in zip(cols, ["Cian", "Magenta", "Amarillo", "Negro"], [c_cov, m_cov, y_cov, k_cov]):
        col.metric(label, f"{value:.1f}%")
    cols[4].metric("Costo total", _money(total))
    cols[5].metric("Precio sugerido", f"${price:,.2f}")
    st.caption(f"{coverage.confidence}: {coverage.note}")
    st.success(f"{p['technology']} · papel {selected_paper['name']} · saldo proyectado {selected_paper['stock'] - billed_sheets:,.2f} {selected_paper['unit']}.")

    breakdown = {
        "Papel de Inventario y merma": paper_total,
        **consumable_costs,
        **component_costs,
        **({"Limpiezas y purgas": cleaning} if cleaning > 0 else {}),
        "Depreciación del activo": printer_dep,
        "Mantenimiento": maintenance,
        "Electricidad": electricity,
        "Mano de obra": labor,
        "Indirectos": overhead,
    }
    st.dataframe([{"Concepto": k, "Costo ($)": round(v, 5), "%": round(v / max(total, .00001) * 100, 2)} for k, v in breakdown.items()], use_container_width=True, hide_index=True)
    result = {
        "archivo": uploaded.name,
        "impresora_asset_id": p["asset_id"], "impresora": p["name"], "tecnologia": p["technology"],
        "papel_inventory_id": selected_paper["item_id"], "papel": selected_paper["name"],
        "papel_costo_unitario": selected_paper["unit_cost"], "papel_stock_antes": selected_paper["stock"],
        "papel_consumo_estimado": billed_sheets, "papel_stock_proyectado": selected_paper["stock"] - billed_sheets,
        "paginas": printed_pages, "hojas": sheets, "costo_total_usd": total, "precio_sugerido_usd": price,
        "desglose": breakdown,
    }
    _download_report(result)
    st.info("Los consumibles se configuran según la tecnología real: botellas, cartuchos o tóner. El papel continúa saliendo exclusivamente de Inventario.")
