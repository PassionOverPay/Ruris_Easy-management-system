from fastapi import APIRouter
from decimal import Decimal, ROUND_HALF_UP

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select

from app.api.dependencies import RequireRole
from app.db.session import get_session
from app.models import Currency, Invoice, User, UserRole
from app.schemas.invoice import InvoiceCreate, InvoiceRead
from app.services.audit import log_action
from app.services.currency import ExchangeRateUnavailable, get_eur_to_ron_rate

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
