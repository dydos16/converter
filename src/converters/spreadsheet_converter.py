"""
Таблицы: xlsx, xls, csv — друг в друга и в PDF.
CSV разбираем сами (UTF-8 или Windows-1251, разделитель «,», «;» или табуляция — как сохраняет русский Excel),
CSV для Excel пишем с BOM. Остальное делает LibreOffice.
"""
import csv
import io
import re
import tempfile
from pathlib import Path
from .base import BaseConverter
from loguru import logger


def _cell(value: str):
    """Числа из CSV — числами, иначе Excel покажет их текстом. Коды с ведущим нулём и длинные номера не трогаем."""
    if re.fullmatch(r"-?(0|[1-9]\d{0,14})", value):
        return int(value)
    if re.fullmatch(r"-?(0|[1-9]\d{0,14})[.,]\d+", value):
        return float(value.replace(",", "."))
    return value


class SpreadsheetConverter(BaseConverter):
    """Конвертер таблиц через openpyxl и LibreOffice"""

    def get_input_formats(self):
        return ['xlsx', 'xls', 'csv']

    def get_output_formats(self):
        return ['xlsx', 'xls', 'csv', 'pdf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        from src.core.libreoffice_manager import LibreOfficeManager, LO_MISSING
        src = input_path.suffix.lower().lstrip('.')
        dst = output_path.suffix.lower().lstrip('.')
        try:
            if src == 'csv' and dst == 'xlsx':
                return self._csv_to_xlsx(input_path, output_path)
            if src == 'xlsx' and dst == 'csv':
                return self._xlsx_to_csv(input_path, output_path)

            lo = LibreOfficeManager()
            if not lo.is_available():
                self._handle_error(LO_MISSING)
                return False
            self._update_status(f"Конвертация через LibreOffice в {dst.upper()}...")
            if src == 'csv':        # → pdf/xls: CSV разбираем сами в XLSX, дальше LibreOffice
                return lo.convert_via(lambda xlsx: self._csv_to_xlsx(input_path, xlsx), output_path, '.xlsx')
            if dst == 'csv':        # xls → csv: LibreOffice делает XLSX, CSV для Excel пишем сами
                with tempfile.TemporaryDirectory() as tmp:
                    xlsx = Path(tmp) / f"{input_path.stem}.xlsx"
                    return lo.convert(input_path, xlsx) and self._xlsx_to_csv(xlsx, output_path)
            return lo.convert(input_path, output_path)      # xlsx ↔ xls, таблица → PDF

        except Exception as e:
            self._handle_error(f"Ошибка конвертации таблицы: {str(e)}")
            logger.exception("Ошибка конвертации таблицы")
            return False

    def _csv_to_xlsx(self, input_path: Path, output_path: Path) -> bool:
        from openpyxl import Workbook
        from src.utils.helpers import read_text_any

        self._update_status(f"Чтение {input_path.name}...")
        text = read_text_any(input_path)
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:                                   # один столбец — разделителя нет
            dialect = csv.excel
        wb = Workbook()
        for row in csv.reader(io.StringIO(text), dialect):
            wb.active.append([_cell(value) for value in row])
        wb.save(output_path)
        self._update_progress(100)
        return True

    def _xlsx_to_csv(self, input_path: Path, output_path: Path) -> bool:
        from openpyxl import load_workbook

        self._update_status("Сохранение в CSV...")
        wb = load_workbook(input_path, read_only=True, data_only=True)
        # С BOM: без него русский Excel откроет UTF-8 кракозябрами
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerows(wb.active.iter_rows(values_only=True))
        wb.close()
        self._update_progress(100)
        return True
