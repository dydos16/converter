#!/usr/bin/env python3
"""
Сборка File Converter Pro
"""
import sys, shutil, subprocess
from pathlib import Path

SYSTEM = __import__("platform").system().lower()
PROJECT = Path(__file__).parent
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"
NAME = "FileConverterPro"

GREEN, RED, CYAN, END = "\033[92m", "\033[91m", "\033[96m", "\033[0m"
PIP_FLAGS = ["--break-system-packages"] if SYSTEM in ["darwin", "linux"] else []

def ok(msg): print(f"{GREEN}✅ {msg}{END}")
def err(msg): print(f"{RED}❌ {msg}{END}")
def info(msg): print(f"{CYAN}📦 {msg}{END}")

def pip_install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg] + PIP_FLAGS)

def step1_clean():
    info("Очистка...")
    for d in [DIST, BUILD]: shutil.rmtree(d, ignore_errors=True)
    for f in PROJECT.glob("*.spec"): f.unlink(missing_ok=True)
    ok("Очищено")

def step2_patch():
    info("Проверка...")
    for d in ["src", "src/gui", "src/core", "src/converters", "src/config", "src/utils"]:
        (PROJECT / d / "__init__.py").touch(exist_ok=True)
    ok("Готово")

def step3_build():
    info(f"Сборка ({SYSTEM})...")
    pip_install("pyinstaller")
    
    sep = ";" if SYSTEM == "windows" else ":"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir", "--windowed",
        "--name", NAME,
        "--add-data", f"src{sep}src",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "loguru",
        "--hidden-import", "PIL._tkinter_finder",
        "--collect-all", "loguru",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "PyQt5",
        "--exclude-module", "PyQt6",
        "run.py"
    ]
    
    subprocess.check_call(cmd)
    
    app = DIST / f"{NAME}.app" if SYSTEM == "darwin" else DIST / f"{NAME}"
    if app.exists():
        ok(f"Собрано: {app}")
        return app
    err("Провал")
    return None

def main():
    print("=" * 60)
    print(f"  🔧 Сборка {NAME} ({SYSTEM})")
    print("=" * 60)
    
    step1_clean()
    step2_patch()
    app = step3_build()
    
    if app and app.exists():
        size_mb = sum(p.stat().st_size for p in app.rglob("*") if p.is_file()) / 1024 / 1024
        print(f"\n{'='*60}")
        print(f"  🎉 {NAME} готов!")
        print(f"{'='*60}")
        print(f"  Размер: {size_mb:.0f} MB")
        print(f"  Файл: {GREEN}{app}{END}")
        print(f"\n  Запуск: {CYAN}open {app}{END}")
        print(f"{'='*60}")
    else:
        err("Сборка провалилась.")

if __name__ == "__main__":
    main()
