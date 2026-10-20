import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core.config import settings
from app.core.security import decode_access_token, hash_password, verify_password
from app.db.session import get_session
from app.main import app
from app.models import AuditLog, PurchaseOrder, User, UserRole


class AuthenticationAndAuthorizationTests(unittest.TestCase):
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

        self.purchaser = User(
            email="buyer@example.com",
            full_name="Buyer User",
            hashed_password=hash_password("buyer-password"),
            roles=[UserRole.PURCHASING.value],
        )
        self.accountant = User(
            email="accounting@example.com",
            full_name="Accounting User",
            hashed_password=hash_password("accounting-password"),
            roles=[UserRole.ACCOUNTING.value],
        )
        self.admin = User(
            email="admin@example.com",
            full_name="Admin User",
            hashed_password=hash_password("admin-password"),
            roles=[UserRole.ADMIN.value],
        )
        self.session.add_all([self.purchaser, self.accountant, self.admin])
        self.session.commit()
        self.session.refresh(self.purchaser)
        self.session.refresh(self.accountant)
        self.session.refresh(self.admin)

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

    def token_for(self, email: str, password: str) -> str:
        response = self.client.post(
            "/token",
            data={"username": email, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def test_token_endpoint_authenticates_and_audits_successful_login(self) -> None:
        token = self.token_for("buyer@example.com", "buyer-password")

        self.assertTrue(token)
        self.assertEqual(
            decode_access_token(token)["roles"],
            [UserRole.PURCHASING.value],
        )
        logs = self.session.exec(select(AuditLog)).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].user_id, self.purchaser.id)
        self.assertEqual(logs[0].action, "login")
        self.assertEqual(logs[0].entity_name, "User")

    def test_invalid_credentials_are_rejected(self) -> None:
        response = self.client.post(
            "/token",
            data={"username": "buyer@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.session.exec(select(AuditLog)).all(), [])

    def test_purchasing_role_can_create_and_audit_purchase_order(self) -> None:
        token = self.token_for("buyer@example.com", "buyer-password")
        response = self.client.post(
            "/api/v1/purchasing/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_number": "PO-AUTH-001",
                "supplier_name": "Supplier",
                "order_date": "2026-10-19",
                "expected_delivery_date": "2026-10-26",
                "currency": "EUR",
                "items_summary": [
                    {"item": "Laptop", "qty": 2, "unit_price": "125.50"}
                ],
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        order = self.session.exec(select(PurchaseOrder)).one()
        self.assertEqual(order.currency, "EUR")
        self.assertEqual(order.expected_total_original, 251.0)
        self.assertEqual(response.json()["expected_total_original"], 251.0)
        self.assertEqual(order.created_by_id, self.purchaser.id)
        logs = self.session.exec(select(AuditLog)).all()
        self.assertEqual(
            [(entry.action, entry.entity_name) for entry in logs],
            [("login", "User"), ("create", "PurchaseOrder")],
        )
        self.assertEqual(logs[1].entity_id, str(order.id))

    def test_purchase_order_number_is_generated_when_omitted(self) -> None:
        token = self.token_for("buyer@example.com", "buyer-password")
        response = self.client.post(
            "/api/v1/purchasing/orders",
            headers={"Authorization": "Bearer " + token},
            json={
                "supplier_name": "Supplier",
                "order_date": "2026-10-19",
                "expected_delivery_date": "2026-10-26",
                "items_summary": [
                    {"item": "Laptop", "qty": 2, "unit_price": 15.25}
                ],
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertRegex(response.json()["po_number"], r"^PO-2026-\d{20}$")

    def test_purchase_order_list_is_newest_first(self) -> None:
        older_order = PurchaseOrder(
            po_number="PO-OLD",
            supplier_name="Older supplier",
            order_date=date(2026, 10, 18),
            expected_delivery_date=date(2026, 10, 25),
            created_by_id=self.purchaser.id,
        )
        newer_order = PurchaseOrder(
            po_number="PO-NEW",
            supplier_name="Newer supplier",
            order_date=date(2026, 10, 19),
            expected_delivery_date=date(2026, 10, 26),
            created_by_id=self.purchaser.id,
        )
        self.session.add_all([older_order, newer_order])
        self.session.commit()

        token = self.token_for("buyer@example.com", "buyer-password")
        response = self.client.get(
            "/api/v1/purchasing/orders",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [order["po_number"] for order in response.json()],
            ["PO-NEW", "PO-OLD"],
        )

    def test_wrong_role_and_missing_token_are_rejected(self) -> None:
        token = self.token_for("accounting@example.com", "accounting-password")
        forbidden = self.client.post(
            "/api/v1/purchasing",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_number": "PO-AUTH-002",
                "supplier_name": "Supplier",
                "order_date": "2026-10-19",
                "expected_delivery_date": "2026-10-26",
            },
        )
        unauthorized = self.client.post(
            "/api/v1/purchasing",
            json={
                "po_number": "PO-AUTH-003",
                "supplier_name": "Supplier",
                "order_date": "2026-10-19",
                "expected_delivery_date": "2026-10-26",
            },
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(self.session.exec(select(PurchaseOrder)).all(), [])

    def test_user_role_is_loaded_from_database_for_each_request(self) -> None:
        token = self.token_for("buyer@example.com", "buyer-password")
        self.purchaser.roles = [UserRole.ACCOUNTING.value]
        self.session.add(self.purchaser)
        self.session.commit()

        response = self.client.post(
            "/api/v1/purchasing",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "po_number": "PO-AUTH-004",
                "supplier_name": "Supplier",
                "order_date": "2026-10-19",
                "expected_delivery_date": "2026-10-26",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.session.exec(select(PurchaseOrder)).all(), [])

    def test_admin_can_provision_a_department_user(self) -> None:
        token = self.token_for("admin@example.com", "admin-password")

        response = self.client.post(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "warehouse@example.com",
                "password": "initial-password",
                "full_name": "Warehouse User",
                "roles": ["warehouse", "accounting"],
            },
        )

        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertNotIn("password", response_data)
        self.assertNotIn("hashed_password", response_data)
        self.assertEqual(response_data["email"], "warehouse@example.com")
        self.assertEqual(response_data["roles"], ["warehouse", "accounting"])
        self.assertEqual(response_data["full_name"], "Warehouse User")
        created_user = self.session.exec(
            select(User).where(User.email == "warehouse@example.com")
        ).one()
        self.assertNotEqual(created_user.hashed_password, "initial-password")
        self.assertTrue(
            verify_password("initial-password", created_user.hashed_password)
        )
        audit_log = self.session.exec(
            select(AuditLog).where(
                AuditLog.entity_name == "User",
                AuditLog.action == "create",
            )
        ).one()
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.action, "create")
        self.assertEqual(audit_log.entity_id, str(created_user.id))

    def test_admin_can_list_users_with_roles_and_active_status(self) -> None:
        token = self.token_for("admin@example.com", "admin-password")

        response = self.client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        listed_user = next(
            user for user in response.json() if user["email"] == "buyer@example.com"
        )
        self.assertEqual(listed_user["full_name"], "Buyer User")
        self.assertEqual(listed_user["roles"], ["purchasing"])
        self.assertTrue(listed_user["is_active"])
        self.assertIn("created_at", listed_user)
        self.assertNotIn("hashed_password", listed_user)

    def test_department_user_cannot_list_admin_users(self) -> None:
        token = self.token_for("buyer@example.com", "buyer-password")

        response = self.client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)

    def test_department_user_cannot_provision_users(self) -> None:
        token = self.token_for("buyer@example.com", "buyer-password")

        response = self.client.post(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "new-user@example.com",
                "password": "initial-password",
                "full_name": "New User",
                "roles": ["accounting"],
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(
            self.session.exec(
                select(User).where(User.email == "new-user@example.com")
            ).first()
        )

    def test_current_user_endpoint_returns_profile_without_password_fields(self) -> None:
        token = self.token_for("buyer@example.com", "buyer-password")

        response = self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "buyer@example.com")
        self.assertEqual(response.json()["full_name"], "Buyer User")
        self.assertEqual(response.json()["roles"], ["purchasing"])
        self.assertNotIn("password", response.json())
        self.assertNotIn("hashed_password", response.json())

    def test_current_user_endpoint_requires_authentication(self) -> None:
        response = self.client.get("/api/v1/users/me")

        self.assertEqual(response.status_code, 401)

    def test_admin_cannot_create_another_admin_through_provisioning(self) -> None:
        token = self.token_for("admin@example.com", "admin-password")

        response = self.client.post(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "another-admin@example.com",
                "password": "initial-password",
                "full_name": "Another Admin",
                "roles": ["admin"],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_multiple_roles_authorize_each_matching_route(self) -> None:
        self.purchaser.roles = [
            UserRole.PURCHASING.value,
            UserRole.ACCOUNTING.value,
        ]
        self.session.add(self.purchaser)
        self.session.commit()
        token = self.token_for("buyer@example.com", "buyer-password")
        headers = {"Authorization": f"Bearer {token}"}

        purchase_order_response = self.client.post(
            "/api/v1/purchasing",
            headers=headers,
            json={
                "po_number": "PO-MULTI-001",
                "supplier_name": "Supplier",
                "order_date": "2026-10-19",
                "expected_delivery_date": "2026-10-26",
            },
        )
        invoice_response = self.client.post(
            "/api/v1/accounting/invoices",
            headers=headers,
            json={
                "invoice_number": "INV-MULTI-001",
                "supplier_name": "Supplier",
                "invoice_date": "2026-10-19",
                "currency": "RON",
                "amount_original": "10.00",
            },
        )

        self.assertEqual(purchase_order_response.status_code, 201)
        self.assertEqual(invoice_response.status_code, 201)


if __name__ == "__main__":
    unittest.main()
