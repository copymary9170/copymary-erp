"""Postcontrol para anulaciones y ajustes: SLA, planes y cierre documental."""

from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import io

import streamlit as st

from src import adjustments_governance as base, app_shell, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save


def _activate_backup() -> None:
    for section, label in (
        ("adjustment_sla_rules", "Reglas SLA de anulaciones y ajustes"),
        ("adjustment_action_plans", "Planes de corrección de anulaciones"),
        ("adjustment_closeouts", "Cierres documentales de ajustes"),
        ("adjustment_impact_snapshots", "Cortes de impacto de ajustes"),
        ("adjustment_followup_cases", "Casos de seguimiento de ajustes"),
    ):
        if section not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, section)
            session_backup.SECTION_LABELS[section] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


_activate_backup()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
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


def _period() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _rules() -> dict:
    defaults = {"high_hours": 4, "medium_hours": 12, "low_hours": 24, "max_unclosed_adjustments": 0}
    rows = _rows("adjustment_sla_rules")
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


def _adjustment_key(row: dict) -> str:
    return str(row.get("adjustment_id", row.get("reference_id", "")))


def _open_adjustments(adjustments: list[dict], closeouts: list[dict]) -> list[dict]:
    closed = {str(row.get("adjustment_id", "")) for row in closeouts}
    return [row for row in adjustments if _adjustment_key(row) not in closed]


def _evidence_count(adjustment_id: str) -> int:
    return sum(1 for row in _rows("adjustment_evidence") if str(row.get("adjustment_id", "")) == adjustment_id)


def _export_plans(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Plan", "Ajuste", "Estado", "Responsable", "Vence", "Prioridad", "Acción"])
    for row in rows:
        writer.writerow([row.get("plan_id", ""), row.get("adjustment_id", ""), row.get("status", ""), row.get("responsible", ""), row.get("due_date", ""), row.get("priority", ""), row.get("action", "")])
    return buffer.getvalue().encode("utf-8-sig")


def render_adjustments_postcontrol() -> None:
    render_page_header("Anulaciones y ajustes", "Agrega SLA, planes correctivos, cierre documental e impacto mensual.")

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_adjustments_governance()
    finally:
        base.render_page_header = original_header

    requests = _rows("adjustment_requests")
    adjustments = _rows("adjustment_records")
    plans = _rows("adjustment_action_plans")
    closeouts = _rows("adjustment_closeouts")
    snapshots = _rows("adjustment_impact_snapshots")
    cases = _rows("adjustment_followup_cases")
    rules = _rules()
    now = datetime.now()
    active_requests = [row for row in requests if row.get("status") in {"Pendiente", "Aprobada"}]
    overdue = [row for row in active_requests if (due := _due_at(row, rules)) is not None and due < now]
    open_items = _open_adjustments(adjustments, closeouts)
    open_plans = [row for row in plans if row.get("status") != "Completado"]
    missing_evidence = [row for row in adjustments if _evidence_count(_adjustment_key(row)) == 0]
    period = _period()
    period_adjustments = [row for row in adjustments if str(row.get("created_at_utc", ""))[:7] == period]
    period_amount = sum(_num(row.get("amount")) for row in period_adjustments)

    st.divider()
    st.markdown("### Postcontrol de anulaciones")
    metrics = st.columns(5)
    metrics[0].metric("SLA vencidos", str(len(overdue)))
    metrics[1].metric("Ajustes sin cierre", str(len(open_items)))
    metrics[2].metric("Planes abiertos", str(len(open_plans)))
    metrics[3].metric("Sin evidencia", str(len(missing_evidence)))
    metrics[4].metric("Impacto mes", format_money(period_amount, get_currency()))

    if overdue:
        st.error("Hay solicitudes de anulación vencidas según SLA.")
    if missing_evidence:
        st.warning("Hay anulaciones sin evidencia registrada.")

    sla_tab, plan_tab, closeout_tab, impact_tab, cases_tab = st.tabs(("SLA", "Planes", "Cierre documental", "Impacto", "Casos"))

    with sla_tab:
        with st.form("adjustment_sla_rules_form"):
            cols = st.columns(4)
            high = cols[0].number_input("Riesgo alto horas", min_value=1, value=int(_num(rules.get("high_hours"), 4)), step=1)
            medium = cols[1].number_input("Riesgo medio horas", min_value=1, value=int(_num(rules.get("medium_hours"), 12)), step=1)
            low = cols[2].number_input("Riesgo bajo horas", min_value=1, value=int(_num(rules.get("low_hours"), 24)), step=1)
            max_open = cols[3].number_input("Máx. sin cerrar", min_value=0, value=int(_num(rules.get("max_unclosed_adjustments"), 0)), step=1)
            submitted = st.form_submit_button("Guardar reglas", type="primary", use_container_width=True)
        if submitted:
            _save("adjustment_sla_rules", [{"high_hours": int(high), "medium_hours": int(medium), "low_hours": int(low), "max_unclosed_adjustments": int(max_open), "updated_at_utc": _now()}])
            st.rerun()
        for request in reversed(active_requests[-100:]):
            due = _due_at(request, rules)
            late = due is not None and due < now
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{request.get('request_id', '')} · {request.get('kind', '')} · {request.get('reference_id', '')}**")
                cols[0].caption(f"Riesgo {request.get('risk', '')} · vence {due.isoformat() if due else 'Sin fecha'}")
                cols[1].metric("Estado", str(request.get("status", "")))
                cols[2].metric("SLA", "Vencido" if late else "Activo")

    with plan_tab:
        if not adjustments:
            st.info("No hay ajustes para planificar.")
        else:
            options = {f"{row.get('kind')} · {row.get('reference_id')} · {format_money(_num(row.get('amount')), get_currency())}": row for row in adjustments[-300:]}
            with st.form("adjustment_action_plan_form", clear_on_submit=True):
                selected = st.selectbox("Ajuste", tuple(options.keys()))
                action = st.text_area("Acción correctiva", max_chars=600)
                responsible = st.text_input("Responsable")
                due_date = st.date_input("Fecha compromiso", value=date.today() + timedelta(days=2))
                priority = st.selectbox("Prioridad", ("Alta", "Media", "Baja"))
                submitted = st.form_submit_button("Crear plan", type="primary", use_container_width=True)
            if submitted:
                if not action.strip() or not responsible.strip():
                    st.error("Acción y responsable son obligatorios.")
                else:
                    row = options[selected]
                    plans.append({"plan_id": f"ADP-{uuid4().hex[:8].upper()}", "adjustment_id": _adjustment_key(row), "reference_id": row.get("reference_id", ""), "action": action.strip(), "responsible": responsible.strip(), "due_date": due_date.isoformat(), "priority": priority, "status": "Abierto", "created_at_utc": _now()})
                    _save("adjustment_action_plans", plans)
                    st.rerun()
        st.download_button("Descargar planes CSV", data=_export_plans(plans), file_name="planes_anulaciones_ajustes.csv", mime="text/csv", use_container_width=True, disabled=not plans)
        for plan in reversed(plans[-100:]):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{plan.get('plan_id')} · ajuste {plan.get('adjustment_id')}**")
                cols[0].caption(f"{plan.get('priority')} · {plan.get('responsible')} · vence {plan.get('due_date')}")
                cols[1].metric("Estado", str(plan.get("status", "")))
                if cols[2].button("Completar", key=f"complete_adjustment_plan_{plan.get('plan_id')}", use_container_width=True, disabled=plan.get("status") == "Completado"):
                    changed = []
                    for item in plans:
                        current = dict(item)
                        if current.get("plan_id") == plan.get("plan_id"):
                            current["status"] = "Completado"
                            current["completed_at_utc"] = _now()
                        changed.append(current)
                    _save("adjustment_action_plans", changed)
                    st.rerun()

    with closeout_tab:
        if not open_items:
            st.success("No hay ajustes pendientes de cierre documental.")
        for row in open_items[-100:]:
            adjustment_id = _adjustment_key(row)
            pending_plans = sum(1 for plan in plans if plan.get("adjustment_id") == adjustment_id and plan.get("status") != "Completado")
            evidence_count = _evidence_count(adjustment_id)
            with st.container(border=True):
                st.markdown(f"**{row.get('kind')} · {row.get('reference_id')}**")
                st.caption(f"Planes pendientes: {pending_plans} · evidencias: {evidence_count}")
                with st.form(f"adjustment_closeout_{adjustment_id}"):
                    reviewer = st.text_input("Revisado por", key=f"closeout_reviewer_{adjustment_id}")
                    conclusion = st.text_area("Conclusión", max_chars=700, key=f"closeout_conclusion_{adjustment_id}")
                    confirmed = st.checkbox("Confirmo que el ajuste quedó documentado", key=f"closeout_confirm_{adjustment_id}")
                    submitted = st.form_submit_button("Cerrar documentalmente", type="primary", use_container_width=True)
                if submitted:
                    if not reviewer.strip() or not conclusion.strip() or not confirmed:
                        st.error("Revisor, conclusión y confirmación son obligatorios.")
                    elif pending_plans:
                        st.error("No se puede cerrar mientras existan planes pendientes.")
                    elif evidence_count == 0:
                        st.error("Registra al menos una evidencia antes de cerrar.")
                    else:
                        closeouts.append({"closeout_id": f"ADC-{uuid4().hex[:8].upper()}", "adjustment_id": adjustment_id, "reference_id": row.get("reference_id", ""), "reviewer": reviewer.strip(), "conclusion": conclusion.strip(), "created_at_utc": _now()})
                        _save("adjustment_closeouts", closeouts)
                        st.rerun()
        for item in reversed(closeouts[-50:]):
            st.success(f"{item.get('closeout_id')} · ajuste {item.get('adjustment_id')} · {item.get('reviewer')}")

    with impact_tab:
        if st.button("Crear corte de impacto", type="primary", use_container_width=True):
            snapshots.append({"snapshot_id": f"AIS-{uuid4().hex[:8].upper()}", "period": period, "adjustments": len(period_adjustments), "amount": period_amount, "open_adjustments": len(open_items), "missing_evidence": len(missing_evidence), "open_plans": len(open_plans), "created_at_utc": _now()})
            _save("adjustment_impact_snapshots", snapshots)
            st.rerun()
        for item in reversed(snapshots[-50:]):
            st.write(f"**{item.get('snapshot_id')} · {item.get('period')}** · impacto {format_money(_num(item.get('amount')), get_currency())} · abiertos {item.get('open_adjustments')}")

    with cases_tab:
        with st.form("adjustment_followup_case_form", clear_on_submit=True):
            case_type = st.selectbox("Tipo", ("Cliente reclama", "Proveedor reclama", "Inventario descuadrado", "Caja descuadrada", "Falta evidencia", "Otro"))
            responsible = st.text_input("Responsable")
            description = st.text_area("Descripción", max_chars=700)
            submitted = st.form_submit_button("Abrir caso", type="primary", use_container_width=True)
        if submitted:
            if not responsible.strip() or not description.strip():
                st.error("Responsable y descripción son obligatorios.")
            else:
                cases.append({"case_id": f"ADF-{uuid4().hex[:8].upper()}", "case_type": case_type, "period": period, "responsible": responsible.strip(), "description": description.strip(), "status": "Abierto", "created_at_utc": _now()})
                _save("adjustment_followup_cases", cases)
                st.rerun()
        for item in reversed(cases[-100:]):
            with st.container(border=True):
                st.markdown(f"**{item.get('case_id')} · {item.get('case_type')} · {item.get('status')}**")
                st.caption(f"{item.get('period')} · {item.get('responsible')}")
                st.write(item.get("description", ""))
                if item.get("status") != "Cerrado" and st.button("Cerrar caso", key=f"close_adjustment_followup_{item.get('case_id')}", use_container_width=True):
                    changed = []
                    for case in cases:
                        current = dict(case)
                        if current.get("case_id") == item.get("case_id"):
                            current["status"] = "Cerrado"
                            current["closed_at_utc"] = _now()
                        changed.append(current)
                    _save("adjustment_followup_cases", changed)
                    st.rerun()

    render_info_card("Ciclo cerrado", "La anulación no termina al revertir: ahora se mide por SLA, plan, evidencia, cierre documental e impacto.", "POSTCONTROL")


app_shell.FUNCTIONAL_MODULES["Anulaciones y ajustes"] = render_adjustments_postcontrol
