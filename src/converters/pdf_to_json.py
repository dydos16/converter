"""
PDF to JSON - извлечение данных из PDF
"""
import json
from pathlib import Path
from .base import BaseConverter
from .pdf_text import page_text
from loguru import logger


class PdfToJsonConverter(BaseConverter):
    """Конвертер PDF в JSON"""

    def __init__(self):
        super().__init__()
        self.pymupdf_available = self._check_pymupdf()

    def _check_pymupdf(self):
        try:
            import fitz
            return True
        except ImportError:
            return False

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['json']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        if not self._require_text_layer(input_path):
            return False
        try:
            self._update_status("Извлечение данных из PDF...")
            self._update_progress(10)

            if not self.pymupdf_available:
                self._handle_error("PyMuPDF не установлен. Установите: pip install PyMuPDF")
                return False

            import fitz

            self._update_progress(30)

            doc = fitz.open(str(input_path))

            data = {
                "filename": input_path.name,
                "pages": [],
                "metadata": doc.metadata if doc.metadata else {}
            }

            for page_num in range(len(doc)):
                self._update_progress(30 + int((page_num / len(doc)) * 60))

                page = doc[page_num]

                page_data = {
                    "page_number": page_num + 1,
                    "text": page_text(page),
                    "words": page.get_text("words"),
                    "size": [page.rect.width, page.rect.height]
                }

                data["pages"].append(page_data)

            doc.close()

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._update_progress(100)
            self._update_status("Конвертация завершена!")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации PDF в JSON")
            return False