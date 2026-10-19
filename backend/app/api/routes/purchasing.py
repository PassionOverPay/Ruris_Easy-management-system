from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import GoodsReceipt, PurchaseOrder
from app.schemas.matching import ThreeWayMatch
from app.services.three_way_match import calculate_three_way_match

router = APIRouter()


@router.get("/{purchase_order_id}/match", response_model=ThreeWayMatch)
def get_purchase_order_match(
    purchase_order_id: int,
    session: Session = Depends(get_session),
) -> ThreeWayMatch:
    purchase_order = session.get(PurchaseOrder, purchase_order_id)
    if purchase_order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    receipts = session.exec(
        select(GoodsReceipt).where(
            GoodsReceipt.purchase_order_id == purchase_order_id
        )
    ).all()
    return calculate_three_way_match(purchase_order, receipts)
