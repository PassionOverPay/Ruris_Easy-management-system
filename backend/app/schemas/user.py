from datetime import datetime
from typing import Literal

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models import UserRole


class UserCreate(SQLModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1)
    full_name: str = Field(min_length=1, max_length=255)
    roles: list[
        Literal[
            UserRole.PURCHASING,
            UserRole.WAREHOUSE,
            UserRole.ACCOUNTING,
        ]
    ] = Field(min_length=1)


class UserResponse(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    roles: list[str]
    created_at: datetime
