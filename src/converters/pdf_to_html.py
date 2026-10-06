"""
PDF to HTML - конвертация PDF в HTML
"""
import html
from pathlib import Path
from .base import BaseConverter
from .pdf_text import page_text
from loguru import logger


class PdfToHtmlConverter(BaseConverter):
    """Конвертер PDF в HTML"""

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
        return ['html']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        if not self._require_text_layer(input_path):
            return False
        try:
            self._update_status("Конвертация PDF в HTML...")
            self._update_progress(10)

            if not self.pymupdf_available:
                self._handle_error("PyMuPDF не установлен. Установите: pip install PyMuPDF")
                return False

            import fitz

            self._update_progress(30)

            doc = fitz.open(str(input_path))

            html_content = []
            html_content.append('<!DOCTYPE html>')
            html_content.append('<html>')
            html_content.append('<head>')
            html_content.append('<meta charset="UTF-8">')
            html_content.append('<title>' + html.escape(input_path.stem) + '</title>')
            html_content.append('<style>')
            html_content.append('body { font-family: Arial, sans-serif; margin: 40px; }')
            html_content.append('.page { margin-bottom: 40px; border-bottom: 1px solid #ccc; }')
            html_content.append('.page-number { color: #666; font-size: 12px; margin-top: 20px; }')
            html_content.append('</style>')
            html_content.append('</head>')
            html_content.append('<body>')

            for page_num in range(len(doc)):
                self._update_progress(30 + int((page_num / len(doc)) * 60))

                page = doc[page_num]
                text = page_text(page)

                html_content.append(f'<div class="page">')
                html_content.append(f'<h2>Page {page_num + 1}</h2>')
                html_content.append(f'<div class="content">')
                # «<», «&» из PDF — текст, а не разметка: иначе «a < b» ломает страницу, а <script> из PDF исполнится
                html_content.append(html.escape(text).replace('\n', '<br>'))
                html_content.append(f'</div>')
                html_content.append(f'<div class="page-number">Page {page_num + 1}</div>')
                html_content.append(f'</div>')

            html_content.append('</body>')
            html_content.append('</html>')

            doc.close()

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(html_content))

            self._update_progress(100)
            self._update_status("Конвертация завершена!")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации PDF в HTML")
            return False