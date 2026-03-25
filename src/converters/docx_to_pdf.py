"""
DOCX to PDF - через python-docx2pdf
"""
from pathlib import Path
from docx2pdf import convert
from .base import BaseConverter
from loguru import logger


class DocxToPdfConverter(BaseConverter):

    def get_input_formats(self):
        return ['docx', 'doc']

    def get_output_formats(self):
        return ['pdf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Конвертация...")
            self._update_progress(50)

            # Конвертируем
            convert(str(input_path), str(output_path))

            self._update_progress(100)
            self._update_status("Готово!")
            return True

        except Exception as e:
            self._handle_error(str(e))
            return False