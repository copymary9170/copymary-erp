"""Ficha técnica de impresión vinculada a activos."""
from __future__ import annotations

import base64
from datetime import date
from uuid import uuid4
import streamlit as st

from src import app_shell, assets, session_backup
from src.session_utils import read_list, save_list, now_iso


TECHNOLOGIES = (
    "Inyección con tanque",
    "Inyección con cartuchos",
    "Láser monocromática",
    "Láser color",
)

INK_COLORS = ("k_percent", "c_percent", "m_percent", "y_percent")
INK_COLOR_LABELS = {"k_percent": "Negro (K)", "c_percent": "Cian (C)", "m_percent": "Magenta (M)", "y_percent": "Amarillo (Y)"}
MAX_PHOTO_MB = 3
PHOTO_TYPES = ("Tanque", "Software")


def _activate_backup() -> None:
    for section, label in (
        ("printer_asset_specs", "Fichas técnicas de impresoras"),
        ("ink_level_readings", "Lecturas de nivel de tinta"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


def _positive(value: float, label: str, errors: list[str]) -> None:
    if value <= 0:
        errors.append(f"{label} debe ser mayor que cero.")


def build_ink_reading(
    asset_id: str, recorded_date: str, k_percent: float, c_percent: float, m_percent: float, y_percent: float,
    note: str = "", photo_bytes: bytes | None = None, photo_mime: str = "", photo_type: str = "",
) -> dict:
    """Construye un registro de lectura de nivel de tinta, con foto opcional
    codificada en base64. No persiste nada por sí sola — eso lo hace el
    llamador con `save_ink_reading`, que reemplaza la lectura anterior del
    mismo tipo en vez de acumular historial (para no 'llenarse' de fotos).

    Los porcentajes se acotan a 0-100 (una lectura inválida no debe romper
    el historial ni mostrar un dato imposible)."""
    photo_base64 = base64.b64encode(photo_bytes).decode("ascii") if photo_bytes else ""
    return {
        "reading_id": f"INK-{uuid4().hex[:8].upper()}",
        "asset_id": asset_id,
        "photo_type": photo_type if photo_base64 else "",
        "recorded_date": recorded_date,
        "created_at_utc": now_iso(),
        "k_percent": max(0.0, min(100.0, float(k_percent))),
        "c_percent": max(0.0, min(100.0, float(c_percent))),
        "m_percent": max(0.0, min(100.0, float(m_percent))),
        "y_percent": max(0.0, min(100.0, float(y_percent))),
        "note": note.strip(),
        "photo_base64": photo_base64,
        "photo_mime": photo_mime if photo_base64 else "",
    }


def save_ink_reading(entry: dict) -> None:
    """Guarda una lectura reemplazando cualquier lectura anterior del MISMO
    activo y el mismo tipo de foto ('Tanque', 'Software', o sin foto) — a
    propósito no se acumula historial ilimitado; solo se conserva la más
    reciente de cada tipo por impresora."""
    asset_id = entry["asset_id"]
    photo_type = entry.get("photo_type", "")
    readings = [
        row for row in read_list("ink_level_readings")
        if not (str(row.get("asset_id")) == str(asset_id) and row.get("photo_type", "") == photo_type)
    ]
    readings.append(entry)
    save_list("ink_level_readings", readings)


def ink_readings_for(asset_id: str) -> list[dict]:
    """Lecturas vigentes de un activo (como mucho una por tipo de foto:
    Tanque, Software, y una sin foto), de la más reciente a la más antigua."""
    readings = [row for row in read_list("ink_level_readings") if str(row.get("asset_id")) == str(asset_id)]
    return sorted(readings, key=lambda row: row.get("recorded_date", row.get("created_at_utc", "")), reverse=True)


def latest_ink_reading(asset_id: str, photo_type: str = "") -> dict | None:
    """La lectura vigente de un tipo específico ('Tanque'/'Software') para
    un activo, o None si todavía no se ha registrado ninguna de ese tipo."""
    for row in read_list("ink_level_readings"):
        if str(row.get("asset_id")) == str(asset_id) and row.get("photo_type", "") == photo_type:
            return row
    return None


def lowest_ink_color(reading: dict) -> tuple[str, float]:
    """El color con menor nivel en una lectura — para resaltar cuál urge
    reponer primero."""
    lowest = min(INK_COLORS, key=lambda color: reading.get(color, 100.0))
    return INK_COLOR_LABELS[lowest], reading.get(lowest, 100.0)


def render_printer_asset_specs() -> None:
    st.title("Ficha técnica de impresoras")
    st.caption("Registra la tecnología y los consumibles reales: botellas, cartuchos o tóner.")
    printers = [a for a in assets._get_assets() if "impres" in a.category.casefold() or "impres" in a.name.casefold()]
    if not printers:
        st.warning("Primero registra una impresora en Activos.")
        return

    options = {f"{a.name} · {a.asset_id}": a for a in printers}
    selected_label = st.selectbox("Impresora", tuple(options))
    asset = options[selected_label]

    spec_tab, ink_tab = st.tabs(("Ficha técnica", "Nivel de tinta actual"))

    with spec_tab:
        _render_spec_form(asset)

    with ink_tab:
        _render_ink_levels(asset)


def _render_spec_form(asset) -> None:
    rows = read_list("printer_asset_specs")
    current = next((r for r in reversed(rows) if str(r.get("asset_id")) == str(asset.asset_id) and r.get("active", True)), {})
    technology = st.selectbox("Tecnología de impresión", TECHNOLOGIES, index=TECHNOLOGIES.index(current.get("technology", "Inyección con tanque")) if current.get("technology") in TECHNOLOGIES else 0)
    st.info(f"Costo y vida útil se toman de Activos: ${asset.acquisition_cost:,.2f} · {asset.lifetime_units:,} páginas.")

    with st.form("printer_asset_spec_form"):
        a, b, c = st.columns(3)
        ppm = a.number_input("Velocidad real (ppm)", min_value=0.1, value=float(current.get("ppm", 8.0)))
        watts = b.number_input("Consumo imprimiendo (W)", min_value=0.1, value=float(current.get("watts", 18.0)))
        maintenance_page = c.number_input("Reserva mantenimiento/página ($)", min_value=0.0, value=float(current.get("maintenance_page", 0.003)), format="%.4f")

        head_cost = head_life = drum_cost = drum_life = fuser_cost = fuser_life = 0.0
        black_cost = black_yield = color_cost = color_yield = 0.0
        c_cost = c_yield = m_cost = m_yield = y_cost = y_yield = 0.0

        if technology == "Inyección con tanque":
            st.markdown("#### Botellas y cabezales")
            a, b = st.columns(2)
            head_cost = a.number_input("Costo cabezales ($)", min_value=0.0, value=float(current.get("head_cost", 100.0)))
            head_life = b.number_input("Vida cabezales (páginas)", min_value=1.0, value=float(current.get("head_life", 30000)))
            a, b, c, d = st.columns(4)
            c_cost = a.number_input("Botella C ($)", min_value=0.01, value=float(current.get("c_cost", current.get("ink_c", 19.0))))
            m_cost = b.number_input("Botella M ($)", min_value=0.01, value=float(current.get("m_cost", current.get("ink_m", 19.0))))
            y_cost = c.number_input("Botella Y ($)", min_value=0.01, value=float(current.get("y_cost", current.get("ink_y", 19.0))))
            black_cost = d.number_input("Botella K ($)", min_value=0.01, value=float(current.get("black_cost", current.get("ink_k", 19.0))))
            a, b = st.columns(2)
            color_yield = a.number_input("Rendimiento color al 5%", min_value=1.0, value=float(current.get("color_yield", 6000)))
            black_yield = b.number_input("Rendimiento negro al 5%", min_value=1.0, value=float(current.get("black_yield", 12000)))
            c_yield = m_yield = y_yield = color_yield

        elif technology == "Inyección con cartuchos":
            st.markdown("#### Cartuchos")
            cartridge_layout = st.radio("Configuración", ("Negro + tricolor", "Cartuchos C/M/Y separados"), horizontal=True, index=1 if current.get("cartridge_layout") == "separate" else 0)
            a, b = st.columns(2)
            black_cost = a.number_input("Cartucho negro ($)", min_value=0.01, value=float(current.get("black_cost", 22.0)))
            black_yield = b.number_input("Rendimiento cartucho negro", min_value=1.0, value=float(current.get("black_yield", 300)))
            if cartridge_layout == "Negro + tricolor":
                a, b = st.columns(2)
                color_cost = a.number_input("Cartucho tricolor ($)", min_value=0.01, value=float(current.get("color_cost", 23.0)))
                color_yield = b.number_input("Rendimiento cartucho tricolor", min_value=1.0, value=float(current.get("color_yield", 100)))
            else:
                a, b, c = st.columns(3)
                c_cost = a.number_input("Cartucho C ($)", min_value=0.01, value=float(current.get("c_cost", 15.0)))
                m_cost = b.number_input("Cartucho M ($)", min_value=0.01, value=float(current.get("m_cost", 15.0)))
                y_cost = c.number_input("Cartucho Y ($)", min_value=0.01, value=float(current.get("y_cost", 15.0)))
                a, b, c = st.columns(3)
                c_yield = a.number_input("Rendimiento C", min_value=1.0, value=float(current.get("c_yield", 300)))
                m_yield = b.number_input("Rendimiento M", min_value=1.0, value=float(current.get("m_yield", 300)))
                y_yield = c.number_input("Rendimiento Y", min_value=1.0, value=float(current.get("y_yield", 300)))

        else:
            st.markdown("#### Tóner y componentes láser")
            a, b = st.columns(2)
            black_cost = a.number_input("Tóner negro ($)", min_value=0.01, value=float(current.get("black_cost", 45.0)))
            black_yield = b.number_input("Rendimiento tóner negro", min_value=1.0, value=float(current.get("black_yield", 1500)))
            if technology == "Láser color":
                a, b, c = st.columns(3)
                c_cost = a.number_input("Tóner C ($)", min_value=0.01, value=float(current.get("c_cost", 55.0)))
                m_cost = b.number_input("Tóner M ($)", min_value=0.01, value=float(current.get("m_cost", 55.0)))
                y_cost = c.number_input("Tóner Y ($)", min_value=0.01, value=float(current.get("y_cost", 55.0)))
                a, b, c = st.columns(3)
                c_yield = a.number_input("Rendimiento C", min_value=1.0, value=float(current.get("c_yield", 1300)))
                m_yield = b.number_input("Rendimiento M", min_value=1.0, value=float(current.get("m_yield", 1300)))
                y_yield = c.number_input("Rendimiento Y", min_value=1.0, value=float(current.get("y_yield", 1300)))
            a, b, c, d = st.columns(4)
            drum_cost = a.number_input("Costo tambor ($)", min_value=0.0, value=float(current.get("drum_cost", 80.0)))
            drum_life = b.number_input("Vida tambor (páginas)", min_value=1.0, value=float(current.get("drum_life", 12000)))
            fuser_cost = c.number_input("Costo fusor ($)", min_value=0.0, value=float(current.get("fuser_cost", 120.0)))
            fuser_life = d.number_input("Vida fusor (páginas)", min_value=1.0, value=float(current.get("fuser_life", 50000)))

        submitted = st.form_submit_button("Guardar ficha técnica", type="primary", use_container_width=True)

    if submitted:
        errors: list[str] = []
        _positive(ppm, "Velocidad", errors)
        _positive(watts, "Consumo eléctrico", errors)
        _positive(black_cost, "Consumible negro", errors)
        _positive(black_yield, "Rendimiento negro", errors)
        if technology == "Inyección con tanque":
            for value, label in ((c_cost, "Botella C"), (m_cost, "Botella M"), (y_cost, "Botella Y"), (color_yield, "Rendimiento color")):
                _positive(value, label, errors)
        elif technology == "Inyección con cartuchos" and cartridge_layout == "Negro + tricolor":
            _positive(color_cost, "Cartucho tricolor", errors)
            _positive(color_yield, "Rendimiento tricolor", errors)
        elif technology in {"Inyección con cartuchos", "Láser color"}:
            for value, label in ((c_cost, "Consumible C"), (m_cost, "Consumible M"), (y_cost, "Consumible Y"), (c_yield, "Rendimiento C"), (m_yield, "Rendimiento M"), (y_yield, "Rendimiento Y")):
                _positive(value, label, errors)
        if errors:
            for error in errors:
                st.error(error)
            return

        for row in rows:
            if str(row.get("asset_id")) == str(asset.asset_id):
                row["active"] = False
        rows.append({
            "spec_id": f"PRS-{uuid4().hex[:8].upper()}", "asset_id": asset.asset_id,
            "technology": technology,
            "cartridge_layout": "separate" if technology == "Inyección con cartuchos" and cartridge_layout == "Cartuchos C/M/Y separados" else "tricolor",
            "head_cost": head_cost, "head_life": int(head_life or 1),
            "drum_cost": drum_cost, "drum_life": int(drum_life or 1),
            "fuser_cost": fuser_cost, "fuser_life": int(fuser_life or 1),
            "black_cost": black_cost, "black_yield": int(black_yield),
            "color_cost": color_cost, "color_yield": int(color_yield or 1),
            "c_cost": c_cost, "c_yield": int(c_yield or 1),
            "m_cost": m_cost, "m_yield": int(m_yield or 1),
            "y_cost": y_cost, "y_yield": int(y_yield or 1),
            "ppm": ppm, "watts": watts, "maintenance_page": maintenance_page,
            "active": True, "created_at_utc": now_iso(),
        })
        save_list("printer_asset_specs", rows)
        st.success("Ficha técnica guardada para el tipo de consumible seleccionado.")
        st.rerun()


def _render_ink_levels(asset) -> None:
    st.caption(
        "Guarda solo la ÚLTIMA foto del tanque/panel y la ÚLTIMA captura del software — cada vez que subas una "
        "nueva, reemplaza a la anterior del mismo tipo. No se acumula historial de fotos para no llenar el respaldo."
    )

    with st.form(f"ink_level_form_{asset.asset_id}", clear_on_submit=True):
        date_col, type_col = st.columns([1, 1])
        recorded_date = date_col.date_input("Fecha de la lectura", value=date.today())
        photo_type = type_col.radio("¿Qué estás registrando?", PHOTO_TYPES, horizontal=True, key=f"ink_type_{asset.asset_id}")
        level_columns = st.columns(4)
        k_percent = level_columns[0].number_input("Negro (K) %", min_value=0.0, max_value=100.0, value=100.0, step=5.0)
        c_percent = level_columns[1].number_input("Cian (C) %", min_value=0.0, max_value=100.0, value=100.0, step=5.0)
        m_percent = level_columns[2].number_input("Magenta (M) %", min_value=0.0, max_value=100.0, value=100.0, step=5.0)
        y_percent = level_columns[3].number_input("Amarillo (Y) %", min_value=0.0, max_value=100.0, value=100.0, step=5.0)
        note = st.text_input("Nota (opcional)", placeholder="Ej. amarillo con sedimento, cambiar pronto")
        photo = st.file_uploader(
            f"Foto ({photo_type.lower() if photo_type else 'opcional'}, máx. {MAX_PHOTO_MB} MB) — reemplaza a la anterior de este tipo",
            type=("png", "jpg", "jpeg"), key=f"ink_photo_{asset.asset_id}",
        )
        submitted = st.form_submit_button("Guardar (reemplaza la anterior de este tipo)", type="primary", use_container_width=True)

    if submitted:
        photo_bytes = None
        photo_mime = ""
        if photo is not None:
            if photo.size > MAX_PHOTO_MB * 1024 * 1024:
                st.error(f"La foto pesa más de {MAX_PHOTO_MB} MB; usa una más liviana.")
                return
            photo_bytes = photo.getvalue()
            photo_mime = photo.type or "image/jpeg"
        entry = build_ink_reading(
            asset.asset_id, recorded_date.isoformat(), k_percent, c_percent, m_percent, y_percent,
            note=note, photo_bytes=photo_bytes, photo_mime=photo_mime, photo_type=photo_type if photo_bytes else "",
        )
        save_ink_reading(entry)
        st.success("Lectura guardada — reemplazó a la anterior de este tipo, si había una.")
        st.rerun()

    tank_reading = latest_ink_reading(asset.asset_id, "Tanque")
    software_reading = latest_ink_reading(asset.asset_id, "Software")
    if not tank_reading and not software_reading:
        st.info("Todavía no hay foto guardada (ni de tanque ni de software) para esta impresora.")
        return

    st.markdown("#### Última foto de cada tipo")
    slot_columns = st.columns(2)
    for column, label, reading in zip(slot_columns, PHOTO_TYPES, (tank_reading, software_reading)):
        with column:
            st.markdown(f"**{label}**")
            if reading is None:
                st.caption("Sin foto registrada todavía.")
                continue
            st.caption(f"{reading.get('recorded_date', '')} · K {reading.get('k_percent', 0):.0f}% · C {reading.get('c_percent', 0):.0f}% · M {reading.get('m_percent', 0):.0f}% · Y {reading.get('y_percent', 0):.0f}%")
            if reading.get("note"):
                st.caption(reading["note"])
            if reading.get("photo_base64"):
                st.image(base64.b64decode(reading["photo_base64"]), use_container_width=True)

    most_recent = max((r for r in (tank_reading, software_reading) if r), key=lambda r: r.get("recorded_date", ""), default=None)
    if most_recent:
        lowest_label, lowest_value = lowest_ink_color(most_recent)
        if lowest_value <= 15:
            st.warning(f"{lowest_label} está en {lowest_value:.0f}% (según la lectura más reciente) — considera reponerlo pronto.")


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
        top_navigation_app.DESCRIPTIONS[name] = "Botellas, cartuchos, tóner, componentes, rendimiento, velocidad y energía."
    except (ImportError, KeyError):
        pass
