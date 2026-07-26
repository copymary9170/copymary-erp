"""Integración UI y persistencia append-only para cumplimiento legal."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

import streamlit as st

from src import commercial_documents, session_backup
from src.components import render_page_header
from src.erp_database import connect, initialize_database
from src.legal_compliance_domain import (
    record_hash,
    render_template,
    retained_deletion_attempt,
    validate_fiscal_invoice,
)

RETAINED = {
    "fiscal_invoices_registry": "invoice_id",
    "contracts_registry": "contract_id",
    "legal_terms_registry": "terms_id",
}

CUSTOMER_TEMPLATE = """CONTRATO DE SERVICIOS\nEntre {{empresa}}, RIF {{rif_empresa}}, y {{cliente}}, RIF/C.I. {{id_cliente}}, se acuerda la prestación de {{servicio}} por {{precio}}. Vigencia: {{vigencia}}. Las partes aceptan confidencialidad, tratamiento limitado de datos y conservación de soportes legales y fiscales."""
SUPPLIER_TEMPLATE = """CONTRATO DE SUMINISTRO\nEntre {{empresa}}, RIF {{rif_empresa}}, y {{proveedor}}, RIF {{rif_proveedor}}, se acuerda el suministro de {{bienes}}, bajo las condiciones de precio, entrega, garantía y responsabilidad descritas en el anexo. Vigencia: {{vigencia}}."""
TERMS_TEMPLATE = """TÉRMINOS Y CONDICIONES\n1. El cliente declara que los datos entregados son correctos.\n2. Los archivos se usan únicamente para ejecutar el servicio contratado.\n3. Los documentos fiscales y registros de auditoría se conservarán íntegros conforme a la política de retención.\n4. Las anulaciones se documentan mediante reverso o nota; no se elimina el registro original."""


def _ensure_tables() -> None:
    initialize_database()
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS immutable_legal_records (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT NOT NULL UNIQUE,
            record_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            integrity_hash TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )""")


def retain_record(record_type: str, record: dict) -> dict:
    """Persiste una copia inalterable encadenada; no expone DELETE ni UPDATE."""
    _ensure_tables()
    created_at = datetime.now(timezone.utc).isoformat()
    body = dict(record)
    body.setdefault("retained_at_utc", created_at)
    record_id = str(body.get("invoice_id") or body.get("contract_id") or body.get("terms_id") or uuid4().hex)
    with connect() as conn:
        row = conn.execute("SELECT integrity_hash FROM immutable_legal_records ORDER BY sequence DESC LIMIT 1").fetchone()
        previous = str(row["integrity_hash"]) if row else ""
        digest = record_hash(body, previous)
        conn.execute(
            "INSERT INTO immutable_legal_records(record_id, record_type, payload_json, previous_hash, integrity_hash, created_at_utc) VALUES (?, ?, ?, ?, ?, ?)",
            (record_id, record_type, json.dumps(body, ensure_ascii=False, sort_keys=True, default=str), previous, digest, created_at),
        )
    retained = dict(body, previous_hash=previous, integrity_hash=digest)
    return retained


def _protected_save(key: str, items: list[dict]) -> None:
    current = [dict(row) for row in st.session_state.get(key, []) if isinstance(row, dict)]
    if key in RETAINED:
        removed = retained_deletion_attempt(current, items, RETAINED[key])
        if removed:
            st.error("Los registros legales retenidos no pueden eliminarse desde la interfaz normal. Usa una anulación o documento de reverso.")
            st.stop()
        known = {str(row.get(RETAINED[key], "")) for row in current}
        normalized = []
        for row in items:
            identifier = str(row.get(RETAINED[key], ""))
            normalized.append(retain_record(key, row) if identifier and identifier not in known else row)
        st.session_state[key] = normalized
        return
    _ORIGINAL_SAVE(key, items)


_ORIGINAL_SAVE = commercial_documents._save_list


def activate_legal_compliance() -> None:
    commercial_documents._save_list = _protected_save
    for key, label in (
        ("fiscal_invoices_registry", "Facturas fiscales"),
        ("contracts_registry", "Contratos"),
        ("legal_terms_registry", "Términos y condiciones"),
    ):
        if key not in session_backup.LIST_SECTIONS:
            session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, key)
            session_backup.SECTION_LABELS[key] = label
    session_backup.SESSION_KEYS = ("general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS)


def render_legal_compliance() -> None:
    render_page_header("Cumplimiento legal", "Facturación fiscal, contratos, protección de datos y retención inalterable.")
    st.warning("Configuración jurídica y fiscal sujeta a revisión de un abogado y asesor tributario venezolano antes de emitir documentos reales.")
    invoices_tab, contracts_tab, retention_tab = st.tabs(("Facturación", "Contratos y términos", "Retención"))
    with invoices_tab:
        with st.form("fiscal_invoice_form"):
            c1, c2 = st.columns(2)
            issuer_name = c1.text_input("Razón social del emisor")
            issuer_rif = c2.text_input("RIF del emisor")
            fiscal_address = st.text_area("Domicilio fiscal")
            method = st.selectbox("Medio de emisión", ("Imprenta autorizada", "Forma libre", "Máquina fiscal", "Digital autorizada"))
            c3, c4 = st.columns(2)
            invoice_number = c3.text_input("Número de factura")
            control_number = c4.text_input("Número de control", placeholder="00-00000000")
            description = st.text_input("Concepto")
            total = st.number_input("Total", min_value=0.0)
            authorization = st.text_input("Autorización/serial aplicable")
            submitted = st.form_submit_button("Validar y retener factura", type="primary")
        if submitted:
            invoice = {
                "invoice_id": f"FAC-{uuid4().hex[:10].upper()}", "issuer_name": issuer_name,
                "issuer_rif": issuer_rif, "fiscal_address": fiscal_address,
                "invoice_number": invoice_number, "control_number": control_number,
                "issued_at": datetime.now(timezone.utc).isoformat(), "issuance_method": method,
                "items": [{"description": description, "quantity": 1, "unit_price": total}], "total": total,
                "printer_name": authorization if method in {"Imprenta autorizada", "Forma libre"} else "",
                "printer_rif": issuer_rif if method in {"Imprenta autorizada", "Forma libre"} else "",
                "printer_authorization": authorization if method in {"Imprenta autorizada", "Forma libre"} else "",
                "printed_at": datetime.now(timezone.utc).date().isoformat() if method in {"Imprenta autorizada", "Forma libre"} else "",
                "fiscal_machine_serial": authorization if method == "Máquina fiscal" else "",
                "digital_authorization": authorization if method == "Digital autorizada" else "",
            }
            result = validate_fiscal_invoice(invoice)
            if not result.valid:
                for error in result.errors: st.error(error)
            else:
                rows = [dict(row) for row in st.session_state.get("fiscal_invoices_registry", []) if isinstance(row, dict)]
                _protected_save("fiscal_invoices_registry", [*rows, invoice])
                st.success("Factura validada y retenida en almacenamiento inalterable.")
    with contracts_tab:
        template_name = st.selectbox("Plantilla", ("Cliente", "Proveedor", "Términos y condiciones"))
        template = CUSTOMER_TEMPLATE if template_name == "Cliente" else SUPPLIER_TEMPLATE if template_name == "Proveedor" else TERMS_TEMPLATE
        st.download_button("Descargar plantilla TXT", template.encode("utf-8"), file_name=f"plantilla_{template_name.casefold().replace(' ', '_')}.txt", mime="text/plain")
        st.text_area("Vista previa editable", render_template(template, {}), height=260)
    with retention_tab:
        _ensure_tables()
        with connect() as conn:
            rows = conn.execute("SELECT sequence, record_id, record_type, integrity_hash, created_at_utc FROM immutable_legal_records ORDER BY sequence DESC").fetchall()
        st.metric("Registros inalterables", len(rows))
        st.dataframe([dict(row) for row in rows], use_container_width=True, hide_index=True)
        st.caption("La interfaz solo permite consulta. Correcciones y anulaciones deben agregarse como nuevos registros, nunca sobrescribir el original.")
