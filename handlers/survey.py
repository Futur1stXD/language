"""Хендлеры опроса"""
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_, update
from datetime import datetime

from models import get_session, Respondent, Answer
from keyboards import get_question_keyboard, get_navigation_keyboard, get_back_to_menu_keyboard
from utils.i18n import get_text
from utils.questions import (
    INITIAL_QUESTIONS,
    LINGUISTIC_QUESTIONS,
    QUESTIONS, 
    get_question_by_code, 
    get_next_question, 
    get_previous_question,
    get_question_number,
    is_linguistic_bullying,
    determine_aggression_type
)
from utils.recommendations import get_recommendation_by_type, get_rejection_message
from .states import SurveyFSM

router = Router()


async def save_answer(respondent_id: int, question_code: str, answer_value: str):
    """Сохранить ответ в БД"""
    async for session in get_session():
        # Проверяем, есть ли уже ответ
        result = await session.execute(
            select(Answer).where(
                and_(
                    Answer.respondent_id == respondent_id,
                    Answer.question_code == question_code
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.answer = answer_value
        else:
            answer = Answer(
                respondent_id=respondent_id,
                question_code=question_code,
                answer=answer_value
            )
            session.add(answer)
        
        await session.commit()


async def get_answers_dict(respondent_id: int) -> dict:
    """Получить все ответы респондента в виде словаря"""
    async for session in get_session():
        result = await session.execute(
            select(Answer).where(Answer.respondent_id == respondent_id)
        )
        answers = result.scalars().all()
        return {a.question_code: a.answer for a in answers}


async def show_question(message: Message, question_code: str, state: FSMContext, edit: bool = False):
    """Показать вопрос"""
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    respondent_id = user_data.get("respondent_id")
    
    question = get_question_by_code(question_code)
    if not question:
        await message.answer("Ошибка: вопрос не найден")
        return
    
    # Определяем этап опроса
    if question_code.startswith('Q'):
        # Начальный опрос
        questions_list = INITIAL_QUESTIONS
        question_num = next((i + 1 for i, q in enumerate(questions_list) if q["code"] == question_code), 0)
        total = len(questions_list)
    else:
        # Языковой опрос
        questions_list = LINGUISTIC_QUESTIONS
        question_num = next((i + 1 for i, q in enumerate(questions_list) if q["code"] == question_code), 0)
        total = len(questions_list)
    
    # Формируем текст с прогрессом
    progress_text = f"📊 {get_text(lang, 'progress', current=question_num, total=total)}\n\n"
    full_text = progress_text + question["text"]
    
    # Для открытых вопросов
    if question["type"] == "open":
        await state.set_state(SurveyFSM.waiting_input)
        await state.update_data(current_question=question_code, input_type="open")
        
        keyboard = get_navigation_keyboard(question_num, total, can_skip=not question.get("required"), lang=lang)
        
        if edit and message.text:
            await message.edit_text(full_text, reply_markup=keyboard)
        else:
            await message.answer(full_text, reply_markup=keyboard)
        return
    
    # Получаем уже выбранные опции (для мультивыбора)
    selected = []
    if question["type"] == "multi":
        answers = await get_answers_dict(respondent_id)
        if question_code in answers:
            try:
                selected = json.loads(answers[question_code])
            except:
                selected = []
    
    # Создаём клавиатуру
    keyboard = get_question_keyboard(
        options=question.get("options", []),
        question_code=question_code,
        multi_select=(question["type"] == "multi"),
        selected=selected,
        lang=lang
    )
    
    await state.update_data(current_question=question_code, selected_options=selected)
    
    # Устанавливаем состояние
    state_name = question_code.replace('Q', 'Q').replace('LQ', 'LQ')
    await state.set_state(getattr(SurveyFSM, state_name, None))
    
    if edit and hasattr(message, 'edit_text'):
        await message.edit_text(full_text, reply_markup=keyboard)
    else:
        await message.answer(full_text, reply_markup=keyboard)


@router.callback_query(F.data == "start_survey")
async def start_survey(callback: CallbackQuery, state: FSMContext):
    """Начать опрос"""
    await callback.answer()
    
    user_data = await state.get_data()
    respondent_id = user_data.get("respondent_id")
    
    if not respondent_id:
        await callback.message.answer("Начните с команды /start")
        return
    
    # Начинаем с первого вопроса
    await show_question(callback.message, "Q1", state)


@router.message(Command("survey"))
async def cmd_survey(message: Message, state: FSMContext):
    """Команда начала опроса"""
    user_data = await state.get_data()
    respondent_id = user_data.get("respondent_id")
    
    if not respondent_id:
        await message.answer("Начните с команды /start")
        return
    
    await show_question(message, "Q1", state)


# Обработка одиночного выбора
@router.callback_query(F.data.startswith("answer_"))
async def handle_single_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка одиночного выбора"""
    await callback.answer()
    
    parts = callback.data.split("_")
    question_code = parts[1]  # Q1, Q2, etc.
    option_code = "_".join(parts[2:])  # Q1_OP1, etc.
    
    user_data = await state.get_data()
    respondent_id = user_data.get("respondent_id")
    lang = user_data.get("lang", "ru")
    
    # Проверяем, нужен ли дополнительный ввод
    question = get_question_by_code(question_code)
    option = next((o for o in question.get("options", []) if o["code"] == option_code), None)
    
    if option and option.get("has_input"):
        # Запрашиваем дополнительный ввод
        await state.set_state(SurveyFSM.waiting_input)
        await state.update_data(
            current_question=question_code,
            pending_answer=option_code,
            input_type="option"
        )
        await callback.message.answer(get_text(lang, "input_text"))
        return
    
    # Сохраняем ответ
    await save_answer(respondent_id, question_code, option_code)
    
    # Определяем следующий вопрос в зависимости от текущего этапа
    answers = await get_answers_dict(respondent_id)
    
    if question_code.startswith('Q'):
        # В начальных вопросах
        current_idx = next((i for i, q in enumerate(INITIAL_QUESTIONS) if q["code"] == question_code), -1)
        if current_idx < len(INITIAL_QUESTIONS) - 1:
            next_q = INITIAL_QUESTIONS[current_idx + 1]["code"]
            await show_question(callback.message, next_q, state, edit=True)
        else:
            # Завершили начальные вопросы
            if is_linguistic_bullying(answers):
                await callback.message.answer(get_text(lang, "linguistic_bullying_detected"))
                await show_question(callback.message, "LQ1", state)
            else:
                await callback.message.answer(
                    get_rejection_message(),
                    reply_markup=get_back_to_menu_keyboard(lang)
                )
                await state.set_state(SurveyFSM.showing_recommendations)
    else:
        # В языковых вопросах
        current_idx = next((i for i, q in enumerate(LINGUISTIC_QUESTIONS) if q["code"] == question_code), -1)
        if current_idx < len(LINGUISTIC_QUESTIONS) - 1:
            next_q = LINGUISTIC_QUESTIONS[current_idx + 1]["code"]
            await show_question(callback.message, next_q, state, edit=True)
        else:
            # Завершили все вопросы
            await finish_survey(callback.message, state)


# Обработка множественного выбора (тогглы)
@router.callback_query(F.data.startswith("toggle_"))
async def handle_multi_toggle(callback: CallbackQuery, state: FSMContext):
    """Обработка тоггла в мультивыборе"""
    await callback.answer()
    
    parts = callback.data.split("_")
    question_code = parts[1]
    option_code = "_".join(parts[2:])
    
    user_data = await state.get_data()
    selected = user_data.get("selected_options", [])
    
    # Тоггл опции
    if option_code in selected:
        selected.remove(option_code)
    else:
        selected.append(option_code)
    
    await state.update_data(selected_options=selected)
    
    # Обновляем клавиатуру
    question = get_question_by_code(question_code)
    lang = user_data.get("lang", "ru")
    
    keyboard = get_question_keyboard(
        options=question.get("options", []),
        question_code=question_code,
        multi_select=True,
        selected=selected,
        lang=lang
    )
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)


# Завершение мультивыбора
@router.callback_query(F.data.startswith("multi_done_"))
async def handle_multi_done(callback: CallbackQuery, state: FSMContext):
    """Завершение мультивыбора"""
    await callback.answer()
    
    question_code = callback.data.replace("multi_done_", "")
    
    user_data = await state.get_data()
    respondent_id = user_data.get("respondent_id")
    lang = user_data.get("lang", "ru")
    selected = user_data.get("selected_options", [])
    
    # Проверяем, есть ли опции с дополнительным вводом
    question = get_question_by_code(question_code)
    for option_code in selected:
        option = next((o for o in question.get("options", []) if o["code"] == option_code), None)
        if option and option.get("has_input"):
            # Запрашиваем ввод для этой опции
            await state.set_state(SurveyFSM.waiting_input)
            await state.update_data(
                current_question=question_code,
                pending_multi_answer=selected,
                input_for_option=option_code,
                input_type="multi_option"
            )
            await callback.message.answer(f"{option['text']}\n\n{get_text(lang, 'input_text')}")
            return
    
    # Сохраняем мультиответ
    await save_answer(respondent_id, question_code, json.dumps(selected))
    
    # Проверяем, завершили ли мы начальные вопросы
    if question_code == "Q2":
        # Это был последний вопрос из начальных
        answers = await get_answers_dict(respondent_id)
        
        # Анализируем, является ли это языковым буллингом
        if is_linguistic_bullying(answers):
            # Языковой буллинг - продолжаем уточняющими вопросами
            await callback.message.answer(get_text(lang, "linguistic_bullying_detected"))
            await show_question(callback.message, "LQ1", state)
        else:
            # Не языковой буллинг - показываем сообщение об отказе
            await callback.message.answer(
                get_rejection_message(),
                reply_markup=get_back_to_menu_keyboard(lang)
            )
            await state.set_state(SurveyFSM.showing_recommendations)
    else:
        # Продолжаем опрос
        answers = await get_answers_dict(respondent_id)
        
        # Определяем следующий вопрос
        if question_code.startswith('Q'):
            # В начальных вопросах
            current_idx = next((i for i, q in enumerate(INITIAL_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(INITIAL_QUESTIONS) - 1:
                next_q = INITIAL_QUESTIONS[current_idx + 1]["code"]
                await show_question(callback.message, next_q, state)
            else:
                # Завершили начальные вопросы, проверяем тип буллинга
                if is_linguistic_bullying(answers):
                    await callback.message.answer(get_text(lang, "linguistic_bullying_detected"))
                    await show_question(callback.message, "LQ1", state)
                else:
                    await callback.message.answer(
                        get_rejection_message(),
                        reply_markup=get_back_to_menu_keyboard(lang)
                    )
                    await state.set_state(SurveyFSM.showing_recommendations)
        else:
            # В языковых вопросах
            current_idx = next((i for i, q in enumerate(LINGUISTIC_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(LINGUISTIC_QUESTIONS) - 1:
                next_q = LINGUISTIC_QUESTIONS[current_idx + 1]["code"]
                await show_question(callback.message, next_q, state)
            else:
                # Завершили все вопросы - показываем рекомендации
                await finish_survey(callback.message, state)


# Обработка текстового ввода
@router.message(SurveyFSM.waiting_input)
async def handle_text_input(message: Message, state: FSMContext):
    """Обработка текстового ввода"""
    user_data = await state.get_data()
    respondent_id = user_data.get("respondent_id")
    question_code = user_data.get("current_question")
    input_type = user_data.get("input_type")
    lang = user_data.get("lang", "ru")
    
    if input_type == "open":
        # Открытый вопрос (пока не используется в новой логике)
        await save_answer(respondent_id, question_code, message.text)
        
        answers = await get_answers_dict(respondent_id)
        
        # Определяем следующий вопрос
        if question_code.startswith('Q'):
            current_idx = next((i for i, q in enumerate(INITIAL_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(INITIAL_QUESTIONS) - 1:
                next_q = INITIAL_QUESTIONS[current_idx + 1]["code"]
                await show_question(message, next_q, state)
            else:
                if is_linguistic_bullying(answers):
                    await message.answer(get_text(lang, "linguistic_bullying_detected"))
                    await show_question(message, "LQ1", state)
                else:
                    await message.answer(
                        get_rejection_message(),
                        reply_markup=get_back_to_menu_keyboard(lang)
                    )
                    await state.set_state(SurveyFSM.showing_recommendations)
        else:
            current_idx = next((i for i, q in enumerate(LINGUISTIC_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(LINGUISTIC_QUESTIONS) - 1:
                next_q = LINGUISTIC_QUESTIONS[current_idx + 1]["code"]
                await show_question(message, next_q, state)
            else:
                await finish_survey(message, state)
    
    elif input_type == "option":
        # Дополнительный ввод для одиночного выбора
        option_code = user_data.get("pending_answer")
        combined = f"{option_code}:{message.text}"
        await save_answer(respondent_id, question_code, combined)
        
        answers = await get_answers_dict(respondent_id)
        
        # Определяем следующий вопрос
        if question_code.startswith('Q'):
            current_idx = next((i for i, q in enumerate(INITIAL_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(INITIAL_QUESTIONS) - 1:
                next_q = INITIAL_QUESTIONS[current_idx + 1]["code"]
                await show_question(message, next_q, state)
            else:
                if is_linguistic_bullying(answers):
                    await message.answer(get_text(lang, "linguistic_bullying_detected"))
                    await show_question(message, "LQ1", state)
                else:
                    await message.answer(
                        get_rejection_message(),
                        reply_markup=get_back_to_menu_keyboard(lang)
                    )
                    await state.set_state(SurveyFSM.showing_recommendations)
        else:
            current_idx = next((i for i, q in enumerate(LINGUISTIC_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(LINGUISTIC_QUESTIONS) - 1:
                next_q = LINGUISTIC_QUESTIONS[current_idx + 1]["code"]
                await show_question(message, next_q, state)
            else:
                await finish_survey(message, state)
    
    elif input_type == "multi_option":
        # Дополнительный ввод для мультивыбора
        selected = user_data.get("pending_multi_answer", [])
        option_code = user_data.get("input_for_option")
        
        # Заменяем код опции на код с текстом
        selected = [f"{opt}:{message.text}" if opt == option_code else opt for opt in selected]
        
        await save_answer(respondent_id, question_code, json.dumps(selected))
        
        answers = await get_answers_dict(respondent_id)
        
        # Определяем следующий вопрос
        if question_code.startswith('Q'):
            current_idx = next((i for i, q in enumerate(INITIAL_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(INITIAL_QUESTIONS) - 1:
                next_q = INITIAL_QUESTIONS[current_idx + 1]["code"]
                await show_question(message, next_q, state)
            else:
                if is_linguistic_bullying(answers):
                    await message.answer(get_text(lang, "linguistic_bullying_detected"))
                    await show_question(message, "LQ1", state)
                else:
                    await message.answer(
                        get_rejection_message(),
                        reply_markup=get_back_to_menu_keyboard(lang)
                    )
                    await state.set_state(SurveyFSM.showing_recommendations)
        else:
            current_idx = next((i for i, q in enumerate(LINGUISTIC_QUESTIONS) if q["code"] == question_code), -1)
            if current_idx < len(LINGUISTIC_QUESTIONS) - 1:
                next_q = LINGUISTIC_QUESTIONS[current_idx + 1]["code"]
                await show_question(message, next_q, state)
            else:
                await finish_survey(message, state)


# Навигация назад
@router.callback_query(F.data.startswith("nav_back_"))
async def handle_back(callback: CallbackQuery, state: FSMContext):
    """Возврат к предыдущему вопросу"""
    await callback.answer()
    
    user_data = await state.get_data()
    current_q = user_data.get("current_question")
    
    prev_q = get_previous_question(current_q)
    if prev_q:
        await show_question(callback.message, prev_q, state, edit=True)


# Пропуск вопроса
@router.callback_query(F.data.startswith("nav_skip_"))
async def handle_skip(callback: CallbackQuery, state: FSMContext):
    """Пропустить вопрос"""
    await callback.answer()
    
    user_data = await state.get_data()
    current_q = user_data.get("current_question")
    respondent_id = user_data.get("respondent_id")
    
    answers = await get_answers_dict(respondent_id)
    next_q = get_next_question(current_q, answers)
    
    if next_q:
        await show_question(callback.message, next_q, state, edit=True)
    else:
        await finish_survey(callback.message, state)


async def finish_survey(message: Message, state: FSMContext):
    """Завершение опроса и показ рекомендаций"""
    user_data = await state.get_data()
    respondent_id = user_data.get("respondent_id")
    lang = user_data.get("lang", "ru")
    
    # Получаем все ответы
    answers = await get_answers_dict(respondent_id)
    
    # Помечаем опрос как завершённый
    async for session in get_session():
        await session.execute(
            update(Respondent)
            .where(Respondent.id == respondent_id)
            .values(completed=True, completed_at=datetime.utcnow())
        )
        await session.commit()
    
    await message.answer(get_text(lang, "survey_completed"))
    
    # Определяем тип агрессии
    aggression_type = determine_aggression_type(answers)
    
    # Получаем рекомендации
    recommendations = get_recommendation_by_type('linguistic', aggression_type)
    
    if recommendations:
        # Отправляем рекомендации (может быть длинным, разбиваем если нужно)
        rec_text = get_text(lang, "recommendations_title") + recommendations
        
        # Telegram имеет ограничение в 4096 символов на сообщение
        max_length = 4000
        if len(rec_text) <= max_length:
            await message.answer(
                rec_text,
                reply_markup=get_back_to_menu_keyboard(lang),
                parse_mode=None  # Отключаем парсинг, так как там могут быть спецсимволы
            )
        else:
            # Разбиваем на части
            parts = []
            current_part = ""
            for line in rec_text.split('\n'):
                if len(current_part) + len(line) + 1 < max_length:
                    current_part += line + '\n'
                else:
                    parts.append(current_part)
                    current_part = line + '\n'
            if current_part:
                parts.append(current_part)
            
            # Отправляем части
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # Последняя часть с кнопкой
                    await message.answer(
                        part,
                        reply_markup=get_back_to_menu_keyboard(lang),
                        parse_mode=None
                    )
                else:
                    await message.answer(part, parse_mode=None)
    
    await state.set_state(SurveyFSM.showing_recommendations)
    await state.clear()
