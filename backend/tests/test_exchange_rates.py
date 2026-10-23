import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models import ExchangeRate
from app.services.exchange_rates import fetch_and_store_eur_ron_rate


class ExchangeRatePersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    async def test_fetches_and_persists_rate_for_requested_date(self) -> None:
        with patch(
            "app.services.exchange_rates.get_eur_to_ron_rate",
            new_callable=AsyncMock,
            return_value=Decimal("5.3310"),
        ) as get_rate:
            stored = await fetch_and_store_eur_ron_rate(
                self.session,
                date(2026, 10, 16),
            )

        self.assertEqual(stored.date, date(2026, 10, 16))
        self.assertEqual(stored.currency_pair, "EUR_RON")
        self.assertEqual(stored.rate, 5.331)
        get_rate.assert_awaited_once_with(date(2026, 10, 16))

    async def test_repeated_fetch_updates_existing_date_without_duplicates(self) -> None:
        rate_date = date(2026, 10, 16)
        with patch(
            "app.services.exchange_rates.get_eur_to_ron_rate",
            new_callable=AsyncMock,
            side_effect=[Decimal("5.3310"), Decimal("5.3320")],
        ):
            await fetch_and_store_eur_ron_rate(self.session, rate_date)
            stored = await fetch_and_store_eur_ron_rate(self.session, rate_date)

        records = self.session.exec(select(ExchangeRate)).all()
        self.assertEqual(len(records), 1)
        self.assertEqual(stored.rate, 5.332)


if __name__ == "__main__":
    unittest.main()
