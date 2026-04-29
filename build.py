#!/usr/bin/env python3
"""Сборка File Converter Pro — минимальный размер"""
import sys, shutil, subprocess
from pathlib import Path

SYSTEM = __import__("platform").system().lower()
PROJECT = Path(__file__).parent
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"
NAME = "FileConverterPro"

PIP_FLAGS = ["--break-system-packages"] if SYSTEM in ["darwin", "linux"] else []
SEP = ";" if SYSTEM == "windows" else ":"

def ok(msg): print(f"\033[92m✅ {msg}\033[0m")
def info(msg): print(f"\033[96m📦 {msg}\033[0m")

# Очистка
for d in [DIST, BUILD]: shutil.rmtree(d, ignore_errors=True)
for f in PROJECT.glob("*.spec"): f.unlink(missing_ok=True)

# __init__.py
for d in ["src", "src/gui", "src/core", "src/converters", "src/config", "src/utils"]:
    (PROJECT / d / "__init__.py").touch(exist_ok=True)

# Ставим pyinstaller
subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"] + PIP_FLAGS)

info("Сборка...")

subprocess.check_call([
    sys.executable, "-m", "PyInstaller",
    "--onedir", "--windowed",
    "--name", NAME,
    "--add-data", f"src{SEP}src",
    "--hidden-import", "PySide6.QtCore",
    "--hidden-import", "PySide6.QtGui",
    "--hidden-import", "PySide6.QtWidgets",
    "--hidden-import", "loguru",
    "--exclude-module", "tkinter",
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
    "--exclude-module", "scipy",
    "--exclude-module", "cv2",
    "--exclude-module", "cffi",
    "--exclude-module", "cryptography",
    "--exclude-module", "pandas.tests",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "pytest",
    "--exclude-module", "setuptools",
    "--exclude-module", "pip",
    "run.py"
])

app = DIST / f"{NAME}.app"
if app.exists():
    # Очистка кеша внутри .app
    info("Очистка...")
    for junk in ["__pycache__", "*.pyc", "tests", "test", "docs", "examples"]:
        for p in app.rglob(junk):
            try:
                if p.is_file(): p.unlink()
                elif p.is_dir(): shutil.rmtree(p, ignore_errors=True)
            except: pass
    
    size = sum(p.stat().st_size for p in app.rglob("*") if p.is_file()) / 1024/1024
    ok(f"Готово: {app} ({size:.0f} MB)")
