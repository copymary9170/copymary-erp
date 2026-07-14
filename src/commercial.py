"""Bloque comercial temporal de CopyMary ERP: clientes, ventas, caja y panel."""


from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.money import format_money
from src.payment_fees import fee_breakdown
from src.session_utils import now_iso as _now


def _get_list(key: str) -> list[dict]:
    return [dict(item) for item in st.session_state.get(key, []) if isinstance(item, dict)]


def _save_list(key: str, items: list[dict]) -> None:
    st.session_state[key] = items


def _find_client_name(client_id: str, clients: list[dict]) -> str:
    for client in clients:
        if str(client.get("client_id", "")) == client_id:
            return str(client.get("name", "Cliente"))
    return "Cliente no disponible"


def render_clients() -> None:
    with st.container(border=True):
        render_page_header(
            "Clientes",
            "Registra clientes y consulta su historial comercial durante la sesión.",
        )
        st.caption("Los datos son temporales y se incluirán en el respaldo general.")

    clients = _get_list("customers_registry")
    sales = _get_list("sales_registry")

    with st.form("customer_form", clear_on_submit=True):
        columns = st.columns(2)
        with columns[0]:
            name = st.text_input("Nombre del cliente", max_chars=100)
            phone = st.text_input("Teléfono", max_chars=40)
        with columns[1]:
            address = st.text_input("Dirección", max_chars=180)
            notes = st.text_area("Notas", max_chars=300)
        submitted = st.form_submit_button("Registrar cliente", type="primary", use_container_width=True)

    if submitted:
        cleaned_name = name.strip()
        if not cleaned_name:
            st.error("El nombre del cliente es obligatorio.")
        else:
            clients.append(
                {
                    "client_id": uuid4().hex[:10],
                    "name": cleaned_name,
                    "phone": phone.strip(),
                    "address": address.strip(),
                    "notes": notes.strip(),
                    "created_at_utc": _now(),
                }
            )
            _save_list("customers_registry", clients)
            st.success("Cliente registrado.")
            st.rerun()

    st.divider()
    st.subheader("Clientes registrados")
    if not clients:
        st.info("Todavía no hay clientes registrados.")
        return

    for client in clients:
        client_sales = [
            sale for sale in sales if str(sale.get("client_id", "")) == str(client.get("client_id", ""))
        ]
        paid_total = sum(
            float(sale.get("total", 0.0))
            for sale in client_sales
            if sale.get("payment_status") == "Pagado"
        )
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {client.get('name', 'Cliente')}")
                st.caption(f"ID {client.get('client_id', '')} · {client.get('phone') or 'Sin teléfono'}")
            with title_columns[1]:
                if st.button("Eliminar", key=f"delete_client_{client.get('client_id')}", use_container_width=True):
                    if client_sales:
                        st.error("No puedes eliminar un cliente con ventas registradas.")
                    else:
                        _save_list(
                            "customers_registry",
                            [item for item in clients if item.get("client_id") != client.get("client_id")],
                        )
                        st.rerun()

            metrics = st.columns(3)
            metrics[0].metric("Ventas", str(len(client_sales)))
            metrics[1].metric("Pagado", format_money(paid_total))
            metrics[2].metric(
                "Pendientes",
                str(sum(1 for sale in client_sales if sale.get("payment_status") != "Pagado")),
            )

            render_info_card(
                "Contacto y notas",
                (
                    f"Dirección: {client.get('address') or 'No registrada'}. "
                    f"Notas: {client.get('notes') or 'Sin notas'}."
                ),
                "FICHA DEL CLIENTE",
            )


def render_sales() -> None:
    with st.container(border=True):
        render_page_header(
            "Ventas y pedidos",
            "Registra trabajos, controla pagos y sigue el estado de entrega.",
        )
        st.caption("Cada venta puede conectarse con un cliente y generar un ingreso en Caja.")

    clients = _get_list("customers_registry")
    saved_prices = _get_list("saved_prices")
    sales = _get_list("sales_registry")
    cash = _get_list("cash_movements")

    client_options = {"Venta sin cliente": ""}
    for client in clients:
        client_options[f"{client.get('name', 'Cliente')} · {client.get('client_id', '')}"] = str(
            client.get("client_id", "")
        )

    price_options = {"Precio manual": None}
    for price in saved_prices:
        price_options[f"{price.get('name', 'Producto o servicio')} · {format_money(float(price.get('unit_price', 0.0)))}"] = price

    with st.form("sale_form", clear_on_submit=True):
        first = st.columns(3)
        with first[0]:
            selected_client_label = st.selectbox("Cliente", tuple(client_options.keys()))
        with first[1]:
            selected_price_label = st.selectbox("Producto o servicio", tuple(price_options.keys()))
        selected_price = price_options[selected_price_label]
        default_description = "" if selected_price is None else str(selected_price.get("name", ""))
        default_unit_price = 0.0 if selected_price is None else float(selected_price.get("unit_price", 0.0))

        with first[2]:
            description = st.text_input("Descripción", value=default_description, max_chars=140)

        second = st.columns(4)
        with second[0]:
            quantity = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
        with second[1]:
            unit_price = st.number_input("Precio unitario", min_value=0.0, value=default_unit_price, step=0.5)
        with second[2]:
            discount = st.number_input("Descuento", min_value=0.0, value=0.0, step=0.5)
        with second[3]:
            estimated_cost = st.number_input("Costo estimado total", min_value=0.0, value=0.0, step=0.5)

        third = st.columns(3)
        with third[0]:
            payment_status = st.selectbox("Pago", ("Pendiente", "Pagado", "Abono"))
        with third[1]:
            order_status = st.selectbox("Estado", ("Pendiente", "En proceso", "Listo", "Entregado", "Cancelado"))
        with third[2]:
            payment_method = st.selectbox("Método de pago", ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"))

        preview_total = max((float(quantity) * float(unit_price)) - float(discount), 0.0)
        preview = fee_breakdown(preview_total, payment_method)
        if preview_total > 0 and (preview["fee_amount"] > 0 or preview["igtf_amount"] > 0):
            note = f"Comisión {payment_method}: {format_money(preview['fee_amount'])}"
            if preview["igtf_applied"]:
                note += f" · IGTF: {format_money(preview['igtf_amount'])}"
            note += f" → Neto real: {format_money(preview['net_amount'])}"
            st.caption(note)

        notes = st.text_area("Notas del pedido", max_chars=300)
        submitted = st.form_submit_button("Registrar venta o pedido", type="primary", use_container_width=True)

    if submitted:
        cleaned_description = description.strip()
        total = max((float(quantity) * float(unit_price)) - float(discount), 0.0)
        if not cleaned_description:
            st.error("La descripción es obligatoria.")
        elif total <= 0:
            st.error("El total de la venta debe ser mayor que cero.")
        else:
            sale_id = uuid4().hex[:10]
            breakdown = fee_breakdown(total, payment_method)
            sales.append(
                {
                    "sale_id": sale_id,
                    "created_at_utc": _now(),
                    "client_id": client_options[selected_client_label],
                    "description": cleaned_description,
                    "quantity": float(quantity),
                    "unit_price": float(unit_price),
                    "discount": float(discount),
                    "total": total,
                    "estimated_cost": float(estimated_cost),
                    "payment_status": payment_status,
                    "order_status": order_status,
                    "payment_method": payment_method,
                    "notes": notes.strip(),
                    "cash_registered": payment_status == "Pagado",
                    "payment_fee_rate": breakdown["fee_rate"],
                    "payment_fee_amount": breakdown["fee_amount"],
                    "igtf_applied": breakdown["igtf_applied"],
                    "igtf_amount": breakdown["igtf_amount"],
                    "net_amount": breakdown["net_amount"],
                }
            )
            if payment_status == "Pagado":
                cash.append(
                    {
                        "movement_id": uuid4().hex[:10],
                        "created_at_utc": _now(),
                        "movement_type": "Ingreso",
                        "category": "Venta",
                        "amount": total,
                        "payment_method": payment_method,
                        "reference": sale_id,
                        "notes": cleaned_description,
                    }
                )
                _save_list("cash_movements", cash)
            _save_list("sales_registry", sales)
            st.success("Venta o pedido registrado.")
            st.rerun()

    st.divider()
    filters = st.columns(2)
    with filters[0]:
        status_filter = st.selectbox("Filtrar por estado", ("Todos", "Pendiente", "En proceso", "Listo", "Entregado", "Cancelado"))
    with filters[1]:
        payment_filter = st.selectbox("Filtrar por pago", ("Todos", "Pendiente", "Pagado", "Abono"))

    filtered_sales = sales
    if status_filter != "Todos":
        filtered_sales = [sale for sale in filtered_sales if sale.get("order_status") == status_filter]
    if payment_filter != "Todos":
        filtered_sales = [sale for sale in filtered_sales if sale.get("payment_status") == payment_filter]

    total_sales = sum(float(sale.get("total", 0.0)) for sale in filtered_sales)
    estimated_profit = sum(
        float(sale.get("total", 0.0)) - float(sale.get("estimated_cost", 0.0))
        for sale in filtered_sales
    )
    metrics = st.columns(3)
    metrics[0].metric("Registros", str(len(filtered_sales)))
    metrics[1].metric("Total", format_money(total_sales))
    metrics[2].metric("Ganancia estimada", format_money(estimated_profit))

    for sale in reversed(filtered_sales):
        with st.container(border=True):
            st.markdown(f"### {sale.get('description', 'Venta')}")
            st.caption(
                f"ID {sale.get('sale_id', '')} · {_find_client_name(str(sale.get('client_id', '')), clients)} · "
                f"{sale.get('created_at_utc', '')}"
            )
            columns = st.columns(5)
            columns[0].metric("Cantidad", f"{float(sale.get('quantity', 0.0)):,.2f}")
            columns[1].metric("Total", format_money(float(sale.get("total", 0.0))))
            columns[2].metric("Pago", str(sale.get("payment_status", "Pendiente")))
            columns[3].metric("Estado", str(sale.get("order_status", "Pendiente")))
            columns[4].metric(
                "Ganancia estimada",
                format_money(float(sale.get("total", 0.0)) - float(sale.get("estimated_cost", 0.0))),
            )

            edit_columns = st.columns(3)
            new_payment = edit_columns[0].selectbox(
                "Actualizar pago",
                ("Pendiente", "Pagado", "Abono"),
                index=("Pendiente", "Pagado", "Abono").index(str(sale.get("payment_status", "Pendiente"))),
                key=f"payment_{sale.get('sale_id')}",
            )
            new_status = edit_columns[1].selectbox(
                "Actualizar estado",
                ("Pendiente", "En proceso", "Listo", "Entregado", "Cancelado"),
                index=("Pendiente", "En proceso", "Listo", "Entregado", "Cancelado").index(str(sale.get("order_status", "Pendiente"))),
                key=f"status_{sale.get('sale_id')}",
            )
            if edit_columns[2].button("Guardar cambios", key=f"save_sale_{sale.get('sale_id')}", use_container_width=True):
                updated_sales = []
                for current in sales:
                    updated = dict(current)
                    if current.get("sale_id") == sale.get("sale_id"):
                        became_paid = new_payment == "Pagado" and not bool(current.get("cash_registered", False))
                        updated["payment_status"] = new_payment
                        updated["order_status"] = new_status
                        if became_paid:
                            cash.append(
                                {
                                    "movement_id": uuid4().hex[:10],
                                    "created_at_utc": _now(),
                                    "movement_type": "Ingreso",
                                    "category": "Venta",
                                    "amount": float(current.get("total", 0.0)),
                                    "payment_method": str(current.get("payment_method", "Otro")),
                                    "reference": str(current.get("sale_id", "")),
                                    "notes": str(current.get("description", "Venta")),
                                }
                            )
                            updated["cash_registered"] = True
                    updated_sales.append(updated)
                _save_list("sales_registry", updated_sales)
                _save_list("cash_movements", cash)
                st.rerun()


def render_cash() -> None:
    with st.container(border=True):
        render_page_header("Caja", "Registra ingresos y egresos y consulta el saldo de la sesión.")
        st.caption("Las ventas pagadas generan ingresos automáticos.")

    movements = _get_list("cash_movements")

    with st.form("cash_form", clear_on_submit=True):
        columns = st.columns(4)
        with columns[0]:
            movement_type = st.selectbox("Movimiento", ("Ingreso", "Egreso"))
        with columns[1]:
            category = st.selectbox("Categoría", ("Venta", "Compra", "Servicio", "Transporte", "Retiro", "Otro"))
        with columns[2]:
            amount = st.number_input("Monto", min_value=0.01, value=1.0, step=1.0)
        with columns[3]:
            payment_method = st.selectbox("Método", ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Otro"))
        notes = st.text_input("Concepto o nota", max_chars=180)
        submitted = st.form_submit_button("Registrar movimiento", type="primary", use_container_width=True)

    if submitted:
        movements.append(
            {
                "movement_id": uuid4().hex[:10],
                "created_at_utc": _now(),
                "movement_type": movement_type,
                "category": category,
                "amount": float(amount),
                "payment_method": payment_method,
                "reference": "",
                "notes": notes.strip(),
            }
        )
        _save_list("cash_movements", movements)
        st.success("Movimiento de caja registrado.")
        st.rerun()

    income = sum(float(item.get("amount", 0.0)) for item in movements if item.get("movement_type") == "Ingreso")
    expenses = sum(float(item.get("amount", 0.0)) for item in movements if item.get("movement_type") == "Egreso")
    metrics = st.columns(3)
    metrics[0].metric("Ingresos", format_money(income))
    metrics[1].metric("Egresos", format_money(expenses))
    metrics[2].metric("Saldo", format_money(income - expenses))

    st.subheader("Movimientos")
    if not movements:
        st.info("Todavía no hay movimientos de caja.")
        return
    for movement in reversed(movements):
        with st.container(border=True):
            columns = st.columns([3, 1])
            with columns[0]:
                st.markdown(f"### {movement.get('movement_type', '')}: {movement.get('category', '')}")
                st.caption(
                    f"{movement.get('created_at_utc', '')} · {movement.get('payment_method', '')} · "
                    f"{movement.get('notes') or 'Sin nota'}"
                )
            columns[1].metric("Monto", format_money(float(movement.get("amount", 0.0))))


def render_commercial_dashboard() -> None:
    with st.container(border=True):
        render_page_header("Panel comercial", "Resumen conectado de clientes, ventas, pedidos y caja.")
        st.caption("Todos los indicadores corresponden a la sesión actual.")

    clients = _get_list("customers_registry")
    sales = _get_list("sales_registry")
    movements = _get_list("cash_movements")
    inventory = _get_list("inventory_registry")

    paid_sales = [sale for sale in sales if sale.get("payment_status") == "Pagado"]
    pending_orders = [sale for sale in sales if sale.get("order_status") not in {"Entregado", "Cancelado"}]
    low_stock = [
        item for item in inventory
        if float(item.get("available_quantity", 0.0)) <= float(item.get("minimum_stock", 0.0))
    ]
    income = sum(float(item.get("amount", 0.0)) for item in movements if item.get("movement_type") == "Ingreso")
    expenses = sum(float(item.get("amount", 0.0)) for item in movements if item.get("movement_type") == "Egreso")
    total_profit = sum(
        float(sale.get("total", 0.0)) - float(sale.get("estimated_cost", 0.0))
        for sale in paid_sales
    )

    first = st.columns(4)
    first[0].metric("Clientes", str(len(clients)))
    first[1].metric("Ventas", str(len(sales)))
    first[2].metric("Pedidos pendientes", str(len(pending_orders)))
    first[3].metric("Materiales bajos", str(len(low_stock)))

    second = st.columns(3)
    second[0].metric("Ingresos", format_money(income))
    second[1].metric("Saldo de caja", format_money(income - expenses))
    second[2].metric("Ganancia estimada", format_money(total_profit))

    st.subheader("Prioridades")
    if pending_orders:
        st.warning(f"Hay {len(pending_orders)} pedido(s) todavía pendientes, en proceso o listos para entregar.")
    else:
        st.success("No hay pedidos pendientes.")
    if low_stock:
        st.warning(f"Hay {len(low_stock)} material(es) en existencia mínima o agotados.")
    else:
        st.success("No hay alertas de inventario.")

    render_info_card(
        "Estado del bloque comercial",
        "Clientes, ventas, caja e indicadores ya comparten datos dentro de la misma sesión.",
        "MÓDULO FUNCIONAL",
    )
