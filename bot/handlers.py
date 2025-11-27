from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, time, timedelta
from io import BytesIO
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import func
from sqlmodel import delete, select

from . import keyboards
from .config import BotConfig
from .db import get_or_create_user, session_scope
from .localization import BUTTONS, button_text, t
from .models import SpreadHistory, User
from .services import astrology, extra, numerology, tarot
from .states import AdminStates, AstroStates, NumerologyStates, ProfileStates, TarotStates
from .services.settings import get_bot_settings, set_response_delay

router = Router()
logger = logging.getLogger(__name__)

CONFIG = BotConfig.load()


async def maybe_delay_response(session) -> None:
    settings = get_bot_settings(session)
    delay = max(settings.response_delay_seconds, 0)
    if delay:
        await asyncio.sleep(delay)


def parse_birthdate(text: str) -> datetime | None:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def get_language(user: User | None) -> str:
    return user.language if user and user.language else CONFIG.default_language


def ensure_user(session, message: Message) -> User:
    user = session.exec(select(User).where(User.telegram_id == message.from_user.id)).first()
    if not user:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            language=CONFIG.default_language,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    return user


def main_menu_markup(lang: str):
    return keyboards.main_menu_keyboard(lang)


def actions_keyboard(lang: str, share_payload: str | None = None):
    return keyboards.result_actions_keyboard(lang, share_payload=share_payload)


async def _feature_unavailable(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await message.answer(t("feature_unavailable", lang), reply_markup=main_menu_markup(lang))


def _date_range(days: int) -> tuple[datetime, datetime]:
    start = datetime.combine(datetime.utcnow().date() - timedelta(days=days - 1), time.min)
    end = datetime.combine(datetime.utcnow().date() + timedelta(days=1), time.min)
    return start, end


def _figure_to_bytes(fig) -> BytesIO:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    plt.close(fig)
    return buffer


def _build_daily_activity_chart(daily_activity: list[tuple[datetime, int]]):
    if not daily_activity:
        return None
    dates = [datetime.fromisoformat(str(day)).strftime("%d.%m") for day, _ in daily_activity]
    counts = [count for _, count in daily_activity]
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(dates, counts, color="#6A5ACD")
    ax.set_title("Активность за 7 дней")
    ax.set_ylabel("Количество раскладов")
    ax.set_xlabel("Дата")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    fig.tight_layout()
    return _figure_to_bytes(fig)


def _build_type_distribution_chart(by_type: list[tuple[str, int]]):
    if not by_type:
        return None
    labels = [item[0] or "Не указан" for item in by_type]
    counts = [item[1] for item in by_type]
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.pie(counts, labels=labels, autopct="%1.0f%%", startangle=140)
    ax.axis("equal")
    ax.set_title("Распределение по типам")
    return _figure_to_bytes(fig)


def _remaining_limit(session, user_id: int) -> tuple[int, int]:
    start_day = datetime.combine(datetime.utcnow().date(), time.min)
    end_day = start_day + timedelta(days=1)
    count = session.exec(
        select(func.count())
        .select_from(SpreadHistory)
        .where(SpreadHistory.user_id == user_id)
        .where(SpreadHistory.created_at >= start_day)
        .where(SpreadHistory.created_at < end_day)
    ).one()
    remaining = max(CONFIG.daily_free_limit - count, 0)
    return remaining, count


def _limit_guard(session, user_id: int, lang: str) -> tuple[bool, str | None]:
    remaining, _ = _remaining_limit(session, user_id)
    if remaining <= 0:
        return False, t("limit_reached", lang)
    return True, t("limit_info", lang, remaining=remaining)


def _is_admin(user_id: int) -> bool:
    return user_id in CONFIG.admin_ids


def _admin_language(user_id: int) -> str:
    with session_scope(CONFIG.database_url) as session:
        user = session.exec(select(User).where(User.telegram_id == user_id)).first()
        return get_language(user)


def _build_admin_stats():
    config = CONFIG
    start_week, end_today = _date_range(7)
    start_month, _ = _date_range(30)
    with session_scope(config.database_url) as session:
        total_users = session.exec(select(func.count()).select_from(User)).one()
        new_users_week = session.exec(
            select(func.count()).select_from(User).where(User.created_at >= start_week)
        ).one()
        total_spreads = session.exec(select(func.count()).select_from(SpreadHistory)).one()
        start_day = datetime.combine(datetime.utcnow().date(), time.min)
        end_day = start_day + timedelta(days=1)
        today_spreads = session.exec(
            select(func.count())
            .select_from(SpreadHistory)
            .where(SpreadHistory.created_at >= start_day)
            .where(SpreadHistory.created_at < end_day)
        ).one()
        week_spreads = session.exec(
            select(func.count())
            .select_from(SpreadHistory)
            .where(SpreadHistory.created_at >= start_week)
            .where(SpreadHistory.created_at < end_today)
        ).one()
        month_spreads = session.exec(
            select(func.count())
            .select_from(SpreadHistory)
            .where(SpreadHistory.created_at >= start_month)
            .where(SpreadHistory.created_at < end_today)
        ).one()
        active_users_week = session.exec(
            select(func.count(func.distinct(SpreadHistory.user_id)))
            .where(SpreadHistory.created_at >= start_week)
            .where(SpreadHistory.created_at < end_today)
        ).one()
        by_type = session.exec(
            select(SpreadHistory.type, func.count()).group_by(SpreadHistory.type)
        ).all()
        by_spread = session.exec(
            select(SpreadHistory.type, SpreadHistory.spread_name, func.count())
            .group_by(SpreadHistory.type, SpreadHistory.spread_name)
            .order_by(func.count().desc())
            .limit(10)
        ).all()
        top_users = session.exec(
            select(User.username, User.first_name, User.telegram_id, func.count())
            .select_from(SpreadHistory)
            .join(User, User.id == SpreadHistory.user_id)
            .group_by(User.id)
            .order_by(func.count().desc())
            .limit(5)
        ).all()
        daily_activity = session.exec(
            select(func.date(SpreadHistory.created_at), func.count())
            .where(SpreadHistory.created_at >= start_week)
            .where(SpreadHistory.created_at < end_today)
            .group_by(func.date(SpreadHistory.created_at))
            .order_by(func.date(SpreadHistory.created_at))
        ).all()
    type_lines = "\n".join(f"• {item[0]}: {item[1]}" for item in by_type) or "—"
    spread_lines = (
        "\n".join(
            f"• {item[0]} / {item[1]}: {item[2]}" if item[1] else f"• {item[0]}: {item[2]}"
            for item in by_spread
        )
        or "—"
    )
    user_lines = (
        "\n".join(
            f"• {('@' + username) if username else (first_name or 'User ' + str(telegram_id))}: {count}"
            for username, first_name, telegram_id, count in top_users
        )
        or "—"
    )
    daily_lines = "\n".join(f"• {str(day)}: {count}" for day, count in daily_activity) or "—"
    text = (
        "📊 Статистика бота"\
        f"\nПользователи: {total_users} (новых за 7 дней: {new_users_week})"\
        f"\nАктивные за 7 дней: {active_users_week}"\
        f"\nРаскладов всего: {total_spreads}"\
        f"\nСегодня: {today_spreads} | 7 дней: {week_spreads} | 30 дней: {month_spreads}"\
        f"\n\nПо типам:\n{type_lines}"\
        f"\n\nТоп раскладов:\n{spread_lines}"\
        f"\n\nТоп-5 пользователей:\n{user_lines}"\
        f"\n\nАктивность за 7 дней:\n{daily_lines}"
    )
    charts = []
    daily_chart = _build_daily_activity_chart(daily_activity)
    if daily_chart:
        charts.append((daily_chart, "Активность за 7 дней"))
    type_chart = _build_type_distribution_chart(by_type)
    if type_chart:
        charts.append((type_chart, "Распределение по типам"))
    return text, charts


async def _send_broadcast(bot, text: str) -> int:
    config = CONFIG
    count = 0
    with session_scope(config.database_url) as session:
        users = session.exec(select(User)).all()
        for user in users:
            try:
                await bot.send_message(user.telegram_id, text)
                count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("broadcast failed for %s: %s", user.telegram_id, exc)
    return count


def log_history(session, user_id: int, spread_type: str, spread_name: str, payload: dict | str, result: str) -> None:
    session.add(
        SpreadHistory(
            user_id=user_id,
            type=spread_type,
            spread_name=spread_name,
            input_data=json.dumps(payload) if not isinstance(payload, str) else payload,
            result=result,
        )
    )
    session.commit()


def reset_to_menu(message: Message, lang: str, state: FSMContext, text: str | None = None) -> Any:
    return message.answer(text or t("menu", lang), reply_markup=main_menu_markup(lang))


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    with session_scope(CONFIG.database_url) as session:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            language=CONFIG.default_language,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        lang = get_language(user)
    await state.set_state(ProfileStates.waiting_for_language)
    await message.answer(t("welcome", lang), reply_markup=main_menu_markup(lang))
    await message.answer(t("ask_language", lang))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await message.answer(t("help", lang), reply_markup=main_menu_markup(lang))


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await reset_to_menu(message, lang, state)


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        birth = user.birth_date.isoformat() if user and user.birth_date else "—"
        gender = user.gender or "—"
        name = user.name or user.first_name or message.from_user.full_name
    await message.answer(t("profile", lang, name=name, birthdate=birth, gender=gender, language=lang), reply_markup=keyboards.profile_keyboard(lang))


@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileStates.waiting_for_language)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
    lang = get_language(user)
    await message.answer(t("ask_language", lang))


@router.message(ProfileStates.waiting_for_language, F.text.lower().in_({"ru", "en"}))
async def set_language(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            language=message.text.lower(),
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        user.language = message.text.lower()
        session.add(user)
        session.commit()
        lang = get_language(user)
    await state.set_state(ProfileStates.waiting_for_name)
    await message.answer(t("ask_name", lang))


@router.message(ProfileStates.waiting_for_language)
async def invalid_language(message: Message) -> None:
    await message.answer(t("unknown_language", CONFIG.default_language))


@router.message(ProfileStates.waiting_for_name)
async def set_profile_name(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if user:
            user.name = message.text.strip()
            user.updated_at = datetime.utcnow()
            session.add(user)
            session.commit()
    await state.set_state(ProfileStates.waiting_for_birthdate)
    await message.answer(t("ask_birthdate", lang))


@router.message(ProfileStates.waiting_for_birthdate)
async def profile_set_birthdate(message: Message, state: FSMContext) -> None:
    parsed = parse_birthdate(message.text)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if not parsed:
            await message.answer(t("bad_date", lang))
            return
        if user:
            user.birth_date = parsed.date()
            user.updated_at = datetime.utcnow()
            session.add(user)
            session.commit()
    await state.set_state(ProfileStates.waiting_for_gender)
    await message.answer(t("ask_gender", lang))


@router.message(ProfileStates.waiting_for_gender)
async def profile_set_gender(message: Message, state: FSMContext) -> None:
    value = message.text.lower().strip() if message.text else ""
    if value not in {"м", "ж", "m", "f", "male", "female", ""}:
        value = ""
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if user:
            user.gender = value or None
            session.add(user)
            session.commit()
    await state.clear()
    await reset_to_menu(message, lang, state, t("saved", lang))


@router.message(F.text.in_({button_text("profile", "ru"), button_text("profile", "en")}))
async def profile_button(message: Message) -> None:
    await cmd_profile(message)


@router.message(F.text.in_({button_text("change_name", "ru"), button_text("change_name", "en")}))
async def profile_change_name(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await state.set_state(ProfileStates.waiting_for_name)
    await message.answer(t("ask_name", lang))


@router.message(F.text.in_({button_text("change_birth", "ru"), button_text("change_birth", "en")}))
async def profile_change_birthdate(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await state.set_state(ProfileStates.waiting_for_birthdate)
    await message.answer(t("ask_birthdate", lang))


@router.message(F.text.in_({button_text("change_lang", "ru"), button_text("change_lang", "en")}))
async def profile_change_lang_button(message: Message, state: FSMContext) -> None:
    await cmd_language(message, state)


@router.message(F.text.in_({button_text("delete", "ru"), button_text("delete", "en")}))
async def profile_delete_request(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileStates.confirming_delete)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await message.answer(t("delete_confirm", lang))


@router.message(ProfileStates.confirming_delete, F.text.lower().in_({"да", "yes"}))
async def profile_delete_confirm(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if user:
            session.delete(user)
            session.exec(delete(SpreadHistory).where(SpreadHistory.user_id == user.id))
            session.commit()
    await reset_to_menu(message, lang, state, t("delete_done", lang))


@router.message(ProfileStates.confirming_delete, F.text.lower().in_({"нет", "no"}))
async def profile_delete_cancel(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await reset_to_menu(message, lang, state, t("delete_cancel", lang))


@router.message(ProfileStates.confirming_delete)
async def profile_delete_unknown(message: Message) -> None:
    await message.answer(t("delete_prompt", CONFIG.default_language))


@router.message(F.text.in_({button_text("tarot", "ru"), button_text("tarot", "en")}))
async def tarot_entry(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await state.set_state(TarotStates.choosing_spread)
    await message.answer(t("tarot_prompt", lang), reply_markup=keyboards.tarot_spreads_keyboard(lang))


@router.message(TarotStates.choosing_spread, F.text.in_(
    {button_text("tarot_one", "ru"), button_text("tarot_one", "en"),
     button_text("tarot_three", "ru"), button_text("tarot_three", "en"),
     button_text("tarot_situation", "ru"), button_text("tarot_situation", "en"),
     button_text("tarot_love", "ru"), button_text("tarot_love", "en"),
     button_text("tarot_career", "ru"), button_text("tarot_career", "en")}
))
async def tarot_choose_spread(message: Message, state: FSMContext) -> None:
    choice = message.text
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        allowed, note = _limit_guard(session, user.id, lang)
        if not allowed:
            await message.answer(note)
            await state.clear()
            return
        mapping = {
            button_text("tarot_one", lang): (tarot.spread_one_card, "tarot_one"),
            button_text("tarot_three", lang): (tarot.spread_three_cards, "tarot_three"),
            button_text("tarot_situation", lang): (tarot.spread_situation, "tarot_situation"),
            button_text("tarot_love", lang): (tarot.spread_love, "tarot_love"),
            button_text("tarot_career", lang): (tarot.spread_career, "tarot_career"),
        }
        func_map = mapping.get(choice)
        if not func_map:
            await message.answer(t("tarot_prompt", lang))
            return
        result = func_map[0](session)
        tarot.save_history(session, user.id, "tarot", func_map[1], json.dumps({}), result)
        await maybe_delay_response(session)
        await message.answer(result, reply_markup=actions_keyboard(lang, share_payload=result))
        await message.answer(note)
    await state.clear()


@router.message(TarotStates.choosing_spread, F.text.in_({button_text("back", "ru"), button_text("back", "en")}))
async def tarot_back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await reset_to_menu(message, lang, state)


@router.message(F.text.in_({button_text("random", "ru"), button_text("random", "en")}))
async def random_spread(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(F.text.in_({button_text("rune", "ru"), button_text("rune", "en")}))
async def rune_day(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        allowed, note = _limit_guard(session, user.id, lang)
        if not allowed:
            await message.answer(note)
            return
        name, meaning = extra.rune_of_the_day()
        result = t("rune", lang, name=name, meaning=meaning)
        log_history(session, user.id, "rune", name, {}, result)
        await maybe_delay_response(session)
        await message.answer(result, reply_markup=actions_keyboard(lang, share_payload=result))
        await message.answer(note)


@router.message(F.text.in_({button_text("metaphor", "ru"), button_text("metaphor", "en")}))
async def metaphor_day(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        allowed, note = _limit_guard(session, user.id, lang)
        if not allowed:
            await message.answer(note)
            return
        text_value = extra.metaphor_of_the_day()
        result = t("metaphor", lang, text=text_value)
        log_history(session, user.id, "metaphor", "metaphor_day", {}, result)
        await maybe_delay_response(session)
        await message.answer(result, reply_markup=actions_keyboard(lang, share_payload=result))
        await message.answer(note)


@router.message(F.text.in_({button_text("numerology", "ru"), button_text("numerology", "en")}))
async def numerology_entry(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("destiny", "ru"), button_text("destiny", "en")}))
async def numerology_choose_destiny(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("name", "ru"), button_text("name", "en")}))
async def numerology_choose_name(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("personality", "ru"), button_text("personality", "en")}))
async def numerology_choose_personality(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("compat", "ru"), button_text("compat", "en")}))
async def numerology_choose_compatibility(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("back", "ru"), button_text("back", "en")}))
async def numerology_back(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.waiting_for_birthdate)
async def numerology_birthdate(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.waiting_for_second_birthdate)
async def numerology_second_birthdate(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(NumerologyStates.waiting_for_name)
async def numerology_name(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(F.text.in_({button_text("astro", "ru"), button_text("astro", "en")}))
async def astro_entry(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(AstroStates.waiting_for_birthdate)
async def astro_birthdate(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await _feature_unavailable(message, state, lang)


@router.message(F.text.in_({button_text("help", "ru"), button_text("help", "en")}))
async def help_button(message: Message) -> None:
    await cmd_help(message)


@router.message(F.text.in_({button_text("back", "ru"), button_text("back", "en")}))
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await reset_to_menu(message, lang, state)


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("admin_panel denied for %s", message.from_user.id)
        return
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await state.clear()
    await message.answer(t("admin_panel", lang), reply_markup=keyboards.admin_panel_keyboard(lang))


@router.message(Command("admin_stats"))
async def admin_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("admin_stats denied for %s", message.from_user.id)
        return
    text, charts = _build_admin_stats()
    await message.answer(text)
    for buffer, caption in charts:
        await message.answer_photo(
            BufferedInputFile(buffer.getvalue(), filename=f"{caption}.png"),
            caption=caption,
        )


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(call: CallbackQuery) -> None:
    await call.answer()
    if not _is_admin(call.from_user.id):
        await call.message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("admin_stats denied for %s", call.from_user.id)
        return
    text, charts = _build_admin_stats()
    await call.message.answer(text)
    for buffer, caption in charts:
        await call.message.answer_photo(
            BufferedInputFile(buffer.getvalue(), filename=f"{caption}.png"),
            caption=caption,
        )


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_menu(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_admin(call.from_user.id):
        await call.message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("broadcast denied for %s", call.from_user.id)
        return
    lang = _admin_language(call.from_user.id)
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await call.message.answer(t("admin_broadcast_prompt", lang))


@router.message(Command("set_delay"))
async def admin_set_delay(message: Message) -> None:
    config = CONFIG
    if message.from_user.id not in config.admin_ids:
        await message.answer(t("admin_denied", config.default_language))
        logger.warning("set_delay denied for %s", message.from_user.id)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(t("delay_usage", config.default_language))
        return
    try:
        delay_seconds = int(parts[1])
    except ValueError:
        await message.answer(t("delay_invalid", config.default_language))
        return
    if delay_seconds < 0:
        await message.answer(t("delay_invalid", config.default_language))
        return
    with session_scope(config.database_url) as session:
        settings = set_response_delay(session, delay_seconds)
    await message.answer(t("delay_updated", config.default_language, seconds=settings.response_delay_seconds))


@router.message(Command("broadcast"))
async def admin_broadcast_command(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("broadcast denied for %s", message.from_user.id)
        return
    lang = _admin_language(message.from_user.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await state.set_state(AdminStates.waiting_for_broadcast_text)
        await message.answer(t("admin_broadcast_prompt", lang))
        return
    count = await _send_broadcast(message.bot, parts[1])
    await message.answer(t("broadcast_ack", lang, count=count), reply_markup=keyboards.admin_panel_keyboard(lang))


@router.message(AdminStates.waiting_for_broadcast_text, F.text.lower().in_({"отмена", "cancel"}))
async def admin_broadcast_cancel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("broadcast denied for %s", message.from_user.id)
        return
    lang = _admin_language(message.from_user.id)
    await state.clear()
    await message.answer(t("admin_broadcast_cancel", lang), reply_markup=keyboards.admin_panel_keyboard(lang))


@router.message(AdminStates.waiting_for_broadcast_text)
async def admin_broadcast(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("broadcast denied for %s", message.from_user.id)
        return
    text = message.text
    lang = _admin_language(message.from_user.id)
    count = await _send_broadcast(message.bot, text)
    await state.clear()
    await message.answer(t("broadcast_ack", lang, count=count), reply_markup=keyboards.admin_panel_keyboard(lang))


@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not _is_admin(call.from_user.id):
        await call.message.answer(t("admin_denied", CONFIG.default_language))
        logger.warning("admin_back denied for %s", call.from_user.id)
        return
    lang = _admin_language(call.from_user.id)
    await state.clear()
    await call.message.answer(t("menu", lang), reply_markup=main_menu_markup(lang))


@router.callback_query(F.data == "another")
async def callback_another(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.clear()
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, call)
        lang = get_language(user)
    await call.message.answer(t("menu", lang), reply_markup=main_menu_markup(lang))


@router.callback_query(F.data == "back")
async def callback_back(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.clear()
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, call)
        lang = get_language(user)
    await call.message.answer(t("menu", lang), reply_markup=main_menu_markup(lang))


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    if await state.get_state():
        await state.clear()
        await reset_to_menu(message, lang, state, t("menu", lang))
        return
    await message.answer(t("help", lang), reply_markup=main_menu_markup(lang))
