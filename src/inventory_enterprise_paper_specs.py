"""Ajustes de unidades de inventario y gramaje para papel y cartulina."""
from __future__ import annotations

import streamlit as st

from src import inventory_enterprise_enhancements as enhancements


INVENTORY_UNITS = (
    "unidad",
    "hoja",
    "pliego",
    "resma",
    "rollo",
    "bobina",
    "paquete",
    "caja",
    "sobre",
    "bolsa",
    "kit",
    "frasco",
    "botella",
    "bidón",
    "tubo",
    "pallet",
)


def _grammage_text(row: dict) -> str:
    """Devuelve el gramaje sin confundirlo con el peso de la unidad."""
    if row.get("category") != "Papel y cartulina":
        return ""
    if row.get("grammage_known") and float(row.get("grammage_gsm") or 0) > 0:
        return f"Gramaje {float(row['grammage_gsm']):,.0f} g/m²"
    return "Gramaje no indicado"


def activate_inventory_enterprise_paper_specs(module) -> None:
    """Añade gramaje opcional y limita las unidades a formas de inventario."""
    module.UNITS = INVENTORY_UNITS

    original_area_measurements = enhancements._area_measurements
    original_dimension_text = enhancements._dimension_text

    def area_measurements_with_grammage(prefix: str) -> dict:
        data = original_area_measurements(prefix)
        if st.session_state.get("reg_category") != "Papel y cartulina":
            return data

        st.markdown("##### Gramaje del papel o cartulina")
        grammage_option = st.radio(
            "¿El empaque indica el gramaje?",
            ("Sí, está indicado", "No indicado / desconocido"),
            horizontal=True,
            key=f"{prefix}_grammage_option",
            help="El gramaje se expresa en g/m². No es el peso de una hoja individual.",
        )
        if grammage_option == "Sí, está indicado":
            grammage_gsm = st.number_input(
                "Gramaje (g/m²)",
                min_value=1.0,
                value=75.0,
                step=1.0,
                format="%.0f",
                key=f"{prefix}_grammage_gsm",
                help="Ejemplos habituales: 75, 90, 120, 150, 180, 200 o 250 g/m².",
            )
            data.update({
                "grammage_gsm": float(grammage_gsm),
                "grammage_known": True,
                "grammage_status": "Indicado en el empaque",
            })
        else:
            st.info("El artículo se guardará con gramaje desconocido. Podrás identificarlo en el catálogo.")
            data.update({
                "grammage_gsm": 0.0,
                "grammage_known": False,
                "grammage_status": "No indicado / desconocido",
            })
        return data

    def dimension_text_with_grammage(row: dict) -> str:
        physical = original_dimension_text(row)
        grammage = _grammage_text(row)
        return f"{physical} · {grammage}" if grammage else physical

    enhancements._area_measurements = area_measurements_with_grammage
    enhancements._dimension_text = dimension_text_with_grammage
