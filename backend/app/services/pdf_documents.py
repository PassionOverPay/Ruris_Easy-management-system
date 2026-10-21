import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#20352A")
MUTED = colors.HexColor("#64756B")
GREEN = colors.HexColor("#1E4937")
PALE = colors.HexColor("#F1F5F1")
LINE = colors.HexColor("#DCE4DD")
FONT = "SupplySans"
FONT_BOLD = "SupplySans-Bold"


def _register_fonts() -> None:
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    candidates = [
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf")),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
    ]
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont(FONT, str(regular)))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
            return
    raise RuntimeError("A Unicode TrueType font is required to generate PDFs")


def safe_pdf_filename(document_type: str, reference: str) -> str:
    safe_reference = re.sub(r"[^A-Za-z0-9._-]+", "-", reference).strip("-._")
    return f"{document_type}-{safe_reference or 'record'}.pdf"


def _money(value: Any, currency: str) -> str:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return "Not available"
    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return f"{formatted} {currency}"


def _date(value: date | datetime | None) -> str:
    if value is None:
        return "Not recorded"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="minutes")
    return value.isoformat()


class _NumberedCanvas(canvas.Canvas):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(page_count)
            super().showPage()
        super().save()

    def _draw_footer(self, page_count: int) -> None:
        width, _ = A4
        self.saveState()
        self.setStrokeColor(LINE)
        self.setLineWidth(0.6)
        self.line(20 * mm, 16 * mm, width - 20 * mm, 16 * mm)
        self.setFont(FONT, 8)
        self.setFillColor(MUTED)
        self.drawString(20 * mm, 10 * mm, "Supply Chain · Internal procurement record")
        self.drawRightString(
            width - 20 * mm,
            10 * mm,
            f"Page {self._pageNumber} of {page_count}",
        )
        self.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    _register_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocumentTitle", parent=base["Title"], fontName=FONT_BOLD,
            fontSize=21, leading=26, textColor=INK, alignment=0,
            spaceAfter=4 * mm,
        ),
        "reference": ParagraphStyle(
            "Reference", fontName=FONT_BOLD, fontSize=10, leading=14,
            textColor=GREEN, spaceAfter=6 * mm,
        ),
        "label": ParagraphStyle(
            "Label", fontName=FONT_BOLD, fontSize=8, leading=11,
            textColor=MUTED,
        ),
        "value": ParagraphStyle(
            "Value", fontName=FONT, fontSize=9, leading=13,
            textColor=INK, wordWrap="CJK",
        ),
        "section": ParagraphStyle(
            "Section", fontName=FONT_BOLD, fontSize=11, leading=15,
            textColor=INK, spaceBefore=5 * mm, spaceAfter=2 * mm,
        ),
        "cell": ParagraphStyle(
            "Cell", fontName=FONT, fontSize=8.5, leading=11,
            textColor=INK, wordWrap="CJK",
        ),
        "cell_right": ParagraphStyle(
            "CellRight", fontName=FONT, fontSize=8.5, leading=11,
            textColor=INK, alignment=TA_RIGHT,
        ),
        "small": ParagraphStyle(
            "Small", fontName=FONT, fontSize=8.5, leading=12,
            textColor=MUTED, wordWrap="CJK",
        ),
    }


def _p(value: Any, style: ParagraphStyle) -> Paragraph:
    text = "—" if value is None or value == "" else str(value)
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _document(title: str, reference: str, story: list[Any]) -> bytes:
    styles = _styles()
    story[:0] = [
        _p(title, styles["title"]),
        _p(reference, styles["reference"]),
        Spacer(1, 1 * mm),
    ]
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"{title} - {reference}",
        author="Supply Chain Workspace",
    )
    document.build(story, canvasmaker=_NumberedCanvas)
    return output.getvalue()


def _metadata(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    cells = [
        [_p(label, styles["label"]), _p(value, styles["value"])]
        for label, value in rows
    ]
    table = Table(cells, colWidths=[40 * mm, 130 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return table


def _item_table(
    headers: list[str],
    rows: list[list[Any]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
) -> LongTable:
    data = [[_p(header, styles["label"]) for header in headers], *rows]
    table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    return table


def _total(label: str, value: str, styles: dict[str, ParagraphStyle]) -> Table:
    amount_style = ParagraphStyle(
        "TotalAmount", parent=styles["value"], fontName=FONT_BOLD,
        fontSize=12, alignment=TA_RIGHT,
    )
    table = Table(
        [[_p(label, styles["label"]), _p(value, amount_style)]],
        colWidths=[80 * mm, 90 * mm],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _item_rows(items: list[dict[str, Any]], currency: str, styles: dict[str, ParagraphStyle]):
    rows: list[list[Any]] = []
    complete_total = Decimal("0")
    all_priced = bool(items)
    for item in items:
        item = item if isinstance(item, dict) else {}
        description = item.get("item") or item.get("description") or "Unspecified item"
        quantity = item.get("qty", item.get("quantity"))
        price = item.get("unit_price")
        line_total: Decimal | None = None
        try:
            if quantity is None or price is None:
                raise InvalidOperation
            line_total = Decimal(str(quantity)) * Decimal(str(price))
            if not line_total.is_finite():
                raise InvalidOperation
            complete_total += line_total
        except (InvalidOperation, ValueError, TypeError):
            all_priced = False
        rows.append([
            _p(description, styles["cell"]),
            _p(quantity if quantity is not None else "Not recorded", styles["cell_right"]),
            _p(_money(price, currency) if price is not None else "Not recorded", styles["cell_right"]),
            _p(_money(line_total, currency) if line_total is not None else "Not available", styles["cell_right"]),
        ])
    if not rows:
        rows.append([_p("No line items recorded", styles["cell"]), "", "", ""])
        all_priced = False
    return rows, complete_total, all_priced


def generate_purchase_order_pdf(order: Any) -> bytes:
    styles = _styles()
    currency = str(order.currency)
    items = order.items_summary if isinstance(order.items_summary, list) else []
    story: list[Any] = [
        _metadata([
            ("Supplier", order.supplier_name),
            ("Order date", _date(order.order_date)),
            ("Expected delivery", _date(order.expected_delivery_date)),
            ("Currency", currency),
            ("Status", getattr(order.status, "value", order.status)),
        ], styles),
        Spacer(1, 6 * mm),
        _p("Order items", styles["section"]),
    ]
    rows, calculated_total, all_priced = _item_rows(items, currency, styles)
    story.append(_item_table(
        ["Description", "Quantity", "Unit price", "Line total"],
        rows,
        [78 * mm, 22 * mm, 34 * mm, 36 * mm],
        styles,
    ))
    original_total = order.expected_total_original
    if original_total is None and all_priced:
        original_total = calculated_total
    story.extend([Spacer(1, 4 * mm), _total(
        f"Original-currency total ({currency})",
        _money(original_total, currency) if original_total is not None else "Not available",
        styles,
    )])
    estimated_ron = None
    if original_total is not None:
        rate = order.budget_exchange_rate
        if rate is not None:
            estimated_ron = (Decimal(str(original_total)) * Decimal(str(rate))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        elif currency == "RON":
            estimated_ron = Decimal(str(original_total))
    story.extend([
        Spacer(1, 3 * mm),
        _p(
            "Estimated RON total: "
            + (_money(estimated_ron, "RON") if estimated_ron is not None else "Not available")
            + " · Budget rate: "
            + (f"{order.budget_exchange_rate} RON/{currency}" if order.budget_exchange_rate is not None else "Not recorded"),
            styles["small"],
        ),
    ])
    return _document("Purchase Order", order.po_number, story)


def generate_invoice_pdf(invoice: Any, purchase_order: Any | None) -> bytes:
    styles = _styles()
    currency = getattr(invoice.currency, "value", invoice.currency)
    linked_po = purchase_order.po_number if purchase_order is not None else "Not linked"
    story: list[Any] = [
        _p(
            "INTERNAL INVOICE REPORT · Not the supplier-issued invoice or a Romanian tax invoice",
            styles["small"],
        ),
        Spacer(1, 4 * mm),
        _metadata([
            ("Supplier", invoice.supplier_name),
            ("Invoice date", _date(invoice.invoice_date)),
            ("Purchase order", linked_po),
            ("Status", getattr(invoice.status, "value", invoice.status)),
            ("Original amount", _money(invoice.amount_original, currency)),
            ("Recorded exchange rate", f"{invoice.exchange_rate} RON/{currency}"),
            ("Stored RON equivalent", _money(invoice.amount_ron, "RON")),
        ], styles),
    ]
    if invoice.match_notes:
        story.extend([
            Spacer(1, 5 * mm),
            _p("Matching notes", styles["section"]),
            _p(invoice.match_notes, styles["small"]),
        ])
    return _document("Supplier Invoice Report", invoice.invoice_number, story)


def generate_goods_receipt_pdf(receipt: Any, purchase_order: Any | None, receiver: Any | None) -> bytes:
    styles = _styles()
    items = receipt.items_received if isinstance(receipt.items_received, list) else []
    story: list[Any] = [
        _metadata([
            ("Receipt date", _date(receipt.received_at)),
            ("Purchase order", purchase_order.po_number if purchase_order else "Unsolicited / not linked"),
            ("Supplier", purchase_order.supplier_name if purchase_order else "Not available"),
            ("Received by", receiver.full_name if receiver else "Not available"),
        ], styles),
        Spacer(1, 6 * mm),
        _p("Items received", styles["section"]),
    ]
    rows = [
        [
            _p(
                (item.get("item") or item.get("description") or "Unspecified item")
                if isinstance(item, dict)
                else "Unspecified item",
                styles["cell"],
            ),
            _p(
                item.get("qty", item.get("quantity", "Not recorded"))
                if isinstance(item, dict)
                else "Not recorded",
                styles["cell_right"],
            ),
        ]
        for item in items
    ]
    if not rows:
        rows = [[_p("No item details recorded", styles["cell"]), ""]]
    story.append(_item_table(
        ["Description", "Quantity received"], rows, [120 * mm, 50 * mm], styles
    ))
    if receipt.notes:
        story.extend([
            Spacer(1, 5 * mm),
            _p("Notes", styles["section"]),
            _p(receipt.notes, styles["small"]),
        ])
    return _document("Goods Receipt", receipt.receipt_number, story)
