import re
import unittest
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models import (
    Currency,
    GoodsReceipt,
    Invoice,
    InvoiceStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
    User,
    UserRole,
)
from unittest.mock import patch


class PdfExportEndpointTests(unittest.TestCase):
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
        self.user = User(
            email="procurement@example.com",
            full_name="Procurement User",
            hashed_password=hash_password("password"),
            roles=[
                UserRole.PURCHASING.value,
                UserRole.WAREHOUSE.value,
                UserRole.ACCOUNTING.value,
            ],
        )
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)
        self.headers = {
            "Authorization": f"Bearer {create_access_token(str(self.user.id), self.user.roles)}"
        }
        self.order = PurchaseOrder(
            po_number="PO-TEST-001",
            supplier_name="Furnizor Ștefan & Fiica SRL",
            order_date=date(2026, 10, 1),
            expected_delivery_date=date(2026, 10, 20),
            currency="EUR",
            expected_total_original=Decimal("100.00"),
            budget_exchange_rate=Decimal("5.000000"),
            items_summary=[{"item": "Șuruburi M8", "qty": 10, "unit_price": 10.0}],
            status=PurchaseOrderStatus.ORDERED,
            created_by_id=self.user.id,
        )
        self.session.add(self.order)
        self.session.commit()
        self.session.refresh(self.order)
        self.invoice = Invoice(
            invoice_number="INV-TEST-001",
            purchase_order_id=self.order.id,
            supplier_name=self.order.supplier_name,
            invoice_date=date(2026, 10, 15),
            currency=Currency.EUR,
            amount_original=Decimal("100.00"),
            exchange_rate=Decimal("4.950000"),
            amount_ron=Decimal("495.00"),
            status=InvoiceStatus.MATCHED,
            match_notes="Matched against received goods.",
            logged_by_id=self.user.id,
        )
        self.receipt = GoodsReceipt(
            receipt_number="REC-TEST-001",
            purchase_order_id=self.order.id,
            received_by_id=self.user.id,
            items_received=[{"item": "Șuruburi M8", "qty": 10}],
            notes="Recepție completă.",
        )
        self.session.add_all([self.invoice, self.receipt])
        self.session.commit()
        self.session.refresh(self.invoice)
        self.session.refresh(self.receipt)

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

    def assert_pdf_download(self, response, filename: str) -> None:
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn(f'filename="{filename}"', response.headers["content-disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_all_three_records_download_as_pdf(self) -> None:
        paths = [
            (f"/api/v1/purchasing/orders/{self.order.id}/pdf", "purchase-order-PO-TEST-001.pdf"),
            (f"/api/v1/accounting/invoices/{self.invoice.id}/pdf", "supplier-invoice-report-INV-TEST-001.pdf"),
            (f"/api/v1/warehouse/receipts/{self.receipt.id}/pdf", "goods-receipt-REC-TEST-001.pdf"),
        ]
        for path, filename in paths:
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assert_pdf_download(response, filename)

    def test_pdf_exports_require_authentication_and_respect_record_permissions(self) -> None:
        path = f"/api/v1/accounting/invoices/{self.invoice.id}/pdf"
        self.assertEqual(self.client.get(path).status_code, 401)

        warehouse_user = User(
            email="warehouse@example.com",
            full_name="Warehouse User",
            hashed_password=hash_password("password"),
            roles=[UserRole.WAREHOUSE.value],
        )
        self.session.add(warehouse_user)
        self.session.commit()
        self.session.refresh(warehouse_user)
        token = create_access_token(str(warehouse_user.id), warehouse_user.roles)
        response = self.client.get(path, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)

    def test_pdf_exports_return_404_for_missing_records(self) -> None:
        paths = [
            "/api/v1/purchasing/orders/999/pdf",
            "/api/v1/accounting/invoices/999/pdf",
            "/api/v1/warehouse/receipts/999/pdf",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(
                    self.client.get(path, headers=self.headers).status_code, 404
                )

    def test_purchase_order_pdf_supports_long_tables_and_unicode(self) -> None:
        self.order.items_summary = [
            {"item": f"Articol {index} - Țeavă și șuruburi", "qty": 1, "unit_price": 2.5}
            for index in range(100)
        ]
        self.session.add(self.order)
        self.session.commit()
        response = self.client.get(
            f"/api/v1/purchasing/orders/{self.order.id}/pdf", headers=self.headers
        )
        self.assert_pdf_download(response, "purchase-order-PO-TEST-001.pdf")
        self.assertGreaterEqual(len(re.findall(rb"/Type\s*/Page\b", response.content)), 2)

    def test_invoice_export_preserves_stored_historical_values(self) -> None:
        response = self.client.get(
            f"/api/v1/accounting/invoices/{self.invoice.id}/pdf", headers=self.headers
        )
        self.assert_pdf_download(response, "supplier-invoice-report-INV-TEST-001.pdf")
        self.session.refresh(self.invoice)
        self.assertEqual(self.invoice.exchange_rate, Decimal("4.950000"))
        self.assertEqual(self.invoice.amount_ron, Decimal("495.00"))

    def test_unlinked_receipt_pdf_omits_optional_purchase_order_data(self) -> None:
        unlinked = GoodsReceipt(
            receipt_number="REC-UNLINKED",
            received_by_id=self.user.id,
            items_received=[{"item": "Piese", "qty": 2}],
        )
        self.session.add(unlinked)
        self.session.commit()
        self.session.refresh(unlinked)
        response = self.client.get(
            f"/api/v1/warehouse/receipts/{unlinked.id}/pdf", headers=self.headers
        )
        self.assert_pdf_download(response, "goods-receipt-REC-UNLINKED.pdf")


if __name__ == "__main__":
    unittest.main()
