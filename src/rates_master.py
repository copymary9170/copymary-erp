"""Puente entre Configuración General y el histórico usado por Costeo.

Configuración General es la única fuente editable de tasas. Este módulo conserva
la tabla histórica ``exchange_rates`` porque Costeo por procesos congela allí la
tasa oficial usada en cada trabajo y no debe perder trazabilidad histórica.
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

from src.erp_database import connect, initialize_database
from src.session_utils import now_iso

MASTER_SOURCE = "Configuración General · BCV"


def _latest_pair(source_currency: str, target_currency: str) -> dict | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM exchange_rates WHERE source_currency = ? AND target_currency = ? "
            "ORDER BY rate_date DESC, created_at_utc DESC LIMIT 1",
            (source_currency, target_currency),
        ).fetchone()
    return dict(row) if row else None


def _record_if_changed(source_currency: str, target_currency: str, rate: float, *, rate_date: str) -> bool:
    value = float(rate or 0)
    if value <= 0:
        return False
    latest = _latest_pair(source_currency, target_currency)
    if latest and float(latest.get("rate") or 0) == value and str(latest.get("rate_date") or "") == rate_date:
        return False
    initialize_database()
    with connect() as conn:
        conn.execute(
            "INSERT INTO exchange_rates(rate_id, rate_date, source_currency, target_currency, rate, source_name, notes, created_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"RATE-{uuid4().hex[:8].upper()}",
                rate_date,
                source_currency,
                target_currency,
                value,
                MASTER_SOURCE,
                "Sincronizada automáticamente desde Configuración General; registro histórico para Costeo.",
                now_iso(),
            ),
        )
    return True


def sync_official_rates_from_settings(settings: object) -> int:
    """Sincroniza solo las tasas oficiales que Costeo necesita por par de moneda.

    Binance y Kontigo permanecen en Configuración General y en ``rates_history``.
    No se insertan en ``exchange_rates`` porque esa tabla identifica por par de
    moneda y Costeo espera que USD→VES represente la tasa oficial, no una tasa
    paralela que pudiera reemplazarla accidentalmente.
    """
    updated_at = str(getattr(settings, "rates_updated_at", "") or "")
    rate_date = updated_at[:10] if len(updated_at) >= 10 else date.today().isoformat()
    changed = 0
    changed += int(_record_if_changed("USD", "VES", float(getattr(settings, "bcv_rate", 0.0) or 0), rate_date=rate_date))
    changed += int(_record_if_changed("EUR", "VES", float(getattr(settings, "bcv_eur_rate", 0.0) or 0), rate_date=rate_date))
    return changed
