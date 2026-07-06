"""Punto de entrada de CopyMary ERP."""
from src import app_shell
from src.app_shell_payments import run_app
from src.commercial_dashboard_insights import render_commercial_dashboard_insights
from src.control_center_today import render_control_center_today
from src.data_audit_insights import render_data_audit_insights
from src.financial_dashboard_plus import render_financial_dashboard_plus

app_shell.FUNCTIONAL_MODULES["Centro de control"] = render_control_center_today
app_shell.FUNCTIONAL_MODULES["Auditoría de datos"] = render_data_audit_insights
app_shell.FUNCTIONAL_MODULES["Panel comercial"] = render_commercial_dashboard_insights
app_shell.FUNCTIONAL_MODULES["Panel financiero y cierres"] = render_financial_dashboard_plus
run_app()
