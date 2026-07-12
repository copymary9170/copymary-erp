"""Versión empresarial del análisis y costeo de impresión."""
from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import asdict

import streamlit as st

from src.print_cost_analyzer import MAX_FILE_MB, SUPPORTED, analyze_file

PAPER_PRESETS = {
    "Bond carta 75 g": 0.0180,
    "Bond oficio 75 g": 0.0240,
    "Fotográfico mate": 0.2500,
    "Fotográfico brillante": 0.1800,
    "Opalina": 0.2500,
    "Adhesivo": 0.3000,
    "Personalizado": 0.0000,
}

PRINTER_PRESETS = {
    "HP Smart Tank 580": {
        "printer_cost": 230.0, "life_pages": 50000, "head_cost": 100.0,
        "head_life": 30000, "color_yield": 6000, "black_yield": 12000,
        "ink_cost": 19.0, "ppm": 8.0, "watts": 18.0,
    },
    "Epson EcoTank L3250": {
        "printer_cost": 220.0, "life_pages": 50000, "head_cost": 85.0,
        "head_life": 35000, "color_yield": 7500, "black_yield": 4500,
        "ink_cost": 16.0, "ppm": 7.0, "watts": 16.0,
    },
    "Personalizado": {
        "printer_cost": 200.0, "life_pages": 40000, "head_cost": 80.0,
        "head_life": 25000, "color_yield": 6000, "black_yield": 10000,
        "ink_cost": 18.0, "ppm": 7.0, "watts": 18.0,
    },
}

QUALITY_FACTORS = {
    "Borrador": (0.72, 1.35),
    "Normal": (1.00, 1.00),
    "Alta": (1.18, 0.72),
    "Fotográfica": (1.42, 0.42),
}


def _money(value: float) -> str:
    return f"${value:,.4f}"


def _download_report(result: dict) -> None:
    c1, c2 = st.columns(2)
    c1.download_button(
        "Descargar resumen JSON",
        data=json.dumps(result, ensure_ascii=False, indent=2),
        file_name="costeo_impresion.json",
        mime="application/json",
        use_container_width=True,
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["concepto", "costo_usd"])
    writer.writeheader()
    for concept, value in result["desglose"].items():
        writer.writerow({"concepto": concept, "costo_usd": round(value, 6)})
    c2.download_button(
        "Descargar desglose CSV",
        data=buffer.getvalue(),
        file_name="desglose_costeo_impresion.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_print_cost_analyzer_v2() -> None:
    st.title("Análisis y costeo de impresión")
    st.caption("Preprensa, cobertura CMYK, consumo técnico, desgaste y precio recomendado por trabajo.")

    uploaded = st.file_uploader(
        "Archivo para analizar",
        type=SUPPORTED,
        help=f"PDF, JPG, PNG, DOCX, XLSX o PPTX. Máximo recomendado: {MAX_FILE_MB} MB.",
    )
    if uploaded is None:
        st.info("Carga un archivo para calcular su costo realista de producción.")
        return
    if uploaded.size > MAX_FILE_MB * 1024 * 1024:
        st.error(f"El archivo supera el límite recomendado de {MAX_FILE_MB} MB.")
        return

    with st.expander("1. Trabajo de impresión", expanded=True):
        a, b, c, d = st.columns(4)
        copies = a.number_input("Copias", min_value=1, max_value=10000, value=1)
        sides = b.selectbox("Caras", ["Una cara", "Doble cara"])
        quality = c.selectbox("Calidad", list(QUALITY_FACTORS))
        color_mode = d.selectbox("Modo", ["Automático", "Solo negro", "Color"])

        a, b, c, d = st.columns(4)
        paper_name = a.selectbox("Papel", list(PAPER_PRESETS))
        paper_cost = b.number_input(
            "Costo por hoja ($)", min_value=0.0,
            value=float(PAPER_PRESETS[paper_name]), format="%.4f",
        )
        waste_pct = c.number_input("Merma (%)", min_value=0.0, max_value=50.0, value=3.0)
        setup_minutes = d.number_input("Preparación (min)", min_value=0.0, value=3.0)

    with st.expander("2. Impresora, tinta y desgaste", expanded=True):
        profile = st.selectbox("Perfil de impresora", list(PRINTER_PRESETS))
        p = PRINTER_PRESETS[profile]
        a, b, c, d = st.columns(4)
        printer_cost = a.number_input("Costo impresora ($)", min_value=0.0, value=p["printer_cost"])
        life_pages = b.number_input("Vida útil (páginas)", min_value=1, value=p["life_pages"])
        head_cost = c.number_input("Costo cabezales ($)", min_value=0.0, value=p["head_cost"])
        head_life = d.number_input("Vida cabezales (páginas)", min_value=1, value=p["head_life"])

        a, b, c, d = st.columns(4)
        ink_c = a.number_input("Botella C ($)", min_value=0.0, value=p["ink_cost"])
        ink_m = b.number_input("Botella M ($)", min_value=0.0, value=p["ink_cost"])
        ink_y = c.number_input("Botella Y ($)", min_value=0.0, value=p["ink_cost"])
        ink_k = d.number_input("Botella K ($)", min_value=0.0, value=p["ink_cost"])

        a, b, c, d = st.columns(4)
        color_yield = a.number_input("Rendimiento color al 5%", min_value=1, value=p["color_yield"])
        black_yield = b.number_input("Rendimiento negro al 5%", min_value=1, value=p["black_yield"])
        ppm = c.number_input("Velocidad real (ppm)", min_value=0.1, value=p["ppm"])
        watts = d.number_input("Consumo imprimiendo (W)", min_value=0.1, value=p["watts"])

        a, b, c, d = st.columns(4)
        maintenance_page = a.number_input("Mantenimiento/página ($)", min_value=0.0, value=0.0030, format="%.4f")
        cleaning_pct = b.number_input("Reserva limpiezas (%)", min_value=0.0, max_value=50.0, value=5.0)
        electricity_kwh = c.number_input("Electricidad ($/kWh)", min_value=0.0, value=0.10, format="%.4f")
        labor_hour = d.number_input("Mano de obra/hora ($)", min_value=0.0, value=2.50)

    with st.expander("3. Precio de venta"):
        a, b, c = st.columns(3)
        overhead_pct = a.number_input("Gastos indirectos (%)", min_value=0.0, max_value=300.0, value=10.0)
        margin_pct = b.number_input("Margen sobre venta (%)", min_value=0.0, max_value=95.0, value=40.0)
        rounding = c.selectbox("Redondear precio", ["Sin redondeo", "$0.05", "$0.10", "$0.50", "$1.00"])

    if not st.button("Analizar archivo y calcular", type="primary", use_container_width=True):
        return

    try:
        with st.spinner("Analizando archivo y calculando consumo..."):
            coverage = analyze_file(uploaded.name, uploaded.getvalue())
    except Exception as exc:
        st.error(f"No se pudo analizar el archivo: {exc}")
        return

    ink_factor, speed_factor = QUALITY_FACTORS[quality]
    c_cov, m_cov, y_cov, k_cov = coverage.cyan, coverage.magenta, coverage.yellow, coverage.black
    if color_mode == "Solo negro":
        c_cov = m_cov = y_cov = 0.0
        k_cov = max(k_cov, min(100.0, (coverage.cyan + coverage.magenta + coverage.yellow) / 3))
    elif color_mode == "Color" and c_cov + m_cov + y_cov < 0.5:
        st.warning("El archivo parece mayormente monocromático aunque se seleccionó modo Color.")

    printed_pages = int(coverage.pages * copies)
    sheets = math.ceil(printed_pages / 2) if sides == "Doble cara" else printed_pages
    billed_sheets = sheets * (1 + waste_pct / 100)

    coverages = {"C": c_cov, "M": m_cov, "Y": y_cov, "K": k_cov}
    bottle_costs = {"C": ink_c, "M": ink_m, "Y": ink_y, "K": ink_k}
    ink_costs = {}
    for channel, pct in coverages.items():
        yield_pages = black_yield if channel == "K" else color_yield
        equivalent_pages = printed_pages * (pct / 5.0) * ink_factor
        ink_costs[channel] = equivalent_pages / yield_pages * bottle_costs[channel]

    paper_total = billed_sheets * paper_cost
    ink_base = sum(ink_costs.values())
    cleaning_reserve = ink_base * cleaning_pct / 100
    printer_depreciation = printed_pages * printer_cost / life_pages
    head_depreciation = printed_pages * head_cost / head_life
    maintenance = printed_pages * maintenance_page
    minutes = setup_minutes + printed_pages / max(0.1, ppm * speed_factor)
    electricity = watts / 1000 * minutes / 60 * electricity_kwh
    labor = minutes / 60 * labor_hour

    direct_cost = paper_total + ink_base + cleaning_reserve + printer_depreciation + head_depreciation + maintenance + electricity + labor
    overhead = direct_cost * overhead_pct / 100
    total_cost = direct_cost + overhead
    suggested_price = total_cost / max(0.05, 1 - margin_pct / 100)
    rounding_steps = {"Sin redondeo": 0, "$0.05": .05, "$0.10": .10, "$0.50": .50, "$1.00": 1.0}
    step = rounding_steps[rounding]
    if step:
        suggested_price = math.ceil(suggested_price / step) * step

    st.subheader("Diagnóstico de cobertura")
    cols = st.columns(5)
    for col, label, value in zip(cols[:4], ["Cian", "Magenta", "Amarillo", "Negro"], [c_cov, m_cov, y_cov, k_cov]):
        col.metric(label, f"{value:.1f}%")
    cols[4].metric("Confianza", coverage.confidence)
    st.caption(coverage.note)

    if max(c_cov, m_cov, y_cov, k_cov) > 80:
        st.warning("Cobertura muy alta: conviene considerar secado, absorción, saturación y posibles pasadas adicionales.")
    if paper_name.startswith("Fotográfico") and quality not in {"Alta", "Fotográfica"}:
        st.info("Para papel fotográfico suele ser más realista usar calidad Alta o Fotográfica.")

    st.subheader("Resultado económico")
    cols = st.columns(6)
    cols[0].metric("Páginas", f"{printed_pages:,}")
    cols[1].metric("Hojas", f"{sheets:,}")
    cols[2].metric("Tiempo", f"{minutes:.1f} min")
    cols[3].metric("Costo total", _money(total_cost))
    cols[4].metric("Costo/página", _money(total_cost / max(1, printed_pages)))
    cols[5].metric("Precio sugerido", f"${suggested_price:,.2f}")

    breakdown = {
        "Papel y merma": paper_total,
        "Tinta C": ink_costs["C"], "Tinta M": ink_costs["M"],
        "Tinta Y": ink_costs["Y"], "Tinta K": ink_costs["K"],
        "Reserva de limpiezas": cleaning_reserve,
        "Depreciación impresora": printer_depreciation,
        "Depreciación cabezales": head_depreciation,
        "Mantenimiento y desgaste": maintenance,
        "Electricidad": electricity,
        "Preparación y mano de obra": labor,
        "Gastos indirectos": overhead,
    }
    rows = [
        {"Concepto": name, "Costo ($)": round(value, 5), "% del costo": round(value / max(total_cost, .00001) * 100, 2)}
        for name, value in breakdown.items()
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    result = {
        "archivo": uploaded.name,
        "analisis": asdict(coverage),
        "trabajo": {"copias": copies, "caras": sides, "calidad": quality, "papel": paper_name, "impresora": profile},
        "paginas_impresas": printed_pages,
        "hojas": sheets,
        "tiempo_minutos": round(minutes, 2),
        "costo_total_usd": round(total_cost, 6),
        "precio_sugerido_usd": round(suggested_price, 2),
        "desglose": breakdown,
    }
    _download_report(result)
    st.warning("Resultado técnico estimado. Debe calibrarse con pruebas reales por impresora, papel, calidad, perfil ICC y mantenimiento.")
