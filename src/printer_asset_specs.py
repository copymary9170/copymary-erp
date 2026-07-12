"""Ficha técnica de impresión vinculada a activos."""
from __future__ import annotations

from uuid import uuid4
import streamlit as st

from src import app_shell, assets, session_backup
from src.session_utils import read_list, save_list, now_iso


def _activate_backup() -> None:
    section = "printer_asset_specs"
    if section not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
        session_backup.SECTION_LABELS[section] = "Fichas técnicas de impresoras"
        session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


def render_printer_asset_specs() -> None:
    st.title("Ficha técnica de impresoras")
    st.caption("Completa una sola vez los datos obligatorios que reutilizarán costeo, mantenimiento y producción.")
    printers = [a for a in assets._get_assets() if "impres" in a.category.casefold() or "impres" in a.name.casefold()]
    if not printers:
        st.warning("Primero registra una impresora en Activos.")
        return
    rows = read_list("printer_asset_specs")
    options = {f"{a.name} · {a.asset_id}": a for a in printers}
    selected_label = st.selectbox("Impresora", tuple(options))
    asset = options[selected_label]
    current = next((r for r in reversed(rows) if str(r.get("asset_id")) == str(asset.asset_id) and r.get("active", True)), {})
    st.info(f"Costo y vida útil se toman obligatoriamente de Activos: ${asset.acquisition_cost:,.2f} · {asset.lifetime_units:,} páginas.")
    with st.form("printer_asset_spec_form"):
        a, b, c, d = st.columns(4)
        head_cost = a.number_input("Costo cabezales ($)", min_value=0.01, value=float(current.get("head_cost", 100.0)))
        head_life = b.number_input("Vida cabezales (páginas)", min_value=1, value=int(current.get("head_life", 30000)))
        color_yield = c.number_input("Rendimiento color al 5%", min_value=1, value=int(current.get("color_yield", 6000)))
        black_yield = d.number_input("Rendimiento negro al 5%", min_value=1, value=int(current.get("black_yield", 12000)))
        a, b, c, d = st.columns(4)
        ink_c = a.number_input("Botella C ($)", min_value=0.01, value=float(current.get("ink_c", 19.0)))
        ink_m = b.number_input("Botella M ($)", min_value=0.01, value=float(current.get("ink_m", 19.0)))
        ink_y = c.number_input("Botella Y ($)", min_value=0.01, value=float(current.get("ink_y", 19.0)))
        ink_k = d.number_input("Botella K ($)", min_value=0.01, value=float(current.get("ink_k", 19.0)))
        a, b, c = st.columns(3)
        ppm = a.number_input("Velocidad real (ppm)", min_value=0.1, value=float(current.get("ppm", 8.0)))
        watts = b.number_input("Consumo imprimiendo (W)", min_value=0.1, value=float(current.get("watts", 18.0)))
        maintenance_page = c.number_input("Reserva mantenimiento/página ($)", min_value=0.0, value=float(current.get("maintenance_page", 0.003)), format="%.4f")
        submitted = st.form_submit_button("Guardar ficha técnica", type="primary", use_container_width=True)
    if submitted:
        for row in rows:
            if str(row.get("asset_id")) == str(asset.asset_id):
                row["active"] = False
        rows.append({
            "spec_id": f"PRS-{uuid4().hex[:8].upper()}", "asset_id": asset.asset_id, "head_cost": head_cost,
            "head_life": int(head_life), "color_yield": int(color_yield), "black_yield": int(black_yield),
            "ink_c": ink_c, "ink_m": ink_m, "ink_y": ink_y, "ink_k": ink_k, "ppm": ppm, "watts": watts,
            "maintenance_page": maintenance_page, "active": True, "created_at_utc": now_iso(),
        })
        save_list("printer_asset_specs", rows)
        st.success("Ficha técnica guardada, respaldable y disponible para el costeo automático.")
        st.rerun()


def activate_printer_asset_specs() -> None:
    _activate_backup()
    name = "Ficha técnica de impresoras"
    app_shell.FUNCTIONAL_MODULES[name] = render_printer_asset_specs
    pages = list(app_shell.NAVIGATION_GROUPS.get("Administración", ()))
    if name not in pages:
        insert_at = pages.index("Activos") + 1 if "Activos" in pages else len(pages)
        pages.insert(insert_at, name)
        app_shell.NAVIGATION_GROUPS["Administración"] = tuple(pages)
    try:
        from src import top_navigation_app
        icon, eyebrow, description, area_pages = top_navigation_app.SPECIALTY_AREAS["Activos y mantenimiento"]
        if name not in area_pages:
            top_navigation_app.SPECIALTY_AREAS["Activos y mantenimiento"] = (icon, eyebrow, description, (*area_pages, name))
        top_navigation_app.DESCRIPTIONS[name] = "Datos obligatorios de tintas, cabezales, rendimiento, velocidad y energía."
    except (ImportError, KeyError):
        pass
