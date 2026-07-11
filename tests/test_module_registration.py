"""Prueba de arquitectura: evita que el menú apunte a una capa vieja.

Varios dominios de negocio están organizados en capas que se extienden entre
sí (`from src import X as base`), por ejemplo:
`costing.py` → `costing_plus.py` → `costing_governance.py` → `costing_control.py`.

Solo la capa más completa de cada dominio debe estar registrada en
`module_bootstrap.MODULE_RENDERERS` (lo que arma el menú). Si alguien agrega
una capa nueva más completa pero se olvida de actualizar el registro, el
usuario seguiría viendo la versión vieja sin darse cuenta. Esta prueba lo
detecta automáticamente: para cada módulo registrado, verifica que ningún
otro módulo lo extienda (si lo extendiera, esa extensión debería ser la
registrada en su lugar).
"""

from __future__ import annotations

import re
from pathlib import Path

from src import module_bootstrap

SRC = Path(__file__).resolve().parent.parent / "src"

EXTENDS_PATTERN = re.compile(r"from src import ([\w, ]*?)(\w+) as base")


def _build_extended_by_map() -> dict[str, list[str]]:
    """Devuelve, por cada módulo base, la lista de módulos que lo extienden."""
    extended_by: dict[str, list[str]] = {}
    for path in SRC.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        match = EXTENDS_PATTERN.search(text)
        if match:
            base_module = match.group(2)
            extended_by.setdefault(base_module, []).append(path.stem)
    return extended_by


def test_no_registered_module_has_a_more_complete_unregistered_layer():
    extended_by = _build_extended_by_map()
    registered_module_names = {module_path.removeprefix("src.") for _, module_path, _ in module_bootstrap.MODULE_RENDERERS}

    stale_entries = []
    for display_name, module_path, _renderer in module_bootstrap.MODULE_RENDERERS:
        module_name = module_path.removeprefix("src.")
        for extender in extended_by.get(module_name, []):
            if extender not in registered_module_names:
                stale_entries.append(f"'{display_name}' apunta a {module_name}, pero {extender}.py lo extiende y no está registrado")

    assert stale_entries == [], "Posibles capas obsoletas en el menú:\n" + "\n".join(stale_entries)


def test_module_renderers_have_unique_display_names():
    """Dos entradas de menú con el mismo nombre serían indistinguibles para el usuario."""
    names = [display_name for display_name, _, _ in module_bootstrap.MODULE_RENDERERS]
    assert len(names) == len(set(names))


def test_all_registered_renderers_import_successfully():
    """Cada módulo registrado debe poder importarse y exponer su función renderer."""
    missing = []
    for display_name, module_path, renderer_name in module_bootstrap.MODULE_RENDERERS:
        renderer = module_bootstrap._load_renderer(module_path, renderer_name, display_name)
        if renderer is None:
            missing.append(f"'{display_name}' ({module_path}.{renderer_name})")
    assert missing == [], "Módulos registrados que no cargan (quedarían invisibles en el menú):\n" + "\n".join(missing)


def test_failed_module_import_is_recorded_not_silently_swallowed():
    """Antes, un módulo roto desaparecía del menú sin dejar rastro. Ahora debe
    quedar registrado en FAILED_MODULES para que se vea en 'Fundación técnica'."""
    module_bootstrap.FAILED_MODULES.clear()
    result = module_bootstrap._try_import("src.este_modulo_no_existe_de_verdad", "Módulo de prueba")

    assert result is None
    assert len(module_bootstrap.FAILED_MODULES) == 1
    display_name, module_path, error_message = module_bootstrap.FAILED_MODULES[0]
    assert display_name == "Módulo de prueba"
    assert module_path == "src.este_modulo_no_existe_de_verdad"
    assert error_message != ""


def test_failed_module_without_display_name_falls_back_to_module_path():
    """Los SIDE_EFFECT_MODULES no tienen nombre visible; deben seguir apareciendo
    en FAILED_MODULES con el module_path como identificador."""
    module_bootstrap.FAILED_MODULES.clear()
    module_bootstrap._try_import("src.este_modulo_no_existe_de_verdad")

    assert module_bootstrap.FAILED_MODULES[0][0] == "src.este_modulo_no_existe_de_verdad"


def test_load_renderer_records_failure_when_renderer_missing():
    """Si el módulo importa bien pero no tiene la función renderer esperada,
    también debe quedar registrado (no solo cuando falla el import)."""
    module_bootstrap.FAILED_MODULES.clear()
    renderer = module_bootstrap._load_renderer("src.money", "funcion_que_no_existe", "Módulo de prueba")

    assert renderer is None
    assert len(module_bootstrap.FAILED_MODULES) == 1
    display_name, module_path, error_message = module_bootstrap.FAILED_MODULES[0]
    assert display_name == "Módulo de prueba"
    assert "funcion_que_no_existe" in error_message


def test_activate_module_bootstrap_clears_previous_failures():
    """Cada llamada a activate_module_bootstrap() debe empezar con la lista
    limpia, para no acumular fallos de una recarga anterior."""
    module_bootstrap.FAILED_MODULES.append(("viejo", "src.viejo", "error viejo"))
    module_bootstrap.activate_module_bootstrap()

    assert ("viejo", "src.viejo", "error viejo") not in module_bootstrap.FAILED_MODULES
