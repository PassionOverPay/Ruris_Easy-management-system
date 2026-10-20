from datetime import datetime
from typing import Any

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


class GoodsReceiptCreate(SQLModel):
    receipt_number: str | None = Field(default=None, min_length=1, max_length=100)
    purchase_order_id: int | None = Field(default=None, gt=0)
    items_received: list[dict[str, Any]] = Field(min_length=1)
    notes: str | None = None


class GoodsReceiptRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_number: str
    purchase_order_id: int | None
    received_at: datetime
    received_by_id: int
    items_received: list[dict[str, Any]]
    notes: str | None
