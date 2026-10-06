"""
PDF to Spreadsheet - извлечение таблиц из PDF.
Без pandas/numpy — экономит ~65 МБ в собранном приложении.
"""
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfToSpreadsheetConverter(BaseConverter):
    """Конвертер PDF в таблицы через pdfplumber (без pandas)."""

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['xlsx', 'xls', 'csv']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        # xls писать сами не умеем (openpyxl — только xlsx): делаем XLSX и пересохраняем через LibreOffice
        if output_path.suffix.lower() == '.xls':
            from src.core.libreoffice_manager import LibreOfficeManager
            return LibreOfficeManager().convert_via(lambda xlsx: self.convert(input_path, xlsx), output_path, '.xlsx')
        if not self._require_text_layer(input_path):
            return False
        try:
            self._update_status("Извлечение таблиц из PDF...")
            self._update_progress(10)

            try:
                import pdfplumber

                self._update_status("Анализ PDF...")
                self._update_progress(30)

                all_tables = []

                with pdfplumber.open(str(input_path)) as pdf:
                    total_pages = len(pdf.pages)

                    for page_num, page in enumerate(pdf.pages):
                        self._update_progress(30 + int((page_num / max(total_pages, 1)) * 50))

                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                if table and len(table) > 1:
                                    cleaned = [row for row in table if any(cell and str(cell).strip() for cell in row)]
                                    if cleaned:
                                        all_tables.append(cleaned)
                                        self._update_status(f"Найдена таблица на странице {page_num + 1}")

                if not all_tables:
                    self._update_status("Таблицы не найдены, извлекаем текст...")
                    return self._extract_text_fallback(input_path, output_path)

                self._update_progress(80)
                output_ext = output_path.suffix.lower().lstrip('.')

                # Объединяем таблицы в список строк (с разделителями)
                rows = []
                for i, table in enumerate(all_tables):
                    if len(all_tables) > 1:
                        rows.append([f"=== Table {i + 1} ==="])
                    for row in table:
                        rows.append([str(c) if c is not None else "" for c in row])
                    if len(all_tables) > 1:
                        rows.append([""])

                if not self._save_rows(rows, output_path, output_ext):
                    return False

                self._update_progress(100)
                self._update_status(f"Извлечено {len(all_tables)} таблиц")
                return True

            except ImportError:
                self._handle_error(
                    "Установите необходимые библиотеки:\n\n"
                    "pip install pdfplumber openpyxl\n\n"
                    "Или используйте виртуальное окружение:\n"
                    "python3 -m venv venv\n"
                    "source venv/bin/activate\n"
                    "pip install pdfplumber openpyxl"
                )
                return False

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка извлечения таблиц из PDF")
            return False

    def _extract_text_fallback(self, input_path: Path, output_path: Path) -> bool:
        """Запасной вариант — извлечение текста."""
        try:
            import fitz
            from .pdf_text import page_text

            self._update_status("Извлечение текста...")

            all_text = []
            with fitz.open(str(input_path)) as pdf:
                for page_num, page in enumerate(pdf):
                    text = page_text(page)          # у скана — распознанный OCR
                    if text:
                        all_text.append(f"=== Page {page_num + 1} ===")
                        all_text.append(text)
                        all_text.append("")

            lines = []
            for line in '\n'.join(all_text).split('\n'):
                if line.strip():
                    lines.append([line.strip()])

            output_ext = output_path.suffix.lower().lstrip('.')

            if not self._save_rows(lines, output_path, output_ext):
                return False

            self._update_progress(100)
            self._update_status("Текст успешно извлечен")
            return True

        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return False

    def _save_rows(self, rows: list, output_path: Path, output_ext: str) -> bool:
        """Сохраняет список строк (lists of str) в xlsx/csv."""
        try:
            if output_ext == 'csv':
                import csv
                with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:   # BOM — для русского Excel
                    writer = csv.writer(f)
                    for row in rows:
                        writer.writerow(row)
                return True

            # xlsx (xls приходит сюда уже как промежуточный xlsx — см. convert)
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            for row in rows:
                ws.append(row)
            wb.save(str(output_path))
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения таблицы: {e}")
            return False
