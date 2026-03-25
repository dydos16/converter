"""
Проверка зависимостей
"""
import shutil
import sys
from pathlib import Path
from loguru import logger


def check_libreoffice():
    """Проверяет наличие LibreOffice"""
    paths = []

    if sys.platform == 'darwin':  # macOS
        paths = [
            '/Applications/LibreOffice.app/Contents/MacOS/soffice',
            '/Applications/LibreOffice.app/Contents/MacOS/libreoffice',
        ]
    elif sys.platform == 'win32':  # Windows
        paths = [
            r'C:\Program Files\LibreOffice\program\soffice.exe',
            r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        ]
    else:  # Linux
        paths = [
            '/usr/bin/libreoffice',
            '/usr/bin/soffice',
        ]

    # Проверяем пути
    for path in paths:
        if Path(path).exists():
            logger.info(f"LibreOffice найден: {path}")
            return True

    # Проверяем в PATH
    if shutil.which('soffice') or shutil.which('libreoffice'):
        logger.info("LibreOffice найден в PATH")
        return True

    logger.warning("LibreOffice не найден!")
    return False


def get_libreoffice_install_instructions():
    """Возвращает инструкцию по установке LibreOffice"""
    if sys.platform == 'darwin':
        return """
LibreOffice не найден. Для конвертации DOCX в PDF необходимо установить LibreOffice.

Установите через Homebrew:
  brew install --cask libreoffice

Или скачайте с официального сайта:
  https://www.libreoffice.org/download/
        """
    elif sys.platform == 'win32':
        return """
LibreOffice не найден. Для конвертации DOCX в PDF необходимо установить LibreOffice.

Скачайте с официального сайта:
  https://www.libreoffice.org/download/
        """
    else:
        return """
LibreOffice не найден. Для конвертации DOCX в PDF необходимо установить LibreOffice.

Установите через пакетный менеджер:
  sudo apt install libreoffice     (Ubuntu/Debian)
  sudo yum install libreoffice     (CentOS/RHEL)
  sudo pacman -S libreoffice-fresh (Arch)
        """