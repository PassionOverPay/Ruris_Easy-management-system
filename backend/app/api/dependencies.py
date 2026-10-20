from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlmodel import Session

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError("JWT subject is missing")
        user_id = int(subject)
    except (JWTError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def RequireRole(allowed_roles: list[UserRole]) -> Callable[..., User]:
    allowed = set(allowed_roles)

    def check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not allowed.intersection(current_user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return check_role
