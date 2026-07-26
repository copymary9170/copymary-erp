"""Libros de IVA (Ventas y Compras) — CopyMary ERP.

Página autocontenida (Streamlit multipágina): se activa solo con colocarla en
`pages/`; no requiere cablear app.py ni la navegación.

Arma el Libro de Ventas y el Libro de Compras del IVA para un período, con base
imponible, IVA (débito/crédito fiscal), exento y total, calcula el IVA a pagar
del período (débito − crédito) y permite exportar cada libro a CSV.

Lee los datos de forma defensiva (tolera nombres de campo distintos y datos
faltantes). Supuesto configurable: si los montos ya incluyen IVA, la base y el
IVA se derivan del total con la tasa vigente.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from typing import Any

import streamlit as st

try:
    from src.session_utils import read_list as _read_list
except Exception:  # pragma: no cover - respaldo defensivo
    def _read_list(key: str) -> list[dict]:
        value = st.session_state.get(key, [])
        return value if isinstance(value, list) else []


MESES = ("Todo el año", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(row: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _row_date(row: dict) -> date | None:
    return _parse_date(_first(row, "created_at_utc", "created_at", "date", "fecha",
                              "issue_date", "invoice_date", "sale_date"))


def _amount(row: dict) -> float:
    return _num(_first(row, "total", "amount", "monto", "importe", "value", default=0.0))


def _settings() -> dict:
    raw = st.session_state.get("general_settings")
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    try:
        return {k: getattr(raw, k) for k in dir(raw) if not k.startswith("_")}
    except Exception:
        return {}


def _directory(key: str, id_keys: tuple[str, ...]) -> dict[str, dict]:
    """Índice id -> registro (clientes o proveedores) para resolver nombre/RIF."""
    index: dict[str, dict] = {}
    for row in _read_list(key):
        for id_key in id_keys:
            value = row.get(id_key)
            if value:
                index[str(value)] = row
    return index


def _split_iva(row: dict, rate: float, amounts_include_iva: bool) -> tuple[float, float, float]:
    """Devuelve (base_imponible, iva, exento) de una fila.

    Usa el IVA explícito si existe; si no, lo deriva del total. Respeta filas
    marcadas como exentas.
    """
    total = _amount(row)
    exento_flag = str(_first(row, "exento", "exempt", "is_exempt", default="")).strip().lower()
    if exento_flag in {"true", "1", "si", "sí", "yes"} or bool(row.get("exento")) is True:
        return 0.0, 0.0, total
    explicit_iva = _first(row, "iva", "iva_amount", "tax", "tax_amount", "impuesto")
    if explicit_iva not in (None, ""):
        iva = _num(explicit_iva)
        base = max(total - iva, 0.0) if amounts_include_iva else total
        return base, iva, 0.0
    factor = 1.0 + (rate / 100.0)
    if amounts_include_iva and factor > 0:
        base = total / factor
        return base, total - base, 0.0
    base = total
    return base, base * (rate / 100.0), 0.0


def _build_book(records: list[dict], directory: dict[str, dict], id_keys: tuple[str, ...],
                rate: float, include_iva: bool, year: int, month: int) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    totals = {"base": 0.0, "iva": 0.0, "exento": 0.0, "total": 0.0}
    for record in records:
        d = _row_date(record)
        if not d or d.year != year:
            continue
        if month and d.month != month:
            continue
        entity = {}
        for id_key in id_keys:
            value = record.get(id_key)
            if value and str(value) in directory:
                entity = directory[str(value)]
                break
        name = _first(record, "customer_name", "supplier_name", "cliente", "proveedor",
                      default=_first(entity, "name", "nombre", default="—"))
        rif = _first(record, "rif", "tax_id", default=_first(entity, "rif", "tax_id", default="—"))
        base, iva, exento = _split_iva(record, rate, include_iva)
        total = base + iva + exento
        rows.append({
            "Fecha": d.isoformat(),
            "RIF": rif,
            "Nombre": name,
            "Factura": _first(record, "invoice_number", "control_number", "numero_factura",
                              "purchase_id", "sale_id", "id", default="—"),
            "Base imponible": round(base, 2),
            "IVA": round(iva, 2),
            "Exento": round(exento, 2),
            "Total": round(total, 2),
        })
        totals["base"] += base
        totals["iva"] += iva
        totals["exento"] += exento
        totals["total"] += total
    rows.sort(key=lambda r: r["Fecha"])
    return rows, totals


def _csv_bytes(rows: list[dict]) -> bytes:
    headers = ["Fecha", "RIF", "Nombre", "Factura", "Base imponible", "IVA", "Exento", "Total"]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=";", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def render() -> None:
    st.title("Libros de IVA")
    st.caption("Libro de Ventas y Libro de Compras del período, con base, IVA y exento. "
               "Exportables a CSV para tu declaración.")

    settings = _settings()
    default_rate = _num(_first(settings, "iva_rate", default=16.0), 16.0)

    controls = st.columns([1, 1, 1, 2])
    year = int(controls[0].number_input("Año", min_value=2000, max_value=2100,
                                        value=date.today().year, step=1))
    month_label = controls[1].selectbox("Mes", MESES, index=date.today().month)
    month = MESES.index(month_label) if month_label != "Todo el año" else 0
    rate = controls[2].number_input("Tasa de IVA (%)", min_value=0.0, max_value=100.0,
                                    value=float(default_rate), step=0.5)
    include_iva = controls[3].checkbox("Los montos registrados YA incluyen IVA", value=True)

    customers = _directory("customers_registry", ("client_id", "customer_id", "id"))
    suppliers = _directory("suppliers_registry", ("supplier_id", "id"))

    sales_rows, sales_totals = _build_book(
        _read_list("sales_registry"), customers, ("client_id", "customer_id", "cliente"),
        rate, include_iva, year, month)
    purchase_rows, purchase_totals = _build_book(
        _read_list("purchases_registry"), suppliers, ("supplier_id", "proveedor"),
        rate, include_iva, year, month)

    debito = sales_totals["iva"]
    credito = purchase_totals["iva"]
    iva_por_pagar = debito - credito

    st.subheader("Resumen del período")
    summary = st.columns(4)
    summary[0].metric("Débito fiscal (IVA ventas)", f"{debito:,.2f}")
    summary[1].metric("Crédito fiscal (IVA compras)", f"{credito:,.2f}")
    summary[2].metric("IVA a pagar" if iva_por_pagar >= 0 else "IVA a favor",
                      f"{abs(iva_por_pagar):,.2f}")
    summary[3].metric("Ventas / Compras (total)",
                      f"{sales_totals['total']:,.0f} / {purchase_totals['total']:,.0f}")

    st.subheader("Libro de Ventas")
    if sales_rows:
        st.dataframe(sales_rows, use_container_width=True, hide_index=True)
        st.caption(f"Base: {sales_totals['base']:,.2f} · IVA: {sales_totals['iva']:,.2f} · "
                   f"Exento: {sales_totals['exento']:,.2f} · Total: {sales_totals['total']:,.2f}")
        st.download_button("Descargar Libro de Ventas (CSV)", data=_csv_bytes(sales_rows),
                           file_name=f"libro_ventas_{year}_{month or 'anual'}.csv",
                           mime="text/csv", use_container_width=True)
    else:
        st.info("No hay ventas registradas en el período seleccionado.")

    st.subheader("Libro de Compras")
    if purchase_rows:
        st.dataframe(purchase_rows, use_container_width=True, hide_index=True)
        st.caption(f"Base: {purchase_totals['base']:,.2f} · IVA: {purchase_totals['iva']:,.2f} · "
                   f"Exento: {purchase_totals['exento']:,.2f} · Total: {purchase_totals['total']:,.2f}")
        st.download_button("Descargar Libro de Compras (CSV)", data=_csv_bytes(purchase_rows),
                           file_name=f"libro_compras_{year}_{month or 'anual'}.csv",
                           mime="text/csv", use_container_width=True)
    else:
        st.info("No hay compras registradas en el período seleccionado.")

    st.caption("Solo lectura. Verifica RIF y número de control antes de declarar; "
               "las filas sin fecha válida no se incluyen.")


render()
