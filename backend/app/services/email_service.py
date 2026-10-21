import asyncio
import smtplib
import ssl
from collections.abc import Sequence
from datetime import date
from email.message import EmailMessage

from app.core.config import settings


def _send_email(
    message: EmailMessage,
    host: str,
    port: int,
    username: str,
    password: str,
) -> None:
    if port == 465:
        with smtplib.SMTP_SSL(
            host,
            port,
            timeout=30,
            context=ssl.create_default_context(),
        ) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)


async def send_delay_alert_email(
    po_number: str,
    supplier: str,
    expected_date: date,
    recipient_emails: Sequence[str],
) -> None:
    await send_workflow_alert_email(
        f"Delayed purchase order: {po_number}",
        f"Purchase order {po_number} from {supplier} is delayed. "
        f"Its expected delivery date was {expected_date.isoformat()}.",
        recipient_emails,
    )


async def send_workflow_alert_email(
    subject: str,
    body: str,
    recipient_emails: Sequence[str],
) -> None:
    if not recipient_emails:
        return

    host = settings.SMTP_HOST
    port_value = settings.SMTP_PORT
    username = settings.SMTP_USER
    password = settings.SMTP_PASSWORD
    if not all((host, port_value, username, password)):
        raise RuntimeError(
            "SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD must be configured"
        )
    try:
        port = int(port_value)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be an integer") from exc

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = username
    message["To"] = ", ".join(recipient_emails)
    message.set_content(body)
    await asyncio.to_thread(
        _send_email,
        message,
        host,
        port,
        username,
        password,
    )
