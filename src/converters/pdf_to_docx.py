"""
PDF to DOCX - использует pdf2docx для точной конвертации
"""
import sys
import subprocess
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfToDocxConverter(BaseConverter):
    """Конвертер PDF в DOCX с сохранением форматирования"""

    def __init__(self):
        super().__init__()
        self.pdf2docx_available = self._check_pdf2docx()
        self.extract_text_only = False  # По умолчанию сохраняем форматирование

    def _check_pdf2docx(self):
        """Проверяет доступность pdf2docx"""
        try:
            import pdf2docx
            return True
        except ImportError:
            return False

    def _install_pdf2docx(self):
        """Устанавливает pdf2docx через pip"""
        try:
            self._update_status("Установка pdf2docx...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'pdf2docx', '--quiet'
            ])
            self.pdf2docx_available = True
            self._update_status("pdf2docx успешно установлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки pdf2docx: {e}")
            return False

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['docx']

    def set_extract_text_only(self, text_only: bool):
        """Устанавливает режим извлечения только текста без форматирования"""
        self.extract_text_only = text_only

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Подготовка к конвертации PDF в DOCX...")
            self._update_progress(10)

            # Если pdf2docx недоступен — сразу извлекаем только текст (лёгкий режим)
            if not self.pdf2docx_available:
                self._update_status("pdf2docx недоступен, извлекаем только текст...")
                return self._convert_text_only(input_path, output_path)

            self._update_progress(30)

            if self.extract_text_only:
                # Режим только текст
                return self._convert_text_only(input_path, output_path)
            else:
                # Полная конвертация с форматированием
                return self._convert_with_formatting(input_path, output_path)

        except Exception as e:
            self._handle_error(f"Ошибка конвертации PDF в DOCX: {str(e)}")
            logger.exception("Ошибка конвертации PDF в DOCX")
            return False

    def _convert_with_formatting(self, input_path: Path, output_path: Path) -> bool:
        """Конвертирует PDF в DOCX с сохранением форматирования"""
        try:
            from pdf2docx import Converter

            self._update_status("Конвертация с сохранением форматирования...")
            self._update_progress(40)

            # Создаем конвертер
            cv = Converter(str(input_path))

            self._update_status("Извлечение содержимого...")
            self._update_progress(60)

            # Конвертируем все страницы
            cv.convert(
                str(output_path),
                start=0,
                end=None,
                pages=None  # Все страницы
            )

            cv.close()

            self._update_progress(100)
            self._update_status("Конвертация PDF в DOCX успешно завершена!")

            return True

        except Exception as e:
            logger.error(f"Ошибка при конвертации с форматированием: {e}")
            # Если не получилось с форматированием, пробуем извлечь только текст
            self._update_status("Пробуем извлечь только текст...")
            return self._convert_text_only(input_path, output_path)

    def _convert_text_only(self, input_path: Path, output_path: Path) -> bool:
        """Извлекает только текст из PDF в DOCX"""
        try:
            import pdfplumber
            from docx import Document

            self._update_status("Извлечение текста из PDF...")
            self._update_progress(40)

            doc = Document()
            text_content = []

            with pdfplumber.open(str(input_path)) as pdf:
                total_pages = len(pdf.pages)

                for i, page in enumerate(pdf.pages):
                    self._update_progress(40 + int((i / total_pages) * 50))

                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)

            self._update_status("Создание DOCX документа...")
            self._update_progress(90)

            # Добавляем текст в документ
            for text in text_content:
                doc.add_paragraph(text)
                doc.add_paragraph()  # Пустая строка между страницами

            doc.save(str(output_path))

            self._update_progress(100)
            self._update_status("Текст успешно извлечен и сохранен!")

            return True

        except ImportError:
            self._handle_error("Для извлечения текста установите pdfplumber: pip install pdfplumber")
            return False
        except Exception as e:
            self._handle_error(f"Ошибка извлечения текста: {str(e)}")
            return False