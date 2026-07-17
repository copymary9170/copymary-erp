"""Mantenimiento preventivo de máquinas para CopyMary ERP.

Cuarto y último gap de la revisión de negocio (dueña + finanzas +
producción): `production_machines` ya existe (para costeo, ver
bom_costing.py), con costo de depreciación por hora — pero no hay
calendario de mantenimiento ni alerta de máquina atrasada. Para un taller
con sublimadora/plotter/impresoras, una máquina sin mantenimiento
preventivo falla en el peor momento (un pedido grande) y sale más caro que
el mantenimiento mismo.

Alcance: planes de mantenimiento por máquina (tarea + frecuencia en días),
con próxima fecha calculada automáticamente, y bitácora de mantenimientos
realizados con su costo. No reemplaza el manual del fabricante de cada
máquina — la frecuencia recomendada debe salir de ahí, este módulo solo
ayuda a no perderla de vista.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database, record_audit_event
from src.money import format_money

TASK_SUGGESTIONS = ("Limpieza de cabezales", "Cambio de cuchilla", "Lubricación", "Calibración", "Revisión eléctrica", "Otro")

# Unidades de uso típicas del taller (el desgaste real es por trabajo, no por
# calendario): una cuchilla se gasta por metros cortados, un cabezal por
# páginas, una prensa por planchados.
USAGE_METRICS = ("", "Páginas impresas", "Metros de corte", "Cortes", "Planchados", "Horas de uso", "Metros laminados")

# Tareas estándar por tipo de equipo de CopyMary, con la frecuencia típica y,
# cuando el desgaste es por uso, la unidad, cada cuánto y el repuesto que se
# cambia. Es un punto de partida con criterio de taller — la frecuencia real
# debe ajustarse al manual de cada máquina y al ritmo de trabajo. frequency_days
# = 0 significa "no va por calendario, va por uso".
EQUIPMENT_PRESETS: dict[str, tuple[dict, ...]] = {
    "Plotter de corte (Cameo / Silhouette)": (
        {"task_name": "Cambiar cuchilla", "frequency_days": 0, "usage_metric": "Metros de corte", "usage_frequency": 500.0, "wear_part": "Cuchilla"},
        {"task_name": "Cambiar tapete / base de corte", "frequency_days": 0, "usage_metric": "Cortes", "usage_frequency": 40.0, "wear_part": "Tapete de corte"},
        {"task_name": "Limpiar rieles y carro", "frequency_days": 30, "usage_metric": "", "usage_frequency": 0.0, "wear_part": ""},
    ),
    "Impresora de sublimación (tanque / EcoTank)": (
        {"task_name": "Test de inyectores / limpieza de cabezales", "frequency_days": 14, "usage_metric": "", "usage_frequency": 0.0, "wear_part": ""},
        {"task_name": "Purga y agitación de tinta de sublimación", "frequency_days": 30, "usage_metric": "", "usage_frequency": 0.0, "wear_part": ""},
        {"task_name": "Cambiar almohadilla de tinta residual (waste pad)", "frequency_days": 0, "usage_metric": "Páginas impresas", "usage_frequency": 15000.0, "wear_part": "Almohadilla de tinta residual"},
    ),
    "Prensa / plancha térmica": (
        {"task_name": "Calibrar temperatura", "frequency_days": 60, "usage_metric": "", "usage_frequency": 0.0, "wear_part": ""},
        {"task_name": "Revisar presión y resistencia", "frequency_days": 0, "usage_metric": "Planchados", "usage_frequency": 2000.0, "wear_part": "Resistencia"},
    ),
    "Laminadora / plastificadora": (
        {"task_name": "Limpiar rodillos", "frequency_days": 30, "usage_metric": "", "usage_frequency": 0.0, "wear_part": ""},
        {"task_name": "Revisar rodillos y temperatura", "frequency_days": 0, "usage_metric": "Metros laminados", "usage_frequency": 3000.0, "wear_part": "Rodillos"},
    ),
}

# El orden importa: las palabras específicas del dispositivo (prensa,
# laminadora, cameo/corte) se evalúan antes que "sublimación", que es una
# palabra amplia del proceso y aparece también en la categoría de una prensa
# o una laminadora del taller.
_PRESET_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Prensa / plancha térmica", ("prensa", "plancha", "térmic", "termic", "calor")),
    ("Laminadora / plastificadora", ("lamin", "plastific", "rodillo")),
    ("Plotter de corte (Cameo / Silhouette)", ("cameo", "silhouette", "plotter", "corte", "vinil")),
    ("Impresora de sublimación (tanque / EcoTank)", ("sublim", "impres", "ecotank", "tanque", "epson")),
)


def preset_group_for_machine(machine_name: str, machine_category: str) -> str:
    """Elige el grupo de tareas estándar más apropiado según palabras clave en
    el nombre y la categoría de la máquina. '' si no reconoce el tipo."""
    text = f"{machine_name} {machine_category}".casefold()
    for group, keywords in _PRESET_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return group
    return ""


def presets_for_machine(machine_name: str, machine_category: str) -> tuple[dict, ...]:
    """Tareas sugeridas para una máquina. Si no se reconoce el tipo, ofrece
    todo el catálogo como referencia."""
    group = preset_group_for_machine(machine_name, machine_category)
    if group:
        return EQUIPMENT_PRESETS[group]
    return tuple(preset for presets in EQUIPMENT_PRESETS.values() for preset in presets)


# ---------------------------------------------------------------------------
# Cálculo puro (testeable sin base de datos)
# ---------------------------------------------------------------------------

def days_until_due(plan: dict, as_of: date) -> int:
    """Días hasta el vencimiento. Negativo si ya está atrasado."""
    due_date = date.fromisoformat(str(plan["next_due_date"]))
    return (due_date - as_of).days


def is_overdue(plan: dict, as_of: date) -> bool:
    return days_until_due(plan, as_of) < 0


def is_due_soon(plan: dict, as_of: date, within_days: int = 7) -> bool:
    remaining = days_until_due(plan, as_of)
    return 0 <= remaining <= within_days


def overdue_plans(plans: list[dict], as_of: date) -> list[dict]:
    return [plan for plan in plans if plan.get("active") and is_overdue(plan, as_of)]


def due_soon_plans(plans: list[dict], as_of: date, within_days: int = 7) -> list[dict]:
    return [plan for plan in plans if plan.get("active") and is_due_soon(plan, as_of, within_days)]


def next_due_date_after(performed_date: date, frequency_days: int) -> date:
    return performed_date + timedelta(days=frequency_days)


# --- Desgaste por USO (además de por tiempo) -------------------------------

def usage_until_due(plan: dict) -> float | None:
    """Unidades de uso que faltan para el próximo servicio. None si el plan no
    tiene disparador por uso (solo por tiempo). Negativo = vencido por uso."""
    frequency = float(plan.get("usage_frequency") or 0)
    if frequency <= 0:
        return None
    return float(plan.get("next_due_usage") or 0) - float(plan.get("current_usage") or 0)


def is_overdue_by_usage(plan: dict) -> bool:
    remaining = usage_until_due(plan)
    return remaining is not None and remaining <= 0


def is_due_soon_by_usage(plan: dict, within_fraction: float = 0.1) -> bool:
    """Próximo a vencer por uso: queda una fracción pequeña del intervalo."""
    remaining = usage_until_due(plan)
    if remaining is None or remaining <= 0:
        return False
    frequency = float(plan.get("usage_frequency") or 0)
    return remaining <= frequency * within_fraction


def next_due_usage_after(usage_at_service: float, usage_frequency: float) -> float:
    return usage_at_service + usage_frequency


# --- Estado combinado: lo que ocurra primero (tiempo o uso) ----------------

def is_overdue_combined(plan: dict, as_of: date) -> bool:
    """Vencido por lo que ocurra primero: por tiempo O por uso."""
    return is_overdue(plan, as_of) or is_overdue_by_usage(plan)


def is_due_soon_combined(plan: dict, as_of: date, within_days: int = 7, within_fraction: float = 0.1) -> bool:
    if is_overdue_combined(plan, as_of):
        return False
    return is_due_soon(plan, as_of, within_days) or is_due_soon_by_usage(plan, within_fraction)


def overdue_plans_combined(plans: list[dict], as_of: date) -> list[dict]:
    return [plan for plan in plans if plan.get("active") and is_overdue_combined(plan, as_of)]


def due_soon_plans_combined(plans: list[dict], as_of: date, within_days: int = 7) -> list[dict]:
    return [plan for plan in plans if plan.get("active") and is_due_soon_combined(plan, as_of, within_days)]


def plan_alert(plan: dict, as_of: date) -> tuple[str, str]:
    """(nivel, razón) para la interfaz. nivel ∈ {'overdue','due_soon','ok'}.
    La razón dice si el disparador fue el tiempo o el uso — lo que ocurra
    primero — para que el reparador sepa por qué toca el mantenimiento."""
    time_over = is_overdue(plan, as_of)
    usage_over = is_overdue_by_usage(plan)
    if time_over or usage_over:
        if time_over and usage_over:
            return "overdue", "Atrasado por tiempo y por uso"
        if time_over:
            return "overdue", f"Atrasado {-days_until_due(plan, as_of)} día(s)"
        metric = str(plan.get("usage_metric") or "uso").lower()
        return "overdue", f"Atrasado por uso ({metric})"
    if is_due_soon_combined(plan, as_of):
        if is_due_soon_by_usage(plan):
            remaining_usage = usage_until_due(plan) or 0.0
            metric = str(plan.get("usage_metric") or "uso").lower()
            return "due_soon", f"Faltan {remaining_usage:,.0f} de {metric}"
        return "due_soon", f"Vence en {days_until_due(plan, as_of)} día(s)"
    return "ok", ""


# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------

def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_machines() -> list[dict]:
    return _fetch_all("SELECT * FROM production_machines WHERE active = 1 ORDER BY name")


def list_plans() -> list[dict]:
    return _fetch_all(
        """
        SELECT mp.*, m.name AS machine_name
        FROM maintenance_plans mp JOIN production_machines m ON m.machine_id = mp.machine_id
        ORDER BY mp.next_due_date
        """
    )


_NO_TIME_TRIGGER_DATE = "9999-12-31"  # plan solo por uso: fecha lejana para no marcar atraso por tiempo


def create_plan(
    machine_id: str,
    task_name: str,
    frequency_days: int,
    notes: str = "",
    usage_metric: str = "",
    usage_frequency: float = 0.0,
    current_usage: float = 0.0,
) -> str:
    """Crea un plan de mantenimiento por tiempo, por uso, o por ambos (lo que
    ocurra primero). `frequency_days` <= 0 crea un plan que va solo por uso."""
    initialize_database()
    plan_id = f"MNT-{uuid4().hex[:8].upper()}"
    if frequency_days and frequency_days > 0:
        next_due = next_due_date_after(date.today(), frequency_days).isoformat()
    else:
        next_due = _NO_TIME_TRIGGER_DATE
    next_due_usage = next_due_usage_after(current_usage, usage_frequency) if usage_frequency > 0 else 0.0
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO maintenance_plans(
                plan_id, machine_id, task_name, frequency_days, last_done_date, next_due_date, notes,
                usage_metric, usage_frequency, last_done_usage, next_due_usage, current_usage, active, created_at_utc
            )
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                plan_id, machine_id, task_name.strip(), int(frequency_days or 0), next_due, notes.strip(),
                usage_metric.strip(), float(usage_frequency), float(current_usage), float(next_due_usage),
                float(current_usage), date.today().isoformat(),
            ),
        )
    return plan_id


def update_usage_reading(plan_id: str, current_usage: float) -> None:
    """Actualiza la lectura del contador de uso de un plan (páginas, metros,
    planchados…) sin registrar un mantenimiento — para que la alerta por uso
    refleje el trabajo acumulado desde el último servicio."""
    initialize_database()
    with connect() as conn:
        conn.execute(
            "UPDATE maintenance_plans SET current_usage = ? WHERE plan_id = ?",
            (float(current_usage), plan_id),
        )


def logs_for_plan(plan_id: str) -> list[dict]:
    return _fetch_all("SELECT * FROM maintenance_logs WHERE plan_id = ? ORDER BY performed_date DESC", (plan_id,))


def all_maintenance_logs() -> list[dict]:
    """Todos los mantenimientos preventivos registrados (de todas las máquinas
    y planes), para poder agregarlos en reportes como el Estado de Resultados.

    Cada registro trae `performed_date` y `cost`. Es la tercera fuente de gasto
    de mantenimiento del sistema (además de las dos bitácoras por activo en el
    módulo de Activos) y la única respaldada en base de datos."""
    return _fetch_all("SELECT * FROM maintenance_logs ORDER BY performed_date DESC")


def register_maintenance(
    plan_id: str,
    machine_id: str,
    performed_date: str,
    frequency_days: int,
    performed_by: str = "",
    cost: float = 0.0,
    notes: str = "",
    usage_at_service: float | None = None,
) -> str:
    """Registra un mantenimiento realizado y reprograma automáticamente el
    próximo, tanto por tiempo (performed_date + frequency_days) como por uso
    (lectura del contador al hacer el servicio + frecuencia por uso del plan).

    `usage_at_service` es la lectura del contador (páginas, metros, planchados)
    al momento del servicio; si no se indica, se conserva la lectura actual
    del plan."""
    initialize_database()
    log_id = f"LOG-{uuid4().hex[:8].upper()}"
    if frequency_days and frequency_days > 0:
        next_due = next_due_date_after(date.fromisoformat(performed_date), frequency_days).isoformat()
    else:
        next_due = _NO_TIME_TRIGGER_DATE
    with connect() as conn:
        plan_row = conn.execute(
            "SELECT usage_frequency, current_usage FROM maintenance_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        usage_frequency = float(plan_row["usage_frequency"]) if plan_row else 0.0
        if usage_at_service is not None:
            service_usage = float(usage_at_service)
        else:
            service_usage = float(plan_row["current_usage"]) if plan_row else 0.0
        next_due_usage = next_due_usage_after(service_usage, usage_frequency) if usage_frequency > 0 else 0.0
        conn.execute(
            "INSERT INTO maintenance_logs(log_id, plan_id, machine_id, performed_date, performed_by, cost, notes, usage_at_service, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (log_id, plan_id, machine_id, performed_date, performed_by.strip(), cost, notes.strip(), service_usage, date.today().isoformat()),
        )
        conn.execute(
            "UPDATE maintenance_plans SET last_done_date = ?, next_due_date = ?, last_done_usage = ?, next_due_usage = ?, current_usage = ? WHERE plan_id = ?",
            (performed_date, next_due, service_usage, next_due_usage, service_usage, plan_id),
        )
    record_audit_event("produccion", "maintenance_plans", plan_id, "maintenance_done", after={"performed_date": performed_date, "cost": cost, "usage_at_service": service_usage})
    return log_id


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def _usage_caption(plan: dict) -> str:
    """Resumen legible del disparador por uso de un plan, o '' si no tiene."""
    remaining = usage_until_due(plan)
    if remaining is None:
        return ""
    metric = str(plan.get("usage_metric") or "uso")
    current = float(plan.get("current_usage") or 0)
    target = float(plan.get("next_due_usage") or 0)
    return f"Uso: {current:,.0f} / {target:,.0f} {metric.lower()} (faltan {remaining:,.0f})"


def _render_create_plan(machines: list[dict], has_plans: bool) -> None:
    machine_options = {machine["name"]: machine for machine in machines}
    with st.expander("Crear plan de mantenimiento", expanded=not has_plans):
        # Máquina y preset van FUERA del form para poder sugerir la tarea del
        # equipo y prellenar frecuencias antes de enviar.
        machine_label = st.selectbox("Máquina", tuple(machine_options.keys()), key="mnt_new_machine")
        machine = machine_options[machine_label]
        presets = presets_for_machine(machine["name"], machine.get("category", ""))

        def _preset_label(index: int) -> str:
            if index == 0:
                return "Personalizado (definir a mano)"
            preset = presets[index - 1]
            if preset["usage_frequency"]:
                trigger = f"cada {preset['usage_frequency']:,.0f} {preset['usage_metric'].lower()}"
            else:
                trigger = f"cada {preset['frequency_days']} días"
            return f"{preset['task_name']} · {trigger}"

        preset_index = st.selectbox(
            "Tarea sugerida para este equipo",
            range(len(presets) + 1),
            format_func=_preset_label,
            key="mnt_new_preset",
            help="Tareas típicas del taller para este tipo de máquina. Elige una y ajusta, o usa 'Personalizado'.",
        )
        chosen = presets[preset_index - 1] if preset_index > 0 else None
        if chosen and chosen["wear_part"]:
            st.caption(f"Repuesto que se cambia: **{chosen['wear_part']}**")

        with st.form("plan_form"):
            default_task = chosen["task_name"] if chosen else ""
            task_name = st.text_input("Tarea", value=default_task, key="mnt_new_task")

            st.markdown("**¿Cuándo toca?** Por tiempo, por uso, o ambos — avisa por lo que ocurra primero.")
            time_col, usage_col = st.columns(2)
            default_days = chosen["frequency_days"] if chosen else 30
            frequency_days = time_col.number_input(
                "Cada … días (0 = no va por calendario)", min_value=0,
                value=int(default_days), step=1, key="mnt_new_days",
            )
            default_metric = chosen["usage_metric"] if chosen else ""
            metric_index = USAGE_METRICS.index(default_metric) if default_metric in USAGE_METRICS else 0
            usage_metric = usage_col.selectbox("Unidad de uso (opcional)", USAGE_METRICS, index=metric_index, key="mnt_new_metric")

            freq_col, reading_col = st.columns(2)
            default_usage_freq = chosen["usage_frequency"] if chosen else 0.0
            usage_frequency = freq_col.number_input(
                "Cada … (unidades de uso)", min_value=0.0, value=float(default_usage_freq),
                step=10.0, disabled=not usage_metric, key="mnt_new_usage_freq",
            )
            current_usage = reading_col.number_input(
                "Lectura de uso actual del contador", min_value=0.0, value=0.0,
                step=10.0, disabled=not usage_metric, key="mnt_new_usage_now",
            )
            notes = st.text_area("Notas (opcional)", key="mnt_new_notes")
            submitted = st.form_submit_button("Crear plan", type="primary", use_container_width=True)

        if submitted:
            if not task_name.strip():
                st.error("Indica la tarea de mantenimiento.")
            elif frequency_days <= 0 and (not usage_metric or usage_frequency <= 0):
                st.error("Define al menos un disparador: una frecuencia en días o una frecuencia por uso.")
            else:
                create_plan(
                    machine["machine_id"], task_name, int(frequency_days), notes,
                    usage_metric=usage_metric if usage_metric else "",
                    usage_frequency=float(usage_frequency) if usage_metric else 0.0,
                    current_usage=float(current_usage) if usage_metric else 0.0,
                )
                st.success("Plan de mantenimiento creado.")
                st.rerun()


def render_machine_maintenance() -> None:
    render_page_header("Mantenimiento preventivo", "Mantenimiento por tiempo y por uso — avisa por lo que ocurra primero.")
    st.caption(
        "El equipo del taller se desgasta por trabajo, no por calendario: una cuchilla por metros "
        "cortados, un cabezal por páginas, una prensa por planchados. Define la frecuencia como te sirva."
    )

    machines = list_machines()
    if not machines:
        st.info("Registra máquinas en Costeo por procesos antes de crear planes de mantenimiento.")
        return

    plans = list_plans()
    today = date.today()
    overdue = overdue_plans_combined(plans, today)
    due_soon = due_soon_plans_combined(plans, today)

    cols = st.columns(3)
    cols[0].metric("Planes activos", str(len([plan for plan in plans if plan.get("active")])))
    cols[1].metric("Atrasados", str(len(overdue)))
    cols[2].metric("Próximos a vencer", str(len(due_soon)))

    if overdue:
        st.error(f"{len(overdue)} mantenimiento(s) atrasado(s): " + ", ".join(f"{plan['machine_name']} · {plan['task_name']}" for plan in overdue))
    elif due_soon:
        st.warning(f"{len(due_soon)} mantenimiento(s) próximos a vencer (por tiempo o por uso).")
    else:
        st.success("No hay mantenimientos atrasados ni próximos a vencer.")

    _render_create_plan(machines, has_plans=bool(plans))

    for plan in plans:
        with st.container(border=True):
            level, reason = plan_alert(plan, today)
            cols = st.columns([3, 3, 2])
            cols[0].markdown(f"**{plan['machine_name']}** · {plan['task_name']}")
            trigger_bits = []
            if int(plan.get("frequency_days") or 0) > 0:
                trigger_bits.append(f"cada {plan['frequency_days']} días")
            usage_caption = _usage_caption(plan)
            if usage_caption:
                trigger_bits.append(usage_caption)
            cols[0].caption(" · ".join(trigger_bits) if trigger_bits else "sin disparador")

            if level == "overdue":
                cols[1].error(reason)
            elif level == "due_soon":
                cols[1].warning(reason)
            else:
                cols[1].success(reason or "En regla")

            with cols[2].popover("Registrar / actualizar"):
                has_usage = usage_until_due(plan) is not None
                if has_usage:
                    with st.form(f"usage_form_{plan['plan_id']}", clear_on_submit=True):
                        st.caption(f"Lectura actual del contador ({plan.get('usage_metric', 'uso')})")
                        new_reading = st.number_input("Uso actual", min_value=0.0, value=float(plan.get("current_usage") or 0), step=10.0, key=f"reading_{plan['plan_id']}")
                        if st.form_submit_button("Actualizar lectura"):
                            update_usage_reading(plan["plan_id"], new_reading)
                            st.rerun()
                with st.form(f"log_form_{plan['plan_id']}", clear_on_submit=True):
                    performed_date = st.date_input("Fecha realizada", value=today, key=f"date_{plan['plan_id']}")
                    performed_by = st.text_input("Realizado por", key=f"by_{plan['plan_id']}")
                    cost = st.number_input("Costo", min_value=0.0, step=1.0, key=f"cost_{plan['plan_id']}")
                    usage_at_service = None
                    if has_usage:
                        usage_at_service = st.number_input(
                            f"Lectura de uso al hacer el servicio ({plan.get('usage_metric', 'uso')})",
                            min_value=0.0, value=float(plan.get("current_usage") or 0), step=10.0, key=f"usvc_{plan['plan_id']}",
                        )
                    log_notes = st.text_input("Notas", key=f"notes_{plan['plan_id']}")
                    log_submitted = st.form_submit_button("Registrar mantenimiento", type="primary")
                if log_submitted:
                    register_maintenance(
                        plan["plan_id"], plan["machine_id"], performed_date.isoformat(), int(plan.get("frequency_days") or 0),
                        performed_by, cost, log_notes, usage_at_service=usage_at_service,
                    )
                    st.success("Mantenimiento registrado. Próximo servicio reprogramado por tiempo y por uso.")
                    st.rerun()

            logs = logs_for_plan(plan["plan_id"])
            if logs:
                total_cost = sum(float(log.get("cost", 0.0)) for log in logs)
                st.caption(f"Último: {logs[0]['performed_date']} · {len(logs)} mantenimiento(s) registrados · {format_money(total_cost)} acumulado")

    render_info_card(
        "Alcance",
        "Mantenimiento por tiempo y por uso (lo que ocurra primero), con tareas sugeridas por tipo de equipo. "
        "No reemplaza el manual del fabricante — la frecuencia real sale de ahí y del ritmo de trabajo.",
        "PRODUCCIÓN",
    )


app_shell.FUNCTIONAL_MODULES["Mantenimiento preventivo"] = render_machine_maintenance
