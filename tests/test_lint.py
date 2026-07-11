"""Prueba de lint: detecta nombres indefinidos en tiempo de importación estática.

Nace de un bug real encontrado en `stock_alerts_plus.py`, que llamaba a
`_item_name(...)` sin haberla definido ni importado — un `NameError` que solo
se disparaba al usar esa pestaña de la app, porque estaba dentro de una
función y nunca se detectaba con un simple `import`.

Esta prueba corre `pyflakes` sobre todo `src/` y falla si aparece cualquier
"undefined name", para atrapar esta clase de error en CI en vez de en
producción.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"


def test_no_undefined_names_in_src():
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", *sorted(str(p) for p in SRC.glob("*.py"))],
        capture_output=True,
        text=True,
    )
    undefined_name_lines = [
        line for line in result.stdout.splitlines() if "undefined name" in line
    ]
    assert undefined_name_lines == [], (
        "pyflakes encontró nombres indefinidos (probable NameError en runtime):\n"
        + "\n".join(undefined_name_lines)
    )
