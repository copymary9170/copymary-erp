"""Punto de restauración automático y reversión de respaldos."""

from copy import deepcopy
from datetime import datetime, timezone

import streamlit as st

from src import session_backup
from src.components import render_info_card
from src.safe_session_backup import render_safe_session_backup


_ORIGINAL_RESTORE = session_backup._restore
SNAPSHOT_KEY = "_restore_rollback_snapshot"
META_KEY = "_restore_rollback_meta"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot(selected: list[str]) -> dict:
    return {
        key: deepcopy(st.session_state.get(key))
        for key in selected
    }


def _restore_with_snapshot(data: dict, selected: list[str]) -> None:
    st.session_state[SNAPSHOT_KEY] = _snapshot(selected)
    st.session_state[META_KEY] = {
        "created_at_utc": _now(),
        "sections": list(selected),
        "source_created_at_utc": str(data.get("created_at_utc", "")),
    }
    _ORIGINAL_RESTORE(data, selected)


def activate_restore_rollback() -> None:
    session_backup._restore = _restore_with_snapshot


def _apply_rollback(snapshot: dict, sections: list[str]) -> None:
    for key in sections:
        if key not in snapshot:
            continue
        value = deepcopy(snapshot[key])
        if value is None:
            st.session_state.pop(key, None)
        else:
            st.session_state[key] = value

    for key in (
        "connected_costing_result",
        "connected_costing_asset",
        "connected_costing_material",
        "price_estimate",
    ):
        st.session_state.pop(key, None)


def render_backup_with_rollback() -> None:
    activate_restore_rollback()
    render_safe_session_backup()

    st.divider()
    st.subheader("Deshacer última restauración")
    snapshot = st.session_state.get(SNAPSHOT_KEY)
    meta = st.session_state.get(META_KEY, {})

    if not isinstance(snapshot, dict) or not snapshot:
        st.info("Todavía no existe un punto de restauración automático.")
    else:
        sections = [key for key in meta.get("sections", []) if key in snapshot]
        st.warning(
            "Existe una copia automática de la sesión anterior a la última restauración."
        )
        st.caption(
            f"Creada: {meta.get('created_at_utc', 'No disponible')} · "
            f"Secciones: {len(sections)} · "
            f"Respaldo aplicado: {meta.get('source_created_at_utc') or 'No disponible'}"
        )

        selected = st.multiselect(
            "Secciones que deseas recuperar del punto anterior",
            options=sections,
            default=sections,
            format_func=lambda key: session_backup.SECTION_LABELS.get(key, key),
            key="rollback_sections",
        )
        confirmation = st.text_input(
            "Escribe DESHACER para confirmar",
            max_chars=20,
            key="rollback_confirmation",
        )
        if st.button(
            "Deshacer última restauración",
            type="primary",
            use_container_width=True,
            disabled=not selected or confirmation.strip().upper() != "DESHACER",
        ):
            _apply_rollback(snapshot, selected)
            st.session_state.pop(SNAPSHOT_KEY, None)
            st.session_state.pop(META_KEY, None)
            st.success("La sesión anterior fue recuperada.")
            st.rerun()

        if st.button(
            "Descartar punto de restauración",
            use_container_width=True,
            key="discard_restore_snapshot",
        ):
            st.session_state.pop(SNAPSHOT_KEY, None)
            st.session_state.pop(META_KEY, None)
            st.rerun()

    render_info_card(
        "Protección adicional",
        "Antes de cada restauración se guarda una copia temporal de las secciones que serán reemplazadas.",
        "PUNTO DE RESTAURACIÓN",
    )
