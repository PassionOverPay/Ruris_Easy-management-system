from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select

from app.api.dependencies import RequireRole
from app.api.pdf_response import pdf_response
from app.db.session import get_session
from app.models import (
    Currency,
    ExchangeRate,
    Invoice,
    InvoiceStatus,
    PurchaseOrder,
    User,
    UserRole,
)
from app.schemas.invoice import InvoiceCreate, InvoiceRead
from app.services.audit import log_action
from app.services.notifications import notify_teams
from app.services.pdf_documents import generate_invoice_pdf
from app.services.three_way_match import reconcile_po_invoices

router = APIRouter()


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(
        RequireRole([UserRole.ACCOUNTING, UserRole.ADMIN])
    ),
):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    purchase_order = (
        session.get(PurchaseOrder, invoice.purchase_order_id)
        if invoice.purchase_order_id is not None
        else None
    )
    return pdf_response(
        generate_invoice_pdf(invoice, purchase_order),
        "supplier-invoice-report",
        invoice.invoice_number,
    )


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

    if invoice_data.purchase_order_id is not None:
        purchase_order = session.get(PurchaseOrder, invoice_data.purchase_order_id)
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if invoice_data.currency.value != purchase_order.currency:
            raise HTTPException(
                status_code=400,
                detail="Invoice currency must match the purchase order currency.",
            )

    if invoice_data.currency == Currency.EUR:
        stored_rate = session.exec(
            select(ExchangeRate).where(
                ExchangeRate.date == invoice_data.invoice_date,
                ExchangeRate.currency_pair == "EUR_RON",
            )
        ).first()
        if stored_rate is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "No stored EUR/RON exchange rate is available for "
                    f"{invoice_data.invoice_date}. No invoice was saved."
                ),
            )
        exchange_rate = Decimal(str(stored_rate.rate)).quantize(
            Decimal("0.000001"),
            rounding=ROUND_HALF_UP,
        )
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
        session.flush()
        if invoice.purchase_order_id is not None:
            reconcile_po_invoices(invoice.purchase_order_id, session)
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
    if invoice.status == InvoiceStatus.DISPUTED:
        order_label = (
            f"purchase order {invoice.purchase_order_id}"
            if invoice.purchase_order_id is not None
            else "no linked purchase order"
        )
        await notify_teams(
            session,
            (UserRole.ACCOUNTING, UserRole.PURCHASING, UserRole.WAREHOUSE),
            f"Invoice requires review: {invoice.invoice_number}",
            f"Invoice {invoice.invoice_number} from {invoice.supplier_name} was marked "
            f"disputed ({order_label}). Review required: "
            f"{invoice.match_notes or 'See the invoice record.'}",
        )
    return invoice
