"""Punto de entrada de CopyMary ERP."""
from src.finishing_loader import activate_finishing_modules
from src.inventory_enterprise_loader import activate_inventory_enterprise
from src.module_bootstrap import activate_module_bootstrap
from src.print_cost_loader import activate_print_cost_module
from src.printer_asset_specs import activate_printer_asset_specs
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


activate_module_bootstrap()
activate_printer_asset_specs()
activate_print_cost_module()
activate_finishing_modules()
activate_inventory_enterprise()
_activate_process_quotes_safely()
run_app()
