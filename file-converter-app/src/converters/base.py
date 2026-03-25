"""
Базовый класс для всех конвертеров
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Callable
from loguru import logger


class BaseConverter(ABC):
    """Абстрактный базовый класс для конвертеров файлов"""

    def __init__(self):
        self.progress_callback: Optional[Callable[[int], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None

    @abstractmethod
    def convert(self, input_path: Path, output_path: Path) -> bool:
        """
        Выполняет конвертацию файла

        Args:
            input_path: Путь к исходному файлу
            output_path: Путь для сохранения результата

        Returns:
            bool: True если конвертация успешна
        """
        pass

    @abstractmethod
    def get_input_formats(self) -> list[str]:
        """Возвращает список поддерживаемых входных форматов"""
        pass

    @abstractmethod
    def get_output_formats(self) -> list[str]:
        """Возвращает список поддерживаемых выходных форматов"""
        pass

    def validate(self, input_path: Path, output_format: str) -> tuple[bool, str]:
        """
        Проверяет возможность конвертации

        Returns:
            tuple[bool, str]: (можно_конвертировать, сообщение_об_ошибке)
        """
        if not input_path.exists():
            return False, f"Файл не найден: {input_path}"

        input_ext = input_path.suffix.lower().lstrip('.')
        if input_ext not in self.get_input_formats():
            return False, f"Формат {input_ext} не поддерживается"

        if output_format.lower() not in self.get_output_formats():
            return False, f"Формат {output_format} не поддерживается"

        return True, "OK"

    def _update_progress(self, percent: int):
        """Обновляет прогресс конвертации"""
        if self.progress_callback:
            self.progress_callback(min(max(percent, 0), 100))
        logger.debug(f"Progress: {percent}%")

    def _update_status(self, status: str):
        """Обновляет статус конвертации"""
        if self.status_callback:
            self.status_callback(status)
        logger.info(status)

    def _handle_error(self, error: str):
        """Обрабатывает ошибку"""
        if self.error_callback:
            self.error_callback(error)
        logger.error(error)