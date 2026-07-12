"""Punto de entrada de CopyMary ERP."""
from src.module_bootstrap import activate_module_bootstrap
from src.print_cost_loader import activate_print_cost_module
from src.printer_asset_specs import activate_printer_asset_specs
from src.top_navigation_app import run_app

activate_module_bootstrap()
activate_printer_asset_specs()
activate_print_cost_module()
run_app()
