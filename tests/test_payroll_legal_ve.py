"""Pruebas de las estimaciones legales de nómina para Venezuela (LOTTT)
(`src/payroll_legal_ve.py`).

Dado que un error aquí puede significar pagarle de menos o de más a una
persona real, estas pruebas cubren las fórmulas exactas del texto legal
(número de días) y los casos borde (año 1 sin adicional, tope de 30 días,
salarios en 0, prorrateo), no solo el camino feliz.
"""

from __future__ import annotations

from src import payroll_legal_ve as legal


# ---------------------------------------------------------------------------
# Prestaciones sociales — garantía trimestral (Art. 142 lit. a)
# ---------------------------------------------------------------------------

def test_quarterly_guarantee_amount_is_15_days_of_daily_salary():
    # Salario diario 20 => 15 * 20 = 300 por trimestre.
    assert legal.quarterly_guarantee_amount(20.0) == 300.0


def test_quarterly_guarantee_amount_zero_salary_is_zero():
    assert legal.quarterly_guarantee_amount(0.0) == 0.0


def test_quarterly_guarantee_amount_never_negative_even_with_bad_input():
    assert legal.quarterly_guarantee_amount(-10.0) == 0.0


# ---------------------------------------------------------------------------
# Prestaciones sociales — días adicionales por año (Art. 142 lit. b)
# ---------------------------------------------------------------------------

def test_additional_severance_days_zero_in_first_year():
    """El primer año de servicio no genera días adicionales (empiezan en el
    segundo año, Art. 142 lit. b)."""
    assert legal.additional_severance_days_for_year(1) == 0


def test_additional_severance_days_second_year_is_two():
    assert legal.additional_severance_days_for_year(2) == 2


def test_additional_severance_days_third_year_is_four():
    assert legal.additional_severance_days_for_year(3) == 4


def test_additional_severance_days_grows_two_per_year():
    assert legal.additional_severance_days_for_year(5) == 8  # 2*(5-1)
    assert legal.additional_severance_days_for_year(10) == 18  # 2*(10-1)


def test_additional_severance_days_caps_at_thirty():
    """A partir del año 16 (2*15=30), el tope de 30 días no debe superarse."""
    assert legal.additional_severance_days_for_year(16) == 30
    assert legal.additional_severance_days_for_year(20) == 30
    assert legal.additional_severance_days_for_year(50) == 30


def test_additional_severance_amount_multiplies_days_by_salary():
    # Año 3 => 4 días adicionales * salario diario 25 = 100.
    assert legal.additional_severance_amount_for_year(3, 25.0) == 100.0


def test_additional_severance_amount_zero_in_first_year_regardless_of_salary():
    assert legal.additional_severance_amount_for_year(1, 100.0) == 0.0


# ---------------------------------------------------------------------------
# Prestaciones sociales — cálculo retroactivo y comparación (Art. 142 lit. c)
# ---------------------------------------------------------------------------

def test_retroactive_severance_amount_is_30_days_per_year_with_last_salary():
    # 5 años * 30 días * salario diario 20 = 3000.
    assert legal.retroactive_severance_amount(5.0, 20.0) == 3000.0


def test_retroactive_severance_amount_handles_fractional_years():
    # 2.5 años * 30 * 10 = 750.
    assert legal.retroactive_severance_amount(2.5, 10.0) == 750.0


def test_retroactive_severance_amount_never_negative():
    assert legal.retroactive_severance_amount(-1.0, 10.0) == 0.0


def test_final_severance_payment_picks_the_greater_amount():
    """El trabajador recibe el MAYOR de los dos cálculos — el corazón de la
    garantía legal del Art. 142 lit. c."""
    assert legal.final_severance_payment(accumulated_guarantee=1000.0, retroactive_calculation=1500.0) == 1500.0
    assert legal.final_severance_payment(accumulated_guarantee=2000.0, retroactive_calculation=1500.0) == 2000.0


def test_final_severance_payment_equal_amounts_returns_that_amount():
    assert legal.final_severance_payment(1000.0, 1000.0) == 1000.0


# ---------------------------------------------------------------------------
# accumulated_guarantee_estimate / severance_estimate (estimación simplificada)
# ---------------------------------------------------------------------------

def test_accumulated_guarantee_estimate_first_year_is_four_quarters_no_additional():
    # 1 año = 4 trimestres * 15 días * salario diario 10 = 600, sin adicionales.
    assert legal.accumulated_guarantee_estimate(1.0, 10.0) == 600.0


def test_accumulated_guarantee_estimate_second_year_adds_two_days():
    # 2 años = 8 trimestres * 15 * 10 = 1200, + año 2 adicional (2 días * 10) = 20 => 1220.
    assert legal.accumulated_guarantee_estimate(2.0, 10.0) == 1220.0


def test_accumulated_guarantee_estimate_partial_year_only_counts_full_quarters():
    # 1.4 años = 5 trimestres completos (int(1.4*4)=5) * 15 * 10 = 750; sin año 2 completo aún.
    assert legal.accumulated_guarantee_estimate(1.4, 10.0) == 750.0


def test_accumulated_guarantee_estimate_zero_years_is_zero():
    assert legal.accumulated_guarantee_estimate(0.0, 10.0) == 0.0


def test_severance_estimate_returns_all_three_figures():
    result = legal.severance_estimate(5.0, 20.0)
    assert set(result) == {"accumulated_guarantee", "retroactive_calculation", "final_payment"}
    assert result["retroactive_calculation"] == legal.retroactive_severance_amount(5.0, 20.0)
    assert result["final_payment"] == max(result["accumulated_guarantee"], result["retroactive_calculation"])


def test_severance_estimate_final_payment_is_never_less_than_either_component():
    result = legal.severance_estimate(8.0, 15.0)
    assert result["final_payment"] >= result["accumulated_guarantee"]
    assert result["final_payment"] >= result["retroactive_calculation"]


# ---------------------------------------------------------------------------
# Utilidades / aguinaldos (Art. 131-133)
# ---------------------------------------------------------------------------

def test_utilities_days_defaults_to_legal_minimum():
    assert legal.utilities_days() == 15.0


def test_utilities_days_below_minimum_is_clamped_up():
    """Ninguna empresa puede pagar menos del mínimo legal, aunque se pida un
    valor menor por error."""
    assert legal.utilities_days(5.0) == 15.0


def test_utilities_days_above_maximum_is_clamped_down():
    assert legal.utilities_days(200.0) == 120.0


def test_utilities_days_within_range_is_respected():
    assert legal.utilities_days(30.0) == 30.0


def test_utilities_amount_full_year_at_minimum():
    # Salario diario 20, 15 días, 12 meses trabajados => 300.
    assert legal.utilities_amount(20.0, days=15.0, months_worked=12) == 300.0


def test_utilities_amount_prorated_for_partial_year():
    # Trabajó 6 de 12 meses => la mitad.
    assert legal.utilities_amount(20.0, days=15.0, months_worked=6) == 150.0


def test_utilities_amount_zero_months_worked_is_zero():
    assert legal.utilities_amount(20.0, days=15.0, months_worked=0) == 0.0


def test_utilities_amount_clamps_months_worked_to_twelve():
    """Más de 12 meses reportados por error no debe inflar el monto."""
    assert legal.utilities_amount(20.0, days=15.0, months_worked=24) == 300.0


# ---------------------------------------------------------------------------
# Vacaciones y bono vacacional (Art. 190 y 192)
# ---------------------------------------------------------------------------

def test_vacation_days_first_year_is_fifteen():
    assert legal.vacation_days(1) == 15


def test_vacation_days_second_year_is_sixteen():
    assert legal.vacation_days(2) == 16


def test_vacation_days_caps_at_thirty():
    assert legal.vacation_days(20) == 30
    assert legal.vacation_days(100) == 30


def test_vacation_days_zero_years_still_gives_base_fifteen():
    """Alguien que aún no cumple un año completo igual tiene derecho a la
    base (el prorrateo real de menos de un año es un caso aparte que este
    módulo no resuelve; se documenta el piso de la fórmula)."""
    assert legal.vacation_days(0) == 15


def test_vacation_bonus_days_matches_vacation_days_formula():
    """Bono vacacional y disfrute de vacaciones comparten la misma fórmula
    de días (15 +1 por año, tope 30), aunque son conceptos distintos."""
    for years in (1, 2, 5, 15, 16, 30):
        assert legal.vacation_bonus_days(years) == legal.vacation_days(years)


def test_vacation_bonus_amount_multiplies_days_by_daily_salary():
    # Año 3 => 17 días * salario diario 15 = 255.
    assert legal.vacation_bonus_amount(15.0, 3) == 255.0


# ---------------------------------------------------------------------------
# IVSS / FAOV / RPE
# ---------------------------------------------------------------------------

def test_contribution_base_uncapped_returns_full_salary():
    assert legal.contribution_base(500.0) == 500.0


def test_contribution_base_caps_at_given_limit():
    assert legal.contribution_base(500.0, cap=300.0) == 300.0


def test_contribution_base_below_cap_is_unaffected():
    assert legal.contribution_base(200.0, cap=300.0) == 200.0


def test_contribution_base_never_negative():
    assert legal.contribution_base(-50.0) == 0.0


def test_ivss_contribution_splits_employer_and_employee_correctly():
    # Salario 1000, patronal 10%, trabajador 4% => 100 y 40.
    employer, employee = legal.ivss_contribution(1000.0, employer_rate_percent=10.0, employee_rate_percent=4.0)
    assert employer == 100.0
    assert employee == 40.0


def test_ivss_contribution_respects_cap():
    # Salario 1000 pero tope 600, patronal 10% => 60, no 100.
    employer, employee = legal.ivss_contribution(1000.0, employer_rate_percent=10.0, employee_rate_percent=4.0, cap=600.0)
    assert employer == 60.0
    assert employee == 24.0


def test_faov_contribution_uses_two_and_one_percent_by_default():
    employer, employee = legal.faov_contribution(1000.0)
    assert employer == 20.0
    assert employee == 10.0


def test_faov_contribution_accepts_custom_rates():
    employer, employee = legal.faov_contribution(1000.0, employer_rate_percent=3.0, employee_rate_percent=1.5)
    assert employer == 30.0
    assert employee == 15.0


def test_rpe_contribution_uses_two_and_half_percent_by_default():
    employer, employee = legal.rpe_contribution(1000.0)
    assert employer == 20.0
    assert employee == 5.0


def test_rpe_contribution_respects_cap():
    employer, employee = legal.rpe_contribution(1000.0, cap=400.0)
    assert employer == 8.0
    assert employee == 2.0
