#!/usr/bin/env python3
"""
Простой запуск приложения
"""
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем функцию main из src.main
from src.main import main

if __name__ == '__main__':
    main()