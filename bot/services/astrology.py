from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, select

from ..models import SpreadHistory, ZodiacSign


@dataclass
class ZodiacResult:
    name: str
    description: str
    element: str
    modality: str


ELEMENTS = {
    "Козерог": "Земля",
    "Телец": "Земля",
    "Дева": "Земля",
    "Овен": "Огонь",
    "Лев": "Огонь",
    "Стрелец": "Огонь",
    "Рак": "Вода",
    "Скорпион": "Вода",
    "Рыбы": "Вода",
    "Близнецы": "Воздух",
    "Весы": "Воздух",
    "Водолей": "Воздух",
}

MODALITIES = {
    "Козерог": "кардинальный",
    "Овен": "кардинальный",
    "Весы": "кардинальный",
    "Рак": "кардинальный",
    "Телец": "фиксированный",
    "Лев": "фиксированный",
    "Скорпион": "фиксированный",
    "Водолей": "фиксированный",
    "Близнецы": "мутабельный",
    "Дева": "мутабельный",
    "Стрелец": "мутабельный",
    "Рыбы": "мутабельный",
}


def zodiac_for_date(session: Session, target: date) -> ZodiacSign | None:
    signs = session.exec(select(ZodiacSign)).all()
    target_pair = (target.month, target.day)
    for sign in signs:
        start_month, start_day = map(int, sign.date_start.split("-"))
        end_month, end_day = map(int, sign.date_end.split("-"))
        start_pair = (start_month, start_day)
        end_pair = (end_month, end_day)

        if start_month > end_month:  # spans new year
            if target_pair >= start_pair or target_pair <= end_pair:
                return sign
        elif start_pair <= target_pair <= end_pair:
            return sign
    return None


def short_portrait(sign: ZodiacSign) -> str:
    element = ELEMENTS.get(sign.name, "")
    modality = MODALITIES.get(sign.name, "")
    lines = [f"Знак: {sign.name}", f"Описание: {sign.description}"]
    if element:
        lines.append(f"Стихия: {element}")
    if modality:
        lines.append(f"Модальность: {modality}")
    lines.append("Космограмма-лайт: используйте сильные стороны стихии, соблюдайте баланс модальности.")
    return "\n".join(lines)


def save_history(session: Session, user_id: int, sign: ZodiacSign, result: str) -> None:
    history = SpreadHistory(
        user_id=user_id,
        type="astro",
        spread_name=sign.name,
        input_data=sign.date_start,
        result=result,
    )
    session.add(history)
    session.commit()
