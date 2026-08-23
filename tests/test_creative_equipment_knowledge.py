from src.creative_equipment_knowledge import PROFILES, electrical_current, load_percent, profile_by_key


def test_researched_profiles_exist():
    assert profile_by_key("sublimation_printer") is not None
    assert profile_by_key("cutting_plotter") is not None
    assert profile_by_key("heat_press") is not None
    assert profile_by_key("laminator") is not None


def test_heat_press_reference_is_high_power():
    profile = profile_by_key("heat_press")
    assert profile is not None
    assert profile.watts_reference == 1400.0
    assert profile.amps_reference == 13.0


def test_current_and_load_helpers():
    assert round(electrical_current(1400, 120), 2) == 11.67
    assert round(load_percent(12, 15), 1) == 80.0
    assert electrical_current(1000, 0) == 0.0
    assert load_percent(10, 0) == 0.0


def test_profiles_have_wear_and_usage_guidance():
    assert PROFILES
    for profile in PROFILES:
        assert profile.equipment
        assert profile.typical_jobs
        assert isinstance(profile.typical_jobs, tuple)
        assert profile.wear_parts
        assert isinstance(profile.wear_parts, tuple)
        assert profile.usage_metric
        assert isinstance(profile.maintenance_focus, tuple)
        assert profile.electrical_level
        assert profile.voltage_note


def test_foil_profile_fields_are_not_shifted():
    profile = profile_by_key("foil_machine")
    assert profile is not None
    assert "Tarjetas" in profile.typical_jobs
    assert "Rodillo/silicona" in profile.wear_parts
    assert profile.usage_metric == "Estampados de foil"
    assert profile.electrical_level == "Media/Alta"
