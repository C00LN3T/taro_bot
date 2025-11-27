from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from .config import BotConfig
from .models import BotSettings, NumerologyText, TarotCard, User, ZodiacSign
from .seed_data import ensure_seed, numerology_seed, tarot_seed, zodiac_seed
from .services.settings import get_bot_settings


_engine = None


def get_engine(database_url: str):
    global _engine
    if _engine is None:
        _engine = create_engine(database_url)
    return _engine


def init_db(config: BotConfig) -> None:
    engine = get_engine(config.database_url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        get_bot_settings(session)
        ensure_seed(TarotCard, session, tarot_seed())
        ensure_seed(NumerologyText, session, numerology_seed())
        ensure_seed(ZodiacSign, session, zodiac_seed())


@contextmanager
def session_scope(database_url: str) -> Iterator[Session]:
    engine = get_engine(database_url)
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_or_create_user(session: Session, telegram_id: int, language: str, username: str | None, first_name: str | None) -> User:
    user = session.exec(select(User).where(User.telegram_id == telegram_id)).first()
    if user:
        user.updated_at = datetime.utcnow()
        return user
    user = User(telegram_id=telegram_id, username=username, first_name=first_name, language=language)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
