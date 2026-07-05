"""Restauración segura con validación estructural y referencial."""

import streamlit as st

from src import session_backup
from src.components import render_info_card, render_page_header


ID_FIELDS = {
    "customers_registry": "client_id",
    "sales_registry": "sale_id",
    "suppliers_registry": "supplier_id",
    "purchases_registry": "purchase_id",
    "products_registry": "product_id",
    "production_log": "production_id",
    "inventory_registry": "item_id",
    "inventory_movements": "movement_id",
    "cash_movements": "movement_id",
    "cash_closings": "closing_id",
    "payment_records": "payment_id",
    "supplier_payment_records": "payment_id",
    "team_members": "member_id",
    "team_payments": "payment_id",
    "commission_assignments": "assignment_id",
}


def _duplicates(records: list[dict], field: str) -> list[str]:
    values = [str(item.get(field, "")) for item in records if item.get(field)]
    return sorted({value for value in values if values.count(value) > 1})


def _validate(restored: dict) -> tuple[list[str], list[str]]:
    critical: list[str] = []
    warnings: list[str] = []

    for section, field in ID_FIELDS.items():
        records = restored.get(section, [])
        duplicates = _duplicates(records, field)
        if duplicates:
            critical.append(
                f"{session_backup.SECTION_LABELS.get(section, section)} contiene IDs duplicados: "
                f"{', '.join(duplicates[:8])}."
            )
        missing = sum(1 for item in records if not item.get(field))
        if missing:
            warnings.append(
                f"{session_backup.SECTION_LABELS.get(section, section)} tiene {missing} registro(s) sin {field}."
            )

    clients = {str(item.get("client_id", "")) for item in restored.get("customers_registry", [])}
    sales = {str(item.get("sale_id", "")) for item in restored.get("sales_registry", [])}
    suppliers = {str(item.get("supplier_id", "")) for item in restored.get("suppliers_registry", [])}
    purchases = {str(item.get("purchase_id", "")) for item in restored.get("purchases_registry", [])}
    inventory = {str(item.get("item_id", "")) for item in restored.get("inventory_registry", [])}
    products = {str(item.get("product_id", "")) for item in restored.get("products_registry", [])}
    members = {str(item.get("member_id", "")) for item in restored.get("team_members", [])}

    for item in restored.get("sales_registry", []):
        client_id = str(item.get("client_id", ""))
        if client_id and client_id not in clients:
            warnings.append(f"Venta {item.get('sale_id', '')} referencia un cliente inexistente.")
    for item in restored.get("purchases_registry", []):
        supplier_id = str(item.get("supplier_id", ""))
        material_id = str(item.get("inventory_item_id", ""))
        if supplier_id and supplier_id not in suppliers:
            warnings.append(f"Compra {item.get('purchase_id', '')} referencia un proveedor inexistente.")
        if material_id and material_id not in inventory:
            warnings.append(f"Compra {item.get('purchase_id', '')} referencia un material inexistente.")
    for item in restored.get("payment_records", []):
        if str(item.get("sale_id", "")) not in sales:
            warnings.append(f"Abono {item.get('payment_id', '')} no tiene una venta válida.")
    for item in restored.get("supplier_payment_records", []):
        if str(item.get("purchase_id", "")) not in purchases:
            warnings.append(f"Pago {item.get('payment_id', '')} no tiene una compra válida.")
    for item in restored.get("team_payments", []):
        if str(item.get("member_id", "")) not in members:
            warnings.append(f"Pago al equipo {item.get('payment_id', '')} no tiene colaborador válido.")
    for item in restored.get("commission_assignments", []):
        if str(item.get("sale_id", "")) not in sales:
            warnings.append(f"Asignación {item.get('assignment_id', '')} no tiene venta válida.")
        if str(item.get("member_id", "")) not in members:
            warnings.append(f"Asignación {item.get('assignment_id', '')} no tiene colaborador válido.")
    for item in restored.get("production_log", []):
        product_id = str(item.get("product_id", ""))
        if product_id and product_id not in products:
            warnings.append(f"Producción {item.get('production_id', '')} no tiene producto válido.")
    for item in restored.get("inventory_registry", []):
        try:
            if float(item.get("available_quantity", 0.0)) < 0:
                critical.append(f"{item.get('name', 'Material')} tiene existencia negativa.")
        except (TypeError, ValueError):
            critical.append(f"{item.get('name', 'Material')} tiene una existencia inválida.")

    return critical, warnings


def render_safe_session_backup() -> None:
    with st.container(border=True):
        render_page_header(
            "Respaldo general",
            "Guarda o recupera la información con validación antes de reemplazar la sesión.",
        )
        st.caption("La restauración revisa estructura, IDs y relaciones principales.")

    st.warning("Descarga este respaldo antes de cerrar la sesión para evitar perder datos.")
    session_backup._metrics(
        {
            session_backup.SECTION_LABELS[key]: session_backup._count(st.session_state.get(key))
            for key in session_backup.SESSION_KEYS
        }
    )
    st.download_button(
        "Descargar respaldo general",
        data=session_backup._build_backup(),
        file_name="copymary_respaldo_sesion_v2.json",
        mime="application/json",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    uploaded = st.file_uploader("Selecciona un respaldo JSON de CopyMary ERP", type=("json",))
    if uploaded is not None:
        try:
            restored = session_backup._parse_backup(uploaded.getvalue())
            critical, warnings = _validate(restored)
        except (TypeError, ValueError) as exc:
            st.error(str(exc))
        else:
            present = restored["present_sections"]
            available = [key for key in session_backup.SESSION_KEYS if key in present]
            st.caption(f"Fecha UTC: {restored['created_at_utc']}")
            session_backup._metrics(
                {
                    session_backup.SECTION_LABELS[key]: session_backup._count(restored[key])
                    for key in available
                }
            )

            if critical:
                st.error("El respaldo está bloqueado porque contiene problemas críticos.")
                for issue in critical[:12]:
                    st.error(issue)
            else:
                st.success("El archivo es compatible y no tiene errores críticos.")

            if warnings:
                with st.expander(f"Advertencias encontradas: {len(warnings)}", expanded=True):
                    for warning in warnings[:30]:
                        st.warning(warning)

            selected = st.multiselect(
                "Secciones que deseas restaurar",
                options=available,
                default=available,
                format_func=lambda key: session_backup.SECTION_LABELS[key],
                disabled=bool(critical),
            )
            confirmation = st.checkbox(
                "Entiendo que las secciones seleccionadas reemplazarán sus datos actuales.",
                disabled=bool(critical),
            )
            if st.button(
                "Restaurar secciones seleccionadas",
                type="primary",
                use_container_width=True,
                disabled=bool(critical) or not selected or not confirmation,
            ):
                session_backup._restore(restored, selected)
                st.success(f"Se restauraron {len(selected)} sección(es).")
                st.rerun()

    render_info_card(
        "Restauración protegida",
        "Los errores críticos bloquean la carga; las advertencias se muestran antes de confirmar.",
        "RESPALDO VALIDADO",
    )
