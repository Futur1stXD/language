"""Главный файл бота"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from utils.config import BOT_TOKEN
from models import init_db
from handlers import common_router, survey_router, admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    # Инициализация БД
    logger.info("Инициализация базы данных...")
    await init_db()
    
    # Создание бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация роутеров
    dp.include_router(common_router)
    dp.include_router(survey_router)
    dp.include_router(admin_router)
    
    logger.info("Бот запущен и готов к работе!")
    
    try:
        # Запуск поллинга
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
