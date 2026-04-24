"""
Конвертер таблиц Excel и CSV
"""
import sys
import subprocess
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class SpreadsheetConverter(BaseConverter):
    """Конвертер таблиц (xlsx, xls, csv) через LibreOffice и openpyxl"""

    def __init__(self):
        super().__init__()
        self._soffice_path = None
        self.libreoffice_available = self._check_libreoffice()
        self.openpyxl_available = self._check_openpyxl()

    def _check_libreoffice(self):
        """Проверяет наличие LibreOffice"""
        import shutil
        import platform

        for name in ['libreoffice', 'soffice']:
            path = shutil.which(name)
            if path:
                self._soffice_path = Path(path)
                return True

        system = platform.system().lower()
        project_root = Path(__file__).parent.parent.parent

        if system == 'darwin':
            paths = [
                project_root / "resources" / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
                '/Applications/LibreOffice.app/Contents/MacOS/soffice',
            ]
            for path in paths:
                if Path(path).exists():
                    self._soffice_path = path
                    return True
        elif system == 'windows':
            paths = [
                project_root / "resources" / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe",
                'C:/Program Files/LibreOffice/program/soffice.exe',
            ]
            for path in paths:
                if Path(path).exists():
                    self._soffice_path = path
                    return True
        else:
            if Path('/usr/bin/libreoffice').exists():
                self._soffice_path = Path('/usr/bin/libreoffice')
                return True

        return False

    def _check_openpyxl(self):
        """Проверяет наличие openpyxl"""
        try:
            import openpyxl
            return True
        except ImportError:
            return False

    def _install_openpyxl(self):
        """Устанавливает openpyxl"""
        try:
            self._update_status("Установка openpyxl...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'openpyxl', '--quiet'
            ])
            self.openpyxl_available = True
            return True
        except Exception as e:
            logger.error(f"Ошибка установки openpyxl: {e}")
            return False

    def get_input_formats(self):
        return ['xlsx', 'xls', 'csv']

    def get_output_formats(self):
        return ['xlsx', 'xls', 'csv', 'pdf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            input_ext = input_path.suffix.lower().lstrip('.')
            output_ext = output_path.suffix.lower().lstrip('.')

            # Конвертация в PDF через LibreOffice
            if output_ext == 'pdf':
                return self._convert_to_pdf(input_path, output_path)

            # Конвертация между табличными форматами
            if input_ext in ['xlsx', 'xls', 'csv'] and output_ext in ['xlsx', 'xls', 'csv']:
                return self._convert_spreadsheet(input_path, output_path, output_ext)

            self._handle_error(f"Конвертация {input_ext} -> {output_ext} не поддерживается")
            return False

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации таблицы")
            return False

    def _convert_to_pdf(self, input_path: Path, output_path: Path) -> bool:
        """Конвертирует таблицу в PDF через LibreOffice"""
        if not self.libreoffice_available:
            error_msg = (
                "LibreOffice не найден!\n\n"
                "Для конвертации таблиц в PDF необходимо установить LibreOffice:\n"
                "- macOS: brew install --cask libreoffice\n"
                "- Windows: https://www.libreoffice.org/download/\n"
                "- Linux: sudo apt install libreoffice"
            )
            self._handle_error(error_msg)
            return False

        self._update_status(f"Конвертация {input_path.name} в PDF...")

        cmd = [
            str(self._soffice_path),
            '--headless',
            '--invisible',
            '--nocrashreport',
            '--nofirststartwizard',
            '--nologo',
            '--norestore',
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            expected_file = output_path.parent / f"{input_path.stem}.pdf"
            if expected_file.exists():
                if expected_file != output_path:
                    expected_file.rename(output_path)
                return True

            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации в PDF: {e}")
            return False

    def _convert_spreadsheet(self, input_path: Path, output_path: Path, output_ext: str) -> bool:
        """Конвертирует между табличными форматами"""
        if not self.openpyxl_available:
            if not self._install_openpyxl():
                self._handle_error("Не удалось установить openpyxl")
                return False

        try:
            import openpyxl
            import csv

            self._update_status(f"Чтение файла {input_path.name}...")

            # Читаем входной файл
            input_ext = input_path.suffix.lower().lstrip('.')

            if input_ext == 'csv':
                # Читаем CSV
                wb = openpyxl.Workbook()
                ws = wb.active

                with open(input_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row_idx, row in enumerate(reader, 1):
                        for col_idx, value in enumerate(row, 1):
                            ws.cell(row=row_idx, column=col_idx, value=value)
            else:
                # Читаем Excel
                wb = openpyxl.load_workbook(input_path)
                ws = wb.active

            self._update_progress(50)

            # Сохраняем в нужном формате
            if output_ext == 'csv':
                self._update_status("Сохранение в CSV...")
                with open(output_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    for row in ws.iter_rows(values_only=True):
                        writer.writerow(row)
            else:
                self._update_status(f"Сохранение в {output_ext.upper()}...")
                wb.save(output_path)

            self._update_progress(100)
            self._update_status("Конвертация завершена!")
            return True

        except Exception as e:
            logger.error(f"Ошибка конвертации таблицы: {e}")
            return False