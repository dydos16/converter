#!/usr/bin/env python3
"""
File Converter Pro - автономный запуск с автоустановкой LibreOffice
"""
import sys
import os
import subprocess
import urllib.request
import tarfile
import shutil
import platform
from pathlib import Path

# Пути для PyInstaller
if getattr(sys, 'frozen', False):
    BASE = Path(sys._MEIPASS)
else:
    BASE = Path(__file__).parent

sys.path.insert(0, str(BASE))


def get_libreoffice_path():
    """Ищет LibreOffice в системе или в App Support"""
    system = platform.system().lower()
    app_support = Path.home() / "Library" / "Application Support" / "FileConverterPro" / "libreoffice"
    
    if system == 'darwin':
        candidates = [
            app_support / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
            Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
            Path('/opt/homebrew/bin/soffice'),
        ]
    elif system == 'windows':
        candidates = [
            app_support / "windows" / "LibreOffice" / "program" / "soffice.exe",
            Path('C:/Program Files/LibreOffice/program/soffice.exe'),
        ]
    else:
        candidates = [
            app_support / "linux" / "usr" / "bin" / "soffice",
            Path('/usr/bin/soffice'),
        ]
    
    for p in candidates:
        if p.exists():
            return p
    return None


def download_with_progress(url, dest, label="Скачивание"):
    """Скачивает файл с прогресс-баром"""
    print(f"\n📥 {label}...")
    
    def report(block_num, block_size, total_size):
        if total_size <= 0:
            return
        percent = int(block_num * block_size / total_size * 100)
        bar = '█' * int(percent / 2) + '░' * (50 - int(percent / 2))
        mb_done = block_num * block_size / 1024 / 1024
        mb_total = total_size / 1024 / 1024
        print(f"\r[{bar}] {percent}% ({mb_done:.0f}/{mb_total:.0f} MB)", end='', flush=True)
    
    urllib.request.urlretrieve(url, dest, reporthook=report)
    print()


def download_libreoffice():
    """Скачивает и распаковывает LibreOffice"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if machine in ['arm64', 'aarch64']:
        arch = 'arm64'
    else:
        arch = 'x86_64'
    
    # URL для скачивания
    if system == 'darwin':
        url = f"https://github.com/MiHoN135/Convertator-Releases/releases/download/v1.0.0/libreoffice_macos_{arch}.tar.gz"
    elif system == 'windows':
        url = "https://github.com/MiHoN135/Convertator-Releases/releases/download/v1.0.0/libreoffice_windows.zip"
    else:
        url = "https://github.com/MiHoN135/Convertator-Releases/releases/download/v1.0.0/libreoffice_linux.tar.gz"
    
    app_support = Path.home() / "Library" / "Application Support" / "FileConverterPro" / "libreoffice"
    app_support.mkdir(parents=True, exist_ok=True)
    
    # Скачиваем
    archive_path = app_support / "libreoffice_temp.tar.gz"
    download_with_progress(url, archive_path, "Скачивание LibreOffice (~500 MB)")
    
    # Распаковываем
    print("📦 Распаковка LibreOffice...")
    with tarfile.open(archive_path, 'r:gz') as tar:
        tar.extractall(app_support)
    
    # Удаляем архив
    archive_path.unlink()
    
    # Настройка прав для macOS
    if system == 'darwin':
        lo_app = app_support / "macos" / "LibreOffice.app"
        if lo_app.exists():
            print("🔧 Настройка прав...")
            subprocess.run(['xattr', '-d', '-r', 'com.apple.quarantine', str(lo_app)], stderr=subprocess.DEVNULL)
            subprocess.run(['chmod', '-R', '755', str(lo_app)], stderr=subprocess.DEVNULL)
            subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(lo_app)], 
                         capture_output=True, stderr=subprocess.DEVNULL)
    
    return get_libreoffice_path() is not None


def main():
    print("=" * 60)
    print("  File Converter Pro")
    print("=" * 60)
    
    # Проверяем/устанавливаем LibreOffice
    lo_path = get_libreoffice_path()
    if not lo_path:
        print("\n❌ LibreOffice не найден")
        print("📥 Скачиваю автоматически (~500 MB)...\n")
        
        try:
            if download_libreoffice():
                lo_path = get_libreoffice_path()
                print(f"✅ LibreOffice установлен: {lo_path}")
            else:
                print("⚠️ Не удалось установить LibreOffice")
                print("   Установите вручную: brew install --cask libreoffice")
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            print("   Конвертация DOCX/PPTX будет недоступна")
    else:
        print(f"✅ LibreOffice найден: {lo_path}")
    
    print("\nЗапуск интерфейса...\n")
    
    # Запускаем GUI
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from loguru import logger
    
    logger.add(Path.home() / '.config' / 'file-converter' / 'logs' / 'app.log', 
               rotation='10 MB', retention='30 days', level='DEBUG')
    logger.add(sys.stderr, level='INFO')
    
    logger.info("Запуск File Converter Pro")
    
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont())
    
    app.setStyleSheet("""
        QMainWindow { background-color: #2b2b2b; }
        QLabel { color: #ffffff; }
        QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; border: none; border-radius: 4px; }
        QPushButton:hover { background-color: #45a049; }
        QPushButton:disabled { background-color: #666666; }
        QListWidget { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; }
        QComboBox { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; padding: 4px; }
        QProgressBar { border: 1px solid #555; border-radius: 3px; text-align: center; }
        QProgressBar::chunk { background-color: #4CAF50; }
        QTabWidget::pane { border: 1px solid #555; background-color: #2b2b2b; }
        QTabBar::tab { background-color: #3c3c3c; color: #ffffff; padding: 5px 10px; }
        QTabBar::tab:selected { background-color: #4a4a4a; }
        QGroupBox { color: #ffffff; border: 1px solid #555; margin-top: 10px; }
        QCheckBox { color: #ffffff; }
        QSpinBox { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; padding: 3px; }
        QTextEdit { background-color: #1e1e1e; color: #00ff00; border: 1px solid #555; }
        QScrollArea { background-color: #2b2b2b; border: none; }
    """)
    
    from src.gui.main_window import MainWindow
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
