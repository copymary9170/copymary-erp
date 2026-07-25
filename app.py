"""Punto de entrada de CopyMary ERP."""
from src import app_shell
from src.catalog_items_reactive import render_catalog_items as render_catalog_items_reactive
from src.finishing_loader import activate_finishing_modules
from src.general_settings_persistence import persist_general_settings_if_changed
from src.inventory_consistency_rules_safe_loader import activate_inventory_consistency_rules_safe
from src.inventory_counts_safe_loader import activate_inventory_counts_safe
from src.inventory_dashboard_safe_loader import activate_inventory_dashboard_safe
from src.inventory_data_quality_safe_loader import activate_inventory_data_quality_safe
from src.inventory_enterprise_loader import activate_inventory_enterprise
from src.inventory_flow_consistency_safe_loader import activate_inventory_flow_consistency_safe
from src.inventory_lots_safe_loader import activate_inventory_lots_safe
from src.inventory_metadata_safe_loader import activate_inventory_metadata_safe
from src.inventory_movements_safe_loader import activate_inventory_movements_safe
from src.inventory_priority_summary_safe_loader import activate_inventory_priority_summary_safe
from src.inventory_replenishment_safe_loader import activate_inventory_replenishment_safe
from src.inventory_reservations_safe_loader import activate_inventory_reservations_safe
from src.inventory_review_plan_safe_loader import activate_inventory_review_plan_safe
from src.inventory_stock_view_loader import activate_inventory_stock_view
from src.inventory_workspace_safe_loader import activate_inventory_workspace_safe
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
# Quinta fase de Inventario: mejora únicamente Reservas y exige confirmación
# para liberar o consumir una reserva completa con trazabilidad.
activate_inventory_reservations_safe()
# Sexta fase de Inventario: mejora únicamente Reposición y considera reservas
# y compras pendientes sin generar órdenes automáticamente.
activate_inventory_replenishment_safe()
# Séptima fase de Inventario: conserva Existencias y añade trazabilidad visual
# de lotes y vencimientos sin modificar datos ni costos.
activate_inventory_lots_safe()
# Octava fase de Inventario: permite editar únicamente ubicación, lote y
# vencimiento con confirmación expresa y un historial separado de auditoría.
activate_inventory_metadata_safe()
# Novena fase de Inventario: elimina de su navegación Registrar y Factura de
# compra para completar la separación entre Catálogo, Compras y Recepción.
activate_inventory_workspace_safe()
# Décima fase de Inventario: añade una guía visual y términos consistentes para
# el flujo Catálogo → Compras → Recepción → Inventario, sin cambiar la lógica.
activate_inventory_flow_consistency_safe()
# Undécima fase de Inventario: añade un diagnóstico de solo lectura para
# detectar datos maestros incompletos sin corregir ni modificar registros.
activate_inventory_data_quality_safe()
# Duodécima fase de Inventario: detecta códigos duplicados, valores negativos,
# mínimos incoherentes y existencias anómalas sin modificar ningún registro.
activate_inventory_consistency_rules_safe()
# Decimotercera fase de Inventario: agrupa los hallazgos por prioridad y muestra
# acciones recomendadas sin corregir ni modificar registros automáticamente.
activate_inventory_priority_summary_safe()
# Decimocuarta fase de Inventario: convierte los hallazgos en una cola de trabajo
# descargable sin modificar datos ni marcar tareas como resueltas.
activate_inventory_review_plan_safe()
# La vista reactiva se registra después de la integración para sustituir la
# versión basada en st.form, cuyos selectores no redibujaban los campos.
app_shell.FUNCTIONAL_MODULES["Catálogo de artículos"] = render_catalog_items_reactive
_activate_process_quotes_safely()

# Se ejecuta en cada rerun, pero solo escribe cuando la huella de Configuración
# General cambió. Así el botón "Guardar configuración" también persiste en la
# base de datos, sin exigir un segundo clic en la pantalla de Respaldos.
persist_general_settings_if_changed()
run_app()
