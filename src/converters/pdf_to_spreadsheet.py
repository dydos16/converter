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
            import pdfplumber

            self._update_status("Извлечение текста...")

            all_text = []
            with pdfplumber.open(str(input_path)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
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
        """Сохраняет список строк (lists of str) в xlsx/xls/csv."""
        try:
            if output_ext == 'csv':
                import csv
                with open(output_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    for row in rows:
                        writer.writerow(row)
                return True

            if output_ext in ('xlsx', 'xls'):
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                for row in rows:
                    ws.append(row)

                # openpyxl не умеет .xls — сначала пишем xlsx, затем конвертируем через LibreOffice
                if output_ext == 'xls':
                    tmp_xlsx = output_path.with_suffix('.xlsx')
                    wb.save(str(tmp_xlsx))
                    return self._convert_xlsx_to_xls(tmp_xlsx, output_path)

                wb.save(str(output_path))
                return True

            # Неизвестный формат — xlsx по умолчанию
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

    def _convert_xlsx_to_xls(self, xlsx_path: Path, xls_path: Path) -> bool:
        """Конвертирует xlsx в xls через LibreOffice."""
        try:
            import subprocess
            from src.core.libreoffice_manager import LibreOfficeManager
            lo_manager = LibreOfficeManager()
            soffice = lo_manager.get_soffice_path() or lo_manager._find_soffice()
            if not soffice:
                logger.error("LibreOffice не найден для конвертации xlsx->xls")
                return False

            user_inst = lo_manager._get_user_profile_path().replace('file://', '-env:UserInstallation=file://')

            cmd = [
                str(soffice),
                user_inst,
                '--headless', '--invisible', '--nocrashreport',
                '--nofirststartwizard', '--nologo', '--norestore',
                '--convert-to', 'xls',
                '--outdir', str(xls_path.parent),
                str(xlsx_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            expected = xls_path.parent / f"{xlsx_path.stem}.xls"
            if expected.exists():
                if expected != xls_path:
                    expected.rename(xls_path)
                return True
            logger.error(f"xls не создан: {result.stderr[:200]}")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации xlsx->xls: {e}")
            return False
