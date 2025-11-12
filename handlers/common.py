"""Базовые хендлеры (команды /start, /help и т.д.)"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_session, Respondent, Answer
from keyboards import (
    get_consent_keyboard, 
    get_main_menu_keyboard,
    get_start_survey_keyboard, 
    get_restart_keyboard,
    get_back_to_menu_keyboard
)
from utils.i18n import get_text
from utils.config import ADMIN_IDS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    await state.clear()
    
    # Устанавливаем русский язык по умолчанию
    await state.update_data(lang="ru")
    lang = "ru"
    
    await message.answer(
        get_text(lang, "start_welcome"),
        reply_markup=get_consent_keyboard(lang)
    )


@router.callback_query(F.data == "consent_yes")
async def consent_yes(callback: CallbackQuery, state: FSMContext):
    """Согласие на участие"""
    await callback.answer()
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await state.update_data(consented=True)
    
    # Создаем или получаем респондента
    async for session in get_session():
        result = await session.execute(
            select(Respondent).where(
                and_(
                    Respondent.user_id == callback.from_user.id,
                    Respondent.archived == False
                )
            )
        )
        respondent = result.scalar_one_or_none()
        
        if not respondent:
            respondent = Respondent(
                user_id=callback.from_user.id,
                username=callback.from_user.username,
                language_code=lang,
                consented=True
            )
            session.add(respondent)
            await session.commit()
            await session.refresh(respondent)
        else:
            respondent.language_code = lang
            respondent.consented = True
            await session.commit()
        
        await state.update_data(respondent_id=respondent.id)
    
    # Переходим сразу к главному меню
    await callback.message.edit_text(
        get_text(lang, "main_menu"),
        reply_markup=get_main_menu_keyboard(lang)
    )


@router.callback_query(F.data == "consent_no")
async def consent_no(callback: CallbackQuery, state: FSMContext):
    """Отказ от участия"""
    await callback.answer()
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await callback.message.edit_text(get_text(lang, "consent_declined"))


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Показать главное меню"""
    await callback.answer()
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await callback.message.edit_text(
        get_text(lang, "main_menu"),
        reply_markup=get_main_menu_keyboard(lang)
    )


@router.callback_query(F.data == "get_help")
async def get_help(callback: CallbackQuery, state: FSMContext):
    """Начать процесс получения помощи"""
    await callback.answer()
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    respondent_id = user_data.get("respondent_id")
    
    if not respondent_id:
        await callback.message.answer("Начните с команды /start")
        return
    
    # Показываем вступительное сообщение
    await callback.message.edit_text(get_text(lang, "get_help_intro"))
    
    # Импортируем функцию show_question из survey
    from handlers.survey import show_question
    
    # Сразу начинаем с первого вопроса
    await show_question(callback.message, "Q1", state)


@router.callback_query(F.data == "about_bot")
async def about_bot(callback: CallbackQuery, state: FSMContext):
    """О боте"""
    await callback.answer()
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await callback.message.edit_text(
        get_text(lang, "about_bot"),
        reply_markup=get_back_to_menu_keyboard(lang)
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    """Команда /help"""
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await message.answer(get_text(lang, "help_text"))


@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext):
    """Команда /status - прогресс опроса"""
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    respondent_id = user_data.get("respondent_id")
    
    if not respondent_id:
        await message.answer("Начните с команды /start")
        return
    
    async for session in get_session():
        result = await session.execute(
            select(Answer).where(Answer.respondent_id == respondent_id)
        )
        answers = result.scalars().all()
        
        # Подсчитываем ответы на начальные и языковые вопросы
        from utils.questions import INITIAL_QUESTIONS, LINGUISTIC_QUESTIONS
        total = len(INITIAL_QUESTIONS)
        
        # Проверяем, перешли ли к языковому опросу
        initial_answers = {a.question_code: a.answer for a in answers if a.question_code.startswith('Q')}
        if len(initial_answers) >= len(INITIAL_QUESTIONS):
            total += len(LINGUISTIC_QUESTIONS)
        
        answered = len(set(a.question_code for a in answers))
        remaining = total - answered
        
        await message.answer(
            get_text(lang, "status_info", 
                    answered=answered, 
                    total=total, 
                    remaining=remaining)
        )


@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext):
    """Команда /restart - перезапуск опроса"""
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await message.answer(
        get_text(lang, "restart_confirm"),
        reply_markup=get_restart_keyboard(lang)
    )


@router.callback_query(F.data == "restart_confirm")
async def restart_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение перезапуска"""
    await callback.answer()
    
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    # Архивируем старую сессию
    async for session in get_session():
        result = await session.execute(
            select(Respondent).where(
                and_(
                    Respondent.user_id == callback.from_user.id,
                    Respondent.archived == False
                )
            )
        )
        old_respondent = result.scalar_one_or_none()
        
        if old_respondent:
            old_respondent.archived = True
            await session.commit()
        
        # Создаем новую сессию
        new_respondent = Respondent(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            language_code=lang,
            consented=True
        )
        session.add(new_respondent)
        await session.commit()
        await session.refresh(new_respondent)
        
        await state.clear()
        await state.update_data(
            respondent_id=new_respondent.id,
            lang=lang,
            consented=True
        )
    
    await callback.message.edit_text(
        get_text(lang, "restart_done"),
        reply_markup=get_main_menu_keyboard(lang)
    )


@router.callback_query(F.data == "restart_cancel")
async def restart_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена перезапуска"""
    await callback.answer()
    
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await callback.message.edit_text(get_text(lang, "restart_cancelled"))


@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext):
    """Команда /status - прогресс опроса"""
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    respondent_id = user_data.get("respondent_id")
    
    if not respondent_id:
        await message.answer("Начните опрос командой /start")
        return
    
    async for session in get_session():
        result = await session.execute(
            select(Answer).where(Answer.respondent_id == respondent_id)
        )
        answers = result.scalars().all()
        
        total = 16
        answered = len(set(a.question_code for a in answers))
        remaining = total - answered
        
        await message.answer(
            get_text(lang, "status_info", 
                    answered=answered, 
                    total=total, 
                    remaining=remaining)
        )


@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext):
    """Команда /restart - перезапуск опроса"""
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await message.answer(
        get_text(lang, "restart_confirm"),
        reply_markup=get_restart_keyboard(lang)
    )


@router.callback_query(F.data == "restart_confirm")
async def restart_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение перезапуска"""
    await callback.answer()
    
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    # Архивируем старую сессию
    async for session in get_session():
        result = await session.execute(
            select(Respondent).where(
                and_(
                    Respondent.user_id == callback.from_user.id,
                    Respondent.archived == False
                )
            )
        )
        old_respondent = result.scalar_one_or_none()
        
        if old_respondent:
            old_respondent.archived = True
            await session.commit()
        
        # Создаем новую сессию
        new_respondent = Respondent(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            language_code=lang,
            consented=True
        )
        session.add(new_respondent)
        await session.commit()
        await session.refresh(new_respondent)
        
        await state.clear()
        await state.update_data(
            respondent_id=new_respondent.id,
            lang=lang,
            consented=True
        )
    
    await callback.message.edit_text(
        get_text(lang, "restart_done"),
        reply_markup=get_start_survey_keyboard(lang)
    )


@router.callback_query(F.data == "restart_cancel")
async def restart_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена перезапуска"""
    await callback.answer()
    
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await callback.message.edit_text(get_text(lang, "restart_cancelled"))
