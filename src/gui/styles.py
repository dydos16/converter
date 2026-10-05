"""
Тема в стиле Telegram для iOS: серый сгруппированный фон, белые карточки,
тёмная тема — чёрный фон и графитовые карточки.

Цвета живут здесь в одном месте. Элементы управления рисуются вручную
в src/gui/glass.py (QSS не сглаживает фон под border-radius — отсюда «лесенка»),
QSS остаётся только для текста, всплывающих списков и скроллбаров.

Режимы: 'light' | 'dark' | 'system' (следует за ОС через QStyleHints).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

ACCENT = QColor("#007AFF")
GREEN = QColor("#34C759")
RED = QColor("#FF3B30")


def _c(r, g, b, a=1.0) -> QColor:
    c = QColor(r, g, b)
    c.setAlphaF(a)
    return c


LIGHT = dict(
    base=QColor("#F2F2F7"), card=QColor("#FFFFFF"),
    text=QColor("#000000"), secondary=QColor("#8E8E93"), disabled=_c(60, 60, 67, .30),
    separator=_c(60, 60, 67, .20),
    bar=_c(250, 250, 252, .86), rim_top=_c(255, 255, 255, .95), rim_bottom=_c(0, 0, 0, .06),
    shadow=_c(0, 0, 0, .10),
    control=_c(255, 255, 255, .92), control_hover=_c(255, 255, 255, 1.0),
    thumb=_c(118, 118, 128, .14),
    field=_c(118, 118, 128, .12), track=_c(120, 120, 128, .16),
    hover=_c(0, 0, 0, .04),
    popup=QColor("#FFFFFF"), popup_border=_c(0, 0, 0, .08),
)

DARK = dict(
    base=QColor("#000000"), card=QColor("#1C1C1E"),
    text=QColor("#FFFFFF"), secondary=QColor("#8D8D93"), disabled=_c(235, 235, 245, .30),
    separator=_c(84, 84, 88, .60),
    bar=_c(36, 36, 38, .86), rim_top=_c(255, 255, 255, .16), rim_bottom=_c(255, 255, 255, .04),
    shadow=_c(0, 0, 0, .50),
    control=_c(44, 44, 46, .92), control_hover=_c(58, 58, 60, 1.0),
    thumb=_c(255, 255, 255, .12),
    field=_c(118, 118, 128, .24), track=_c(120, 120, 128, .36),
    hover=_c(255, 255, 255, .05),
    popup=QColor("#2C2C2E"), popup_border=_c(255, 255, 255, .10),
)


def css(c: QColor) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alphaF():.3f})"


def tokens_for(dark: bool) -> dict:
    return DARK if dark else LIGHT


def detect_system_theme() -> str:
    """Текущая тема ОС: 'light' или 'dark'."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
        return "dark"
    return "light"


def _tokens(mode: str) -> dict:
    resolved = mode if mode in ("light", "dark") else detect_system_theme()
    return tokens_for(resolved == "dark")


def get_stylesheet_for(mode: str) -> str:
    """QSS для режима 'light'|'dark'|'system'."""
    t = {k: css(v) for k, v in _tokens(mode).items()}
    a = css(ACCENT)
    return f"""
    QWidget {{ color: {t['text']}; font-size: 13px; }}
    QLabel {{ background: transparent; }}
    QLabel[title="true"] {{ font-size: 28px; font-weight: 700; }}
    QLabel[subtitle="true"] {{ color: {t['secondary']}; font-size: 13px; }}
    QLabel[section="true"] {{ color: {t['secondary']}; font-size: 12px; }}
    QLabel[footer="true"] {{ color: {t['secondary']}; font-size: 12px; }}
    QLabel[row="true"] {{ font-size: 14px; }}
    QLabel[value="true"] {{ color: {t['secondary']}; font-size: 14px; }}
    QToolTip {{ background: {t['popup']}; color: {t['text']}; border: 1px solid {t['popup_border']}; padding: 5px 8px; }}

    QAbstractSpinBox {{ background: transparent; border: none; padding: 0 10px; font-size: 14px; }}
    QListWidget {{ background: transparent; border: none; outline: none; }}
    QTextEdit {{ background: transparent; border: none; selection-background-color: {a}; }}

    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 1px; }}
    QScrollBar::handle:vertical {{ background: {t['track']}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['secondary']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    """


def get_palette_for(mode: str) -> QPalette:
    """QPalette для режима 'light'|'dark'|'system' (по ней же виджеты узнают тему)."""
    t = _tokens(mode)
    pal = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window, t["base"]),
        (QPalette.ColorRole.WindowText, t["text"]),
        (QPalette.ColorRole.Base, t["card"]),
        (QPalette.ColorRole.AlternateBase, t["card"]),
        (QPalette.ColorRole.Text, t["text"]),
        (QPalette.ColorRole.Button, t["card"]),
        (QPalette.ColorRole.ButtonText, t["text"]),
        (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, QColor("#FFFFFF")),
        (QPalette.ColorRole.ToolTipBase, t["popup"]),
        (QPalette.ColorRole.ToolTipText, t["text"]),
        (QPalette.ColorRole.PlaceholderText, t["secondary"]),
        (QPalette.ColorRole.Link, ACCENT),
    ]:
        pal.setColor(role, color)
    return pal
