"""Registro temporal de activos productivos de CopyMary ERP."""

from dataclasses import asdict, dataclass, replace
from uuid import uuid4

import streamlit as st

from src.components import render_info_card, render_page_header
from src.erp_database import latest_exchange_rate
from src.money import format_money, get_currency
from src.production_processes import PROCESS_OPTIONS, normalize_process_codes, process_labels
from src.session_utils import now_iso as _now, read_list as _rows, save_list as _save_list


ASSET_STATUSES = ("Activo", "En mantenimiento", "Fuera de servicio", "Dado de baja", "Vendido")
ASSET_CATEGORIES = (
    "Impresora",
    "Impresora láser",
    "Impresora de sublimación",
    "Impresora 3D",
    "Impresora de carnets PVC",
    "Impresora térmica (tickets/etiquetas)",
    "Impresora de esténciles de tatuaje",
    "Equipo de corte",
    "Láser de grabado o corte",
    "Equipo de sublimación",
    "Prensa o plancha térmica",
    "Plastificadora o laminadora",
    "Guillotina o cizalla",
    "Anilladora o encuadernadora",
    "Computación",
    "Accesorio o herramienta menor",
    "Otro",
)
CURRENCIES = ("USD", "VES", "EUR")
PAYMENT_METHODS = ("Efectivo", "Pago móvil", "Transferencia", "Zelle", "Tarjeta", "Crédito de proveedor", "Otro")


@dataclass(frozen=True)
class Asset:
    asset_id: str
    name: str
    category: str
    acquisition_cost: float
    lifetime_units: int
    current_units: int
    status: str = "Activo"
    participates_in_costing: bool = True
    process_codes: tuple[str, ...] = ()
    # Detalle real de cómo se adquirió el equipo, con el mismo criterio que
    # el costo de compra detallado de Inventario: el costo del equipo, el
    # envío/flete, los aranceles de importación y los impuestos pagados se
    # capturan por separado, en la moneda real de la compra, y
    # `acquisition_cost` termina siendo el costo total ya convertido a la
    # moneda base del ERP ("landed cost") — no un número puesto a ojo.
    supplier: str = ""
    purchase_date: str = ""
    invoice_reference: str = ""
    purchase_currency: str = "USD"
    exchange_rate_used: float = 1.0
    payment_method: str = ""
    acquisition_subtotal: float = 0.0
    shipping_cost: float = 0.0
    has_import_duties: bool = False
    import_duties: float = 0.0
    tax_amount: float = 0.0
    no_purchase_cost: bool = False
    warranty_until: str = ""

    @property
    def depreciation_per_unit(self) -> float:
        return self.acquisition_cost / self.lifetime_units

    @property
    def accumulated_depreciation(self) -> float:
        used_units = min(self.current_units, self.lifetime_units)
        return used_units * self.depreciation_per_unit

    @property
    def remaining_value(self) -> float:
        return max(self.acquisition_cost - self.accumulated_depreciation, 0.0)

    @property
    def usage_percent(self) -> float:
        return min((self.current_units / self.lifetime_units) * 100, 100.0)

    @property
    def available_for_quoting(self) -> bool:
        return self.status == "Activo" and self.participates_in_costing and bool(self.process_codes)

    @property
    def purchase_total_in_purchase_currency(self) -> float:
        return self.acquisition_subtotal + self.shipping_cost + self.import_duties + self.tax_amount


def landed_acquisition_cost(subtotal: float, shipping: float, import_duties: float, tax: float, exchange_rate: float) -> float:
    """Convierte costo del equipo + envío/flete + aranceles + impuestos (en
    la moneda de la compra) a la moneda base del ERP, usando la tasa de
    cambio indicada. Mismo criterio que `inventory_enterprise._landed_unit_cost`,
    aplicado aquí al activo completo en vez de a un costo por unidad."""
    total_purchase_currency = subtotal + shipping + import_duties + tax
    return total_purchase_currency / max(exchange_rate, 0.0001)


def _asset_from_dict(raw_asset: dict) -> Asset:
    """Mantiene compatibilidad con activos creados antes del costeo por procesos."""
    return Asset(
        asset_id=str(raw_asset.get("asset_id", uuid4().hex[:8])),
        name=str(raw_asset.get("name", "Equipo")),
        category=str(raw_asset.get("category", "Otro")),
        acquisition_cost=float(raw_asset.get("acquisition_cost", 0.0)),
        lifetime_units=max(int(raw_asset.get("lifetime_units", 1)), 1),
        current_units=max(int(raw_asset.get("current_units", 0)), 0),
        status=str(raw_asset.get("status", "Activo")),
        participates_in_costing=bool(raw_asset.get("participates_in_costing", True)),
        process_codes=normalize_process_codes(raw_asset.get("process_codes", ())),
        supplier=str(raw_asset.get("supplier", "") or ""),
        purchase_date=str(raw_asset.get("purchase_date", "") or ""),
        invoice_reference=str(raw_asset.get("invoice_reference", "") or ""),
        purchase_currency=str(raw_asset.get("purchase_currency", "") or get_currency()),
        exchange_rate_used=float(raw_asset.get("exchange_rate_used", 1.0) or 1.0),
        payment_method=str(raw_asset.get("payment_method", "") or ""),
        acquisition_subtotal=float(raw_asset.get("acquisition_subtotal", 0.0) or 0.0),
        shipping_cost=float(raw_asset.get("shipping_cost", 0.0) or 0.0),
        has_import_duties=bool(raw_asset.get("has_import_duties", False)),
        import_duties=float(raw_asset.get("import_duties", 0.0) or 0.0),
        tax_amount=float(raw_asset.get("tax_amount", 0.0) or 0.0),
        no_purchase_cost=bool(raw_asset.get("no_purchase_cost", False)),
        warranty_until=str(raw_asset.get("warranty_until", "") or ""),
    )


def _get_assets() -> list[Asset]:
    raw_assets = st.session_state.get("assets_registry", [])
    assets: list[Asset] = []
    for raw_asset in raw_assets:
        if isinstance(raw_asset, Asset):
            assets.append(replace(raw_asset, process_codes=normalize_process_codes(raw_asset.process_codes)))
        elif isinstance(raw_asset, dict):
            assets.append(_asset_from_dict(raw_asset))
    return assets


def _save_assets(assets: list[Asset]) -> None:
    st.session_state.assets_registry = [asdict(asset) for asset in assets]


def _replace_asset(assets: list[Asset], updated_asset: Asset) -> list[Asset]:
    return [updated_asset if asset.asset_id == updated_asset.asset_id else asset for asset in assets]


def _update_asset_units(assets: list[Asset], asset_id: str, units_to_add: int) -> list[Asset]:
    updated_assets: list[Asset] = []
    for asset in assets:
        if asset.asset_id == asset_id:
            updated_assets.append(replace(asset, current_units=asset.current_units + units_to_add))
        else:
            updated_assets.append(asset)
    return updated_assets


def _activate_maintenance_backup() -> None:
    from src import session_backup
    if "asset_maintenance_log" not in session_backup.LIST_SECTIONS:
        session_backup.LIST_SECTIONS = (*session_backup.LIST_SECTIONS, "asset_maintenance_log")
        session_backup.SECTION_LABELS["asset_maintenance_log"] = "Historial de mantenimiento de activos"
        session_backup.SESSION_KEYS = (
            "general_settings", *session_backup.LIST_SECTIONS, *session_backup.DICT_SECTIONS,
        )


_activate_maintenance_backup()


def _log_maintenance(
    asset_id: str, *, event_date: str, description: str, part_replaced: str, cost: float,
    inventory_item_id: str = "", inventory_quantity: float = 0.0,
) -> dict:
    """Registra un evento de mantenimiento o reemplazo de repuesto en un
    activo específico — esto es distinto de simplemente TENER el repuesto
    en existencia (eso es Inventario): aquí queda el momento real en que se
    instaló/reemplazó en la máquina, qué costó y, si el repuesto salió de
    Inventario, el descuento real de esa existencia.
    """
    inventory_deducted = False
    if inventory_item_id and inventory_quantity > 0:
        from src.print_jobs import deduct_inventory_item
        inventory_deducted = deduct_inventory_item(
            inventory_item_id, inventory_quantity, f"Mantenimiento: {description or part_replaced}"
        )
    log = _rows("asset_maintenance_log")
    entry = {
        "log_id": uuid4().hex[:10],
        "asset_id": asset_id,
        "event_date": event_date,
        "recorded_at_utc": _now(),
        "description": description.strip(),
        "part_replaced": part_replaced.strip(),
        "cost": float(cost),
        "inventory_item_id": inventory_item_id,
        "inventory_quantity": float(inventory_quantity),
        "inventory_deducted": inventory_deducted,
    }
    log.append(entry)
    _save_list("asset_maintenance_log", log)
    return entry


def _maintenance_history(asset_id: str) -> list[dict]:
    return [entry for entry in _rows("asset_maintenance_log") if entry.get("asset_id") == asset_id]


def _inventory_value() -> float:
    """Valor total de existencias en Inventario (cantidad disponible × costo
    unitario de cada ítem), para sumarlo al valor de Activos y así calcular
    el patrimonio total del negocio."""
    try:
        from src import inventory_enterprise
        items = inventory_enterprise._items()
    except Exception:
        return 0.0
    return sum(float(item.get("available_quantity", 0.0) or 0.0) * float(item.get("unit_cost", 0.0) or 0.0) for item in items)


def render_assets() -> None:
    """Renderiza activos y define en qué procesos se usan para cotizar."""
    with st.container(border=True):
        render_page_header(
            "Activos",
            "Registra equipos, controla su estado y define los procesos donde participan al cotizar.",
        )
        st.caption("Los registros se conservan únicamente durante la sesión actual.")

    st.warning(
        "Este módulo todavía no utiliza base de datos. Los activos pueden perderse al cerrar o reiniciar la aplicación."
    )

    assets = _get_assets()
    process_codes = [code for code, _label in PROCESS_OPTIONS]
    process_label_map = dict(PROCESS_OPTIONS)

    st.subheader("Registrar activo")
    with st.form("asset_form", clear_on_submit=True):
        first_row = st.columns(3)
        with first_row[0]:
            name = st.text_input("Nombre del equipo", max_chars=80)
        with first_row[1]:
            category = st.selectbox("Categoría", ASSET_CATEGORIES)
        with first_row[2]:
            status = st.selectbox("Estado operativo", ASSET_STATUSES)

        st.markdown("##### ¿Qué costó realmente adquirir este equipo?")
        base_currency = get_currency()
        purchase_row = st.columns(3)
        with purchase_row[0]:
            supplier = st.text_input("Proveedor")
        with purchase_row[1]:
            purchase_currency = st.selectbox(
                "Moneda de la compra", CURRENCIES,
                index=CURRENCIES.index(base_currency) if base_currency in CURRENCIES else 0,
            )
        with purchase_row[2]:
            payment_method = st.selectbox("Método de pago", PAYMENT_METHODS)
        same_currency = purchase_currency == base_currency
        default_rate = 1.0
        if not same_currency:
            looked_up = latest_exchange_rate(purchase_currency, base_currency)
            default_rate = float(looked_up.get("rate", 1.0)) if looked_up else 1.0
        rate_row = st.columns(3)
        with rate_row[0]:
            exchange_rate_used = st.number_input(
                f"Tasa de cambio usada (1 {base_currency} = ? {purchase_currency})",
                min_value=0.0001, value=1.0 if same_currency else default_rate,
                step=0.01, format="%.4f", disabled=same_currency,
            )
        with rate_row[1]:
            purchase_date = st.date_input("Fecha de compra", value=None)
        with rate_row[2]:
            invoice_reference = st.text_input("N° de factura / control")

        cost_row = st.columns(3)
        with cost_row[0]:
            acquisition_subtotal = st.number_input(f"Costo del equipo ({purchase_currency})", min_value=0.0, value=0.0, step=10.0)
        with cost_row[1]:
            shipping_cost = st.number_input(f"Envío / flete / aduana ({purchase_currency})", min_value=0.0, value=0.0, step=1.0)
        with cost_row[2]:
            has_import_duties = st.checkbox(
                "Pagó aranceles / derechos de importación",
                value=False,
                help="Márcalo solo si esta compra pagó aranceles — muchos equipos comprados localmente no tienen.",
            )
            import_duties = st.number_input(
                f"Aranceles / derechos de importación ({purchase_currency})",
                min_value=0.0, value=0.0, step=1.0, disabled=not has_import_duties,
            )
        tax_amount = st.number_input(f"Impuestos pagados en la compra, ej. IVA ({purchase_currency})", min_value=0.0, value=0.0, step=1.0)
        no_purchase_cost = st.checkbox(
            "Este equipo ya se tenía / no hay costo de compra registrado (heredado, regalado, comprado hace mucho)",
            value=False,
            help="Si lo marcas, el costo del equipo queda en 0 y no se exige llenarlo. Puedes poner un valor estimado igual si lo quieres incluir en la depreciación.",
        )

        life_row = st.columns(3)
        with life_row[0]:
            lifetime_units = st.number_input("Vida útil estimada en unidades", min_value=1, value=30000, step=100)
        with life_row[1]:
            current_units = st.number_input("Unidades acumuladas iniciales", min_value=0, value=0, step=100)
        with life_row[2]:
            warranty_until = st.date_input("Garantía hasta (opcional)", value=None)

        participates_in_costing = st.checkbox(
            "Usar este activo para calcular costos y cotizaciones",
            value=True,
            help="Solo se utilizará cuando esté Activo y el producto requiera uno de sus procesos.",
        )
        selected_processes = st.multiselect(
            "Procesos que puede realizar este activo",
            options=process_codes,
            format_func=lambda code: process_label_map[code],
            help="Se configura una sola vez. Las cotizaciones detectarán el equipo según los procesos del producto.",
        )

        submitted = st.form_submit_button(
            "Registrar activo", type="primary", use_container_width=True
        )

    if submitted:
        cleaned_name = name.strip()
        effective_rate = 1.0 if same_currency else float(exchange_rate_used)
        effective_import_duties = float(import_duties) if has_import_duties else 0.0
        landed_cost = landed_acquisition_cost(acquisition_subtotal, shipping_cost, effective_import_duties, tax_amount, effective_rate)
        if not cleaned_name:
            st.error("El nombre del equipo no puede quedar vacío.")
        elif acquisition_subtotal <= 0 and not no_purchase_cost:
            st.error("El costo del equipo debe ser mayor que cero, o marca que ya se tenía sin costo registrado.")
        elif participates_in_costing and not selected_processes:
            st.error("Selecciona al menos un proceso o desactiva su uso en costos y cotizaciones.")
        else:
            assets.append(
                Asset(
                    asset_id=uuid4().hex[:8],
                    name=cleaned_name,
                    category=category,
                    acquisition_cost=landed_cost,
                    lifetime_units=int(lifetime_units),
                    current_units=int(current_units),
                    status=status,
                    participates_in_costing=bool(participates_in_costing),
                    process_codes=normalize_process_codes(selected_processes),
                    supplier=supplier.strip(),
                    purchase_date=purchase_date.isoformat() if purchase_date else "",
                    invoice_reference=invoice_reference.strip(),
                    purchase_currency=purchase_currency,
                    exchange_rate_used=effective_rate,
                    payment_method=payment_method,
                    acquisition_subtotal=float(acquisition_subtotal),
                    shipping_cost=float(shipping_cost),
                    has_import_duties=bool(has_import_duties),
                    import_duties=effective_import_duties,
                    tax_amount=float(tax_amount),
                    no_purchase_cost=bool(no_purchase_cost),
                    warranty_until=warranty_until.isoformat() if warranty_until else "",
                )
            )
            _save_assets(assets)
            if no_purchase_cost:
                st.success("Activo registrado como equipo ya existente, sin costo de compra.")
            else:
                st.success(f"Activo registrado. Costo real (con envío, aranceles e impuestos incluidos): {format_money(landed_cost)}.")
            st.rerun()

    st.divider()
    st.subheader("Resumen de activos")

    total_cost = sum(asset.acquisition_cost for asset in assets)
    total_remaining = sum(asset.remaining_value for asset in assets)
    available_count = sum(1 for asset in assets if asset.available_for_quoting)
    summary_columns = st.columns(4)
    summary_columns[0].metric("Activos registrados", str(len(assets)))
    summary_columns[1].metric("Disponibles para cotizar", str(available_count))
    summary_columns[2].metric("Inversión registrada", format_money(total_cost))
    summary_columns[3].metric("Valor pendiente", format_money(total_remaining))

    inventory_value = _inventory_value()
    st.markdown("#### Patrimonio total")
    st.caption("Valor en libros de tus equipos (ya con la depreciación descontada) más el valor de lo que tienes en Inventario ahora mismo.")
    patrimony_columns = st.columns(3)
    patrimony_columns[0].metric("Activos (valor en libros)", format_money(total_remaining))
    patrimony_columns[1].metric("Inventario (existencias)", format_money(inventory_value))
    patrimony_columns[2].metric("Patrimonio total", format_money(total_remaining + inventory_value))

    if not assets:
        st.info("Todavía no hay activos registrados en esta sesión.")
        return

    st.subheader("Equipos registrados")
    for asset in assets:
        with st.container(border=True):
            title_columns = st.columns([3, 1])
            with title_columns[0]:
                st.markdown(f"### {asset.name}")
                state_text = "Disponible para cotizar" if asset.available_for_quoting else "No usado automáticamente"
                st.caption(f"{asset.category} · {asset.status} · {state_text} · ID {asset.asset_id}")
            with title_columns[1]:
                if st.button("Eliminar", key=f"delete_asset_{asset.asset_id}", use_container_width=True):
                    _save_assets([item for item in assets if item.asset_id != asset.asset_id])
                    st.rerun()

            metric_columns = st.columns(5)
            metric_columns[0].metric("Costo", format_money(asset.acquisition_cost))
            metric_columns[1].metric("Depreciación/unidad", f"$ {asset.depreciation_per_unit:,.4f}")
            metric_columns[2].metric("Unidades acumuladas", f"{asset.current_units:,}")
            metric_columns[3].metric("Uso estimado", f"{asset.usage_percent:.1f}%")
            metric_columns[4].metric("Valor pendiente", format_money(asset.remaining_value))
            st.progress(asset.usage_percent / 100)

            labels = process_labels(asset.process_codes)
            st.markdown("**Procesos para cotización:** " + (" · ".join(labels) if labels else "Ninguno"))

            with st.expander("Editar estado y procesos", expanded=not asset.process_codes):
                with st.form(f"asset_process_form_{asset.asset_id}"):
                    edit_columns = st.columns(2)
                    with edit_columns[0]:
                        edited_status = st.selectbox(
                            "Estado operativo",
                            ASSET_STATUSES,
                            index=ASSET_STATUSES.index(asset.status) if asset.status in ASSET_STATUSES else 0,
                            key=f"status_{asset.asset_id}",
                        )
                        edited_participation = st.checkbox(
                            "Usar para costos y cotizaciones",
                            value=asset.participates_in_costing,
                            key=f"participation_{asset.asset_id}",
                        )
                    with edit_columns[1]:
                        edited_processes = st.multiselect(
                            "Procesos que realiza",
                            options=process_codes,
                            default=list(asset.process_codes),
                            format_func=lambda code: process_label_map[code],
                            key=f"processes_{asset.asset_id}",
                        )
                    save_processes = st.form_submit_button(
                        "Guardar estado y procesos", type="primary", use_container_width=True
                    )
                if save_processes:
                    if edited_participation and not edited_processes:
                        st.error("Selecciona al menos un proceso para usar el activo en cotizaciones.")
                    else:
                        updated_asset = replace(
                            asset,
                            status=edited_status,
                            participates_in_costing=bool(edited_participation),
                            process_codes=normalize_process_codes(edited_processes),
                        )
                        _save_assets(_replace_asset(assets, updated_asset))
                        st.success("Estado y procesos actualizados.")
                        st.rerun()

            with st.form(f"asset_usage_form_{asset.asset_id}", clear_on_submit=True):
                usage_columns = st.columns([2, 1])
                with usage_columns[0]:
                    units_to_add = st.number_input(
                        "Agregar unidades producidas",
                        min_value=1,
                        value=1,
                        step=1,
                        key=f"units_to_add_{asset.asset_id}",
                    )
                with usage_columns[1]:
                    update_submitted = st.form_submit_button(
                        "Actualizar uso", type="primary", use_container_width=True
                    )

            if update_submitted:
                _save_assets(_update_asset_units(assets, asset.asset_id, int(units_to_add)))
                st.success(f"Se agregaron {int(units_to_add):,} unidades a {asset.name}.")
                st.rerun()

            detail_columns = st.columns(2)
            with detail_columns[0]:
                render_info_card(
                    "Depreciación acumulada",
                    f"El equipo ha consumido aproximadamente {format_money(asset.accumulated_depreciation)} de su valor.",
                    "SEGUIMIENTO DE USO",
                )
            with detail_columns[1]:
                render_info_card(
                    "Uso automático al cotizar",
                    (
                        "El ERP lo añadirá cuando un producto requiera alguno de sus procesos."
                        if asset.available_for_quoting
                        else "No se añadirá hasta que esté Activo, habilitado y tenga procesos asignados."
                    ),
                    "COSTEO POR PROCESOS",
                )

            if asset.supplier or asset.acquisition_subtotal or asset.no_purchase_cost:
                with st.expander("Detalle de la compra"):
                    if asset.no_purchase_cost:
                        st.info("Equipo ya existente: no tiene costo de compra registrado.")
                    purchase_columns = st.columns(3)
                    purchase_columns[0].metric("Proveedor", asset.supplier or "Sin registrar")
                    purchase_columns[1].metric("Método de pago", asset.payment_method or "Sin registrar")
                    purchase_columns[2].metric("N° de factura", asset.invoice_reference or "Sin registrar")
                    breakdown_columns = st.columns(4)
                    breakdown_columns[0].metric(f"Costo equipo ({asset.purchase_currency})", f"{asset.acquisition_subtotal:,.2f}")
                    breakdown_columns[1].metric(f"Envío/aduana ({asset.purchase_currency})", f"{asset.shipping_cost:,.2f}")
                    breakdown_columns[2].metric(f"Aranceles ({asset.purchase_currency})", f"{asset.import_duties:,.2f}" if asset.has_import_duties else "No aplica")
                    breakdown_columns[3].metric(f"Impuestos ({asset.purchase_currency})", f"{asset.tax_amount:,.2f}")
                    st.caption(
                        f"Tasa de cambio usada: {asset.exchange_rate_used:,.4f} · "
                        f"Total en {asset.purchase_currency}: {asset.purchase_total_in_purchase_currency:,.2f} · "
                        f"Fecha de compra: {asset.purchase_date or 'sin registrar'} · "
                        f"Garantía hasta: {asset.warranty_until or 'sin registrar'}"
                    )

            maintenance_history = _maintenance_history(asset.asset_id)
            with st.expander(f"Mantenimiento y repuestos instalados ({len(maintenance_history)})"):
                st.caption(
                    "Aquí queda el momento en que un repuesto se INSTALÓ en esta máquina (cuchilla, tapete, "
                    "cabezal), no solo que lo tienes disponible en Inventario. Si el repuesto salía de una "
                    "existencia registrada ahí, se descuenta real al confirmarlo aquí."
                )
                inventory_options = {"Ninguno / no venía de Inventario": ""}
                try:
                    from src import inventory_enterprise
                    for item in inventory_enterprise._items():
                        if item.get("active", True):
                            inventory_options[f"{item['name']} · stock {item['available_quantity']:,.2f} {item['unit_name']}"] = item["item_id"]
                except Exception:
                    pass
                with st.form(f"asset_maintenance_form_{asset.asset_id}", clear_on_submit=True):
                    m_cols = st.columns(3)
                    event_date = m_cols[0].date_input("Fecha del reemplazo/mantenimiento", value=None, key=f"maint_date_{asset.asset_id}")
                    part_replaced = m_cols[1].text_input("Repuesto instalado (ej. Cuchilla, Tapete, Cabezal)", key=f"maint_part_{asset.asset_id}")
                    cost = m_cols[2].number_input("Costo del repuesto/servicio", min_value=0.0, value=0.0, step=1.0, key=f"maint_cost_{asset.asset_id}")
                    description = st.text_input("Descripción / motivo", key=f"maint_desc_{asset.asset_id}")
                    inv_cols = st.columns(2)
                    selected_inventory_label = inv_cols[0].selectbox("¿Salió de una existencia en Inventario?", tuple(inventory_options), key=f"maint_inv_{asset.asset_id}")
                    inventory_quantity = inv_cols[1].number_input("Cantidad a descontar", min_value=0.0, value=1.0, step=1.0, key=f"maint_qty_{asset.asset_id}")
                    maintenance_submitted = st.form_submit_button("Registrar mantenimiento", type="primary", use_container_width=True)
                if maintenance_submitted:
                    if not part_replaced.strip() and not description.strip():
                        st.error("Indica al menos qué repuesto se instaló o una descripción del mantenimiento.")
                    else:
                        selected_item_id = inventory_options[selected_inventory_label]
                        entry = _log_maintenance(
                            asset.asset_id, event_date=event_date.isoformat() if event_date else "",
                            description=description, part_replaced=part_replaced, cost=cost,
                            inventory_item_id=selected_item_id, inventory_quantity=inventory_quantity if selected_item_id else 0.0,
                        )
                        if selected_item_id and not entry["inventory_deducted"]:
                            st.warning("No se pudo descontar de Inventario; revísalo manualmente.")
                        st.success("Mantenimiento registrado.")
                        st.rerun()

                if maintenance_history:
                    for entry in reversed(maintenance_history[-20:]):
                        st.write(
                            f"**{entry.get('event_date') or entry.get('recorded_at_utc', '')[:10]}** · "
                            f"{entry.get('part_replaced') or 'Mantenimiento'} — {entry.get('description') or 'sin descripción'} · "
                            f"{format_money(entry.get('cost', 0.0))}"
                            + (" · descontado de Inventario" if entry.get("inventory_deducted") else "")
                        )
