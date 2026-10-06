"""
PDF to XML - извлечение данных из PDF в XML
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from .base import BaseConverter
from .pdf_text import page_text
from loguru import logger


class PdfToXmlConverter(BaseConverter):
    """Конвертер PDF в XML"""

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
        return ['xml']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        if not self._require_text_layer(input_path):
            return False
        try:
            self._update_status("Конвертация PDF в XML...")
            self._update_progress(10)

            if not self.pymupdf_available:
                self._handle_error("PyMuPDF не установлен. Установите: pip install PyMuPDF")
                return False

            import fitz

            self._update_progress(30)

            doc = fitz.open(str(input_path))

            # Создаем корневой элемент
            root = ET.Element("document")
            root.set("filename", input_path.name)

            # Добавляем метаданные
            if doc.metadata:
                meta = ET.SubElement(root, "metadata")
                for key, value in doc.metadata.items():
                    elem = ET.SubElement(meta, key)
                    elem.text = str(value)

            # Добавляем страницы
            pages = ET.SubElement(root, "pages")

            for page_num in range(len(doc)):
                self._update_progress(30 + int((page_num / len(doc)) * 60))

                page = doc[page_num]
                page_elem = ET.SubElement(pages, "page")
                page_elem.set("number", str(page_num + 1))
                page_elem.set("width", str(page.rect.width))
                page_elem.set("height", str(page.rect.height))

                text_elem = ET.SubElement(page_elem, "text")
                text_elem.text = page_text(page)

            doc.close()

            # Сохраняем XML
            tree = ET.ElementTree(root)
            tree.write(str(output_path), encoding='utf-8', xml_declaration=True)

            self._update_progress(100)
            self._update_status("Конвертация завершена!")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации PDF в XML")
            return False