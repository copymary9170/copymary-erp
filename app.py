"""Punto de entrada de CopyMary ERP."""
from src import app_shell
from src.catalog_items_reactive import render_catalog_items as render_catalog_items_reactive
from src.finishing_loader import activate_finishing_modules
from src.general_settings_persistence import persist_general_settings_if_changed
from src.inventory_counts_safe_loader import activate_inventory_counts_safe
from src.inventory_dashboard_safe_loader import activate_inventory_dashboard_safe
from src.inventory_enterprise_loader import activate_inventory_enterprise
from src.inventory_movements_safe_loader import activate_inventory_movements_safe
from src.inventory_stock_view_loader import activate_inventory_stock_view
from src.module_bootstrap import activate_module_bootstrap
from src.print_cost_loader import activate_print_cost_module
from src.printer_asset_specs import activate_printer_asset_specs
from src.startup_restore import restore_session_snapshot_on_startup
from src.supply_chain_integration import activate_supply_chain_integration
from src.top_navigation_app import run_app


def _activate_process_quotes_safely() -> None:
    """Activa la extensión de cotizaciones sin derribar todo el ERP si falta el archivo."""
    try:
        from src.process_quote_loader import activate_process_quotes
    except ModuleNotFoundError as exc:
        if exc.name != "src.process_quote_loader":
            raise
        return
    activate_process_quotes()


restore_session_snapshot_on_startup()
activate_module_bootstrap()
activate_printer_asset_specs()
activate_print_cost_module()
activate_finishing_modules()
activate_inventory_enterprise()
activate_supply_chain_integration()
# Primera fase de Inventario: solo sustituye la tabla visual de existencias.
# No modifica movimientos, reservas, conteos ni datos guardados.
activate_inventory_stock_view()
# Segunda fase de Inventario: sustituye únicamente la vista de movimientos
# para impedir que una compra se registre manualmente fuera de Recepción.
activate_inventory_movements_safe()
# Tercera fase de Inventario: mejora únicamente el panel de indicadores y
# calcula físico, reservado y disponible sin modificar los registros.
activate_inventory_dashboard_safe()
# Cuarta fase de Inventario: el conteo físico calcula y muestra diferencias,
# pero solo aplica el ajuste después de una confirmación expresa.
activate_inventory_counts_safe()
# La vista reactiva se registra después de la integración para sustituir la
# versión basada en st.form, cuyos selectores no redibujaban los campos.
app_shell.FUNCTIONAL_MODULES["Catálogo de artículos"] = render_catalog_items_reactive
_activate_process_quotes_safely()

# Se ejecuta en cada rerun, pero solo escribe cuando la huella de Configuración
# General cambió. Así el botón "Guardar configuración" también persiste en la
# base de datos, sin exigir un segundo clic en la pantalla de Respaldos.
persist_general_settings_if_changed()
run_app()
