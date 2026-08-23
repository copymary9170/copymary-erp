from types import SimpleNamespace

from src import rates_master


def test_sync_only_publishes_official_rates(monkeypatch):
    calls = []

    def fake_record(source_currency, target_currency, rate, *, rate_date):
        calls.append((source_currency, target_currency, rate, rate_date))
        return True

    monkeypatch.setattr(rates_master, "_record_if_changed", fake_record)
    settings = SimpleNamespace(
        bcv_rate=779.95,
        bcv_eur_rate=911.22,
        binance_rate=917.95,
        kontigo_in_rate=920.0,
        kontigo_out_rate=930.0,
        rates_updated_at="2026-08-23T22:15:00+00:00",
    )

    assert rates_master.sync_official_rates_from_settings(settings) == 2
    assert calls == [
        ("USD", "VES", 779.95, "2026-08-23"),
        ("EUR", "VES", 911.22, "2026-08-23"),
    ]


def test_sync_ignores_zero_rates(monkeypatch):
    calls = []

    def fake_record(source_currency, target_currency, rate, *, rate_date):
        calls.append(rate)
        return rate > 0

    monkeypatch.setattr(rates_master, "_record_if_changed", fake_record)
    settings = SimpleNamespace(bcv_rate=0.0, bcv_eur_rate=0.0, rates_updated_at="")

    assert rates_master.sync_official_rates_from_settings(settings) == 0
    assert calls == [0.0, 0.0]
