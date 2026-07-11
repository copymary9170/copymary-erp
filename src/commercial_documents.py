"""Cotizaciones y comprobantes comerciales temporales para CopyMary ERP."""


from html import escape
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money, get_currency
from src.session_utils import now_iso as _now


def _get_list(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save_list(key: str, items: list[dict]) -> None:
    st.session_state[key] = items


def _client_options(clients: list[dict]) -> dict[str, str]:
    options = {"Sin cliente": ""}
    for client in clients:
        options[f"{client.get('name', 'Cliente')} · {client.get('client_id', '')}"] = str(
            client.get("client_id", "")
        )
    return options


def _client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Cliente no registrado"


def _business_name() -> str:
    settings = st.session_state.get("general_settings")
    if settings is None:
        return "Copy Mary"
    if isinstance(settings, dict):
        return str(settings.get("business_name", "Copy Mary"))
    return str(getattr(settings, "business_name", "Copy Mary"))


def _quote_total(items: list[dict], discount: float) -> float:
    subtotal = sum(float(item.get("quantity", 0.0)) * float(item.get("unit_price", 0.0)) for item in items)
    return max(subtotal - discount, 0.0)


def _build_document_html(
    title: str,
    document_id: str,
    client_name: str,
    created_at: str,
    items: list[dict],
    discount: float,
    notes: str,
) -> bytes:
    currency = get_currency()
    rows = "".join(
        (
            "<tr>"
            f"<td>{escape(str(item.get('description', '')))}</td>"
            f"<td>{float(item.get('quantity', 0.0)):.2f}</td>"
            f"<td>{escape(format_money(float(item.get('unit_price', 0.0)), currency))}</td>"
            f"<td>{escape(format_money(float(item.get('quantity', 0.0)) * float(item.get('unit_price', 0.0)), currency))}</td>"
            "</tr>"
        )
        for item in items
    )
    subtotal = sum(float(item.get("quantity", 0.0)) * float(item.get("unit_price", 0.0)) for item in items)
    total = max(subtotal - discount, 0.0)
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{escape(title)} {escape(document_id)}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
h1 {{ margin-bottom: 4px; }}
.meta {{ color: #666; margin-bottom: 24px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
th {{ background: #f3f3f3; }}
.totals {{ margin-top: 24px; text-align: right; }}
.notes {{ margin-top: 28px; padding: 14px; background: #f7f7f7; }}
</style>
</head>
<body>
<h1>{escape(_business_name())}</h1>
<h2>{escape(title)}</h2>
<div class="meta">Documento: {escape(document_id)}<br>Cliente: {escape(client_name)}<br>Fecha UTC: {escape(created_at)}</div>
<table>
<thead><tr><th>Descripción</th><th>Cantidad</th><th>Precio unitario</th><th>Total</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<div class="totals">
<p>Subtotal: <strong>{escape(format_money(subtotal, currency))}</strong></p>
<p>Descuento: <strong>{escape(format_money(discount, currency))}</strong></p>
<p>Total: <strong>{escape(format_money(total, currency))}</strong></p>
</div>
<div class="notes"><strong>Notas:</strong> {escape(notes or 'Sin notas')}</div>
</body>
</html>"""
    return html.encode("utf-8")


def render_quotes() -> None:
    with st.container(border=True):
        render_page_header(
            "Cotizaciones",
            "Crea cotizaciones con varios conceptos y conviértelas después en ventas.",
        )
        st.caption("Las cotizaciones se guardan durante la sesión y forman parte del respaldo general.")

    clients = _get_list("customers_registry")
    quotes = _get_list("quotes_registry")
    sales = _get_list("sales_registry")
    client_options = _client_options(clients)

    with st.form("quote_form", clear_on_submit=True):
        header_columns = st.columns(2)
        with header_columns[0]:
            selected_client = st.selectbox("Cliente", tuple(client_options.keys()))
        with header_columns[1]:
            validity_days = st.number_input("Vigencia en días", min_value=1, value=7, step=1)

        st.markdown("#### Conceptos")
        quote_items: list[dict] = []
        for index in range(1, 6):
            columns = st.columns([3, 1, 1])
            with columns[0]:
                description = st.text_input(
                    f"Descripción {index}",
                    key=f"quote_description_{index}",
                    max_chars=140,
                )
            with columns[1]:
                quantity = st.number_input(
                    f"Cantidad {index}",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key=f"quote_quantity_{index}",
                )
            with columns[2]:
                unit_price = st.number_input(
                    f"Precio {index}",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key=f"quote_price_{index}",
                )
            if description.strip() and quantity > 0 and unit_price > 0:
                quote_items.append(
                    {
                        "description": description.strip(),
                        "quantity": float(quantity),
                        "unit_price": float(unit_price),
                    }
                )

        footer_columns = st.columns(2)
        with footer_columns[0]:
            discount = st.number_input("Descuento total", min_value=0.0, value=0.0, step=0.5)
        with footer_columns[1]:
            notes = st.text_area("Condiciones o notas", max_chars=400)

        submitted = st.form_submit_button("Guardar cotización", type="primary", use_container_width=True)

    if submitted:
        total = _quote_total(quote_items, float(discount))
        if not quote_items:
            st.error("Agrega al menos un concepto completo.")
        elif total <= 0:
            st.error("El total de la cotización debe ser mayor que cero.")
        else:
            quotes.append(
                {
                    "quote_id": uuid4().hex[:10],
                    "created_at_utc": _now(),
                    "client_id": client_options[selected_client],
                    "validity_days": int(validity_days),
                    "items": quote_items,
                    "discount": float(discount),
                    "notes": notes.strip(),
                    "status": "Borrador",
                    "converted_sale_id": "",
                }
            )
            _save_list("quotes_registry", quotes)
            st.success("Cotización guardada.")
            st.rerun()

    st.divider()
    st.subheader("Cotizaciones registradas")
    if not quotes:
        st.info("Todavía no hay cotizaciones.")
        return

    for quote in reversed(quotes):
        items = [dict(item) for item in quote.get("items", []) if isinstance(item, dict)]
        total = _quote_total(items, float(quote.get("discount", 0.0)))
        client_name = _client_name(str(quote.get("client_id", "")), clients)
        with st.container(border=True):
            st.markdown(f"### Cotización {quote.get('quote_id', '')}")
            st.caption(
                f"{client_name} · {quote.get('created_at_utc', '')} · Vigencia {quote.get('validity_days', 7)} días"
            )
            metrics = st.columns(3)
            metrics[0].metric("Conceptos", str(len(items)))
            metrics[1].metric("Total", format_money(total))
            metrics[2].metric("Estado", str(quote.get("status", "Borrador")))

            action_columns = st.columns(3)
            with action_columns[0]:
                st.download_button(
                    "Descargar HTML",
                    data=_build_document_html(
                        "Cotización",
                        str(quote.get("quote_id", "")),
                        client_name,
                        str(quote.get("created_at_utc", "")),
                        items,
                        float(quote.get("discount", 0.0)),
                        str(quote.get("notes", "")),
                    ),
                    file_name=f"cotizacion_{quote.get('quote_id', '')}.html",
                    mime="text/html",
                    use_container_width=True,
                    key=f"download_quote_{quote.get('quote_id')}",
                )
            with action_columns[1]:
                if st.button(
                    "Convertir en venta",
                    key=f"convert_quote_{quote.get('quote_id')}",
                    use_container_width=True,
                    disabled=bool(quote.get("converted_sale_id")),
                ):
                    sale_id = uuid4().hex[:10]
                    description = " + ".join(str(item.get("description", "")) for item in items)
                    sales.append(
                        {
                            "sale_id": sale_id,
                            "created_at_utc": _now(),
                            "client_id": str(quote.get("client_id", "")),
                            "description": description[:140],
                            "quantity": 1.0,
                            "unit_price": total,
                            "discount": 0.0,
                            "total": total,
                            "estimated_cost": 0.0,
                            "payment_status": "Pendiente",
                            "order_status": "Pendiente",
                            "payment_method": "Otro",
                            "notes": f"Creada desde cotización {quote.get('quote_id', '')}",
                            "cash_registered": False,
                        }
                    )
                    updated_quotes = []
                    for current in quotes:
                        updated = dict(current)
                        if current.get("quote_id") == quote.get("quote_id"):
                            updated["status"] = "Convertida"
                            updated["converted_sale_id"] = sale_id
                        updated_quotes.append(updated)
                    _save_list("sales_registry", sales)
                    _save_list("quotes_registry", updated_quotes)
                    st.rerun()
            with action_columns[2]:
                if st.button(
                    "Eliminar",
                    key=f"delete_quote_{quote.get('quote_id')}",
                    use_container_width=True,
                    disabled=bool(quote.get("converted_sale_id")),
                ):
                    _save_list(
                        "quotes_registry",
                        [item for item in quotes if item.get("quote_id") != quote.get("quote_id")],
                    )
                    st.rerun()

            for item in items:
                st.write(
                    f"{item.get('description', '')}: {float(item.get('quantity', 0.0)):.2f} × "
                    f"{format_money(float(item.get('unit_price', 0.0)))}"
                )


def render_receipts() -> None:
    with st.container(border=True):
        render_page_header(
            "Comprobantes",
            "Genera comprobantes descargables para ventas registradas y pagadas.",
        )
        st.caption("Los comprobantes se generan en HTML y pueden imprimirse desde el navegador.")

    clients = _get_list("customers_registry")
    sales = _get_list("sales_registry")
    paid_sales = [sale for sale in sales if sale.get("payment_status") == "Pagado"]

    if not paid_sales:
        st.info("No hay ventas pagadas disponibles para generar comprobantes.")
        return

    for sale in reversed(paid_sales):
        client_name = _client_name(str(sale.get("client_id", "")), clients)
        items = [
            {
                "description": str(sale.get("description", "Venta")),
                "quantity": float(sale.get("quantity", 1.0)),
                "unit_price": float(sale.get("unit_price", 0.0)),
            }
        ]
        with st.container(border=True):
            st.markdown(f"### Comprobante {sale.get('sale_id', '')}")
            st.caption(
                f"{client_name} · {sale.get('created_at_utc', '')} · {sale.get('payment_method', 'Otro')}"
            )
            metrics = st.columns(3)
            metrics[0].metric("Total", format_money(float(sale.get("total", 0.0))))
            metrics[1].metric("Pago", "Pagado")
            metrics[2].metric("Estado", str(sale.get("order_status", "Pendiente")))
            st.download_button(
                "Descargar comprobante HTML",
                data=_build_document_html(
                    "Comprobante de pago",
                    str(sale.get("sale_id", "")),
                    client_name,
                    str(sale.get("created_at_utc", "")),
                    items,
                    float(sale.get("discount", 0.0)),
                    str(sale.get("notes", "")),
                ),
                file_name=f"comprobante_{sale.get('sale_id', '')}.html",
                mime="text/html",
                use_container_width=True,
                key=f"download_receipt_{sale.get('sale_id')}",
            )

    render_info_card(
        "Uso del comprobante",
        "Descarga el HTML, ábrelo en el navegador y utiliza la opción Imprimir para guardarlo como PDF.",
        "DOCUMENTO COMERCIAL",
    )
