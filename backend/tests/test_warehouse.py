import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_session
from app.main import app
from app.models import AuditLog, GoodsReceipt, User, UserRole


class GoodsReceiptEndpointTests(unittest.TestCase):
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
        self.warehouse_user = User(
            email="warehouse@example.com",
            full_name="Warehouse User",
            hashed_password=hash_password("warehouse-password"),
            roles=[UserRole.WAREHOUSE.value],
        )
        self.session.add(self.warehouse_user)
        self.session.commit()
        self.session.refresh(self.warehouse_user)
        token = create_access_token(
            str(self.warehouse_user.id),
            self.warehouse_user.roles,
        )
        self.headers = {"Authorization": f"Bearer {token}"}

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

    def test_warehouse_user_can_create_receipt_without_purchase_order(self) -> None:
        response = self.client.post(
            "/api/v1/warehouse/receipts",
            headers=self.headers,
            json={
                "purchase_order_id": None,
                "notes": "One box was damaged.",
                "items_received": [
                    {"item": "Laptop", "qty": 4},
                    {"item": "Mouse", "qty": 2},
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertRegex(
            response.json()["receipt_number"],
            r"^REC-2026-\d{20}$",
        )
        self.assertIsNone(response.json()["purchase_order_id"])
        self.assertEqual(response.json()["notes"], "One box was damaged.")
        self.assertEqual(
            response.json()["items_received"],
            [{"item": "Laptop", "qty": 4}, {"item": "Mouse", "qty": 2}],
        )
        receipt = self.session.exec(select(GoodsReceipt)).one()
        self.assertEqual(receipt.received_by_id, self.warehouse_user.id)
        audit = self.session.exec(select(AuditLog)).one()
        self.assertEqual(audit.user_id, self.warehouse_user.id)
        self.assertEqual(audit.action, "create")
        self.assertEqual(audit.entity_name, "GoodsReceipt")
        self.assertEqual(audit.entity_id, str(receipt.id))

    def test_warehouse_user_can_list_receipt_history(self) -> None:
        response = self.client.get(
            "/api/v1/warehouse/receipts",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_receipt_creation_requires_warehouse_role(self) -> None:
        purchaser = User(
            email="buyer@example.com",
            full_name="Buyer",
            hashed_password=hash_password("buyer-password"),
            roles=[UserRole.PURCHASING.value],
        )
        self.session.add(purchaser)
        self.session.commit()
        self.session.refresh(purchaser)
        token = create_access_token(str(purchaser.id), purchaser.roles)

        response = self.client.post(
            "/api/v1/warehouse/receipts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receipt_number": "GR-002",
                "items_received": [{"item": "Laptop", "qty": 1}],
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.session.exec(select(GoodsReceipt)).all(), [])

    def test_receipt_creation_rejects_unknown_purchase_order(self) -> None:
        response = self.client.post(
            "/api/v1/warehouse/receipts",
            headers=self.headers,
            json={
                "receipt_number": "GR-003",
                "purchase_order_id": 999,
                "items_received": [{"item": "Laptop", "qty": 1}],
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.session.exec(select(GoodsReceipt)).all(), [])


if __name__ == "__main__":
    unittest.main()
