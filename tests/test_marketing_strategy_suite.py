"""Pruebas de la suite estratégica de Marketing."""

from src import marketing_strategy_suite as suite


def test_content_strategy_completeness_full_chain():
    row = {
        "objective": "Ventas",
        "strategy": "Storyselling",
        "tactic": "Reels de demostración",
        "content_type": "Conversión",
        "kpi": "Conversaciones",
    }
    assert suite.content_strategy_completeness(row) == 100.0


def test_content_strategy_completeness_partial_chain():
    row = {"objective": "Branding", "strategy": "Branded Content"}
    assert suite.content_strategy_completeness(row) == 40.0


def test_social_listening_summary_counts_supported_sentiments():
    rows = [
        {"sentiment": "Positivo"},
        {"sentiment": "Negativo"},
        {"sentiment": "Positivo"},
        {"sentiment": "Neutral"},
    ]
    assert suite.social_listening_summary(rows) == {
        "Positivo": 2,
        "Neutral": 1,
        "Negativo": 1,
    }


def test_copy_framework_templates_preserve_course_order():
    assert suite.copy_framework_template("AIDA") == ("Atención", "Interés", "Deseo", "Acción")
    assert suite.copy_framework_template("PAS") == ("Problema", "Agitación", "Solución")
    assert suite.copy_framework_template("PASTOR") == (
        "Problema", "Amplificación", "Story", "Transformación", "Oferta", "Respuesta"
    )


def test_core_course_taxonomies_are_available():
    assert "Fidelización" in suite.CONTENT_OBJECTIVES
    assert "Testimonial" in suite.CONTENT_TYPES
    assert "Números + beneficio" in suite.HOOK_TYPES
    assert "9:16 Vertical" in suite.VIDEO_RATIOS
