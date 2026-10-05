#!/usr/bin/env python3
"""
File Converter Pro — точка входа (LibreOffice докачивает LibreOfficeManager)
"""
import sys
from pathlib import Path

# Пути для PyInstaller
if getattr(sys, 'frozen', False):
    BASE = Path(sys._MEIPASS)
else:
    BASE = Path(__file__).parent

sys.path.insert(0, str(BASE))


def main():
    print("=" * 60)
    print("  File Converter Pro")
    print("=" * 60)
    
    print("\nЗапуск интерфейса...\n")
    
    # Запускаем GUI
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from loguru import logger
    
    # Убираем стандартный stderr-хендлер loguru, чтобы сообщения не дублировались
    logger.remove()
    from src.utils.helpers import get_config_dir
    logger.add(get_config_dir() / 'logs' / 'app.log', 
               rotation='10 MB', retention='30 days', level='DEBUG')
    logger.add(sys.stderr, level='INFO')
    
    logger.info("Запуск File Converter Pro")
    
    # HighDPI в PySide6 >=6.4 включён по умолчанию — устаревшие атрибуты не нужны.
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont())

    # Тема из настроек: 'system' (по умолчанию) | 'light' | 'dark'
    from src.core.settings import Settings
    from src.gui.styles import get_stylesheet_for, get_palette_for
    theme_mode = Settings().get('theme', 'system')
    app.setPalette(get_palette_for(theme_mode))
    app.setStyleSheet(get_stylesheet_for(theme_mode))

    from src.gui.main_window import MainWindow
    window = MainWindow()
    window.show()
    
    # Фоновая проверка LibreOffice и авто-докачка при его отсутствии (не блокируют GUI)
    window.maybe_start_libreoffice_install()
    window.libreoffice_manager.start_periodic_check()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
