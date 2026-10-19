from sqlmodel import Session

from app.models import AuditLog


def log_action(
    db: Session,
    user_id: int,
    action: str,
    entity_name: str,
    entity_id: str,
) -> AuditLog:
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        entity_name=entity_name,
        entity_id=entity_id,
    )
    db.add(audit_log)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(audit_log)
    return audit_log
