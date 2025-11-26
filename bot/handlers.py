from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func
from sqlmodel import delete, select

from . import keyboards
from .config import BotConfig
from .db import get_or_create_user, session_scope
from .localization import BUTTONS, button_text, t
from .models import SpreadHistory, User
from .services import astrology, extra, numerology, tarot
from .states import AstroStates, NumerologyStates, ProfileStates, TarotStates

router = Router()
logger = logging.getLogger(__name__)

CONFIG = BotConfig.load()


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


@router.message(ProfileStates.waiting_for_language, F.text.lower().in_("ru", "en"))
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


@router.message(ProfileStates.confirming_delete, F.text.lower().in_("да", "yes"))
async def profile_delete_confirm(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if user:
            session.delete(user)
            session.exec(delete(SpreadHistory).where(SpreadHistory.user_id == user.id))
            session.commit()
    await reset_to_menu(message, lang, state, t("delete_done", lang))


@router.message(ProfileStates.confirming_delete, F.text.lower().in_("нет", "no"))
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
    import random

    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        allowed, note = _limit_guard(session, user.id, lang)
        if not allowed:
            await message.answer(note)
            return
        systems = ["tarot", "numerology", "astro", "rune", "metaphor"]
        system = random.choice(systems)
        if system == "tarot":
            result = tarot.spread_three_cards(session)
            tarot.save_history(session, user.id, system, "random_tarot", json.dumps({}), result)
        elif system == "numerology":
            today = datetime.utcnow().date()
            destiny = numerology.destiny_number(session, today.day, today.month, today.year)
            result = f"{destiny.title}: {destiny.number}\n{destiny.description}"
            numerology.save_history(session, user.id, json.dumps({"random": True}), result)
        elif system == "astro":
            today = datetime.utcnow().date()
            sign = astrology.zodiac_for_date(session, today)
            result = astrology.short_portrait(sign) if sign else t("bad_date", lang)
            if sign:
                astrology.save_history(session, user.id, sign, result)
        elif system == "rune":
            name, meaning = extra.rune_of_the_day()
            result = t("rune", lang, name=name, meaning=meaning)
            log_history(session, user.id, "rune", name, {}, result)
        else:
            text = extra.metaphor_of_the_day()
            result = t("metaphor", lang, text=text)
            log_history(session, user.id, "metaphor", "metaphor_day", {}, result)
        await message.answer(t("random_result", lang, system=system, result=result), reply_markup=actions_keyboard(lang, share_payload=result))
        await message.answer(note)


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
        await message.answer(result, reply_markup=actions_keyboard(lang, share_payload=result))
        await message.answer(note)


@router.message(F.text.in_({button_text("numerology", "ru"), button_text("numerology", "en")}))
async def numerology_entry(message: Message, state: FSMContext) -> None:
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await state.set_state(NumerologyStates.choosing_calculation)
    await message.answer(t("numerology_prompt", lang), reply_markup=keyboards.numerology_options_keyboard(lang))


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("destiny", "ru"), button_text("destiny", "en")}))
async def numerology_choose_destiny(message: Message, state: FSMContext) -> None:
    await state.set_state(NumerologyStates.waiting_for_birthdate)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await message.answer(t("ask_birthdate", lang))


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("name", "ru"), button_text("name", "en")}))
async def numerology_choose_name(message: Message, state: FSMContext) -> None:
    await state.set_state(NumerologyStates.waiting_for_name)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await message.answer(t("name_prompt", lang))


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("personality", "ru"), button_text("personality", "en")}))
async def numerology_choose_personality(message: Message, state: FSMContext) -> None:
    await state.set_state(NumerologyStates.waiting_for_name)
    await state.update_data(require_birthdate=True)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await message.answer(t("name_prompt", lang))


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("compat", "ru"), button_text("compat", "en")}))
async def numerology_choose_compatibility(message: Message, state: FSMContext) -> None:
    await state.set_state(NumerologyStates.waiting_for_birthdate)
    await state.update_data(compatibility=True)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await message.answer(t("compat_first", lang))


@router.message(NumerologyStates.choosing_calculation, F.text.in_({button_text("back", "ru"), button_text("back", "en")}))
async def numerology_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await reset_to_menu(message, lang, state)


@router.message(NumerologyStates.waiting_for_birthdate)
async def numerology_birthdate(message: Message, state: FSMContext) -> None:
    parsed = parse_birthdate(message.text)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if not parsed:
            await message.answer(t("bad_date", lang))
            return
        data = await state.get_data()
        allowed, note = _limit_guard(session, user.id, lang)
        if not allowed:
            await message.answer(note)
            await state.clear()
            return
        if data.get("require_birthdate"):
            name = data.get("name", message.from_user.full_name)
            results = numerology.personality_card(session, name, parsed.day, parsed.month, parsed.year)
            text_lines = ["Краткая нумерологическая карта личности:"]
            for item in results:
                text_lines.append(f"{item.title}: {item.number} — {item.description}")
            payload = json.dumps({"name": name, "birthdate": parsed.date().isoformat()})
            numerology.save_history(session, user.id, payload, "\n".join(text_lines))
            await message.answer("\n".join(text_lines), reply_markup=actions_keyboard(lang, share_payload="\n".join(text_lines)))
            await message.answer(note)
            await state.clear()
            return
        if data.get("compatibility") and not data.get("first_birthdate"):
            await state.update_data(first_birthdate=parsed)
            await state.set_state(NumerologyStates.waiting_for_second_birthdate)
            await message.answer(t("compat_second", lang))
            return
        result = numerology.destiny_number(session, parsed.day, parsed.month, parsed.year)
        profile_user = user
        if profile_user:
            profile_user.birth_date = parsed.date()
            session.add(profile_user)
            session.commit()
        numerology.save_history(session, user.id, json.dumps({"birthdate": parsed.date().isoformat()}), f"{result.title}: {result.number}\n{result.description}")
        await message.answer(f"{result.title}: {result.number}\n{result.description}", reply_markup=actions_keyboard(lang, share_payload=f"{result.title}: {result.number}"))
        await message.answer(note)
    await state.clear()


@router.message(NumerologyStates.waiting_for_second_birthdate)
async def numerology_second_birthdate(message: Message, state: FSMContext) -> None:
    parsed = parse_birthdate(message.text)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if not parsed:
            await message.answer(t("bad_date", lang))
            return
        data = await state.get_data()
        first: datetime = data.get("first_birthdate")
        compat = numerology.compatibility(session, (first.day, first.month, first.year), (parsed.day, parsed.month, parsed.year))
        text = (
            f"Совместимость чисел судьбы: {compat.score}/10\n"
            f"Первый: {compat.first_number}, Второй: {compat.second_number}\n{compat.description}"
        )
        numerology.save_history(session, user.id, json.dumps({"first": first.date().isoformat(), "second": parsed.date().isoformat()}), text)
        await message.answer(text, reply_markup=actions_keyboard(lang, share_payload=text))
    await state.clear()


@router.message(NumerologyStates.waiting_for_name)
async def numerology_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    name = message.text.strip()
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        allowed, note = _limit_guard(session, user.id, lang)
        if not allowed:
            await message.answer(note)
            await state.clear()
            return
        if data.get("require_birthdate"):
            await state.update_data(name=name)
            await state.set_state(NumerologyStates.waiting_for_birthdate)
            await message.answer(t("ask_birthdate", lang))
            return
        result = numerology.name_number(session, name)
        numerology.save_history(session, user.id, json.dumps({"name": name}), f"{result.title}: {result.number}\n{result.description}")
        await message.answer(f"{result.title}: {result.number}\n{result.description}", reply_markup=actions_keyboard(lang, share_payload=f"{result.title}: {result.number}"))
        await message.answer(note)
    await state.clear()


@router.message(F.text.in_({button_text("astro", "ru"), button_text("astro", "en")}))
async def astro_entry(message: Message, state: FSMContext) -> None:
    await state.set_state(AstroStates.waiting_for_birthdate)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
    await message.answer(t("astro_prompt", lang))


@router.message(AstroStates.waiting_for_birthdate)
async def astro_birthdate(message: Message, state: FSMContext) -> None:
    parsed = parse_birthdate(message.text)
    with session_scope(CONFIG.database_url) as session:
        user = ensure_user(session, message)
        lang = get_language(user)
        if not parsed:
            await message.answer(t("bad_date", lang))
            return
        allowed, note = _limit_guard(session, user.id, lang)
        if not allowed:
            await message.answer(note)
            await state.clear()
            return
        sign = astrology.zodiac_for_date(session, parsed.date())
        if user:
            user.birth_date = parsed.date()
            session.add(user)
            session.commit()
        await state.clear()
        if not sign:
            await message.answer(t("bad_date", lang))
            return
        text = astrology.short_portrait(sign)
        astrology.save_history(session, user.id, sign, text)
        await message.answer(text, reply_markup=actions_keyboard(lang, share_payload=text))
        await message.answer(note)


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


@router.message(Command("admin_stats"))
async def admin_stats(message: Message) -> None:
    config = CONFIG
    if message.from_user.id not in config.admin_ids:
        await message.answer(t("admin_denied", config.default_language))
        logger.warning("admin_stats denied for %s", message.from_user.id)
        return
    with session_scope(config.database_url) as session:
        total_users = session.exec(select(func.count()).select_from(User)).one()
        total_spreads = session.exec(select(func.count()).select_from(SpreadHistory)).one()
        start_day = datetime.combine(datetime.utcnow().date(), time.min)
        end_day = start_day + timedelta(days=1)
        today_spreads = session.exec(
            select(func.count())
            .select_from(SpreadHistory)
            .where(SpreadHistory.created_at >= start_day)
            .where(SpreadHistory.created_at < end_day)
        ).one()
        by_type = session.exec(
            select(SpreadHistory.type, func.count()).group_by(SpreadHistory.type)
        ).all()
        type_lines = "\n".join(f"{item[0]}: {item[1]}" for item in by_type)
        text = (
            f"Пользователи: {total_users}\n"
            f"Раскладов всего: {total_spreads}\n"
            f"За сегодня: {today_spreads}\n"
            f"По типам:\n{type_lines}"
        )
        await message.answer(text)


@router.message(Command("broadcast"))
async def admin_broadcast(message: Message) -> None:
    config = CONFIG
    if message.from_user.id not in config.admin_ids:
        await message.answer(t("admin_denied", config.default_language))
        logger.warning("broadcast denied for %s", message.from_user.id)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(t("broadcast_usage", config.default_language))
        return
    text = parts[1]
    count = 0
    with session_scope(config.database_url) as session:
        users = session.exec(select(User)).all()
        for user in users:
            try:
                await message.bot.send_message(user.telegram_id, text)
                count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("broadcast failed for %s: %s", user.telegram_id, exc)
    await message.answer(t("broadcast_ack", config.default_language, count=count))


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
