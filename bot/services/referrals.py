from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from ..models import Referral, User
from .settings import ReferralSettings


@dataclass
class ReferralResult:
    inviter: User | None
    bonus_applied: bool


def parse_referral_payload(payload: str | None) -> int | None:
    if not payload:
        return None
    if not payload.startswith("ref_"):
        return None
    try:
        return int(payload.split("_", maxsplit=1)[1])
    except (ValueError, IndexError):
        return None


def apply_referral(
    session: Session,
    new_user: User,
    start_payload: str | None,
    settings: ReferralSettings,
    is_new_user: bool,
) -> ReferralResult:
    inviter_id = parse_referral_payload(start_payload)
    if not is_new_user or not settings.enabled or inviter_id is None:
        return ReferralResult(inviter=None, bonus_applied=False)
    if inviter_id == new_user.id:
        return ReferralResult(inviter=None, bonus_applied=False)
    inviter = session.get(User, inviter_id)
    if not inviter:
        return ReferralResult(inviter=None, bonus_applied=False)
    existing_link = session.exec(
        select(Referral).where(Referral.invited_id == new_user.id)
    ).first()
    if existing_link:
        return ReferralResult(inviter=None, bonus_applied=False)

    new_user.referred_by = inviter_id
    session.add(new_user)
    session.add(
        Referral(inviter_id=inviter_id, invited_id=new_user.id, created_at=datetime.utcnow())
    )
    inviter.free_spreads += settings.bonus
    session.add(inviter)
    session.commit()
    session.refresh(inviter)
    session.refresh(new_user)
    return ReferralResult(inviter=inviter, bonus_applied=True)
