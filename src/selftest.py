"""
Самопроверка собранного приложения: `FileConverterPro --self-test[=отчёт.txt]`.

PyInstaller может не захватить модуль — тогда приложение падает у пользователей,
хотя сборка «зелёная». CI запускает собранную программу с этим флагом: она проверяет
библиотеки, конвертеры, окно и пару настоящих конвертаций, пишет отчёт и выходит
с кодом 0 (всё в порядке) или 1.
"""
import importlib
import sys
import tempfile
import traceback
from pathlib import Path

# Сторонние библиотеки, без которых часть конвертаций не работает
MODULES = ["PySide6.QtWidgets", "loguru", "PIL", "pillow_heif", "fitz", "pdfplumber", "pypdf",
           "docx", "pptx", "openpyxl", "reportlab", "lxml"]


def run_self_test(window, report: Path | None) -> int:
    lines: list[str] = []
    failed = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal failed
        failed += not ok
        lines.append(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    for name in MODULES:
        try:
            importlib.import_module(name)
            check(f"модуль {name}", True)
        except Exception as e:
            check(f"модуль {name}", False, repr(e))

    from PySide6.QtWidgets import QApplication
    from src.converters.factory import ConverterFactory
    try:
        for cls in ConverterFactory._CONVERTER_MAP.values():
            cls()
        check("все конвертеры создаются", True, str(len(ConverterFactory._CONVERTER_MAP)))
    except Exception as e:
        check("все конвертеры создаются", False, repr(e))

    try:
        window.tabs.setCurrentIndex(1)
        QApplication.processEvents()
        check("окно открыто, вкладки переключаются", window.isVisible() and window.pages.currentIndex() == 1)
    except Exception as e:
        check("окно открыто, вкладки переключаются", False, repr(e))

    tmp = Path(tempfile.mkdtemp(prefix="fcp_selftest_"))
    conversions = [("png", "jpg"), ("pdf", "png"), ("pdf", "txt")]
    try:
        from PIL import Image
        import fitz
        Image.new("RGB", (32, 32), (200, 80, 40)).save(tmp / "sample.png")
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "self-test")
        doc.save(tmp / "sample.pdf")
    except Exception as e:
        check("тестовые файлы созданы", False, repr(e))
        conversions = []
    for src, dst in conversions:
        out = tmp / f"result_{src}_to_{dst}.{dst}"
        try:
            ok = ConverterFactory.get_converter(src, dst).convert(tmp / f"sample.{src}", out)
            made = [p for p in tmp.glob(f"result_{src}_to_{dst}*") if p.stat().st_size > 0]
            check(f"{src.upper()} → {dst.upper()}", bool(ok and made))
        except Exception:
            check(f"{src.upper()} → {dst.upper()}", False, traceback.format_exc(limit=3).strip().splitlines()[-1])

    # Распознавание скана: модели Tesseract попали в сборку, а встроенный в PyMuPDF Tesseract работает
    try:
        import fitz
        from src.converters.pdf_text import ocr_lines
        with fitz.open() as text_pdf, fitz.open() as scan:
            text_pdf.new_page().insert_text((72, 120), "Scanner check 2026", fontsize=28)
            page = scan.new_page()
            page.insert_image(page.rect, stream=text_pdf[0].get_pixmap(dpi=200).tobytes("png"))
            found = " ".join(text for _, pieces in ocr_lines(page) for text, _ in pieces)
        check("распознавание скана (OCR)", "Scanner check 2026" in found, found[:60])
    except Exception as e:
        check("распознавание скана (OCR)", False, repr(e))

    lines.append(f"Итог: {'ошибок нет' if not failed else f'не прошло проверок: {failed}'}")
    text = "\n".join(lines)
    if sys.stdout is not None:
        print(text, flush=True)
    if report is not None:
        report.write_text(text + "\n", encoding="utf-8")
    return 1 if failed else 0
