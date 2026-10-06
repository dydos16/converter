"""
PDF to TXT - извлечение текста из PDF
"""
import sys
import subprocess
from pathlib import Path
from .base import BaseConverter
from .pdf_text import page_text
from loguru import logger


class PdfToTextConverter(BaseConverter):
    """Конвертер PDF в TXT - извлекает текст"""

    def __init__(self):
        super().__init__()
        self.pdfplumber_available = self._check_pdfplumber()
        self.pymupdf_available = self._check_pymupdf()

    def _check_pdfplumber(self):
        """Проверяет доступность pdfplumber"""
        try:
            import pdfplumber
            return True
        except ImportError:
            return False

    def _check_pymupdf(self):
        """Проверяет доступность PyMuPDF (fitz)"""
        try:
            import fitz
            return True
        except ImportError:
            return False

    def _install_pdfplumber(self):
        """Устанавливает pdfplumber"""
        try:
            self._update_status("Установка pdfplumber...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'pdfplumber', '--quiet'
            ])
            self.pdfplumber_available = True
            self._update_status("pdfplumber успешно установлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки pdfplumber: {e}")
            return False

    def _install_pymupdf(self):
        """Устанавливает PyMuPDF"""
        try:
            self._update_status("Установка PyMuPDF...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'PyMuPDF', '--quiet'
            ])
            self.pymupdf_available = True
            self._update_status("PyMuPDF успешно установлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки PyMuPDF: {e}")
            return False

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

            # Пробуем использовать PyMuPDF (быстрее)
            if self.pymupdf_available:
                return self._convert_with_pymupdf(input_path, output_path)

            # Если PyMuPDF нет, используем pdfplumber
            if not self.pdfplumber_available:
                if not self._install_pdfplumber():
                    self._handle_error("Не удалось установить библиотеки для извлечения текста")
                    return False

            return self._convert_with_pdfplumber(input_path, output_path)

        except Exception as e:
            self._handle_error(f"Ошибка извлечения текста из PDF: {str(e)}")
            logger.exception("Ошибка конвертации PDF в TXT")
            return False

    def _convert_with_pymupdf(self, input_path: Path, output_path: Path) -> bool:
        """Извлекает текст с помощью PyMuPDF (быстро)"""
        try:
            import fitz

            self._update_status("Используем PyMuPDF для быстрого извлечения...")
            self._update_progress(30)

            doc = fitz.open(str(input_path))
            total_pages = len(doc)

            text_content = []

            for page_num in range(total_pages):
                self._update_progress(30 + int((page_num / total_pages) * 60))

                page = doc[page_num]
                text = page_text(page)

                if text.strip():
                    text_content.append(f"--- Страница {page_num + 1} ---")
                    text_content.append(text)
                    text_content.append("\n")

            doc.close()

            self._update_progress(90)
            self._update_status("Сохранение текста...")

            # Сохраняем текст в файл
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(text_content))

            self._update_progress(100)
            self._update_status(f"Текст успешно извлечен! {total_pages} страниц")

            return True

        except Exception as e:
            logger.error(f"Ошибка в PyMuPDF: {e}")
            return False

    def _convert_with_pdfplumber(self, input_path: Path, output_path: Path) -> bool:
        """Извлекает текст с помощью pdfplumber (более точный)"""
        try:
            import pdfplumber

            self._update_status("Используем pdfplumber для точного извлечения...")
            self._update_progress(30)

            text_content = []

            with pdfplumber.open(str(input_path)) as pdf:
                total_pages = len(pdf.pages)

                for i, page in enumerate(pdf.pages):
                    self._update_progress(30 + int((i / total_pages) * 60))

                    page_text = page.extract_text()

                    if page_text:
                        text_content.append(f"--- Страница {i + 1} ---")
                        text_content.append(page_text)
                        text_content.append("\n")
                    else:
                        # Если текст не извлекся, пробуем извлечь таблицы
                        tables = page.extract_tables()
                        if tables:
                            text_content.append(f"--- Страница {i + 1} (таблицы) ---")
                            for table in tables:
                                for row in table:
                                    text_content.append(' | '.join(str(cell) for cell in row if cell))
                            text_content.append("\n")

            self._update_progress(90)
            self._update_status("Сохранение текста...")

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(text_content))

            self._update_progress(100)
            self._update_status(f"Текст успешно извлечен! {total_pages} страниц")

            return True

        except Exception as e:
            logger.error(f"Ошибка в pdfplumber: {e}")
            return False