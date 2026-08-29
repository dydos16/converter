"""
Темы оформления для File Converter Pro.

Поддерживаются три режима:
  * light  — светлая тема (Telegram-палитра)
  * dark   — тёмная тема (глубокий сине-графитовый фон)
  * system — автоматически следует за системной темой (через QStyleHints)

Каждая тема задана как QSS-строка. Выбор и применение осуществляется через
функции, которые также возвращают нужную QPalette для согласованного рендера.
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor


# --------------------------------------------------------------------------- #
#  СВЕТЛАЯ ТЕМА (Telegram :: light)
# --------------------------------------------------------------------------- #
LIGHT_STYLE = """
    QMainWindow, QDialog {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #e4eff9, stop:0.55 #f0f7fd, stop:1 #fafdff);
    }
    QWidget { color: #0f0f10; font-size: 13px; }
    QLabel { color: #0f0f10; background: transparent; }
    QLabel[secondary="true"] { color: #707579; }
    QLabel[big="true"] { font-size: 15px; font-weight: 600; color: #0f0f10; }

    QGroupBox {
        background-color: rgba(255,255,255,0.72);
        color: #0f0f10;
        border: 1px solid rgba(34,158,217,0.10);
        border-radius: 16px;
        margin-top: 14px;
        padding-top: 16px;
        padding-bottom: 6px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px; top: -2px;
        padding: 0 6px;
        color: #229ED9; font-size: 12px; font-weight: 700; letter-spacing: 0.4px;
    }

    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f2f7fc);
        color: #0f0f10;
        border: 1px solid rgba(34,158,217,0.16);
        border-radius: 22px;
        padding: 10px 22px;
        font-weight: 600;
        letter-spacing: 0.2px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #eef7ff, stop:1 #ddeffd);
        border: 1px solid rgba(34,158,217,0.6);
        color: #1177b0;
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(34,158,217,0.28), stop:1 rgba(34,158,217,0.16));
        border: 1px solid #229ED9;
    }
    QPushButton:disabled { background-color: #f2f4f7; color: #b0b8c1; border-color: rgba(0,0,0,0.04); }

    QPushButton[primary="true"] {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #2AABEE, stop:0.5 #35B6F0, stop:1 #1E96D6);
        color: #ffffff;
        border: 1px solid rgba(120,220,255,0.5);
        border-radius: 32px;
        padding: 13px 26px;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    QPushButton[primary="true"]:hover {
        border: 1px solid rgba(180,240,255,0.9);
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #45C0F7, stop:0.5 #4FC4FA, stop:1 #2AA2E5);
    }
    QPushButton[primary="true"]:pressed {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #1580C0, stop:1 #126AA5);
        border: 1px solid #229ED9;
    }
    QPushButton[primary="true"]:disabled { background-color: #c8d7e3; color: #ffffff; border: none; }

    /* Небольшие кнопки-пилюли */
    QPushButton[slim="true"] {
        border-radius: 18px;
        padding: 7px 16px;
        font-size: 12px;
        font-weight: 500;
    }
    QPushButton[primary="true"]:disabled { background-color: #c8d7e3; color: #ffffff; }

    QListWidget {
        background-color: rgba(255,255,255,0.78);
        color: #0f0f10;
        border: 1px solid rgba(34,158,217,0.10);
        border-radius: 14px;
        padding: 6px;
        outline: none;
    }
    QListWidget::item { padding: 9px 12px; border-radius: 9px; margin: 1px 2px; }
    QListWidget::item:hover { background-color: rgba(34,158,217,0.07); }
    QListWidget::item:selected { background-color: rgba(34,158,217,0.14); color: #0f0f10; }

    QComboBox {
        background-color: #ffffff; color: #0f0f10;
        border: 1px solid rgba(34,158,217,0.20);
        border-radius: 12px; padding: 12px 16px; min-width: 8em;
        font-size: 15px; font-weight: 600;
    }
    QComboBox:hover { border-color: rgba(34,158,217,0.5); }
    QComboBox::drop-down { border: none; width: 28px; }
    QComboBox::down-arrow {
        image: none;
        border-left: 6px solid transparent; border-right: 6px solid transparent;
        border-top: 6px solid #229ED9; margin-right: 8px;
    }
    QComboBox QAbstractItemView {
        background-color: #ffffff; color: #0f0f10;
        border: 1px solid #e3eaf1;
        selection-background-color: rgba(34,158,217,0.14);
        selection-color: #0f0f10; border-radius: 12px; outline: none; padding: 6px;
        font-size: 14px;
    }
    QComboBox QAbstractItemView::item { padding: 6px 12px; }

    QProgressBar {
        background-color: rgba(34,158,217,0.10);
        border: none; border-radius: 6px;
        text-align: center; color: #0f0f10;
        min-height: 8px; font-size: 11px; font-weight: 600;
    }
    QProgressBar::chunk { background-color: #229ED9; border-radius: 6px; }

    QTabWidget::pane { border: none; background-color: rgba(255,255,255,0.72); border-radius: 16px; top: -1px; }
    QTabBar { background: transparent; }
    QTabBar::tab {
        background: transparent; color: #8a93a0;
        padding: 10px 20px; margin-right: 4px; border: none;
        border-bottom: 2px solid transparent; font-weight: 500;
        border-top-left-radius: 10px; border-top-right-radius: 10px;
    }
    QTabBar::tab:hover { color: #0f0f10; background-color: rgba(255,255,255,0.5); }
    QTabBar::tab:selected { color: #229ED9; border-bottom: 2px solid #229ED9; background-color: rgba(255,255,255,0.7); font-weight: 700; }

    QCheckBox { color: #0f0f10; spacing: 8px; background: transparent; }
    QCheckBox::indicator { width: 19px; height: 19px; border: 2px solid rgba(34,158,217,0.4); border-radius: 6px; background-color: #ffffff; }
    QCheckBox::indicator:hover { border-color: #229ED9; }
    QCheckBox::indicator:checked { background-color: #229ED9; border-color: #229ED9; image: url(:/icons/check.png); }

    QSpinBox {
        background-color: #ffffff; color: #0f0f10;
        border: 1px solid rgba(34,158,217,0.20); border-radius: 8px; padding: 6px; min-width: 60px;
    }
    QSpinBox:focus { border-color: #229ED9; }

    QSlider::groove:horizontal { height: 6px; background-color: rgba(34,158,217,0.14); border-radius: 3px; }
    QSlider::sub-page:horizontal { background-color: #229ED9; border-radius: 3px; }
    QSlider::handle:horizontal { width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; background-color: #ffffff; border: 2px solid #229ED9; }
    QSlider::handle:horizontal:hover { background-color: #f0f9ff; }

    QTextEdit { background-color: rgba(15,20,30,0.92); color: #b8f6c8; border: none; border-radius: 12px; padding: 10px; selection-background-color: rgba(34,158,217,0.5); font-family: "Menlo","Consolas",monospace; font-size: 12px; }
    QScrollArea { background-color: transparent; border: none; }

    QScrollBar:vertical { background-color: transparent; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical { background-color: rgba(34,158,217,0.35); border-radius: 5px; min-height: 24px; }
    QScrollBar::handle:vertical:hover { background-color: rgba(34,158,217,0.55); }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

    QStatusBar { background-color: rgba(255,255,255,0.55); color: #707579; border-top: 1px solid rgba(34,158,217,0.10); }
    QStatusBar::item { border: none; }

    QMenu { background-color: #ffffff; color: #0f0f10; border: 1px solid rgba(34,158,217,0.15); border-radius: 10px; padding: 6px; }
    QMenu::item { padding: 7px 20px; border-radius: 6px; }
    QMenu::item:selected { background-color: rgba(34,158,217,0.12); }

    QSplitter::handle { background-color: rgba(34,158,217,0.12); border-radius: 2px; }
"""


# --------------------------------------------------------------------------- #
#  ТЁМНАЯ ТЕМА (deep graphite :: dark)
# --------------------------------------------------------------------------- #
DARK_STYLE = """
    QMainWindow, QDialog {
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #0f1620, stop:0.6 #141d29, stop:1 #1b2430);
    }
    QWidget { color: #e8edf2; font-size: 13px; }
    QLabel { color: #e8edf2; background: transparent; }
    QLabel[secondary="true"] { color: #8a95a3; }
    QLabel[big="true"] { font-size: 15px; font-weight: 600; color: #e8edf2; }

    QGroupBox {
        background-color: rgba(30,42,58,0.55);
        color: #e8edf2;
        border: 1px solid rgba(120,150,180,0.12);
        border-radius: 16px;
        margin-top: 14px;
        padding-top: 16px;
        padding-bottom: 6px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px; top: -2px;
        padding: 0 6px;
        color: #4FC3F7; font-size: 12px; font-weight: 700; letter-spacing: 0.4px;
    }

    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(60,76,96,0.9), stop:1 rgba(40,52,68,0.9));
        color: #e8edf2;
        border: 1px solid rgba(120,150,180,0.18);
        border-radius: 22px;
        padding: 10px 22px;
        font-weight: 600;
        letter-spacing: 0.2px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(74,94,118,0.95), stop:1 rgba(52,70,90,0.95));
        border: 1px solid rgba(79,195,247,0.7);
        color: #ffffff;
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(79,195,247,0.35), stop:1 rgba(30,80,120,0.55));
        border: 1px solid #4FC3F7;
    }
    QPushButton:disabled { background-color: rgba(40,50,60,0.5); color: #6b7683; border-color: rgba(120,150,180,0.08); }

    QPushButton[primary="true"] {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(33,150,243,0.95), stop:0.5 rgba(42,160,235,0.95), stop:1 rgba(24,110,190,0.95));
        color: #ffffff;
        border: 1px solid rgba(120,220,255,0.35);
        border-radius: 32px;
        padding: 13px 26px;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    QPushButton[primary="true"]:hover {
        border: 1px solid rgba(160,235,255,0.9);
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(45,170,255,1), stop:0.5 rgba(60,185,255,1), stop:1 rgba(35,130,215,1));
    }
    QPushButton[primary="true"]:pressed {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(20,90,160,1), stop:1 rgba(15,70,130,1));
        border: 1px solid #4FC3F7;
    }
    QPushButton[primary="true"]:disabled { background-color: #33465a; color: #8095aa; border: none; }

    /* Небольшие кнопки-пилюли (очистить, обслуживающие) */
    QPushButton[slim="true"] {
        border-radius: 18px;
        padding: 7px 16px;
        font-size: 12px;
        font-weight: 500;
    }

    QListWidget {
        background-color: rgba(24,34,48,0.7);
        color: #e8edf2;
        border: 1px solid rgba(120,150,180,0.12);
        border-radius: 14px;
        padding: 6px;
        outline: none;
    }
    QListWidget::item { padding: 9px 12px; border-radius: 9px; margin: 1px 2px; }
    QListWidget::item:hover { background-color: rgba(79,195,247,0.08); }
    QListWidget::item:selected { background-color: rgba(79,195,247,0.18); color: #e8edf2; }

    QComboBox {
        background-color: rgba(50,64,82,0.7); color: #e8edf2;
        border: 1px solid rgba(120,150,180,0.20);
        border-radius: 12px; padding: 12px 16px; min-width: 8em;
        font-size: 15px; font-weight: 600;
    }
    QComboBox:hover { border-color: rgba(79,195,247,0.5); }
    QComboBox::drop-down { border: none; width: 28px; }
    QComboBox::down-arrow {
        image: none;
        border-left: 6px solid transparent; border-right: 6px solid transparent;
        border-top: 6px solid #4FC3F7; margin-right: 8px;
    }
    QComboBox QAbstractItemView {
        background-color: #1a2330; color: #e8edf2;
        border: 1px solid #2a3646;
        selection-background-color: rgba(79,195,247,0.18);
        selection-color: #e8edf2; border-radius: 12px; outline: none; padding: 6px;
        font-size: 14px;
    }
    QComboBox QAbstractItemView::item { padding: 6px 12px; }

    QProgressBar {
        background-color: rgba(79,195,247,0.10);
        border: none; border-radius: 6px;
        text-align: center; color: #e8edf2;
        min-height: 8px; font-size: 11px; font-weight: 600;
    }
    QProgressBar::chunk { background-color: #4FC3F7; border-radius: 6px; }

    QTabWidget::pane { border: none; background-color: rgba(30,42,58,0.5); border-radius: 16px; top: -1px; }
    QTabBar { background: transparent; }
    QTabBar::tab {
        background: transparent; color: #7d8896;
        padding: 10px 20px; margin-right: 4px; border: none;
        border-bottom: 2px solid transparent; font-weight: 500;
        border-top-left-radius: 10px; border-top-right-radius: 10px;
    }
    QTabBar::tab:hover { color: #e8edf2; background-color: rgba(255,255,255,0.04); }
    QTabBar::tab:selected { color: #4FC3F7; border-bottom: 2px solid #4FC3F7; background-color: rgba(255,255,255,0.05); font-weight: 700; }

    QCheckBox { color: #e8edf2; spacing: 8px; background: transparent; }
    QCheckBox::indicator { width: 19px; height: 19px; border: 2px solid rgba(79,195,247,0.4); border-radius: 6px; background-color: #1a2330; }
    QCheckBox::indicator:hover { border-color: #4FC3F7; }
    QCheckBox::indicator:checked { background-color: #4FC3F7; border-color: #4FC3F7; image: url(:/icons/check.png); }

    QSpinBox {
        background-color: rgba(50,64,82,0.7); color: #e8edf2;
        border: 1px solid rgba(120,150,180,0.20); border-radius: 8px; padding: 6px; min-width: 60px;
    }
    QSpinBox:focus { border-color: #4FC3F7; }

    QSlider::groove:horizontal { height: 6px; background-color: rgba(79,195,247,0.14); border-radius: 3px; }
    QSlider::sub-page:horizontal { background-color: #4FC3F7; border-radius: 3px; }
    QSlider::handle:horizontal { width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; background-color: #22303f; border: 2px solid #4FC3F7; }
    QSlider::handle:horizontal:hover { background-color: #2c3c4d; }

    QTextEdit { background-color: rgba(10,15,22,0.95); color: #a5d8be; border: none; border-radius: 12px; padding: 10px; selection-background-color: rgba(79,195,247,0.5); font-family: "Menlo","Consolas",monospace; font-size: 12px; }
    QScrollArea { background-color: transparent; border: none; }

    QScrollBar:vertical { background-color: transparent; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical { background-color: rgba(79,195,247,0.35); border-radius: 5px; min-height: 24px; }
    QScrollBar::handle:vertical:hover { background-color: rgba(79,195,247,0.55); }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

    QStatusBar { background-color: rgba(24,34,48,0.6); color: #8a95a3; border-top: 1px solid rgba(79,195,247,0.10); }
    QStatusBar::item { border: none; }

    QMenu { background-color: #1a2330; color: #e8edf2; border: 1px solid #2a3646; border-radius: 10px; padding: 6px; }
    QMenu::item { padding: 7px 20px; border-radius: 6px; }
    QMenu::item:selected { background-color: rgba(79,195,247,0.14); }

    QSplitter::handle { background-color: rgba(79,195,247,0.12); border-radius: 2px; }
"""


def detect_system_theme(*_, **__) -> str:
    """Определяет текущую тему операционной системы: 'light' или 'dark'."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return "light"
        hints = app.styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        return "light"
    except Exception:
        return "light"


def resolve_theme_mode(mode: str) -> str:
    """Приводит выбранный режим к фактическому 'light'/'dark' (учитывая system)."""
    if mode in ("light", "dark"):
        return mode
    return detect_system_theme()


def _palette_for(mode: str) -> tuple[QPalette, str]:
    """Возвращает (palette, css) для факт. режима 'light'/'dark'."""
    if mode == "dark":
        return _dark_palette(), DARK_STYLE
    return _light_palette(), LIGHT_STYLE


def _light_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#f0f7fd"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#0f0f10"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#f4f9fd"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#0f0f10"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#0f0f10"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#229ED9"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f0f10"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#99a2ad"))
    return pal


def _dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#141d29"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e8edf2"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#1a2330"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#22303f"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e8edf2"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#2a3848"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e8edf2"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#4FC3F7"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#0f1620"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#22303f"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8edf2"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6b7683"))
    return pal


# --------------------------------------------------------------------------- #
#  Публичный API (обратная совместимость)
# --------------------------------------------------------------------------- #

def get_stylesheet_for(mode: str) -> str:
    """Возвращает CSS-стиль для режима 'light'|'dark'|'system'."""
    resolved = resolve_theme_mode(mode)
    return DARK_STYLE if resolved == "dark" else LIGHT_STYLE


def get_palette_for(mode: str) -> QPalette:
    """Возвращает QPalette для режима 'light'|'dark'|'system'."""
    resolved = resolve_theme_mode(mode)
    return _dark_palette() if resolved == "dark" else _light_palette()


# -- reverse-compatible aliases -------------------------------------------- #
GLASSMORPHISM_STYLE = LIGHT_STYLE
_CLASSIC_DARK = DARK_STYLE


def get_glassmorphism_style() -> str:
    """Обратная совместимость: светлая тема."""
    return LIGHT_STYLE


def get_classic_dark_style() -> str:
    """Обратная совместимость: тёмная тема."""
    return DARK_STYLE
