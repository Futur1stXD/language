"""Админские хендлеры"""
import os
import csv
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import update

from models import get_session, Respondent
from services.analytics import SurveyAnalytics
from utils.config import ADMIN_IDS

router = Router()


def admin_only(func):
    """Декоратор для проверки прав администратора"""
    async def wrapper(message: Message, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("⛔️ Эта команда доступна только администраторам.")
            return
        return await func(message)
    return wrapper


@router.message(Command("stats"))
@admin_only
async def cmd_stats(message: Message):
    """Команда /stats - статистика"""
    async for session in get_session():
        analytics = SurveyAnalytics(session)
        stats_text = await analytics.generate_stats_text()
        await message.answer(stats_text, parse_mode="Markdown")


@router.message(Command("detailed_stats"))
@admin_only
async def cmd_detailed_stats(message: Message):
    """Команда /detailed_stats - детальная статистика по всем вопросам"""
    await message.answer("⏳ Генерирую детальную статистику...")
    
    async for session in get_session():
        analytics = SurveyAnalytics(session)
        detailed_stats = await analytics.generate_detailed_stats()
        
        # Отправляем статистику (может быть длинной, разбиваем если нужно)
        if len(detailed_stats) > 4096:
            # Разбиваем на части
            parts = [detailed_stats[i:i+4096] for i in range(0, len(detailed_stats), 4096)]
            for part in parts:
                await message.answer(part, parse_mode="Markdown")
        else:
            await message.answer(detailed_stats, parse_mode="Markdown")


@router.message(Command("export"))
@admin_only
async def cmd_export(message: Message):
    """Команда /export - экспорт в CSV"""
    await message.answer("⏳ Подготавливаю экспорт...")
    
    async for session in get_session():
        analytics = SurveyAnalytics(session)
        data = await analytics.export_to_csv_data()
        
        if not data:
            await message.answer("Нет данных для экспорта.")
            return
        
        # Создаём директорию exports если её нет
        os.makedirs("exports", exist_ok=True)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"exports/responses_{timestamp}.csv"
        
        # Формируем заголовки для CSV
        # Начальные вопросы Q1-Q6
        fieldnames = ["user_id", "wave_id", "completed_at"]
        fieldnames += [f"Q{i}" for i in range(1, 7)]
        # Языковые вопросы LQ1-LQ10
        fieldnames += [f"LQ{i}" for i in range(1, 11)]
        
        # Записываем CSV
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        # Отправляем файл
        document = FSInputFile(filename)
        await message.answer_document(
            document=document,
            caption=f"📊 Экспорт данных ({len(data)} респондентов)\n"
                   f"Начальные вопросы: Q1-Q6\n"
                   f"Языковые вопросы: LQ1-LQ10"
        )


@router.message(Command("reset_wave"))
@admin_only
async def cmd_reset_wave(message: Message):
    """Команда /reset_wave - начать новую волну опроса"""
    # Генерируем ID новой волны
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    new_wave_id = f"wave_{timestamp}"
    
    await message.answer(
        f"🔄 Новая волна опроса: `{new_wave_id}`\n\n"
        f"Новые респонденты будут относиться к этой волне.",
        parse_mode="Markdown"
    )


@router.message(Command("admin"))
@admin_only
async def cmd_admin_help(message: Message):
    """Команда /admin - справка для админов"""
    help_text = """
🔧 Команды администратора

📊 `/stats` — краткая статистика по опросу
📈 `/detailed_stats` — детальная статистика по всем вопросам
💾 `/export` — экспорт данных в CSV
🔄 `/reset_wave` — начать новую волну опроса

Структура опроса:
• Первый этап: Q1-Q6 (определение типа буллинга)
• Второй этап: LQ1-LQ10 (языковой буллинг)

Вы можете использовать эти команды для мониторинга и анализа результатов исследования.
"""
    await message.answer(help_text, parse_mode="Markdown")

