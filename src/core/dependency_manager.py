"""
Менеджер зависимостей - автоматическая установка всех необходимых пакетов и LibreOffice
"""
import sys
import subprocess
import importlib
from pathlib import Path
from loguru import logger


class DependencyManager:
    """Автоматическая установка зависимостей"""

    # Список необходимых Python пакетов
    REQUIRED_PACKAGES = {
        'PySide6': '6.11.0',
        'python-docx': '1.2.0',
        'python-pptx': '1.0.2',
        'reportlab': '4.4.10',
        'Pillow': '12.1.1',
        'openpyxl': '3.1.5',
        'loguru': '0.7.3',
        'colorama': '0.4.6',
        'requests': '2.31.0',
        'lxml': '6.0.2',
    }

    def __init__(self):
        self.missing_packages = []
        self.installed = False

    def check_python_packages(self) -> bool:
        """Проверяет установку Python пакетов"""
        missing = []

        for package, version in self.REQUIRED_PACKAGES.items():
            try:
                # Пробуем импортировать пакет
                if package == 'python-docx':
                    importlib.import_module('docx')
                elif package == 'python-pptx':
                    importlib.import_module('pptx')
                elif package == 'Pillow':
                    importlib.import_module('PIL')
                else:
                    importlib.import_module(package.lower())
                logger.info(f"✓ {package} установлен")
            except ImportError:
                missing.append(package)
                logger.warning(f"✗ {package} не установлен")

        self.missing_packages = missing
        return len(missing) == 0

    def install_python_packages(self, progress_callback=None) -> bool:
        """Устанавливает недостающие Python пакеты"""
        if not self.missing_packages:
            return True

        logger.info(f"Установка {len(self.missing_packages)} пакетов...")

        for i, package in enumerate(self.missing_packages):
            version = self.REQUIRED_PACKAGES.get(package, '')
            package_spec = f"{package}=={version}" if version else package

            if progress_callback:
                progress_callback(i, len(self.missing_packages), package)

            try:
                # Добавляем флаг --break-system-packages для обхода защиты
                cmd = [sys.executable, '-m', 'pip', 'install', package_spec, '--break-system-packages']
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info(f"Установлен: {package}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Ошибка установки {package}: {e.stderr}")
                return False

        if progress_callback:
            progress_callback(len(self.missing_packages), len(self.missing_packages), "Готово")

        return True

    def check_libreoffice(self) -> bool:
        """Проверяет наличие LibreOffice"""
        import shutil

        paths = []

        if sys.platform == 'darwin':
            paths = [
                '/Applications/LibreOffice.app/Contents/MacOS/soffice',
                '/Applications/LibreOffice.app/Contents/MacOS/libreoffice',
            ]
        elif sys.platform == 'win32':
            paths = [
                r'C:\Program Files\LibreOffice\program\soffice.exe',
                r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
            ]
        else:
            paths = [
                '/usr/bin/libreoffice',
                '/usr/bin/soffice',
            ]

        for path in paths:
            if Path(path).exists():
                return True

        if shutil.which('soffice') or shutil.which('libreoffice'):
            return True

        return False

    def install_libreoffice(self, progress_callback=None) -> bool:
        """Устанавливает LibreOffice через встроенный менеджер"""
        from .libreoffice_manager import LibreOfficeManager

        manager = LibreOfficeManager()

        if manager.is_installed():
            return True

        if progress_callback:
            progress_callback(0, 100, "Скачивание LibreOffice...")

        def inner_callback(progress):
            if progress_callback:
                progress_callback(progress, 100, f"Установка LibreOffice: {progress}%")

        return manager.install(inner_callback)

    def check_all(self) -> dict:
        """Проверяет все зависимости"""
        return {
            'python_packages': self.check_python_packages(),
            'libreoffice': self.check_libreoffice()
        }

    def install_all(self, progress_callback=None) -> bool:
        """Устанавливает все зависимости"""
        # Сначала Python пакеты
        if not self.check_python_packages():
            logger.info("Установка Python пакетов...")
            if not self.install_python_packages(progress_callback):
                return False

        # Затем LibreOffice
        if not self.check_libreoffice():
            logger.info("Установка LibreOffice...")
            if not self.install_libreoffice(progress_callback):
                return False

        return True