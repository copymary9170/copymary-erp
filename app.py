"""Punto de entrada de CopyMary ERP."""
from src import app_shell
from src.app_shell_payments import run_app
from src.clients_followup import render_clients_followup
from src.commercial_dashboard_intelligence import render_commercial_dashboard_intelligence
from src.control_center_today import render_control_center_today
from src.data_audit_insights import render_data_audit_insights
from src.financial_dashboard_plus import render_financial_dashboard_plus
from src.receipts_control import render_receipts_control
from src import accounts_receivable_plus_loader
from src import suppliers_intelligence_loader
from src import production_reversals_visible
from src.inventory_planning import render_inventory_planning
from src.inventory_movements_enterprise import render_inventory_movements_enterprise
from src.stock_alerts_intelligence import render_stock_alerts_intelligence
from src.costing_control import render_costing_control
from src.price_adjustment_governance import render_price_adjustment_governance
from src.price_io_governance import render_price_io_governance

app_shell.FUNCTIONAL_MODULES["Centro de control"] = render_control_center_today
app_shell.FUNCTIONAL_MODULES["Auditoría de datos"] = render_data_audit_insights
app_shell.FUNCTIONAL_MODULES["Panel comercial"] = render_commercial_dashboard_intelligence
app_shell.FUNCTIONAL_MODULES["Panel financiero y cierres"] = render_financial_dashboard_plus
app_shell.FUNCTIONAL_MODULES["Clientes"] = render_clients_followup
app_shell.FUNCTIONAL_MODULES["Comprobantes"] = render_receipts_control
app_shell.FUNCTIONAL_MODULES["Inventario"] = render_inventory_planning
app_shell.FUNCTIONAL_MODULES["Movimientos de inventario"] = render_inventory_movements_enterprise
app_shell.FUNCTIONAL_MODULES["Alertas de inventario"] = render_stock_alerts_intelligence
app_shell.FUNCTIONAL_MODULES["Costeo"] = render_costing_control
app_shell.FUNCTIONAL_MODULES["Ajustar precios"] = render_price_adjustment_governance
app_shell.FUNCTIONAL_MODULES["Exportar precios"] = render_price_io_governance
run_app()
