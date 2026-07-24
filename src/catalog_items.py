"""Catálogo maestro de artículos con ficha técnica completa.

Catálogo define QUÉ es el artículo, incluyendo sus propiedades físicas permanentes.
Compras registra CÓMO se adquiere. Recepción confirma QUÉ llegó. Inventario
controla CUÁNTO existe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.session_utils import read_list, save_list

CATALOG_KEY = "catalog_items"
ARTICLE_TYPES = ("Material consumible", "Producto para venta", "Servicio", "Activo", "Insumo de empaque", "Repuesto", "Otro")
INVENTORY_UNITS = ("Unidad", "Hoja", "Pliego", "Resma", "Rollo", "Bobina", "Paquete", "Caja", "Sobre", "Kit", "Bolsa", "Frasco", "Botella", "Bidón", "Tubo", "Pallet")
FORBIDDEN_INVENTORY_UNITS = {"cm", "m", "cm²", "cm2", "m²", "m2", "g", "gr", "kg", "ml", "l", "lt", "litro", "litros", "mm"}
CATEGORIES = ("Papel y cartulina", "Tintas y botellas", "Cartuchos", "Tóner", "Sublimación", "Corte y Cameo", "Plastificación", "Papelería", "Empaque", "Repuestos", "Producto terminado", "Servicio", "Otro")
MEASUREMENT_TYPES = ("Pieza completa", "Área", "Peso", "Volumen")
GRAMMAGE_INDICATED = "Sí, está indicado"
GRAMMAGE_UNKNOWN = "No indicado / desconocido"
GRAMMAGE_NA = "No aplica"
CUT_TOLERANCE_CM = 0.20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class CatalogItem:
    item_id: str
    sku: str
    name: str
    article_type: str
    category: str
    inventory_unit: str
    brand: str = ""
    description: str = ""
    color: str = ""
    compatibility: str = ""
    measurement_type: str = "Pieza completa"
    grammage_status: str = GRAMMAGE_NA
    grammage_gsm: float = 0.0
    width_cm: float = 0.0
    height_cm: float = 0.0
    width_top_cm: float = 0.0
    width_bottom_cm: float = 0.0
    height_left_cm: float = 0.0
    height_right_cm: float = 0.0
    estimated_area_cm2: float = 0.0
    usable_area_cm2_value: float = 0.0
    area_m2: float = 0.0
    width_difference_cm: float = 0.0
    height_difference_cm: float = 0.0
    maximum_difference_cm: float = 0.0
    cut_status: str = "Sin medir"
    unit_weight_g: float = 0.0
    unit_volume_ml: float = 0.0
    minimum_stock: float = 0.0
    maximum_stock: float = 0.0
    manage_by_lot: bool = False
    manage_by_expiry: bool = False
    manage_by_serial: bool = False
    active: bool = True
    technical_notes: str = ""
    source: str = "manual"
    migrated_from_inventory_id: str = ""
    created_at_utc: str = ""
    updated_at_utc: str = ""

    @property
    def usable_area_cm2(self) -> float:
        if self.usable_area_cm2_value > 0:
            return round(self.usable_area_cm2_value, 2)
        widths = [v for v in (self.width_top_cm, self.width_bottom_cm) if v > 0] or [self.width_cm]
        heights = [v for v in (self.height_left_cm, self.height_right_cm) if v > 0] or [self.height_cm]
        return round(min(widths) * min(heights), 2)

    @property
    def usable_area_m2(self) -> float:
        return round(self.area_m2 if self.area_m2 > 0 else self.usable_area_cm2 / 10000, 6)

    @property
    def grammage_label(self) -> str:
        if self.grammage_status == GRAMMAGE_INDICATED and self.grammage_gsm > 0:
            return f"{self.grammage_gsm:g} g/m²"
        if self.grammage_status == GRAMMAGE_UNKNOWN:
            return "No indicado"
        return "—"

    @property
    def dimensions_label(self) -> str:
        sides = (self.width_top_cm, self.width_bottom_cm, self.height_left_cm, self.height_right_cm)
        if all(value > 0 for value in sides):
            return (
                f"Anchos {self.width_top_cm:g}/{self.width_bottom_cm:g} cm · "
                f"Altos {self.height_left_cm:g}/{self.height_right_cm:g} cm · "
                f"Útil {self.usable_area_cm2:g} cm² ({self.usable_area_m2:g} m²)"
            )
        if self.width_cm > 0 and self.height_cm > 0:
            return f"{self.width_cm:g} × {self.height_cm:g} cm · {self.usable_area_cm2:g} cm²"
        if self.unit_volume_ml > 0:
            return f"{self.unit_volume_ml:g} ml"
        if self.unit_weight_g > 0:
            return f"{self.unit_weight_g:g} g"
        return "—"


def _from_dict(raw: dict) -> CatalogItem:
    fields = CatalogItem.__dataclass_fields__
    data = {name: raw.get(name, field.default) for name, field in fields.items()}
    data["item_id"] = str(raw.get("item_id") or uuid4().hex[:8].upper())
    data["name"] = str(raw.get("name") or raw.get("material") or "Artículo").strip()
    data["sku"] = str(raw.get("sku") or raw.get("code") or "").strip()
    numeric_fields = (
        "grammage_gsm", "width_cm", "height_cm", "width_top_cm", "width_bottom_cm",
        "height_left_cm", "height_right_cm", "estimated_area_cm2", "usable_area_cm2_value",
        "area_m2", "width_difference_cm", "height_difference_cm", "maximum_difference_cm",
        "unit_weight_g", "unit_volume_ml", "minimum_stock", "maximum_stock",
    )
    for key in numeric_fields:
        data[key] = _num(data.get(key))
    return CatalogItem(**data)


def get_catalog_items(include_inactive: bool = True) -> list[CatalogItem]:
    items = [_from_dict(row) for row in read_list(CATALOG_KEY)]
    return items if include_inactive else [item for item in items if item.active]


def save_catalog_items(items: list[CatalogItem]) -> None:
    save_list(CATALOG_KEY, [asdict(item) for item in items])


def find_by_id(item_id: str) -> CatalogItem | None:
    return next((item for item in get_catalog_items() if item.item_id == item_id), None)


def find_by_sku(sku: str) -> CatalogItem | None:
    normalized = sku.strip().casefold()
    return next((item for item in get_catalog_items() if item.sku.strip().casefold() == normalized), None)


def add_item(item: CatalogItem) -> CatalogItem:
    items = get_catalog_items()
    if item.sku and any(row.sku.casefold() == item.sku.casefold() for row in items):
        raise ValueError("Ya existe un artículo con ese SKU.")
    items.append(item)
    save_catalog_items(items)
    return item


def _technical_values(top: float, bottom: float, left: float, right: float) -> dict:
    complete = all(value > 0 for value in (top, bottom, left, right))
    if not complete:
        return {
            "width_cm": 0.0, "height_cm": 0.0, "estimated_area_cm2": 0.0,
            "usable_area_cm2_value": 0.0, "area_m2": 0.0,
            "width_difference_cm": 0.0, "height_difference_cm": 0.0,
            "maximum_difference_cm": 0.0, "cut_status": "Sin medir",
        }
    average_width = (top + bottom) / 2
    average_height = (left + right) / 2
    estimated = average_width * average_height
    usable = min(top, bottom) * min(left, right)
    width_difference = abs(top - bottom)
    height_difference = abs(left - right)
    maximum_difference = max(width_difference, height_difference)
    return {
        "width_cm": average_width,
        "height_cm": average_height,
        "estimated_area_cm2": estimated,
        "usable_area_cm2_value": usable,
        "area_m2": usable / 10000,
        "width_difference_cm": width_difference,
        "height_difference_cm": height_difference,
        "maximum_difference_cm": maximum_difference,
        "cut_status": "Corte irregular" if maximum_difference > CUT_TOLERANCE_CM else "Corte regular",
    }


def migrate_inventory_to_catalog(dry_run: bool = True) -> dict:
    inventory = read_list("inventory_registry")
    current = get_catalog_items()
    migrated_ids = {item.migrated_from_inventory_id for item in current if item.migrated_from_inventory_id}
    skus = {item.sku.casefold() for item in current if item.sku}
    created: list[CatalogItem] = []
    skipped = 0
    for row in inventory:
        source_id = str(row.get("id") or row.get("item_id") or row.get("material_id") or "")
        sku = str(row.get("sku") or row.get("code") or "").strip()
        if (source_id and source_id in migrated_ids) or (sku and sku.casefold() in skus):
            skipped += 1
            continue
        grammage = _num(row.get("grammage_gsm") or row.get("grammage"))
        top = _num(row.get("width_top_cm"))
        bottom = _num(row.get("width_bottom_cm"))
        left = _num(row.get("height_left_cm"))
        right = _num(row.get("height_right_cm"))
        technical = _technical_values(top, bottom, left, right)
        item = CatalogItem(
            item_id=uuid4().hex[:8].upper(), sku=sku,
            name=str(row.get("name") or row.get("material") or row.get("material_name") or "Artículo"),
            article_type="Material consumible", category=str(row.get("category") or "Otro"),
            inventory_unit=str(row.get("unit") or row.get("unit_name") or "Unidad"),
            brand=str(row.get("brand") or ""),
            measurement_type={"area": "Área", "weight": "Peso", "volume": "Volumen"}.get(str(row.get("content_type")), "Pieza completa"),
            grammage_gsm=grammage,
            grammage_status=GRAMMAGE_INDICATED if grammage > 0 else (GRAMMAGE_UNKNOWN if row.get("category") == "Papel y cartulina" else GRAMMAGE_NA),
            width_cm=_num(row.get("width_cm"), technical["width_cm"]),
            height_cm=_num(row.get("height_cm"), technical["height_cm"]),
            width_top_cm=top, width_bottom_cm=bottom, height_left_cm=left, height_right_cm=right,
            estimated_area_cm2=_num(row.get("estimated_area_cm2"), technical["estimated_area_cm2"]),
            usable_area_cm2_value=_num(row.get("usable_area_cm2") or row.get("area_cm2") or row.get("content_value"), technical["usable_area_cm2_value"]),
            area_m2=_num(row.get("area_m2"), technical["area_m2"]),
            width_difference_cm=_num(row.get("width_difference_cm"), technical["width_difference_cm"]),
            height_difference_cm=_num(row.get("height_difference_cm"), technical["height_difference_cm"]),
            maximum_difference_cm=_num(row.get("maximum_difference_cm"), technical["maximum_difference_cm"]),
            cut_status=str(row.get("cut_status") or technical["cut_status"]),
            unit_weight_g=_num(row.get("unit_weight_g") or (row.get("content_value") if row.get("content_type") == "weight" else 0)),
            unit_volume_ml=_num(row.get("ml") or row.get("unit_volume_ml") or (row.get("content_value") if row.get("content_type") == "volume" else 0)),
            minimum_stock=_num(row.get("minimum_stock") or row.get("min_stock")),
            maximum_stock=_num(row.get("maximum_stock") or row.get("max_stock")),
            technical_notes=str(row.get("notes") or ""), source="migrado",
            migrated_from_inventory_id=source_id, created_at_utc=_now(), updated_at_utc=_now(),
        )
        created.append(item)
        if sku:
            skus.add(sku.casefold())
    if not dry_run and created:
        save_catalog_items([*current, *created])
    return {"created": len(created), "skipped": skipped, "created_items": created}


def render_catalog_items() -> None:
    st.title("Catálogo de artículos")
    st.caption("Aquí se conservan las propiedades permanentes del material: medidas reales de los cuatro lados, área útil, m², gramaje, peso, volumen y calidad del corte.")
    tab_list, tab_create, tab_migrate = st.tabs(["Artículos", "Crear artículo", "Migrar desde Inventario"])
    with tab_list:
        items = get_catalog_items()
        if not items:
            st.info("No hay artículos registrados.")
        else:
            st.dataframe([
                {
                    "SKU": item.sku,
                    "Artículo": item.name,
                    "Tipo": item.article_type,
                    "Categoría": item.category,
                    "Unidad": item.inventory_unit,
                    "Medidas / contenido": item.dimensions_label,
                    "Gramaje": item.grammage_label,
                    "Calidad de corte": item.cut_status,
                    "Diferencia máxima": f"{item.maximum_difference_cm:g} cm" if item.maximum_difference_cm > 0 else "—",
                    "Activo": item.active,
                }
                for item in items
            ], use_container_width=True, hide_index=True)
    with tab_create:
        with st.form("catalog_item_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre")
            sku = c2.text_input("SKU")
            c3, c4, c5 = st.columns(3)
            article_type = c3.selectbox("Tipo", ARTICLE_TYPES)
            category = c4.selectbox("Categoría", CATEGORIES)
            unit = c5.selectbox("Unidad de inventario", INVENTORY_UNITS)
            brand = st.text_input("Marca")
            measurement_type = st.selectbox("¿Cómo se mide físicamente cada unidad?", MEASUREMENT_TYPES)

            top = bottom = left = right = 0.0
            weight = volume = 0.0
            if measurement_type == "Área":
                st.markdown("##### Medidas reales de los cuatro lados")
                st.caption("Mide cada borde por separado. El sistema detecta si el material está mal cortado y usa los lados más pequeños para calcular el área utilizable.")
                a, b = st.columns(2)
                top = a.number_input("Ancho superior (cm)", min_value=0.0, step=0.01)
                bottom = b.number_input("Ancho inferior (cm)", min_value=0.0, step=0.01)
                c, d = st.columns(2)
                left = c.number_input("Alto izquierdo (cm)", min_value=0.0, step=0.01)
                right = d.number_input("Alto derecho (cm)", min_value=0.0, step=0.01)
                technical = _technical_values(top, bottom, left, right)
                if technical["usable_area_cm2_value"] > 0:
                    metrics = st.columns(4)
                    metrics[0].metric("Ancho promedio", f"{technical['width_cm']:.2f} cm")
                    metrics[1].metric("Alto promedio", f"{technical['height_cm']:.2f} cm")
                    metrics[2].metric("Área utilizable", f"{technical['usable_area_cm2_value']:.2f} cm²")
                    metrics[3].metric("Equivalente", f"{technical['area_m2']:.6f} m²")
                    if technical["cut_status"] == "Corte irregular":
                        st.warning(f"Corte irregular: diferencia máxima de {technical['maximum_difference_cm']:.2f} cm. Producción y Costeo usarán el área utilizable conservadora.")
                    else:
                        st.success("Corte regular: las diferencias están dentro de la tolerancia de 0,20 cm.")
            elif measurement_type == "Peso":
                weight = st.number_input("Peso por unidad (g)", min_value=0.0, step=0.1)
            elif measurement_type == "Volumen":
                volume = st.number_input("Volumen por unidad (ml)", min_value=0.0, step=1.0)

            grammage_status = GRAMMAGE_NA
            grammage = 0.0
            if category == "Papel y cartulina":
                st.markdown("##### Gramaje")
                grammage_status = st.radio("¿El empaque indica el gramaje?", (GRAMMAGE_INDICATED, GRAMMAGE_UNKNOWN), horizontal=True)
                if grammage_status == GRAMMAGE_INDICATED:
                    grammage = st.number_input("Gramaje (g/m²)", min_value=1.0, value=75.0, step=1.0)

            a, b = st.columns(2)
            minimum = a.number_input("Stock mínimo", min_value=0.0)
            maximum = b.number_input("Stock máximo", min_value=0.0)
            notes = st.text_area("Observaciones técnicas")
            submitted = st.form_submit_button("Crear artículo", type="primary")

        if submitted:
            technical = _technical_values(top, bottom, left, right)
            if not name.strip():
                st.error("El nombre es obligatorio.")
            elif unit.casefold() in FORBIDDEN_INVENTORY_UNITS:
                st.error("Las medidas físicas no pueden usarse como unidad de inventario.")
            elif measurement_type == "Área" and technical["usable_area_cm2_value"] <= 0:
                st.error("Debes completar los cuatro lados para un material medido por área.")
            elif maximum > 0 and minimum > maximum:
                st.error("El stock mínimo no puede ser mayor que el máximo.")
            else:
                try:
                    add_item(CatalogItem(
                        item_id=uuid4().hex[:8].upper(), sku=sku.strip(), name=name.strip(),
                        article_type=article_type, category=category, inventory_unit=unit,
                        brand=brand.strip(), measurement_type=measurement_type,
                        grammage_status=grammage_status, grammage_gsm=grammage,
                        width_top_cm=top, width_bottom_cm=bottom,
                        height_left_cm=left, height_right_cm=right,
                        unit_weight_g=weight, unit_volume_ml=volume,
                        minimum_stock=minimum, maximum_stock=maximum,
                        technical_notes=notes.strip(), created_at_utc=_now(), updated_at_utc=_now(),
                        **technical,
                    ))
                    st.success("Artículo creado con su ficha técnica completa.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    with tab_migrate:
        preview = migrate_inventory_to_catalog(dry_run=True)
        st.write(f"Se crearían **{preview['created']}** artículos y se omitirían **{preview['skipped']}**.")
        st.caption("La migración conserva medidas de los cuatro lados, área utilizable, m², gramaje, ml, peso, calidad del corte y observaciones. El inventario original no se modifica.")
        if preview["created"] and st.button("Ejecutar migración", type="primary"):
            result = migrate_inventory_to_catalog(dry_run=False)
            st.success(f"Migración completada: {result['created']} artículos creados. El inventario original no fue modificado.")
            st.rerun()
