"""Embudo CRM (leads → oportunidad → cierre) — CopyMary ERP.

Página autocontenida (Streamlit multipágina): se activa solo con colocarla en
`pages/`; no requiere cablear app.py ni la navegación.

Gestiona prospectos por etapas del embudo, con valor estimado, origen y notas;
calcula pipeline y tasa de conversión; y al ganar un prospecto permite
registrarlo como cliente. Los datos se guardan en la clave `crm_leads` y se
suman al respaldo general si está disponible.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import streamlit as st

try:
    from src.session_utils import read_list as _read_list, save_list as _save_list
except Exception:  # pragma: no cover - respaldo defensivo
    def _read_list(key: str) -> list[dict]:
        value = st.session_state.get(key, [])
        return value if isinstance(value, list) else []

    def _save_list(key: str, rows: list[dict]) -> None:
        st.session_state[key] = rows


LEADS_KEY = "crm_leads"

STAGE_PROSPECT = "Prospecto"
STAGE_CONTACTED = "Contactado"
STAGE_QUOTED = "Cotizado"
STAGE_NEGOTIATION = "Negociación"
STAGE_WON = "Ganado"
STAGE_LOST = "Perdido"

ACTIVE_STAGES = (STAGE_PROSPECT, STAGE_CONTACTED, STAGE_QUOTED, STAGE_NEGOTIATION)
ALL_STAGES = (*ACTIVE_STAGES, STAGE_WON, STAGE_LOST)
SOURCES = ("Recomendación", "Redes sociales", "WhatsApp", "Local / mostrador",
           "Publicidad", "Cliente recurrente", "Otro")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _register_backup_section() -> None:
    """Suma la sección de leads al respaldo general, sin pisar lo existente."""
    try:
        from src import session_backup
        if LEADS_KEY not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, LEADS_KEY)
            session_backup.SECTION_LABELS[LEADS_KEY] = "Embudo CRM (prospectos)"
            session_backup.SESSION_KEYS = (
                "general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS,
            )
    except Exception:
        pass


def _leads() -> list[dict]:
    return _read_list(LEADS_KEY)


def _save(leads: list[dict]) -> None:
    _save_list(LEADS_KEY, leads)


def add_lead(*, name: str, contact: str, source: str, value: float, notes: str) -> dict:
    lead = {
        "lead_id": uuid4().hex[:8].upper(),
        "name": name.strip(),
        "contact": contact.strip(),
        "source": source,
        "estimated_value": _num(value),
        "notes": notes.strip(),
        "stage": STAGE_PROSPECT,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
    }
    leads = _leads()
    leads.append(lead)
    _save(leads)
    return lead


def set_stage(lead_id: str, stage: str) -> bool:
    leads = _leads()
    changed = False
    for lead in leads:
        if str(lead.get("lead_id")) == lead_id:
            lead["stage"] = stage
            lead["updated_at_utc"] = _now()
            changed = True
    if changed:
        _save(leads)
    return changed


def _register_as_customer(lead: dict) -> None:
    """Al ganar, agrega el prospecto a customers_registry si no existe ya."""
    customers = _read_list("customers_registry")
    name = str(lead.get("name", "")).strip()
    if name and not any(str(c.get("name", "")).strip().casefold() == name.casefold() for c in customers):
        customers.append({
            "client_id": uuid4().hex[:8].upper(),
            "name": name,
            "contact": lead.get("contact", ""),
            "source": lead.get("source", ""),
            "created_at_utc": _now(),
        })
        _save_list("customers_registry", customers)


def _metrics(leads: list[dict]) -> dict:
    active = [l for l in leads if l.get("stage") in ACTIVE_STAGES]
    won = [l for l in leads if l.get("stage") == STAGE_WON]
    lost = [l for l in leads if l.get("stage") == STAGE_LOST]
    closed = len(won) + len(lost)
    return {
        "pipeline_value": sum(_num(l.get("estimated_value")) for l in active),
        "won_value": sum(_num(l.get("estimated_value")) for l in won),
        "active": len(active),
        "won": len(won),
        "lost": len(lost),
        "conversion": (len(won) / closed * 100.0) if closed else 0.0,
    }


def render() -> None:
    _register_backup_section()
    st.title("Embudo CRM")
    st.caption("Sigue tus prospectos desde el primer contacto hasta el cierre. "
               "Prospecto → Contactado → Cotizado → Negociación → Ganado / Perdido.")

    leads = _leads()
    metrics = _metrics(leads)
    row = st.columns(5)
    row[0].metric("En pipeline", str(metrics["active"]))
    row[1].metric("Valor en pipeline", f"{metrics['pipeline_value']:,.2f}")
    row[2].metric("Ganados", str(metrics["won"]))
    row[3].metric("Perdidos", str(metrics["lost"]))
    row[4].metric("Conversión", f"{metrics['conversion']:.0f}%")

    with st.expander("➕ Nuevo prospecto", expanded=not leads):
        with st.form("crm_new_lead", clear_on_submit=True):
            cols = st.columns(3)
            name = cols[0].text_input("Nombre / empresa", max_chars=100)
            contact = cols[1].text_input("Contacto (teléfono / correo)", max_chars=80)
            source = cols[2].selectbox("Origen", SOURCES)
            value = st.number_input("Valor estimado", min_value=0.0, value=0.0, step=1.0)
            notes = st.text_area("Notas", max_chars=300)
            submitted = st.form_submit_button("Agregar prospecto", type="primary",
                                              use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("El nombre del prospecto no puede quedar vacío.")
            else:
                add_lead(name=name, contact=contact, source=source, value=value, notes=notes)
                st.success("Prospecto agregado.")
                st.rerun()

    st.subheader("Embudo")
    board = st.columns(len(ACTIVE_STAGES))
    for index, stage in enumerate(ACTIVE_STAGES):
        with board[index]:
            in_stage = [l for l in leads if l.get("stage") == stage]
            st.markdown(f"**{stage}** ({len(in_stage)})")
            for lead in in_stage:
                with st.container(border=True):
                    st.markdown(f"**{lead.get('name', '—')}**")
                    st.caption(f"{lead.get('source', '')} · {_num(lead.get('estimated_value')):,.2f}")
                    if lead.get("contact"):
                        st.caption(f"📞 {lead['contact']}")
                    new_stage = st.selectbox(
                        "Mover a", ALL_STAGES, index=ALL_STAGES.index(stage),
                        key=f"crm_stage_{lead['lead_id']}", label_visibility="collapsed",
                    )
                    make_customer = False
                    if new_stage == STAGE_WON:
                        make_customer = st.checkbox("Registrar como cliente",
                                                    key=f"crm_cust_{lead['lead_id']}", value=True)
                    if new_stage != stage and st.button("Aplicar", key=f"crm_apply_{lead['lead_id']}",
                                                        use_container_width=True):
                        set_stage(lead["lead_id"], new_stage)
                        if new_stage == STAGE_WON and make_customer:
                            _register_as_customer(lead)
                        st.rerun()

    closed = [l for l in leads if l.get("stage") in (STAGE_WON, STAGE_LOST)]
    if closed:
        with st.expander(f"Cerrados ({len(closed)})"):
            st.dataframe(
                [{"Nombre": l.get("name", "—"), "Etapa": l.get("stage", ""),
                  "Origen": l.get("source", ""), "Valor": round(_num(l.get("estimated_value")), 2)}
                 for l in closed],
                use_container_width=True, hide_index=True,
            )


render()
