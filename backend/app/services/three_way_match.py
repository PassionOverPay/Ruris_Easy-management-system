import math
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.models import GoodsReceipt, Invoice, InvoiceStatus, PurchaseOrder
from app.schemas.matching import MatchLine, MatchStatus, ThreeWayMatch


def _aggregate_quantities(items: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            raise ValueError(f"Item at index {index} must be an object")

        item = entry.get("item")
        quantity = entry.get("qty")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Item at index {index} must have a non-empty item name")
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or not math.isfinite(quantity)
            or quantity < 0
        ):
            raise ValueError(
                f"Quantity for item {item!r} must be a finite non-negative number"
            )

        totals[item] = totals.get(item, 0.0) + quantity

    return totals


def calculate_three_way_match(
    purchase_order: PurchaseOrder,
    receipts: list[GoodsReceipt],
) -> ThreeWayMatch:
    ordered = _aggregate_quantities(purchase_order.items_summary)
    received: dict[str, float] = {}
    for receipt in receipts:
        for item, quantity in _aggregate_quantities(receipt.items_received).items():
            received[item] = received.get(item, 0.0) + quantity

    lines: list[MatchLine] = []
    for item in dict.fromkeys([*ordered, *received]):
        ordered_quantity = ordered.get(item, 0.0)
        received_quantity = received.get(item, 0.0)
        missing_quantity = max(ordered_quantity - received_quantity, 0.0)
        unexpected_quantity = max(received_quantity - ordered_quantity, 0.0)

        if item not in ordered:
            status = MatchStatus.UNEXPECTED
        elif missing_quantity > 0:
            status = MatchStatus.MISSING
        elif unexpected_quantity > 0:
            status = MatchStatus.OVER_RECEIVED
        else:
            status = MatchStatus.MATCHED

        lines.append(
            MatchLine(
                item=item,
                ordered_quantity=ordered_quantity,
                received_quantity=received_quantity,
                missing_quantity=missing_quantity,
                unexpected_quantity=unexpected_quantity,
                status=status,
            )
        )

    return ThreeWayMatch(
        purchase_order_id=purchase_order.id,
        items=lines,
    )


def reconcile_po_invoices(po_id: int, db: Session) -> None:
    purchase_order = db.get(PurchaseOrder, po_id)
    if purchase_order is None:
        raise ValueError(f"Purchase order {po_id} does not exist")

    item_quantity_and_value: dict[str, tuple[Decimal, Decimal]] = {}
    total_po_value = Decimal("0")
    for item in purchase_order.items_summary:
        name = item.get("item")
        quantity = item.get("qty")
        unit_price = item.get("unit_price")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(quantity, (int, float))
            or isinstance(quantity, bool)
            or not isinstance(unit_price, (int, float, str))
            or isinstance(unit_price, bool)
        ):
            for invoice in _invoices_for_po(db, po_id):
                invoice.status = InvoiceStatus.PENDING
                invoice.match_notes = (
                    "Auto-reconciliation unavailable: purchase order item pricing "
                    "is incomplete."
                )
            db.flush()
            return

        ordered_quantity = Decimal(str(quantity))
        line_value = ordered_quantity * Decimal(str(unit_price))
        total_po_value += line_value
        previous_quantity, previous_value = item_quantity_and_value.get(
            name,
            (Decimal("0"), Decimal("0")),
        )
        item_quantity_and_value[name] = (
            previous_quantity + ordered_quantity,
            previous_value + line_value,
        )

    if total_po_value <= 0:
        for invoice in _invoices_for_po(db, po_id):
            invoice.status = InvoiceStatus.PENDING
            invoice.match_notes = (
                "Auto-reconciliation unavailable: purchase order has no priced items."
            )
        db.flush()
        return

    unit_prices = {
        name: total_value / quantity
        for name, (quantity, total_value) in item_quantity_and_value.items()
        if quantity > 0
    }
    receipts = db.exec(
        select(GoodsReceipt).where(GoodsReceipt.purchase_order_id == po_id)
    ).all()
    quantity_match_has_differences = False
    if receipts:
        match_result = calculate_three_way_match(purchase_order, receipts)
        quantity_match_has_differences = any(
            line.status != MatchStatus.MATCHED for line in match_result.items
        )

    total_received_value = Decimal("0")
    for receipt in receipts:
        for item in receipt.items_received:
            name = item.get("item")
            quantity = item.get("qty")
            if (
                isinstance(name, str)
                and name in unit_prices
                and isinstance(quantity, (int, float))
                and not isinstance(quantity, bool)
            ):
                total_received_value += Decimal(str(quantity)) * unit_prices[name]

    running_invoiced_total = Decimal("0")
    for invoice in _invoices_for_po(db, po_id):
        invoice_currency = (
            invoice.currency.value
            if hasattr(invoice.currency, "value")
            else str(invoice.currency)
        )
        if invoice_currency != purchase_order.currency:
            invoice.status = InvoiceStatus.DISPUTED
            invoice.match_notes = (
                "Disputed: Invoice currency does not match the purchase order."
            )
            continue
        if invoice.supplier_name.strip().casefold() != (
            purchase_order.supplier_name.strip().casefold()
        ):
            invoice.status = InvoiceStatus.DISPUTED
            invoice.match_notes = (
                "Disputed: Invoice supplier does not match the purchase order."
            )
            continue
        running_invoiced_total += invoice.amount_original
        if (
            running_invoiced_total <= total_received_value
            and not quantity_match_has_differences
        ):
            invoice.status = InvoiceStatus.MATCHED
            invoice.match_notes = (
                "Auto-matched: Received quantity and price verified."
            )
        elif quantity_match_has_differences:
            invoice.status = InvoiceStatus.DISPUTED
            invoice.match_notes = (
                "Disputed: Received quantities do not match the purchase order."
            )
        else:
            invoice.status = InvoiceStatus.DISPUTED
            invoice.match_notes = (
                "Disputed: Cumulative invoice total "
                f"({running_invoiced_total}) exceeds received goods value "
                f"({total_received_value})."
            )
    db.flush()


def _invoices_for_po(db: Session, po_id: int) -> list[Invoice]:
    return db.exec(
        select(Invoice)
        .where(Invoice.purchase_order_id == po_id)
        .order_by(Invoice.id)
    ).all()
