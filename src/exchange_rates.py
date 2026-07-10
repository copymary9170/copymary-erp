"""Tasas de cambio con fecha, para costear en moneda base y convertir a moneda de cotización.

Alimenta la tabla `exchange_rates` (ya existía en el esquema fundacional pero
nada la escribía todavía). `bom_costing.py` lee de aquí, vía
`erp_database.latest_exchange_rate`, la tasa vigente más reciente para
congelarla en cada trabajo costeado.
"""

from datetime import date
from uuid import uuid4

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header
from src.erp_database import connect, initialize_database

TABLE_NAME = "exchange_rates"
CURRENCIES = ("USD", "VES", "EUR")


def _rows() -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM exchange_rates ORDER BY rate_date DESC, created_at_utc DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def _insert(values: dict) -> None:
    initialize_database()
    columns = list(values.keys())
    sql = (
        "INSERT INTO " + TABLE_NAME + " (" + ", ".join(columns) + ") VALUES ("
        + ", ".join("?" for _ in columns) + ")"
    )
    with connect() as conn:
        conn.execute(sql, tuple(values[col] for col in columns))


def _latest_by_pair(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Se queda con la fila más reciente por cada par de moneda (ya vienen ordenadas)."""
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["source_currency"], row["target_currency"])
        if key not in latest:
            latest[key] = row
    return latest


def render_exchange_rates() -> None:
    render_page_header(
        "Tasas de cambio",
        "Registra la tasa vigente por fecha. Cada trabajo costeado congela la tasa del día, aunque cambie después.",
    )
    initialize_database()

    rows = _rows()
    latest = _latest_by_pair(rows)

    cols = st.columns(3)
    cols[0].metric("Tasas registradas", str(len(rows)))
    cols[1].metric("Pares de moneda con tasa", str(len(latest)))
    cols[2].metric(
        "Última actualización",
        rows[0]["rate_date"] if rows else "—",
    )

    st.subheader("Tasas vigentes (más reciente por par)")
    if not latest:
        st.info("Todavía no hay ninguna tasa registrada.")
    else:
        for (source, target), row in latest.items():
            st.write(
                f"**1 {source} = {row['rate']:,.4f} {target}** · vigente desde {row['rate_date']} "
                f"· fuente: {row.get('source_name') or 'Manual'}"
            )

    st.divider()
    st.subheader("Registrar nueva tasa")
    with st.form("exchange_rate_form", clear_on_submit=True):
        pair_cols = st.columns(2)
        with pair_cols[0]:
            source_currency = st.selectbox("Moneda origen", CURRENCIES, index=0)
        with pair_cols[1]:
            target_currency = st.selectbox("Moneda destino", CURRENCIES, index=1)

        value_cols = st.columns(2)
        with value_cols[0]:
            rate_value = st.number_input(
                "Valor (unidades de destino por 1 de origen)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.4f",
            )
        with value_cols[1]:
            rate_date = st.date_input("Fecha de vigencia", value=date.today())

        source_name = st.selectbox(
            "Fuente",
            ("Manual", "API BCV", "API otra"),
            help="Manual por defecto. Las fuentes de API quedan como opción para cuando se conecte una fuente automática.",
        )
        notes = st.text_input("Notas", placeholder="Opcional")

        submitted = st.form_submit_button("Guardar tasa", type="primary", use_container_width=True)

    if submitted:
        if source_currency == target_currency:
            st.error("La moneda de origen y destino no pueden ser la misma.")
        elif rate_value <= 0:
            st.error("El valor de la tasa debe ser mayor a cero.")
        else:
            _insert(
                {
                    "rate_id": f"RATE-{uuid4().hex[:8].upper()}",
                    "rate_date": rate_date.isoformat(),
                    "source_currency": source_currency,
                    "target_currency": target_currency,
                    "rate": float(rate_value),
                    "source_name": source_name,
                    "notes": notes.strip(),
                    "created_at_utc": date.today().isoformat(),
                }
            )
            st.success("Tasa guardada.")
            st.rerun()

    st.divider()
    st.subheader("Historial completo")
    if not rows:
        st.info("Sin historial todavía.")
    else:
        for row in rows[:200]:
            st.write(
                f"{row['rate_date']} · 1 {row['source_currency']} = {row['rate']:,.4f} {row['target_currency']} "
                f"· {row.get('source_name') or 'Manual'}"
                + (f" · {row['notes']}" if row.get("notes") else "")
            )

    render_info_card(
        "Por qué importa",
        "Cada trabajo costeado en 'Costeo por procesos' guarda la tasa exacta usada ese día, "
        "para que el histórico de precios no cambie retroactivamente si la tasa cambia después.",
        "TASA CONGELADA",
    )


app_shell.FUNCTIONAL_MODULES["Tasas de cambio"] = render_exchange_rates
