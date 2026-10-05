"""
Проверка интерфейса настоящей мышью на настоящем экране.
В CI — Windows и Linux (Xvfb + openbox); локально работает и на macOS.

Кликает вкладки и тумблер, тащит линзу панели вкладок и само окно за заголовок,
открывает меню формата и прокручивает его колёсиком, вызывает контекстное меню,
снимает скриншоты всего экрана.

    python tests/ui_check.py [папка_для_скриншотов]

Ввод — системный, как от пользователя: Windows — user32, Linux — xdotool, macOS — CoreGraphics.
Код возврата 0 — всё прошло, 1 — что-то сломано.
"""
import ctypes
import faulthandler
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402


# --------------------------------------------------------------------------- #
#  Системный ввод
# --------------------------------------------------------------------------- #

class WindowsInput:
    def __init__(self):
        self.u = ctypes.windll.user32
        # dwData — DWORD: отрицательная прокрутка передаётся как беззнаковое число
        self.u.mouse_event.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.c_size_t]

    def move(self, x, y):
        self.u.SetCursorPos(int(x), int(y))

    def button(self, down: bool, right=False):
        flag = (0x0008 if down else 0x0010) if right else (0x0002 if down else 0x0004)
        self.u.mouse_event(flag, 0, 0, 0, 0)

    def wheel(self, clicks: int):
        self.u.mouse_event(0x0800, 0, 0, ctypes.c_uint32(120 * clicks & 0xFFFFFFFF).value, 0)

    def escape(self):
        self.u.keybd_event(0x1B, 0, 0, 0)
        self.u.keybd_event(0x1B, 0, 2, 0)


class X11Input:
    def _x(self, *args):
        subprocess.run(["xdotool", *map(str, args)], check=True)

    def move(self, x, y):
        self._x("mousemove", int(x), int(y))

    def button(self, down: bool, right=False):
        self._x("mousedown" if down else "mouseup", 3 if right else 1)

    def wheel(self, clicks: int):
        for _ in range(abs(clicks)):
            self._x("click", 4 if clicks > 0 else 5)

    def escape(self):
        self._x("key", "Escape")


class MacInput:
    def __init__(self):
        import ctypes.util
        self.cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

        class CGPoint(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]
        self.CGPoint = CGPoint
        self.cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
        self.cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
        self.cg.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
        self.cg.CGEventCreateScrollWheelEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32]
        self.cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
        self.cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
        self.cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        self.release = cf.CFRelease
        self.release.argtypes = [ctypes.c_void_p]
        self.pos = (0.0, 0.0)
        self.pressed = None

    def _post(self, e):
        self.cg.CGEventPost(0, e)
        self.release(e)

    def _mouse(self, kind, button=0):
        self._post(self.cg.CGEventCreateMouseEvent(None, kind, self.CGPoint(*self.pos), button))

    def move(self, x, y):
        self.pos = (x, y)
        self._mouse({None: 5, "left": 6, "right": 7}[self.pressed])

    def button(self, down: bool, right=False):
        self.pressed = ("right" if right else "left") if down else None
        self._mouse((3 if down else 4) if right else (1 if down else 2), 1 if right else 0)

    def wheel(self, clicks: int):
        self._post(self.cg.CGEventCreateScrollWheelEvent(None, 1, 1, clicks))

    def escape(self):
        for down in (True, False):
            self._post(self.cg.CGEventCreateKeyboardEvent(None, 53, down))


# --------------------------------------------------------------------------- #

results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((ok, name))
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def main() -> int:
    # Обычно проверка идёт 20–30 с. Если что-то зависло — печатаем, где стоит каждый поток, и выходим,
    # а не ждём тайм-аута CI
    faulthandler.dump_traceback_later(90, exit=True)
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="fcp_ui_"))

    app = QApplication([])
    app.setStyle("Fusion")
    from src.core.settings import Settings
    Settings.save = lambda self: None                      # не трогаем настройки пользователя
    from src.gui.main_window import MainWindow
    from src.gui.styles import get_palette_for, get_stylesheet_for
    from src.gui.glass import GlassPopup

    inp = WindowsInput() if sys.platform == "win32" else MacInput() if sys.platform == "darwin" else X11Input()
    screen = app.primaryScreen()
    # Windows ждёт физические пиксели, X11 и macOS — те же логические координаты, что у Qt
    scale = screen.devicePixelRatio() if sys.platform == "win32" else 1.0

    def pump(seconds: float):
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(.005)

    def act(fn):
        """Ввод — из отдельного потока, пока окно продолжает обрабатывать события."""
        t = threading.Thread(target=fn)
        t.start()
        while t.is_alive():
            app.processEvents()
            time.sleep(.005)
        pump(.5)

    def g(widget, local) -> tuple[float, float]:
        p = widget.mapToGlobal(QPoint(int(local.x()), int(local.y())))
        return p.x() * scale, p.y() * scale

    def click(xy, right=False):
        def run():
            inp.move(*xy)
            time.sleep(.08)
            inp.button(True, right)
            time.sleep(.08)
            inp.button(False, right)
        act(run)

    def drag(a, b, steps=14):
        def run():
            inp.move(*a)
            time.sleep(.1)
            inp.button(True)
            time.sleep(.12)
            for i in range(1, steps + 1):
                inp.move(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
                time.sleep(.025)
            time.sleep(.08)
            inp.button(False)
        act(run)

    def shot(name):
        if shots:
            screen.grabWindow(0).save(str(shots / f"{name}.png"))

    def visible_popup():
        return next((x for x in app.topLevelWidgets() if isinstance(x, GlassPopup) and x.isVisible()), None)

    w = MainWindow()
    w.settings.settings['auto_open_folder'] = False
    app.setPalette(get_palette_for("light"))
    app.setStyleSheet(get_stylesheet_for("light"))
    avail = screen.availableGeometry()
    print(f"Экран {screen.geometry().width()}×{screen.geometry().height()}, окно {w.width()}×{w.height()}", flush=True)
    w.move(avail.left() + 20, avail.top() + 20)
    w.show()
    w.raise_()
    w.activateWindow()
    pump(2.0)
    try:
        shot("01_converter_light")
        tabs = w.tabs

        # 1. Вкладка «Настройки» — настоящим кликом
        click(g(tabs, tabs._item(1).center()))
        pump(.6)
        check("Клик по вкладке «Настройки»", tabs.currentIndex() == 1 and w.pages.currentIndex() == 1)

        # 2. Тумблер
        tg = w.pdf_remove_metadata_check
        w.pages.widget(1).findChild(QScrollArea).ensureWidgetVisible(tg, 0, 160)
        pump(.5)
        before = tg.isChecked()
        click(g(tg, tg.rect().center()))
        check("Клик по тумблеру переключает его", tg.isChecked() != before)
        click(g(tg, tg.rect().center()))
        shot("02_settings_light")

        # 3. Линзу панели вкладок тащим с «Настроек» на «Журнал»
        drag(g(tabs, tabs._item(1).center()), g(tabs, tabs._item(2).center()))
        pump(.8)
        check("Перетаскивание линзы переключает вкладку", tabs.currentIndex() == 2 and w.pages.currentIndex() == 2)
        click(g(tabs, tabs._item(0).center()))
        pump(.6)
        check("Клик по вкладке «Конвертер»", tabs.currentIndex() == 0)

        # 4. Меню «Из»: открывается кликом, прокручивается колёсиком, закрывается Esc
        combo = w.input_format_combo
        click(g(combo, combo.rect().center()))
        pump(.6)
        popup = visible_popup()
        check("Клик открывает стеклянное меню формата", popup is not None)
        if popup is not None:
            shot("03_format_menu")
            body = popup._body().center()
            act(lambda: (inp.move(*g(popup, body)), time.sleep(.1), inp.wheel(-3)))
            pump(.8)
            check("Колёсико прокручивает меню", popup._scroll.value > 1, f"смещение {popup._scroll.value:.0f} px")
            act(inp.escape)
            pump(.4)
            check("Esc закрывает меню", visible_popup() is None)

        # 5. Контекстное меню у файла — правым кликом
        from PIL import Image
        files = []
        for i in range(3):
            f = tmp / f"photo_{i}.png"
            Image.new("RGB", (40, 40), (i * 70, 140, 220)).save(f)
            files.append(f)
        w.add_paths(files)
        pump(.5)
        row = w.file_list.visualItemRect(w.file_list.item(0)).center()
        click(g(w.file_list.viewport(), row), right=True)
        pump(.6)
        check("Правый клик по файлу открывает меню", visible_popup() is not None)
        shot("04_context_menu")
        act(inp.escape)
        pump(.4)

        # 6. Окно перетаскивается за заголовок
        frame, geo = w.frameGeometry(), w.geometry()
        title_h = geo.top() - frame.top()
        if title_h > 4:
            start = ((frame.center().x()) * scale, (frame.top() + title_h / 2) * scale)
            before = w.pos()
            drag(start, (start[0] + 120 * scale, start[1] + 70 * scale))
            pump(.8)
            check("Окно перетаскивается за заголовок", w.pos() != before,
                  f"{before.x()},{before.y()} → {w.pos().x()},{w.pos().y()}")
        else:
            print("[SKIP] Окно без рамки оконного менеджера — перетаскивание за заголовок не проверить", flush=True)

        # 7. Тёмная тема
        app.setPalette(get_palette_for("dark"))
        app.setStyleSheet(get_stylesheet_for("dark"))
        pump(.6)
        shot("05_converter_dark")
    except Exception:
        traceback.print_exc()
        check("Проверка дошла до конца без исключений", False)
    finally:
        w.close()
        pump(.3)

    failed = [name for ok, name in results if not ok]
    print(f"\nИтог: {len(results) - len(failed)} из {len(results)} проверок прошли" +
          (f"; не прошли: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
