import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(".env.local")
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.core.security import hash_password  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.models import User, UserRole  # noqa: E402


def main() -> None:
    with Session(engine) as session:
        existing_admin = next(
            (
                user
                for user in session.exec(select(User)).all()
                if UserRole.ADMIN.value in user.roles
            ),
            None,
        )
        if existing_admin is not None:
            print("An admin user already exists; no changes made.")
            return

        email = os.getenv("FIRST_ADMIN_EMAIL")
        password = os.getenv("FIRST_ADMIN_PASSWORD")
        if not email or not password:
            raise SystemExit(
                "Set FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD before running "
                "this script."
            )

        admin = User(
            email=email,
            full_name="Administrator",
            hashed_password=hash_password(password),
            roles=[UserRole.ADMIN.value],
        )
        session.add(admin)
        session.commit()
        print(f"Created the first admin user: {email}")


if __name__ == "__main__":
    main()
