from fastapi import APIRouter
from decimal import Decimal, ROUND_HALF_UP

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select
from sqlalchemy import func

from app.api.dependencies import RequireRole
from app.db.session import get_session
from app.models import (
    Currency,
    GoodsReceipt,
    Invoice,
    InvoiceStatus,
    PurchaseOrder,
    User,
    UserRole,
)
from app.schemas.invoice import InvoiceCreate, InvoiceRead
from app.schemas.matching import MatchStatus
from app.services.audit import log_action
from app.services.currency import ExchangeRateUnavailable, get_eur_to_ron_rate
from app.services.three_way_match import calculate_three_way_match

router = APIRouter()


@router.get(
    "/invoices",
    response_model=list[InvoiceRead],
    dependencies=[Depends(RequireRole([UserRole.ACCOUNTING, UserRole.ADMIN]))],
)
def list_invoices(
    session: Session = Depends(get_session),
) -> list[Invoice]:
    return session.exec(
        select(Invoice).order_by(desc(Invoice.invoice_date), desc(Invoice.id))
    ).all()


@router.post("/invoices", response_model=InvoiceRead, status_code=201)
async def create_invoice(
    invoice_data: InvoiceCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(RequireRole([UserRole.ACCOUNTING])),
) -> Invoice:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is invalid")

    invoice_status = InvoiceStatus.PENDING
    if invoice_data.purchase_order_id is not None:
        purchase_order = session.get(PurchaseOrder, invoice_data.purchase_order_id)
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if invoice_data.currency.value != purchase_order.currency:
            raise HTTPException(
                status_code=400,
                detail="Invoice currency must match the purchase order currency.",
            )

        existing_invoiced = session.exec(
            select(func.coalesce(func.sum(Invoice.amount_original), 0)).where(
                Invoice.purchase_order_id == purchase_order.id
            )
        ).one()
        cumulative_invoiced = Decimal(str(existing_invoiced)) + invoice_data.amount_original
        price_variance = (
            purchase_order.expected_total_original is not None
            and cumulative_invoiced > Decimal(str(purchase_order.expected_total_original))
        )

        if price_variance:
            invoice_status = InvoiceStatus.DISPUTED
        else:
            receipts = session.exec(
                select(GoodsReceipt).where(
                    GoodsReceipt.purchase_order_id == purchase_order.id
                )
            ).all()
            if receipts:
                match_result = calculate_three_way_match(purchase_order, receipts)
                invoice_status = (
                    InvoiceStatus.DISPUTED
                    if any(
                        item.status != MatchStatus.MATCHED
                        for item in match_result.items
                    )
                    else InvoiceStatus.MATCHED
                )

    if invoice_data.currency == Currency.EUR:
        try:
            exchange_rate = await get_eur_to_ron_rate(invoice_data.invoice_date)
        except ExchangeRateUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    else:
        exchange_rate = Decimal("1")

    amount_ron = (invoice_data.amount_original * exchange_rate).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    invoice = Invoice(
        **invoice_data.model_dump(),
        exchange_rate=exchange_rate,
        amount_ron=amount_ron,
        status=invoice_status,
        logged_by_id=current_user.id,
    )
    session.add(invoice)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invoice could not be saved; check the invoice number and linked IDs.",
        ) from exc
    log_action(
        session,
        current_user.id,
        "create",
        "Invoice",
        str(invoice.id),
    )
    session.refresh(invoice)
    return invoice
