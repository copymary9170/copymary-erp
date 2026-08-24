from src import creative_equipment_knowledge as knowledge
from src.laser_printer_profile_loader import activate_laser_printer_profile


def test_laser_printer_profile_is_added_once():
    original = knowledge.PROFILES
    try:
        knowledge.PROFILES = tuple(p for p in original if p.key != "laser_printer")
        activate_laser_printer_profile()
        activate_laser_printer_profile()
        matches = [p for p in knowledge.PROFILES if p.key == "laser_printer"]
        assert len(matches) == 1
        profile = matches[0]
        assert profile.equipment == "Impresora láser"
        assert profile.usage_metric == "Páginas impresas"
        assert "fusor" in " ".join(profile.wear_parts).lower()
        assert "tóner" in " ".join(profile.wear_parts).lower()
    finally:
        knowledge.PROFILES = original
