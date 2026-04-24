"""
Менеджер зависимостей - использует единые утилиты
"""
from typing import Optional, Callable
from loguru import logger

from src.utils.dependency_checker import DependencyChecker
from src.utils.install_manager import InstallManager


class DependencyManager:
    """Менеджер зависимостей (обёртка над утилитами)"""
    
    def __init__(self):
        self.checker = DependencyChecker()
        self.installer = InstallManager()
    
    def check_python_packages(self) -> bool:
        """Проверяет установку Python пакетов"""
        ok, _ = self.checker.check_python_packages()
        return ok
    
    def install_python_packages(self, progress_callback=None) -> bool:
        """Устанавливает недостающие Python пакеты"""
        return self.installer.install_python_packages(progress_callback)
    
    def check_libreoffice(self) -> bool:
        """Проверяет наличие LibreOffice"""
        return self.checker.check_libreoffice()
    
    def install_libreoffice(self, progress_callback=None) -> bool:
        """Устанавливает LibreOffice"""
        return self.installer.install_libreoffice(progress_callback)
    
    def check_all(self) -> dict:
        """Проверяет все зависимости"""
        return self.checker.check_all()
    
    def install_all(self, progress_callback=None) -> bool:
        """Устанавливает все зависимости"""
        return self.installer.install_all(progress_callback)