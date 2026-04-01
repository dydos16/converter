# src/utils/libreoffice_utils.py
"""
Утилиты для работы с LibreOffice
"""
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Callable
import logging

# Настройка логгера
logger = logging.getLogger(__name__)


class LibreOfficeUtils:
    """Класс для работы с LibreOffice"""

    @staticmethod
    def get_project_root() -> Path:
        """Возвращает корневую директорию проекта"""
        # Если запущено как скрипт
        if getattr(sys, 'frozen', False):
            # Запущено как собранное приложение
            return Path(sys.executable).parent
        else:
            # Запущено как скрипт
            return Path(__file__).parent.parent.parent

    @staticmethod
    def find_libreoffice() -> Optional[Path]:
        """Находит путь к исполняемому файлу LibreOffice"""
        paths = []

        if sys.platform == 'win32':  # Windows
            # 1. Встроенная в проект версия (приоритет)
            project_root = LibreOfficeUtils.get_project_root()
            paths.append(
                project_root / "resources" / "libreoffice" / "windows" /
                "LibreOffice" / "program" / "soffice.exe"
            )
            paths.append(
                project_root / "resources" / "libreoffice" / "windows" /
                "extract" / "PFiles" / "LibreOffice" / "program" / "soffice.exe"
            )

            # 2. Системные установки
            paths.extend([
                Path(r'C:\Program Files\LibreOffice\program\soffice.exe'),
                Path(r'C:\Program Files (x86)\LibreOffice\program\soffice.exe'),
                Path(r'C:\Program Files\LibreOffice\program\soffice.bin'),
            ])

        elif sys.platform == 'darwin':  # macOS
            project_root = LibreOfficeUtils.get_project_root()
            paths.append(
                project_root / "resources" / "libreoffice" / "macos" /
                "LibreOffice.app" / "Contents" / "MacOS" / "soffice"
            )
            paths.extend([
                Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
                Path('/Applications/LibreOffice.app/Contents/MacOS/libreoffice'),
                Path('/usr/local/bin/soffice'),
            ])

        else:  # Linux
            project_root = LibreOfficeUtils.get_project_root()
            paths.append(
                project_root / "resources" / "libreoffice" / "linux" /
                "program" / "soffice"
            )
            paths.extend([
                Path('/usr/bin/libreoffice'),
                Path('/usr/bin/soffice'),
                Path('/opt/libreoffice/program/soffice'),
                Path('/opt/libreoffice7.6/program/soffice'),
            ])

        # Проверяем все пути
        for path in paths:
            if path and path.exists():
                logger.info(f"LibreOffice найден: {path}")
                return path

        # Проверяем в PATH
        soffice = shutil.which('soffice') or shutil.which('libreoffice')
        if soffice:
            logger.info(f"LibreOffice найден в PATH: {soffice}")
            return Path(soffice)

        logger.warning("LibreOffice не найден")
        return None

    @staticmethod
    def is_installed() -> bool:
        """Проверяет, установлен ли LibreOffice"""
        return LibreOfficeUtils.find_libreoffice() is not None

    @staticmethod
    def get_install_instructions() -> str:
        """Возвращает инструкцию по установке LibreOffice"""
        if sys.platform == 'darwin':
            return """
╔══════════════════════════════════════════════════════════════╗
║          LibreOffice не найден!                              ║
╚══════════════════════════════════════════════════════════════╝

Для работы с документами Word и PowerPoint необходимо установить LibreOffice.

📦 Установка через Homebrew (рекомендуется):
    brew install --cask libreoffice

🌐 Или скачайте с официального сайта:
    https://www.libreoffice.org/download/

🔄 После установки перезапустите приложение.
"""
        elif sys.platform == 'win32':
            return """
╔══════════════════════════════════════════════════════════════╗
║          LibreOffice не найден!                              ║
╚══════════════════════════════════════════════════════════════╝

Для работы с документами Word и PowerPoint необходимо установить LibreOffice.

🌐 Скачайте установщик с официального сайта:
    https://www.libreoffice.org/download/

📦 Запустите скачанный файл и следуйте инструкциям установщика.

🔄 После установки перезапустите приложение.
"""
        else:
            return """
╔══════════════════════════════════════════════════════════════╗
║          LibreOffice не найден!                              ║
╚══════════════════════════════════════════════════════════════╝

Для работы с документами Word и PowerPoint необходимо установить LibreOffice.

📦 Установка через пакетный менеджер:

    Ubuntu/Debian:
        sudo apt update && sudo apt install -y libreoffice

    Fedora/RHEL:
        sudo dnf install libreoffice

    Arch Linux:
        sudo pacman -S libreoffice-fresh

🔄 После установки перезапустите приложение.
"""

    @staticmethod
    def convert_to_pdf(
            input_path: Path,
            output_path: Path,
            progress_callback: Optional[Callable[[int], None]] = None
    ) -> bool:
        """Конвертирует документ в PDF используя LibreOffice"""
        try:
            if progress_callback:
                progress_callback(10)

            # Находим LibreOffice
            soffice_path = LibreOfficeUtils.find_libreoffice()
            if not soffice_path:
                logger.error("LibreOffice не найден")
                return False

            logger.info(f"Используется LibreOffice: {soffice_path}")

            if progress_callback:
                progress_callback(30)

            # Формируем команду
            cmd = [
                str(soffice_path),
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(output_path.parent),
                str(input_path)
            ]

            logger.info(f"Запуск конвертации: {' '.join(cmd)}")

            if progress_callback:
                progress_callback(50)

            # Запускаем процесс
            use_shell = sys.platform == 'win32'
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                shell=use_shell
            )

            if progress_callback:
                progress_callback(70)

            # Проверяем результат
            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"

            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)

                if output_path.exists() and output_path.stat().st_size > 0:
                    if progress_callback:
                        progress_callback(100)
                    logger.info(f"PDF создан: {output_path}")
                    return True
                else:
                    logger.error("PDF файл поврежден")
                    return False

            # Ищем любой PDF в папке
            for pdf_file in output_path.parent.glob("*.pdf"):
                if pdf_file.stat().st_size > 0:
                    if pdf_file != output_path:
                        pdf_file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    logger.info(f"PDF создан: {output_path}")
                    return True

            error_msg = result.stderr if result.stderr else "PDF не создан"
            logger.error(f"Ошибка конвертации: {error_msg}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации (5 минут)")
            return False
        except Exception as e:
            logger.exception(f"Ошибка конвертации: {e}")
            return False


# Экспортируем класс для обратной совместимости
__all__ = ['LibreOfficeUtils']