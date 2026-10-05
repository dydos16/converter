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
        """Ищет soffice через общий LibreOfficeManager — одно место для всех путей установки"""
        from src.core.libreoffice_manager import LibreOfficeManager
        lo = LibreOfficeManager()
        self._soffice_path = lo.get_soffice_path() or lo._find_soffice()
        return self._soffice_path is not None

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
            self._user_installation_arg(),
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
        input_ext = input_path.suffix.lower().lstrip('.')
        self._update_status(f"Чтение файла {input_path.name}...")

        # Старые .xls / бинарные форматы openpyxl не читает и не пишет —
        # используем LibreOffice как универсальный конвертер таблиц.
        if input_ext == 'xls' or output_ext == 'xls':
            if not self.libreoffice_available:
                self._handle_error("Для работы с .xls требуется LibreOffice.")
                return False
            return self._convert_via_soffice(input_path, output_path, output_ext)

        if not self.openpyxl_available:
            if not self._install_openpyxl():
                self._handle_error("Не удалось установить openpyxl")
                return False

        try:
            import openpyxl
            import csv

            # Читаем входной файл
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
                # Читаем Excel (xlsx)
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

    def _user_installation_arg(self) -> str:
        """Возвращает аргумент -env:UserInstallation для изолированного профиля LibreOffice."""
        try:
            from src.core.libreoffice_manager import LibreOfficeManager
            return LibreOfficeManager()._get_user_profile_path().replace('file://', '-env:UserInstallation=file://')
        except Exception:
            return '--norestore'

    def _convert_via_soffice(self, input_path: Path, output_path: Path, output_ext: str) -> bool:
        """Конвертирует таблицы через LibreOffice (для .xls и др.)."""
        if not self.libreoffice_available:
            self._handle_error("LibreOffice не найден!")
            return False

        self._update_status(f"Конвертация через LibreOffice в {output_ext.upper()}...")

        # LibreOffice поддерживает запись xls/xlsx/csv через фильтры
        cmd = [
            str(self._soffice_path),
            self._user_installation_arg(),
            '--headless', '--invisible', '--nocrashreport',
            '--nofirststartwizard', '--nologo', '--norestore',
            '--convert-to', output_ext,
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            expected_file = output_path.parent / f"{input_path.stem}.{output_ext}"
            if expected_file.exists():
                if expected_file != output_path:
                    expected_file.rename(output_path)
                self._update_status("Конвертация завершена!")
                return True

            logger.error(f"Файл не создан после LibreOffice: {result.stderr[:200]}")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации через LibreOffice: {e}")
            return False