"""Punto de entrada de CopyMary ERP."""
from src.database_startup_guard import install_database_startup_guard

# Debe instalarse antes de importar módulos que capturan referencias a
# initialize_database o abren conexiones durante el arranque.
install_database_startup_guard()

from src import app_shell
from src.assets_workspace_loader import activate_assets_workspace
from src.business_goals_admin_loader import activate_business_goals_admin
from src.core_data_startup import load_core_data_on_startup
from src.enterprise_coordination_loader import activate_enterprise_coordination_hub
from src.finishing_loader import activate_finishing_modules
from src.general_settings_persistence import persist_general_settings_if_changed
from src.global_rates_bar import activate_global_rates_bar
from src.home_dashboard_safe_loader import activate_home_dashboard_safe
from src.integrated_inventory_catalog import wrap_inventory_renderer
from src.integrated_purchases_receiving import wrap_purchases_renderer
from src.inventory_audit_unified_safe_loader import activate_inventory_unified_audit_safe
from src.inventory_counts_safe_loader import activate_inventory_counts_safe
from src.inventory_dashboard_safe_loader import activate_inventory_dashboard_safe
from src.inventory_enterprise_loader import activate_inventory_enterprise
from src.inventory_flow_consistency_safe_loader import activate_inventory_flow_consistency_safe
from src.inventory_insights_hub_loader import activate_inventory_insights_hub
from src.inventory_lots_safe_loader import activate_inventory_lots_safe
from src.inventory_metadata_safe_loader import activate_inventory_metadata_safe
from src.inventory_movements_safe_loader import activate_inventory_movements_safe
from src.inventory_replenishment_safe_loader import activate_inventory_replenishment_safe
from src.inventory_reservations_safe_loader import activate_inventory_reservations_safe
from src.inventory_stock_view_loader import activate_inventory_stock_view
from src.inventory_workspace_safe_loader import activate_inventory_workspace_safe
from src.module_bootstrap import activate_module_bootstrap
from src.navigation_cleanup_loader import activate_navigation_cleanup
from src.print_cost_loader import activate_print_cost_module
from src.printer_asset_specs import activate_printer_asset_specs
from src.purchases_overview_safe_loader import activate_purchases_overview_safe
from src.rates_master_loader import activate_rates_master
from src.reports_hub_loader import activate_reports_hub
from src.session_store import hydrate_session_store_on_startup
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
load_core_data_on_startup()
hydrate_session_store_on_startup()
activate_module_bootstrap()
activate_printer_asset_specs()
activate_print_cost_module()
activate_finishing_modules()
activate_inventory_enterprise()
activate_supply_chain_integration()
activate_home_dashboard_safe()
activate_business_goals_admin()
activate_purchases_overview_safe()
activate_inventory_stock_view()
activate_inventory_movements_safe()
activate_inventory_dashboard_safe()
activate_inventory_counts_safe()
activate_inventory_reservations_safe()
activate_inventory_replenishment_safe()
activate_inventory_lots_safe()
activate_inventory_metadata_safe()
activate_inventory_workspace_safe()
activate_inventory_flow_consistency_safe()
activate_inventory_insights_hub()
activate_inventory_unified_audit_safe()

if "Inventario" in app_shell.FUNCTIONAL_MODULES:
    app_shell.FUNCTIONAL_MODULES["Inventario"] = wrap_inventory_renderer(app_shell.FUNCTIONAL_MODULES["Inventario"])
if "Compras" in app_shell.FUNCTIONAL_MODULES:
    app_shell.FUNCTIONAL_MODULES["Compras"] = wrap_purchases_renderer(app_shell.FUNCTIONAL_MODULES["Compras"])
app_shell.FUNCTIONAL_MODULES.pop("Catálogo de artículos", None)
app_shell.FUNCTIONAL_MODULES.pop("Recepción de mercancía", None)

_activate_process_quotes_safely()
# Configuración General queda como única fuente editable de tasas; Costeo solo consume su histórico.
activate_rates_master()
activate_reports_hub()
activate_enterprise_coordination_hub()
# Reorganiza Activos sin eliminar el registro, historial o mantenimiento existentes.
activate_assets_workspace()
activate_navigation_cleanup()
# Debe activarse al final, cuando todos los loaders ya sustituyeron sus renderers.
activate_global_rates_bar()
persist_general_settings_if_changed()
run_app()
