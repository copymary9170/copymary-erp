from __future__ import annotations

import pytest

from src.business_goals_kpi_contract import (
    expected_target_value_type,
    validate_kpi_target,
)
from src.home_kpi_registry import definitions_by_key


def test_registry_units_map_to_persistent_value_types():
    definitions = definitions_by_key()
    assert expected_target_value_type(definitions["monthly_sales"]) == "currency"
    assert expected_target_value_type(definitions["quote_conversion"]) == "percentage"


def test_unknown_kpi_is_rejected():
    with pytest.raises(ValueError, match="Código KPI desconocido"):
        validate_kpi_target("invented_kpi", 10, "number")


def test_wrong_value_type_is_rejected():
    with pytest.raises(ValueError, match="requiere target_value_type=currency"):
        validate_kpi_target("monthly_sales", 1000, "number")


def test_percentage_range_is_enforced():
    with pytest.raises(ValueError, match="no puede superar 100"):
        validate_kpi_target("quote_conversion", 120, "percentage")


def test_valid_target_is_normalized():
    result = validate_kpi_target("monthly_sales", "1250.50", "currency")
    assert result.value == 1250.50
    assert result.value_type == "currency"
