"""
DOCX to PDF - через LibreOffice
"""
from pathlib import Path
from .base import BaseConverter
from src.utils.libreoffice_utils import LibreOfficeUtils
from loguru import logger


class DocxToPdfConverter(BaseConverter):
    """Конвертер Word документов в PDF"""

    def __init__(self):
        super().__init__()
        self.lo_utils = LibreOfficeUtils()

    def get_input_formats(self):
        return ['docx', 'doc']

    def get_output_formats(self):
        return ['pdf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Проверка LibreOffice...")
            self._update_progress(10)

            # Проверяем наличие LibreOffice
            if not self.lo_utils.is_installed():
                self._update_status("LibreOffice не найден")
                self._handle_error(self.lo_utils.get_install_instructions())
                return False

            self._update_status(f"Конвертация {input_path.name} в PDF...")
            self._update_progress(30)

            # Используем единый метод конвертации
            success = self.lo_utils.convert_to_pdf(
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