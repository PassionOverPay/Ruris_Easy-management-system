import math
from typing import Any

from app.models import GoodsReceipt, PurchaseOrder
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
