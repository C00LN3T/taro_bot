import os
import sys
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.models import NumerologyText, TarotCard, User, ZodiacSign
from bot.seed_data import ensure_seed, numerology_seed, tarot_seed, zodiac_seed


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ensure_seed(TarotCard, session, tarot_seed())
        ensure_seed(NumerologyText, session, numerology_seed())
        ensure_seed(ZodiacSign, session, zodiac_seed())
        yield session
