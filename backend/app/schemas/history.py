from datetime import datetime

from sqlmodel import SQLModel


class HistoryEntry(SQLModel):
    id: int
    actor_name: str
    actor_roles: list[str]
    action: str
    entity_name: str
    entity_id: str
    timestamp: datetime
    description: str
