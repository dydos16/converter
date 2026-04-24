"""
Единый менеджер установки всех зависимостей
"""
import sys
import subprocess
from pathlib import Path
from typing import Optional, Callable
from loguru import logger

from src.utils.dependency_checker import DependencyChecker
from src.utils.libreoffice_utils import LibreOfficeUtils


class InstallManager:
    """Менеджер для установки всех зависимостей"""

    def __init__(self):
        self.checker = DependencyChecker()
        self.libreoffice_utils = LibreOfficeUtils()

    def install_python_packages(
            self,
            progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """
        Устанавливает Python пакеты из requirements.txt

        Args:
            progress_callback: Callback для обновления прогресса (current, total, package)

        Returns:
            bool: True если установка успешна
        """
        req_file = Path(__file__).parent.parent.parent / "requirements.txt"
        if not req_file.exists():
            logger.error("requirements.txt не найден")
            return False

        # Проверяем, какие пакеты уже установлены
        _, missing = self.checker.check_python_packages()

        if not missing:
            logger.info("Все Python пакеты уже установлены")
            return True

        logger.info(f"Установка {len(missing)} пакетов...")

        # Определяем команду для установки
        if sys.platform == 'win32':
            cmd = [sys.executable, '-m', 'pip', 'install', '-r', str(req_file)]
        else:
            cmd = [sys.executable, '-m', 'pip', 'install', '--break-system-packages', '-r', str(req_file)]

        try:
            if progress_callback:
                progress_callback(0, len(missing), "Начало установки")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for i, line in enumerate(process.stdout):
                if 'Collecting' in line or 'Downloading' in line:
                    if progress_callback:
                        progress_callback(i, len(missing), line.strip())

            process.wait()

            if process.returncode == 0:
                logger.success("Все Python пакеты установлены")
                if progress_callback:
                    progress_callback(len(missing), len(missing), "Готово")
                return True
            else:
                logger.error("Ошибка установки Python пакетов")
                return False

        except Exception as e:
            logger.exception(f"Ошибка установки: {e}")
            return False

    def install_libreoffice(
            self,
            progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """
        Устанавливает LibreOffice (показывает инструкции)

        Args:
            progress_callback: Callback для обновления прогресса

        Returns:
            bool: True если LibreOffice уже установлен
        """
        if self.libreoffice_utils.is_installed():
            logger.info("LibreOffice уже установлен")
            return True

        if progress_callback:
            progress_callback(0, 100, "LibreOffice не найден")

        # Показываем инструкцию по установке
        instructions = self.libreoffice_utils.get_install_instructions()
        print(instructions)

        if progress_callback:
            progress_callback(100, 100, "Требуется ручная установка")

        return False

    def install_all(
            self,
            progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """
        Устанавливает все зависимости

        Args:
            progress_callback: Callback для обновления прогресса

        Returns:
            bool: True если все зависимости установлены успешно
        """
        # Сначала Python пакеты
        if progress_callback:
            progress_callback(0, 2, "Установка Python пакетов...")

        if not self.install_python_packages(progress_callback):
            logger.error("Не удалось установить Python пакеты")
            return False

        # Затем LibreOffice
        if progress_callback:
            progress_callback(1, 2, "Проверка LibreOffice...")

        if not self.install_libreoffice(progress_callback):
            # Не критично, можно работать без LibreOffice
            logger.warning("LibreOffice не установлен - некоторые функции недоступны")

        if progress_callback:
            progress_callback(2, 2, "Готово")

        return True