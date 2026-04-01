"""
PDF to Spreadsheet - извлечение таблиц из PDF
"""
import sys
import subprocess
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfToSpreadsheetConverter(BaseConverter):
    """Конвертер PDF в таблицы (XLSX, CSV)"""

    def __init__(self):
        super().__init__()
        self.camelot_available = self._check_camelot()

    def _check_camelot(self):
        try:
            import camelot
            return True
        except ImportError:
            return False

    def _install_camelot(self):
        try:
            self._update_status("Установка camelot-py...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'camelot-py[cv]', '--quiet'
            ])
            self.camelot_available = True
            return True
        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            return False

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['xlsx', 'xls', 'csv']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Извлечение таблиц из PDF...")
            self._update_progress(10)

            if not self.camelot_available:
                if not self._install_camelot():
                    self._handle_error(
                        "Не удалось установить camelot-py\n\n"
                        "Попробуйте установить вручную:\n"
                        "pip install camelot-py[cv]"
                    )
                    return False

            import camelot

            self._update_status("Поиск таблиц...")
            self._update_progress(30)

            # Извлекаем таблицы
            tables = camelot.read_pdf(str(input_path), pages='all', flavor='lattice')

            if len(tables) == 0:
                self._update_status("Пробуем другой метод извлечения...")
                tables = camelot.read_pdf(str(input_path), pages='all', flavor='stream')

            if len(tables) == 0:
                self._handle_error("В PDF не найдено таблиц")
                return False

            self._update_progress(60)

            output_ext = output_path.suffix.lower().lstrip('.')

            if output_ext in ['xlsx', 'xls']:
                # Сохраняем в Excel
                if len(tables) == 1:
                    tables[0].to_excel(str(output_path))
                else:
                    import openpyxl
                    wb = openpyxl.Workbook()
                    for i, table in enumerate(tables):
                        ws = wb.create_sheet(f"Table_{i + 1}")
                        df = table.df
                        for r in range(len(df)):
                            for c in range(len(df.columns)):
                                ws.cell(row=r + 1, column=c + 1, value=df.iloc[r, c])
                    wb.remove(wb['Sheet'])
                    wb.save(str(output_path))

            elif output_ext == 'csv':
                # Сохраняем в CSV
                if len(tables) == 1:
                    tables[0].to_csv(str(output_path))
                else:
                    import csv
                    with open(output_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        for i, table in enumerate(tables):
                            writer.writerow([f"=== Table {i + 1} ==="])
                            df = table.df
                            for row in df.values:
                                writer.writerow(row)
                            writer.writerow([])

            self._update_progress(100)
            self._update_status(f"Извлечено {len(tables)} таблиц")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка извлечения таблиц из PDF")
            return False