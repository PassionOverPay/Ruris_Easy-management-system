from datetime import date
from decimal import Decimal

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models import Currency, InvoiceStatus


class InvoiceCreate(SQLModel):
    invoice_number: str = Field(min_length=1, max_length=100)
    purchase_order_id: int | None = None
    supplier_name: str = Field(min_length=1, max_length=255)
    invoice_date: date
    currency: Currency
    amount_original: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
    )


class InvoiceRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    purchase_order_id: int | None
    supplier_name: str
    invoice_date: date
    currency: Currency
    amount_original: Decimal
    exchange_rate: Decimal
    amount_ron: Decimal
    status: InvoiceStatus
    logged_by_id: int
