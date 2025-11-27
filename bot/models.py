from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from sqlmodel import Field, SQLModel


class BotSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    response_delay_seconds: int = 0


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(index=True, unique=True)
    username: Optional[str] = None
    first_name: Optional[str] = None
    name: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    language: str = "ru"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TarotCard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    arcana_type: str
    suit: Optional[str] = None
    upright_meaning: str
    reversed_meaning: str
    image_url: Optional[str] = None


class NumerologyText(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    number: int
    type: str
    description: str


class ZodiacSign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    date_start: str
    date_end: str
    description: str


class SpreadHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    type: str
    spread_name: str
    input_data: str
    result: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SessionState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    current_state: str
    payload: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
