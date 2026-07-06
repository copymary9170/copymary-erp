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

app_shell.FUNCTIONAL_MODULES["Centro de control"] = render_control_center_today
app_shell.FUNCTIONAL_MODULES["Auditoría de datos"] = render_data_audit_insights
app_shell.FUNCTIONAL_MODULES["Panel comercial"] = render_commercial_dashboard_intelligence
app_shell.FUNCTIONAL_MODULES["Panel financiero y cierres"] = render_financial_dashboard_plus
app_shell.FUNCTIONAL_MODULES["Clientes"] = render_clients_followup
app_shell.FUNCTIONAL_MODULES["Comprobantes"] = render_receipts_control
run_app()
