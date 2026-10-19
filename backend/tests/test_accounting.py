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
from app.models import AuditLog, Invoice, User, UserRole
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.services.currency import (
    ExchangeRateUnavailable,
    get_eur_to_ron_rate,
)


class CurrencyRateTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_bnr_rate_when_published_for_requested_date(self) -> None:
        bnr_xml = b"""<DataSet><Body><Cube date="2026-10-19">
        <Rate currency="EUR">5.3264</Rate></Cube></Body></DataSet>"""
        bnr_response = httpx.Response(
            200,
            content=bnr_xml,
            request=httpx.Request("GET", "https://www.bnr.ro/nbrfxrates.xml"),
        )
        client = AsyncMock()
        client.get.return_value = bnr_response
        async_client = AsyncMock()
        async_client.__aenter__.return_value = client

        with patch(
            "app.services.currency.httpx.AsyncClient",
            return_value=async_client,
        ):
            rate = await get_eur_to_ron_rate(date(2026, 10, 19))

        self.assertEqual(rate, Decimal("5.3264"))
        client.get.assert_awaited_once()

    async def test_uses_exact_historical_frankfurter_rate_when_bnr_date_differs(
        self,
    ) -> None:
        bnr_xml = b"""<DataSet><Body><Cube date="2026-10-19">
        <Rate currency="EUR">5.3264</Rate></Cube></Body></DataSet>"""
        bnr_response = httpx.Response(
            200,
            content=bnr_xml,
            request=httpx.Request("GET", "https://www.bnr.ro/nbrfxrates.xml"),
        )
        frankfurter_response = httpx.Response(
            200,
            json={
                "amount": 1,
                "base": "EUR",
                "date": "2026-10-16",
                "rates": {"RON": 5.331},
            },
            request=httpx.Request(
                "GET",
                "https://api.frankfurter.dev/v1/2026-10-16",
            ),
        )
        client = AsyncMock()
        client.get.side_effect = [bnr_response, frankfurter_response]
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
        bnr_response = httpx.Response(
            503,
            request=httpx.Request("GET", "https://www.bnr.ro/nbrfxrates.xml"),
        )
        frankfurter_response = httpx.Response(
            503,
            request=httpx.Request(
                "GET",
                "https://api.frankfurter.dev/v1/2026-10-16",
            ),
        )
        client = AsyncMock()
        client.get.side_effect = [bnr_response, frankfurter_response]
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

    async def test_rejects_non_matching_frankfurter_date(self) -> None:
        bnr_response = httpx.Response(
            503,
            request=httpx.Request("GET", "https://www.bnr.ro/nbrfxrates.xml"),
        )
        frankfurter_response = httpx.Response(
            200,
            json={
                "amount": 1,
                "base": "EUR",
                "date": "2026-10-15",
                "rates": {"RON": 5.2},
            },
            request=httpx.Request(
                "GET",
                "https://api.frankfurter.dev/v1/2026-10-16",
            ),
        )
        client = AsyncMock()
        client.get.side_effect = [bnr_response, frankfurter_response]
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
        self.assertEqual(response.json()["logged_by_id"], self.user_id)
        get_rate.assert_awaited_once_with(date(2026, 10, 16))
        saved = self.session.exec(select(Invoice)).one()
        self.assertEqual(saved.amount_ron, Decimal("533.10"))
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
        get_rate.assert_not_awaited()

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
