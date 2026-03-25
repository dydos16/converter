"""
Вспомогательные функции для приложения
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import subprocess
from loguru import logger

# Пытаемся импортировать magic (не критично, если не установлен)
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logger.warning("python-magic не установлен, определение MIME-типов будет ограничено")

def find_libreoffice() -> Optional[Path]:
    """
    Находит путь к исполняемому файлу LibreOffice

    Returns:
        Path или None, если LibreOffice не найден
    """
    # Список возможных путей для разных ОС
    possible_paths = []

    if sys.platform == 'win32':
        # Windows
        possible_paths = [
            r'C:\Program Files\LibreOffice\program\soffice.exe',
            r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        ]
    elif sys.platform == 'darwin':
        # macOS
        possible_paths = [
            '/Applications/LibreOffice.app/Contents/MacOS/soffice',
        ]
    else:
        # Linux
        possible_paths = [
            '/usr/bin/libreoffice',
            '/usr/bin/soffice',
            '/opt/libreoffice/program/soffice',
        ]

    # Проверяем пути
    for path in possible_paths:
        p = Path(path)
        if p.exists():
            return p

    # Проверяем в PATH
    libreoffice = shutil.which('libreoffice') or shutil.which('soffice')
    if libreoffice:
        return Path(libreoffice)

    return None


def create_temp_dir() -> Path:
    """Создает временную директорию"""
    temp_dir = Path(tempfile.mkdtemp(prefix='converter_'))
    logger.debug(f"Создана временная директория: {temp_dir}")
    return temp_dir


def cleanup_temp_dir(temp_dir: Path):
    """Удаляет временную директорию"""
    try:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.debug(f"Удалена временная директория: {temp_dir}")
    except Exception as e:
        logger.warning(f"Не удалось удалить временную директорию {temp_dir}: {e}")


def get_file_size_str(path: Path) -> str:
    """Возвращает размер файла в человекочитаемом формате"""
    size = path.stat().st_size

    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0

    return f"{size:.1f} TB"


def ensure_output_directory(output_path: Path) -> bool:
    """Создает директорию для выходного файла, если её нет"""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Не удалось создать директорию {output_path.parent}: {e}")
        return False


def get_unique_filename(path: Path) -> Path:
    """
    Возвращает уникальное имя файла, если файл уже существует

    Например: file.pdf -> file (1).pdf
    """
    if not path.exists():
        return path

    counter = 1
    stem = path.stem
    suffix = path.suffix

    while True:
        new_path = path.parent / f"{stem} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def validate_file(file_path: Path, allowed_extensions: list[str]) -> tuple[bool, str]:
    """
    Проверяет файл на валидность

    Returns:
        tuple[bool, str]: (валиден, сообщение_об_ошибке)
    """
    if not file_path.exists():
        return False, "Файл не существует"

    if not file_path.is_file():
        return False, "Путь указывает не на файл"

    ext = file_path.suffix.lower().lstrip('.')
    if ext not in allowed_extensions:
        return False, f"Формат {ext} не поддерживается"

    # Проверяем размер (максимум 500MB)
    max_size = 500 * 1024 * 1024
    if file_path.stat().st_size > max_size:
        return False, f"Файл слишком большой (максимум 500MB)"

    return True, "OK"


def get_file_icon(extension: str) -> str:
    """Возвращает эмодзи или иконку для типа файла"""
    icons = {
        'pdf': '📄',
        'docx': '📝',
        'doc': '📝',
        'txt': '📃',
        'jpg': '🖼️',
        'jpeg': '🖼️',
        'png': '🖼️',
        'gif': '🖼️',
        'webp': '🖼️',
        'bmp': '🖼️',
        'xlsx': '📊',
        'xls': '📊',
        'csv': '📊',
        'zip': '📦',
        'rar': '📦',
    }

    return icons.get(extension.lower(), '📁')