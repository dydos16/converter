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

# Консоль Windows по умолчанию в cp1252: на кириллице print() падал, и собранное приложение
# не запускалось из командной строки. В оконной сборке потоков нет совсем (None) — их не трогаем
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


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
    # В оконной сборке Windows (PyInstaller --windowed) консоли нет и sys.stderr = None —
    # loguru на нём падает, и приложение не запустилось бы вовсе
    if sys.stderr is not None:
        logger.add(sys.stderr, level='INFO')
    
    logger.info("Запуск File Converter Pro")
    
    # HighDPI в PySide6 >=6.4 включён по умолчанию — устаревшие атрибуты не нужны.
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    from PySide6.QtGui import QIcon
    icon = BASE / 'packaging' / 'icon.png'      # в сборке лежит рядом, см. --add-data в build.py
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
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

    # --self-test[=отчёт.txt]: проверка собранного приложения в CI, без докачки LibreOffice
    self_test = next((a for a in sys.argv if a.startswith('--self-test')), None)
    if self_test:
        from PySide6.QtCore import QTimer
        from src.selftest import run_self_test
        report = Path(self_test.split('=', 1)[1]) if '=' in self_test else None
        def finish():
            code = run_self_test(window, report)
            window.close()          # штатно останавливает фоновые потоки, иначе Qt прервёт процесс
            app.exit(code)
        QTimer.singleShot(1500, finish)
    else:
        # Фоновая проверка LibreOffice и авто-докачка при его отсутствии (не блокируют GUI)
        window.maybe_start_libreoffice_install()
        window.libreoffice_manager.start_periodic_check()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
