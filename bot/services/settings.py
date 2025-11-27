from __future__ import annotations

from sqlmodel import Session, select

from ..models import BotSettings


def get_bot_settings(session: Session) -> BotSettings:
    settings = session.exec(select(BotSettings).limit(1)).first()
    if not settings:
        settings = BotSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def set_response_delay(session: Session, seconds: int) -> BotSettings:
    settings = get_bot_settings(session)
    settings.response_delay_seconds = seconds
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings
