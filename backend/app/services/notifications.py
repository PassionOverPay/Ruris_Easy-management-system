import logging
import smtplib
from collections.abc import Iterable

from sqlmodel import Session, select

from app.models import User, UserRole
from app.services.email_service import send_workflow_alert_email

logger = logging.getLogger(__name__)


def recipient_emails_for_roles(
    session: Session,
    roles: Iterable[UserRole],
) -> list[str]:
    role_names = {role.value for role in roles}
    return list(
        dict.fromkeys(
            user.email
            for user in session.exec(
                select(User).where(User.is_active.is_(True))
            ).all()
            if role_names.intersection(user.roles)
        )
    )


async def notify_teams(
    session: Session,
    roles: Iterable[UserRole],
    subject: str,
    body: str,
) -> None:
    recipients = recipient_emails_for_roles(session, roles)
    if not recipients:
        logger.warning(
            "Could not send workflow alert; no active recipients for %s", subject
        )
        return
    try:
        await send_workflow_alert_email(subject, body, recipients)
    except (OSError, RuntimeError, smtplib.SMTPException):
        logger.exception("Could not send workflow alert: %s", subject)
