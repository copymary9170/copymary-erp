from src.app_shell_payments import run_app as base_run
from src.status_consistency import normalize_session_statuses

def run_app():
    normalize_session_statuses()
    base_run()
