from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.dependencies import RequireRole
from app.db.session import get_session
from app.models import GoodsReceipt, PurchaseOrder, User, UserRole
from app.schemas.matching import ThreeWayMatch
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderRead
from app.services.audit import log_action
from app.services.three_way_match import calculate_three_way_match

router = APIRouter()


@router.get("/{purchase_order_id}/match", response_model=ThreeWayMatch)
def get_purchase_order_match(
    purchase_order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(RequireRole([UserRole.PURCHASING])),
) -> ThreeWayMatch:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is invalid")

    purchase_order = session.get(PurchaseOrder, purchase_order_id)
    if purchase_order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    receipts = session.exec(
        select(GoodsReceipt).where(
            GoodsReceipt.purchase_order_id == purchase_order_id
        )
    ).all()
    log_action(
        session,
        current_user.id,
        "read_match",
        "PurchaseOrder",
        str(purchase_order_id),
    )
    return calculate_three_way_match(purchase_order, receipts)


@router.post("", response_model=PurchaseOrderRead, status_code=201)
@router.post("/orders", response_model=PurchaseOrderRead, status_code=201)
def create_purchase_order(
    order_data: PurchaseOrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(RequireRole([UserRole.PURCHASING])),
) -> PurchaseOrder:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is invalid")

    order = PurchaseOrder(
        **order_data.model_dump(),
        created_by_id=current_user.id,
    )
    session.add(order)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Purchase order could not be saved; check its number.",
        ) from exc
    log_action(
        session,
        current_user.id,
        "create",
        "PurchaseOrder",
        str(order.id),
    )
    session.refresh(order)
    return order
