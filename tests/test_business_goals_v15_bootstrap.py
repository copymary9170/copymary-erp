from src import business_goals_v15_bootstrap as bootstrap


def test_bootstrap_uses_declared_v15(monkeypatch):
    calls = []

    class FakeConnection:
        def execute(self, sql, params):
            calls.append((sql, params))

    class FakeContext:
        def __enter__(self):
            return FakeConnection()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(bootstrap.erp_database, "initialize_database", lambda: calls.append(("initialize", ())))
    monkeypatch.setattr(bootstrap, "migrate_business_goals_v15", lambda: calls.append(("migrate", ())))
    monkeypatch.setattr(bootstrap.erp_database, "connect", lambda: FakeContext())
    monkeypatch.setattr(bootstrap.erp_database, "SCHEMA_VERSION", 14)

    bootstrap.activate_business_goals_schema_v15()

    assert calls[0][0] == "initialize"
    assert calls[1][0] == "migrate"
    assert calls[2][1][0] == 15
    assert calls[2][1][1] == "persistent_business_goals"
    assert bootstrap.erp_database.SCHEMA_VERSION == 15


def test_bootstrap_never_reduces_schema_version(monkeypatch):
    class FakeConnection:
        def execute(self, sql, params):
            return None

    class FakeContext:
        def __enter__(self):
            return FakeConnection()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(bootstrap.erp_database, "initialize_database", lambda: None)
    monkeypatch.setattr(bootstrap, "migrate_business_goals_v15", lambda: None)
    monkeypatch.setattr(bootstrap.erp_database, "connect", lambda: FakeContext())
    monkeypatch.setattr(bootstrap.erp_database, "SCHEMA_VERSION", 20)

    bootstrap.activate_business_goals_schema_v15()

    assert bootstrap.erp_database.SCHEMA_VERSION == 20
