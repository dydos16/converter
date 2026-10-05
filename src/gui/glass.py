"""
Виджеты «жидкого стекла».

Всё рисуется через QPainter со сглаживанием: QSS заливает фон под border-radius
без антиалиасинга, отсюда «лесенка» на скруглениях. Анимации — QVariantAnimation
по одному числу на виджет, перерисовывается только сам виджет.

Тема берётся из палитры окна (styles.get_palette_for), поэтому смена темы
перекрашивает всё без перезапуска.
"""
from __future__ import annotations

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
)

from src.gui.styles import tokens_for, ACCENT, GREEN, RED

PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 1   # int 0..100, -1 = ошибка, None = в очереди
META_ROLE = Qt.ItemDataRole.UserRole + 2       # вторая строка элемента: размер / причина

OUT = QEasingCurve.Type.OutCubic
SPRING = QEasingCurve.Type.OutBack


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


def font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setPixelSize(size)
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


# --------------------------------------------------------------------------- #
#  Карточка
# --------------------------------------------------------------------------- #

class GlassGroup(QWidget):
    """Замена QGroupBox: заголовок над стеклянной карточкой."""
    TITLE_H = 28

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._highlight = Tween(self, 200)
        top = self.TITLE_H if title else 4
        self.setContentsMargins(4, top + 2, 4, 8)

    def setHighlighted(self, on: bool):
        self._highlight.to(1 if on else 0)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        top = self.TITLE_H if self._title else 3
        card = QRectF(self.rect()).adjusted(3, top, -3, -6)
        hl = self._highlight.value
        paint_glass(p, card, 20, t, t["glass_top"], t["glass_bottom"], shadow=t["shadow"],
                    rim_top=mix(t["rim_top"], ACCENT, hl), rim_bottom=mix(t["rim_bottom"], ACCENT, hl))
        if hl > 0:
            p.fillPath(rounded(card, 20), alpha(ACCENT, .06 * hl))
        if self._title:
            p.setPen(t["secondary"])
            p.setFont(font(12, QFont.Weight.DemiBold))
            p.drawText(QRectF(12, 0, card.width(), top - 7),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self._title)


# --------------------------------------------------------------------------- #
#  Кнопка
# --------------------------------------------------------------------------- #

class GlassButton(_Hoverable, QPushButton):
    """Кнопка-капсула. setProperty('primary', True) — акцентная синяя."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._init_hover()
        self._press = Tween(self, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        self._press.to(1, 90)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._press.to(0, 380, SPRING)
        super().mouseReleaseEvent(e)

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(self._font()).horizontalAdvance(self.text()) + 48, 40)

    def _font(self) -> QFont:
        return font(15 if self.property("primary") else 13, QFont.Weight.DemiBold)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = QRectF(self.rect()).adjusted(2, 1, -2, -3)
        s = 1 - .04 * self._press.value
        p.translate(r.center())
        p.scale(s, s)
        p.translate(-r.center())
        radius = r.height() / 2
        h = self._hover.value
        primary = bool(self.property("primary"))

        if not self.isEnabled():
            paint_glass(p, r, radius, t, t["track"], t["track"],
                        rim_top=alpha(t["rim_top"], .3), rim_bottom=alpha(t["rim_bottom"], .3))
            fg = t["disabled"]
        elif primary:
            top = mix(QColor("#3D9BFF"), QColor("#6CB4FF"), h * .6)
            bottom = mix(QColor("#0A6FE8"), QColor("#1E86FF"), h * .6)
            body = paint_glass(p, r, radius, t, top, bottom,
                               shadow=alpha(ACCENT, .28 + .22 * h - .15 * self._press.value),
                               rim_top=QColor(255, 255, 255, 150), rim_bottom=QColor(0, 50, 140, 70))
            # Блик на верхней половине — то самое «стекло»
            gloss = QLinearGradient(r.topLeft(), QPointF(r.left(), r.center().y()))
            gloss.setColorAt(0, QColor(255, 255, 255, 80))
            gloss.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(body, gloss)
            fg = QColor("#FFFFFF")
        else:
            paint_glass(p, r, radius, t, mix(t["control"], t["control_hover"], h),
                        mix(alpha(t["control"], t["control"].alphaF() * .8), t["control_hover"], h * .8),
                        shadow=alpha(t["shadow"], t["shadow"].alphaF() * (1 + h)))
            fg = t["text"]

        p.setFont(self._font())
        p.setPen(fg)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())


# --------------------------------------------------------------------------- #
#  Сегментированный переключатель + стек страниц с плавной сменой
# --------------------------------------------------------------------------- #

class Segmented(QWidget):
    currentChanged = Signal(int)
    PAD = 3

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self._items = items
        self._index = 0
        self._hover_i = -1
        self._pos = Tween(self, 320)
        fm = QFontMetrics(font(13, QFont.Weight.DemiBold))
        self._seg = max(fm.horizontalAdvance(s) for s in items) + 44
        self.setFixedSize(int(self._seg * len(items) + self.PAD * 2), 38)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _at(self, x: float) -> int:
        return max(0, min(len(self._items) - 1, int((x - self.PAD) // self._seg)))

    def setCurrentIndex(self, i: int):
        if i == self._index:
            return
        self._index = i
        self._pos.to(i, 340, QEasingCurve.Type.OutQuint)
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
        track = QRectF(self.rect()).adjusted(0, 0, 0, -1)
        paint_glass(p, track, track.height() / 2, t, t["track"], t["track"],
                    rim_top=alpha(t["rim_bottom"], .4), rim_bottom=alpha(t["rim_top"], .5))
        pill = QRectF(self.PAD + self._pos.value * self._seg, self.PAD, self._seg, track.height() - self.PAD * 2)
        paint_glass(p, pill, pill.height() / 2, t, t["thumb"], alpha(t["thumb"], t["thumb"].alphaF() * .85),
                    shadow=t["shadow"])
        for i, label in enumerate(self._items):
            seg = QRectF(self.PAD + i * self._seg, 0, self._seg, track.height())
            near = max(0.0, 1 - abs(self._pos.value - i))  # насколько индикатор над этим сегментом
            p.setFont(font(13, QFont.Weight.DemiBold if near > .5 else QFont.Weight.Medium))
            p.setPen(mix(t["secondary"] if self._hover_i != i else t["text"], t["text"], near))
            p.drawText(seg, Qt.AlignmentFlag.AlignCenter, label)


class FadeStack(QStackedWidget):
    """QStackedWidget, где новая страница проявляется и чуть всплывает."""

    def setCurrentIndex(self, i: int):
        if i == self.currentIndex():
            return
        super().setCurrentIndex(i)
        page = self.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        anim = QVariantAnimation(self)
        anim.setDuration(260)
        anim.setEasingCurve(OUT)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.valueChanged.connect(effect.setOpacity)
        # Эффект рендерит страницу в буфер — снимаем его, как только анимация закончилась
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)


# --------------------------------------------------------------------------- #
#  Поля ввода
# --------------------------------------------------------------------------- #

def _paint_field(w: QWidget, p: QPainter, hover: float, focused: bool) -> QRectF:
    t = T(w)
    r = QRectF(w.rect()).adjusted(1, 1, -1, -2)
    base = mix(t["field"], t["control_hover"], hover * .7)
    paint_glass(p, r, min(12.0, r.height() / 2), t, base, alpha(base, base.alphaF() * .9),
                shadow=alpha(t["shadow"], t["shadow"].alphaF() * .6),
                rim_top=ACCENT if focused else None, rim_bottom=ACCENT if focused else None)
    return r


class GlassCombo(_Hoverable, QComboBox):

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
        popup.popup_under(self)

    def hidePopup(self):
        if getattr(self, "_popup", None) is not None:
            self._popup.close()

    def _choose(self, i: int):
        self.setCurrentIndex(i)
        self.activated.emit(i)

    def sizeHint(self) -> QSize:
        # Ширина по нашему шрифту, а не по метрикам стиля — иначе текст обрезается
        fm = QFontMetrics(font(14, QFont.Weight.DemiBold))
        widest = max((fm.horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=60)
        return QSize(widest + 64, 36)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = _paint_field(self, p, self._hover.value if self.isEnabled() else 0, False)
        big = r.height() >= 38
        p.setFont(font(14 if big else 13, QFont.Weight.DemiBold))
        p.setPen(t["text"] if self.isEnabled() else t["disabled"])
        text_rect = r.adjusted(14, 0, -34, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   p.fontMetrics().elidedText(self.currentText(), Qt.TextElideMode.ElideRight, int(text_rect.width())))
        # Шеврон
        cx, cy = r.right() - 18, r.center().y()
        p.setPen(QPen(t["secondary"], 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPointF(cx - 4, cy - 2))
        path.lineTo(cx, cy + 2)
        path.lineTo(cx + 4, cy - 2)
        p.drawPath(path)


class GlassSpin(_Hoverable, QSpinBox):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_hover()
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFrame(False)
        self.setMinimumHeight(36)

    def sizeHint(self) -> QSize:
        s = super().sizeHint()
        return QSize(s.width() + 28, 36)

    def paintEvent(self, e):
        # Текст рисует вложенный QLineEdit; здесь только подложка
        _paint_field(self, painter(self), self._hover.value, self.hasFocus())


class Toggle(QCheckBox):
    """Переключатель в стиле iOS вместо галочки."""
    W, H = 42, 25

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._pos = Tween(self, 240)
        self.toggled.connect(lambda on: self._pos.to(1 if on else 0, 300, SPRING if on else OUT))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setChecked(self, on: bool):
        super().setChecked(on)
        if not self.isVisible():
            self._pos.jump(1 if on else 0)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(font(13))
        return QSize(self.W + 12 + fm.horizontalAdvance(self.text()) + 4, max(self.H, fm.height()) + 6)

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
        p.setFont(font(13))
        p.setPen(t["text"] if self.isEnabled() else t["disabled"])
        p.drawText(QRectF(self.W + 12, 0, self.width() - self.W - 12, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


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
        self.setFixedHeight(6)

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
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0, QColor("#5AB0FF"))
        g.setColorAt(1, ACCENT)
        p.fillPath(fill, g)
        if self._shine.state() == QVariantAnimation.State.Running:
            x = (self._shine.currentValue() or 0) * (w + 80) - 80
            sg = QLinearGradient(x, 0, x + 80, 0)
            sg.setColorAt(0, QColor(255, 255, 255, 0))
            sg.setColorAt(.5, QColor(255, 255, 255, 110))
            sg.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(fill, sg)


# --------------------------------------------------------------------------- #
#  Список файлов
# --------------------------------------------------------------------------- #

class FileDelegate(QStyledItemDelegate):
    ROW = 50

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ROW)

    def paint(self, p: QPainter, option, index):
        t = T(option.widget)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect).adjusted(2, 2, -2, -2)
        if option.state & QStyle.StateFlag.State_Selected:
            p.fillPath(rounded(r, 12), t["selected"])
        elif option.state & QStyle.StateFlag.State_MouseOver:
            p.fillPath(rounded(r, 12), t["hover"])

        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        meta = index.data(META_ROLE) or ""
        progress = index.data(PROGRESS_ROLE)
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        invalid = brush is not None

        # Бейдж с расширением
        badge = QRectF(r.left() + 8, r.center().y() - 16, 32, 32)
        tint = RED if invalid else ACCENT
        p.fillPath(rounded(badge, 9), alpha(tint, .14))
        p.setPen(tint)
        p.setFont(font(9, QFont.Weight.Bold))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, Path(name).suffix[1:].upper()[:4] or "?")

        right = r.right() - 12
        if progress is not None:
            right = self._paint_status(p, t, r, progress) - 14

        text_left = badge.right() + 12
        width = int(right - text_left)
        p.setPen(brush.color() if invalid else t["text"])
        p.setFont(font(13, QFont.Weight.Medium))
        p.drawText(QRectF(text_left, r.top() + 7, width, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, width))
        p.setPen(t["secondary"])
        p.setFont(font(11))
        p.drawText(QRectF(text_left, r.top() + 25, width, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(meta, Qt.TextElideMode.ElideRight, width))
        p.restore()

    @staticmethod
    def _paint_status(p: QPainter, t: dict, r: QRectF, progress: int) -> float:
        cy = r.center().y()
        if progress >= 100 or progress < 0:
            c = QPointF(r.right() - 22, cy)
            color = GREEN if progress >= 100 else RED
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(c, 9, 9)
            p.setPen(QPen(QColor("#FFFFFF"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            if progress >= 100:
                path = QPainterPath(QPointF(c.x() - 4, c.y()))
                path.lineTo(c.x() - 1, c.y() + 3)
                path.lineTo(c.x() + 4, c.y() - 3)
                p.drawPath(path)
            else:
                p.drawLine(QPointF(c.x() - 3, c.y() - 3), QPointF(c.x() + 3, c.y() + 3))
                p.drawLine(QPointF(c.x() + 3, c.y() - 3), QPointF(c.x() - 3, c.y() + 3))
            return c.x() - 9
        bar = QRectF(r.right() - 132, cy - 2.5, 120, 5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(t["track"])
        p.drawRoundedRect(bar, 2.5, 2.5)
        p.setBrush(ACCENT)
        p.drawRoundedRect(QRectF(bar.left(), bar.top(), max(5.0, bar.width() * progress / 100), 5), 2.5, 2.5)
        p.setPen(t["secondary"])
        p.setFont(font(11, QFont.Weight.Medium))
        label = QRectF(bar.left() - 44, cy - 8, 38, 16)
        p.drawText(label, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{progress}%")
        return label.left()


class FileList(QListWidget):
    """Список файлов с подсказкой, когда он пуст."""

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
        # Пиктограмма: лист со стрелкой вниз
        sheet = QRectF(c.x() - 18, c.y() - 58, 36, 44)
        p.setPen(QPen(t["secondary"], 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(sheet, 7, 7)
        arrow = QPainterPath(QPointF(c.x(), sheet.top() + 12))
        arrow.lineTo(c.x(), sheet.bottom() - 12)
        arrow.moveTo(c.x() - 6, sheet.bottom() - 18)
        arrow.lineTo(c.x(), sheet.bottom() - 12)
        arrow.lineTo(c.x() + 6, sheet.bottom() - 18)
        p.drawPath(arrow)
        p.setPen(t["text"])
        p.setFont(font(15, QFont.Weight.DemiBold))
        p.drawText(QRectF(0, c.y() - 4, self.viewport().width(), 22), Qt.AlignmentFlag.AlignCenter,
                   "Перетащите файлы сюда")
        p.setPen(t["secondary"])
        p.setFont(font(12))
        p.drawText(QRectF(0, c.y() + 20, self.viewport().width(), 18), Qt.AlignmentFlag.AlignCenter,
                   "или нажмите «Добавить файлы»")


# --------------------------------------------------------------------------- #
#  Всплывающее уведомление
# --------------------------------------------------------------------------- #

class Toast(QWidget):
    """Уведомление внизу окна вместо модальных QMessageBox."""
    COLORS = {"info": ACCENT, "success": GREEN, "error": RED}

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
        width = min(fm.horizontalAdvance(text) + 64, self.parentWidget().width() - 40)
        self.resize(int(width), 48)
        self.reposition()
        self.show()
        self.raise_()
        self._shown.to(1, 420, SPRING)
        self._timer.start(ms)

    def reposition(self):
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 96)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        k = self._shown.value
        p.setOpacity(max(0.0, min(1.0, k)))
        p.translate(0, (1 - k) * 14)
        r = QRectF(self.rect()).adjusted(4, 3, -4, -7)
        paint_glass(p, r, r.height() / 2, t, alpha(t["popup"], .92), alpha(t["popup"], .86),
                    shadow=alpha(QColor(0, 0, 0), .18))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.COLORS.get(self._kind, ACCENT))
        p.drawEllipse(QPointF(r.left() + 20, r.center().y()), 4, 4)
        p.setPen(t["text"])
        p.setFont(font(13, QFont.Weight.Medium))
        text_rect = r.adjusted(34, 0, -16, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
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
        fm = QFontMetrics(font(13, QFont.Weight.Medium))
        self._body_w = max(fm.horizontalAdvance(t) for t in items) + 64

    # --- размещение
    def _body(self) -> QRectF:
        return QRectF(self.rect()).adjusted(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)

    def popup_under(self, anchor: QWidget):
        self._body_w = max(self._body_w, anchor.width())
        self._show_at(anchor.mapToGlobal(QPoint(0, anchor.height() + 4)), anchor.height() + 8)

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
                p.setPen(QPen(fg, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                cx, cy = r.left() + 14, r.center().y()
                tick = QPainterPath(QPointF(cx - 4, cy))
                tick.lineTo(cx - 1, cy + 3)
                tick.lineTo(cx + 4, cy - 3)
                p.drawPath(tick)
            p.setPen(fg)
            p.setFont(font(13, QFont.Weight.Medium))
            p.drawText(r.adjusted(30, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self._items[i])
        if len(self._items) > self._rows:              # тонкий индикатор прокрутки
            track_h = body.height() - self.PAD * 4
            bar_h = max(24.0, track_h * self._rows / len(self._items))
            y = body.top() + self.PAD * 2 + (track_h - bar_h) * self._scroll / (len(self._items) - self._rows)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(t["track"])
            p.drawRoundedRect(QRectF(body.right() - 6, y, 3, bar_h), 1.5, 1.5)
