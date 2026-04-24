"""
Главный файл приложения для PySide6
"""
import sys
import os
from pathlib import Path

# Добавляем путь к src
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from loguru import logger

from gui.main_window import MainWindow


def setup_logging():
    """Настраивает логирование"""
    log_dir = Path.home() / '.config' / 'file-converter' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / 'app.log',
        rotation='10 MB',
        retention='30 days',
        level='DEBUG'
    )

    logger.add(sys.stderr, level='INFO')


def main():
    """Точка входа"""
    setup_logging()

    logger.info("Запуск приложения File Converter Pro")

    # Включаем поддержку высокого DPI для ретина-дисплеев
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Устанавливаем атрибуты до создания QApplication
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Устанавливаем стандартный шрифт системы вместо SF Pro Text
    default_font = QFont()
    default_font.setPointSize(11)
    app.setFont(default_font)

    # Настройка стиля (убираем использование специфических шрифтов)
    app.setStyleSheet("""
        QMainWindow {
            background-color: #2b2b2b;
        }
        QLabel {
            color: #ffffff;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            padding: 8px;
            border: none;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:disabled {
            background-color: #666666;
        }
        QListWidget {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555;
        }
        QComboBox {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555;
            padding: 4px;
        }
        QProgressBar {
            border: 1px solid #555;
            border-radius: 3px;
            text-align: center;
            color: #ffffff;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 3px;
        }
        QTabWidget::pane {
            border: 1px solid #555;
            background-color: #2b2b2b;
        }
        QTabBar::tab {
            background-color: #3c3c3c;
            color: #ffffff;
            padding: 5px 10px;
        }
        QTabBar::tab:selected {
            background-color: #4a4a4a;
        }
        QGroupBox {
            color: #ffffff;
            border: 1px solid #555;
            margin-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QCheckBox {
            color: #ffffff;
        }
        QSpinBox {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555;
            padding: 3px;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #3c3c3c;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #4CAF50;
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }
        QTextEdit {
            background-color: #1e1e1e;
            color: #00ff00;
            border: 1px solid #555;
        }
        QScrollArea {
            background-color: #2b2b2b;
            border: none;
        }
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 12px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #555;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #666;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()