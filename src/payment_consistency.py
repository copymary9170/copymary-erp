"""Compatibilidad para excluir pagos revertidos de todos los cálculos."""

from src import accounts_payable, accounts_receivable, adjustments, control_center


def _active(records: list[dict]) -> list[dict]:
    return [item for item in records if not item.get("reversed")]


def _receivable_payments_for(sale_id: str, payments: list[dict]) -> list[dict]:
    return [
        item
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    ]


def _payable_payments_for(purchase_id: str, payments: list[dict]) -> list[dict]:
    return [
        item
        for item in payments
        if str(item.get("purchase_id", "")) == purchase_id and not item.get("reversed")
    ]


def _sale_paid(sale: dict, payments: list[dict]) -> float:
    sale_id = str(sale.get("sale_id", ""))
    total = float(sale.get("total", 0.0))
    explicit = sum(
        float(item.get("amount", 0.0))
        for item in payments
        if str(item.get("sale_id", "")) == sale_id and not item.get("reversed")
    )
    if explicit > 0:
        return min(explicit, total)
    if sale.get("payment_status") == "Pagado" and sale.get("cash_registered"):
        return total
    return 0.0


def _purchase_paid(purchase: dict, payments: list[dict]) -> float:
    purchase_id = str(purchase.get("purchase_id", ""))
    total = float(purchase.get("total", 0.0))
    explicit = sum(
        float(item.get("amount", 0.0))
        for item in payments
        if str(item.get("purchase_id", "")) == purchase_id and not item.get("reversed")
    )
    if explicit > 0:
        return min(explicit, total)
    if purchase.get("payment_status") == "Pagado" and purchase.get("cash_registered"):
        return total
    return 0.0


def _linked_references(reference_id: str, payments: list[dict], link_key: str) -> set[str]:
    references = {reference_id}
    references.update(
        str(item.get("payment_id", ""))
        for item in payments
        if str(item.get(link_key, "")) == reference_id
        and item.get("payment_id")
        and not item.get("reversed")
    )
    return references


def activate_payment_consistency() -> None:
    """Activa cálculos coherentes después de revertir pagos."""
    accounts_receivable._payments_for = _receivable_payments_for
    accounts_payable._payments_for = _payable_payments_for
    control_center._sale_paid = _sale_paid
    control_center._purchase_paid = _purchase_paid
    adjustments._linked_references = _linked_references
