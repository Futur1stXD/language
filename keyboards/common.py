"""Общие клавиатуры"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.i18n import get_text


def get_consent_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура согласия на участие"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(lang, "consent_agree"),
            callback_data="consent_yes"
        )],
        [InlineKeyboardButton(
            text=get_text(lang, "consent_decline"),
            callback_data="consent_no"
        )]
    ])


def get_main_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(lang, "btn_get_help"),
            callback_data="get_help"
        )],
        [InlineKeyboardButton(
            text=get_text(lang, "btn_about"),
            callback_data="about_bot"
        )]
    ])


def get_start_survey_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура начала опроса"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(lang, "btn_start_survey"),
            callback_data="start_survey"
        )]
    ])


def get_back_to_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(lang, "btn_main_menu"),
            callback_data="main_menu"
        )]
    ])


def get_restart_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения перезапуска"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(lang, "restart_yes"),
            callback_data="restart_confirm"
        )],
        [InlineKeyboardButton(
            text=get_text(lang, "restart_no"),
            callback_data="restart_cancel"
        )]
    ])
