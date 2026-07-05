"""Alertas temporales de inventario y lista de reposición para CopyMary ERP."""

import csv
from io import StringIO

import streamlit as st

from src.components import render_info_card, render_page_header


def _get_items() -> list[dict]:
    items: list[dict] = []
    for raw_item in st.session_state.get("inventory_registry", []):
        if isinstance(raw_item, dict):
            items.append(dict(raw_item))
        else:
            items.append(
                {
                    "item_id": getattr(raw_item, "item_id", ""),
                    "name": getattr(raw_item, "name", "Material"),
                    "category": getattr(raw_item, "category", "Otro"),
                    "purchase_cost": float(getattr(raw_item, "purchase_cost", 0.0)),
                    "purchased_quantity": float(getattr(raw_item, "purchased_quantity", 1.0)),
                    "available_quantity": float(getattr(raw_item, "available_quantity", 0.0)),
                    "unit_name": getattr(raw_item, "unit_name", "unidad"),
                    "minimum_stock": float(getattr(raw_item, "minimum_stock", 0.0)),
                }
            )
    return items


def _unit_cost(item: dict) -> float:
    purchased_quantity = max(float(item.get("purchased_quantity", 1.0)), 0.01)
    return float(item.get("purchase_cost", 0.0)) / purchased_quantity


def _reorder_quantity(item: dict, multiplier: float) -> float:
    minimum_stock = float(item.get("minimum_stock", 0.0))
    target_stock = minimum_stock * multiplier
    available_quantity = float(item.get("available_quantity", 0.0))
    return max(target_stock - available_quantity, 0.0)


def _build_reorder_csv(items: list[dict], multiplier: float) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(
        [
            "ID",
            "Material",
            "Categoría",
            "Existencia actual",
            "Existencia mínima",
            "Cantidad sugerida a comprar",
            "Unidad",
            "Costo unitario",
            "Costo estimado de reposición",
        ]
    )
    for item in items:
        reorder_quantity = _reorder_quantity(item, multiplier)
        unit_cost = _unit_cost(item)
        writer.writerow(
            [
                item.get("item_id", ""),
                item.get("name", ""),
                item.get("category", ""),
                f"{float(item.get('available_quantity', 0.0)):.4f}",
                f"{float(item.get('minimum_stock', 0.0)):.4f}",
                f"{reorder_quantity:.4f}",
                item.get("unit_name", "unidad"),
                f"{unit_cost:.4f}",
                f"{(reorder_quantity * unit_cost):.4f}",
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def render_stock_alerts() -> None:
    """Renderiza alertas de existencias y sugerencias de reposición."""
    with st.container(border=True):
        render_page_header(
            "Alertas de inventario",
            "Detecta materiales bajos y prepara una lista orientativa de reposición.",
        )
        st.caption("Las alertas se calculan con las existencias y mínimos de la sesión actual.")

    items = _get_items()
    if not items:
        st.info("No hay materiales registrados. Primero agrega o importa inventario.")
        return

    multiplier = st.selectbox(
        "Objetivo de reposición",
        options=(1.0, 1.5, 2.0, 3.0),
        index=2,
        format_func=lambda value: f"{value:.1f} × la existencia mínima",
        help="La cantidad sugerida intenta llevar cada material hasta este múltiplo de su mínimo.",
    )

    low_stock_items = [
        item
        for item in items
        if float(item.get("available_quantity", 0.0))
        <= float(item.get("minimum_stock", 0.0))
    ]
    out_of_stock_items = [
        item for item in items if float(item.get("available_quantity", 0.0)) <= 0
    ]
    estimated_reorder_cost = sum(
        _reorder_quantity(item, multiplier) * _unit_cost(item)
        for item in low_stock_items
    )

    summary_columns = st.columns(4)
    summary_columns[0].metric("Materiales registrados", str(len(items)))
    summary_columns[1].metric("Existencias bajas", str(len(low_stock_items)))
    summary_columns[2].metric("Agotados", str(len(out_of_stock_items)))
    summary_columns[3].metric(
        "Reposición estimada",
        f"$ {estimated_reorder_cost:,.2f}",
    )

    if not low_stock_items:
        st.success("No hay materiales en nivel mínimo o agotados.")
        return

    st.download_button(
        "Descargar lista de reposición",
        data=_build_reorder_csv(low_stock_items, multiplier),
        file_name="copymary_lista_reposicion.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )

    st.subheader("Materiales que requieren atención")
    for item in sorted(
        low_stock_items,
        key=lambda current: float(current.get("available_quantity", 0.0)),
    ):
        available_quantity = float(item.get("available_quantity", 0.0))
        minimum_stock = float(item.get("minimum_stock", 0.0))
        reorder_quantity = _reorder_quantity(item, multiplier)
        unit_cost = _unit_cost(item)
        estimated_cost = reorder_quantity * unit_cost
        unit_name = str(item.get("unit_name", "unidad"))

        with st.container(border=True):
            st.markdown(f"### {item.get('name', 'Material')}")
            st.caption(
                f"{item.get('category', 'Otro')} · ID {item.get('item_id', '')}"
            )

            metric_columns = st.columns(4)
            metric_columns[0].metric(
                "Existencia actual",
                f"{available_quantity:,.2f} {unit_name}",
            )
            metric_columns[1].metric(
                "Existencia mínima",
                f"{minimum_stock:,.2f} {unit_name}",
            )
            metric_columns[2].metric(
                "Compra sugerida",
                f"{reorder_quantity:,.2f} {unit_name}",
            )
            metric_columns[3].metric(
                "Costo estimado",
                f"$ {estimated_cost:,.2f}",
            )

            status = "AGOTADO" if available_quantity <= 0 else "EXISTENCIA BAJA"
            render_info_card(
                "Prioridad de reposición",
                (
                    f"Estado: {status}. El cálculo propone llegar a {multiplier:.1f} veces "
                    "la existencia mínima definida."
                ),
                "ALERTA TEMPORAL",
            )

    st.warning(
        "La cantidad sugerida usa el costo unitario histórico del inventario y no sustituye una cotización actual del proveedor."
    )
