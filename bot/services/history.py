from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from ..models import SpreadHistory, User


def daily_usage_count(session: Session, user_id: int) -> int:
    start_day = datetime.combine(datetime.utcnow().date(), time.min)
    end_day = start_day + timedelta(days=1)
    return session.exec(
        select(func.count())
        .select_from(SpreadHistory)
        .where(SpreadHistory.user_id == user_id)
        .where(SpreadHistory.created_at >= start_day)
        .where(SpreadHistory.created_at < end_day)
    ).one()


def save_spread(
    session: Session,
    user_id: int,
    spread_type: str,
    spread_name: str,
    input_data: str,
    result: str,
    daily_limit: int | None = None,
) -> bool:
    bonus_used = False
    if daily_limit is not None:
        usage_count = daily_usage_count(session, user_id)
        user = session.get(User, user_id)
        if user and usage_count >= daily_limit and user.free_spreads > 0:
            user.free_spreads -= 1
            bonus_used = True
            session.add(user)
    history = SpreadHistory(
        user_id=user_id,
        type=spread_type,
        spread_name=spread_name,
        input_data=input_data,
        result=result,
    )
    session.add(history)
    session.commit()
    return bonus_used
