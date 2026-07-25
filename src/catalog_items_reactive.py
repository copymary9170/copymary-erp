"""Vista reactiva del Catálogo de artículos.

Los selectores que controlan campos condicionales viven fuera de ``st.form`` para
que Streamlit vuelva a dibujar inmediatamente las medidas, el peso, el volumen y
el gramaje.
"""
from __future__ import annotations

from uuid import uuid4

import streamlit as st

from src.catalog_items import (
    ARTICLE_TYPES,
    CATEGORIES,
    FORBIDDEN_INVENTORY_UNITS,
    GRAMMAGE_INDICATED,
    GRAMMAGE_NA,
    GRAMMAGE_UNKNOWN,
    INVENTORY_UNITS,
    MEASUREMENT_TYPES,
    CatalogItem,
    _now,
    _technical_values,
    add_item,
    get_catalog_items,
    migrate_inventory_to_catalog,
)


def _render_list() -> None:
    items = get_catalog_items()
    if not items:
        st.info("No hay artículos registrados.")
        return
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


def _render_create() -> None:
    st.caption("Los campos cambian inmediatamente según la categoría y el tipo de medida seleccionado.")

    with st.container(border=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nombre", key="catalog_name")
        sku = c2.text_input("SKU", key="catalog_sku")

        c3, c4, c5 = st.columns(3)
        article_type = c3.selectbox("Tipo", ARTICLE_TYPES, key="catalog_article_type")
        category = c4.selectbox("Categoría", CATEGORIES, key="catalog_category")
        unit = c5.selectbox("Unidad de inventario", INVENTORY_UNITS, key="catalog_inventory_unit")
        brand = st.text_input("Marca", key="catalog_brand")

        measurement_type = st.selectbox(
            "¿Cómo se mide físicamente cada unidad?",
            MEASUREMENT_TYPES,
            key="catalog_measurement_type",
        )

        top = bottom = left = right = 0.0
        weight = volume = 0.0
        technical = _technical_values(0.0, 0.0, 0.0, 0.0)

        if measurement_type == "Área":
            st.markdown("##### Medidas reales de los cuatro lados")
            st.caption(
                "Mide cada borde por separado. El sistema detecta cortes irregulares y usa "
                "los lados más pequeños para calcular el área utilizable."
            )
            a, b = st.columns(2)
            top = a.number_input("Ancho superior (cm)", min_value=0.0, step=0.01, key="catalog_width_top")
            bottom = b.number_input("Ancho inferior (cm)", min_value=0.0, step=0.01, key="catalog_width_bottom")
            c, d = st.columns(2)
            left = c.number_input("Alto izquierdo (cm)", min_value=0.0, step=0.01, key="catalog_height_left")
            right = d.number_input("Alto derecho (cm)", min_value=0.0, step=0.01, key="catalog_height_right")
            technical = _technical_values(top, bottom, left, right)

            if technical["usable_area_cm2_value"] > 0:
                metrics = st.columns(5)
                metrics[0].metric("Ancho promedio", f"{technical['width_cm']:.2f} cm")
                metrics[1].metric("Alto promedio", f"{technical['height_cm']:.2f} cm")
                metrics[2].metric("Área estimada", f"{technical['estimated_area_cm2']:.2f} cm²")
                metrics[3].metric("Área utilizable", f"{technical['usable_area_cm2_value']:.2f} cm²")
                metrics[4].metric("Equivalente", f"{technical['area_m2']:.6f} m²")
                if technical["cut_status"] == "Corte irregular":
                    st.warning(
                        f"Corte irregular: diferencia máxima de {technical['maximum_difference_cm']:.2f} cm. "
                        "Producción y Costeo usarán el área utilizable conservadora."
                    )
                else:
                    st.success("Corte regular: las diferencias están dentro de la tolerancia de 0,20 cm.")
            elif any(value > 0 for value in (top, bottom, left, right)):
                st.info("Completa los cuatro lados para calcular el área y evaluar el corte.")

        elif measurement_type == "Peso":
            weight = st.number_input("Peso por unidad (g)", min_value=0.0, step=0.1, key="catalog_weight")
        elif measurement_type == "Volumen":
            volume = st.number_input("Volumen por unidad (ml)", min_value=0.0, step=1.0, key="catalog_volume")

        grammage_status = GRAMMAGE_NA
        grammage = 0.0
        if category == "Papel y cartulina":
            st.markdown("##### Gramaje")
            grammage_status = st.radio(
                "¿El empaque indica el gramaje?",
                (GRAMMAGE_INDICATED, GRAMMAGE_UNKNOWN),
                horizontal=True,
                key="catalog_grammage_status",
            )
            if grammage_status == GRAMMAGE_INDICATED:
                grammage = st.number_input(
                    "Gramaje (g/m²)", min_value=1.0, value=75.0, step=1.0,
                    key="catalog_grammage_gsm",
                )
            else:
                st.info("Se guardará como gramaje no indicado. No se asignará 75 g/m² automáticamente.")

        a, b = st.columns(2)
        minimum = a.number_input("Stock mínimo", min_value=0.0, key="catalog_minimum")
        maximum = b.number_input("Stock máximo", min_value=0.0, key="catalog_maximum")
        notes = st.text_area("Observaciones técnicas", key="catalog_notes")
        submitted = st.button("Crear artículo", type="primary", use_container_width=True, key="catalog_submit")

    if not submitted:
        return
    if not name.strip():
        st.error("El nombre es obligatorio.")
        return
    if unit.casefold() in FORBIDDEN_INVENTORY_UNITS:
        st.error("Las medidas físicas no pueden usarse como unidad de inventario.")
        return
    if measurement_type == "Área" and technical["usable_area_cm2_value"] <= 0:
        st.error("Debes completar los cuatro lados para un material medido por área.")
        return
    if measurement_type == "Peso" and weight <= 0:
        st.error("El peso por unidad debe ser mayor que cero.")
        return
    if measurement_type == "Volumen" and volume <= 0:
        st.error("El volumen por unidad debe ser mayor que cero.")
        return
    if maximum > 0 and minimum > maximum:
        st.error("El stock mínimo no puede ser mayor que el máximo.")
        return

    try:
        add_item(CatalogItem(
            item_id=uuid4().hex[:8].upper(), sku=sku.strip(), name=name.strip(),
            article_type=article_type, category=category, inventory_unit=unit,
            brand=brand.strip(), measurement_type=measurement_type,
            grammage_status=grammage_status, grammage_gsm=float(grammage),
            width_top_cm=float(top), width_bottom_cm=float(bottom),
            height_left_cm=float(left), height_right_cm=float(right),
            unit_weight_g=float(weight), unit_volume_ml=float(volume),
            minimum_stock=float(minimum), maximum_stock=float(maximum),
            technical_notes=notes.strip(), created_at_utc=_now(), updated_at_utc=_now(),
            **technical,
        ))
        st.success("Artículo creado con su ficha técnica completa.")
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))


def render_catalog_items() -> None:
    st.title("Catálogo de artículos")
    st.caption(
        "Aquí se conservan las propiedades permanentes del material: medidas reales de los cuatro lados, "
        "área útil, m², gramaje, peso, volumen y calidad del corte."
    )
    tab_list, tab_create, tab_migrate = st.tabs(["Artículos", "Crear artículo", "Migrar desde Inventario"])
    with tab_list:
        _render_list()
    with tab_create:
        _render_create()
    with tab_migrate:
        preview = migrate_inventory_to_catalog(dry_run=True)
        st.write(f"Se crearían **{preview['created']}** artículos y se omitirían **{preview['skipped']}**.")
        st.caption(
            "La migración conserva medidas de los cuatro lados, área utilizable, m², gramaje, ml, peso, "
            "calidad del corte y observaciones. El inventario original no se modifica."
        )
        if preview["created"] and st.button("Ejecutar migración", type="primary", key="catalog_migrate"):
            result = migrate_inventory_to_catalog(dry_run=False)
            st.success(f"Migración completada: {result['created']} artículos creados. El inventario original no fue modificado.")
            st.rerun()
