import logging
import smtplib
from datetime import date

from sqlmodel import Session, select

from app.models import PurchaseOrder, PurchaseOrderStatus, UserRole
from app.services.email_service import send_delay_alert_email
from app.services.notifications import recipient_emails_for_roles

logger = logging.getLogger(__name__)


async def check_delayed_orders(db_session: Session) -> None:
    today = date.today()
    delayed_orders = db_session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.expected_delivery_date < today,
            PurchaseOrder.status.notin_(
                (PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.CANCELLED)
            ),
        )
    ).all()
    if not delayed_orders:
        return

    recipient_emails = recipient_emails_for_roles(
        db_session,
        (UserRole.PURCHASING, UserRole.WAREHOUSE, UserRole.ACCOUNTING),
    )
    if not recipient_emails:
        logger.warning("Delayed purchase orders found, but no active team recipients exist")
        return

    for order in delayed_orders:
        try:
            await send_delay_alert_email(
                order.po_number,
                order.supplier_name,
                order.expected_delivery_date,
                recipient_emails,
            )
        except (OSError, RuntimeError, smtplib.SMTPException):
            logger.exception(
                "Could not send delayed-order alert for PO %s",
                order.po_number,
            )
