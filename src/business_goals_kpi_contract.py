"""Contrato entre las metas persistentes y el registro declarativo de KPI.

Centraliza la validación de códigos, tipos de objetivo y límites para evitar que
la base acepte metas incompatibles con los calculadores del dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.home_kpi_registry import KPIDefinition, definitions_by_key


@dataclass(frozen=True)
class ValidatedGoalTarget:
    definition: KPIDefinition
    value: float
    value_type: str


_UNIT_TO_VALUE_TYPE = {
    "currency": "currency",
    "percent": "percentage",
    "number": "number",
}


def expected_target_value_type(definition: KPIDefinition) -> str:
    return _UNIT_TO_VALUE_TYPE.get(definition.unit, "number")


def validate_kpi_target(kpi_code: str, target_value: float, target_value_type: str) -> ValidatedGoalTarget:
    definitions = definitions_by_key()
    code = str(kpi_code or "").strip()
    if code not in definitions:
        raise ValueError(f"Código KPI desconocido: {code or '(vacío)' }.")

    definition = definitions[code]
    expected_type = expected_target_value_type(definition)
    supplied_type = str(target_value_type or "").strip()
    if supplied_type != expected_type:
        raise ValueError(
            f"El KPI {code} requiere target_value_type={expected_type}; "
            f"se recibió {supplied_type or '(vacío)'}.")

    try:
        value = float(target_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("target_value debe ser numérico.") from exc

    if value < 0:
        raise ValueError("target_value no puede ser negativo.")
    if expected_type == "percentage" and value > 100:
        raise ValueError("Una meta porcentual no puede superar 100.")

    return ValidatedGoalTarget(definition=definition, value=value, value_type=expected_type)
