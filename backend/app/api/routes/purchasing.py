from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.api.dependencies import RequireRole
from app.api.pdf_response import pdf_response
from app.db.session import get_session
from app.models import GoodsReceipt, PurchaseOrder, User, UserRole
from app.schemas.matching import ThreeWayMatch
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderRead
from app.services.audit import log_action
from app.services.currency import ExchangeRateUnavailable, get_eur_to_ron_rate
from app.services.pdf_documents import generate_purchase_order_pdf
from app.services.three_way_match import calculate_three_way_match

router = APIRouter()


@router.get("/orders/{purchase_order_id}/pdf")
def download_purchase_order_pdf(
    purchase_order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(
        RequireRole(
            [
                UserRole.PURCHASING,
                UserRole.WAREHOUSE,
                UserRole.ACCOUNTING,
                UserRole.ADMIN,
            ]
        )
    ),
):
    order = session.get(PurchaseOrder, purchase_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return pdf_response(
        generate_purchase_order_pdf(order), "purchase-order", order.po_number
    )


@router.get("/orders", response_model=list[PurchaseOrderRead])
def list_purchase_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(
        RequireRole(
            [
                UserRole.PURCHASING,
                UserRole.WAREHOUSE,
                UserRole.ACCOUNTING,
                UserRole.ADMIN,
            ]
        )
    ),
) -> list[PurchaseOrder]:
    return session.exec(
        select(PurchaseOrder).order_by(
            desc(PurchaseOrder.order_date),
            desc(PurchaseOrder.id),
        )
    ).all()


@router.get("/{purchase_order_id}/match", response_model=ThreeWayMatch)
def get_purchase_order_match(
    purchase_order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(
        RequireRole([UserRole.PURCHASING, UserRole.ACCOUNTING])
    ),
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
async def create_purchase_order(
    order_data: PurchaseOrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(RequireRole([UserRole.PURCHASING])),
) -> PurchaseOrder:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is invalid")

    order_values = order_data.model_dump()
    if not order_values["po_number"]:
        timestamp = datetime.now(UTC)
        order_values["po_number"] = (
            f"PO-{timestamp.year}-{timestamp.strftime('%Y%m%d%H%M%S%f')}"
        )
    order_values["currency"] = order_data.currency.value
    order_values["items_summary"] = [
        {
            **item.model_dump(exclude={"unit_price"}),
            "unit_price": float(item.unit_price),
        }
        for item in order_data.items_summary
    ]
    order_values["expected_total_original"] = float(
        sum(
            (
                Decimal(item.qty) * item.unit_price
                for item in order_data.items_summary
            ),
            start=Decimal("0"),
        )
    )
    if order_data.currency.value == "EUR":
        try:
            budget_exchange_rate = await get_eur_to_ron_rate(order_data.order_date)
        except ExchangeRateUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        order_values["budget_exchange_rate"] = budget_exchange_rate.quantize(
            Decimal("0.000001"),
            rounding=ROUND_HALF_UP,
        )
    else:
        order_values["budget_exchange_rate"] = Decimal("1.000000")

    order = PurchaseOrder(
        **order_values,
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
