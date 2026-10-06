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

    def _require_text_layer(self, pdf_path: Path) -> bool:
        """У скана нет текстового слоя: вместо пустого файла — понятная ошибка."""
        import fitz
        with fitz.open(pdf_path) as doc:
            if any(page.get_text().strip() for page in doc):
                return True
        self._handle_error("В PDF нет текста — похоже, это скан. Распознавание текста (OCR) не поддерживается: "
                           "сконвертируйте его в DOCX или картинки.")
        return False