"""Конфигурация бота"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env файле")

if not ADMIN_IDS:
    print("⚠️ Предупреждение: ADMIN_IDS не установлены. Админ-команды будут недоступны.")
