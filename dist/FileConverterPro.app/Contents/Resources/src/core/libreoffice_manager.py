"""
Менеджер для использования LibreOffice с максимальным ускорением (без потери качества)
"""
import sys
import os
import platform
import subprocess
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional, Callable
from loguru import logger


class LibreOfficeManager:
    """Использование LibreOffice с оптимизациями скорости (качество не снижается)"""

    def __init__(self):
        self.system = platform.system().lower()
        self.setup_paths()

    def setup_paths(self):
        """Настраивает пути к LibreOffice"""
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
            if self.system == 'darwin':
                self.base_dir = base.parent / "Resources"
            else:
                self.base_dir = base
        else:
            base = Path(__file__).parent.parent.parent
            self.base_dir = base / "resources"

        # Пути к LibreOffice
        if self.system == 'darwin':
            self.bin_path = self.base_dir / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice"
        elif self.system == 'windows':
            self.bin_path = self.base_dir / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe"
        else:
            self.bin_path = Path("/usr/bin/libreoffice")

    def is_installed(self) -> bool:
        """Проверяет, доступен ли LibreOffice"""
        import shutil

        # Проверяем системную версию
        if shutil.which('libreoffice'):
            self.bin_path = Path(shutil.which('libreoffice'))
            return True
        if shutil.which('soffice'):
            self.bin_path = Path(shutil.which('soffice'))
            return True

        # Проверяем встроенную версию
        if self.bin_path.exists():
            return True

        # macOS
        if self.system == 'darwin':
            if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists():
                self.bin_path = Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')
                return True

        # Windows
        if self.system == 'windows':
            paths = [
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
            ]
            for path in paths:
                if path.exists():
                    self.bin_path = path
                    return True

        return False

    def get_optimized_cmd(self, input_path: Path, output_path: Path) -> list:
        """
        Возвращает оптимизированную команду LibreOffice
        Все параметры увеличивают скорость, НЕ снижая качество
        """
        cmd = [
            str(self.bin_path),
            '--headless',           # Без GUI
            '--invisible',          # Не показывать окна
            '--nocrashreport',      # Отключить отчёт о сбоях
            '--nofirststartwizard', # Отключить мастер первого запуска
            '--nologo',             # Без логотипа
            '--norestore',          # Не восстанавливать документы
            '--nofavmenu',          # Отключить меню избранного
            '--nologo',             # Без логотипа
            '--nodefault',          # Не загружать документ по умолчанию
        ]

        # Ускоряющие параметры для конкретных форматов
        ext = input_path.suffix.lower()

        if ext == '.docx':
            # Оптимизация для Word
            cmd.extend([
                '--infilter=MS Word 2007 XML',  # Специфичный фильтр для docx
            ])
        elif ext == '.pptx':
            # Оптимизация для PowerPoint
            cmd.extend([
                '--infilter=Impress MS PowerPoint 2007 XML',
            ])
        elif ext in ['.xlsx', '.xls']:
            # Оптимизация для Excel
            cmd.extend([
                '--infilter=Calc MS Excel 2007 XML',
            ])

        # Параметры PDF
        cmd.extend([
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ])

        return cmd

    def convert_with_soffice(self, input_path: Path, output_path: Path, progress_callback=None) -> bool:
        """Конвертирует через LibreOffice с оптимизациями"""
        cmd = self.get_optimized_cmd(input_path, output_path)

        logger.info(f"Запуск оптимизированной конвертации: {' '.join(cmd)}")

        try:
            if progress_callback:
                progress_callback(50)

            # Используем PIPE для меньшего потребления ресурсов
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                # Оптимизации процесса
                stdin=subprocess.DEVNULL,
                startupinfo=self.get_startup_info() if self.system == 'windows' else None
            )

            if progress_callback:
                progress_callback(80)

            # Проверяем результат
            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                return True

            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False

    def get_startup_info(self):
        """Настройки для Windows (скрыть окно)"""
        if self.system == 'windows':
            import subprocess
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = subprocess.SW_HIDE
            return info
        return None

    def convert(self, input_path: Path, output_path: Path, progress_callback: Optional[Callable] = None) -> bool:
        """Конвертирует файл через LibreOffice"""
        if not self.is_installed():
            logger.error("LibreOffice не найден")
            return False

        return self.convert_with_soffice(input_path, output_path, progress_callback)