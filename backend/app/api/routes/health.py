from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/database")
def database_health_check(
    session: Session = Depends(get_session),
) -> dict[str, str]:
    session.connection().execute(text("SELECT 1")).scalar_one()
    return {"status": "ok", "database": "ok"}
