from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.api.dependencies import RequireRole
from app.db.session import get_session
from app.models import GoodsReceipt, PurchaseOrder, User, UserRole
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptRead
from app.services.audit import log_action

router = APIRouter()


@router.post("/receipts", response_model=GoodsReceiptRead, status_code=201)
def create_goods_receipt(
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

    receipt = GoodsReceipt(
        **receipt_data.model_dump(),
        received_by_id=current_user.id,
    )
    session.add(receipt)
    try:
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
    return receipt
