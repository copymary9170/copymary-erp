"""Legal y cumplimiento fiscal — CopyMary ERP.

Página autocontenida (Streamlit multipágina): se activa solo con colocarla en
`pages/`; no requiere cablear app.py ni la navegación.

- Datos fiscales del negocio: verifica RIF, razón social y domicilio fiscal.
- Cumplimiento de facturas: revisa que las ventas/comprobantes tengan los datos
  obligatorios (RIF del receptor, número de factura, número de control, fecha,
  total) y reporta las que están incompletas.
- Validador de factura: comprueba una factura puntual contra los requisitos.
- Plantillas: genera Términos y Condiciones y un contrato de servicio
  descargables a partir de los datos del negocio.

Solo lectura sobre los datos del ERP. AVISO: es una ayuda de cumplimiento, no
asesoría legal; verifica siempre la normativa vigente del SENIAT.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

try:
    from src.session_utils import read_list as _read_list
except Exception:  # pragma: no cover
    def _read_list(key: str) -> list[dict]:
        value = st.session_state.get(key, [])
        return value if isinstance(value, list) else []


# Datos obligatorios del RECEPTOR/venta en una factura (nombre visible -> claves posibles)
INVOICE_REQUIRED = {
    "RIF/C.I. del cliente": ("rif", "tax_id", "client_rif", "customer_rif", "cedula", "ci"),
    "Nombre o razón social": ("customer_name", "cliente", "client_name", "name", "nombre"),
    "Número de factura": ("invoice_number", "numero_factura", "factura", "sale_id", "id"),
    "Número de control": ("control_number", "numero_control", "control"),
    "Fecha": ("date", "fecha", "created_at_utc", "created_at", "issue_date"),
    "Total": ("total", "amount", "monto", "importe"),
}

# Datos fiscales obligatorios del NEGOCIO (emisor)
BUSINESS_REQUIRED = {
    "Razón social / nombre": ("business_name", "razon_social", "nombre"),
    "RIF del negocio": ("rif", "business_rif", "tax_id"),
    "Domicilio fiscal": ("fiscal_address", "domicilio", "domicilio_fiscal", "address", "direccion"),
}


def _first(row: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


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


def validate_invoice(row: dict) -> list[str]:
    """Devuelve la lista de datos obligatorios que FALTAN en la factura."""
    missing = []
    for label, keys in INVOICE_REQUIRED.items():
        if _first(row, keys) in (None, ""):
            missing.append(label)
    return missing


def validate_business(settings: dict) -> list[str]:
    missing = []
    for label, keys in BUSINESS_REQUIRED.items():
        if _first(settings, keys) in (None, ""):
            missing.append(label)
    return missing


def _compliance_report(records: list[dict]) -> tuple[int, int, list[dict]]:
    compliant = 0
    incomplete: list[dict] = []
    for row in records:
        missing = validate_invoice(row)
        if missing:
            incomplete.append({
                "Factura": _first(row, INVOICE_REQUIRED["Número de factura"]) or "—",
                "Cliente": _first(row, INVOICE_REQUIRED["Nombre o razón social"]) or "—",
                "Faltan": ", ".join(missing),
            })
        else:
            compliant += 1
    return compliant, len(incomplete), incomplete


def build_terms(business: str, rif: str) -> str:
    return (
        f"TÉRMINOS Y CONDICIONES\n"
        f"{business} (RIF: {rif or 'por indicar'})\n\n"
        "1. Alcance. Estos términos rigen la prestación de servicios de impresión, "
        "papelería y afines.\n"
        "2. Presupuestos. Las cotizaciones tienen validez de 15 días salvo indicación "
        "distinta y están sujetas a la tasa de cambio vigente.\n"
        "3. Pagos. El cliente acepta las condiciones y medios de pago informados. Los "
        "precios pueden incluir IVA e IGTF cuando corresponda.\n"
        "4. Entregas. Los tiempos de entrega son estimados y pueden variar por causas "
        "ajenas al proveedor.\n"
        "5. Aprobación de artes. El cliente es responsable de revisar y aprobar pruebas "
        "antes de la producción; una vez aprobado, no se aceptan reclamos por contenido.\n"
        "6. Protección de datos. Los datos del cliente se usan solo para gestionar la "
        "relación comercial y no se comparten con terceros salvo obligación legal.\n"
        "7. Jurisdicción. Se rige por las leyes de la República Bolivariana de Venezuela.\n"
    )


def build_service_contract(business: str, rif: str, client: str, detail: str) -> str:
    today = date.today().isoformat()
    return (
        f"CONTRATO DE PRESTACIÓN DE SERVICIOS\n\n"
        f"Entre {business} (RIF: {rif or 'por indicar'}), en adelante EL PROVEEDOR, y "
        f"{client or '____________'}, en adelante EL CLIENTE, se acuerda:\n\n"
        f"PRIMERA. Objeto: EL PROVEEDOR prestará los siguientes servicios: "
        f"{detail or '____________'}.\n"
        "SEGUNDA. Precio y pago: según cotización aceptada, en la moneda y medios "
        "informados, más los impuestos aplicables (IVA/IGTF).\n"
        "TERCERA. Plazo: los tiempos de entrega serán los acordados por escrito.\n"
        "CUARTA. Responsabilidades: EL CLIENTE aprueba las pruebas antes de producir.\n"
        "QUINTA. Confidencialidad y datos: se tratarán conforme a la ley.\n"
        "SEXTA. Jurisdicción: leyes de la República Bolivariana de Venezuela.\n\n"
        f"Fecha: {today}\n\n"
        "____________________            ____________________\n"
        "     EL PROVEEDOR                      EL CLIENTE\n"
    )


def render() -> None:
    st.title("Legal y cumplimiento fiscal")
    st.caption("Ayuda de cumplimiento (no asesoría legal). Verifica datos de factura y del "
               "negocio, y genera plantillas de contrato.")

    settings = _settings()
    business = str(_first(settings, BUSINESS_REQUIRED["Razón social / nombre"]) or "Tu negocio")
    rif = str(_first(settings, BUSINESS_REQUIRED["RIF del negocio"]) or "")

    # Datos fiscales del negocio
    st.subheader("Datos fiscales del negocio")
    business_missing = validate_business(settings)
    if business_missing:
        st.error("⚠️ Faltan datos fiscales obligatorios del emisor: " + ", ".join(business_missing) +
                 ". Complétalos en Configuración General para poder facturar conforme al SENIAT.")
    else:
        st.success("Los datos fiscales del negocio están completos.")

    # Cumplimiento de facturas
    st.subheader("Cumplimiento de facturas")
    records = _read_list("sales_registry") + _read_list("receipts_registry")
    if not records:
        st.info("No hay ventas ni comprobantes para revisar.")
    else:
        compliant, incomplete_count, incomplete = _compliance_report(records)
        total = compliant + incomplete_count
        cols = st.columns(3)
        cols[0].metric("Documentos revisados", str(total))
        cols[1].metric("Conformes", str(compliant))
        cols[2].metric("Incompletos", str(incomplete_count))
        if total:
            pct = compliant / total * 100
            st.progress(pct / 100, text=f"Cumplimiento: {pct:.0f}%")
        if incomplete:
            st.warning("Facturas con datos obligatorios faltantes:")
            st.dataframe(incomplete[:200], use_container_width=True, hide_index=True)

    # Validador puntual
    st.subheader("Validar una factura")
    with st.form("legal_validate_invoice"):
        cols = st.columns(3)
        v_rif = cols[0].text_input("RIF/C.I. del cliente")
        v_name = cols[1].text_input("Nombre o razón social")
        v_invoice = cols[2].text_input("Número de factura")
        cols2 = st.columns(3)
        v_control = cols2[0].text_input("Número de control")
        v_date = cols2[1].text_input("Fecha (YYYY-MM-DD)")
        v_total = cols2[2].number_input("Total", min_value=0.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("Validar", type="primary", use_container_width=True)
    if submitted:
        row = {"rif": v_rif, "customer_name": v_name, "invoice_number": v_invoice,
               "control_number": v_control, "date": v_date, "total": v_total or ""}
        missing = validate_invoice(row)
        if missing:
            st.error("Faltan: " + ", ".join(missing))
        else:
            st.success("La factura tiene todos los datos obligatorios.")

    # Plantillas
    st.subheader("Plantillas legales")
    cols = st.columns(2)
    cols[0].download_button("Descargar Términos y Condiciones",
                            data=build_terms(business, rif).encode("utf-8"),
                            file_name="terminos_y_condiciones.txt", mime="text/plain",
                            use_container_width=True)
    with cols[1]:
        client = st.text_input("Cliente (para el contrato)", key="legal_client")
        detail = st.text_input("Servicio (para el contrato)", key="legal_detail")
        st.download_button("Descargar Contrato de servicio",
                           data=build_service_contract(business, rif, client, detail).encode("utf-8"),
                           file_name="contrato_servicio.txt", mime="text/plain",
                           use_container_width=True)

    st.caption("Ayuda de cumplimiento; verifica la normativa vigente del SENIAT y consulta a un "
               "profesional para casos concretos.")


render()
