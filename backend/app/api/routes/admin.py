from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.api.dependencies import RequireRole
from app.core.security import hash_password
from app.db.session import get_session
from app.models import User, UserRole
from app.schemas.user import UserCreate, UserResponse
from app.services.audit import log_action

router = APIRouter()


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    user_data: UserCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
) -> User:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is invalid")

    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=UserRole(user_data.role),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists",
        ) from exc

    session.refresh(user)
    log_action(
        session,
        current_user.id,
        "create",
        "User",
        str(user.id),
    )
    return user
