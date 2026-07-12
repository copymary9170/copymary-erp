"""Pruebas de venta rápida de mostrador (`src/quick_sale.py`)."""

from __future__ import annotations

from src import quick_sale


# ---------------------------------------------------------------------------
# Cálculo puro
# ---------------------------------------------------------------------------

def test_line_total_multiplies_quantity_by_price():
    assert quick_sale.line_total(quantity=5, unit_price=0.20, discount=0.0) == 1.0


def test_line_total_subtracts_discount():
    assert quick_sale.line_total(quantity=10, unit_price=0.20, discount=0.50) == 1.50


def test_line_total_never_negative():
    """Un descuento mayor que el subtotal no debe generar un cobro negativo."""
    assert quick_sale.line_total(quantity=1, unit_price=100.0, discount=200.0) == 0.0


def test_line_total_with_zero_quantity_is_zero():
    assert quick_sale.line_total(quantity=0, unit_price=100.0, discount=0.0) == 0.0


# ---------------------------------------------------------------------------
# Registro de cliente ocasional
# ---------------------------------------------------------------------------

def test_find_walk_in_client_returns_existing():
    clients = [{"client_id": "ABC", "name": quick_sale.WALK_IN_CLIENT_NAME}]
    assert quick_sale.find_walk_in_client(clients) == clients[0]


def test_find_walk_in_client_none_when_missing():
    clients = [{"client_id": "X", "name": "Otro"}]
    assert quick_sale.find_walk_in_client(clients) is None


# ---------------------------------------------------------------------------
# Compatibilidad de esquema con commercial.py
# ---------------------------------------------------------------------------

# Estos campos son los mismos que crea render_sales() en commercial.py — si
# faltaran, los módulos existentes (Estado de Resultados, flujo de caja,
# comisiones) no verían las ventas de mostrador. Es el contrato de
# integración de este módulo, así que se prueba explícitamente.
SALE_REQUIRED_FIELDS = {
    "sale_id", "created_at_utc", "client_id", "description",
    "quantity", "unit_price", "discount", "total", "estimated_cost",
    "payment_status", "order_status", "payment_method", "notes",
    "cash_registered",
}

CASH_REQUIRED_FIELDS = {
    "movement_id", "created_at_utc", "movement_type", "category",
    "amount", "payment_method", "reference", "notes",
}


def test_build_sale_record_has_all_fields_commercial_expects():
    sale = quick_sale.build_sale_record("CLI-1", "Fotocopia", 5, 0.20, 0.0, "Efectivo")
    assert set(sale.keys()) >= SALE_REQUIRED_FIELDS


def test_build_sale_record_is_always_paid_and_delivered():
    """Una venta de mostrador se cobra y se entrega en el mismo instante."""
    sale = quick_sale.build_sale_record("CLI-1", "Fotocopia", 5, 0.20, 0.0, "Efectivo")
    assert sale["payment_status"] == "Pagado"
    assert sale["order_status"] == "Entregado"
    assert sale["cash_registered"] is True


def test_build_sale_record_total_matches_line_total():
    sale = quick_sale.build_sale_record("CLI-1", "Fotocopia", 10, 0.05, 0.10, "Efectivo")
    assert sale["total"] == quick_sale.line_total(10, 0.05, 0.10)


def test_build_cash_movement_has_all_fields_reports_expect():
    sale = quick_sale.build_sale_record("CLI-1", "Fotocopia", 5, 0.20, 0.0, "Efectivo")
    mvmt = quick_sale.build_cash_movement_record(sale)
    assert set(mvmt.keys()) >= CASH_REQUIRED_FIELDS


def test_cash_movement_amount_matches_sale_total_and_references_sale():
    sale = quick_sale.build_sale_record("CLI-1", "Fotocopia", 5, 0.20, 0.0, "Efectivo")
    mvmt = quick_sale.build_cash_movement_record(sale)
    assert mvmt["amount"] == sale["total"]
    assert mvmt["reference"] == sale["sale_id"]
    assert mvmt["movement_type"] == "Ingreso"


# ---------------------------------------------------------------------------
# Tarifario (base de datos)
# ---------------------------------------------------------------------------

def test_seed_default_services_creates_typical_stationery_catalog(isolated_database):
    quick_sale.seed_default_services_if_empty()
    services = quick_sale.list_services()
    names = {s["name"] for s in services}
    # Los servicios más típicos de una papelería/copiado no pueden faltar.
    assert "Fotocopia B/N" in names
    assert "Fotocopia color" in names
    assert "Impresión color" in names


def test_seed_default_services_is_idempotent(isolated_database):
    """No debe duplicar el tarifario si se llama dos veces."""
    quick_sale.seed_default_services_if_empty()
    first_count = len(quick_sale.list_services())
    quick_sale.seed_default_services_if_empty()
    assert len(quick_sale.list_services()) == first_count


def test_seed_does_not_overwrite_edited_prices(isolated_database):
    """Si ya existe cualquier servicio, seed no toca nada — respeta precios editados."""
    quick_sale.create_service("Servicio manual", "Otro", 999.0, "por unidad")
    quick_sale.seed_default_services_if_empty()
    services = quick_sale.list_services()
    assert len(services) == 1
    assert services[0]["name"] == "Servicio manual"


def test_create_service_persists_all_fields(isolated_database):
    quick_sale.create_service("Escaneo doble faz", "Escaneo", 0.15, "por página")
    services = quick_sale.list_services()
    assert services[0]["name"] == "Escaneo doble faz"
    assert services[0]["category"] == "Escaneo"
    assert services[0]["unit_price"] == 0.15
    assert services[0]["unit_label"] == "por página"


def test_set_service_active_toggles_visibility(isolated_database):
    service_id = quick_sale.create_service("Servicio X", "Otro", 1.0, "por unidad")
    assert len(quick_sale.list_services()) == 1

    quick_sale.set_service_active(service_id, active=False)
    assert quick_sale.list_services() == []
    assert len(quick_sale.list_services(active_only=False)) == 1


# ---------------------------------------------------------------------------
# Integración con reportes existentes
# ---------------------------------------------------------------------------

def test_quick_sale_appears_in_income_statement_revenue():
    """La razón entera de este módulo: las ventas de mostrador deben aparecer
    en el Estado de Resultados sin tocar ese módulo."""
    from datetime import date
    from src import income_statement

    sale = quick_sale.build_sale_record("CLI-1", "Fotocopia", 5, 0.20, 0.0, "Efectivo")
    month = date.today().strftime("%Y-%m")

    assert income_statement.revenue_for_month([sale], month) == 1.0


def test_quick_sale_cash_movement_appears_in_cash_position():
    """Igual con el flujo de caja: la venta debe reflejarse en la posición
    de caja actual sin tocar cash_flow_forecast.py."""
    from src import cash_flow_forecast

    sale = quick_sale.build_sale_record("CLI-1", "Fotocopia", 5, 0.20, 0.0, "Efectivo")
    mvmt = quick_sale.build_cash_movement_record(sale)

    assert cash_flow_forecast.current_cash_position([mvmt]) == 1.0
