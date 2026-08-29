#!/usr/bin/env python3
"""Сборка File Converter Pro — минимальный размер + обход arch-конвертации.

Оптимизации веса:
  * не тянем numpy/opencv/scipy/pandas/pdf2docx (pdf->docx через лёгкий текстовый фолбэк);
  * исключаем неиспользуемые тяжёлые модули (PyQt5/6, tkinter, matplotlib);
  * onedir вместо onefile (быстрый старт, меньше памяти на распаковку).

Запуск программный (не через subprocess), чтобы обойти требование
MacOS Xcode license для `lipo` — universal-бинарники работают на arm64 сами.
"""
import sys, shutil, subprocess, platform, os, tempfile
from pathlib import Path

# Windows-консоль не всегда поддерживает Unicode emoji — включим UTF-8 вывод
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SYSTEM = platform.system().lower()
PROJECT = Path(__file__).parent
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"
NAME = "FileConverterPro"

def ok(msg): print(f"[OK] {msg}")
def info(msg): print(f"[..] {msg}")
def err(msg): print(f"[!!] {msg}")

# Очистка старых артефактов
for d in [DIST, BUILD]:
    shutil.rmtree(d, ignore_errors=True)
for f in PROJECT.glob("*.spec"):
    f.unlink(missing_ok=True)

# __init__.py для пакетов
for d in ["src", "src/gui", "src/core", "src/converters", "src/config", "src/utils"]:
    (PROJECT / d / "__init__.py").touch(exist_ok=True)

# Кэш PyInstaller и конфиг — во временную папку ОС (обход sandbox/лишнего диска)
_tmp = Path(tempfile.gettempdir())
os.environ.setdefault("XDG_CACHE_HOME", str(_tmp / "pyi_cache"))
os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(_tmp / "pyi_cfg"))
os.makedirs(_tmp / "pyi_cache", exist_ok=True)
os.makedirs(_tmp / "pyi_cfg", exist_ok=True)

# На macOS обходим Xcode-license-зависимый `lipo` (thin-архитектуры).
# Подпись (codesign) РАБОТАЕТ без принятой лицензии — её НЕ отключаем,
# иначе .app не запускается (Launchd error 163).
if SYSTEM == "darwin":
    import PyInstaller.utils.osx as osx
    def _noop(*a, **k):
        return a[0] if a else None
    # Только lipo-зависимые этапы превращаем в no-op
    osx.binary_to_target_arch = _noop
    osx.convert_binary_to_thin_arch = _noop
    osx.set_dylib_dependency_paths = _noop
    import PyInstaller.building.utils as _bu
    _bu.osxutils.binary_to_target_arch = _noop
    _bu.osxutils.convert_binary_to_thin_arch = _noop
    _bu.osxutils.set_dylib_dependency_paths = _noop
    import PyInstaller.building.api as _api
    _api.osxutils.binary_to_target_arch = _noop
    _api.osxutils.convert_binary_to_thin_arch = _noop
    _api.osxutils.set_dylib_dependency_paths = _noop

excludes = [
    "tkinter", "matplotlib", "scipy",
    "numpy", "opencv", "cv2", "pandas",
    "pdf2docx", "camelot", "tabula",
    "PyQt5", "PyQt6", "PySide2",
    "pytest", "setuptools", "pip",
    "IPython", "jupyter", "notebook",
]

sys.argv = [
    "pyinstaller", "--onedir", "--windowed", "--name", NAME,
    "--hidden-import", "PySide6.QtCore",
    "--hidden-import", "PySide6.QtGui",
    "--hidden-import", "PySide6.QtWidgets",
    "--hidden-import", "loguru",
    "--hidden-import", "fitz",
    "--hidden-import", "pdfplumber",
    "--hidden-import", "openpyxl",
    "--hidden-import", "pypdf",
    "--hidden-import", "PIL",
    "--hidden-import", "docx",
    "--hidden-import", "pptx",
    "--hidden-import", "reportlab",
    "--hidden-import", "lxml",
    "--hidden-import", "src.core.libreoffice_manager",
    "--hidden-import", "src.converters",
    "--hidden-import", "src.gui",
    "--collect-submodules", "pdfplumber",
]

for exc in excludes:
    sys.argv.extend(["--exclude-module", exc])

sys.argv.append("run.py")

info("Сборка (onedir, без numpy/opencv)...")
from PyInstaller.__main__ import run
run()

app = DIST / f"{NAME}.app" if SYSTEM == "darwin" else DIST / NAME

if app.exists():
    info("Чистка после сборки...")
    for junk in ["__pycache__", "*.pyc", "tests", "test", "docs", "examples"]:
        for p in app.rglob(junk):
            try:
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
            except Exception:
                pass
    size = sum(p.stat().st_size for p in app.rglob("*") if p.is_file()) / 1024 / 1024
    ok(f"Готово: {app}")
    ok(f"Размер: {size:.0f} MB")
else:
    ok("Сборка завершена (см. dist/)")
