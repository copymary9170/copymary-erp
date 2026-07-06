from src import app_shell
from src.app_shell_goals import run_app as _run_base_app
from src.cash_closing_reopen import activate_closing_reopen_support, render_cash_closing_reopen
from src.commission_history import render_commission_history
from src.commission_snapshots import activate_commission_snapshots
from src.deletion_protection import activate_deletion_protection
from src.financial_reconciliation import render_financial_reconciliation
from src.payment_consistency import activate_payment_consistency
from src.payment_reversals import render_payment_reversals
from src.quotes_followup import render_quotes_followup
from src.restore_rollback import activate_restore_rollback, render_backup_with_rollback
from src.sales_orders_plus import render_sales_orders_plus

activate_payment_consistency()
activate_deletion_protection()
activate_closing_reopen_support()
activate_restore_rollback()
activate_commission_snapshots()
app_shell.FUNCTIONAL_MODULES['Reversos de pagos'] = render_payment_reversals
app_shell.FUNCTIONAL_MODULES['Conciliación financiera'] = render_financial_reconciliation
app_shell.FUNCTIONAL_MODULES['Reabrir cierre de caja'] = render_cash_closing_reopen
app_shell.FUNCTIONAL_MODULES['Historial de comisiones'] = render_commission_history
app_shell.FUNCTIONAL_MODULES['Respaldo general'] = render_backup_with_rollback
app_shell.FUNCTIONAL_MODULES['Cotizaciones'] = render_quotes_followup
app_shell.FUNCTIONAL_MODULES['Ventas y pedidos'] = render_sales_orders_plus
app_shell.NAVIGATION_GROUPS['Administración'] = (
    'Caja', 'Conciliación financiera', 'Reabrir cierre de caja',
    'Gastos y presupuesto', 'Equipo y comisiones', 'Historial de comisiones',
    'Reversos de pagos', 'Anulaciones y ajustes', 'Activos',
    'Respaldar activos', 'Configuración General', 'Respaldo general',
)

def run_app():
    activate_commission_snapshots()
    _run_base_app()
