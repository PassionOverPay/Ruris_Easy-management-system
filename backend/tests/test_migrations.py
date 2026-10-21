import importlib.util
import unittest
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


class PurchaseOrderBudgetRateMigrationTests(unittest.TestCase):
    def test_existing_purchase_orders_survive_with_unknown_rate(self) -> None:
        engine = create_engine("sqlite://")
        migration_path = (
            Path(__file__).resolve().parents[2]
            / "alembic"
            / "versions"
            / "d34e8a7f2c91_add_po_budget_exchange_rate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "po_budget_exchange_rate_migration",
            migration_path,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE purchase_orders ("
                    "id INTEGER PRIMARY KEY, "
                    "currency VARCHAR(3) NOT NULL, "
                    "expected_total_original FLOAT)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO purchase_orders "
                    "(id, currency, expected_total_original) "
                    "VALUES (1, 'EUR', 100.0)"
                )
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()

            row = connection.execute(
                text(
                    "SELECT currency, expected_total_original, "
                    "budget_exchange_rate FROM purchase_orders WHERE id = 1"
                )
            ).one()

        self.assertEqual(row.currency, "EUR")
        self.assertEqual(row.expected_total_original, 100.0)
        self.assertIsNone(row.budget_exchange_rate)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
