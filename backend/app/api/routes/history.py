from fastapi import APIRouter, Depends
from sqlmodel import Session, desc, select

from app.api.dependencies import get_current_user
from app.db.session import get_session
from app.models import AuditLog, User
from app.schemas.history import HistoryEntry

router = APIRouter()

_ACTIONS = {
    "login": "Signed in",
    "create": "Created",
    "read_match": "Reviewed order and receipt match",
    "read": "Viewed",
}
_ENTITIES = {
    "PurchaseOrder": "purchase order",
    "GoodsReceipt": "goods receipt",
    "Invoice": "invoice",
    "User": "user account",
}


@router.get("", response_model=list[HistoryEntry])
def list_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[HistoryEntry]:
    """Return recent recorded activity for authenticated team members."""
    rows = session.exec(
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id)
        .order_by(desc(AuditLog.timestamp), desc(AuditLog.id))
        .limit(200)
    ).all()
    return [
        HistoryEntry(
            id=entry.id,
            actor_name=user.full_name,
            actor_roles=user.roles,
            action=entry.action,
            entity_name=entry.entity_name,
            entity_id=entry.entity_id,
            timestamp=entry.timestamp,
            description=(
                f"{_ACTIONS.get(entry.action, entry.action.replace('_', ' ').capitalize())} "
                f"{_ENTITIES.get(entry.entity_name, entry.entity_name)}"
                + (f" #{entry.entity_id}" if entry.entity_id != "list" else "")
            ),
        )
        for entry, user in rows
    ]
