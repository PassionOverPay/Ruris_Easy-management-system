from datetime import date
from typing import Any

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models import PurchaseOrderStatus


class PurchaseOrderCreate(SQLModel):
    po_number: str = Field(min_length=1, max_length=100)
    supplier_name: str = Field(min_length=1, max_length=255)
    order_date: date
    expected_delivery_date: date
    items_summary: list[dict[str, Any]] = Field(default_factory=list)
    status: PurchaseOrderStatus = PurchaseOrderStatus.ORDERED


class PurchaseOrderRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier_name: str
    order_date: date
    expected_delivery_date: date
    items_summary: list[dict[str, Any]]
    status: PurchaseOrderStatus
    created_by_id: int
