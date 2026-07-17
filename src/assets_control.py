"""Inteligencia de costo total de propiedad (TCO) de la flota de activos.

Capa superior del dominio de activos. Compone sobre `assets_governance`
(que ya agrega perfiles, mantenimiento, inspecciones, incidencias, garantías
y reposición) y le suma la visión financiera que faltaba: cuánto ha COSTADO
REALMENTE poseer y operar cada equipo, no solo lo que se pagó al comprarlo.

Dos aportes concretos, ambos con valor de negocio real:

1. **Unifica las DOS bitácoras de mantenimiento** que hasta ahora vivían
   separadas y no se sumaban en ninguna vista:
     - `asset_maintenance_log`  — registro en línea de `assets.py`, con
       descuento real de Inventario cuando el repuesto salía de existencias;
     - `asset_maintenance_logs` — bitácora administrativa de
       `assets_governance.py`, con responsable y detalle.
   El gasto de mantenimiento de un equipo estaba partido en dos lugares y
   ninguna pantalla lo mostraba completo. Aquí se suma por primera vez.

2. **Costo total de propiedad (TCO) y costo REAL por unidad.** El TCO es el
   costo de compra (ya con envío, aranceles e impuestos) MÁS todo lo gastado
   en mantenimiento. El costo real por unidad producida suma la depreciación
   consumida y el mantenimiento gastado, dividido entre las unidades reales —
   el número honesto de "cuánto me cuesta cada página/corte/laminado en
   términos de equipo", que la depreciación sola subestima porque ignora las
   reparaciones. Comparado con el costo por unidad planeado, revela cuándo un
   equipo se está volviendo caro de sostener.

Todas las funciones de cálculo son puras (no tocan Streamlit ni
`st.session_state`): reciben los activos y los registros ya leídos, para
poder probarse directamente. `render_assets_control` es la única que lee de
la sesión y dibuja la interfaz.
"""

from __future__ import annotations

from datetime import date
import csv
import io

import streamlit as st

from src import app_shell, assets_governance as base
from src.assets import Asset
from src.components import render_info_card
from src.money import format_money, get_currency
from src.session_utils import read_list as _rows


# Las dos bitácoras de mantenimiento que conviven en el proyecto. Ambas
# guardan al menos `asset_id` y `cost`; se combinan para no perder gasto.
MAINTENANCE_LOG_SECTIONS: tuple[str, ...] = ("asset_maintenance_log", "asset_maintenance_logs")

# Cuando el mantenimiento acumulado supera esta fracción del costo de compra,
# el equipo empieza a ser candidato a reposición en vez de seguir reparándolo.
REPLACE_SIGNAL_RATIO = 0.5


def _num(value, default: float = 0.0) -> float:
    """Convierte a float de forma tolerante (mismo criterio que governance)."""
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError, AttributeError):
        return default


# ---------------------------------------------------------------------------
# Mantenimiento unificado (las dos bitácoras combinadas)
# ---------------------------------------------------------------------------

def combine_maintenance_logs(*logs: list[dict]) -> list[dict]:
    """Une varias listas de registros de mantenimiento en una sola.

    Se usa para juntar `asset_maintenance_log` (en línea) y
    `asset_maintenance_logs` (administrativa) en una sola secuencia, sin
    perder ninguna: son fuentes distintas del mismo hecho (se gastó dinero
    manteniendo una máquina) que hasta ahora nadie sumaba junto.
    """
    combined: list[dict] = []
    for log in logs:
        for row in log:
            if isinstance(row, dict):
                combined.append(row)
    return combined


def maintenance_cost_for(asset_id: str, entries: list[dict]) -> float:
    """Costo total de mantenimiento de un activo, a partir de registros ya
    combinados de ambas bitácoras."""
    return sum(_num(row.get("cost")) for row in entries if str(row.get("asset_id", "")) == str(asset_id))


def maintenance_events_for(asset_id: str, entries: list[dict]) -> int:
    """Cuántos eventos de mantenimiento tiene registrados un activo (de
    cualquiera de las dos bitácoras)."""
    return sum(1 for row in entries if str(row.get("asset_id", "")) == str(asset_id))


# ---------------------------------------------------------------------------
# Costo total de propiedad (TCO) por activo
# ---------------------------------------------------------------------------

def total_cost_of_ownership(asset: Asset, maintenance_cost: float) -> float:
    """Costo de compra (landed) + todo lo gastado en mantenimiento a la fecha."""
    return asset.acquisition_cost + max(maintenance_cost, 0.0)


def planned_cost_per_unit(asset: Asset) -> float:
    """Costo por unidad que asume la depreciación: costo de compra repartido
    entre toda la vida útil. Es el 'plan', sin contar reparaciones."""
    if asset.lifetime_units <= 0:
        return 0.0
    return asset.acquisition_cost / asset.lifetime_units


def actual_cost_per_unit(asset: Asset, maintenance_cost: float) -> float:
    """Costo REAL por unidad producida: depreciación consumida más
    mantenimiento gastado, dividido entre las unidades realmente producidas.

    Si el equipo aún no ha producido nada, no hay costo por unidad que
    calcular (sería dividir entre cero), así que devuelve 0.0 en vez de un
    número engañosamente enorme.
    """
    if asset.current_units <= 0:
        return 0.0
    return (asset.accumulated_depreciation + max(maintenance_cost, 0.0)) / asset.current_units


def remaining_useful_units(asset: Asset) -> int:
    """Unidades de vida útil que le quedan al equipo antes de agotarse."""
    return max(asset.lifetime_units - asset.current_units, 0)


def maintenance_ratio(asset: Asset, maintenance_cost: float) -> float:
    """Qué fracción del costo de compra se ha gastado ya en mantenimiento.

    0.0 cuando no hay costo de compra registrado (equipo heredado): sin
    denominador válido, la razón no tiene sentido y no debe disparar la
    señal de reposición por sí sola.
    """
    if asset.acquisition_cost <= 0:
        return 0.0
    return max(maintenance_cost, 0.0) / asset.acquisition_cost


def should_consider_replacement(asset: Asset, maintenance_cost: float) -> bool:
    """True cuando el equipo ya gastó en reparaciones al menos la fracción
    `REPLACE_SIGNAL_RATIO` de lo que costó comprarlo: a partir de ahí suele
    convenir reponer en vez de seguir reparando."""
    return maintenance_ratio(asset, maintenance_cost) >= REPLACE_SIGNAL_RATIO


# ---------------------------------------------------------------------------
# Reporte de flota
# ---------------------------------------------------------------------------

def build_tco_report(assets: list[Asset], combined_logs: list[dict]) -> list[dict]:
    """Una fila por activo con su costo total de propiedad y métricas
    derivadas, ordenada del equipo más caro de poseer al más barato."""
    report: list[dict] = []
    for asset in assets:
        m_cost = maintenance_cost_for(asset.asset_id, combined_logs)
        report.append({
            "asset_id": asset.asset_id,
            "name": asset.name,
            "category": asset.category,
            "status": asset.status,
            "acquisition_cost": asset.acquisition_cost,
            "maintenance_cost": m_cost,
            "maintenance_events": maintenance_events_for(asset.asset_id, combined_logs),
            "tco": total_cost_of_ownership(asset, m_cost),
            "remaining_value": asset.remaining_value,
            "current_units": asset.current_units,
            "remaining_useful_units": remaining_useful_units(asset),
            "usage_percent": asset.usage_percent,
            "planned_cost_per_unit": planned_cost_per_unit(asset),
            "actual_cost_per_unit": actual_cost_per_unit(asset, m_cost),
            "maintenance_ratio": maintenance_ratio(asset, m_cost),
            "consider_replacement": should_consider_replacement(asset, m_cost),
        })
    report.sort(key=lambda row: row["tco"], reverse=True)
    return report


def fleet_totals(report: list[dict]) -> dict:
    """Totales de flota a partir del reporte de TCO."""
    return {
        "asset_count": len(report),
        "total_acquisition": sum(row["acquisition_cost"] for row in report),
        "total_maintenance": sum(row["maintenance_cost"] for row in report),
        "total_tco": sum(row["tco"] for row in report),
        "total_remaining_value": sum(row["remaining_value"] for row in report),
        "replacement_candidates": sum(1 for row in report if row["consider_replacement"]),
    }


def _export_tco(report: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Activo", "Categoría", "Estado", "Costo de compra", "Mantenimiento acumulado",
        "Eventos mant.", "Costo total de propiedad", "Valor en libros", "Unidades producidas",
        "Vida útil restante", "Costo/unidad planeado", "Costo/unidad real", "Mant. / compra",
        "Reponer",
    ])
    for row in report:
        writer.writerow([
            row["asset_id"], row["name"], row["category"], row["status"],
            f"{row['acquisition_cost']:.2f}", f"{row['maintenance_cost']:.2f}",
            row["maintenance_events"], f"{row['tco']:.2f}", f"{row['remaining_value']:.2f}",
            row["current_units"], row["remaining_useful_units"],
            f"{row['planned_cost_per_unit']:.6f}", f"{row['actual_cost_per_unit']:.6f}",
            f"{row['maintenance_ratio'] * 100:.1f}%", "Sí" if row["consider_replacement"] else "No",
        ])
    return buffer.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------

def render_assets_control() -> None:
    """Activos con gobierno completo + análisis de costo total de propiedad."""
    base.render_assets_governance()

    assets = base.base._get_assets()
    combined_logs = combine_maintenance_logs(
        _rows("asset_maintenance_log"), _rows("asset_maintenance_logs")
    )
    report = build_tco_report(assets, combined_logs)
    currency = get_currency()

    st.divider()
    st.markdown("### Costo total de propiedad (TCO)")
    st.caption(
        "Cuánto ha costado realmente cada equipo: lo que se pagó al comprarlo MÁS todo "
        "lo gastado en mantenimiento (uniendo las dos bitácoras del sistema). El costo "
        "real por unidad suma depreciación y reparaciones, y revela cuándo una máquina "
        "se está volviendo cara de sostener."
    )

    if not report:
        st.info("Registra activos arriba para ver su costo total de propiedad.")
        return

    totals = fleet_totals(report)
    top = st.columns(4)
    top[0].metric("Inversión de compra", format_money(totals["total_acquisition"], currency))
    top[1].metric("Mantenimiento acumulado", format_money(totals["total_maintenance"], currency))
    top[2].metric("Costo total de propiedad", format_money(totals["total_tco"], currency))
    top[3].metric("Candidatos a reponer", str(totals["replacement_candidates"]))

    if totals["replacement_candidates"]:
        st.warning(
            f"{totals['replacement_candidates']} equipo(s) ya gastaron en reparaciones "
            f"la mitad o más de lo que costaron: evalúa reponer en vez de seguir reparando."
        )

    for row in report:
        with st.container(border=True):
            header = st.columns([3, 1, 1])
            header[0].markdown(f"**{row['name']}**")
            header[0].caption(f"{row['category']} · {row['status']} · {row['maintenance_events']} evento(s) de mantenimiento")
            header[1].metric("TCO", format_money(row["tco"], currency))
            header[2].metric("Mant. / compra", f"{row['maintenance_ratio'] * 100:.0f}%")

            detail = st.columns(4)
            detail[0].metric("Costo de compra", format_money(row["acquisition_cost"], currency))
            detail[1].metric("Mantenimiento", format_money(row["maintenance_cost"], currency))
            detail[2].metric("Costo/unidad planeado", f"{row['planned_cost_per_unit']:,.4f}")
            actual = row["actual_cost_per_unit"]
            delta = None
            if actual > 0 and row["planned_cost_per_unit"] > 0:
                delta = f"{(actual - row['planned_cost_per_unit']):+,.4f} vs plan"
            detail[3].metric(
                "Costo/unidad real",
                f"{actual:,.4f}" if actual > 0 else "Sin uso aún",
                delta=delta,
            )

            if row["consider_replacement"]:
                st.warning(
                    "Reparaciones ≥ 50% del costo de compra: considera reponer este equipo."
                )
            elif actual > 0 and actual > row["planned_cost_per_unit"] > 0:
                st.info(
                    "El costo real por unidad supera al planeado: el mantenimiento está "
                    "encareciendo cada trabajo por encima de lo que asumía la depreciación."
                )

    st.download_button(
        "Descargar análisis TCO (CSV)",
        data=_export_tco(report),
        file_name=f"tco_activos_{date.today().isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    render_info_card(
        "Costo total de propiedad",
        "Un equipo barato de comprar puede ser caro de mantener. El TCO junta ambas "
        "cosas para decidir con datos cuándo conviene reponer en vez de reparar.",
        "ACTIVOS",
    )


app_shell.FUNCTIONAL_MODULES["Activos"] = render_assets_control
