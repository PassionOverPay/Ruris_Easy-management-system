from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select

from app.api.dependencies import RequireRole
from app.db.session import get_session
from app.models import (
    GoodsReceipt,
    Invoice,
    InvoiceStatus,
    PurchaseOrder,
    User,
    UserRole,
)
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptRead
from app.services.audit import log_action
from app.services.notifications import notify_teams
from app.services.three_way_match import (
    calculate_three_way_match,
    reconcile_po_invoices,
)

router = APIRouter()


@router.get(
    "/receipts",
    response_model=list[GoodsReceiptRead],
    dependencies=[Depends(RequireRole([UserRole.WAREHOUSE, UserRole.ADMIN]))],
)
def list_goods_receipts(
    session: Session = Depends(get_session),
) -> list[GoodsReceipt]:
    return session.exec(
        select(GoodsReceipt).order_by(
            desc(GoodsReceipt.received_at),
            desc(GoodsReceipt.id),
        )
    ).all()


@router.post("/receipts", response_model=GoodsReceiptRead, status_code=201)
async def create_goods_receipt(
    receipt_data: GoodsReceiptCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(RequireRole([UserRole.WAREHOUSE])),
) -> GoodsReceipt:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is invalid")

    if (
        receipt_data.purchase_order_id is not None
        and session.get(PurchaseOrder, receipt_data.purchase_order_id) is None
    ):
        raise HTTPException(status_code=404, detail="Purchase order not found")

    receipt_values = receipt_data.model_dump()
    if not receipt_values["receipt_number"]:
        timestamp = datetime.now(UTC)
        receipt_values["receipt_number"] = (
            f"REC-{timestamp.year}-{timestamp.strftime('%Y%m%d%H%M%S%f')}"
        )

    previous_invoice_statuses = {}
    if receipt_values["purchase_order_id"] is not None:
        previous_invoice_statuses = {
            invoice.id: invoice.status
            for invoice in session.exec(
                select(Invoice).where(
                    Invoice.purchase_order_id == receipt_values["purchase_order_id"]
                )
            ).all()
        }

    receipt = GoodsReceipt(
        **receipt_values,
        received_by_id=current_user.id,
    )
    session.add(receipt)
    try:
        session.flush()
        if receipt.purchase_order_id is not None:
            reconcile_po_invoices(receipt.purchase_order_id, session)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Goods receipt could not be saved; check its receipt number.",
        ) from exc

    session.refresh(receipt)
    log_action(
        session,
        current_user.id,
        "create",
        "GoodsReceipt",
        str(receipt.id),
    )
    if receipt.purchase_order_id is not None:
        purchase_order = session.get(PurchaseOrder, receipt.purchase_order_id)
        if purchase_order is not None:
            receipts = session.exec(
                select(GoodsReceipt).where(
                    GoodsReceipt.purchase_order_id == receipt.purchase_order_id
                )
            ).all()
            match = calculate_three_way_match(purchase_order, receipts)
            differences = [
                line for line in match.items if line.status.value != "matched"
            ]
            if differences:
                summary = "; ".join(
                    f"{line.item}: ordered {line.ordered_quantity}, received "
                    f"{line.received_quantity} ({line.status.value.replace('_', ' ')})"
                    for line in differences
                )
                await notify_teams(
                    session,
                    (UserRole.PURCHASING, UserRole.WAREHOUSE, UserRole.ACCOUNTING),
                    f"Receipt discrepancy: {purchase_order.po_number}",
                    f"Receipt {receipt.receipt_number} for purchase order "
                    f"{purchase_order.po_number} from {purchase_order.supplier_name} "
                    f"does not match the order: {summary}.",
                )

            disputed_invoices = session.exec(
                select(Invoice).where(
                    Invoice.purchase_order_id == receipt.purchase_order_id,
                    Invoice.status == InvoiceStatus.DISPUTED,
                )
            ).all()
            for invoice in disputed_invoices:
                if previous_invoice_statuses.get(invoice.id) != InvoiceStatus.DISPUTED:
                    await notify_teams(
                        session,
                        (UserRole.ACCOUNTING, UserRole.PURCHASING, UserRole.WAREHOUSE),
                        f"Invoice requires review: {invoice.invoice_number}",
                        f"Invoice {invoice.invoice_number} from {invoice.supplier_name} "
                        f"was marked disputed after receipt {receipt.receipt_number} "
                        f"for purchase order {purchase_order.po_number}. "
                        f"Review required: {invoice.match_notes or 'See the invoice record.'}",
                    )
    return receipt
