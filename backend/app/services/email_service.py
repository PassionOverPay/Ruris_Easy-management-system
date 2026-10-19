import asyncio
import os
import smtplib
import ssl
from collections.abc import Sequence
from datetime import date
from email.message import EmailMessage


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
    if not recipient_emails:
        return

    host = os.getenv("SMTP_HOST")
    port_value = os.getenv("SMTP_PORT")
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not all((host, port_value, username, password)):
        raise RuntimeError(
            "SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD must be configured"
        )
    try:
        port = int(port_value)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be an integer") from exc

    message = EmailMessage()
    message["Subject"] = f"Delayed purchase order: {po_number}"
    message["From"] = username
    message["To"] = ", ".join(recipient_emails)
    message.set_content(
        f"Purchase order {po_number} from {supplier} is delayed. "
        f"Its expected delivery date was {expected_date.isoformat()}."
    )
    await asyncio.to_thread(
        _send_email,
        message,
        host,
        port,
        username,
        password,
    )
