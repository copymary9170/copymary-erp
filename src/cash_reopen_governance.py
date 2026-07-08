"""Seguimiento posterior para reaperturas de cierre de caja."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, cash_closing_reopen_control as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("cash_reopen_action_plans", "Planes de corrección por reapertura de caja"),
        ("cash_reopen_evidence", "Evidencias de reapertura de caja"),
        ("cash_reopen_sla_rules", "SLA de reapertura de caja"),
        ("cash_reopen_closeouts", "Cierres posteriores a reapertura de caja"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _rows(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save(key: str, rows: list[dict]) -> None:
    st.session_state[key] = rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dt(value) -> datetime | None:
    raw = str(value or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:10])
        except ValueError:
            return None


def _sla_rules() -> dict:
    defaults = {"low_hours": 24, "medium_hours": 12, "high_hours": 4, "max_reopen_days": 10}
    rows = _rows("cash_reopen_sla_rules")
    if rows:
        defaults.update(rows[0])
    return defaults


def _risk_hours(risk: str, rules: dict) -> int:
    if risk == "Alto":
        return int(_num(rules.get("high_hours"), 4))
    if risk == "Medio":
        return int(_num(rules.get("medium_hours"), 12))
    return int(_num(rules.get("low_hours"), 24))


def _due_at(request: dict, rules: dict) -> datetime | None:
    created = _dt(request.get("created_at_utc"))
    if created is None:
        return None
    return created + timedelta(hours=_risk_hours(str(request.get("risk", "Bajo")), rules))


def _reopened_closings() -> list[dict]:
    return [row for row in _rows("cash_closings") if row.get("reopened")]


def _export_plans(plans: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Plan", "Cierre", "Estado", "Responsable", "Fecha compromiso", "Acción", "Fecha"])
    for row in plans:
        writer.writerow([
            row.get("plan_id", ""), row.get("closing_id", ""), row.get("status", ""), row.get("responsible", ""),
            row.get("due_date", ""), row.get("action", ""), row.get("created_at_utc", ""),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_cash_reopen_governance() -> None:
    render_page_header(
        "Reabrir cierre de caja",
        "Controla SLA, plan de corrección, evidencias y cierre posterior de cada reapertura.",
    )

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_cash_closing_reopen_control()
    finally:
        base.render_page_header = original_header

    requests = _rows("cash_reopen_requests")
    plans = _rows("cash_reopen_action_plans")
    evidence = _rows("cash_reopen_evidence")
    closeouts = _rows("cash_reopen_closeouts")
    rules = _sla_rules()
    reopened = _reopened_closings()
    now = datetime.now()

    active_requests = [row for row in requests if row.get("status") in {"Pendiente", "Aprobada", "Aplicada"}]
    overdue = [row for row in active_requests if (due := _due_at(row, rules)) is not None and due < now and row.get("status") != "Aplicada"]
    open_plans = [row for row in plans if row.get("status") != "Completado"]
    missing_evidence = [row for row in reopened if not any(ev.get("closing_id") == row.get("closing_id") for ev in evidence)]

    st.divider()
    st.markdown("### Seguimiento posterior de reaperturas")
    metrics = st.columns(5)
    metrics[0].metric("SLA vencidos", str(len(overdue)))
    metrics[1].metric("Planes abiertos", str(len(open_plans)))
    metrics[2].metric("Sin evidencia", str(len(missing_evidence)))
    metrics[3].metric("Cierres posteriores", str(len(closeouts)))
    metrics[4].metric("Reabiertos", str(len(reopened)))

    if overdue:
        st.error(f"Hay {len(overdue)} solicitud(es) con SLA vencido.")
    if missing_evidence:
        st.warning(f"Hay {len(missing_evidence)} reapertura(s) sin evidencia registrada.")

    sla_tab, plan_tab, evidence_tab, closeout_tab, rules_tab = st.tabs(("SLA", "Plan de corrección", "Evidencias", "Cierre posterior", "Reglas"))

    with sla_tab:
        if not active_requests:
            st.info("No hay solicitudes activas para medir SLA.")
        for request in reversed(active_requests[-100:]):
            due = _due_at(request, rules)
            late = due is not None and due < now and request.get("status") != "Aplicada"
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{request.get('request_id', '')} · cierre {request.get('closing_id', '')}**")
                cols[0].caption(f"Riesgo {request.get('risk', 'Bajo')} · estado {request.get('status', '')} · vence {due.isoformat() if due else 'Sin fecha'}")
                cols[1].metric("SLA", "Vencido" if late else "Activo")
                cols[2].metric("Urgente", "Sí" if request.get("urgent") else "No")

    with plan_tab:
        closing_options = {f"{row.get('closing_id', '')} · {row.get('closing_date', '')}": str(row.get("closing_id", "")) for row in reopened}
        if not closing_options:
            st.info("No hay cierres reabiertos para planificar corrección.")
        else:
            with st.form("cash_reopen_action_plan_form", clear_on_submit=True):
                selected = st.selectbox("Cierre reabierto", tuple(closing_options.keys()))
                action = st.text_area("Acción correctiva", max_chars=600)
                responsible = st.text_input("Responsable")
                due_date = st.date_input("Fecha compromiso", value=date.today() + timedelta(days=1))
                priority = st.selectbox("Prioridad", ("Alta", "Media", "Baja"))
                submitted = st.form_submit_button("Crear plan", type="primary", use_container_width=True)
            if submitted:
                if not action.strip() or not responsible.strip():
                    st.error("Acción y responsable son obligatorios.")
                else:
                    plans.append({
                        "plan_id": f"RPL-{uuid4().hex[:8].upper()}",
                        "closing_id": closing_options[selected],
                        "action": action.strip(),
                        "responsible": responsible.strip(),
                        "due_date": due_date.isoformat(),
                        "priority": priority,
                        "status": "Abierto",
                        "created_at_utc": _now(),
                    })
                    _save("cash_reopen_action_plans", plans)
                    st.rerun()
        st.download_button("Descargar planes CSV", data=_export_plans(plans), file_name="planes_reapertura_caja.csv", mime="text/csv", use_container_width=True, disabled=not plans)
        for plan in reversed(plans[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{plan.get('plan_id', '')} · cierre {plan.get('closing_id', '')}**")
                cols[0].caption(f"{plan.get('priority', '')} · {plan.get('responsible', '')} · compromiso {plan.get('due_date', '')}")
                cols[1].metric("Estado", str(plan.get("status", "")))
                if cols[2].button("Completar", key=f"complete_plan_{plan.get('plan_id')}", use_container_width=True, disabled=plan.get("status") == "Completado"):
                    changed = []
                    for row in plans:
                        current = dict(row)
                        if current.get("plan_id") == plan.get("plan_id"):
                            current["status"] = "Completado"
                            current["completed_at_utc"] = _now()
                        changed.append(current)
                    _save("cash_reopen_action_plans", changed)
                    st.rerun()

    with evidence_tab:
        closing_options = {f"{row.get('closing_id', '')} · {row.get('closing_date', '')}": str(row.get("closing_id", "")) for row in reopened}
        if not closing_options:
            st.info("No hay cierres reabiertos para registrar evidencia.")
        else:
            with st.form("cash_reopen_evidence_form", clear_on_submit=True):
                selected = st.selectbox("Cierre", tuple(closing_options.keys()), key="evidence_closing")
                evidence_type = st.selectbox("Tipo", ("Comprobante", "Nota interna", "Reconteo", "Conciliación", "Otro"))
                reference = st.text_input("Referencia")
                responsible = st.text_input("Responsable")
                note = st.text_area("Detalle", max_chars=600)
                submitted = st.form_submit_button("Guardar evidencia", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not note.strip():
                    st.error("Responsable y detalle son obligatorios.")
                else:
                    evidence.append({
                        "evidence_id": f"REV-{uuid4().hex[:8].upper()}",
                        "closing_id": closing_options[selected],
                        "evidence_type": evidence_type,
                        "reference": reference.strip(),
                        "responsible": responsible.strip(),
                        "note": note.strip(),
                        "created_at_utc": _now(),
                    })
                    _save("cash_reopen_evidence", evidence)
                    st.rerun()
        for row in reversed(evidence[-100:]):
            st.write(f"**{row.get('evidence_id', '')} · cierre {row.get('closing_id', '')} · {row.get('evidence_type', '')}** — {row.get('responsible', '')}: {row.get('note', '')}")

    with closeout_tab:
        candidates = [row for row in reopened if not any(closeout.get("closing_id") == row.get("closing_id") for closeout in closeouts)]
        if not candidates:
            st.info("No hay reaperturas pendientes de cierre posterior.")
        for closing in candidates[-50:]:
            closing_id = str(closing.get("closing_id", ""))
            closing_plans = [row for row in plans if row.get("closing_id") == closing_id]
            pending_plan_count = sum(1 for row in closing_plans if row.get("status") != "Completado")
            evidence_count = sum(1 for row in evidence if row.get("closing_id") == closing_id)
            with st.container(border=True):
                st.markdown(f"**Cierre {closing_id}**")
                st.caption(f"Planes pendientes: {pending_plan_count} · evidencias: {evidence_count}")
                with st.form(f"closeout_reopen_{closing_id}"):
                    reviewer = st.text_input("Revisado por", key=f"closeout_by_{closing_id}")
                    conclusion = st.text_area("Conclusión", max_chars=700, key=f"closeout_note_{closing_id}")
                    confirmed = st.checkbox("Confirmo que la corrección quedó documentada", key=f"closeout_confirm_{closing_id}")
                    submitted = st.form_submit_button("Cerrar seguimiento de reapertura", type="primary", use_container_width=True)
                if submitted:
                    if not reviewer.strip() or not conclusion.strip() or not confirmed:
                        st.error("Revisor, conclusión y confirmación son obligatorios.")
                    elif pending_plan_count:
                        st.error("No se puede cerrar mientras existan planes pendientes.")
                    elif evidence_count == 0:
                        st.error("Registra al menos una evidencia antes de cerrar seguimiento.")
                    else:
                        closeouts.append({
                            "closeout_id": f"RCO-{uuid4().hex[:8].upper()}",
                            "closing_id": closing_id,
                            "reviewer": reviewer.strip(),
                            "conclusion": conclusion.strip(),
                            "created_at_utc": _now(),
                        })
                        _save("cash_reopen_closeouts", closeouts)
                        st.rerun()
        for row in reversed(closeouts[-50:]):
            st.success(f"{row.get('closeout_id', '')} · cierre {row.get('closing_id', '')} · {row.get('reviewer', '')} · {row.get('created_at_utc', '')}")

    with rules_tab:
        with st.form("cash_reopen_sla_rules_form"):
            cols = st.columns(4)
            high_hours = cols[0].number_input("SLA riesgo alto horas", min_value=1, value=int(_num(rules.get("high_hours"), 4)), step=1)
            medium_hours = cols[1].number_input("SLA riesgo medio horas", min_value=1, value=int(_num(rules.get("medium_hours"), 12)), step=1)
            low_hours = cols[2].number_input("SLA riesgo bajo horas", min_value=1, value=int(_num(rules.get("low_hours"), 24)), step=1)
            max_days = cols[3].number_input("Antigüedad máxima días", min_value=1, value=int(_num(rules.get("max_reopen_days"), 10)), step=1)
            submitted = st.form_submit_button("Guardar reglas", type="primary", use_container_width=True)
        if submitted:
            _save("cash_reopen_sla_rules", [{
                "high_hours": int(high_hours),
                "medium_hours": int(medium_hours),
                "low_hours": int(low_hours),
                "max_reopen_days": int(max_days),
                "updated_at_utc": _now(),
            }])
            st.rerun()

    render_info_card(
        "Reapertura con cierre de ciclo",
        "La reapertura no termina al abrir el cierre: ahora exige plan, evidencia y cierre posterior documentado.",
        "POSTCONTROL",
    )


app_shell.FUNCTIONAL_MODULES["Reabrir cierre de caja"] = render_cash_reopen_governance
