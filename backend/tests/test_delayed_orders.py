import asyncio
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.scheduler import create_scheduler
from app.core.security import hash_password
from app.models import PurchaseOrder, PurchaseOrderStatus, User, UserRole
from app.services.delayed_orders import check_delayed_orders
from app.services.email_service import send_delay_alert_email
from app.worker import run_worker


class DelayedOrderAlertTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.purchasing_user = User(
            email="buyer@example.com",
            full_name="Buyer User",
            hashed_password=hash_password("password"),
            roles=[UserRole.PURCHASING.value],
        )
        self.warehouse_user = User(
            email="warehouse@example.com",
            full_name="Warehouse User",
            hashed_password=hash_password("password"),
            roles=[UserRole.WAREHOUSE.value],
        )
        self.session.add_all([self.purchasing_user, self.warehouse_user])
        self.session.commit()
        self.session.refresh(self.purchasing_user)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    async def test_alerts_only_overdue_nonterminal_orders_to_affected_team_users(self) -> None:
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        orders = [
            PurchaseOrder(
                po_number="PO-ORDERED",
                supplier_name="Supplier A",
                order_date=yesterday,
                expected_delivery_date=yesterday,
                created_by_id=self.purchasing_user.id,
                status=PurchaseOrderStatus.ORDERED,
            ),
            PurchaseOrder(
                po_number="PO-PARTIAL",
                supplier_name="Supplier B",
                order_date=yesterday,
                expected_delivery_date=yesterday,
                created_by_id=self.purchasing_user.id,
                status=PurchaseOrderStatus.PARTIALLY_RECEIVED,
            ),
            PurchaseOrder(
                po_number="PO-BLOCKED",
                supplier_name="Supplier F",
                order_date=yesterday,
                expected_delivery_date=yesterday,
                created_by_id=self.purchasing_user.id,
                status=PurchaseOrderStatus.BLOCKED,
            ),
            PurchaseOrder(
                po_number="PO-RECEIVED",
                supplier_name="Supplier C",
                order_date=yesterday,
                expected_delivery_date=yesterday,
                created_by_id=self.purchasing_user.id,
                status=PurchaseOrderStatus.RECEIVED,
            ),
            PurchaseOrder(
                po_number="PO-CANCELLED",
                supplier_name="Supplier D",
                order_date=yesterday,
                expected_delivery_date=yesterday,
                created_by_id=self.purchasing_user.id,
                status=PurchaseOrderStatus.CANCELLED,
            ),
            PurchaseOrder(
                po_number="PO-DUE-TODAY",
                supplier_name="Supplier E",
                order_date=yesterday,
                expected_delivery_date=today,
                created_by_id=self.purchasing_user.id,
                status=PurchaseOrderStatus.ORDERED,
            ),
        ]
        self.session.add_all(orders)
        self.session.commit()

        with patch(
            "app.services.delayed_orders.send_delay_alert_email",
            new_callable=AsyncMock,
        ) as send_alert:
            await check_delayed_orders(self.session)

        self.assertEqual(send_alert.await_count, 3)
        notified_numbers = [call.args[0] for call in send_alert.await_args_list]
        self.assertEqual(
            notified_numbers,
            ["PO-ORDERED", "PO-PARTIAL", "PO-BLOCKED"],
        )
        for call in send_alert.await_args_list:
            self.assertEqual(
                call.args[3],
                ["buyer@example.com", "warehouse@example.com"],
            )

    async def test_email_service_uses_configured_smtp_and_message_fields(self) -> None:
        with (
            patch("app.services.email_service.settings.SMTP_HOST", "smtp.example.com"),
            patch("app.services.email_service.settings.SMTP_PORT", "587"),
            patch("app.services.email_service.settings.SMTP_USER", "alerts@example.com"),
            patch("app.services.email_service.settings.SMTP_PASSWORD", "smtp-password"),
            patch(
                "app.services.email_service._send_email"
            ) as send_email,
        ):
            await send_delay_alert_email(
                "PO-123",
                "Supplier",
                date(2026, 10, 19),
                ["buyer@example.com"],
            )

        send_email.assert_called_once()
        message, host, port, username, password = send_email.call_args.args
        self.assertEqual(host, "smtp.example.com")
        self.assertEqual(port, 587)
        self.assertEqual(username, "alerts@example.com")
        self.assertEqual(password, "smtp-password")
        self.assertEqual(message["To"], "buyer@example.com")
        self.assertIn("PO-123", message.get_content())
        self.assertIn("2026-10-19", message.get_content())

    async def test_email_service_fails_explicitly_without_smtp_configuration(self) -> None:
        with (
            patch("app.services.email_service.settings.SMTP_HOST", None),
            patch("app.services.email_service.settings.SMTP_PORT", None),
            patch("app.services.email_service.settings.SMTP_USER", None),
            patch("app.services.email_service.settings.SMTP_PASSWORD", None),
        ):
            with self.assertRaisesRegex(RuntimeError, "SMTP_HOST"):
                await send_delay_alert_email(
                    "PO-123",
                    "Supplier",
                    date.today(),
                    ["buyer@example.com"],
                )

    def test_scheduler_runs_daily_at_eight(self) -> None:
        scheduler = create_scheduler()
        job = scheduler.get_job("delayed-order-email-alerts")

        self.assertIsNotNone(job)
        self.assertEqual(job.trigger.fields[5].name, "hour")
        self.assertEqual(str(job.trigger.fields[5]), "8")
        self.assertEqual(job.trigger.fields[6].name, "minute")
        self.assertEqual(str(job.trigger.fields[6]), "0")

    def test_scheduler_fetches_exchange_rates_daily_at_001(self) -> None:
        scheduler = create_scheduler()
        job = scheduler.get_job("daily-eur-ron-exchange-rate")

        self.assertIsNotNone(job)
        self.assertEqual(job.trigger.fields[5].name, "hour")
        self.assertEqual(str(job.trigger.fields[5]), "0")
        self.assertEqual(job.trigger.fields[6].name, "minute")
        self.assertEqual(str(job.trigger.fields[6]), "1")

    async def test_worker_starts_and_stops_scheduler(self) -> None:
        scheduler = create_scheduler()
        with patch("app.worker.create_scheduler", return_value=scheduler):
            worker_task = asyncio.create_task(run_worker())
            try:
                await asyncio.sleep(0)
                self.assertTrue(scheduler.running)
            finally:
                worker_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await worker_task

        self.assertFalse(scheduler.running)

    def test_api_health_does_not_start_background_scheduler(self) -> None:
        with patch("app.worker.create_scheduler") as create_worker_scheduler:
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/v1/health").status_code, 200)

        create_worker_scheduler.assert_not_called()


if __name__ == "__main__":
    unittest.main()
