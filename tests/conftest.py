"""Fixtures compartidas para las pruebas de CopyMary ERP.

Aísla cada prueba en:
- su propia base de datos SQLite temporal (vía `COPYMARY_DB_PATH`), para que
  las pruebas nunca toquen `copymary_erp.sqlite3` real ni se contaminen entre sí;
- un `st.session_state` limpio, ya que varios módulos guardan datos ahí.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Permite `import src...` al correr `pytest` desde la raíz del repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Cada prueba obtiene su propio archivo SQLite temporal y vacío."""
    db_path = tmp_path / "test_copymary_erp.sqlite3"
    monkeypatch.setenv("COPYMARY_DB_PATH", str(db_path))
    monkeypatch.delenv("COPYMARY_DATABASE_URL", raising=False)
    yield db_path


@pytest.fixture(autouse=True)
def clean_session_state():
    """Limpia `st.session_state` antes y después de cada prueba."""
    st.session_state.clear()
    yield
    st.session_state.clear()
