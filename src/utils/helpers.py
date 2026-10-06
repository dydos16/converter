"""
Вспомогательные функции для приложения
"""
import os
import sys
import tempfile
import shutil
import platform
import zipfile
from pathlib import Path
from typing import Optional
import subprocess
from loguru import logger
from src.config.formats import FILE_TYPE_INFO


# --------------------------------------------------------------------------- #
#  Кроссплатформенные пути
# --------------------------------------------------------------------------- #
def get_platform() -> str:
    """Возвращает 'windows' | 'macos' | 'linux'."""
    s = platform.system().lower()
    if s == 'darwin':
        return 'macos'
    if s == 'windows':
        return 'windows'
    return 'linux'


def get_app_data_dir() -> Path:
    """
    Возвращает каталог данных приложения (для LibreOffice и пр.).

    macOS:   ~/Library/Application Support/FileConverterPro
    Windows: %LOCALAPPDATA%/FileConverterPro
    Linux:   ~/.local/share/FileConverterPro
    """
    system = get_platform()
    if system == 'windows':
        base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
        return Path(base) / "FileConverterPro"
    if system == 'macos':
        return Path.home() / "Library" / "Application Support" / "FileConverterPro"
    # Linux
    xdg_data = os.environ.get('XDG_DATA_HOME')
    if xdg_data:
        return Path(xdg_data) / "FileConverterPro"
    return Path.home() / ".local" / "share" / "FileConverterPro"


def get_config_dir() -> Path:
    """
    Возвращает каталог конфигурации (настройки, логи).

    macOS:   ~/Library/Application Support/FileConverterPro
    Windows: %APPDATA%/FileConverterPro
    Linux:   ~/.config/file-converter
    """
    system = get_platform()
    if system == 'windows':
        base = os.environ.get('APPDATA') or str(Path.home())
        return Path(base) / "FileConverterPro"
    if system == 'macos':
        return Path.home() / "Library" / "Application Support" / "FileConverterPro"
    # Linux
    xdg_conf = os.environ.get('XDG_CONFIG_HOME')
    if xdg_conf:
        return Path(xdg_conf) / "file-converter"
    return Path.home() / ".config" / "file-converter"


def get_libreoffice_dir() -> Path:
    """Каталог для встроенного/самодостаточного LibreOffice."""
    return get_app_data_dir() / "libreoffice"



def get_file_icon(extension: str) -> str:
    """Возвращает эмодзи для типа файла"""
    ext = extension.lower().lstrip('.')
    return FILE_TYPE_INFO.get(ext, {}).get('icon', '📁')


def get_file_type_name(extension: str) -> str:
    """Возвращает название типа файла"""
    ext = extension.lower().lstrip('.')
    return FILE_TYPE_INFO.get(ext, {}).get('name', 'Неизвестный формат')


# Остальные функции helpers.py остаются без изменений
def create_temp_dir() -> Path:
    """Создает временную директорию"""
    temp_dir = Path(tempfile.mkdtemp(prefix='converter_'))
    logger.debug(f"Создана временная директория: {temp_dir}")
    return temp_dir


def cleanup_temp_dir(temp_dir: Path):
    """Удаляет временную директорию"""
    try:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.debug(f"Удалена временная директория: {temp_dir}")
    except Exception as e:
        logger.warning(f"Не удалось удалить временную директорию {temp_dir}: {e}")


def get_file_size_str(path: Path) -> str:
    """Возвращает размер файла в человекочитаемом формате"""
    try:
        size = path.stat().st_size
    except OSError:
        return "размер неизвестен"
    return format_size(size)


ZIP_FORMATS = {"docx", "pptx", "ppsx", "xlsx", "odt", "odp", "ods"}       # внутри — всегда zip-архив
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"                              # старый контейнер Office


def _file_contains(path: Path, marker: bytes, chunk: int = 1 << 20) -> bool:
    """Есть ли в файле последовательность байт — читаем кусками, без загрузки файла целиком."""
    tail = b""
    with open(path, "rb") as f:
        while block := f.read(chunk):
            if marker in tail + block:
                return True
            tail = block[-len(marker):]
    return False


def input_problem(path: Path) -> Optional[str]:
    """Почему файл не сконвертировать ещё до начала: его нет, он пустой или повреждён. None — можно."""
    path = Path(path)
    if not path.exists():
        return f"Файл не найден: {path.name} — его переместили или удалили."
    if path.stat().st_size == 0:
        return f"Файл пустой: {path.name}."
    ext = path.suffix.lower().lstrip(".")
    if ext in ZIP_FORMATS and not zipfile.is_zipfile(path):
        with open(path, "rb") as f:
            ole = f.read(8) == OLE_MAGIC
        # Документ Office под паролем — не zip, а старый контейнер OLE с потоком EncryptedPackage
        if ole and _file_contains(path, "EncryptedPackage".encode("utf-16-le")):
            return (f"Документ защищён паролем: {path.name}. Откройте его в Word, Excel или PowerPoint, "
                    f"снимите пароль и сконвертируйте снова.")
        if not ole:
            # LibreOffice открыл бы такой файл как текст и «успешно» выдал бы абракадабру
            return f"Файл повреждён или это не {ext.upper()}: {path.name}."
        # иначе это старый .doc/.xls/.ppt с новым расширением — LibreOffice прочтёт его по содержимому
    if ext == "pdf":
        from src.converters.pdf_text import pdf_problem
        return pdf_problem(path)
    return None


def folder_writable(folder: Path) -> bool:
    """Можно ли писать в папку. Пробуем создать файл: os.access на Windows про папки врёт."""
    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False


def child_env() -> dict:
    """
    Окружение для чужих программ (LibreOffice, файловый менеджер). Собранное приложение подставляет себе
    свои библиотеки (LD_LIBRARY_PATH) и плагины Qt (QT_PLUGIN_PATH) — чужой программе они не подходят:
    Dolphin падает на «нашем» Qt, системный gio — на встроенной glib. Отдаём окружение как до запуска.
    """
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        env.pop("QT_PLUGIN_PATH", None)
        env.pop("QML2_IMPORT_PATH", None)
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)    # PyInstaller сохраняет сюда исходное значение
        if original is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = original
    return env


def open_folder(folder) -> None:
    """Показывает папку в Проводнике / Finder / файловом менеджере Linux."""
    if sys.platform == "win32":
        os.startfile(folder)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)], env=child_env())


def read_text_any(path: Path) -> str:
    """Текст файла в UTF-8 (с BOM или без) или в Windows-1251 — так сохраняют русский Excel и старый Блокнот."""
    data = Path(path).read_bytes()
    # UTF-16 с BOM: «Текст Юникод» из Excel, Блокнот «Юникод», вывод PowerShell «> файл.txt»
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


def format_size(size: float) -> str:
    """183 Б, 4,2 КБ, 12,5 МБ — по-русски, байты без дробей."""
    if size < 1024:
        return f"{int(size)} Б"
    for unit in ("КБ", "МБ", "ГБ"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}".replace(".", ",")
    return f"{size / 1024:.1f} ТБ".replace(".", ",")


def ensure_output_directory(output_path: Path) -> bool:
    """Создает директорию для выходного файла, если её нет"""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Не удалось создать директорию {output_path.parent}: {e}")
        return False


def get_unique_filename(path: Path, taken=()) -> Path:
    """
    Свободное имя: файла нет на диске, и оно не выдано другой задаче этой же очереди (taken) —
    два «отчёт.docx» из разных папок иначе получили бы один «отчёт.pdf»
    """
    if not path.exists() and path not in taken:
        return path

    counter = 1
    stem = path.stem
    suffix = path.suffix

    while True:
        new_path = path.parent / f"{stem} ({counter}){suffix}"
        if not new_path.exists() and new_path not in taken:
            return new_path
        counter += 1


def validate_file(file_path: Path, allowed_extensions: list[str]) -> tuple[bool, str]:
    """
    Проверяет файл на валидность
    """
    if not file_path.exists():
        return False, "Файл не существует"

    if not file_path.is_file():
        return False, "Путь указывает не на файл"

    ext = file_path.suffix.lower().lstrip('.')
    if ext not in allowed_extensions:
        return False, f"Формат {ext} не поддерживается"

    max_size = 500 * 1024 * 1024
    try:
        if file_path.stat().st_size > max_size:
            return False, f"Файл слишком большой (максимум 500MB)"
    except Exception:
        pass

    return True, "OK"