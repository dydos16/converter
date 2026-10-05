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
    Qt, QRect, QRectF, QPointF, QPoint, QSize, QTimer, QEasingCurve, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QLinearGradient, QRadialGradient, QPen, QPalette, QFont, QFontMetrics,
    QPixmap, QImage, QCursor,
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


_SHADOW_PAD = 36
_shadow_cache: dict = {}


def _shadow_pixmap(size, radius: float, color: QColor, dpr: float, reach: float = 33.0) -> QPixmap:
    """Мягкая тень вокруг плашки (как у Telegram: размытие ~30–40 pt, едва заметная).
    reach — как далеко тень выходит за плашку: должна помещаться в виджет, иначе обрежется квадратом.
    Рисуется один раз на размер и цвет, дальше — из кэша."""
    key = (round(size.width()), round(size.height()), round(radius), color.rgba(), dpr, round(reach))
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
    # Набор расширяющихся слоёв ≈ гауссова тень, смещённая на 1 pt вниз
    f = min(reach, _SHADOW_PAD - 2) / 33
    for spread, k in ((1.5, .30), (4, .24), (8, .18), (13, .12), (19, .08), (26, .05), (33, .03)):
        spread *= f
        p.setBrush(alpha(color, color.alphaF() * k))
        r = body.adjusted(-spread, -spread + f, spread, spread + f)
        p.drawRoundedRect(r, radius + spread, radius + spread)
    # Под самим стеклом тени нет — иначе она бы его затемнила
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.setBrush(Qt.GlobalColor.black)
    p.drawRoundedRect(body, radius, radius)
    p.end()
    _shadow_cache[key] = pm
    return pm


class Tween:
    """Одно анимируемое число по кривой; каждый шаг перерисовывает владельца."""

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


# --------------------------------------------------------------------------- #
#  Жидкое стекло — по мотивам реализации Telegram для iOS
#  (Telegram-iOS: GlassBackgroundComponent, LegacyGlassView, TouchEffect, LiquidLens)
# --------------------------------------------------------------------------- #

# Пружины Telegram: (масса, жёсткость, демпфирование)
LIFT_ON = (1.36, 568.0, 39.7)     # «подъём» стекла при нажатии — быстро, без перелёта
LIFT_OFF = (2.0, 460.0, 21.8)     # возврат — с заметным пружинящим перелётом


def is_dark() -> bool:
    return QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


class Spring:
    """Затухающий осциллятор, как анимации стекла в Telegram, вместо кривых QEasingCurve."""

    def __init__(self, owner: QWidget, value: float = 0.0, params=LIFT_OFF):
        self.value = self.target = float(value)
        self.velocity = 0.0
        self.params = params
        self._owner = owner
        self._timer = QTimer(owner)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._tick)
        self._last = 0.0

    @property
    def moving(self) -> bool:
        return self._timer.isActive()

    def to(self, target: float, params=None):
        self.target = float(target)
        if params:
            self.params = params
        if not self._timer.isActive():
            self._last = time.perf_counter()
            self._timer.start()

    def jump(self, value: float):
        self.value = self.target = float(value)
        self.velocity = 0.0
        self._timer.stop()
        self._owner.update()

    def _tick(self):
        now = time.perf_counter()
        dt = min(.05, now - self._last)
        self._last = now
        m, k, c = self.params
        steps = max(1, int(dt / .002))       # мелкие шаги — жёсткая пружина устойчива
        h = dt / steps
        for _ in range(steps):
            a = (-k * (self.value - self.target) - c * self.velocity) / m
            self.velocity += a * h
            self.value += self.velocity * h
        if abs(self.value - self.target) < 1e-3 and abs(self.velocity) < 1e-2:
            self.value, self.velocity = self.target, 0.0
            self._timer.stop()
        self._owner.update()


def jelly(w: float, h: float, stretch: QPointF, base: float) -> tuple[float, float, float, float]:
    """Растяжение «желе» вслед за курсором: (scale_x, scale_y, dx, dy).
    Формула из TouchEffect.swift: объём сохраняется, сдвиг до 24 pt."""
    h = max(1.0, h)
    aspect = w / h
    ax = stretch.x() / aspect
    length = math.hypot(ax, stretch.y())
    if length < 1e-6:
        return base, base, 0.0, 0.0
    nx, ny = ax / length, stretch.y() / length
    k = 1 - 1 / ((length / h) / (5 * aspect) + 1)
    t = ((h + 16 / aspect) / h - 1) * k * aspect
    if abs(nx) > abs(ny):
        d = abs(nx) - abs(ny)
        sx, sy = base * (1 + t * d), base / (1 + t * d)
    else:
        d = abs(ny) - abs(nx)
        sx, sy = base / (1 + t * d), base * (1 + t * d)
    return sx, sy, nx * 24 * k, ny * 24 * k


def _bezier_y(x: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Кубическая Безье (как CSS cubic-bezier): y по x."""
    lo, hi = 0.0, 1.0
    for _ in range(20):
        s = (lo + hi) / 2
        bx = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3
        lo, hi = (s, hi) if bx < x else (lo, s)
    s = (lo + hi) / 2
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s ** 2 * y2 + s ** 3


def glass_fill(dark: bool) -> QColor:
    """Заливка панели Telegram: белый 70% или почти чёрный (белый, смешанный с 89% чёрного) 85%."""
    return QColor(28, 28, 28, 217) if dark else QColor(255, 255, 255, 179)


def _rim_path(rect: QRectF, radius: float, lw: float) -> QPainterPath:
    """Кромка стекла как у Telegram: у верхнего левого и нижнего правого углов радиус полный,
    у двух других — чуть меньше. После обрезки по форме блик остаётся на двух углах по диагонали."""
    r = rect.adjusted(lw / 2, lw / 2, -lw / 2, -lw / 2)
    big = max(0.0, min(radius - lw / 2, r.width() / 2, r.height() / 2))
    small = max(0.0, big - lw * 1.33)
    path = QPainterPath(QPointF(r.left(), r.top() + big))
    path.arcTo(QRectF(r.left(), r.top(), 2 * big, 2 * big), 180, -90)
    path.lineTo(r.right() - small, r.top())
    path.arcTo(QRectF(r.right() - 2 * small, r.top(), 2 * small, 2 * small), 90, -90)
    path.lineTo(r.right(), r.bottom() - big)
    path.arcTo(QRectF(r.right() - 2 * big, r.bottom() - 2 * big, 2 * big, 2 * big), 0, -90)
    path.lineTo(r.left() + small, r.bottom())
    path.arcTo(QRectF(r.left(), r.bottom() - 2 * small, 2 * small, 2 * small), 270, -90)
    path.closeSubpath()
    return path


def frost(pm: QPixmap, blur_px: int) -> QPixmap:
    """Фон под стеклом: лёгкое размытие и усиленная насыщенность (в Telegram — 2 pt и матрица ×2)."""
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()
    if blur_px > 1 and w > blur_px and h > blur_px:
        small = img.scaled(w // blur_px, h // blur_px, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        img = small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    p = QPainter(img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Overlay)   # наложение на себя = ярче цвета
    p.setOpacity(.35)
    p.drawImage(0, 0, img.copy())
    p.end()
    out = QPixmap.fromImage(img)
    out.setDevicePixelRatio(pm.devicePixelRatio())
    return out


REFRACT_BAND = 12.0        # ширина полосы преломления у края, pt
REFRACT_SHIFT = 20.0       # насколько сдвигается фон у самого края, pt
_REFRACT_RINGS = 6
_ring_cache: dict = {}


def _refraction_rings(rect: QRectF, radius: float) -> list[tuple[QPainterPath, float, float]]:
    """Кольца от края к центру и масштаб фона в каждом — вместо сетки meshTransform Telegram."""
    key = (round(rect.x(), 1), round(rect.y(), 1), round(rect.width(), 1), round(rect.height(), 1), round(radius, 1))
    rings = _ring_cache.get(key)
    if rings is not None:
        return rings
    if len(_ring_cache) > 128:
        _ring_cache.clear()
    band = min(REFRACT_BAND, radius, rect.width() / 2, rect.height() / 2)
    step = band / _REFRACT_RINGS
    rings = []
    for i in range(_REFRACT_RINGS):
        e = i * step
        outer = rounded(rect.adjusted(e, e, -e, -e), max(0.0, radius - e))
        inner = rounded(rect.adjusted(e + step, e + step, -e - step, -e - step), max(0.0, radius - e - step))
        k = 1 - (e + step / 2) / band                                 # 1 у края → 0 к середине
        shift = REFRACT_SHIFT * _bezier_y(k, .816, .205, .581, .873)  # кривая смещения из LegacyGlassView
        # У края показываем фон, лежащий дальше наружу, — сжимаем его к центру
        sx = 1 / (1 + shift / max(1.0, rect.width() / 2))
        sy = 1 / (1 + shift / max(1.0, rect.height() / 2))
        rings.append((outer.subtracted(inner), sx, sy))
    _ring_cache[key] = rings
    return rings


def _draw_refracted(p: QPainter, pm: QPixmap, origin: QPointF, rect: QRectF, radius: float) -> None:
    c = rect.center()
    p.save()
    p.setClipPath(rounded(rect, radius))
    p.drawPixmap(origin, pm)
    for ring, sx, sy in _refraction_rings(rect, radius):
        p.save()
        p.setClipPath(ring)
        p.translate(c)
        p.scale(sx, sy)
        p.translate(-c)
        p.drawPixmap(origin, pm)
        p.restore()
    p.restore()


def grab_backdrop(source: QWidget, widget: QWidget, rect: QRectF, blur_px: int = 4):
    """Снимок того, что лежит под стеклом (source — виджет ниже, в том же окне),
    с полями под преломление. Возвращает (pixmap, точка в координатах widget) или None."""
    margin = REFRACT_SHIFT + 4
    area = rect.adjusted(-margin, -margin, margin, margin).toAlignedRect()
    win = widget.window()
    src_tl = source.mapFrom(win, widget.mapTo(win, area.topLeft()))
    region = QRect(src_tl, area.size()).intersected(source.rect())
    if region.isEmpty():
        return None
    pm = source.grab(region)
    return frost(pm, blur_px), QPointF(area.topLeft() + (region.topLeft() - src_tl))


def paint_liquid_glass(p: QPainter, rect: QRectF, radius: float, *, fill: QColor | None = None,
                       backdrop=None, rim: QColor | None = None, shadow: QColor | None = None,
                       reach: float = 33.0) -> QPainterPath:
    """Стекло как у Telegram: тень → преломлённый фон → полупрозрачная заливка → кромка 0,8 pt."""
    dark = is_dark()
    body = rounded(rect, radius)
    shadow = shadow if shadow is not None else QColor(0, 0, 0, 100 if dark else 22)
    if shadow.alpha():
        p.drawPixmap(rect.topLeft() - QPointF(_SHADOW_PAD, _SHADOW_PAD),
                     _shadow_pixmap(rect.size(), radius, shadow, p.device().devicePixelRatioF(), reach))
    if backdrop is not None:
        _draw_refracted(p, backdrop[0], backdrop[1], rect, radius)
    p.fillPath(body, fill if fill is not None else glass_fill(dark))
    lw = .8
    p.save()
    p.setClipPath(body)
    p.setPen(QPen(rim if rim is not None else QColor(255, 255, 255, 38 if dark else 153), lw))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(_rim_path(rect, radius, lw))
    p.restore()
    return body


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


class _GlassTouch(_Hoverable):
    """Отклик стекла на нажатие, как TouchEffect в Telegram: элемент «поднимается» (растёт),
    тянется за курсором как желе, под курсором — мягкое свечение; при отпускании пружинит назад."""
    LIFT = 20.0        # pressedSizeIncrease: на сколько pt вырастает больший размер
    MAX_SHIFT = 24.0   # насколько желе может сместиться за курсором

    def _init_touch(self):
        self._init_hover()
        self._lift = Spring(self)
        self._stretch_x = Spring(self)
        self._stretch_y = Spring(self)
        self._glow = Tween(self, 120)
        self._touch = QPointF()
        self._press_pos: QPointF | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_pos = QPointF(e.position())
            self._touch = QPointF(e.position())
            self._lift.to(1, LIFT_ON)
            self._glow.to(1, 120)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press_pos is not None:
            d = e.position() - self._press_pos
            self._stretch_x.to(d.x(), LIFT_ON)
            self._stretch_y.to(d.y(), LIFT_ON)
            self._touch = QPointF(e.position())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        self._lift.to(0, LIFT_OFF)
        self._stretch_x.to(0, LIFT_OFF)
        self._stretch_y.to(0, LIFT_OFF)
        self._glow.to(0, 220)
        super().mouseReleaseEvent(e)

    def _apply_touch(self, p: QPainter, r: QRectF):
        """Подъём + желе: сдвигает и масштабирует painter вокруг центра стекла."""
        base = 1 + self.LIFT * self._lift.value / max(r.width(), r.height())
        sx, sy, dx, dy = jelly(r.width(), r.height(), QPointF(self._stretch_x.value, self._stretch_y.value), base)
        k = self.MAX_SHIFT / 24
        c = r.center()
        p.translate(c.x() + dx * k, c.y() + dy * k)
        p.scale(sx, sy)
        p.translate(-c.x(), -c.y())

    def _paint_glow(self, p: QPainter, shape: QPainterPath):
        a = self._glow.value
        if a <= 0:
            return
        g = QRadialGradient(self._touch, 150)
        g.setColorAt(0, QColor(255, 255, 255, int(255 * .5 * .14 * a)))   # Telegram: 0,5 × непрозрачность 0,1
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillPath(shape, g)


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

class PrimaryButton(_GlassTouch, QPushButton):
    """Синяя кнопка-капсула главного действия: окрашенное стекло, «поднимается» при нажатии."""
    LIFT = 20.0
    MAX_SHIFT = 6.0
    BODY = QSize(316, 50)
    MARGIN = QSize(22, 16)   # поле под подъём, желе и тень

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._init_touch()

    def sizeHint(self) -> QSize:
        return self.BODY + self.MARGIN * 2

    def _body(self) -> QRectF:
        r = QRectF(self.rect())
        return QRectF(r.center().x() - self.BODY.width() / 2, r.center().y() - self.BODY.height() / 2,
                      self.BODY.width(), self.BODY.height())

    def hitButton(self, pos) -> bool:
        return self._body().contains(QPointF(pos))

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = self._body()
        radius = r.height() / 2
        if not self.isEnabled():
            p.fillPath(rounded(r, radius), t["track"])
            p.setFont(font(15, QFont.Weight.DemiBold))
            p.setPen(t["disabled"])
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())
            return
        self._apply_touch(p, r)
        h = self._hover.value
        base = RED if self.property("danger") else ACCENT     # «Остановить» — красная
        body = paint_liquid_glass(p, r, radius, fill=mix(base, base.lighter(115), h),
                                  rim=QColor(255, 255, 255, 110), shadow=alpha(base, .35), reach=10)
        self._paint_glow(p, body)
        p.setFont(font(15, QFont.Weight.DemiBold))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())


class IconButton(_GlassTouch, QPushButton):
    """Круглая стеклянная кнопка со значком — как кнопки навигации в Telegram для iOS 26."""
    LIFT = 10.0
    MAX_SHIFT = 4.0
    D = 38

    def __init__(self, icon: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self._icon = icon
        self._init_touch()
        self.setToolTip(tooltip)
        self.setFixedSize(self.D + 24, self.D + 24)   # поле под «подъём», желе и тень

    def _body(self) -> QRectF:
        c = QRectF(self.rect()).center()
        return QRectF(c.x() - self.D / 2, c.y() - self.D / 2, self.D, self.D)

    def hitButton(self, pos) -> bool:
        return self._body().adjusted(-3, -3, 3, 3).contains(QPointF(pos))

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        r = self._body()
        self._apply_touch(p, r)
        fill = glass_fill(is_dark())
        fill.setAlphaF(min(1.0, fill.alphaF() + .2 * self._hover.value))
        body = paint_liquid_glass(p, r, r.height() / 2, fill=fill, reach=6)
        self._paint_glow(p, body)
        color = t["text"] if self.isEnabled() else t["disabled"]
        draw_icon(p, self._icon, r.adjusted(10, 10, -10, -10), color, 2.0)


# --------------------------------------------------------------------------- #
#  Плавающая панель вкладок + стек страниц с плавной сменой
# --------------------------------------------------------------------------- #

class _ShadowOverlay(QWidget):
    """Тень панели вкладок отдельным слоем, прозрачным для мыши:
    иначе широкое поле под тень перехватывало бы клики по содержимому под ним."""

    def __init__(self, parent: QWidget, radius: float):
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, e):
        p = painter(self)
        body = QRectF(self.rect()).adjusted(_SHADOW_PAD, _SHADOW_PAD, -_SHADOW_PAD, -_SHADOW_PAD)
        color = QColor(0, 0, 0, 120 if is_dark() else 30)
        p.drawPixmap(QPointF(0, 0), _shadow_pixmap(body.size(), self._radius, color, self.devicePixelRatioF()))


class TabBar(QWidget):
    """Плавающая стеклянная панель вкладок, как в Telegram для iOS 26.
    За стеклом виден преломлённый у краёв контент страницы. Выбранная вкладка — «линза»:
    её можно потащить мышью, поднятая линза увеличивает значки, а цвет значков
    меняется ровно по её границе."""
    currentChanged = Signal(int)
    INSET = 4          # отступ вкладок от края панели (innerInset)
    ITEM_W = 96
    ITEM_H = 56        # высота панели = 56 + 4 × 2
    PAD = 6            # поле вокруг панели: под подъём линзы
    LIFTED = 4         # насколько линза выходит за вкладку, когда её тащат

    def __init__(self, items: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.backdrop_source: QWidget | None = None
        self._items = items
        self._index = 0
        self._hover_i = -1
        self._pos = Spring(self, 0.0)       # положение линзы в «вкладках» (дробное)
        self._lift = Spring(self)           # линзу подняли — её тащат
        self._backdrop = None
        self._backdrop_at = 0.0
        bar_w = self.ITEM_W * len(items) + self.INSET * 2
        bar_h = self.ITEM_H + self.INSET * 2
        self.setFixedSize(bar_w + self.PAD * 2, bar_h + self.PAD * 2)
        self._shadow = _ShadowOverlay(parent, bar_h / 2) if parent is not None else None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # --- геометрия
    def _bar(self) -> QRectF:
        return QRectF(self.rect()).adjusted(self.PAD, self.PAD, -self.PAD, -self.PAD)

    def _item(self, i: float) -> QRectF:
        b = self._bar()
        return QRectF(b.left() + self.INSET + i * self.ITEM_W, b.top() + self.INSET, self.ITEM_W, self.ITEM_H)

    def _index_at(self, x: float) -> float:
        i = (x - self._bar().left() - self.INSET) / self.ITEM_W - .5
        return max(0.0, min(len(self._items) - 1.0, i))

    def moveEvent(self, e):
        if self._shadow is not None:
            self._shadow.setGeometry(self.geometry().adjusted(self.PAD - _SHADOW_PAD, self.PAD - _SHADOW_PAD,
                                                              _SHADOW_PAD - self.PAD, _SHADOW_PAD - self.PAD))
            self._shadow.stackUnder(self)
        super().moveEvent(e)

    # --- выбор
    def currentIndex(self) -> int:
        return self._index

    def setCurrentIndex(self, i: int):
        if i == self._index:
            return
        self._index = i
        self._pos.to(i, LIFT_OFF)
        self.currentChanged.emit(i)

    # --- мышь: нажали — линза поднимается и едет под курсор, тащим — следует за ним
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._lift.to(1, LIFT_ON)
            self._pos.to(self._index_at(e.position().x()), LIFT_ON)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._pos.to(self._index_at(e.position().x()), LIFT_ON)
        else:
            i = round(self._index_at(e.position().x()))
            if i != self._hover_i:
                self._hover_i = i
                self.update()

    def mouseReleaseEvent(self, e):
        i = round(self._index_at(e.position().x()))
        self._lift.to(0, LIFT_OFF)
        self._pos.to(i, LIFT_OFF)
        if i != self._index:
            self._index = i
            self.currentChanged.emit(i)

    def leaveEvent(self, e):
        self._hover_i = -1
        self.update()

    # --- отрисовка
    def _get_backdrop(self, bar: QRectF):
        if self.backdrop_source is None:
            return None
        # Пока анимируется сама панель, фон под ней не меняется — берём снимок из кэша
        animating = self._pos.moving or self._lift.moving
        if self._backdrop is None or not animating or time.perf_counter() - self._backdrop_at > .2:
            self._backdrop = grab_backdrop(self.backdrop_source, self, bar, blur_px=4)
            self._backdrop_at = time.perf_counter()
        return self._backdrop

    def _paint_items(self, p: QPainter, t: dict, selected: bool):
        for i, (label, icon) in enumerate(self._items):
            r = self._item(i)
            if selected:
                color = ACCENT
            else:
                color = t["text"] if self._hover_i == i else mix(t["text"], t["secondary"], .3)
            draw_icon(p, icon, QRectF(r.center().x() - 13, r.top() + 7, 26, 26), color, 1.9)
            p.setFont(font(11, QFont.Weight.DemiBold))
            p.setPen(color)
            p.drawText(QRectF(r.left(), r.bottom() - 8 - 14, r.width(), 14), Qt.AlignmentFlag.AlignCenter, label)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        dark = is_dark()
        bar = self._bar()
        bar_shape = paint_liquid_glass(p, bar, bar.height() / 2, backdrop=self._get_backdrop(bar),
                                       shadow=QColor(0, 0, 0, 0))
        lift = max(0.0, self._lift.value)
        grow = self.LIFTED * lift
        lens = self._item(self._pos.value).adjusted(-grow, -grow, grow, grow)
        lens_shape = rounded(lens, lens.height() / 2)

        # Подложка выбранной вкладки в покое: чёрный 7,5% / белый 10%; когда линзу тащат — исчезает
        rest = max(0.0, 1 - lift)
        if rest > 0:
            tint = QColor(255, 255, 255) if dark else QColor(0, 0, 0)
            p.fillPath(lens_shape, alpha(tint, (.10 if dark else .075) * rest))

        # Вне линзы — обычный цвет, внутри — синий: цвет меняется ровно по её границе
        p.save()
        p.setClipPath(bar_shape.subtracted(lens_shape))
        self._paint_items(p, t, selected=False)
        p.restore()
        p.save()
        p.setClipPath(lens_shape)
        if lift > 0:   # поднятая линза увеличивает то, что под ней (×1,15, как значок в Telegram)
            c = lens.center()
            s = 1 + .15 * min(1.0, lift)
            p.translate(c)
            p.scale(s, s)
            p.translate(-c)
        self._paint_items(p, t, selected=True)
        p.restore()

        if lift > .01:   # сама линза — прозрачное стекло с кромкой и тенью
            k = min(1.0, lift)
            paint_liquid_glass(p, lens, lens.height() / 2, fill=QColor(255, 255, 255, int((10 if dark else 40) * k)),
                               rim=QColor(255, 255, 255, int((90 if dark else 220) * k)),
                               shadow=QColor(0, 0, 0, int((90 if dark else 26) * k)), reach=5)


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


def _glass_knob(p: QPainter, knob: QRectF, lift: float, reach: float) -> None:
    """Ручка тумблера и ползунка, как в iOS 26: в покое белая, при нажатии
    расплывается в прозрачную стеклянную линзу, сквозь которую видно дорожку."""
    k = max(0.0, min(1.0, lift))
    radius = knob.height() / 2
    p.drawPixmap(knob.topLeft() - QPointF(_SHADOW_PAD, _SHADOW_PAD),
                 _shadow_pixmap(knob.size(), radius, QColor(0, 0, 0, int(70 - 40 * k)),
                                p.device().devicePixelRatioF(), reach))
    shape = rounded(knob, radius)
    p.fillPath(shape, QColor(255, 255, 255, int(255 * (1 - .8 * k))))
    if k > 0:
        p.save()
        p.setClipPath(shape)
        p.setPen(QPen(QColor(255, 255, 255, int(235 * k)), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(_rim_path(knob, radius, 1.0))
        p.restore()


class Toggle(QCheckBox):
    """Переключатель iOS 26. Подпись — в строке слева, сам тумблер без текста."""
    W, H = 46, 28

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._pos = Spring(self)
        self._lift = Spring(self)
        self.toggled.connect(lambda on: self._pos.to(1 if on else 0, LIFT_OFF))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setChecked(self, on: bool):
        super().setChecked(on)
        if not self.isVisible():
            self._pos.jump(1 if on else 0)

    def sizeHint(self) -> QSize:
        return QSize(self.W + 16, self.H + 16)   # поле под расплывшуюся ручку и её тень

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def mousePressEvent(self, e):
        self._lift.to(1, LIFT_ON)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._lift.to(0, LIFT_OFF)
        super().mouseReleaseEvent(e)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        k = self._pos.value
        lift = max(0.0, self._lift.value)
        track = QRectF((self.width() - self.W) / 2, (self.height() - self.H) / 2, self.W, self.H)
        p.fillPath(rounded(track, self.H / 2), mix(t["track"], GREEN, k))
        d = self.H - 4
        kw, kh = d * (1 + .55 * lift), d * (1 + .14 * lift)
        travel = track.width() - 4 - d
        cx = track.left() + 2 + d / 2 + travel * min(1.2, max(-.2, k))
        _glass_knob(p, QRectF(cx - kw / 2, track.center().y() - kh / 2, kw, kh), lift, reach=4)


class GlassSlider(QSlider):
    K = 22  # диаметр ручки

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._lift = Spring(self)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _frac(self) -> float:
        span = self.maximum() - self.minimum()
        return (self.value() - self.minimum()) / span if span else 0.0

    def _value_at(self, x: float) -> int:
        k = (x - self.K) / max(1.0, self.width() - self.K * 2)
        return round(self.minimum() + max(0.0, min(1.0, k)) * (self.maximum() - self.minimum()))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(True)
            self.setValue(self._value_at(e.position().x()))
            self._lift.to(1, LIFT_ON)

    def mouseMoveEvent(self, e):
        if self.isSliderDown():
            self.setValue(self._value_at(e.position().x()))

    def mouseReleaseEvent(self, e):
        self.setSliderDown(False)
        self._lift.to(0, LIFT_OFF)

    def paintEvent(self, e):
        t = T(self)
        p = painter(self)
        cy = self.height() / 2
        left, width = self.K, self.width() - self.K * 2
        x = left + width * self._frac()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(t["track"])
        p.drawRoundedRect(QRectF(left, cy - 2.5, width, 5), 2.5, 2.5)
        p.setBrush(ACCENT)
        p.drawRoundedRect(QRectF(left, cy - 2.5, x - left, 5), 2.5, 2.5)
        lift = max(0.0, self._lift.value)
        kw, kh = self.K * (1 + .7 * lift), self.K * (1 + .2 * lift)
        _glass_knob(p, QRectF(x - kw / 2, cy - kh / 2, kw, kh), lift, reach=5)


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
    """Список файлов. Пока он пуст — это зона для файлов: сюда можно перетащить файлы
    или нажать, чтобы выбрать их в Finder."""
    browseRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(FileDelegate(self))
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        # Список рисует себя во viewport — анимации должны перерисовывать именно его
        self._hover = Tween(self.viewport(), 180)
        self._press = Tween(self.viewport(), 110)
        self._pressed_in_zone = False   # флаг, а не анимация: быстрый тап короче первого кадра

    def _zone(self) -> QRectF:
        return QRectF(self.viewport().rect()).adjusted(12, 10, -12, -10)

    def _over_zone(self, pos) -> bool:
        return not self.count() and self._zone().contains(QPointF(pos))

    def mouseMoveEvent(self, e):
        over = self._over_zone(e.position())
        self._hover.to(1 if over else 0)
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hover.to(0, 260)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._pressed_in_zone = e.button() == Qt.MouseButton.LeftButton and self._over_zone(e.position())
        if self._pressed_in_zone:
            self._press.to(1, 90)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        clicked = self._pressed_in_zone and self._over_zone(e.position())
        self._pressed_in_zone = False
        self._press.to(0, 380, SPRING)
        super().mouseReleaseEvent(e)
        if clicked:
            self.browseRequested.emit()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count():
            return
        t = T(self)
        p = painter(self.viewport())
        h = self._hover.value
        zone = self._zone()
        # Пунктирная рамка зоны: при наведении — синяя с лёгкой заливкой
        p.fillPath(rounded(zone, 14), alpha(ACCENT, .06 * h))
        pen = QPen(mix(t["separator"], ACCENT, h), 1.5, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([4, 4])
        p.setPen(pen)
        p.drawPath(rounded(zone.adjusted(.75, .75, -.75, -.75), 13.25))

        c = zone.center()
        s = 1 + .06 * h - .06 * self._press.value       # кружок чуть растёт при наведении и «вдавливается»
        circle = QRectF(c.x() - 34 * s, c.y() - 44 - 34 * s, 68 * s, 68 * s)
        g = QLinearGradient(circle.topLeft(), circle.bottomLeft())
        g.setColorAt(0, QColor(_AVATAR["blue"][0]))
        g.setColorAt(1, QColor(_AVATAR["blue"][1]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(circle)
        draw_icon(p, "plus", circle.adjusted(19 * s, 19 * s, -19 * s, -19 * s), QColor("#FFFFFF"), 2.4)
        p.setPen(t["text"])
        p.setFont(font(17, QFont.Weight.DemiBold))
        p.drawText(QRectF(zone.left(), c.y() + 2, zone.width(), 24), Qt.AlignmentFlag.AlignCenter,
                   "Перетащите файлы сюда")
        p.setPen(mix(t["secondary"], ACCENT, h))
        p.setFont(font(13))
        p.drawText(QRectF(zone.left(), c.y() + 28, zone.width(), 20), Qt.AlignmentFlag.AlignCenter,
                   "или нажмите, чтобы выбрать")


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
                     _shadow_pixmap(r.size(), 14, QColor(0, 0, 0, 70), p.device().devicePixelRatioF(), reach=4))
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

SCROLL = (1.0, 260.0, 32.0)      # пружина прокрутки: почти критическое затухание, без перелёта
SCROLL_BACK = (1.0, 200.0, 24.0)  # возврат после оттяга за край — с лёгким пружинением


class GlassPopup(QWidget):
    """Стеклянное меню со скруглёнными углами вместо квадратного системного.
    Прокрутка как в iOS: трекпад — попиксельно с системной инерцией, колёсико — плавно на пружине,
    за краями — резиновый оттяг; подсветка пункта плавно переезжает между строками."""
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
        self._scroll = Spring(self, 0.0, SCROLL)     # смещение списка в пикселях
        self._hl = Spring(self, float(self._hover), LIFT_ON)   # где сейчас подсветка (в строках)
        self._bar_alpha = Tween(self, 180)           # полоса прокрутки видна только во время прокрутки
        self._bar_timer = QTimer(self)
        self._bar_timer.setSingleShot(True)
        self._bar_timer.timeout.connect(lambda: self._bar_alpha.to(0, 400))
        self._settle_timer = QTimer(self)            # после жеста возвращаем оттянутый край на место
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._settle)
        self._moved = False
        self._opened_at = 0.0
        self._shown = Spring(self)
        self._backdrop = None
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
        self._backdrop = self._grab_window_below(pos)
        self._scroll.jump(self._clamp((self._current - self._rows // 2) * self.ROW))
        self._opened_at = time.monotonic()
        self.show()
        self.setFocus()
        self._shown.to(1, LIFT_OFF)

    def _grab_window_below(self, pos: QPoint):
        """Меню — отдельное окно, поэтому то, что под ним, снимаем с главного окна заранее."""
        win = self.parentWidget().window() if self.parentWidget() else None
        if win is None:
            return None
        margin = int(REFRACT_SHIFT + 4)
        body = self._body().toAlignedRect()
        want = QRect(win.mapFromGlobal(pos + body.topLeft()) - QPoint(margin, margin),
                     body.size() + QSize(margin * 2, margin * 2))
        region = want.intersected(win.rect())
        if region.isEmpty():
            return None
        # Сильнее размываем, чем у панели вкладок: на меню должен читаться текст
        return frost(win.grab(region), 16), QPointF(body.topLeft() - QPoint(margin, margin)
                                                    + (region.topLeft() - want.topLeft()))

    # --- прокрутка
    def _max_scroll(self) -> float:
        return max(0.0, (len(self._items) - self._rows) * self.ROW)

    def _clamp(self, v: float) -> float:
        return max(0.0, min(self._max_scroll(), v))

    def _settle(self):
        """Вернуть список в границы, если его оттянули за край."""
        v = self._scroll.value
        if v != self._clamp(v):
            self._scroll.to(self._clamp(v), SCROLL_BACK)

    def _show_bar(self):
        if self._max_scroll() > 0:
            self._bar_alpha.to(1, 120)
            self._bar_timer.start(700)

    def wheelEvent(self, e):
        pd, ad = e.pixelDelta(), e.angleDelta()
        if not pd.isNull():
            # Трекпад: едем за пальцами попиксельно, инерцию присылает сама macOS.
            # За краем — сопротивление, как резинка в iOS
            v = self._scroll.value - pd.y()
            if v != self._clamp(v):
                v = self._scroll.value - pd.y() * .3
            self._scroll.jump(v)
            self._settle_timer.start(90)
        elif ad.y():
            # Колёсико мыши: плавно доезжаем до цели на пружине
            target = self._clamp(self._scroll.target - ad.y() / 120 * self.ROW * 1.5)
            self._scroll.to(target, SCROLL)
        self._show_bar()
        self._hover_from_cursor()
        e.accept()

    def _hover_from_cursor(self):
        i = self._row_at(self.mapFromGlobal(QCursor.pos()).y())
        if i >= 0 and i != self._hover:
            self._hover = i
            self._hl.to(i, LIFT_ON)

    # --- ввод
    def _row_at(self, y: float) -> int:
        i = int((y - self.MARGIN - self.PAD + self._scroll.value) // self.ROW)
        return i if 0 <= i < len(self._items) and self._body().contains(QPointF(self.MARGIN + 1, y)) else -1

    def mouseMoveEvent(self, e):
        self._moved = True
        i = self._row_at(e.position().y())
        if i >= 0 and i != self._hover:
            self._hover = i
            self._hl.to(i, LIFT_ON)

    def mouseReleaseEvent(self, e):
        # Отпускание той же кнопки, что открыла меню, — не выбор
        if not self._moved and time.monotonic() - self._opened_at < .35:
            return
        i = self._row_at(e.position().y())
        if i >= 0:
            self._pick(i)

    def keyPressEvent(self, e):
        key = e.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._hover = max(0, min(len(self._items) - 1, self._hover + (1 if key == Qt.Key.Key_Down else -1)))
            self._hl.to(self._hover, LIFT_ON)
            # Плавно докручиваем, чтобы выбранная строка была видна
            top = self._hover * self.ROW
            view = self._rows * self.ROW
            target = self._scroll.target
            if top < target:
                target = top
            elif top + self.ROW > target + view:
                target = top + self.ROW - view
            if target != self._scroll.target:
                self._scroll.to(self._clamp(target), SCROLL)
                self._show_bar()
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
        p.setOpacity(max(0.0, min(1.0, k * 1.6)))
        body = self._body()
        s = .94 + .06 * k                              # раскрывается от верхнего края
        p.translate(body.center().x(), body.top())
        p.scale(s, s)
        p.translate(-body.center().x(), -body.top())
        dark = is_dark()
        shape = paint_liquid_glass(p, body, 18, backdrop=self._backdrop,
                                   fill=QColor(36, 36, 38, 205) if dark else QColor(255, 255, 255, 190),
                                   shadow=QColor(0, 0, 0, 120 if dark else 45))
        p.setClipPath(shape)
        scroll = self._scroll.value
        top = body.top() + self.PAD - scroll            # где была бы первая строка
        x, w = body.left() + self.PAD, body.width() - self.PAD * 2
        # Подсветка едет между строками сама по себе, текст под ней — белый, вне её — обычный
        hl = rounded(QRectF(x, top + self._hl.value * self.ROW, w, self.ROW), 8)
        p.fillPath(hl, ACCENT)
        first = max(0, int(scroll // self.ROW) - 1)
        last = min(len(self._items), first + self._rows + 3)
        p.setFont(font(14, QFont.Weight.Medium))
        for selected_layer in (False, True):
            p.save()
            p.setClipPath(hl if selected_layer else shape.subtracted(hl))
            fg = QColor("#FFFFFF") if selected_layer else t["text"]
            p.setPen(fg)
            for i in range(first, last):
                r = QRectF(x, top + i * self.ROW, w, self.ROW)
                if i == self._current:
                    draw_icon(p, "check", QRectF(r.left() + 6, r.center().y() - 8, 16, 16), fg, 2.2)
                p.drawText(r.adjusted(30, 0, -10, 0), AlignLeftV, self._items[i])
            p.restore()
        a = self._bar_alpha.value
        if self._max_scroll() > 0 and a > 0:             # тонкая полоса прокрутки, как в iOS
            track_h = body.height() - self.PAD * 4
            bar_h = max(24.0, track_h * self._rows / len(self._items))
            k = max(0.0, min(1.0, scroll / self._max_scroll()))
            y = body.top() + self.PAD * 2 + (track_h - bar_h) * k
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(alpha(t["secondary"], .55 * a))
            p.drawRoundedRect(QRectF(body.right() - 6, y, 3, bar_h), 1.5, 1.5)
