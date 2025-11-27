from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .localization import button_text


def main_menu_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=button_text("tarot", lang)), KeyboardButton(text=button_text("numerology", lang))],
        [KeyboardButton(text=button_text("astro", lang)), KeyboardButton(text=button_text("random", lang))],
        [KeyboardButton(text=button_text("rune", lang)), KeyboardButton(text=button_text("metaphor", lang))],
        [KeyboardButton(text=button_text("profile", lang)), KeyboardButton(text=button_text("help", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def tarot_spreads_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=button_text("tarot_one", lang)), KeyboardButton(text=button_text("tarot_three", lang))],
        [KeyboardButton(text=button_text("tarot_situation", lang)), KeyboardButton(text=button_text("tarot_love", lang))],
        [KeyboardButton(text=button_text("tarot_career", lang)), KeyboardButton(text=button_text("back", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def numerology_options_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=button_text("destiny", lang)), KeyboardButton(text=button_text("name", lang))],
        [KeyboardButton(text=button_text("personality", lang)), KeyboardButton(text=button_text("compat", lang))],
        [KeyboardButton(text=button_text("back", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def profile_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=button_text("change_name", lang)), KeyboardButton(text=button_text("change_birth", lang))],
        [KeyboardButton(text=button_text("change_lang", lang)), KeyboardButton(text=button_text("delete", lang))],
        [KeyboardButton(text=button_text("back", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def result_actions_keyboard(lang: str = "ru", share_payload: str | None = None) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=button_text("another", lang), callback_data="another")],
        [InlineKeyboardButton(text=button_text("back", lang), callback_data="back")],
    ]
    if share_payload:
        buttons.insert(1, [InlineKeyboardButton(text=button_text("share", lang), switch_inline_query=share_payload)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_panel_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=button_text("admin_stats", lang), callback_data="admin_stats")],
        [InlineKeyboardButton(text=button_text("admin_broadcast", lang), callback_data="admin_broadcast")],
        [InlineKeyboardButton(text=button_text("admin_back", lang), callback_data="admin_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
