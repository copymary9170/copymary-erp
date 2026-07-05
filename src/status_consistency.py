"""Normalización central de estados para evitar conteos inconsistentes."""

import unicodedata

import streamlit as st


def _text(value) -> str:
    raw = str(value or "").strip().lower()
    return "".join(
        character
        for character in unicodedata.normalize("NFD", raw)
        if unicodedata.category(character) != "Mn"
    )


def _sale_status(value) -> str:
    normalized = _text(value)
    if normalized in {"cancelado", "cancelada", "anulado", "anulada", "revertido", "revertida"}:
        return "Cancelado"
    if normalized in {"entregado", "entregada"}:
        return "Entregado"
    if normalized in {"listo", "lista"}:
        return "Listo"
    if normalized in {"en proceso", "proceso"}:
        return "En proceso"
    if normalized in {"pendiente", ""}:
        return "Pendiente"
    return str(value).strip()


def _purchase_status(value) -> str:
    normalized = _text(value)
    if normalized in {"cancelado", "cancelada", "anulado", "anulada", "revertido", "revertida"}:
        return "Cancelada"
    if normalized in {"recibido", "recibida"}:
        return "Recibida"
    if normalized in {"pendiente", ""}:
        return "Pendiente"
    return str(value).strip()


def _payment_status(value) -> str:
    normalized = _text(value)
    if normalized in {"pagado", "pagada", "completo", "completa"}:
        return "Pagado"
    if normalized in {"abono", "parcial", "parcialmente pagado", "parcialmente pagada"}:
        return "Abono"
    if normalized in {"pendiente", "", "no pagado", "no pagada"}:
        return "Pendiente"
    return str(value).strip()


def normalize_session_statuses() -> dict[str, int]:
    """Corrige variantes conocidas y devuelve cuántos registros cambiaron."""
    changes = {"sales": 0, "purchases": 0, "payments": 0}

    sales = []
    for item in st.session_state.get("sales_registry", []):
        if not isinstance(item, dict):
            continue
        current = dict(item)
        new_order = _sale_status(current.get("order_status"))
        new_payment = _payment_status(current.get("payment_status"))
        if new_order != current.get("order_status"):
            changes["sales"] += 1
            current["order_status"] = new_order
        if new_payment != current.get("payment_status"):
            changes["payments"] += 1
            current["payment_status"] = new_payment
        sales.append(current)
    if sales or "sales_registry" in st.session_state:
        st.session_state["sales_registry"] = sales

    purchases = []
    for item in st.session_state.get("purchases_registry", []):
        if not isinstance(item, dict):
            continue
        current = dict(item)
        new_receipt = _purchase_status(current.get("receipt_status"))
        new_payment = _payment_status(current.get("payment_status"))
        if new_receipt != current.get("receipt_status"):
            changes["purchases"] += 1
            current["receipt_status"] = new_receipt
        if new_payment != current.get("payment_status"):
            changes["payments"] += 1
            current["payment_status"] = new_payment
        purchases.append(current)
    if purchases or "purchases_registry" in st.session_state:
        st.session_state["purchases_registry"] = purchases

    return changes


def is_cancelled(record: dict) -> bool:
    """Reconoce cualquier variante de estado cancelado o anulado."""
    values = (
        record.get("order_status"),
        record.get("receipt_status"),
        record.get("status"),
    )
    cancelled = {"cancelado", "cancelada", "anulado", "anulada", "revertido", "revertida"}
    return any(_text(value) in cancelled for value in values if value is not None)
