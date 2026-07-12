"""Costeo de impresión integrado con Activos, Inventario y Configuración."""
from __future__ import annotations

import math
import streamlit as st

from src.print_cost_analyzer import MAX_FILE_MB, SUPPORTED, analyze_file
from src.print_cost_analyzer_v2 import PAPER_PRESETS, QUALITY_FACTORS, _download_report, _money
from src.print_cost_data_bridge import business_defaults, paper_costs, printer_assets


def render_print_cost_analyzer_v3() -> None:
    st.title("Análisis y costeo de impresión")
    st.caption("Usa automáticamente datos de Activos, ficha técnica, mantenimiento, inventario y configuración general.")

    printers = printer_assets()
    papers = {**PAPER_PRESETS, **paper_costs()}
    defaults = business_defaults()
    source_cols = st.columns(4)
    source_cols[0].metric("Impresoras ERP", len(printers))
    source_cols[1].metric("Papeles con costo", sum(1 for v in papers.values() if v > 0))
    source_cols[2].metric("Datos automáticos", "Activos + Config.")
    source_cols[3].metric("Modo", "Integrado")

    if not printers:
        st.warning("No hay impresoras registradas en Activos. Registra una impresora y completa su ficha técnica para evitar datos manuales.")
        return

    labels = {f"{p['name']} · {p['remaining_pages']:,} pág. restantes": p for p in printers}
    selected_label = st.selectbox("Impresora registrada", tuple(labels))
    p = labels[selected_label]
    if p["complete"]:
        st.success("Datos técnicos cargados automáticamente desde Activos y Ficha técnica de impresoras.")
    else:
        st.warning("El activo no tiene ficha técnica completa. Se usan valores provisionales; completa la ficha antes de cotizar formalmente.")
    if p["remaining_pages"] <= max(500, p["life_pages"] * .05):
        st.error("La impresora está cerca del fin de su vida útil registrada. Revisa reposición y riesgo antes de aceptar trabajos grandes.")

    uploaded = st.file_uploader("Archivo para analizar", type=SUPPORTED, help=f"Máximo recomendado: {MAX_FILE_MB} MB")
    if uploaded is None:
        st.info("Carga un PDF, JPG, PNG, DOCX, XLSX o PPTX.")
        return
    if uploaded.size > MAX_FILE_MB * 1024 * 1024:
        st.error(f"El archivo supera {MAX_FILE_MB} MB.")
        return

    with st.expander("1. Datos variables del trabajo", expanded=True):
        a, b, c, d = st.columns(4)
        copies = a.number_input("Copias", 1, 10000, 1)
        sides = b.selectbox("Caras", ["Una cara", "Doble cara"])
        quality = c.selectbox("Calidad", list(QUALITY_FACTORS))
        color_mode = d.selectbox("Modo", ["Automático", "Solo negro", "Color"])
        a, b, c, d = st.columns(4)
        paper_name = a.selectbox("Papel", list(papers))
        paper_cost = b.number_input("Costo por hoja ($)", min_value=0.0, value=float(papers[paper_name]), format="%.4f")
        waste_pct = c.number_input("Merma (%)", 0.0, 50.0, 3.0)
        setup_minutes = d.number_input("Preparación (min)", 0.0, value=3.0)

    with st.expander("2. Datos automáticos del ERP", expanded=True):
        st.caption("Estos valores se leen del activo seleccionado. Solo deben editarse desde Activos o Ficha técnica de impresoras.")
        a, b, c, d = st.columns(4)
        a.metric("Costo activo", f"${p['printer_cost']:,.2f}")
        b.metric("Vida útil", f"{p['life_pages']:,} pág.")
        c.metric("Uso acumulado", f"{p['current_pages']:,} pág.")
        d.metric("Depreciación/pág.", _money(p["depreciation_per_page"]))
        a, b, c, d = st.columns(4)
        a.metric("Rendimiento color", f"{p['color_yield']:,}")
        b.metric("Rendimiento negro", f"{p['black_yield']:,}")
        c.metric("Velocidad", f"{p['ppm']:.1f} ppm")
        d.metric("Consumo", f"{p['watts']:.1f} W")

    with st.expander("3. Política comercial"):
        a, b, c, d = st.columns(4)
        electricity_kwh = a.number_input("Electricidad ($/kWh)", 0.0, value=float(defaults["electricity_kwh"]), format="%.4f")
        labor_hour = b.number_input("Mano de obra/hora ($)", 0.0, value=float(defaults["labor_hour"]))
        overhead_pct = c.number_input("Gastos indirectos (%)", 0.0, 300.0, float(defaults["overhead_pct"]))
        margin_pct = d.number_input("Margen sobre venta (%)", 0.0, 95.0, float(defaults["margin_pct"]))
        cleaning_pct = st.number_input("Reserva de limpiezas y purgas (%)", 0.0, 50.0, 5.0)

    if not st.button("Analizar y calcular", type="primary", use_container_width=True):
        return
    try:
        with st.spinner("Analizando cobertura y calculando costos integrados..."):
            coverage = analyze_file(uploaded.name, uploaded.getvalue())
    except Exception as exc:
        st.error(f"No se pudo analizar el archivo: {exc}")
        return

    ink_factor, speed_factor = QUALITY_FACTORS[quality]
    c_cov, m_cov, y_cov, k_cov = coverage.cyan, coverage.magenta, coverage.yellow, coverage.black
    if color_mode == "Solo negro":
        c_cov = m_cov = y_cov = 0.0
        k_cov = max(k_cov, min(100.0, (coverage.cyan + coverage.magenta + coverage.yellow) / 3))
    printed_pages = int(coverage.pages * copies)
    sheets = math.ceil(printed_pages / 2) if sides == "Doble cara" else printed_pages
    billed_sheets = sheets * (1 + waste_pct / 100)
    coverages = {"C": c_cov, "M": m_cov, "Y": y_cov, "K": k_cov}
    costs = {"C": p["ink_c"], "M": p["ink_m"], "Y": p["ink_y"], "K": p["ink_k"]}
    ink_costs = {}
    for channel, pct in coverages.items():
        yield_pages = p["black_yield"] if channel == "K" else p["color_yield"]
        ink_costs[channel] = printed_pages * (pct / 5) * ink_factor / max(1, yield_pages) * costs[channel]

    paper_total = billed_sheets * paper_cost
    ink_base = sum(ink_costs.values())
    cleaning = ink_base * cleaning_pct / 100
    printer_dep = printed_pages * p["depreciation_per_page"]
    head_dep = printed_pages * p["head_cost"] / max(1, p["head_life"])
    maintenance = printed_pages * p["maintenance_page"]
    minutes = setup_minutes + printed_pages / max(.1, p["ppm"] * speed_factor)
    electricity = p["watts"] / 1000 * minutes / 60 * electricity_kwh
    labor = minutes / 60 * labor_hour
    direct = paper_total + ink_base + cleaning + printer_dep + head_dep + maintenance + electricity + labor
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

    breakdown = {
        "Papel y merma": paper_total, "Tinta C": ink_costs["C"], "Tinta M": ink_costs["M"],
        "Tinta Y": ink_costs["Y"], "Tinta K": ink_costs["K"], "Limpiezas": cleaning,
        "Depreciación del activo": printer_dep, "Depreciación de cabezales": head_dep,
        "Mantenimiento": maintenance, "Electricidad": electricity, "Mano de obra": labor, "Indirectos": overhead,
    }
    st.dataframe([{"Concepto": k, "Costo ($)": round(v, 5), "%": round(v / max(total, .00001) * 100, 2)} for k, v in breakdown.items()], use_container_width=True, hide_index=True)
    result = {"archivo": uploaded.name, "impresora_asset_id": p["asset_id"], "impresora": p["name"], "paginas": printed_pages, "hojas": sheets, "costo_total_usd": total, "precio_sugerido_usd": price, "desglose": breakdown}
    _download_report(result)
    st.info("Los datos permanentes deben corregirse en Activos, Ficha técnica, Inventario o Configuración; aquí solo se ajusta el trabajo específico.")
