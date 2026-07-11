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
        renderer = module_bootstrap._load_renderer(module_path, renderer_name)
        if renderer is None:
            missing.append(f"'{display_name}' ({module_path}.{renderer_name})")
    assert missing == [], "Módulos registrados que no cargan (quedarían invisibles en el menú):\n" + "\n".join(missing)
