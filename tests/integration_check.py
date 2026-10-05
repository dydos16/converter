"""
Сквозная проверка на настоящей ОС. В CI запускается на Windows, работает и на macOS/Linux:
окно приложения без экрана (offscreen), вкладки и меню, конвертация PNG → JPG через интерфейс,
автоустановка LibreOffice с нуля (если его ещё нет) и DOCX → PDF.

    python tests/integration_check.py [папка_для_скриншотов]

Код возврата 0 — всё прошло, 1 — что-то сломано.
"""
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((ok, name))
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def wait(app, seconds: float, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(.01)
    return bool(until and until())


def main() -> int:
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="fcp_check_"))

    app = QApplication([])
    app.setStyle("Fusion")
    from src.core.settings import Settings
    Settings.save = lambda self: None              # не трогаем настройки пользователя
    from src.gui.main_window import MainWindow
    from src.gui.styles import get_palette_for, get_stylesheet_for
    from src.gui.glass import PROGRESS_ROLE
    from src.converters.factory import ConverterFactory

    w = MainWindow()
    w.settings.settings['auto_open_folder'] = False
    w.settings.settings['show_notifications'] = True
    app.setPalette(get_palette_for("light"))
    app.setStyleSheet(get_stylesheet_for("light"))
    w.show()
    wait(app, 1.0)

    try:
        if os.environ.get("FCP_EXPECT_NON_ADMIN") and sys.platform == "win32":
            import ctypes
            check("Запущено от обычного пользователя, без прав администратора",
                  not ctypes.windll.shell32.IsUserAnAdmin(), os.environ.get("USERNAME", ""))

        # 1. Вкладки
        for i in (1, 2, 0):
            w.tabs.setCurrentIndex(i)
            wait(app, .4)
        check("Вкладки переключаются", w.pages.currentIndex() == 0 and w.tabs.currentIndex() == 0)

        # 2. Выпадающее меню формата
        w.input_format_combo.setCurrentText("png")
        w.output_format_combo.showPopup()
        wait(app, .5)
        popup = w.output_format_combo._popup
        check("Меню формата открывается", popup is not None and popup.isVisible())
        if popup is not None:
            popup.close()

        # 3. PNG → JPG через интерфейс
        from PIL import Image
        src = []
        for i in range(3):
            path = tmp / f"img_{i}.png"
            Image.new("RGB", (64, 64), (i * 80, 120, 200)).save(path)
            src.append(path)
        out = tmp / "out"
        out.mkdir()
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(out))
        w.add_paths(src)
        w.output_format_combo.setCurrentText("jpg")
        w.start_conversion()
        done = wait(app, 60, lambda: all(w.file_list.item(i).data(PROGRESS_ROLE) in (100, -1) for i in range(3)))
        made = sorted(p.name for p in out.iterdir())
        check("PNG → JPG через интерфейс", done and made == ["img_0.jpg", "img_1.jpg", "img_2.jpg"], str(made))

        if shots:
            wait(app, 1.0)
            w.grab().save(str(shots / "converter_light.png"))
            w.tabs.setCurrentIndex(1)
            wait(app, .6)
            w.grab().save(str(shots / "settings_light.png"))
            app.setPalette(get_palette_for("dark"))
            app.setStyleSheet(get_stylesheet_for("dark"))
            wait(app, .3)
            w.grab().save(str(shots / "settings_dark.png"))
            w.tabs.setCurrentIndex(0)
            wait(app, .6)
            w.grab().save(str(shots / "converter_dark.png"))

        # 4. LibreOffice: автоустановка с нуля и DOCX → PDF
        lo = w.libreoffice_manager
        if lo.is_available():
            check("LibreOffice уже установлен — автоустановку пропускаем", True, str(lo.get_soffice_path()))
        else:
            finished = []
            lo.install_finished.connect(lambda ok, msg: finished.append((ok, msg)))
            t = time.time()
            lo._do_install_blocking()
            wait(app, .5)
            ok = bool(finished and finished[-1][0])
            check("Автоустановка LibreOffice", ok, f"{time.time() - t:.0f} с, {finished[-1][1] if finished else 'нет ответа'}")
            lo._check_attempted = False
        check("soffice найден", lo.is_available(), str(lo.get_soffice_path()))

        from docx import Document
        doc = Document()
        doc.add_heading("Integration check", 1)
        doc.add_paragraph("LibreOffice auto-install works on this OS.")
        docx_path = tmp / "check.docx"
        doc.save(docx_path)
        pdf_path = tmp / "check.pdf"
        converter = ConverterFactory.get_converter("docx", "pdf")
        t = time.time()
        ok = converter.convert(docx_path, pdf_path)
        is_pdf = pdf_path.exists() and pdf_path.read_bytes()[:5] == b"%PDF-"
        check("DOCX → PDF через LibreOffice", ok and is_pdf, f"{time.time() - t:.1f} с")
    except Exception:
        traceback.print_exc()
        check("Проверка дошла до конца без исключений", False)
    finally:
        w.job_manager.stop()
        w.worker.quit()
        w.worker.wait(2000)

    failed = [name for ok, name in results if not ok]
    print(f"\nИтог: {len(results) - len(failed)} из {len(results)} проверок прошли" +
          (f"; не прошли: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
