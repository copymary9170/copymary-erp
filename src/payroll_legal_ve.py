"""Estimaciones legales de nómina para Venezuela (LOTTT) — CopyMary ERP.

ADVERTENCIA IMPORTANTE — LEE ANTES DE USAR ESTE MÓDULO:

Este módulo implementa las FÓRMULAS ESTRUCTURALES de la Ley Orgánica del
Trabajo, los Trabajadores y las Trabajadoras (LOTTT, Venezuela, 2012):
prestaciones sociales (Art. 142), utilidades (Art. 131-133), vacaciones y
bono vacacional (Art. 190 y 192), e IVSS/FAOV/RPE. El NÚMERO DE DÍAS que
exige la ley (15 días por trimestre, 2 días adicionales por año, 15 días de
utilidades, etc.) está fijado en el código porque es texto legal estable.

Lo que NO está fijado — y a propósito — son los PARÁMETROS que cambian por
decreto o Gaceta Oficial: el salario mínimo vigente, los topes de cotización
de IVSS/FAOV/RPE (normalmente múltiplos del salario mínimo), y la tasa
patronal de IVSS (varía 9%-11% según la clasificación de riesgo de la
empresa ante el INPSASEL). Este módulo NO tiene forma de saber cuál es el
valor vigente HOY — Venezuela actualiza estas cifras con frecuencia y en
períodos de inflación alta pueden cambiar en semanas. Cada cálculo recibe
esos valores como parámetro explícito; es responsabilidad de quien usa el
ERP mantenerlos al día con la Gaceta Oficial vigente.

Esto es una HERRAMIENTA DE ESTIMACIÓN para planeación interna (cuánto se
está acumulando en prestaciones, cuánto tocaría de utilidades este año),
NO un cálculo fiscal/legal certificado y NO se aplica automáticamente a los
pagos reales de `payroll.py`. Antes de usar estos montos para liquidar a un
empleado, pagar prestaciones, o declarar aportes patronales ante el
IVSS/BANAVIH/INCES, VALÍDALOS con un contador o abogado laboral. Un error
aquí puede significar pagarle de menos o de más a una persona real.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Prestaciones sociales (Art. 142 LOTTT)
# ---------------------------------------------------------------------------

QUARTERLY_GUARANTEE_DAYS = 15  # Art. 142 lit. a: 15 días de salario por trimestre trabajado.
ADDITIONAL_DAYS_PER_YEAR = 2   # Art. 142 lit. b: 2 días adicionales por año, a partir del 2do año.
ADDITIONAL_DAYS_CAP = 30       # Art. 142 lit. b: tope de días adicionales acumulados por año.
RETROACTIVE_DAYS_PER_YEAR = 30  # Art. 142 lit. c: piso de comparación, 30 días por año con el último salario.


def quarterly_guarantee_amount(quarterly_daily_salary: float) -> float:
    """Depósito de garantía de un trimestre: 15 días del salario diario
    vigente en ESE trimestre (Art. 142 lit. a LOTTT). Se deposita cada
    trimestre trabajado, sin esperar a que termine la relación laboral."""
    return QUARTERLY_GUARANTEE_DAYS * max(quarterly_daily_salary, 0.0)


def additional_severance_days_for_year(years_of_service: int) -> int:
    """Días adicionales de garantía que corresponden AL año `years_of_service`
    de servicio (no acumulado): 0 en el primer año, 2 en el segundo, 4 en el
    tercero... hasta un tope de 30 días en un mismo año (Art. 142 lit. b
    LOTTT). Súmalos año por año para obtener el total adicional acumulado."""
    if years_of_service < 2:
        return 0
    return min(ADDITIONAL_DAYS_PER_YEAR * (years_of_service - 1), ADDITIONAL_DAYS_CAP)


def additional_severance_amount_for_year(years_of_service: int, annual_daily_salary: float) -> float:
    """Monto en dinero de los días adicionales de un año específico, con el
    salario diario vigente ESE año (cada año se calcula con su propio
    salario, no con el último)."""
    return additional_severance_days_for_year(years_of_service) * max(annual_daily_salary, 0.0)


def retroactive_severance_amount(years_of_service: float, last_daily_salary: float) -> float:
    """Cálculo de comparación (Art. 142 lit. c LOTTT): 30 días de salario
    integral por año de servicio (o fracción), con el ÚLTIMO salario. Es el
    'piso' que se compara contra lo depositado trimestralmente al terminar
    la relación laboral."""
    return RETROACTIVE_DAYS_PER_YEAR * max(years_of_service, 0.0) * max(last_daily_salary, 0.0)


def final_severance_payment(accumulated_guarantee: float, retroactive_calculation: float) -> float:
    """Al terminar la relación laboral, el trabajador recibe el MAYOR entre
    lo acumulado por depósitos trimestrales + adicionales, y el cálculo
    retroactivo de 30 días/año con el último salario (Art. 142 lit. c
    LOTTT — 'lo que sea más favorable al trabajador')."""
    return max(accumulated_guarantee, retroactive_calculation)


def accumulated_guarantee_estimate(years_of_service: float, current_daily_salary: float) -> float:
    """Estimación SIMPLIFICADA de lo acumulado por garantía trimestral + días
    adicionales, usando el salario diario ACTUAL para TODA la antigüedad.

    El cálculo legal real usa el salario vigente de CADA trimestre/año (que
    puede haber sido distinto en el pasado); este ERP no lleva ese desglose
    histórico exacto por trimestre, así que esta función aproxima con el
    salario de hoy. Es una herramienta de planeación, no el monto exacto que
    correspondería liquidar — para eso hace falta el historial real de
    salarios de cada período, revisado por un contador."""
    quarters_completed = int(max(years_of_service, 0.0) * 4)
    total_guarantee = quarters_completed * quarterly_guarantee_amount(current_daily_salary)
    full_years_completed = int(max(years_of_service, 0.0))
    total_additional = sum(
        additional_severance_amount_for_year(year, current_daily_salary)
        for year in range(2, full_years_completed + 1)
    )
    return total_guarantee + total_additional


def severance_estimate(years_of_service: float, current_daily_salary: float) -> dict:
    """Resumen de la estimación de prestaciones sociales: lo acumulado
    (simplificado), el piso retroactivo, y el mayor de los dos — listo para
    mostrar en pantalla. Ver `accumulated_guarantee_estimate` para las
    limitaciones de la simplificación."""
    accumulated = accumulated_guarantee_estimate(years_of_service, current_daily_salary)
    retroactive = retroactive_severance_amount(years_of_service, current_daily_salary)
    return {
        "accumulated_guarantee": accumulated,
        "retroactive_calculation": retroactive,
        "final_payment": final_severance_payment(accumulated, retroactive),
    }


# ---------------------------------------------------------------------------
# Utilidades / aguinaldos (Art. 131-133 LOTTT)
# ---------------------------------------------------------------------------

MINIMUM_UTILITIES_DAYS = 15  # Art. 131: mínimo legal, sin importar si la empresa tuvo ganancias.
MAXIMUM_UTILITIES_DAYS = 120  # Art. 131: tope legal (4 meses) cuando las ganancias de la empresa lo permiten.


def utilities_days(requested_days: float | None = None) -> float:
    """Días de utilidades a pagar, siempre dentro del piso legal (15) y el
    techo legal (120 = 4 meses). Si no se indica un valor propio de la
    empresa, aplica el mínimo legal."""
    if requested_days is None:
        return float(MINIMUM_UTILITIES_DAYS)
    return min(max(requested_days, MINIMUM_UTILITIES_DAYS), MAXIMUM_UTILITIES_DAYS)


def utilities_amount(daily_salary: float, days: float = MINIMUM_UTILITIES_DAYS, months_worked: int = 12) -> float:
    """Monto de utilidades, prorrateado si el empleado no trabajó el año
    calendario completo (p. ej. alguien contratado a mitad de año)."""
    months = max(min(months_worked, 12), 0)
    return max(daily_salary, 0.0) * utilities_days(days) * (months / 12.0)


# ---------------------------------------------------------------------------
# Vacaciones y bono vacacional (Art. 190 y 192 LOTTT)
# ---------------------------------------------------------------------------

BASE_VACATION_DAYS = 15   # Días del primer año de servicio.
ADDITIONAL_VACATION_DAY_PER_YEAR = 1  # +1 día por cada año adicional.
MAX_ADDITIONAL_VACATION_DAYS = 15     # Tope de días adicionales (total máximo: 30).


def _fifteen_plus_one_per_year(years_of_service: int) -> int:
    additional = min(max(years_of_service - 1, 0), MAX_ADDITIONAL_VACATION_DAYS)
    return BASE_VACATION_DAYS + additional


def vacation_days(years_of_service: int) -> int:
    """Días de disfrute de vacaciones: 15 el primer año +1 por cada año
    adicional, tope 30 en total (Art. 190 LOTTT)."""
    return _fifteen_plus_one_per_year(years_of_service)


def vacation_bonus_days(years_of_service: int) -> int:
    """Días de bono vacacional: misma fórmula que los días de disfrute — 15
    el primer año +1 por cada año adicional, tope 30 (Art. 192 LOTTT). Es un
    concepto DISTINTO de las utilidades/aguinaldos: se paga junto con el
    disfrute de vacaciones, no a fin de año."""
    return _fifteen_plus_one_per_year(years_of_service)


def vacation_bonus_amount(daily_salary: float, years_of_service: int) -> float:
    return max(daily_salary, 0.0) * vacation_bonus_days(years_of_service)


# ---------------------------------------------------------------------------
# IVSS / FAOV / RPE — aportes patronales y del trabajador
#
# Los PORCENTAJES y TOPES de estas tres contribuciones se fijan por decreto o
# Gaceta Oficial y cambian con el tiempo. Ninguno se hardcodea como "la
# verdad": todos se reciben como parámetro, para que quien usa el ERP los
# mantenga al día. Los valores por defecto de FAOV y RPE son los que fijan
# sus leyes respectivas (más estables que el tope salarial), pero incluso
# esos deben confirmarse antes de declarar aportes reales.
# ---------------------------------------------------------------------------

def contribution_base(salary: float, cap: float | None = None) -> float:
    """Base de cotización: el salario, topado si se indica un tope (el tope
    de IVSS/FAOV/RPE se fija por decreto, normalmente como múltiplo del
    salario mínimo vigente)."""
    base = max(salary, 0.0)
    if cap is not None:
        return min(base, max(cap, 0.0))
    return base


def ivss_contribution(salary: float, employer_rate_percent: float, employee_rate_percent: float, cap: float | None = None) -> tuple[float, float]:
    """(aporte_patronal, aporte_trabajador) del IVSS. La tasa patronal típica
    va de 9% a 11% según la clasificación de riesgo de la empresa ante el
    INPSASEL, y la del trabajador ronda 4% — pero ambas deben confirmarse:
    no se asume ningún valor por defecto porque depende de cada empresa."""
    base = contribution_base(salary, cap)
    return base * employer_rate_percent / 100.0, base * employee_rate_percent / 100.0


FAOV_EMPLOYER_RATE_PERCENT = 2.0
FAOV_EMPLOYEE_RATE_PERCENT = 1.0


def faov_contribution(
    integral_salary: float,
    employer_rate_percent: float = FAOV_EMPLOYER_RATE_PERCENT,
    employee_rate_percent: float = FAOV_EMPLOYEE_RATE_PERCENT,
) -> tuple[float, float]:
    """(aporte_patronal, aporte_trabajador) del FAOV (Fondo de Ahorro
    Obligatorio para la Vivienda — Ley del Régimen Prestacional de Vivienda y
    Hábitat): 2% patronal / 1% trabajador sobre el salario integral. Estas
    son las tasas de referencia de la ley, pero confírmalas antes de usarlas
    para una declaración real — no hay tope de cotización conocido fijo."""
    base = max(integral_salary, 0.0)
    return base * employer_rate_percent / 100.0, base * employee_rate_percent / 100.0


RPE_EMPLOYER_RATE_PERCENT = 2.0
RPE_EMPLOYEE_RATE_PERCENT = 0.5


def rpe_contribution(
    salary: float,
    employer_rate_percent: float = RPE_EMPLOYER_RATE_PERCENT,
    employee_rate_percent: float = RPE_EMPLOYEE_RATE_PERCENT,
    cap: float | None = None,
) -> tuple[float, float]:
    """(aporte_patronal, aporte_trabajador) del Régimen Prestacional de
    Empleo (paro forzoso): 2% patronal / 0.5% trabajador, sobre el salario
    topado. Tasas de referencia de la ley — confírmalas antes de declarar."""
    base = contribution_base(salary, cap)
    return base * employer_rate_percent / 100.0, base * employee_rate_percent / 100.0
