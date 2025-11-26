from datetime import date, datetime

from bot import handlers
from bot.models import SpreadHistory, User
from bot.services import astrology, numerology, tarot


def test_tarot_seed_loaded(session):
    deck = tarot.load_deck(session)
    assert len(deck) >= 22


def test_numerology_destiny(session):
    result = numerology.destiny_number(session, 1, 1, 2000)
    assert result.number == 4
    assert result.description


def test_zodiac_for_date(session):
    sign = astrology.zodiac_for_date(session, date(2024, 3, 25))
    assert sign is not None
    assert sign.name == "Овен"


def test_daily_limit_counter(session):
    user = User(telegram_id=123, language="ru")
    session.add(user)
    session.commit()
    session.refresh(user)
    for _ in range(2):
        session.add(
            SpreadHistory(
                user_id=user.id,
                type="tarot",
                spread_name="test",
                input_data="{}",
                result="ok",
                created_at=datetime.utcnow(),
            )
        )
    session.commit()
    remaining, count = handlers._remaining_limit(session, user.id)
    assert count == 2
    assert remaining == handlers.CONFIG.daily_free_limit - 2
