from fastapi.responses import Response

from app.services.pdf_documents import safe_pdf_filename


def pdf_response(content: bytes, document_type: str, reference: str) -> Response:
    filename = safe_pdf_filename(document_type, reference)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
