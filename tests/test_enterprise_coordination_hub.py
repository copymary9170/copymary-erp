from datetime import date

from src.enterprise_coordination_hub import document_notifications, task_notifications


def test_task_notifications_marks_overdue_and_upcoming():
    today = date(2026, 8, 23)
    rows = [
        {"title": "Vencida", "due_date": "2026-08-22", "status": "Pendiente", "reminder_days": 1},
        {"title": "Próxima", "due_date": "2026-08-24", "status": "Pendiente", "reminder_days": 2},
        {"title": "Hecha", "due_date": "2026-08-20", "status": "Hecha", "reminder_days": 5},
    ]
    notices = task_notifications(rows, today)
    assert [x["kind"] for x in notices] == ["Tarea vencida", "Tarea próxima"]


def test_document_notifications_respects_warning_window():
    today = date(2026, 8, 23)
    rows = [
        {"name": "RIF", "expiry_date": "2026-08-30", "reminder_days": 10},
        {"name": "Garantía", "expiry_date": "2027-08-30", "reminder_days": 30},
    ]
    notices = document_notifications(rows, today)
    assert len(notices) == 1
    assert notices[0]["title"] == "RIF"
