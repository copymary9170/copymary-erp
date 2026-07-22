"""Inventario temporal de materiales para CopyMary ERP."""

import csv
from dataclasses import asdict, dataclass, replace
from io import StringIO
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money

BASE_CSV_HEADERS = [
    "ID", "Nombre", "Categoría", "Costo total de compra", "Cantidad comprada",
    "Existencia disponible", "Unidad", "Existencia mínima",
]
LEGACY_DIMENSION_CSV_HEADERS = ["Mililitros (ml)", "Longitud (cm)", "Área (m²)"]
DIMENSION_CSV_HEADERS = [
    "Mililitros (ml)", "Largo (cm)", "Ancho (cm)", "Área (cm²)", "Área (m²)",
]
LEGACY_CSV_HEADERS = [*BASE_CSV_HEADERS, *LEGACY_DIMENSION_CSV_HEADERS]
CSV_HEADERS = [*BASE_CSV_HEADERS, *DIMENSION_CSV_HEADERS]


@dataclass(frozen=True)
class InventoryItem:
    item_id: str
    name: str
    category: str
    purchase_cost: float
    purchased_quantity: float
    available_quantity: float
    unit_name: str
    minimum_stock: float
    milliliters: float = 0.0
    length_cm: float = 0.0
    width_cm: float = 0.0
    area_cm2: float = 0.0
    square_meters: float = 0.0

    @property
    def unit_cost(self) -> float:
        return self.purchase_cost / self.purchased_quantity

    @property
    def stock_value(self) -> float:
        return self.available_quantity * self.unit_cost

    @property
    def is_low_stock(self) -> bool:
        return self.available_quantity <= self.minimum_stock

    @property
    def dimensions_summary(self) -> str:
        parts = []
        if self.milliliters > 0:
            parts.append(f"{self.milliliters:,.2f} ml")
        if self.length_cm > 0 and self.width_cm > 0:
            parts.append(f"{self.length_cm:,.2f} × {self.width_cm:,.2f} cm")
        if self.area_cm2 > 0:
            parts.append(f"{self.area_cm2:,.2f} cm²")
        if self.square_meters > 0:
            parts.append(f"{self.square_meters:,.6f} m²")
        return " · ".join(parts) if parts else "Sin dimensiones registradas"


def _calculate_area(length_cm: float, width_cm: float) -> tuple[float, float]:
    """Calcula el área en cm² y m² desde largo y ancho en centímetros."""
    if length_cm <= 0 or width_cm <= 0:
        return 0.0, 0.0
    area_cm2 = length_cm * width_cm
    return area_cm2, area_cm2 / 10_000


def _item_from_dict(raw_item: dict) -> InventoryItem:
    """Adapta respaldos antiguos que todavía no contienen largo y ancho."""
    compatible = dict(raw_item)
    legacy_centimeters = float(compatible.pop("centimeters", 0.0) or 0.0)
    compatible.setdefault("length_cm", legacy_centimeters)
    compatible.setdefault("width_cm", 0.0)
    compatible.setdefault("milliliters", 0.0)
    area_cm2 = float(compatible.get("area_cm2", 0.0) or 0.0)
    square_meters = float(compatible.get("square_meters", 0.0) or 0.0)
    if area_cm2 <= 0 and square_meters > 0:
        area_cm2 = square_meters * 10_000
    if square_meters <= 0 and area_cm2 > 0:
        square_meters = area_cm2 / 10_000
    compatible["area_cm2"] = area_cm2
    compatible["square_meters"] = square_meters
    return InventoryItem(**compatible)


def _get_items() -> list[InventoryItem]:
    raw_items = st.session_state.get("inventory_registry", [])
    items: list[InventoryItem] = []
    for raw_item in raw_items:
        if isinstance(raw_item, InventoryItem):
            items.append(raw_item)
        elif isinstance(raw_item, dict):
            items.append(_item_from_dict(raw_item))
    return items


def _save_items(items: list[InventoryItem]) -> None:
    st.session_state.inventory_registry = [asdict(item) for item in items]


def _adjust_stock(items: list[InventoryItem], item_id: str, movement: str, quantity: float) -> list[InventoryItem]:
    updated_items: list[InventoryItem] = []
    for item in items:
        if item.item_id != item_id:
            updated_items.append(item)
            continue
        new_quantity = item.available_quantity + quantity if movement == "Entrada" else max(item.available_quantity - quantity, 0.0)
        updated_items.append(replace(item, available_quantity=new_quantity))
    return updated_items


def _build_inventory_csv(items: list[InventoryItem]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(CSV_HEADERS)
    for item in items:
        writer.writerow([
            item.item_id, item.name, item.category, f"{item.purchase_cost:.4f}",
            f"{item.purchased_quantity:.4f}", f"{item.available_quantity:.4f}",
            item.unit_name, f"{item.minimum_stock:.4f}", f"{item.milliliters:.4f}",
            f"{item.length_cm:.4f}", f"{item.width_cm:.4f}", f"{item.area_cm2:.4f}",
            f"{item.square_meters:.8f}",
        ])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _parse_number(value: str, field_name: str, row_number: int, allow_zero: bool = True) -> float:
    cleaned_value = value.strip().replace(",", ".")
    try:
        number = float(cleaned_value)
    except ValueError as exc:
        raise ValueError(f"Fila {row_number}: el campo '{field_name}' debe contener un número válido.") from exc
    if number < 0 or (not allow_zero and number == 0):
        condition = "mayor que cero" if not allow_zero else "igual o mayor que cero"
        raise ValueError(f"Fila {row_number}: el campo '{field_name}' debe ser {condition}.")
    return number


def _parse_inventory_csv(file_bytes: bytes) -> list[InventoryItem]:
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("El archivo debe estar guardado con codificación UTF-8.") from exc
    reader = csv.DictReader(StringIO(decoded), delimiter=";")
    if reader.fieldnames not in (BASE_CSV_HEADERS, LEGACY_CSV_HEADERS, CSV_HEADERS):
        raise ValueError("El archivo no tiene las columnas esperadas. Usa un CSV exportado desde el módulo Inventario.")

    imported_items: list[InventoryItem] = []
    for row_number, row in enumerate(reader, start=2):
        name = (row.get("Nombre") or "").strip()
        category = (row.get("Categoría") or "").strip()
        unit_name = (row.get("Unidad") or "").strip()
        if not name:
            raise ValueError(f"Fila {row_number}: falta el nombre del material.")
        if not category:
            raise ValueError(f"Fila {row_number}: falta la categoría.")
        if not unit_name:
            raise ValueError(f"Fila {row_number}: falta la unidad de control.")

        length_cm = _parse_number(row.get("Largo (cm)") or row.get("Longitud (cm)") or "0", "Largo (cm)", row_number)
        width_cm = _parse_number(row.get("Ancho (cm)") or "0", "Ancho (cm)", row_number)
        calculated_cm2, calculated_m2 = _calculate_area(length_cm, width_cm)
        imported_area_cm2 = _parse_number(row.get("Área (cm²)") or "0", "Área (cm²)", row_number)
        imported_m2 = _parse_number(row.get("Área (m²)") or "0", "Área (m²)", row_number)
        area_cm2 = calculated_cm2 or imported_area_cm2 or imported_m2 * 10_000
        square_meters = calculated_m2 or imported_m2 or area_cm2 / 10_000

        imported_items.append(InventoryItem(
            item_id=(row.get("ID") or "").strip() or uuid4().hex[:8],
            name=name,
            category=category,
            purchase_cost=_parse_number(row.get("Costo total de compra") or "0", "Costo total de compra", row_number, False),
            purchased_quantity=_parse_number(row.get("Cantidad comprada") or "0", "Cantidad comprada", row_number, False),
            available_quantity=_parse_number(row.get("Existencia disponible") or "0", "Existencia disponible", row_number),
            unit_name=unit_name,
            minimum_stock=_parse_number(row.get("Existencia mínima") or "0", "Existencia mínima", row_number),
            milliliters=_parse_number(row.get("Mililitros (ml)") or "0", "Mililitros (ml)", row_number),
            length_cm=length_cm,
            width_cm=width_cm,
            area_cm2=area_cm2,
            square_meters=square_meters,
        ))
    if not imported_items:
        raise ValueError("El archivo no contiene materiales para importar.")
    return imported_items


def _merge_items(current_items: list[InventoryItem], imported_items: list[InventoryItem]) -> list[InventoryItem]:
    merged_by_id = {item.item_id: item for item in current_items}
    for item in imported_items:
        merged_by_id[item.item_id] = item
    return list(merged_by_id.values())


def render_inventory() -> None:
    with st.container(border=True):
        render_page_header("Inventario", "Registra materiales, calcula áreas, controla existencias y respalda la lista en CSV.")
        st.caption("Los registros se conservan únicamente mientras la sesión permanezca abierta.")
    st.warning("Este inventario todavía no usa base de datos. Exporta el CSV antes de cerrar y vuelve a importarlo al comenzar otra sesión.")
    items = _get_items()

    st.subheader("Respaldar o recuperar inventario")
    backup_columns = st.columns(2)
    with backup_columns[0]:
        uploaded_file = st.file_uploader("Importar inventario desde CSV", type=("csv",), accept_multiple_files=False)
        import_mode = st.radio("Cómo aplicar la importación", ("Reemplazar inventario actual", "Combinar por ID"), horizontal=True, help="Combinar conserva los materiales actuales y reemplaza solo los que tengan el mismo ID.")
        if uploaded_file is not None and st.button("Importar inventario", type="primary", use_container_width=True):
            try:
                imported_items = _parse_inventory_csv(uploaded_file.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                _save_items(_merge_items(items, imported_items) if import_mode == "Combinar por ID" else imported_items)
                st.success(f"Se importaron {len(imported_items)} material(es) correctamente.")
                st.rerun()

    with backup_columns[1]:
        if items:
            st.download_button("Descargar inventario en CSV", data=_build_inventory_csv(items), file_name="copymary_inventario.csv", mime="text/csv", type="primary", use_container_width=True)
            render_info_card("Contenido del respaldo", "Incluye identificación, costos, existencias, ml, largo, ancho, cm² y m².", "CSV PARA EXCEL")
        else:
            st.info("Registra o importa materiales para habilitar la descarga del inventario.")

    st.divider()
    st.subheader("Registrar material")
    with st.form("inventory_item_form", clear_on_submit=True):
        first_row = st.columns(3)
        with first_row[0]:
            name = st.text_input("Nombre del material", max_chars=100)
        with first_row[1]:
            category = st.selectbox("Categoría", ("Papel", "Tinta", "Adhesivo", "Sublimación", "Papelería", "Empaque", "Otro"))
        with first_row[2]:
            unit_name = st.text_input("Unidad de control", value="unidad", max_chars=30, help="Ejemplos: hoja, unidad, ml, metro o pliego.")

        second_row = st.columns(3)
        with second_row[0]:
            purchase_cost = st.number_input("Costo total de compra", min_value=0.0, value=0.0, step=1.0)
        with second_row[1]:
            purchased_quantity = st.number_input("Cantidad comprada", min_value=0.01, value=1.0, step=1.0)
        with second_row[2]:
            minimum_stock = st.number_input("Existencia mínima", min_value=0.0, value=0.0, step=1.0)

        st.caption("Dimensiones opcionales del material")
        dimension_row = st.columns(3)
        with dimension_row[0]:
            milliliters = st.number_input("Mililitros (ml)", min_value=0.0, value=0.0, step=1.0)
        with dimension_row[1]:
            length_cm = st.number_input("Largo (cm)", min_value=0.0, value=0.0, step=0.1, help="Ejemplo: una hoja carta mide aproximadamente 27,94 cm de largo.")
        with dimension_row[2]:
            width_cm = st.number_input("Ancho (cm)", min_value=0.0, value=0.0, step=0.1, help="Ejemplo: una hoja carta mide aproximadamente 21,59 cm de ancho.")

        area_cm2, square_meters = _calculate_area(float(length_cm), float(width_cm))
        if length_cm > 0 and width_cm > 0:
            result_columns = st.columns(2)
            result_columns[0].metric("Área calculada", f"{area_cm2:,.2f} cm²")
            result_columns[1].metric("Equivalente", f"{square_meters:,.6f} m²")
            st.caption("Cálculo automático: largo × ancho. 10.000 cm² equivalen a 1 m².")
        elif length_cm > 0 or width_cm > 0:
            st.info("Completa el largo y el ancho para calcular automáticamente los cm².")

        submitted = st.form_submit_button("Registrar material", type="primary", use_container_width=True)

    if submitted:
        cleaned_name = name.strip()
        cleaned_unit = unit_name.strip()
        if not cleaned_name:
            st.error("El nombre del material no puede quedar vacío.")
        elif not cleaned_unit:
            st.error("La unidad de control no puede quedar vacía.")
        elif purchase_cost <= 0:
            st.error("El costo total de compra debe ser mayor que cero.")
        elif (length_cm > 0) != (width_cm > 0):
            st.error("Para calcular el área debes completar tanto el largo como el ancho.")
        else:
            items.append(InventoryItem(
                item_id=uuid4().hex[:8], name=cleaned_name, category=category,
                purchase_cost=float(purchase_cost), purchased_quantity=float(purchased_quantity),
                available_quantity=float(purchased_quantity), unit_name=cleaned_unit,
                minimum_stock=float(minimum_stock), milliliters=float(milliliters),
                length_cm=float(length_cm), width_cm=float(width_cm), area_cm2=float(area_cm2),
                square_meters=float(square_meters),
            ))
            _save_items(items)
            st.success("Material registrado durante esta sesión.")
            st.rerun()

    st.divider()
    st.subheader("Resumen de inventario")
    items = _get_items()
    total_value = sum(item.stock_value for item in items)
    low_stock_count = sum(1 for item in items if item.is_low_stock)
    total_area_cm2 = sum(item.area_cm2 for item in items)
    total_area_m2 = sum(item.square_meters for item in items)
    summary_columns = st.columns(5)
    summary_columns[0].metric("Materiales registrados", str(len(items)))
    summary_columns[1].metric("Valor disponible", format_money(total_value))
    summary_columns[2].metric("Existencias bajas", str(low_stock_count))
    summary_columns[3].metric("Área registrada", f"{total_area_cm2:,.2f} cm²")
    summary_columns[4].metric("Equivalente total", f"{total_area_m2:,.6f} m²")

    if not items:
        st.info("Todavía no hay materiales registrados en esta sesión.")
        return

    st.subheader("Materiales disponibles")
    for item in items:
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {item.name}")
                st.caption(f"{item.category} · ID {item.item_id} · {item.dimensions_summary}")
            with title_columns[1]:
                if st.button("Eliminar", key=f"delete_item_{item.item_id}", use_container_width=True):
                    _save_items([current for current in items if current.item_id != item.item_id])
                    st.rerun()

            metric_columns = st.columns(4)
            metric_columns[0].metric("Costo unitario", format_money(item.unit_cost))
            metric_columns[1].metric("Existencia", f"{item.available_quantity:,.2f} {item.unit_name}")
            metric_columns[2].metric("Valor disponible", format_money(item.stock_value))
            metric_columns[3].metric("Estado", "BAJO" if item.is_low_stock else "DISPONIBLE")

            if item.is_low_stock:
                st.warning(f"La existencia alcanzó el mínimo definido de {item.minimum_stock:,.2f} {item.unit_name}.")

            with st.form(f"stock_movement_form_{item.item_id}", clear_on_submit=True):
                movement_columns = st.columns(3)
                with movement_columns[0]:
                    movement = st.selectbox("Movimiento", ("Entrada", "Salida"), key=f"movement_{item.item_id}")
                with movement_columns[1]:
                    movement_quantity = st.number_input(f"Cantidad en {item.unit_name}", min_value=0.01, value=1.0, step=1.0, key=f"movement_quantity_{item.item_id}")
                with movement_columns[2]:
                    movement_submitted = st.form_submit_button("Aplicar movimiento", type="primary", use_container_width=True)

            if movement_submitted:
                if movement == "Salida" and movement_quantity > item.available_quantity:
                    st.error("La salida no puede superar la existencia disponible.")
                else:
                    _save_items(_adjust_stock(items, item.item_id, movement, float(movement_quantity)))
                    st.rerun()

            render_info_card("Costo utilizable en Costeo", f"Cada {item.unit_name} de {item.name} tiene un costo orientativo de {format_money(item.unit_cost)}.", "COSTO UNITARIO")
