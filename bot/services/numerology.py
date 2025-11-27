from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlmodel import Session, select

from ..models import NumerologyText, SpreadHistory
from .history import save_spread


@dataclass
class NumerologyResult:
    number: int
    title: str
    description: str


@dataclass
class CompatibilityResult:
    first_number: int
    second_number: int
    score: int
    description: str


def _digital_root(value: int) -> int:
    while value > 9:
        value = sum(int(d) for d in str(value))
    return value


def _lookup_description(session: Session, number: int, calc_type: str, fallback: str) -> str:
    record = session.exec(
        select(NumerologyText).where(NumerologyText.number == number, NumerologyText.type == calc_type)
    ).first()
    return record.description if record else fallback


def destiny_number(session: Session, day: int, month: int, year: int) -> NumerologyResult:
    base = _digital_root(day + month + year)
    description = _lookup_description(
        session,
        base,
        "destiny",
        "Путь развития и ключевые качества.",
    )
    return NumerologyResult(number=base, title="Число судьбы", description=description)


def name_number(session: Session, name: str) -> NumerologyResult:
    normalized = [char for char in name.lower() if char.isalpha()]
    position_sum = sum((ord(char) - 96) for char in normalized)
    value = _digital_root(position_sum) if position_sum > 0 else 0
    description = _lookup_description(session, value, "name", "Число имени отражает самовыражение и стиль общения.")
    return NumerologyResult(number=value, title="Число имени", description=description)


def personality_card(session: Session, name: str, day: int, month: int, year: int) -> list[NumerologyResult]:
    results: list[NumerologyResult] = []
    results.append(destiny_number(session, day, month, year))
    results.append(name_number(session, name))
    life_period_value = _digital_root(day * month)
    description = _lookup_description(session, life_period_value, "life_cycle", "Подсказывает задачи периода и ключевые уроки.")
    results.append(
        NumerologyResult(
            number=life_period_value,
            title="Число жизненного цикла",
            description=description,
        )
    )
    return results


def compatibility(session: Session, first: tuple[int, int, int], second: tuple[int, int, int]) -> CompatibilityResult:
    first_destiny = destiny_number(session, *first).number
    second_destiny = destiny_number(session, *second).number
    score = 10 - abs(first_destiny - second_destiny)
    description = (
        "Чем ближе числа судьбы, тем проще договориться. Высокая разница добавляет динамики и уроков."
    )
    return CompatibilityResult(
        first_number=first_destiny,
        second_number=second_destiny,
        score=max(score, 1),
        description=description,
    )


def save_history(session: Session, user_id: int, payload: str, result: str, daily_limit: int | None = None) -> None:
    save_spread(
        session,
        user_id=user_id,
        spread_type="numerology",
        spread_name="numerology",
        input_data=payload,
        result=result,
        daily_limit=daily_limit,
    )
