from sqlmodel import select

from bot import handlers
from bot.models import Referral, SpreadHistory, User
from bot.services.history import save_spread
from bot.services.referrals import apply_referral, parse_referral_payload
from bot.services.settings import get_referral_settings, set_setting, REF_BONUS_KEY, REF_ENABLED_KEY


def test_parse_referral_payload():
    assert parse_referral_payload("ref_10") == 10
    assert parse_referral_payload("start") is None


def test_referral_bonus_for_new_user(session):
    inviter = User(telegram_id=10, language="ru")
    session.add(inviter)
    session.commit()
    session.refresh(inviter)

    new_user = User(telegram_id=11, language="ru")
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    settings = get_referral_settings(session)
    result = apply_referral(session, new_user, f"ref_{inviter.id}", settings, is_new_user=True)
    updated_inviter = session.get(User, inviter.id)
    updated_user = session.get(User, new_user.id)

    assert result.bonus_applied is True
    assert updated_user.referred_by == inviter.id
    assert updated_inviter.free_spreads == settings.bonus
    count = session.exec(select(Referral)).all()
    assert len(count) == 1


def test_referral_not_for_existing_user(session):
    inviter = User(telegram_id=21, language="ru")
    session.add(inviter)
    session.commit()
    session.refresh(inviter)

    existing = User(telegram_id=22, language="ru")
    session.add(existing)
    session.commit()
    session.refresh(existing)

    settings = get_referral_settings(session)
    result = apply_referral(session, existing, f"ref_{inviter.id}", settings, is_new_user=False)
    assert result.bonus_applied is False
    assert existing.referred_by is None
    assert session.exec(select(Referral)).all() == []


def test_save_spread_consumes_bonus(session):
    user = User(telegram_id=30, language="ru", free_spreads=1)
    session.add(user)
    session.commit()
    session.refresh(user)

    for _ in range(handlers.CONFIG.daily_free_limit):
        save_spread(session, user.id, "tarot", "one", "{}", "ok", daily_limit=handlers.CONFIG.daily_free_limit)
    save_spread(session, user.id, "tarot", "one", "{}", "ok", daily_limit=handlers.CONFIG.daily_free_limit)

    updated = session.get(User, user.id)
    assert updated.free_spreads == 0
    count = len(session.exec(select(SpreadHistory)).all())
    assert count == handlers.CONFIG.daily_free_limit + 1


def test_referral_settings_toggle(session):
    set_setting(session, REF_BONUS_KEY, 7)
    set_setting(session, REF_ENABLED_KEY, False)
    settings = get_referral_settings(session)
    assert settings.bonus == 7
    assert settings.enabled is False
