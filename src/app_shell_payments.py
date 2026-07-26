from src import app_shell
from src.app_shell_goals import run_app as _run_base_app
from src.accounts_payable_control import render_accounts_payable_control
from src.cash_closing_reopen import activate_closing_reopen_support, render_cash_closing_reopen
from src.catalog_maintenance_bulk import render_catalog_maintenance_bulk
from src.catalog_production_quality import render_catalog_production_quality
from src.commercial_reports_intelligence import render_commercial_reports_intelligence
from src.commission_history import render_commission_history
from src.commission_snapshots import activate_commission_snapshots
from src.deletion_protection import activate_deletion_protection
from src.financial_reconciliation import render_financial_reconciliation
from src.hr_labor_integration import activate_hr_labor_support, render_hr_labor_management
from src.inventory_plus import render_inventory_plus
from src.legal_compliance_integration import activate_legal_compliance, render_legal_compliance
from src.order_planning_capacity import render_order_planning_capacity
from src.payment_consistency import activate_payment_consistency
from src.payment_reversals import render_payment_reversals
from src.production_reversals_visible import render_production_reversals_visible as render_production_reversals
from src.purchases_control import render_purchases_control
from src.quotes_followup import render_quotes_followup
from src.restore_rollback import activate_restore_rollback, render_backup_with_rollback
from src.sales_orders_tracking import render_sales_orders_tracking
from src.suppliers_plus import render_suppliers_plus

activate_payment_consistency()
activate_deletion_protection()
activate_closing_reopen_support()
activate_restore_rollback()
activate_commission_snapshots()
activate_hr_labor_support()
activate_legal_compliance()
app_shell.FUNCTIONAL_MODULES['Reversos de pagos'] = render_payment_reversals
app_shell.FUNCTIONAL_MODULES['Conciliación financiera'] = render_financial_reconciliation
app_shell.FUNCTIONAL_MODULES['Reabrir cierre de caja'] = render_cash_closing_reopen
app_shell.FUNCTIONAL_MODULES['Historial de comisiones'] = render_commission_history
app_shell.FUNCTIONAL_MODULES['Respaldo general'] = render_backup_with_rollback
app_shell.FUNCTIONAL_MODULES['Cotizaciones'] = render_quotes_followup
app_shell.FUNCTIONAL_MODULES['Ventas y pedidos'] = render_sales_orders_tracking
app_shell.FUNCTIONAL_MODULES['Agenda de producción y entregas'] = render_order_planning_capacity
app_shell.FUNCTIONAL_MODULES['Reportes comerciales'] = render_commercial_reports_intelligence
app_shell.FUNCTIONAL_MODULES['Proveedores'] = render_suppliers_plus
app_shell.FUNCTIONAL_MODULES['Compras'] = render_purchases_control
app_shell.FUNCTIONAL_MODULES['Cuentas por pagar'] = render_accounts_payable_control
app_shell.FUNCTIONAL_MODULES['Catálogo y producción'] = render_catalog_production_quality
app_shell.FUNCTIONAL_MODULES['Mantenimiento del catálogo'] = render_catalog_maintenance_bulk
app_shell.FUNCTIONAL_MODULES['Reversos de producción'] = render_production_reversals
app_shell.FUNCTIONAL_MODULES['Inventario'] = render_inventory_plus
app_shell.FUNCTIONAL_MODULES['RRHH y nómina'] = render_hr_labor_management
app_shell.FUNCTIONAL_MODULES['Comprobantes'] = render_legal_compliance


def run_app():
    activate_commission_snapshots()
    activate_hr_labor_support()
    activate_legal_compliance()
    _run_base_app()
