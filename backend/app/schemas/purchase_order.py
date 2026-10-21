from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from pydantic import ConfigDict, computed_field
from sqlmodel import Field, SQLModel

from app.models import Currency, PurchaseOrderStatus


class PurchaseOrderItem(SQLModel):
    item: str = Field(min_length=1, max_length=255)
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class PurchaseOrderCreate(SQLModel):
    po_number: str | None = Field(default=None, min_length=1, max_length=100)
    supplier_name: str = Field(min_length=1, max_length=255)
    order_date: date
    expected_delivery_date: date
    currency: Currency = Currency.RON
    items_summary: list[PurchaseOrderItem] = Field(default_factory=list)
    status: PurchaseOrderStatus = PurchaseOrderStatus.ORDERED


class PurchaseOrderRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier_name: str
    order_date: date
    expected_delivery_date: date
    currency: str
    expected_total_original: float | None
    budget_exchange_rate: Decimal | None
    items_summary: list[dict[str, object]]
    status: PurchaseOrderStatus
    created_by_id: int

    @computed_field
    @property
    def estimated_total_ron(self) -> Decimal | None:
        if self.expected_total_original is None:
            return None
        if self.currency == Currency.EUR.value and self.budget_exchange_rate is None:
            return None

        rate = self.budget_exchange_rate or Decimal("1")
        return (Decimal(str(self.expected_total_original)) * rate).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
