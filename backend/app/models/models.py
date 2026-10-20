from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import Column, Enum as SQLAlchemyEnum, Float, JSON, Numeric, String
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    PURCHASING = "purchasing"
    WAREHOUSE = "warehouse"
    ACCOUNTING = "accounting"
    ADMIN = "admin"


class PurchaseOrderStatus(str, Enum):
    ORDERED = "ordered"
    PARTIALLY_RECEIVED = "partially_received"
    BLOCKED = "blocked"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Currency(str, Enum):
    RON = "RON"
    EUR = "EUR"


class InvoiceStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    DISPUTED = "disputed"
    PAID = "paid"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: str
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = Field(default=True)
    roles: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )


class PurchaseOrder(SQLModel, table=True):
    __tablename__ = "purchase_orders"

    id: int | None = Field(default=None, primary_key=True)
    po_number: str = Field(index=True, unique=True)
    supplier_name: str
    order_date: date
    expected_delivery_date: date
    currency: str = Field(
        default="RON",
        sa_column=Column(String(length=3), nullable=False, default="RON"),
    )
    expected_total_original: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    items_summary: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_type=JSON,
    )
    status: PurchaseOrderStatus = Field(
        default=PurchaseOrderStatus.ORDERED,
        sa_column=Column(
            SQLAlchemyEnum(
                PurchaseOrderStatus,
                name="purchase_order_status",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            default=PurchaseOrderStatus.ORDERED,
        ),
    )
    created_by_id: int = Field(foreign_key="users.id")


class GoodsReceipt(SQLModel, table=True):
    __tablename__ = "goods_receipts"

    id: int | None = Field(default=None, primary_key=True)
    receipt_number: str = Field(index=True, unique=True)
    purchase_order_id: int | None = Field(
        default=None,
        foreign_key="purchase_orders.id",
        index=True,
    )
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    received_by_id: int = Field(foreign_key="users.id")
    items_received: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_type=JSON,
    )
    notes: str | None = None


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"

    id: int | None = Field(default=None, primary_key=True)
    invoice_number: str = Field(index=True, unique=True)
    purchase_order_id: int | None = Field(
        default=None,
        foreign_key="purchase_orders.id",
        index=True,
    )
    supplier_name: str
    invoice_date: date
    currency: Currency = Field(
        sa_column=Column(
            SQLAlchemyEnum(
                Currency,
                name="invoice_currency",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
        )
    )
    amount_original: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    exchange_rate: Decimal = Field(
        default=Decimal("1"),
        sa_column=Column(Numeric(12, 6), nullable=False, default=Decimal("1")),
    )
    amount_ron: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    status: InvoiceStatus = Field(
        default=InvoiceStatus.PENDING,
        sa_column=Column(
            SQLAlchemyEnum(
                InvoiceStatus,
                name="invoice_status",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            default=InvoiceStatus.PENDING,
        ),
    )
    logged_by_id: int = Field(foreign_key="users.id")


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    action: str
    entity_name: str
    entity_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )
