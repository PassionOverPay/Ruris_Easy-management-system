import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db.session import get_session
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models import GoodsReceipt, PurchaseOrder, User, UserRole


class ThreeWayMatchTests(unittest.TestCase):
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
            email="buyer@example.com",
            full_name="Buyer User",
            hashed_password=hash_password("correct-password"),
            roles=[UserRole.PURCHASING.value],
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

    def test_match_aggregates_receipts_and_reports_short_and_unexpected_items(
        self,
    ) -> None:
        purchase_order = PurchaseOrder(
            po_number="PO-001",
            supplier_name="Supplier",
            order_date=date(2026, 1, 1),
            expected_delivery_date=date(2026, 1, 10),
            items_summary=[
                {"item": "Laptop", "qty": 10},
                {"item": "Mouse", "qty": 4},
                {"item": "Monitor", "qty": 2},
            ],
            created_by_id=self.user_id,
        )
        self.session.add(purchase_order)
        self.session.commit()
        self.session.refresh(purchase_order)

        self.session.add_all(
            [
                GoodsReceipt(
                    receipt_number="GR-001",
                    purchase_order_id=purchase_order.id,
                    received_by_id=self.user_id,
                    items_received=[
                        {"item": "Laptop", "qty": 6},
                        {"item": "Monitor", "qty": 3},
                        {"item": "Cable", "qty": 2},
                    ],
                ),
                GoodsReceipt(
                    receipt_number="GR-002",
                    purchase_order_id=purchase_order.id,
                    received_by_id=self.user_id,
                    items_received=[{"item": "Laptop", "qty": 3}],
                ),
            ]
        )
        self.session.commit()

        response = self.client.get(
            f"/api/v1/purchasing/{purchase_order.id}/match",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "purchase_order_id": purchase_order.id,
                "items": [
                    {
                        "item": "Laptop",
                        "ordered_quantity": 10.0,
                        "received_quantity": 9.0,
                        "missing_quantity": 1.0,
                        "unexpected_quantity": 0.0,
                        "status": "missing",
                    },
                    {
                        "item": "Mouse",
                        "ordered_quantity": 4.0,
                        "received_quantity": 0.0,
                        "missing_quantity": 4.0,
                        "unexpected_quantity": 0.0,
                        "status": "missing",
                    },
                    {
                        "item": "Monitor",
                        "ordered_quantity": 2.0,
                        "received_quantity": 3.0,
                        "missing_quantity": 0.0,
                        "unexpected_quantity": 1.0,
                        "status": "over_received",
                    },
                    {
                        "item": "Cable",
                        "ordered_quantity": 0.0,
                        "received_quantity": 2.0,
                        "missing_quantity": 0.0,
                        "unexpected_quantity": 2.0,
                        "status": "unexpected",
                    },
                ],
            },
        )

    def test_missing_purchase_order_returns_404(self) -> None:
        response = self.client.get(
            "/api/v1/purchasing/999/match",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Purchase order not found")

    def test_accounting_user_can_review_purchase_order_match(self) -> None:
        purchase_order = PurchaseOrder(
            po_number="PO-ACCOUNTING-001",
            supplier_name="Supplier",
            order_date=date(2026, 10, 1),
            expected_delivery_date=date(2026, 10, 15),
            items_summary=[{"item": "Laptop", "qty": 2}],
            created_by_id=self.user_id,
        )
        accountant = User(
            email="accountant@example.com",
            full_name="Accountant",
            hashed_password=hash_password("accounting-password"),
            roles=[UserRole.ACCOUNTING.value],
        )
        self.session.add_all([purchase_order, accountant])
        self.session.commit()
        self.session.refresh(purchase_order)
        self.session.refresh(accountant)
        token = create_access_token(str(accountant.id), accountant.roles)

        response = self.client.get(
            f"/api/v1/purchasing/{purchase_order.id}/match",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purchase_order_id"], purchase_order.id)
        self.assertEqual(response.json()["items"][0]["ordered_quantity"], 2)


if __name__ == "__main__":
    unittest.main()
