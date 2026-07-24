"""Catálogo maestro de artículos.

Catálogo define QUÉ es el artículo. Compras registra CÓMO se adquiere.
Recepción confirma QUÉ llegó. Inventario controla CUÁNTO existe.
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
GRAMMAGE_INDICATED = "Sí, está indicado"
GRAMMAGE_UNKNOWN = "No indicado / desconocido"
GRAMMAGE_NA = "No aplica"


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
    grammage_status: str = GRAMMAGE_NA
    grammage_gsm: float = 0.0
    width_cm: float = 0.0
    height_cm: float = 0.0
    width_top_cm: float = 0.0
    width_bottom_cm: float = 0.0
    height_left_cm: float = 0.0
    height_right_cm: float = 0.0
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
        widths = [v for v in (self.width_top_cm, self.width_bottom_cm) if v > 0] or [self.width_cm]
        heights = [v for v in (self.height_left_cm, self.height_right_cm) if v > 0] or [self.height_cm]
        return round(min(widths) * min(heights), 2)

    @property
    def usable_area_m2(self) -> float:
        return round(self.usable_area_cm2 / 10000, 6)

    @property
    def grammage_label(self) -> str:
        if self.grammage_status == GRAMMAGE_INDICATED and self.grammage_gsm > 0:
            return f"{self.grammage_gsm:g} g/m²"
        if self.grammage_status == GRAMMAGE_UNKNOWN:
            return "No indicado"
        return "—"


def _from_dict(raw: dict) -> CatalogItem:
    fields = CatalogItem.__dataclass_fields__
    data = {name: raw.get(name, field.default) for name, field in fields.items()}
    data["item_id"] = str(raw.get("item_id") or uuid4().hex[:8].upper())
    data["name"] = str(raw.get("name") or raw.get("material") or "Artículo").strip()
    data["sku"] = str(raw.get("sku") or raw.get("code") or "").strip()
    for key in ("grammage_gsm", "width_cm", "height_cm", "width_top_cm", "width_bottom_cm", "height_left_cm", "height_right_cm", "unit_weight_g", "unit_volume_ml", "minimum_stock", "maximum_stock"):
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
        item = CatalogItem(
            item_id=uuid4().hex[:8].upper(), sku=sku,
            name=str(row.get("name") or row.get("material") or row.get("material_name") or "Artículo"),
            article_type="Material consumible", category=str(row.get("category") or "Otro"),
            inventory_unit=str(row.get("unit") or row.get("unit_name") or "Unidad"),
            brand=str(row.get("brand") or ""), grammage_gsm=_num(row.get("grammage_gsm") or row.get("grammage")),
            grammage_status=GRAMMAGE_INDICATED if _num(row.get("grammage_gsm") or row.get("grammage")) > 0 else GRAMMAGE_NA,
            width_cm=_num(row.get("width_cm") or row.get("cm")), height_cm=_num(row.get("height_cm")),
            unit_volume_ml=_num(row.get("ml")), minimum_stock=_num(row.get("minimum_stock") or row.get("min_stock")),
            maximum_stock=_num(row.get("maximum_stock") or row.get("max_stock")), source="migrado",
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
    st.caption("Define qué es cada artículo. Los proveedores, precios y existencias se gestionan en Compras, Recepción e Inventario.")
    tab_list, tab_create, tab_migrate = st.tabs(["Artículos", "Crear artículo", "Migrar desde Inventario"])
    with tab_list:
        items = get_catalog_items()
        if not items:
            st.info("No hay artículos registrados.")
        else:
            st.dataframe([{"SKU": i.sku, "Artículo": i.name, "Tipo": i.article_type, "Categoría": i.category, "Unidad": i.inventory_unit, "Gramaje": i.grammage_label, "Activo": i.active} for i in items], use_container_width=True, hide_index=True)
    with tab_create:
        with st.form("catalog_item_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre")
            sku = c2.text_input("SKU")
            c3, c4, c5 = st.columns(3)
            article_type = c3.selectbox("Tipo", ARTICLE_TYPES)
            category = c4.selectbox("Categoría", CATEGORIES)
            unit = c5.selectbox("Unidad de inventario", INVENTORY_UNITS)
            c6, c7, c8 = st.columns(3)
            width = c6.number_input("Ancho (cm)", min_value=0.0)
            height = c7.number_input("Alto (cm)", min_value=0.0)
            grammage = c8.number_input("Gramaje (g/m²)", min_value=0.0)
            submitted = st.form_submit_button("Crear artículo", type="primary")
        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            elif unit.casefold() in FORBIDDEN_INVENTORY_UNITS:
                st.error("Las medidas físicas no pueden usarse como unidad de inventario.")
            else:
                try:
                    add_item(CatalogItem(item_id=uuid4().hex[:8].upper(), sku=sku.strip(), name=name.strip(), article_type=article_type, category=category, inventory_unit=unit, width_cm=width, height_cm=height, grammage_status=GRAMMAGE_INDICATED if grammage else GRAMMAGE_NA, grammage_gsm=grammage, created_at_utc=_now(), updated_at_utc=_now()))
                    st.success("Artículo creado.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    with tab_migrate:
        preview = migrate_inventory_to_catalog(dry_run=True)
        st.write(f"Se crearían **{preview['created']}** artículos y se omitirían **{preview['skipped']}**.")
        if preview["created"] and st.button("Ejecutar migración", type="primary"):
            result = migrate_inventory_to_catalog(dry_run=False)
            st.success(f"Migración completada: {result['created']} artículos creados. El inventario original no fue modificado.")
            st.rerun()
