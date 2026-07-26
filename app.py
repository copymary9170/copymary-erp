"""Punto de entrada de CopyMary ERP."""
from src import app_shell
from src.business_goals_admin_loader import activate_business_goals_admin
from src.catalog_items_reactive import render_catalog_items as render_catalog_items_reactive
from src.finishing_loader import activate_finishing_modules
from src.general_settings_persistence import persist_general_settings_if_changed
from src.home_dashboard_safe_loader import activate_home_dashboard_safe
from src.inventory_audit_unified_safe_loader import activate_inventory_unified_audit_safe
from src.inventory_consistency_rules_safe_loader import activate_inventory_consistency_rules_safe
from src.inventory_counts_safe_loader import activate_inventory_counts_safe
from src.inventory_dashboard_safe_loader import activate_inventory_dashboard_safe
from src.inventory_data_quality_safe_loader import activate_inventory_data_quality_safe
from src.inventory_enterprise_loader import activate_inventory_enterprise
from src.inventory_flow_consistency_safe_loader import activate_inventory_flow_consistency_safe
from src.inventory_health_history_readiness_safe_loader import activate_inventory_health_history_readiness_safe
from src.inventory_health_history_safe_loader import activate_inventory_health_history_safe
from src.inventory_health_summary_safe_loader import activate_inventory_health_summary_safe
from src.inventory_health_trend_safe_loader import activate_inventory_health_trend_safe
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
from src.purchases_overview_safe_loader import activate_purchases_overview_safe
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


# Desde la Fase 6B parte 12, initialize_database() ya incorpora y registra v15.
# Los módulos que restauran sesión o acceden a metas invocan la inicialización
# fundacional cuando corresponde; se elimina el bootstrap temporal duplicado.
restore_session_snapshot_on_startup()
activate_module_bootstrap()
activate_printer_asset_specs()
activate_print_cost_module()
activate_finishing_modules()
activate_inventory_enterprise()
activate_supply_chain_integration()
# Primera fase de Inicio: sustituye la bienvenida por un centro ejecutivo de
# solo lectura con indicadores, alertas, actividad y accesos rápidos.
activate_home_dashboard_safe()
# Fase 6B: registra el gestor persistente de metas. La navegación ya reserva
# "Metas del negocio" y el loader resuelve el usuario autenticado al renderizar.
activate_business_goals_admin()
# Primera fase de Compras: añade un resumen operativo de solo lectura con filtros,
# métricas y valores calculados sin modificar órdenes, recepciones ni existencias.
activate_purchases_overview_safe()
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
# Decimoquinta fase de Inventario: consolida calidad, hallazgos y prioridades en
# un resumen ejecutivo de salud, sin modificar ni valorar registros.
activate_inventory_health_summary_safe()
# Decimosexta fase de Inventario: permite guardar observaciones temporales dentro
# de la sesión para comparar tendencias sin escribir historial en la base de datos.
activate_inventory_health_trend_safe()
# Decimoséptima fase de Inventario: prepara y documenta la migración para un
# historial persistente, sin ejecutar SQL ni habilitar escrituras automáticas.
activate_inventory_health_history_readiness_safe()
# Decimoctava fase de Inventario: habilita guardado manual y lectura del historial
# solo cuando la tabla preparada ya existe, con responsable y confirmación expresa.
activate_inventory_health_history_safe()
# Vigesimosegunda fase de Inventario: consolida movimientos, reservas, conteos,
# cambios logísticos y mediciones de salud en una auditoría de solo lectura.
activate_inventory_unified_audit_safe()
# La vista reactiva se registra después de la integración para sustituir la
# versión basada en st.form, cuyos selectores no redibujaban los campos.
app_shell.FUNCTIONAL_MODULES["Catálogo de artículos"] = render_catalog_items_reactive
_activate_process_quotes_safely()

# Se ejecuta en cada rerun, pero solo escribe cuando la huella de Configuración
# General cambió. Así el botón "Guardar configuración" también persiste en la
# base de datos, sin exigir un segundo clic en la pantalla de Respaldos.
persist_general_settings_if_changed()
run_app()
