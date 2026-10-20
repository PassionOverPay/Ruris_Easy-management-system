from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

ALGORITHM = "HS256"
password_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__rounds=600_000,
)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, roles: list[str]) -> str:
    secret_key = settings.JWT_SECRET_KEY
    if secret_key is None or len(secret_key.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters")

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": subject, "roles": roles, "exp": expires_at},
        secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, object]:
    secret_key = settings.JWT_SECRET_KEY
    if secret_key is None or len(secret_key.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters")

    return jwt.decode(token, secret_key, algorithms=[ALGORITHM])


__all__ = [
    "JWTError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
