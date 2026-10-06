"""
PDF to TXT - извлечение текста из PDF (у скана — распознанного OCR)
"""
from pathlib import Path

import fitz
from loguru import logger

from .base import BaseConverter
from .pdf_text import page_text


class PdfToTextConverter(BaseConverter):
    """Конвертер PDF в TXT - извлекает текст"""

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['txt']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        if not self._require_text_layer(input_path):
            return False
        try:
            self._update_status("Извлечение текста из PDF...")
            self._update_progress(10)
            parts = []
            with fitz.open(str(input_path)) as doc:
                for page_num, page in enumerate(doc):
                    self._update_progress(10 + int(page_num / len(doc) * 80))
                    text = page_text(page)
                    if text.strip():
                        parts += [f"--- Страница {page_num + 1} ---", text, "\n"]

            self._update_status("Сохранение текста...")
            output_path.write_text('\n'.join(parts), encoding='utf-8')
            self._update_progress(100)
            self._update_status("Текст успешно извлечён!")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка извлечения текста из PDF: {str(e)}")
            logger.exception("Ошибка конвертации PDF в TXT")
            return False
