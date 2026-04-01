"""
Единый модуль для проверки зависимостей
"""
import sys
import importlib
from typing import List, Dict, Tuple
from loguru import logger
from src.utils.libreoffice_utils import LibreOfficeUtils


class DependencyChecker:
    """Класс для проверки всех зависимостей"""

    # Список необходимых пакетов: {пакет: импортируемое_имя}
    REQUIRED_PACKAGES = {
        'PySide6': 'PySide6',
        'python-docx': 'docx',
        'python-pptx': 'pptx',
        'reportlab': 'reportlab',
        'Pillow': 'PIL',
        'openpyxl': 'openpyxl',
        'loguru': 'loguru',
        'colorama': 'colorama',
        'requests': 'requests',
        'lxml': 'lxml',
    }

    @classmethod
    def check_python_packages(cls) -> Tuple[bool, List[str]]:
        """
        Проверяет установку Python пакетов

        Returns:
            Tuple[bool, List[str]]: (все_установлены, список_отсутствующих)
        """
        missing = []

        for package, import_name in cls.REQUIRED_PACKAGES.items():
            try:
                importlib.import_module(import_name)
                logger.debug(f"✓ {package} установлен")
            except ImportError:
                missing.append(package)
                logger.warning(f"✗ {package} не установлен")

        return len(missing) == 0, missing

    @classmethod
    def check_libreoffice(cls) -> bool:
        """Проверяет наличие LibreOffice"""
        return LibreOfficeUtils.is_installed()

    @classmethod
    def check_all(cls) -> Dict[str, bool]:
        """Проверяет все зависимости"""
        python_ok, missing = cls.check_python_packages()

        return {
            'python_packages': python_ok,
            'python_missing': missing,
            'libreoffice': cls.check_libreoffice()
        }

    @classmethod
    def get_status_report(cls) -> str:
        """Возвращает текстовый отчет о зависимостях"""
        status = cls.check_all()

        report = []
        report.append("=" * 60)
        report.append("  Отчет о зависимостях")
        report.append("=" * 60)

        # Python пакеты
        if status['python_packages']:
            report.append("✅ Python пакеты: все установлены")
        else:
            report.append(f"❌ Python пакеты: отсутствуют {len(status['python_missing'])} пакет(ов)")
            for pkg in status['python_missing']:
                report.append(f"   - {pkg}")

        # LibreOffice
        if status['libreoffice']:
            report.append("✅ LibreOffice: установлен")
        else:
            report.append("❌ LibreOffice: не установлен")

        return "\n".join(report)