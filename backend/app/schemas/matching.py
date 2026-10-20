from enum import Enum

from pydantic import BaseModel


class MatchStatus(str, Enum):
    MATCHED = "matched"
    MISSING = "missing"
    OVER_RECEIVED = "over_received"
    UNEXPECTED = "unexpected"


class MatchLine(BaseModel):
    item: str
    ordered_quantity: float
    received_quantity: float
    missing_quantity: float
    unexpected_quantity: float
    status: MatchStatus


class ThreeWayMatch(BaseModel):
    purchase_order_id: int
    items: list[MatchLine]
