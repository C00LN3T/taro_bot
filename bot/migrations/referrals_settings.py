from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

NAME = "001_referrals_settings"


def _has_column(session: Session, table: str, column: str) -> bool:
    try:
        result = session.exec(text(f"PRAGMA table_info('{table}')"))
    except Exception:  # noqa: BLE001
        return False
    return any(row[1] == column for row in result)


def apply_migration(session: Session) -> None:
    if not _has_column(session, "user", "referred_by"):
        session.exec(text("ALTER TABLE user ADD COLUMN referred_by INTEGER"))
    if not _has_column(session, "user", "free_spreads"):
        session.exec(text("ALTER TABLE user ADD COLUMN free_spreads INTEGER NOT NULL DEFAULT 0"))

    session.exec(
        text(
            """
            CREATE TABLE IF NOT EXISTS referral (
                inviter_id INTEGER NOT NULL,
                invited_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (inviter_id, invited_id)
            )
            """
        )
    )

    session.exec(
        text(
            """
            CREATE TABLE IF NOT EXISTS setting (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
    )
    session.commit()
