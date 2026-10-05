"""
Тема «жидкое стекло» для File Converter Pro.

Цвета живут здесь в одном месте. Элементы управления рисуются вручную
в src/gui/glass.py (QSS не сглаживает фон под border-radius — отсюда «лесенка»),
QSS остаётся только для текста, всплывающих списков, меню и скроллбаров.

Режимы: 'light' | 'dark' | 'system' (следует за ОС через QStyleHints).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPalette, QColor, QPainter, QRadialGradient

ACCENT = QColor("#0A84FF")
GREEN = QColor("#34C759")
RED = QColor("#FF3B30")


def _c(r, g, b, a=1.0) -> QColor:
    c = QColor(r, g, b)
    c.setAlphaF(a)
    return c


LIGHT = dict(
    base=QColor("#E9EDF3"),
    blobs=[("#8FB8FF", 150), ("#FFC4A3", 120), ("#A8EBCF", 120), ("#D3BDFF", 100)],
    text=QColor("#1D1D1F"), secondary=QColor("#6E6E73"), disabled=_c(60, 60, 67, .35),
    glass_top=_c(255, 255, 255, .70), glass_bottom=_c(255, 255, 255, .42),
    rim_top=_c(255, 255, 255, .95), rim_bottom=_c(255, 255, 255, .30),
    shadow=_c(30, 40, 80, .10),
    control=_c(255, 255, 255, .62), control_hover=_c(255, 255, 255, .95),
    thumb=_c(255, 255, 255, 1.0),
    field=_c(255, 255, 255, .72), track=_c(118, 118, 128, .16),
    selected=_c(10, 132, 255, .14), hover=_c(0, 0, 0, .045),
    popup=QColor("#FFFFFF"), popup_border=_c(0, 0, 0, .10),
)

DARK = dict(
    base=QColor("#0B0D12"),
    blobs=[("#2D4BFF", 110), ("#FF5E7A", 60), ("#17C3A0", 70), ("#8A5CFF", 90)],
    text=QColor("#F5F5F7"), secondary=QColor("#98989D"), disabled=_c(235, 235, 245, .30),
    glass_top=_c(255, 255, 255, .13), glass_bottom=_c(255, 255, 255, .055),
    rim_top=_c(255, 255, 255, .30), rim_bottom=_c(255, 255, 255, .04),
    shadow=_c(0, 0, 0, .30),
    control=_c(255, 255, 255, .10), control_hover=_c(255, 255, 255, .18),
    thumb=_c(255, 255, 255, .24),
    field=_c(0, 0, 0, .25), track=_c(120, 120, 128, .32),
    selected=_c(10, 132, 255, .30), hover=_c(255, 255, 255, .06),
    popup=QColor("#1C1E24"), popup_border=_c(255, 255, 255, .12),
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
    t = {k: css(v) for k, v in _tokens(mode).items() if isinstance(v, QColor)}
    a = css(ACCENT)
    return f"""
    QWidget {{ color: {t['text']}; font-size: 13px; }}
    QLabel {{ background: transparent; }}
    QLabel[secondary="true"], QLabel[big="true"] {{ color: {t['secondary']}; }}
    QLabel[big="true"] {{ font-weight: 600; }}
    QLabel[title="true"] {{ font-size: 26px; font-weight: 700; }}
    QLabel[subtitle="true"] {{ color: {t['secondary']}; }}
    QToolTip {{ background: {t['popup']}; color: {t['text']}; border: 1px solid {t['popup_border']}; padding: 5px 8px; }}

    QComboBox QAbstractItemView {{
        background: {t['popup']}; color: {t['text']}; border: 1px solid {t['popup_border']};
        padding: 4px; outline: none; selection-background-color: {a}; selection-color: #FFFFFF;
    }}
    QComboBox QAbstractItemView::item {{ min-height: 26px; padding: 0 8px; }}

    QAbstractSpinBox {{ background: transparent; border: none; padding: 0 12px; }}
    QListWidget {{ background: transparent; border: none; outline: none; }}
    QTextEdit {{ background: transparent; border: none; selection-background-color: {a}; }}

    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 1px; }}
    QScrollBar::handle:vertical {{ background: {t['track']}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['secondary']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QStatusBar {{ background: transparent; }}
    QStatusBar::item {{ border: none; }}
    QStatusBar QLabel {{ color: {t['secondary']}; font-size: 12px; padding: 0 6px; }}

    QMenu {{ background: {t['popup']}; border: 1px solid {t['popup_border']}; padding: 5px; }}
    QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {a}; color: #FFFFFF; }}
    QMenu::separator {{ height: 1px; background: {t['popup_border']}; margin: 4px 8px; }}
    """


def get_palette_for(mode: str) -> QPalette:
    """QPalette для режима 'light'|'dark'|'system' (по ней же виджеты узнают тему)."""
    t = _tokens(mode)
    pal = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window, t["base"]),
        (QPalette.ColorRole.WindowText, t["text"]),
        (QPalette.ColorRole.Base, t["popup"]),
        (QPalette.ColorRole.AlternateBase, t["popup"]),
        (QPalette.ColorRole.Text, t["text"]),
        (QPalette.ColorRole.Button, t["popup"]),
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


# Центры пятен фона в долях окна и радиус в долях ширины
_BLOB_LAYOUT = [(0.12, 0.08, 0.55), (0.92, 0.22, 0.50), (0.28, 0.98, 0.60), (0.86, 0.92, 0.45)]


def paint_backdrop(painter: QPainter, rect: QRectF, dark: bool) -> None:
    """Рисует мягкий цветной фон, сквозь который «видно» стеклянные карточки."""
    t = tokens_for(dark)
    painter.fillRect(rect, t["base"])
    w, h = rect.width(), rect.height()
    for (cx, cy, r), (color, alpha) in zip(_BLOB_LAYOUT, t["blobs"]):
        g = QRadialGradient(QPointF(rect.left() + cx * w, rect.top() + cy * h), r * max(w, h))
        c = QColor(color)
        c.setAlpha(alpha)
        g.setColorAt(0, c)
        c.setAlpha(0)
        g.setColorAt(1, c)
        painter.fillRect(rect, g)
