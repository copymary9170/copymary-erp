"""Gobierno avanzado de activos productivos."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import csv
import io

import streamlit as st

from src import app_shell, assets as base, session_backup
from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency


def _activate_backup() -> None:
    for section, label in (
        ("asset_profiles", "Perfiles administrativos de activos"),
        ("asset_maintenance_plans", "Planes de mantenimiento de activos"),
        ("asset_maintenance_logs", "Bitácora de mantenimiento de activos"),
        ("asset_inspections", "Inspecciones de activos"),
        ("asset_replacement_plans", "Planes de reposición de activos"),
        ("asset_incidents", "Incidencias de activos"),
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
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _asset_rows() -> list[dict]:
    rows = []
    for asset in base._get_assets():
        rows.append({
            "asset_id": asset.asset_id,
            "name": asset.name,
            "category": asset.category,
            "acquisition_cost": asset.acquisition_cost,
            "lifetime_units": asset.lifetime_units,
            "current_units": asset.current_units,
            "usage_percent": asset.usage_percent,
            "remaining_value": asset.remaining_value,
            "depreciation_per_unit": asset.depreciation_per_unit,
            "accumulated_depreciation": asset.accumulated_depreciation,
        })
    return rows


def _asset_name(asset_id: str, assets: list[dict]) -> str:
    for asset in assets:
        if str(asset.get("asset_id", "")) == asset_id:
            return str(asset.get("name", "Activo"))
    return "Activo"


def _profile(asset_id: str, profiles: list[dict]) -> dict:
    for row in reversed(profiles):
        if str(row.get("asset_id", "")) == asset_id and row.get("active", True):
            return row
    return {}


def _latest_maintenance(asset_id: str, logs: list[dict]) -> dict:
    candidates = [row for row in logs if str(row.get("asset_id", "")) == asset_id]
    return sorted(candidates, key=lambda row: str(row.get("maintenance_date", row.get("created_at_utc", ""))), reverse=True)[0] if candidates else {}


def _next_due(asset_id: str, plans: list[dict], logs: list[dict]) -> tuple[str, int | None]:
    plan = next((row for row in reversed(plans) if str(row.get("asset_id", "")) == asset_id and row.get("active", True)), None)
    if plan is None:
        return "Sin plan", None
    last = _latest_maintenance(asset_id, logs)
    start = str(last.get("maintenance_date", plan.get("start_date", date.today().isoformat())))[:10]
    try:
        due = date.fromisoformat(start) + timedelta(days=int(_num(plan.get("frequency_days"), 30)))
    except ValueError:
        due = date.today()
    return due.isoformat(), (due - date.today()).days


def _risk(asset: dict, profiles: list[dict], plans: list[dict], logs: list[dict], incidents: list[dict]) -> tuple[str, list[str]]:
    warnings = []
    usage = _num(asset.get("usage_percent"))
    if usage >= 90:
        warnings.append("Uso superior al 90% de la vida útil.")
    elif usage >= 75:
        warnings.append("Uso superior al 75% de la vida útil.")
    due_label, due_days = _next_due(str(asset.get("asset_id", "")), plans, logs)
    if due_days is not None and due_days < 0:
        warnings.append(f"Mantenimiento vencido desde {due_label}.")
    if not _profile(str(asset.get("asset_id", "")), profiles):
        warnings.append("Falta perfil administrativo: responsable, ubicación o garantía.")
    open_incidents = [row for row in incidents if row.get("asset_id") == asset.get("asset_id") and row.get("status") != "Cerrada"]
    if open_incidents:
        warnings.append("Tiene incidencias abiertas.")
    if any("vencido" in item.casefold() or "90%" in item for item in warnings) or len(warnings) >= 3:
        return "Alto", warnings
    if warnings:
        return "Medio", warnings
    return "Bajo", warnings


def _export_assets(assets: list[dict], profiles: list[dict], plans: list[dict], logs: list[dict], incidents: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Activo", "Categoría", "Costo", "Uso %", "Valor pendiente", "Responsable", "Ubicación", "Riesgo", "Alertas"])
    for asset in assets:
        profile = _profile(str(asset.get("asset_id", "")), profiles)
        risk, warnings = _risk(asset, profiles, plans, logs, incidents)
        writer.writerow([
            asset.get("asset_id", ""), asset.get("name", ""), asset.get("category", ""), asset.get("acquisition_cost", 0),
            asset.get("usage_percent", 0), asset.get("remaining_value", 0), profile.get("responsible", ""), profile.get("location", ""), risk, " | ".join(warnings),
        ])
    return buffer.getvalue().encode("utf-8-sig")


def render_assets_governance() -> None:
    render_page_header("Activos", "Controla responsables, mantenimiento, garantías, incidencias y reposición.")

    original_header = base.render_page_header
    base.render_page_header = lambda *_args, **_kwargs: None
    try:
        base.render_assets()
    finally:
        base.render_page_header = original_header

    assets = _asset_rows()
    profiles = _rows("asset_profiles")
    plans = _rows("asset_maintenance_plans")
    logs = _rows("asset_maintenance_logs")
    inspections = _rows("asset_inspections")
    replacements = _rows("asset_replacement_plans")
    incidents = _rows("asset_incidents")
    high_risk = [asset for asset in assets if _risk(asset, profiles, plans, logs, incidents)[0] == "Alto"]
    due_soon = []
    for asset in assets:
        _label, days = _next_due(str(asset.get("asset_id", "")), plans, logs)
        if days is not None and days <= 7:
            due_soon.append(asset)
    open_incidents = [row for row in incidents if row.get("status") != "Cerrada"]

    st.divider()
    st.markdown("### Gobierno de activos")
    metrics = st.columns(5)
    metrics[0].metric("Riesgo alto", str(len(high_risk)))
    metrics[1].metric("Mant. próximos", str(len(due_soon)))
    metrics[2].metric("Incidencias abiertas", str(len(open_incidents)))
    metrics[3].metric("Valor pendiente", format_money(sum(_num(asset.get("remaining_value")) for asset in assets), get_currency()))
    metrics[4].metric("Reposiciones", str(len(replacements)))

    if high_risk:
        st.error("Hay activos en riesgo alto: revisa mantenimiento, evidencia o reposición.")
    if due_soon:
        st.warning("Hay mantenimientos vencidos o próximos a vencer.")

    profile_tab, maintenance_tab, inspection_tab, replacement_tab, incident_tab, export_tab = st.tabs(("Perfil", "Mantenimiento", "Inspección", "Reposición", "Incidencias", "Exportar"))

    with profile_tab:
        if not assets:
            st.info("Primero registra activos.")
        else:
            options = {f"{asset.get('name')} · {asset.get('asset_id')}": asset for asset in assets}
            with st.form("asset_profile_form", clear_on_submit=True):
                selected = st.selectbox("Activo", tuple(options.keys()))
                responsible = st.text_input("Responsable")
                location = st.text_input("Ubicación")
                serial = st.text_input("Serial / etiqueta")
                warranty_until = st.date_input("Garantía hasta", value=date.today() + timedelta(days=365))
                note = st.text_area("Nota", max_chars=500)
                submitted = st.form_submit_button("Guardar perfil", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not location.strip():
                    st.error("Responsable y ubicación son obligatorios.")
                else:
                    asset = options[selected]
                    for row in profiles:
                        if row.get("asset_id") == asset.get("asset_id"):
                            row["active"] = False
                            row["ended_at_utc"] = _now()
                    profiles.append({"profile_id": f"ASP-{uuid4().hex[:8].upper()}", "asset_id": asset.get("asset_id"), "responsible": responsible.strip(), "location": location.strip(), "serial": serial.strip(), "warranty_until": warranty_until.isoformat(), "note": note.strip(), "active": True, "created_at_utc": _now()})
                    _save("asset_profiles", profiles)
                    st.rerun()
        for asset in assets:
            profile = _profile(str(asset.get("asset_id", "")), profiles)
            risk, warnings = _risk(asset, profiles, plans, logs, incidents)
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{asset.get('name')}**")
                cols[0].caption(f"{profile.get('responsible', 'Sin responsable')} · {profile.get('location', 'Sin ubicación')} · garantía {profile.get('warranty_until', 'Sin garantía')}")
                cols[1].metric("Uso", f"{_num(asset.get('usage_percent')):,.1f}%")
                cols[2].metric("Riesgo", risk)
                for warning in warnings[:4]:
                    st.warning(warning)

    with maintenance_tab:
        if assets:
            options = {f"{asset.get('name')} · {asset.get('asset_id')}": asset for asset in assets}
            with st.form("asset_maintenance_plan_form", clear_on_submit=True):
                selected = st.selectbox("Activo", tuple(options.keys()), key="maintenance_plan_asset")
                frequency = st.number_input("Frecuencia días", min_value=1, value=30, step=1)
                task = st.text_area("Rutina de mantenimiento", max_chars=600)
                responsible = st.text_input("Responsable")
                submitted = st.form_submit_button("Guardar plan", type="primary", use_container_width=True)
            if submitted:
                if not task.strip() or not responsible.strip():
                    st.error("Rutina y responsable son obligatorios.")
                else:
                    asset = options[selected]
                    plans.append({"plan_id": f"AMP-{uuid4().hex[:8].upper()}", "asset_id": asset.get("asset_id"), "frequency_days": int(frequency), "task": task.strip(), "responsible": responsible.strip(), "start_date": date.today().isoformat(), "active": True, "created_at_utc": _now()})
                    _save("asset_maintenance_plans", plans)
                    st.rerun()
            with st.form("asset_maintenance_log_form", clear_on_submit=True):
                selected = st.selectbox("Activo mantenido", tuple(options.keys()), key="maintenance_log_asset")
                maintenance_date = st.date_input("Fecha", value=date.today())
                cost = st.number_input("Costo", min_value=0.0, value=0.0, step=1.0)
                detail = st.text_area("Detalle", max_chars=600)
                responsible = st.text_input("Responsable", key="maintenance_log_responsible")
                submitted = st.form_submit_button("Registrar mantenimiento", type="primary", use_container_width=True)
            if submitted:
                if not detail.strip() or not responsible.strip():
                    st.error("Detalle y responsable son obligatorios.")
                else:
                    asset = options[selected]
                    logs.append({"log_id": f"AML-{uuid4().hex[:8].upper()}", "asset_id": asset.get("asset_id"), "maintenance_date": maintenance_date.isoformat(), "cost": float(cost), "detail": detail.strip(), "responsible": responsible.strip(), "created_at_utc": _now()})
                    _save("asset_maintenance_logs", logs)
                    st.rerun()
        for asset in assets:
            due_label, days = _next_due(str(asset.get("asset_id", "")), plans, logs)
            st.write(f"**{asset.get('name')}** · próximo mantenimiento: {due_label} · {'vencido' if days is not None and days < 0 else 'en regla'}")

    with inspection_tab:
        if assets:
            options = {f"{asset.get('name')} · {asset.get('asset_id')}": asset for asset in assets}
            with st.form("asset_inspection_form", clear_on_submit=True):
                selected = st.selectbox("Activo", tuple(options.keys()), key="inspection_asset")
                condition = st.selectbox("Condición", ("Excelente", "Buena", "Regular", "Crítica"))
                reviewer = st.text_input("Revisado por")
                finding = st.text_area("Hallazgo", max_chars=600)
                submitted = st.form_submit_button("Guardar inspección", type="primary", use_container_width=True)
            if submitted:
                if not reviewer.strip() or not finding.strip():
                    st.error("Revisor y hallazgo son obligatorios.")
                else:
                    asset = options[selected]
                    inspections.append({"inspection_id": f"AIN-{uuid4().hex[:8].upper()}", "asset_id": asset.get("asset_id"), "condition": condition, "reviewer": reviewer.strip(), "finding": finding.strip(), "created_at_utc": _now()})
                    _save("asset_inspections", inspections)
                    st.rerun()
        for item in reversed(inspections[-100:]):
            st.write(f"**{_asset_name(str(item.get('asset_id', '')), assets)} · {item.get('condition')}** — {item.get('reviewer')}: {item.get('finding')}")

    with replacement_tab:
        if assets:
            options = {f"{asset.get('name')} · {asset.get('asset_id')}": asset for asset in assets}
            with st.form("asset_replacement_form", clear_on_submit=True):
                selected = st.selectbox("Activo", tuple(options.keys()), key="replacement_asset")
                target_cost = st.number_input("Costo estimado reposición", min_value=0.0, value=0.0, step=10.0)
                monthly_reserve = st.number_input("Reserva mensual", min_value=0.0, value=0.0, step=1.0)
                target_date = st.date_input("Fecha objetivo", value=date.today() + timedelta(days=365))
                responsible = st.text_input("Responsable")
                submitted = st.form_submit_button("Guardar plan de reposición", type="primary", use_container_width=True)
            if submitted:
                if target_cost <= 0 or not responsible.strip():
                    st.error("Costo objetivo y responsable son obligatorios.")
                else:
                    asset = options[selected]
                    replacements.append({"replacement_id": f"ARP-{uuid4().hex[:8].upper()}", "asset_id": asset.get("asset_id"), "target_cost": float(target_cost), "monthly_reserve": float(monthly_reserve), "target_date": target_date.isoformat(), "responsible": responsible.strip(), "status": "Activo", "created_at_utc": _now()})
                    _save("asset_replacement_plans", replacements)
                    st.rerun()
        for item in reversed(replacements[-100:]):
            st.write(f"**{_asset_name(str(item.get('asset_id', '')), assets)}** · objetivo {format_money(_num(item.get('target_cost')), get_currency())} · reserva {format_money(_num(item.get('monthly_reserve')), get_currency())}/mes · {item.get('target_date')}")

    with incident_tab:
        if assets:
            options = {f"{asset.get('name')} · {asset.get('asset_id')}": asset for asset in assets}
            with st.form("asset_incident_form", clear_on_submit=True):
                selected = st.selectbox("Activo", tuple(options.keys()), key="incident_asset")
                severity = st.selectbox("Severidad", ("Alta", "Media", "Baja"))
                responsible = st.text_input("Responsable")
                description = st.text_area("Descripción", max_chars=700)
                submitted = st.form_submit_button("Abrir incidencia", type="primary", use_container_width=True)
            if submitted:
                if not responsible.strip() or not description.strip():
                    st.error("Responsable y descripción son obligatorios.")
                else:
                    asset = options[selected]
                    incidents.append({"incident_id": f"AIC-{uuid4().hex[:8].upper()}", "asset_id": asset.get("asset_id"), "severity": severity, "responsible": responsible.strip(), "description": description.strip(), "status": "Abierta", "created_at_utc": _now()})
                    _save("asset_incidents", incidents)
                    st.rerun()
        for item in reversed(incidents[-100:]):
            with st.container(border=True):
                st.markdown(f"**{_asset_name(str(item.get('asset_id', '')), assets)} · {item.get('severity')} · {item.get('status')}**")
                st.caption(f"{item.get('responsible')} · {item.get('created_at_utc')}")
                st.write(item.get("description", ""))
                if item.get("status") != "Cerrada" and st.button("Cerrar incidencia", key=f"close_asset_incident_{item.get('incident_id')}", use_container_width=True):
                    changed = []
                    for incident in incidents:
                        current = dict(incident)
                        if current.get("incident_id") == item.get("incident_id"):
                            current["status"] = "Cerrada"
                            current["closed_at_utc"] = _now()
                        changed.append(current)
                    _save("asset_incidents", changed)
                    st.rerun()

    with export_tab:
        st.download_button("Descargar activos CSV", data=_export_assets(assets, profiles, plans, logs, incidents), file_name=f"activos_{date.today().isoformat()}.csv", mime="text/csv", use_container_width=True, disabled=not assets)
        render_info_card("Qué revisar", "Responsable, ubicación, garantía, mantenimiento, incidencias y plan de reposición ayudan a decidir cuándo invertir de nuevo.", "ACTIVOS")

    render_info_card("Activos protegidos", "El módulo ahora no solo calcula depreciación: también controla mantenimiento, incidencias, garantía y reposición.", "GOBIERNO")


app_shell.FUNCTIONAL_MODULES["Activos"] = render_assets_governance
