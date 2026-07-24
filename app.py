"""Punto de entrada de CopyMary ERP."""
from src.finishing_loader import activate_finishing_modules
from src.general_settings_persistence import persist_general_settings_if_changed
from src.inventory_enterprise_loader import activate_inventory_enterprise
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
_activate_process_quotes_safely()

# Se ejecuta en cada rerun, pero solo escribe cuando la huella de Configuración
# General cambió. Así el botón "Guardar configuración" también persiste en la
# base de datos, sin exigir un segundo clic en la pantalla de Respaldos.
persist_general_settings_if_changed()
run_app()