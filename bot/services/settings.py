from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from ..models import BotSettings, Setting

REF_BONUS_KEY = "ref_bonus"
REF_WELCOME_BONUS_KEY = "ref_welcome_bonus"
REF_ENABLED_KEY = "ref_system_enabled"


@dataclass
class ReferralSettings:
    bonus: int = 5
    welcome_bonus: int = 0
    enabled: bool = True


def _ensure_setting(session: Session, key: str, default: str) -> Setting:
    setting = session.get(Setting, key)
    if setting:
        return setting
    setting = Setting(key=key, value=default)
    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting


def get_setting(session: Session, key: str, default: str | None = None) -> Setting | None:
    setting = session.get(Setting, key)
    if setting:
        return setting
    if default is None:
        return None
    return _ensure_setting(session, key, default)


def set_setting(session: Session, key: str, value: str | int | bool) -> Setting:
    setting = session.get(Setting, key)
    serialized = str(value).lower() if isinstance(value, bool) else str(value)
    if not setting:
        setting = Setting(key=key, value=serialized)
    else:
        setting.value = serialized
    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting


def get_referral_settings(session: Session) -> ReferralSettings:
    bonus_setting = get_setting(session, REF_BONUS_KEY, default="5")
    welcome_bonus_setting = get_setting(session, REF_WELCOME_BONUS_KEY, default="0")
    enabled_setting = get_setting(session, REF_ENABLED_KEY, default="true")
    bonus_value = int(bonus_setting.value) if bonus_setting and bonus_setting.value.isdigit() else 5
    welcome_bonus_value = (
        int(welcome_bonus_setting.value)
        if welcome_bonus_setting and welcome_bonus_setting.value.isdigit()
        else 0
    )
    enabled_value = (enabled_setting.value.lower() != "false") if enabled_setting else True
    return ReferralSettings(bonus=bonus_value, welcome_bonus=welcome_bonus_value, enabled=enabled_value)


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
