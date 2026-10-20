import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.db.session import get_session
from app.main import app
from app.models import (
    AuditLog,
    GoodsReceipt,
    Invoice,
    InvoiceStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
    User,
    UserRole,
)
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.services.currency import (
    ExchangeRateUnavailable,
    get_eur_to_ron_rate,
)


class CurrencyRateTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_latest_ecb_rate_on_or_before_requested_date(self) -> None:
        ecb_csv = (
            "TIME_PERIOD,CURRENCY,CURRENCY_DENOM,OBS_VALUE\n"
            "2026-10-16,RON,EUR,5.3310\n"
            "2026-10-19,RON,EUR,5.3264\n"
            "2026-10-21,RON,EUR,5.4000\n"
        )
        ecb_response = httpx.Response(
            200,
            text=ecb_csv,
            request=httpx.Request(
                "GET",
                "https://data-api.ecb.europa.eu/service/data/EXR/D.RON.EUR.SP00.A",
            ),
        )
        client = AsyncMock()
        client.get.return_value = ecb_response
        async_client = AsyncMock()
        async_client.__aenter__.return_value = client

        with patch(
            "app.services.currency.httpx.AsyncClient",
            return_value=async_client,
        ):
            rate = await get_eur_to_ron_rate(date(2026, 10, 20))

        self.assertEqual(rate, Decimal("5.3264"))
        client.get.assert_awaited_once()
        self.assertEqual(
            client.get.await_args.kwargs["params"],
            {
                "startPeriod": "2026-10-13",
                "endPeriod": "2026-10-20",
                "format": "csvdata",
            },
        )

    async def test_uses_frankfurter_previous_rate_when_ecb_has_no_rate(
        self,
    ) -> None:
        ecb_response = httpx.Response(
            200,
            text="TIME_PERIOD,CURRENCY,CURRENCY_DENOM,OBS_VALUE\n",
            request=httpx.Request(
                "GET",
                "https://data-api.ecb.europa.eu/service/data/EXR/D.RON.EUR.SP00.A",
            ),
        )
        frankfurter_response = httpx.Response(
            200,
            json={
                "amount": 1,
                "base": "EUR",
                "date": "2026-10-15",
                "rates": {"RON": 5.331},
            },
            request=httpx.Request(
                "GET",
                "https://api.frankfurter.dev/v1/2026-10-16",
            ),
        )
        client = AsyncMock()
        client.get.side_effect = [ecb_response, frankfurter_response]
        async_client = AsyncMock()
        async_client.__aenter__.return_value = client

        with patch(
            "app.services.currency.httpx.AsyncClient",
            return_value=async_client,
        ):
            rate = await get_eur_to_ron_rate(date(2026, 10, 16))

        self.assertEqual(rate, Decimal("5.331"))
        self.assertEqual(client.get.await_count, 2)
        self.assertEqual(
            client.get.await_args_list[1].args[0],
            "https://api.frankfurter.dev/v1/2026-10-16",
        )

    async def test_fails_if_neither_source_can_provide_rate(self) -> None:
        ecb_response = httpx.Response(
            503,
            request=httpx.Request(
                "GET",
                "https://data-api.ecb.europa.eu/service/data/EXR/D.RON.EUR.SP00.A",
            ),
        )
        frankfurter_response = httpx.Response(
            503,
            request=httpx.Request(
                "GET",
                "https://api.frankfurter.dev/v1/2026-10-16",
            ),
        )
        client = AsyncMock()
        client.get.side_effect = [ecb_response, frankfurter_response]
        async_client = AsyncMock()
        async_client.__aenter__.return_value = client

        with (
            patch(
                "app.services.currency.httpx.AsyncClient",
                return_value=async_client,
            ),
            self.assertRaises(ExchangeRateUnavailable) as error,
        ):
            await get_eur_to_ron_rate(date(2026, 10, 16))

        self.assertIn("No EUR/RON rate is available", str(error.exception))
        self.assertIn("No invoice was saved", str(error.exception))

    async def test_rejects_future_frankfurter_date(self) -> None:
        ecb_response = httpx.Response(
            503,
            request=httpx.Request(
                "GET",
                "https://data-api.ecb.europa.eu/service/data/EXR/D.RON.EUR.SP00.A",
            ),
        )
        frankfurter_response = httpx.Response(
            200,
            json={
                "amount": 1,
                "base": "EUR",
                "date": "2026-10-17",
                "rates": {"RON": 5.2},
            },
            request=httpx.Request(
                "GET",
                "https://api.frankfurter.dev/v1/2026-10-16",
            ),
        )
        client = AsyncMock()
        client.get.side_effect = [ecb_response, frankfurter_response]
        async_client = AsyncMock()
        async_client.__aenter__.return_value = client

        with (
            patch(
                "app.services.currency.httpx.AsyncClient",
                return_value=async_client,
            ),
            self.assertRaises(ExchangeRateUnavailable),
        ):
            await get_eur_to_ron_rate(date(2026, 10, 16))


class InvoiceEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.secret_patcher = patch.object(
            settings,
            "JWT_SECRET_KEY",
            "test-secret-key-with-at-least-32-characters",
        )
        self.secret_patcher.start()
        user = User(
            email="accounting@example.com",
            full_name="Accounting User",
            hashed_password=hash_password("correct-password"),
            roles=[UserRole.ACCOUNTING.value],
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        self.user_id = user.id
        self.headers = {
            "Authorization": f"Bearer {create_access_token(str(user.id), user.roles)}"
        }

        def override_get_session():
            yield self.session

        app.dependency_overrides[get_session] = override_get_session
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.pop(get_session, None)
        self.session.close()
        self.engine.dispose()
        self.secret_patcher.stop()

    def invoice_payload(self, currency: str) -> dict[str, object]:
        return {
            "invoice_number": "INV-001",
            "supplier_name": "Supplier",
            "invoice_date": "2026-10-16",
            "currency": currency,
            "amount_original": "100.00",
        }

    def create_purchase_order(self) -> PurchaseOrder:
        order = PurchaseOrder(
            po_number="PO-MATCH-001",
            supplier_name="Supplier",
            order_date=date(2026, 10, 1),
            expected_delivery_date=date(2026, 10, 20),
            items_summary=[
                {
                    "item": "Laptop",
                    "qty": 2,
                    "unit_price": 50.0,
                    "currency": "RON",
                }
            ],
            expected_total_original=100.0,
            status=PurchaseOrderStatus.ORDERED,
            created_by_id=self.user_id,
        )
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        return order

    def create_receipt(
        self,
        order: PurchaseOrder,
        items: list[dict[str, object]],
    ) -> None:
        self.session.add(
            GoodsReceipt(
                receipt_number="REC-MATCH-001",
                purchase_order_id=order.id,
                received_by_id=self.user_id,
                items_received=items,
            )
        )
        self.session.commit()

    def test_eur_invoice_fetches_rate_and_saves_converted_amount(self) -> None:
        with patch(
            "app.api.routes.accounting.get_eur_to_ron_rate",
            new_callable=AsyncMock,
            return_value=Decimal("5.331"),
        ) as get_rate:
            response = self.client.post(
                "/api/v1/accounting/invoices",
                json=self.invoice_payload("EUR"),
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["exchange_rate"], "5.331000")
        self.assertEqual(response.json()["amount_ron"], "533.10")
        self.assertEqual(response.json()["status"], "pending")
        self.assertEqual(response.json()["logged_by_id"], self.user_id)
        get_rate.assert_awaited_once_with(date(2026, 10, 16))
        saved = self.session.exec(select(Invoice)).one()
        self.assertEqual(saved.amount_ron, Decimal("533.10"))
        self.assertEqual(saved.status, InvoiceStatus.PENDING)
        audit = self.session.exec(select(AuditLog)).one()
        self.assertEqual(audit.action, "create")
        self.assertEqual(audit.entity_name, "Invoice")
        self.assertEqual(audit.entity_id, str(saved.id))

    def test_non_accounting_role_cannot_create_invoice(self) -> None:
        purchaser = User(
            email="buyer@example.com",
            full_name="Buyer User",
            hashed_password=hash_password("buyer-password"),
            roles=[UserRole.PURCHASING.value],
        )
        self.session.add(purchaser)
        self.session.commit()
        self.session.refresh(purchaser)
        token = create_access_token(str(purchaser.id), purchaser.roles)

        response = self.client.post(
            "/api/v1/accounting/invoices",
            json=self.invoice_payload("RON"),
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.session.exec(select(Invoice)).all(), [])

    def test_ron_invoice_does_not_call_external_rate_service(self) -> None:
        with patch(
            "app.api.routes.accounting.get_eur_to_ron_rate",
            new_callable=AsyncMock,
        ) as get_rate:
            response = self.client.post(
                "/api/v1/accounting/invoices",
                json=self.invoice_payload("RON"),
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["exchange_rate"], "1.000000")
        self.assertEqual(response.json()["amount_ron"], "100.00")
        self.assertEqual(response.json()["status"], "pending")
        get_rate.assert_not_awaited()

    def test_invoice_is_matched_when_receipt_quantities_match_order(self) -> None:
        order = self.create_purchase_order()
        self.create_receipt(order, [{"item": "Laptop", "qty": 2}])
        payload = self.invoice_payload("RON")
        payload["purchase_order_id"] = order.id

        response = self.client.post(
            "/api/v1/accounting/invoices",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "matched")
        self.assertEqual(
            response.json()["match_notes"],
            "Auto-matched: Received quantity and price verified.",
        )
        saved = self.session.exec(select(Invoice)).one()
        self.assertEqual(saved.status, InvoiceStatus.MATCHED)

    def test_invoice_is_disputed_when_receipt_quantities_differ(self) -> None:
        order = self.create_purchase_order()
        self.create_receipt(order, [{"item": "Laptop", "qty": 1}])
        payload = self.invoice_payload("RON")
        payload["purchase_order_id"] = order.id

        response = self.client.post(
            "/api/v1/accounting/invoices",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "disputed")
        self.assertEqual(
            response.json()["match_notes"],
            "Disputed: Received quantities do not match the purchase order.",
        )

    def test_invoice_creation_reconciles_against_current_received_value(self) -> None:
        order = self.create_purchase_order()
        payload = self.invoice_payload("RON")
        payload["purchase_order_id"] = order.id

        response = self.client.post(
            "/api/v1/accounting/invoices",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "disputed")
        self.assertEqual(
            response.json()["match_notes"],
            "Disputed: Cumulative invoice total (100.00) exceeds received goods value (0).",
        )
        saved = self.session.exec(select(Invoice)).one()
        self.assertEqual(saved.status, InvoiceStatus.DISPUTED)

    def test_cumulative_invoices_over_po_total_are_disputed(self) -> None:
        order = self.create_purchase_order()
        self.create_receipt(order, [{"item": "Laptop", "qty": 2}])
        first_payload = self.invoice_payload("RON")
        first_payload.update(
            invoice_number="INV-UNDER",
            purchase_order_id=order.id,
            amount_original="60.00",
        )
        first_response = self.client.post(
            "/api/v1/accounting/invoices",
            json=first_payload,
            headers=self.headers,
        )
        self.assertEqual(first_response.status_code, 201, first_response.text)
        self.assertEqual(first_response.json()["status"], "matched")

        second_payload = self.invoice_payload("RON")
        second_payload.update(
            invoice_number="INV-OVER",
            purchase_order_id=order.id,
            amount_original="50.00",
        )
        second_response = self.client.post(
            "/api/v1/accounting/invoices",
            json=second_payload,
            headers=self.headers,
        )

        self.assertEqual(second_response.status_code, 201, second_response.text)
        self.assertEqual(second_response.json()["status"], "disputed")
        self.assertEqual(
            self.session.exec(
                select(Invoice).where(Invoice.invoice_number == "INV-OVER")
            ).one().status,
            InvoiceStatus.DISPUTED,
        )

    def test_invoice_currency_must_match_purchase_order(self) -> None:
        order = self.create_purchase_order()
        order.currency = "EUR"
        self.session.add(order)
        self.session.commit()
        payload = self.invoice_payload("RON")
        payload["purchase_order_id"] = order.id

        response = self.client.post(
            "/api/v1/accounting/invoices",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("currency must match", response.json()["detail"])
        self.assertEqual(self.session.exec(select(Invoice)).all(), [])

    def test_accounting_user_can_list_invoice_history(self) -> None:
        response = self.client.get(
            "/api/v1/accounting/invoices",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_rate_failure_returns_503_and_does_not_save_invoice(self) -> None:
        with patch(
            "app.api.routes.accounting.get_eur_to_ron_rate",
            new_callable=AsyncMock,
            side_effect=ExchangeRateUnavailable(
                "No EUR/RON rate is available for 2026-10-16. No invoice was saved."
            ),
        ):
            response = self.client.post(
                "/api/v1/accounting/invoices",
                json=self.invoice_payload("EUR"),
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("No invoice was saved", response.json()["detail"])
        self.assertEqual(self.session.exec(select(Invoice)).all(), [])


if __name__ == "__main__":
    unittest.main()
