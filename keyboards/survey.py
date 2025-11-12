"""Клавиатуры для опроса"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict
from utils.i18n import get_text


def get_question_keyboard(
    options: List[Dict[str, str]],
    question_code: str,
    multi_select: bool = False,
    selected: List[str] = None,
    lang: str = "ru"
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для вопроса
    
    options: список опций [{"code": "Q1_OP1", "text": "12-13"}, ...]
    multi_select: множественный выбор (с тогглами)
    selected: уже выбранные опции (для мультивыбора)
    """
    selected = selected or []
    buttons = []
    
    for option in options:
        code = option["code"]
        text = option["text"]
        
        if multi_select:
            # Для мультивыбора добавляем галочку
            prefix = "✅ " if code in selected else ""
            callback_data = f"toggle_{question_code}_{code}"
        else:
            prefix = ""
            callback_data = f"answer_{question_code}_{code}"
        
        buttons.append([InlineKeyboardButton(
            text=f"{prefix}{text}",
            callback_data=callback_data
        )])
    
    # Для мультивыбора добавляем кнопку "Далее"
    if multi_select and selected:
        buttons.append([InlineKeyboardButton(
            text=get_text(lang, "btn_next"),
            callback_data=f"multi_done_{question_code}"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_navigation_keyboard(
    current_question: int,
    total_questions: int,
    can_skip: bool = False,
    lang: str = "ru"
) -> InlineKeyboardMarkup:
    """Клавиатура навигации между вопросами"""
    buttons = []
    row = []
    
    if current_question > 1:
        row.append(InlineKeyboardButton(
            text=get_text(lang, "btn_back"),
            callback_data=f"nav_back_{current_question}"
        ))
    
    if can_skip:
        row.append(InlineKeyboardButton(
            text=get_text(lang, "btn_skip"),
            callback_data=f"nav_skip_{current_question}"
        ))
    
    if row:
        buttons.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
