"""
PDF to Spreadsheet - извлечение таблиц из PDF.
Без pandas/numpy — экономит ~65 МБ в собранном приложении.
"""
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfToSpreadsheetConverter(BaseConverter):
    """Конвертер PDF в таблицы через PyMuPDF (без pandas)."""

    def __init__(self):
        super().__init__()
        self.table_strategy = 'auto'        # «Извлечение таблиц» в настройках: auto, lattice, stream

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
            import fitz
            from .pdf_text import page_text

            self._update_status("Извлечение таблиц из PDF...")
            self._update_progress(10)

            # lattice/auto — таблицы по линиям рамки; stream — без рамок, по выравниванию текста
            strategy = "text" if self.table_strategy == 'stream' else "lines"
            all_tables = []
            with fitz.open(str(input_path)) as pdf:
                for page_num, page in enumerate(pdf):
                    self._update_progress(10 + int(page_num / max(len(pdf), 1) * 70))
                    for table in page.find_tables(strategy=strategy).tables:
                        # Текст ячейки — по её области через page_text: pdfplumber на PDF со шрифтом Calibri
                        # (сделанных на Windows) выдавал «Отчё(cid:5)т» вместо «Отчёт»
                        rows = [[page_text(page, clip=cell).replace("\n", " ") if cell else "" for cell in row.cells]
                                for row in table.rows]
                        rows = [row for row in rows if any(cell.strip() for cell in row)]
                        if len(rows) > 1:
                            all_tables.append(rows)
                            self._update_status(f"Найдена таблица на странице {page_num + 1}")

            if not all_tables:
                self._update_status("Таблицы не найдены, извлекаем текст...")
                return self._extract_text_fallback(input_path, output_path)

            self._update_progress(80)
            # Несколько таблиц — подряд, с разделителями
            rows = []
            for i, table in enumerate(all_tables):
                if len(all_tables) > 1:
                    rows.append([f"=== Таблица {i + 1} ==="])
                rows += table
                if len(all_tables) > 1:
                    rows.append([""])

            if not self._save_rows(rows, output_path, output_path.suffix.lower().lstrip('.')):
                return False

            self._update_progress(100)
            self._update_status(f"Извлечено таблиц: {len(all_tables)}")
            return True

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
                from .spreadsheet_converter import excel_csv_delimiter
                with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:   # BOM — для русского Excel
                    writer = csv.writer(f, delimiter=excel_csv_delimiter())
                    for row in rows:
                        writer.writerow(row)
                return True

            # xlsx (xls приходит сюда уже как промежуточный xlsx — см. convert)
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            from .spreadsheet_converter import ILLEGAL_CHARACTERS_RE
            for row in rows:        # управляющие символы из «битых» шрифтов PDF Excel хранить не умеет
                ws.append([ILLEGAL_CHARACTERS_RE.sub("", c) if isinstance(c, str) else c for c in row])
            wb.save(str(output_path))
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения таблицы: {e}")
            return False
