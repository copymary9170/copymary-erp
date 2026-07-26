"""Reglas puras de cumplimiento fiscal y retención documental venezolana."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping

RIF_RE = re.compile(r"^[VEJPG]-?\d{8}-?\d$")
CONTROL_RE = re.compile(r"^\d{2}-\d{8}$")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def normalize_rif(value: object) -> str:
    return str(value or "").strip().upper().replace(" ", "")


def validate_fiscal_invoice(invoice: Mapping[str, object]) -> ValidationResult:
    """Valida mínimos transversales y requisitos según el medio de emisión."""
    errors: list[str] = []
    required = {
        "issuer_name": "razón social del emisor",
        "issuer_rif": "RIF del emisor",
        "fiscal_address": "domicilio fiscal",
        "invoice_number": "número consecutivo de factura",
        "issued_at": "fecha de emisión",
        "items": "detalle de bienes o servicios",
        "total": "total de la factura",
        "issuance_method": "medio de emisión",
    }
    for key, label in required.items():
        value = invoice.get(key)
        if value in (None, "", [], ()): errors.append(f"Falta {label}.")

    rif = normalize_rif(invoice.get("issuer_rif"))
    if rif and not RIF_RE.fullmatch(rif): errors.append("El RIF del emisor no tiene un formato válido.")

    method = str(invoice.get("issuance_method", "")).strip().casefold()
    if method in {"imprenta autorizada", "forma libre", "digital autorizada"}:
        control = str(invoice.get("control_number", "")).strip()
        if not control: errors.append("Falta la numeración de control.")
        elif not CONTROL_RE.fullmatch(control): errors.append("La numeración de control debe usar el formato 00-00000000.")
    if method in {"imprenta autorizada", "forma libre"}:
        for key, label in {
            "printer_name": "razón social de la imprenta autorizada",
            "printer_rif": "RIF de la imprenta autorizada",
            "printer_authorization": "providencia de autorización de la imprenta",
            "printed_at": "fecha de elaboración del formato",
        }.items():
            if not str(invoice.get(key, "")).strip(): errors.append(f"Falta {label}.")
    elif method == "máquina fiscal":
        if not str(invoice.get("fiscal_machine_serial", "")).strip():
            errors.append("Falta el serial de la máquina fiscal.")
    elif method == "digital autorizada":
        if not str(invoice.get("digital_authorization", "")).strip():
            errors.append("Falta la autorización SENIAT para emisión digital.")
    elif method:
        errors.append("El medio de emisión fiscal no está soportado.")

    items = invoice.get("items")
    if isinstance(items, Iterable) and not isinstance(items, (str, bytes, Mapping)):
        if not any(isinstance(row, Mapping) and str(row.get("description", "")).strip() for row in items):
            errors.append("La factura debe incluir al menos un concepto identificado.")
    try:
        if float(invoice.get("total", 0)) <= 0: errors.append("El total debe ser mayor que cero.")
    except (TypeError, ValueError): errors.append("El total no es numérico.")
    return ValidationResult(not errors, tuple(errors))


def canonical_json(record: Mapping[str, object]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def record_hash(record: Mapping[str, object], previous_hash: str = "") -> str:
    payload = f"{previous_hash}|{canonical_json(record)}".encode("utf-8")
    return sha256(payload).hexdigest()


def verify_hash_chain(records: Iterable[Mapping[str, object]]) -> bool:
    previous = ""
    for row in records:
        body = dict(row)
        expected = str(body.pop("integrity_hash", ""))
        body.pop("previous_hash", None)
        if not expected or record_hash(body, previous) != expected: return False
        previous = expected
    return True


def retained_deletion_attempt(current: Iterable[Mapping[str, object]], proposed: Iterable[Mapping[str, object]], id_field: str) -> tuple[str, ...]:
    current_ids = {str(row.get(id_field, "")) for row in current if row.get(id_field)}
    proposed_ids = {str(row.get(id_field, "")) for row in proposed if row.get(id_field)}
    return tuple(sorted(current_ids - proposed_ids))


def render_template(template: str, values: Mapping[str, object]) -> str:
    result = template
    for key, value in values.items(): result = result.replace("{{" + key + "}}", str(value))
    return result
