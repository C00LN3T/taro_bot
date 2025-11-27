from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text
from sqlmodel import Session

from .referrals_settings import apply_migration as apply_referral_migration
from .referrals_settings import NAME as REFERRAL_MIGRATION_NAME

MIGRATIONS: list[tuple[str, Callable[[Session], None]]] = [
    (REFERRAL_MIGRATION_NAME, apply_referral_migration),
]


def _ensure_table(session: Session) -> None:
    session.exec(
        text(
            """
            CREATE TABLE IF NOT EXISTS migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    session.commit()


def run_migrations(engine) -> None:
    with Session(engine) as session:
        _ensure_table(session)
        applied = {row[0] for row in session.exec(text("SELECT name FROM migrations"))}
        for name, func in MIGRATIONS:
            if name in applied:
                continue
            func(session)
            session.exec(text("INSERT INTO migrations (name) VALUES (:name)"), {"name": name})
            session.commit()
