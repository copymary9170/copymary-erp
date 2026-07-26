"""Registro declarativo de KPI para Inicio fase 6A.

Las metas se mantienen en memoria de sesión y no modifican registros operativos.
Cada definición describe el origen, periodo y formato esperado del indicador.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KPIDefinition:
    key: str
    label: str
    source: str
    period: str
    target: float
    unit: str = "number"
    direction: str = "higher"
    description: str = ""


KPI_DEFINITIONS: tuple[KPIDefinition, ...] = (
    KPIDefinition(
        "monthly_sales",
        "Ventas mensuales",
        "sales_registry",
        "month",
        4000.0,
        "currency",
        "higher",
        "Facturación registrada durante el mes actual.",
    ),
    KPIDefinition(
        "monthly_collections",
        "Cobranza mensual",
        "cash_movements",
        "month",
        3000.0,
        "currency",
        "higher",
        "Ingresos clasificados como cobros durante el mes actual.",
    ),
    KPIDefinition(
        "quote_conversion",
        "Conversión de cotizaciones",
        "quotes_registry",
        "month",
        35.0,
        "percent",
        "higher",
        "Porcentaje de cotizaciones aceptadas o convertidas.",
    ),
    KPIDefinition(
        "on_time_delivery",
        "Entregas a tiempo",
        "sales_registry",
        "month",
        90.0,
        "percent",
        "higher",
        "Pedidos entregados dentro o antes de la fecha prevista.",
    ),
    KPIDefinition(
        "healthy_inventory",
        "Inventario saludable",
        "inventory_registry",
        "current",
        85.0,
        "percent",
        "higher",
        "Artículos activos por encima del mínimo y con disponibilidad.",
    ),
    KPIDefinition(
        "overdue_receivables_limit",
        "Límite de cartera vencida",
        "receivables_registry",
        "current",
        500.0,
        "currency",
        "lower",
        "Saldo vencido máximo tolerado.",
    ),
)


def definitions_by_key() -> dict[str, KPIDefinition]:
    return {definition.key: definition for definition in KPI_DEFINITIONS}
