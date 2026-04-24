"""Очистка собранного .app от лишнего"""
import shutil, sys
from pathlib import Path

app = Path("dist/FileConverterPro.app/Contents/Resources")

# Удаляем явный мусор
junk = ["**/tests", "**/test", "**/docs", "**/examples", "**/__pycache__", "**/*.pyc", "**/.git"]
for pattern in junk:
    for p in app.rglob(pattern.split("/")[-1]):
        try:
            if p.is_file(): p.unlink()
            elif p.is_dir(): shutil.rmtree(p, ignore_errors=True)
        except: pass

# LibreOffice: оставляем только нужное для конвертации
lo = app / "resources/libreoffice/macos/LibreOffice.app/Contents/Resources"
if lo.exists():
    # Удаляем иконки, темы, шаблоны
    for crap in ["shellext", "tango", "breeze", "hicontrast", "templates", "gallery"]:
        crap_path = lo / crap
        if crap_path.exists():
            shutil.rmtree(crap_path, ignore_errors=True)

size = sum(p.stat().st_size for p in app.rglob("*") if p.is_file()) / 1024 / 1024
print(f"✅ Очищено. Финальный размер: {size:.1f} MB")
