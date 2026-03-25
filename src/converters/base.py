from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Callable
from loguru import logger


class BaseConverter(ABC):
    """Базовый класс для конвертеров"""

    def __init__(self):
        self.progress_callback: Optional[Callable[[int], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None

    @abstractmethod
    def convert(self, input_path: Path, output_path: Path) -> bool:
        pass

    @abstractmethod
    def get_input_formats(self) -> list[str]:
        pass

    @abstractmethod
    def get_output_formats(self) -> list[str]:
        pass

    def _update_progress(self, percent: int):
        if self.progress_callback:
            self.progress_callback(min(max(percent, 0), 100))

    def _update_status(self, status: str):
        if self.status_callback:
            self.status_callback(status)
        logger.info(status)

    def _handle_error(self, error: str):
        if self.error_callback:
            self.error_callback(error)
        logger.error(error)