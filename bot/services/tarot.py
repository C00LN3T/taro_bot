from __future__ import annotations

import random
from typing import Iterable, NamedTuple

from sqlmodel import Session, select

from ..models import SpreadHistory, TarotCard


class TarotCardView(NamedTuple):
    name: str
    upright: str
    reversed: str
    arcana_type: str
    suit: str | None


class DrawnCard(NamedTuple):
    name: str
    position: str
    meaning: str


def load_deck(session: Session) -> list[TarotCardView]:
    records = session.exec(select(TarotCard)).all()
    if not records:
        return []
    return [
        TarotCardView(
            name=item.name,
            upright=item.upright_meaning,
            reversed=item.reversed_meaning,
            arcana_type=item.arcana_type,
            suit=item.suit,
        )
        for item in records
    ]


def draw_cards(session: Session, count: int, deck: Iterable[TarotCardView] | None = None) -> list[DrawnCard]:
    cards = list(deck or load_deck(session))
    if not cards:
        return []
    selected = random.sample(cards, k=min(count, len(cards)))
    result: list[DrawnCard] = []
    for card in selected:
        is_reversed = random.choice([True, False])
        if is_reversed:
            result.append(DrawnCard(name=card.name, position="Перевёрнутая", meaning=card.reversed))
        else:
            result.append(DrawnCard(name=card.name, position="Прямое", meaning=card.upright))
    return result


def _format_cards(title: str, cards: list[DrawnCard]) -> str:
    if not cards:
        return f"{title}: нет доступных карт"
    lines = [title]
    for idx, card in enumerate(cards, start=1):
        lines.append(f"{idx}. {card.name} — {card.position}. {card.meaning}")
    return "\n".join(lines)


def spread_one_card(session: Session) -> str:
    cards = draw_cards(session, 1)
    return _format_cards("Совет дня", cards)


def spread_three_cards(session: Session) -> str:
    cards = draw_cards(session, 3)
    title = "Три карты (прошлое / настоящее / будущее)"
    return _format_cards(title, cards)


def spread_situation(session: Session) -> str:
    cards = draw_cards(session, 3)
    title = "Ситуация: проблема / ресурсы / результат"
    return _format_cards(title, cards)


def spread_love(session: Session) -> str:
    cards = draw_cards(session, 4)
    title = "Любовный расклад: я / партнёр / потенциал / совет"
    return _format_cards(title, cards)


def spread_career(session: Session) -> str:
    cards = draw_cards(session, 4)
    title = "Карьера и финансы: текущая позиция / вызов / ресурс / совет"
    return _format_cards(title, cards)


SPREAD_FUNCS = {
    "one": spread_one_card,
    "three": spread_three_cards,
    "situation": spread_situation,
    "love": spread_love,
    "career": spread_career,
}


def save_history(session: Session, user_id: int, spread_type: str, spread_name: str, input_payload: str, result: str) -> None:
    history = SpreadHistory(
        user_id=user_id,
        type=spread_type,
        spread_name=spread_name,
        input_data=input_payload,
        result=result,
    )
    session.add(history)
    session.commit()
