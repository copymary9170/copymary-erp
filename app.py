"""Punto de entrada de CopyMary ERP."""

import streamlit as st

from src.assets import render_assets
from src.assets_backup import render_assets_backup
from src.commercial import (
    render_cash,
    render_clients,
    render_commercial_dashboard,
    render_sales,
)
from src.commercial_documents import render_quotes, render_receipts
from src.commercial_reports import render_commercial_reports
from src.components import apply_base_styles, render_info_card, render_page_header
from src.config import APP_NAME, APP_VERSION, PROJECT_STATUS
from src.costing import render_costing
from src.general_settings import render_general_settings
from src.inventory import render_inventory
from src.inventory_movements import render_inventory_movements
from src.modules import MODULES
from src.price_export import render_price_export
from src.price_rounding import render_price_rounding
from src.purchasing import render_purchases, render_suppliers
from src.session_backup import render_session_backup
from src.stock_alerts import render_stock_alerts

st.set_page_config(
    page_title=APP_NAME,
    page_icon="CM",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_base_styles()

FUNCTIONAL_MODULES = {
    "Configuración General": render_general_settings,
    "Panel comercial": render_commercial_dashboard,
    "Clientes": render_clients,
    "Ventas y pedidos": render_sales,
    "Cotizaciones": render_quotes,
    "Comprobantes": render_receipts,
    "Caja": render_cash,
    "Reportes comerciales": render_commercial_reports,
    "Proveedores": render_suppliers,
    "Compras": render_purchases,
    "Activos": render_assets,
    "Respaldar activos": render_assets_backup,
    "Inventario": render_inventory,
    "Movimientos de inventario": render_inventory_movements,
    "Alertas de inventario": render_stock_alerts,
    "Costeo": render_costing,
    "Ajustar precios": render_price_rounding,
    "Exportar precios": render_price_export,
    "Respaldo general": render_session_backup,
}
NAVIGATION_OPTIONS = ["Inicio", *MODULES.keys()]
for extra_page in (
    "Panel comercial",
    "Clientes",
    "Ventas y pedidos",
    "Cotizaciones",
    "Comprobantes",
    "Caja",
    "Reportes comerciales",
    "Proveedores",
    "Compras",
    "Inventario",
    "Movimientos de inventario",
    "Alertas de inventario",
    "Respaldar activos",
    "Ajustar precios",
    "Exportar precios",
    "Respaldo general",
):
    if extra_page not in NAVIGATION_OPTIONS:
        NAVIGATION_OPTIONS.append(extra_page)

with st.sidebar:
    st.title(APP_NAME)
    st.caption("Panel empresarial en construcción")
    st.divider()
    selected_page = st.radio(
        "Secciones disponibles",
        NAVIGATION_OPTIONS,
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(f"Versión {APP_VERSION}")
    st.caption(f"Estado: {PROJECT_STATUS}")
    st.info("Las funciones actuales trabajan solo durante la sesión y no guardan datos permanentemente.")


def render_home() -> None:
    with st.container(border=True):
        render_page_header(
            APP_NAME,
            "Sistema empresarial en construcción con módulos temporales conectados.",
        )
        st.caption(
            "El ERP conecta clientes, ventas, compras, proveedores, caja, inventario y reportes."
        )

    st.warning("Los datos pueden perderse al cerrar o reiniciar la aplicación.")

    st.subheader("Flujo funcional actual")
    flow_columns = st.columns(3)
    flow = (
        ("Panel comercial", "Resume ventas, pedidos, caja y alertas."),
        ("Clientes", "Registra clientes y consulta su historial."),
        ("Cotizaciones", "Crea propuestas con varios conceptos y conviértelas en ventas."),
        ("Ventas y pedidos", "Controla trabajos, pagos, entregas y ganancias."),
        ("Comprobantes", "Genera documentos descargables para ventas pagadas."),
        ("Caja", "Registra ingresos y egresos y calcula el saldo."),
        ("Reportes comerciales", "Exporta clientes, ventas, caja y cotizaciones."),
        ("Proveedores", "Registra proveedores y consulta sus compras."),
        ("Compras", "Conecta abastecimiento con Inventario y Caja."),
        ("Configuración General", "Define moneda, margen y costos fijos."),
        ("Activos", "Aporta la depreciación por unidad del equipo."),
        ("Inventario", "Calcula el costo unitario de los materiales."),
        ("Movimientos de inventario", "Registra entradas y salidas con trazabilidad."),
        ("Alertas de inventario", "Detecta faltantes y prepara una lista de reposición."),
        ("Costeo", "Combina los datos y calcula precios orientativos."),
        ("Ajustar precios", "Redondea hacia arriba para proteger el margen."),
        ("Exportar precios", "Descarga o recupera la lista de precios en CSV."),
        ("Respaldo general", "Guarda toda la sesión principal en un solo archivo JSON."),
    )
    for index, (title, description) in enumerate(flow):
        with flow_columns[index % 3]:
            render_info_card(title, description, "FUNCIÓN TEMPORAL")

    st.divider()
    st.subheader("Estado de los demás módulos")
    descriptive_modules = [
        (name, info)
        for name, info in MODULES.items()
        if name not in FUNCTIONAL_MODULES
    ]
    module_columns = st.columns(2)
    for index, (name, info) in enumerate(descriptive_modules):
        with module_columns[index % 2]:
            render_info_card(name, info["description"], "INTERFAZ DESCRIPTIVA")


def render_descriptive_module(module_name: str) -> None:
    module_info = MODULES.get(module_name)
    if module_info is None:
        st.error("La sección solicitada no está disponible.")
        return

    with st.container(border=True):
        render_page_header(module_name, module_info["description"])
        st.caption("Este módulo permanece en etapa de Blueprint.")

    st.warning("Esta pantalla todavía no ejecuta operaciones ni guarda datos.")
    render_info_card("Estado", module_info["status"], "SITUACIÓN ACTUAL")
    render_info_card("Objetivo", module_info["objective"], "PROPÓSITO")
    st.subheader("Funciones previstas")
    for planned_function in module_info["planned_functions"]:
        st.markdown(f"- {planned_function}")


if selected_page == "Inicio":
    render_home()
elif selected_page in FUNCTIONAL_MODULES:
    FUNCTIONAL_MODULES[selected_page]()
elif selected_page in MODULES:
    render_descriptive_module(selected_page)
else:
    st.error("La opción seleccionada no existe.")
