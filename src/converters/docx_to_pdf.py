"""
DOCX to PDF - через LibreOffice с ленивой загрузкой
"""
from pathlib import Path
from .base import BaseConverter
from src.core.libreoffice_manager import LibreOfficeManager
from loguru import logger


class DocxToPdfConverter(BaseConverter):
    """Конвертер Word документов в PDF"""

    def __init__(self):
        super().__init__()
        self.lo_manager = LibreOfficeManager()

    def get_input_formats(self):
        return ['docx', 'doc']

    def get_output_formats(self):
        return ['pdf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Проверка LibreOffice...")
            self._update_progress(10)

            # Проверяем наличие LibreOffice
            if not self.lo_manager.is_available():
                self._update_status("LibreOffice не найден")
                self._handle_error("LibreOffice не установлен. Конвертация будет доступна после установки.")
                return False

            self._update_status(f"Конвертация {input_path.name} в PDF...")
            self._update_progress(30)

            # Используем единый метод конвертации
            success = self.lo_manager.convert(
                input_path,
                output_path,
                progress_callback=self._update_progress
            )

            if success:
                self._update_status("Готово!")
                return True
            else:
                self._handle_error("Ошибка конвертации")
                return False

        except Exception as e:
            self._handle_error(str(e))
            logger.exception("Ошибка конвертации")
            return False