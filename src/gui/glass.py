"""
Виджеты в стиле Telegram для iOS: сгруппированные списки со строками,
очередь файлов как список чатов, плавающая стеклянная панель вкладок,
круглые кнопки навигации.

Всё рисуется через QPainter со сглаживанием: QSS заливает фон под border-radius
без антиалиасинга, отсюда «лесенка» на скруглениях. Анимации — QVariantAnimation
по одному числу на виджет, перерисовывается только сам виджет.

Тема берётся из палитры приложения (styles.get_palette_for), поэтому смена темы
перекрашивает всё без перезапуска.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

from PySide6.QtCore import (
    Qt, QRectF, QPointF, QPoint, QSize, QTimer, QEasingCurve, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QLinearGradient, QPen, QPalette, QFont, QFontMetrics, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QComboBox, QSpinBox, QCheckBox, QSlider, QListWidget,
    QStyledItemDelegate, QStyle, QStackedWidget, QGraphicsOpacityEffect, QAbstractSpinBox,
    QLabel, QVBoxLayout, QHBoxLayout,
)

from src.gui.styles import tokens_for, ACCENT, GREEN, RED

PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 1   # int 0..100, -1 = ошибка, None = не в работе
META_ROLE = Qt.ItemDataRole.UserRole + 2       # вторая строка элемента: размер · папка

OUT = QEasingCurve.Type.OutCubic
SPRING = QEasingCurve.Type.OutBack
AlignLeftV = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
AlignRightV = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


# --------------------------------------------------------------------------- #
#  Общие помощники
# --------------------------------------------------------------------------- #

def T(widget: QWidget) -> dict:
    """Токены темы. Смотрим палитру приложения, а не виджета: QSS `background: transparent`
    подменяет Window в палитре виджета, и тема определилась бы как тёмная."""
    return tokens_for(QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128)


def mix(a: QColor, b: QColor, k: float) -> QColor:
    k = max(0.0, min(1.0, k))
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * k,
        a.greenF() + (b.greenF() - a.greenF()) * k,
        a.blueF() + (b.blueF() - a.blueF()) * k,
        a.alphaF() + (b.alphaF() - a.alphaF()) * k,
    )


def alpha(c: QColor, a: float) -> QColor:
    c = QColor(c)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


def font(size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setPixelSize(round(size))
    f.setWeight(weight)
    return f


def rounded(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def painter(widget: QWidget) -> QPainter:
    p = QPainter(widget)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return p


_SHADOW_PAD = 16
_shadow_cache: dict = {}


def _shadow_pixmap(size, radius: float, color: QColor, dpr: float) -> QPixmap:
    """Мягкая тень вокруг плашки. Рисуется один раз на размер и цвет, дальше — из кэша."""
    key = (round(size.width()), round(size.height()), round(radius), color.rgba(), dpr)
    pm = _shadow_cache.get(key)
    if pm is not None:
        return pm
    if len(_shadow_cache) > 256:
        _shadow_cache.clear()
    w, h = size.width() + _SHADOW_PAD * 2, size.height() + _SHADOW_PAD * 2
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    body = QRectF(_SHADOW_PAD, _SHADOW_PAD, size.width(), size.height())
    for spread, k in ((1.0, .55), (3.0, .30), (6.0, .15), (11.0, .07)):
        p.setBrush(alpha(color, color.alphaF() * k))
        r = body.adjusted(-spread * .6, spread * .5, spread * .6, spread)
        p.drawRoundedRect(r, radius + spread * .6, radius + spread * .6)
    # Под самим стеклом тени нет — иначе она бы его затемнила
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.setBrush(Qt.GlobalColor.black)
    p.drawRoundedRect(body, radius, radius)
    p.end()
    _shadow_cache[key] = pm
    return pm


def paint_glass(p: QPainter, rect: QRectF, radius: float, t: dict,
                top: QColor, bottom: QColor, shadow: QColor | None = None,
                rim_top: QColor | None = None, rim_bottom: QColor | None = None) -> QPainterPath:
    """Стеклянная плашка: мягкая тень снаружи, заливка, светлая кромка сверху."""
    body = rounded(rect, radius)
    if shadow is not None and shadow.alphaF() > 0:
        p.drawPixmap(rect.topLeft() - QPointF(_SHADOW_PAD, _SHADOW_PAD),
                     _shadow_pixmap(rect.size(), radius, shadow, p.device().devicePixelRatioF()))
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0, top)
    g.setColorAt(1, bottom)
    p.fillPath(body, g)
    rg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    rg.setColorAt(0, rim_top or t["rim_top"])
    rg.setColorAt(1, rim_bottom or t["rim_bottom"])
    p.setPen(QPen(rg, 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(rounded(rect.adjusted(.5, .5, -.5, -.5), max(0.0, radius - .5)))
    return body


class Tween:
    """Одно анимируемое число; каждый шаг перерисовывает владельца."""

    def __init__(self, owner: QWidget, ms: int = 180, value: float = 0.0):
        self.value = value
        self._owner = owner
        self._ms = ms
        self._a = QVariantAnimation(owner)
        self._a.valueChanged.connect(self._step)
        self.finished = self._a.finished

    def _step(self, v):
        self.value = float(v)
        self._owner.update()

    def to(self, target: float, ms: int | None = None, curve=OUT):
        target = float(target)
        if self._a.state() != QVariantAnimation.State.Running and abs(self.value - target) < 1e-4:
            return
        self._a.stop()
        self._a.setDuration(ms or self._ms)
        self._a.setEasingCurve(curve)
        self._a.setStartValue(self.value)
        self._a.setEndValue(target)
        self._a.start()

    def jump(self, v: float):
        self._a.stop()
        self.value = float(v)
        self._owner.update()


class _Hoverable:
    """Плавная подсветка при наведении для любого QWidget."""

    def _init_hover(self):
        self._hover = Tween(self, 160)

    def enterEvent(self, e):
        self._hover.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover.to(0, 260)
        super().leaveEvent(e)


class _Pressable(_Hoverable):
    """Наведение + «вдавливание» с пружинкой при отпускании."""

    def _init_press(self):
        self._init_hover()
        self._press = Tween(self, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        self._press.to(1, 90)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._press.to(0, 380, SPRING)
        super().mouseReleaseEvent(e)

    def _scale(self, p: QPainter, r: QRectF, depth: float = .05):
        s = 1 - depth * self._press.value
        p.translate(r.center())
        p.scale(s, s)
        p.translate(-r.center())


# --------------------------------------------------------------------------- #
#  Значки (рисуем сами: SF Symbols из Qt недоступны, а шрифтовые символы
#  выглядят по-разному на разных ОС). Координаты — сетка 24×24.
# --------------------------------------------------------------------------- #

def _polar(r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return 12 + r * math.cos(a), 12 + r * math.sin(a)


def draw_icon(p: QPainter, name: str, rect: QRectF, color: QColor, weight: float = 1.8) -> None:
    path = QPainterPath()
    fill = False

    def line(*pts):
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)

    if name == "plus":
        line((12, 5), (12, 19)); line((5, 12), (19, 12))
    elif name == "folder":
        path.moveTo(3.5, 8); path.lineTo(3.5, 6.8); path.quadTo(3.5, 5.5, 4.8, 5.5); path.lineTo(9, 5.5)
        path.lineTo(11, 7.5); path.lineTo(19.2, 7.5); path.quadTo(20.5, 7.5, 20.5, 8.8); path.lineTo(20.5, 17.2)
        path.quadTo(20.5, 18.5, 19.2, 18.5); path.lineTo(4.8, 18.5); path.quadTo(3.5, 18.5, 3.5, 17.2)
        path.closeSubpath()
        line((3.5, 10), (20.5, 10))
    elif name == "trash":
        line((4.5, 7), (19.5, 7)); line((9.5, 7), (9.5, 4.8), (14.5, 4.8), (14.5, 7))
        line((6.5, 7), (7.4, 19.5), (16.6, 19.5), (17.5, 7))
        line((10.2, 10.5), (10.4, 16)); line((13.8, 10.5), (13.6, 16))
    elif name == "arrows":
        line((4.5, 8.5), (19, 8.5)); line((15, 4.5), (19, 8.5), (15, 12.5))
        line((19.5, 15.5), (5, 15.5)); line((9, 11.5), (5, 15.5), (9, 19.5))
    elif name == "gear":
        pts = []
        for k in range(8):
            a = k * 45
            pts += [_polar(7.0, a - 15), _polar(9.4, a - 8), _polar(9.4, a + 8), _polar(7.0, a + 15)]
        line(*pts, pts[0])
        path.addEllipse(QPointF(12, 12), 3, 3)
    elif name == "list":
        for y in (7, 12, 17):
            line((5, y), (5.01, y)); line((9, y), (19.5, y))
    elif name == "moon":
        a, b = QPainterPath(), QPainterPath()
        a.addEllipse(QPointF(12, 12), 8, 8)
        b.addEllipse(QPointF(16.5, 8), 7, 7)
        path, fill = a.subtracted(b), True
    elif name == "bolt":
        line((13.5, 2.5), (5, 13.5), (11.2, 13.5), (10.2, 21.5), (19, 10.2), (12.8, 10.2), (13.5, 2.5))
        fill = True
    elif name == "bell":
        path.moveTo(6, 16.5); path.lineTo(6, 11); path.quadTo(6, 5.5, 12, 5.5); path.quadTo(18, 5.5, 18, 11)
        path.lineTo(18, 16.5); path.lineTo(19.5, 18); path.lineTo(4.5, 18); path.closeSubpath()
        path.moveTo(10, 20.3); path.quadTo(12, 22, 14, 20.3)
        line((12, 3.5), (12, 5.5))
    elif name == "tag":
        line((4, 12.5), (11.5, 5), (19, 5), (19, 12.5), (11.5, 20), (4, 12.5))
        path.addEllipse(QPointF(15.2, 8.8), 1.3, 1.3)
    elif name == "doc":
        line((6.5, 3.5), (14, 3.5), (18.5, 8), (18.5, 20.5), (6.5, 20.5), (6.5, 3.5))
        line((14, 3.5), (14, 8), (18.5, 8))
    elif name == "clock":
        path.addEllipse(QPointF(12, 12), 8.5, 8.5)
        line((12, 7.5), (12, 12), (15, 14))
    elif name == "check":
        line((5, 12.5), (9.5, 17), (19, 7.5))
    elif name == "check2":
        line((2.5, 12.5), (6.5, 16.5), (13.5, 8)); line((10.5, 15.5), (11.5, 16.5), (18.5, 8))
    elif name == "excl":
        line((12, 6.5), (12, 13.5)); line((12, 17.5), (12, 17.51))
    elif name == "info":
        line((12, 10.5), (12, 17.5)); line((12, 6.8), (12, 6.81))
    elif name == "chevron_ud":
        line((8.5, 9.5), (12, 6), (15.5, 9.5)); line((8.5, 14.5), (12, 18), (15.5, 14.5))
    elif name == "image":
        path.addRoundedRect(QRectF(3.5, 5, 17, 14), 2.5, 2.5)
        line((3.5, 16), (9, 11), (13, 15), (15.5, 12.5), (20.5, 17))
        path.addEllipse(QPointF(15.5, 9), 1.5, 1.5)
    elif name == "box":
        line((12, 3), (20, 7.5), (20, 16.5), (12, 21), (4, 16.5), (4, 7.5), (12, 3))
        line((4, 7.5), (12, 12), (20, 7.5)); line((12, 12), (12, 21))

    p.save()
    p.translate(rect.topLeft())
    p.scale(rect.width() / 24, rect.height() / 24)
    if fill:
        p.fillPath(path, color)
    else:
        p.setPen(QPen(color, weight, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    p.restore()


# --------------------------------------------------------------------------- #
#  Сгруппированный список: секция с заголовком, карточка, строки
# --------------------------------------------------------------------------- #

class IconBadge(QWidget):
    """Цветной квадратик со значком, как у пунктов настроек Telegram."""

    def __init__(self, icon: str, color: QColor | str, size: int = 28, parent=None):
        super().__init__(parent)
        self._icon, self._color = icon, QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(self.rect())
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, self._color.lighter(112))
        g.setColorAt(1, self._color)
        p.fillPath(rounded(r, r.width() * .26), g)
        inset = r.width() * .19
        draw_icon(p, self._icon, r.adjusted(inset, inset, -inset, -inset), QColor("#FFFFFF"), 2.1)


class _Card(QWidget):
    RADIUS = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlight = Tween(self, 200)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = QRectF(self.rect())
        p.fillPath(rounded(r, self.RADIUS), t["card"])
        hl = self._highlight.value
        if hl > 0:
            p.fillPath(rounded(r, self.RADIUS), alpha(ACCENT, .06 * hl))
            p.setPen(QPen(alpha(ACCENT, hl), 1.5))
            p.drawPath(rounded(r.adjusted(.75, .75, -.75, -.75), self.RADIUS - .75))
        # Тонкие разделители между строками, с отступом от левого края как в iOS
        rows = [self.layout().itemAt(i).widget() for i in range(self.layout().count())]
        rows = [w for w in rows if w is not None and w.isVisible() and hasattr(w, "separator_inset")]
        p.setPen(QPen(t["separator"], 0))
        for w in rows[:-1]:
            y = w.y() + w.height() - .25
            p.drawLine(QPointF(w.x() + w.separator_inset, y), QPointF(r.right(), y))


class InsetSection(QWidget):
    """Секция сгруппированного списка: ЗАГОЛОВОК, белая карточка со строками, подпись снизу."""

    def __init__(self, title: str = "", footer: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if title:
            header = QLabel(title.upper())
            header.setProperty("section", True)
            header.setContentsMargins(16, 0, 0, 0)
            lay.addWidget(header)
        self.card = _Card()
        self.rows = QVBoxLayout(self.card)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        lay.addWidget(self.card, 1)
        if footer:
            note = QLabel(footer)
            note.setProperty("footer", True)
            note.setWordWrap(True)
            note.setContentsMargins(16, 0, 16, 0)
            lay.addWidget(note)

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.rows.addWidget(widget, stretch)
        return widget

    def setHighlighted(self, on: bool):
        self.card._highlight.to(1 if on else 0)


class Row(QWidget):
    """Строка списка: [значок] Название ............ элемент управления.
    Клик по строке открывает выпадающий список или переключает тумблер — как в iOS."""

    def __init__(self, title: str, control: QWidget | None = None,
                 icon: str | None = None, color: str | None = None, parent=None):
        super().__init__(parent)
        self.control = control
        self._press = Tween(self, 120)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 7, 14, 7)
        lay.setSpacing(12)
        if icon:
            lay.addWidget(IconBadge(icon, color or ACCENT))
        self.label = QLabel(title)
        self.label.setProperty("row", True)
        lay.addWidget(self.label)
        lay.addStretch(1)
        if control is not None:
            lay.addWidget(control)
        self.separator_inset = 14 + (28 + 12 if icon else 0)
        self.setMinimumHeight(46)
        if isinstance(control, (QComboBox, QCheckBox)):
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        c = self.control
        if isinstance(c, (QComboBox, QCheckBox)) and c.isEnabled():
            self._press.to(1, 80)
            c.showPopup() if isinstance(c, QComboBox) else c.toggle()

    def mouseReleaseEvent(self, e):
        self._press.to(0, 320)

    def paintEvent(self, e):
        if self._press.value > 0:
            p = painter(self)
            p.fillPath(rounded(QRectF(self.rect()).adjusted(4, 2, -4, -2), 10),
                       alpha(T(self)["hover"], T(self)["hover"].alphaF() * 2 * self._press.value))


class SliderRow(QWidget):
    """Строка с ползунком: название и значение сверху, ползунок во всю ширину снизу."""

    def __init__(self, title: str, slider: QSlider, suffix: str = "%", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 9, 14, 6)
        lay.setSpacing(2)
        top = QHBoxLayout()
        label = QLabel(title)
        label.setProperty("row", True)
        value = QLabel(f"{slider.value()}{suffix}")
        value.setProperty("value", True)
        slider.valueChanged.connect(lambda v: value.setText(f"{v}{suffix}"))
        top.addWidget(label)
        top.addStretch(1)
        top.addWidget(value)
        lay.addLayout(top)
        lay.addWidget(slider)
        self.separator_inset = 14


class PageHeader(QWidget):
    """Крупный заголовок страницы, как в iOS, с кнопками справа.
    За пустое место заголовка можно таскать окно — на маке шапка окна прозрачная."""

    def __init__(self, title: str, buttons: list[QWidget] = (), parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(8)
        text = QVBoxLayout()
        text.setSpacing(0)
        self.title = QLabel(title)
        self.title.setProperty("title", True)
        self.subtitle = QLabel("")
        self.subtitle.setProperty("subtitle", True)
        self.subtitle.hide()
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        lay.addLayout(text)
        lay.addStretch(1)
        for b in buttons:
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)

    def setSubtitle(self, text: str):
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))

    def mousePressEvent(self, e):
        handle = self.window().windowHandle()
        if e.button() == Qt.MouseButton.LeftButton and handle is not None:
            handle.startSystemMove()


# --------------------------------------------------------------------------- #
#  Кнопки
# --------------------------------------------------------------------------- #

class PrimaryButton(_Pressable, QPushButton):
    """Синяя кнопка-капсула главного действия."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._init_press()

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(font(15, QFont.Weight.DemiBold)).horizontalAdvance(self.text()) + 56, 50)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = QRectF(self.rect()).adjusted(2, 1, -2, -4)
        self._scale(p, r, .03)
        radius = r.height() / 2
        if not self.isEnabled():
            p.fillPath(rounded(r, radius), t["track"])
            fg = t["disabled"]
        else:
            h = self._hover.value
            body = paint_glass(p, r, radius, t, mix(QColor("#2B8CFF"), QColor("#4C9EFF"), h * .7),
                               mix(ACCENT, QColor("#1A84FF"), h * .7),
                               shadow=alpha(ACCENT, .28 + .2 * h - .15 * self._press.value),
                               rim_top=QColor(255, 255, 255, 140), rim_bottom=QColor(0, 50, 140, 60))
            gloss = QLinearGradient(r.topLeft(), QPointF(r.left(), r.center().y()))
            gloss.setColorAt(0, QColor(255, 255, 255, 70))
            gloss.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(body, gloss)
            fg = QColor("#FFFFFF")
        p.setFont(font(15, QFont.Weight.DemiBold))
        p.setPen(fg)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())


class IconButton(_Pressable, QPushButton):
    """Круглая стеклянная кнопка со значком — как кнопки в навигации iOS 26."""

    def __init__(self, icon: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self._icon = icon
        self._init_press()
        self.setToolTip(tooltip)
        self.setFixedSize(44, 44)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = QRectF(self.rect()).adjusted(4, 3, -4, -5)
        self._scale(p, r, .08)
        paint_glass(p, r, r.height() / 2, t, mix(t["control"], t["control_hover"], self._hover.value),
                    t["control"], shadow=alpha(t["shadow"], t["shadow"].alphaF() * .8))
        color = t["text"] if self.isEnabled() else t["disabled"]
        draw_icon(p, self._icon, r.adjusted(9, 9, -9, -9), color, 2.0)


# --------------------------------------------------------------------------- #
#  Плавающая панель вкладок + стек страниц с плавной сменой
# --------------------------------------------------------------------------- #

class TabBar(QWidget):
    """Стеклянная панель вкладок внизу окна, как в Telegram для iOS 26."""
    currentChanged = Signal(int)
    MARGIN = 14      # поле под тень вокруг панели
    PAD = 5
    ITEM_W = 92
    BAR_H = 58

    def __init__(self, items: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self._items = items
        self._index = 0
        self._hover_i = -1
        self._pos = Tween(self, 340)
        self.setFixedSize(self.ITEM_W * len(items) + self.PAD * 2 + self.MARGIN * 2, self.BAR_H + self.MARGIN * 2)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def currentIndex(self) -> int:
        return self._index

    def _at(self, x: float) -> int:
        return max(0, min(len(self._items) - 1, int((x - self.MARGIN - self.PAD) // self.ITEM_W)))

    def setCurrentIndex(self, i: int):
        if i == self._index:
            return
        self._index = i
        self._pos.to(i, 360, QEasingCurve.Type.OutQuint)
        self.currentChanged.emit(i)

    def mousePressEvent(self, e):
        self.setCurrentIndex(self._at(e.position().x()))

    def mouseMoveEvent(self, e):
        i = self._at(e.position().x())
        if i != self._hover_i:
            self._hover_i = i
            self.update()

    def leaveEvent(self, e):
        self._hover_i = -1
        self.update()

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        bar = QRectF(self.MARGIN, self.MARGIN, self.width() - self.MARGIN * 2, self.BAR_H)
        paint_glass(p, bar, bar.height() / 2, t, t["bar"], alpha(t["bar"], t["bar"].alphaF() * .94),
                    shadow=alpha(t["shadow"], t["shadow"].alphaF() * 1.4))
        pill = QRectF(bar.left() + self.PAD + self._pos.value * self.ITEM_W, bar.top() + self.PAD,
                      self.ITEM_W, bar.height() - self.PAD * 2)
        p.fillPath(rounded(pill, pill.height() / 2), t["thumb"])
        for i, (label, icon) in enumerate(self._items):
            x = bar.left() + self.PAD + i * self.ITEM_W
            near = max(0.0, 1 - abs(self._pos.value - i))   # насколько индикатор над этой вкладкой
            base = t["text"] if self._hover_i == i else mix(t["text"], t["secondary"], .35)
            color = mix(base, ACCENT, near)
            draw_icon(p, icon, QRectF(x + self.ITEM_W / 2 - 12, bar.top() + 8, 24, 24), color, 1.9)
            p.setFont(font(11, QFont.Weight.DemiBold if near > .5 else QFont.Weight.Medium))
            p.setPen(color)
            p.drawText(QRectF(x, bar.top() + 34, self.ITEM_W, 16), Qt.AlignmentFlag.AlignCenter, label)


class FadeStack(QStackedWidget):
    """QStackedWidget, где новая страница плавно проявляется."""

    def setCurrentIndex(self, i: int):
        if i == self.currentIndex():
            return
        super().setCurrentIndex(i)
        page = self.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        anim = QVariantAnimation(self)
        anim.setDuration(240)
        anim.setEasingCurve(OUT)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(effect.setOpacity)
        # Эффект рендерит страницу в буфер — снимаем его, как только анимация закончилась
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)


# --------------------------------------------------------------------------- #
#  Элементы управления внутри строк
# --------------------------------------------------------------------------- #

class GlassCombo(_Hoverable, QComboBox):
    """Значение серым справа и ⌃⌄ — как всплывающее меню в строке настроек iOS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_hover()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def showPopup(self):
        items = [self.itemText(i) for i in range(self.count())]
        if not items:
            return
        popup = GlassPopup(items, self.currentIndex(), self)
        popup.triggered.connect(self._choose)
        # Меню удаляется при закрытии — забываем ссылку, чтобы не тронуть удалённый объект
        popup.destroyed.connect(lambda: setattr(self, "_popup", None))
        self._popup = popup
        popup.popup_under(self, align_right=True)

    def hidePopup(self):
        if getattr(self, "_popup", None) is not None:
            self._popup.close()

    def _choose(self, i: int):
        self.setCurrentIndex(i)
        self.activated.emit(i)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(font(14))
        widest = max((fm.horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=40)
        return QSize(widest + 28, 30)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = QRectF(self.rect())
        color = mix(t["secondary"], t["text"], self._hover.value * .7) if self.isEnabled() else t["disabled"]
        p.setFont(font(14))
        p.setPen(color)
        text_rect = r.adjusted(0, 0, -20, 0)
        p.drawText(text_rect, AlignRightV,
                   p.fontMetrics().elidedText(self.currentText(), Qt.TextElideMode.ElideRight, int(text_rect.width())))
        draw_icon(p, "chevron_ud", QRectF(r.right() - 16, r.center().y() - 8, 16, 16), color, 2.0)


class GlassSpin(_Hoverable, QSpinBox):
    """Число в серой «таблетке» справа в строке."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_hover()
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFrame(False)
        self.setAlignment(AlignRightV)

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width() + 24, 32)

    def paintEvent(self, e):
        # Текст рисует вложенный QLineEdit; здесь только подложка
        t = T(self)
        p = painter(self)
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        p.fillPath(rounded(r, 9), mix(t["field"], alpha(t["field"], t["field"].alphaF() * 1.6), self._hover.value))
        if self.hasFocus():
            p.setPen(QPen(ACCENT, 1.5))
            p.drawPath(rounded(r.adjusted(.5, .5, -.5, -.5), 8.5))


class Toggle(QCheckBox):
    """Переключатель iOS. Подпись — в строке слева, сам тумблер без текста."""
    W, H = 44, 26

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._pos = Tween(self, 240)
        self.toggled.connect(lambda on: self._pos.to(1 if on else 0, 300, SPRING if on else OUT))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setChecked(self, on: bool):
        super().setChecked(on)
        if not self.isVisible():
            self._pos.jump(1 if on else 0)

    def sizeHint(self) -> QSize:
        return QSize(self.W + 2, self.H + 4)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        k = self._pos.value
        track = QRectF(1, (self.height() - self.H) / 2, self.W, self.H)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mix(t["track"], GREEN, k))
        p.drawRoundedRect(track, self.H / 2, self.H / 2)
        d = self.H - 4
        knob = QRectF(track.left() + 2 + (self.W - self.H) * min(1.0, max(0.0, k)), track.top() + 2, d, d)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(knob.translated(0, 1.2))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(knob)


class GlassSlider(QSlider):
    K = 22  # диаметр ручки

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._press = Tween(self, 160)
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _frac(self) -> float:
        span = self.maximum() - self.minimum()
        return (self.value() - self.minimum()) / span if span else 0.0

    def _value_at(self, x: float) -> int:
        k = (x - self.K / 2) / max(1.0, self.width() - self.K)
        return round(self.minimum() + max(0.0, min(1.0, k)) * (self.maximum() - self.minimum()))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(True)
            self.setValue(self._value_at(e.position().x()))
            self._press.to(1, 140)

    def mouseMoveEvent(self, e):
        if self.isSliderDown():
            self.setValue(self._value_at(e.position().x()))

    def mouseReleaseEvent(self, e):
        self.setSliderDown(False)
        self._press.to(0, 320, SPRING)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        cy = self.height() / 2
        x = self.K / 2 + (self.width() - self.K) * self._frac()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(t["track"])
        p.drawRoundedRect(QRectF(self.K / 2, cy - 2, self.width() - self.K, 4), 2, 2)
        p.setBrush(ACCENT)
        p.drawRoundedRect(QRectF(self.K / 2, cy - 2, x - self.K / 2, 4), 2, 2)
        r = self.K / 2 * (1 + .12 * self._press.value)
        p.setBrush(QColor(0, 0, 0, 35))
        p.drawEllipse(QPointF(x, cy + 1.2), r + .5, r + .5)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(0, 0, 0, 25), .8))
        p.drawEllipse(QPointF(x, cy), r, r)


class GlassProgress(QWidget):
    """Тонкая полоса прогресса: плавно догоняет значение, пока идёт работа — бежит блик."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._shown = Tween(self, 500)
        self._shine = QVariantAnimation(self)
        self._shine.setDuration(1500)
        self._shine.setStartValue(0.0)
        self._shine.setEndValue(1.0)
        self._shine.setLoopCount(-1)
        self._shine.valueChanged.connect(self.update)
        self.setFixedHeight(5)

    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        self._value = max(0, min(100, int(v)))
        self._shown.to(self._value)
        running = 0 < self._value < 100
        if running and self._shine.state() != QVariantAnimation.State.Running:
            self._shine.start()
        elif not running:
            self._shine.stop()

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = QRectF(self.rect())
        rad = r.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(t["track"])
        p.drawRoundedRect(r, rad, rad)
        w = r.width() * self._shown.value / 100
        if w <= 0:
            return
        fill = rounded(QRectF(0, 0, max(w, r.height()), r.height()), rad)
        p.fillPath(fill, ACCENT)
        if self._shine.state() == QVariantAnimation.State.Running:
            x = (self._shine.currentValue() or 0) * (w + 80) - 80
            sg = QLinearGradient(x, 0, x + 80, 0)
            sg.setColorAt(0, QColor(255, 255, 255, 0))
            sg.setColorAt(.5, QColor(255, 255, 255, 110))
            sg.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(fill, sg)


# --------------------------------------------------------------------------- #
#  Очередь файлов — как список чатов Telegram
# --------------------------------------------------------------------------- #

# Пары градиентов аватарок Telegram
_AVATAR = {
    "red": ("#FF845E", "#D45246"), "orange": ("#FEBB5B", "#F68136"), "violet": ("#B694F9", "#6C61DF"),
    "green": ("#9AD164", "#46BA43"), "cyan": ("#53EDD6", "#28C9B7"), "blue": ("#5BCBE3", "#359AD4"),
    "pink": ("#FF8AAC", "#D95574"),
}
_EXT_COLOR = {
    **dict.fromkeys(("pdf",), "red"),
    **dict.fromkeys(("doc", "docx", "odt", "rtf", "txt", "md"), "blue"),
    **dict.fromkeys(("xls", "xlsx", "csv", "ods"), "green"),
    **dict.fromkeys(("ppt", "pptx", "pps", "ppsx", "odp"), "orange"),
    **dict.fromkeys(("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"), "violet"),
    **dict.fromkeys(("heic", "heif"), "pink"),
    **dict.fromkeys(("html", "json", "xml"), "cyan"),
}


class FileDelegate(QStyledItemDelegate):
    ROW = 62
    AVATAR = 44

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ROW)

    def paint(self, p: QPainter, option, index):
        t = T(option.widget)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:   # как выделенный чат в Telegram для macOS: синяя плашка, белый текст
            p.fillPath(rounded(r.adjusted(4, 2, -4, -2), 11), ACCENT)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            p.fillPath(rounded(r.adjusted(4, 2, -4, -2), 11), t["hover"])

        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        meta = index.data(META_ROLE) or ""
        progress = index.data(PROGRESS_ROLE)
        invalid = index.data(Qt.ItemDataRole.ForegroundRole) is not None
        ext = Path(name).suffix[1:].lower()

        # Аватарка: градиент Telegram и расширение вместо инициалов
        av = QRectF(r.left() + 14, r.center().y() - self.AVATAR / 2, self.AVATAR, self.AVATAR)
        top, bottom = _AVATAR["red" if invalid else _EXT_COLOR.get(ext, "blue")]
        g = QLinearGradient(av.topLeft(), av.bottomLeft())
        g.setColorAt(0, QColor(top))
        g.setColorAt(1, QColor(bottom))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(av)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(font(12 if len(ext) <= 3 else 10.5, QFont.Weight.Bold))
        p.drawText(av, Qt.AlignmentFlag.AlignCenter, ext.upper()[:4] or "?")

        fg = QColor("#FFFFFF") if selected else (RED if invalid else t["text"])
        sub = QColor(255, 255, 255, 200) if selected else t["secondary"]
        text_left = av.right() + 12
        right = r.right() - 16
        if progress is not None:
            right = self._paint_status(p, t, r, progress, selected) - 10

        width = int(right - text_left)
        p.setPen(fg)
        p.setFont(font(14, QFont.Weight.DemiBold))
        p.drawText(QRectF(text_left, r.top() + 11, width, 20), AlignLeftV,
                   p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, width))
        p.setPen(sub)
        p.setFont(font(13))
        p.drawText(QRectF(text_left, r.top() + 32, width, 18), AlignLeftV,
                   p.fontMetrics().elidedText(meta, Qt.TextElideMode.ElideRight, width))

        # Разделитель под строкой — от начала текста, как в списке чатов
        if index.row() < index.model().rowCount() - 1 and not selected:
            p.setPen(QPen(t["separator"], 0))
            p.drawLine(QPointF(text_left, r.bottom() + .5), QPointF(r.right() - 4, r.bottom() + .5))
        p.restore()

    @staticmethod
    def _paint_status(p: QPainter, t: dict, r: QRectF, progress: int, selected: bool) -> float:
        """Статус справа, как у сообщений: часы, кольцо прогресса, ✓✓ или красный «!». Возвращает левый край."""
        cx, cy = r.right() - 28, r.center().y()
        white = QColor("#FFFFFF")
        if progress < 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(white if selected else RED)
            p.drawEllipse(QPointF(cx, cy), 11, 11)
            draw_icon(p, "excl", QRectF(cx - 9, cy - 9, 18, 18), RED if selected else white, 2.6)
            return cx - 11
        if progress >= 100:
            draw_icon(p, "check2", QRectF(cx - 12, cy - 12, 24, 24), white if selected else ACCENT, 2.0)
            return cx - 12
        if progress == 0:
            draw_icon(p, "clock", QRectF(cx - 10, cy - 10, 20, 20), white if selected else t["secondary"], 1.8)
            return cx - 10
        ring = QRectF(cx - 10, cy - 10, 20, 20)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(alpha(white, .35) if selected else t["track"], 2.2))
        p.drawEllipse(ring)
        p.setPen(QPen(white if selected else ACCENT, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(ring, 90 * 16, -int(360 * 16 * progress / 100))
        p.setFont(font(11, QFont.Weight.Medium))
        p.setPen(white if selected else t["secondary"])
        label = QRectF(cx - 52, cy - 8, 36, 16)
        p.drawText(label, AlignRightV, f"{progress}%")
        return label.left()


class FileList(QListWidget):
    """Список файлов с заглушкой, когда он пуст."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(FileDelegate(self))
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count():
            return
        t = T(self)
        p = painter(self.viewport())
        c = QRectF(self.viewport().rect()).center()
        circle = QRectF(c.x() - 34, c.y() - 78, 68, 68)
        g = QLinearGradient(circle.topLeft(), circle.bottomLeft())
        g.setColorAt(0, QColor(_AVATAR["blue"][0]))
        g.setColorAt(1, QColor(_AVATAR["blue"][1]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(circle)
        draw_icon(p, "doc", circle.adjusted(18, 18, -18, -18), QColor("#FFFFFF"), 2.0)
        w = self.viewport().width()
        p.setPen(t["text"])
        p.setFont(font(17, QFont.Weight.DemiBold))
        p.drawText(QRectF(0, c.y() + 2, w, 24), Qt.AlignmentFlag.AlignCenter, "Нет файлов")
        p.setPen(t["secondary"])
        p.setFont(font(13))
        p.drawText(QRectF(0, c.y() + 28, w, 20), Qt.AlignmentFlag.AlignCenter,
                   "Перетащите файлы в окно или нажмите «+» вверху")


# --------------------------------------------------------------------------- #
#  Всплывающее уведомление
# --------------------------------------------------------------------------- #

class Toast(QWidget):
    """Тёмная плашка-уведомление над панелью вкладок, как в Telegram."""
    ICONS = {"info": ("info", ACCENT), "success": ("check", GREEN), "error": ("excl", RED)}
    BOTTOM = 166   # над кнопкой «Конвертировать» и панелью вкладок

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._text = ""
        self._kind = "info"
        self._shown = Tween(self, 260)
        self._shown.finished.connect(lambda: self._shown.value < .01 and self.hide())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._shown.to(0, 220))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def show_message(self, text: str, kind: str = "info", ms: int = 3200):
        self._text, self._kind = text, kind
        fm = QFontMetrics(font(13, QFont.Weight.Medium))
        width = min(fm.horizontalAdvance(text) + 70, self.parentWidget().width() - 40)
        self.resize(int(width), 50)
        self.reposition()
        self.show()
        self.raise_()
        self._shown.to(1, 420, SPRING)
        self._timer.start(ms)

    def reposition(self):
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - self.BOTTOM)

    def paintEvent(self, e):
        p = painter(self)
        k = self._shown.value
        p.setOpacity(max(0.0, min(1.0, k)))
        p.translate(0, (1 - k) * 14)
        r = QRectF(self.rect()).adjusted(4, 3, -4, -7)
        p.drawPixmap(r.topLeft() - QPointF(_SHADOW_PAD, _SHADOW_PAD),
                     _shadow_pixmap(r.size(), 14, QColor(0, 0, 0, 70), p.device().devicePixelRatioF()))
        dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        # В тёмной теме плашка светлее карточек, иначе сливается с ними
        p.fillPath(rounded(r, 14), QColor(64, 64, 68, 245) if dark else QColor(30, 30, 32, 236))
        icon, color = self.ICONS.get(self._kind, self.ICONS["info"])
        dot = QRectF(r.left() + 12, r.center().y() - 11, 22, 22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(dot)
        draw_icon(p, icon, dot.adjusted(3, 3, -3, -3), QColor("#FFFFFF"), 2.6)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(font(13, QFont.Weight.Medium))
        text_rect = r.adjusted(44, 0, -14, 0)
        p.drawText(text_rect, AlignLeftV,
                   p.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, int(text_rect.width())))


# --------------------------------------------------------------------------- #
#  Всплывающее меню (выпадающие списки, контекстное меню)
# --------------------------------------------------------------------------- #

class GlassPopup(QWidget):
    """Стеклянное меню со скруглёнными углами вместо квадратного системного."""
    triggered = Signal(int)
    ROW = 32
    PAD = 6
    MARGIN = _SHADOW_PAD   # поле под тень
    MAX_ROWS = 11

    def __init__(self, items: list[str], current: int = -1, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self._items = items
        self._current = current
        self._hover = max(current, 0)
        self._scroll = 0
        self._moved = False
        self._opened_at = 0.0
        self._shown = Tween(self, 200)
        self._rows = min(len(items), self.MAX_ROWS)
        fm = QFontMetrics(font(14, QFont.Weight.Medium))
        self._body_w = max(fm.horizontalAdvance(t) for t in items) + 64

    # --- размещение
    def _body(self) -> QRectF:
        return QRectF(self.rect()).adjusted(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)

    def popup_under(self, anchor: QWidget, align_right: bool = False):
        self._body_w = max(self._body_w, 160 if align_right else anchor.width())
        x = anchor.width() - self._body_w if align_right else 0
        self._show_at(anchor.mapToGlobal(QPoint(x, anchor.height() + 4)), anchor.height() + 8)

    def popup_at(self, global_pos: QPoint):
        self._show_at(global_pos, 0)

    def _show_at(self, top_left: QPoint, flip_by: int):
        h = self._rows * self.ROW + self.PAD * 2
        self.resize(self._body_w + self.MARGIN * 2, h + self.MARGIN * 2)
        pos = top_left - QPoint(self.MARGIN, self.MARGIN)
        screen = (self.parentWidget().screen() if self.parentWidget() else self.screen()).availableGeometry()
        if pos.y() + self.height() > screen.bottom():          # нет места снизу — открываемся вверх
            pos.setY(pos.y() - h - flip_by)
        pos.setX(max(screen.left(), min(pos.x(), screen.right() - self.width())))
        self.move(pos)
        self._scroll = max(0, min(self._current - self._rows // 2, len(self._items) - self._rows))
        self._opened_at = time.monotonic()
        self.show()
        self.setFocus()
        self._shown.to(1, 260, SPRING)

    # --- ввод
    def _row_at(self, y: float) -> int:
        i = int((y - self.MARGIN - self.PAD) // self.ROW) + self._scroll
        return i if 0 <= i < len(self._items) and self._body().contains(QPointF(self.MARGIN + 1, y)) else -1

    def mouseMoveEvent(self, e):
        self._moved = True
        i = self._row_at(e.position().y())
        if i >= 0 and i != self._hover:
            self._hover = i
            self.update()

    def mouseReleaseEvent(self, e):
        # Отпускание той же кнопки, что открыла меню, — не выбор
        if not self._moved and time.monotonic() - self._opened_at < .35:
            return
        i = self._row_at(e.position().y())
        if i >= 0:
            self._pick(i)

    def wheelEvent(self, e):
        step = -1 if e.angleDelta().y() > 0 else 1
        self._scroll = max(0, min(self._scroll + step, len(self._items) - self._rows))
        self.update()

    def keyPressEvent(self, e):
        key = e.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._hover = max(0, min(len(self._items) - 1, self._hover + (1 if key == Qt.Key.Key_Down else -1)))
            self._scroll = max(min(self._scroll, self._hover), self._hover - self._rows + 1)
            self.update()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._pick(self._hover)
        elif key == Qt.Key.Key_Escape:
            self.close()

    def _pick(self, i: int):
        self.close()
        self.triggered.emit(i)

    # --- отрисовка
    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        k = self._shown.value
        p.setOpacity(max(0.0, min(1.0, k * 1.4)))
        body = self._body()
        s = .94 + .06 * k                              # раскрывается от верхнего края
        p.translate(body.center().x(), body.top())
        p.scale(s, s)
        p.translate(-body.center().x(), -body.top())
        shape = paint_glass(p, body, 14, t, alpha(t["popup"], .97), alpha(t["popup"], .93),
                            shadow=QColor(0, 0, 0, 60))
        p.setClipPath(shape)
        for row in range(self._rows):
            i = row + self._scroll
            r = QRectF(body.left() + self.PAD, body.top() + self.PAD + row * self.ROW,
                       body.width() - self.PAD * 2, self.ROW)
            hovered = i == self._hover
            if hovered:
                p.fillPath(rounded(r, 8), ACCENT)
            fg = QColor("#FFFFFF") if hovered else t["text"]
            if i == self._current:
                draw_icon(p, "check", QRectF(r.left() + 6, r.center().y() - 8, 16, 16), fg, 2.2)
            p.setPen(fg)
            p.setFont(font(14, QFont.Weight.Medium))
            p.drawText(r.adjusted(30, 0, -10, 0), AlignLeftV, self._items[i])
        if len(self._items) > self._rows:              # тонкий индикатор прокрутки
            track_h = body.height() - self.PAD * 4
            bar_h = max(24.0, track_h * self._rows / len(self._items))
            y = body.top() + self.PAD * 2 + (track_h - bar_h) * self._scroll / (len(self._items) - self._rows)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(t["track"])
            p.drawRoundedRect(QRectF(body.right() - 6, y, 3, bar_h), 1.5, 1.5)
