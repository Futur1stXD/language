"""Инициализация пакета tests"""
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
