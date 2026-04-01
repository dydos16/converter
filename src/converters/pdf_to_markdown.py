"""
PDF to Markdown - конвертация PDF в Markdown
"""
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfToMarkdownConverter(BaseConverter):
    """Конвертер PDF в Markdown"""

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
        return ['md']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Конвертация PDF в Markdown...")
            self._update_progress(10)

            if not self.pymupdf_available:
                self._handle_error("PyMuPDF не установлен. Установите: pip install PyMuPDF")
                return False

            import fitz

            self._update_progress(30)

            doc = fitz.open(str(input_path))

            md_content = []
            md_content.append(f"# {input_path.stem}")
            md_content.append("")

            for page_num in range(len(doc)):
                self._update_progress(30 + int((page_num / len(doc)) * 60))

                page = doc[page_num]
                text = page.get_text()

                md_content.append(f"## Page {page_num + 1}")
                md_content.append("")
                md_content.append(text)
                md_content.append("")
                md_content.append("---")
                md_content.append("")

            doc.close()

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(md_content))

            self._update_progress(100)
            self._update_status("Конвертация завершена!")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации PDF в Markdown")
            return False