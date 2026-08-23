from src.marketing_ai_builder import ai_qa_score, build_master_prompt, unresolved_placeholders


def test_build_master_prompt_has_seven_blocks():
    prompt = build_master_prompt({
        "role": "Estratega",
        "objective": "Generar leads",
        "deliverable": "Landing",
        "context": "Marca local",
        "structure": "Hero, prueba, CTA",
        "behavior": "Pregunta si falta un dato",
        "constraints": "No inventar precios",
    })
    assert prompt.count("## ") == 7
    assert "NO INVENTAR" not in prompt  # conserva exactamente el criterio escrito
    assert "No inventar precios" in prompt


def test_unresolved_placeholders_detects_pending_fields():
    assert unresolved_placeholders("Usa [MARCA] para [AUDIENCIA] y [MARCA]") == ["[AUDIENCIA]", "[MARCA]"]
    assert unresolved_placeholders("Prompt completo") == []


def test_ai_qa_score():
    assert ai_qa_score({"a": True, "b": False, "c": True, "d": True}) == 75.0
    assert ai_qa_score({}) == 0.0
