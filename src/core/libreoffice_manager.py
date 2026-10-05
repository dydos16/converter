"""
Менеджер LibreOffice с ленивой инициализацией и фоновой проверкой.
Обеспечивает thread-safe доступ к soffice и предотвращает блокирующие проверки при старте.
Использует оптимизированные параметры запуска для ускорения конвертации.
"""

import subprocess
import platform
import os
import re
import sys
import tarfile
import threading
import zipfile
import shutil
import urllib.request
from pathlib import Path
from typing import Optional
from loguru import logger
from PySide6.QtCore import QObject, QTimer, QThread, Signal


# Пакеты, которых обычно нет только на серверах и в минимальных контейнерах
LINUX_DEPS_COMMAND = (
    "sudo apt install libxinerama1 libnss3 libdbus-1-3 libcairo2 libx11-6 libx11-xcb1 "
    "libxext6 libcups2 libfontconfig1 libfreetype6 libgssapi-krb5-2 libxrender1 libsm6 libice6 libxrandr2"
)


def missing_libraries(stderr: str) -> list[str]:
    """Имена библиотек из ошибки загрузчика Linux: «error while loading shared libraries: libX.so.1: ...»"""
    return re.findall(r"error while loading shared libraries: (\S+?):", stderr or "")


def _skip_unsafe(member: tarfile.TarInfo, dest: str):
    """Фильтр 'data', но небезопасные элементы пропускаем, а не падаем.
    В .deb есть абсолютные симлинки вроде /usr/bin/libreoffice -> /opt/...: нам они не нужны."""
    try:
        return tarfile.data_filter(member, dest)
    except tarfile.FilterError:
        return None


def unpack_deb(deb: Path, dest: Path) -> None:
    """Распаковывает .deb без dpkg и sudo: это ar-архив, программа лежит в data.tar.*"""
    with open(deb, 'rb') as f:
        if f.read(8) != b'!<arch>\n':
            raise ValueError(f"{deb.name}: не ar-архив")
        while header := f.read(60):
            name = header[:16].decode().strip().rstrip('/')
            size = int(header[48:58])
            start = f.tell()
            if name.startswith('data.tar'):
                if name.endswith('.zst'):
                    raise ValueError(f"{deb.name}: zstd не поддерживается стандартной библиотекой")
                # 'r|*' читает поток последовательно и сам определяет xz/gz/bz2
                with tarfile.open(fileobj=f, mode='r|*') as tar:
                    tar.extractall(dest, filter=_skip_unsafe)
                return
            f.seek(start + size + (size % 2))   # элементы ar выровнены по 2 байта
    raise ValueError(f"{deb.name}: нет data.tar")


class LibreOfficeManager(QObject):
    """Синглтон-менеджер для управления LibreOffice (soffice) с ленивой загрузкой."""

    # Сигналы для уведомления GUI
    status_changed = Signal(str, bool)          # status_message, is_available
    check_finished = Signal(bool)               # is_available после проверки
    install_progress = Signal(int, str)         # percent(0-100), status_message
    install_finished = Signal(bool, str)        # success, message
    libraries_missing = Signal(str)             # каких системных библиотек не хватает soffice

    _instance: Optional['LibreOfficeManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию
        if getattr(self, '_initialized', False):
            return
        super().__init__()
        self._initialized = True

        self._soffice_path: Optional[Path] = None
        self._is_available: bool = False
        self._is_checking: bool = False
        self._check_timer: Optional[QTimer] = None
        self._install_thread: Optional[QThread] = None
        self._check_attempted: bool = False
        self._profile_lock = threading.Lock()
        self._profile_slots: dict[int, threading.Thread] = {}
        # Проверка идёт в фоновом потоке; таймер останавливаем уже в GUI-потоке
        self.check_finished.connect(self._on_check_finished)

        # Настройки таймера для фоновой проверки
        self._check_interval = 5000  # 5 секунд
        self._max_check_attempts = 3
        self._check_attempts = 0

        logger.debug("LibreOfficeManager initialized (lazy mode)")

    @staticmethod
    def get_app_support_dir() -> Path:
        """Возвращает каталог App Support, куда скачивается встроенный LibreOffice."""
        from src.utils.helpers import get_libreoffice_dir
        return get_libreoffice_dir()

    def _find_soffice(self) -> Optional[Path]:
        """Ищет исполняемый файл soffice в типичных местах."""
        system = platform.system()
        possible_paths = []

        # 1. Каталог App Support (встроенный / самодостаточный LibreOffice)
        app_support = self.get_app_support_dir()
        if system == "Darwin":  # macOS
            possible_paths.extend(app / "Contents" / "MacOS" / "soffice" for app in self._bundled_mac_apps())
        elif system == "Windows":
            # Административная распаковка MSI кладёт программу на 1–3 уровня глубже (например, PFiles\LibreOffice)
            win = app_support / "windows" / "LibreOffice"
            possible_paths.append(win / "program" / "soffice.exe")
            for depth in ("*", "*/*", "*/*/*"):
                possible_paths.extend(sorted(win.glob(f"{depth}/program/soffice.exe")))
        else:  # Linux
            possible_paths.append(app_support / "linux" / "usr" / "bin" / "soffice")
            # Из .deb программа попадает в opt/libreoffice<версия>/program
            possible_paths.extend(sorted((app_support / "linux" / "opt").glob("libreoffice*/program/soffice"),
                                         reverse=True))

        # 2. Системные пути
        if system == "Darwin":
            possible_paths.extend([
                Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
                Path("/opt/homebrew/bin/soffice"),
                Path("/usr/local/bin/soffice"),
            ])
        elif system == "Linux":
            possible_paths.extend([
                Path("/usr/bin/soffice"),
                Path("/usr/local/bin/soffice"),
                Path("/opt/libreoffice/program/soffice"),
            ])
        elif system == "Windows":
            possible_paths.extend([
                Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
                Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
            ])

        # Также проверяем PATH через which/where
        try:
            if system == "Windows":
                result = subprocess.run(
                    ["where", "soffice"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
            else:
                result = subprocess.run(
                    ["which", "soffice"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
            if result.returncode == 0 and result.stdout.strip():
                path_str = result.stdout.strip().split('\n')[0]  # Берем первое совпадение
                possible_paths.insert(0, Path(path_str))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # Ignore - PATH lookup failed

        for path in possible_paths:
            if path.is_file() and os.access(path, os.X_OK):
                logger.info(f"Найден soffice: {path}")
                return path

        logger.debug("Soffice не найден в стандартных местах")
        return None

    def _bundled_mac_apps(self) -> list:
        """Где может лежать скачанный LibreOffice.app: в Intel-архиве — в macos/, в arm64 — в корне."""
        app_support = self.get_app_support_dir()
        return [app_support / "macos" / "LibreOffice.app", app_support / "LibreOffice.app"]

    def _get_user_profile_path(self) -> str:
        """
        Возвращает путь к изолированному пользовательскому профилю LibreOffice.
        Используем собственный каталог в App Support, чтобы избежать повреждённого
        системного профиля (~/Library/Application Support/LibreOffice), вызывающего
        DeploymentException при конвертации.
        Каждый поток получает свой слот профиля: два soffice на одном профиле
        мешают друг другу, и параллельные конвертации падают или зависают.
        """
        me = threading.current_thread()
        with self._profile_lock:
            slot = next((i for i, t in self._profile_slots.items() if t is me), None)
            if slot is None:
                slot = next((i for i, t in self._profile_slots.items() if not t.is_alive()),
                            len(self._profile_slots))
                self._profile_slots[slot] = me
        profile = self.get_app_support_dir() / "profile" / str(slot)
        profile.mkdir(parents=True, exist_ok=True)
        # as_uri() корректно кодирует пробелы (например в "Application Support") -> %20
        return profile.as_uri()

    def _get_optimized_cmd(self, input_path: Path, output_path: Path) -> list:
        """
        Возвращает оптимизированную команду LibreOffice для конвертации в PDF.
        Использует изолированный пользовательский профиль и параметры, ускоряющие
        конвертацию, НЕ снижая качество.
        """
        if not self._soffice_path:
            raise RuntimeError("Soffice path not initialized")

        cmd = [
            str(self._soffice_path),
            f"-env:UserInstallation={self._get_user_profile_path()}",
            '--headless',           # Без GUI
            '--invisible',          # Не показывать окна
            '--nocrashreport',      # Отключить отчёт о сбоях
            '--nofirststartwizard', # Отключить мастер первого запуска
            '--nologo',             # Без логотипа
            '--norestore',          # Не восстанавливать документы
            '--nodefault',          # Не загружать документ по умолчанию
        ]

        # Параметры PDF
        cmd.extend([
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ])

        return cmd

    def _report_missing_libraries(self, stderr: str) -> bool:
        """Если soffice не запустился из-за системных библиотек — сообщаем, чем их поставить."""
        libs = missing_libraries(stderr)
        if not libs:
            return False
        logger.error(f"LibreOffice не хватает системных библиотек ({', '.join(libs)}). Установите: {LINUX_DEPS_COMMAND}")
        if not getattr(self, "_libs_reported", False):   # подсказку показываем один раз, а не на каждый файл
            self._libs_reported = True
            self.libraries_missing.emit(", ".join(libs))
        return True

    def _check_availability(self):
        """Выполняет реальную проверку доступности soffice через --version."""
        if self._is_checking:
            return

        self._is_checking = True
        self._check_attempted = True
        self._check_attempts += 1
        logger.debug(f"Проверка доступности LibreOffice (попытка {self._check_attempts})")

        def _run_check():
            try:
                if not self._soffice_path:
                    self._soffice_path = self._find_soffice()

                if self._soffice_path and self._soffice_path.is_file():
                    result = subprocess.run(
                        [str(self._soffice_path), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        version_info = result.stdout.strip()
                        logger.info(f"LibreOffice доступен: {version_info}")
                        self._is_available = True
                        self.status_changed.emit(f"LibreOffice готов: {version_info}", True)
                    elif self._report_missing_libraries(result.stderr):
                        self._is_available = False
                        self.status_changed.emit("LibreOffice: не хватает системных библиотек", False)
                    else:
                        logger.warning(f"Soffice вернул код ошибки: {result.returncode}")
                        self._is_available = False
                        self.status_changed.emit("LibreOffice установлен, но не отвечает", False)
                else:
                    logger.info("Soffice не найден")
                    self._is_available = False
                    self.status_changed.emit("LibreOffice не установлен", False)

            except subprocess.TimeoutExpired:
                logger.warning("Проверка LibreOffice таймаут (>10s)")
                self._is_available = False
                self.status_changed.emit("LibreOffice не отвечает (таймаут проверки)", False)
            except Exception as e:
                logger.error(f"Ошибка при проверке LibreOffice: {e}")
                self._is_available = False
                self.status_changed.emit(f"Ошибка проверки LibreOffice: {e}", False)
            finally:
                self._is_checking = False
                self.check_finished.emit(self._is_available)

        # soffice --version может идти секунды — не блокируем GUI
        threading.Thread(target=_run_check, daemon=True, name="LibreOfficeCheck").start()

    def _on_check_finished(self, available: bool):
        """Вызывается в GUI-потоке: останавливает таймер при успехе или исчерпании попыток."""
        if available or self._check_attempts >= self._max_check_attempts:
            self.stop_periodic_check()
            logger.info(f"Проверка LibreOffice завершена: {'доступен' if available else 'недоступен'}")

    def start_periodic_check(self):
        """Запускает периодическую проверку доступности LibreOffice."""
        if self._check_timer is not None:
            return  # Уже запущен

        self._check_timer = QTimer()
        self._check_timer.timeout.connect(self._check_availability)
        self._check_timer.setInterval(self._check_interval)
        self._check_timer.start()
        self._check_attempts = 0
        logger.debug("Запущена периодическая проверка LibreOffice")

        # Сразу выполняем первую проверку
        self._check_availability()

    def stop_periodic_check(self):
        """Останавливает периодическую проверку."""
        if self._check_timer:
            self._check_timer.stop()
            self._check_timer.deleteLater()
            self._check_timer = None
            logger.debug("Периодическая проверка LibreOffice остановлена")

    # ------------------------------------------------------------------
    # Автоматическая установка при отсутствии LibreOffice
    # ------------------------------------------------------------------

    def _libreoffice_archive_url(self) -> str:
        """Возвращает URL для скачивания LibreOffice под текущую платформу."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        arch = 'arm64' if machine in ('arm64', 'aarch64') else 'x86_64'
        base = "https://github.com/MiHoN135/Convertator-Releases/releases/download/v1.0.0"
        if system == 'darwin':
            # В релизе Intel-сборка лежит без суффикса архитектуры
            return f"{base}/libreoffice_macos_arm64.tar.gz" if arch == 'arm64' else f"{base}/libreoffice_macos.tar.gz"
        elif system == 'windows':
            return f"{base}/libreoffice_windows.zip"
        else:
            return (f"{base}/LibreOffice_26.2.2_Linux_aarch64_deb.tar.gz" if arch == 'arm64'
                    else f"{base}/libreoffice_linux.tar.gz")

    def _download_with_progress(self, url: str, dest: Path) -> bool:
        """Скачивает файл по URL, отчитываясь о прогрессе."""
        app_support = self.get_app_support_dir()
        app_support.mkdir(parents=True, exist_ok=True)

        last = [-1]

        def _report(block_num, block_size, total_size):
            if total_size <= 0:
                return
            percent = min(int(block_num * block_size / total_size * 100), 99)
            # urlretrieve зовёт это каждые 8 КБ — шлём в GUI только смену процента
            if percent != last[0]:
                last[0] = percent
                self.install_progress.emit(percent, f"Скачивание LibreOffice... {percent}%")

        try:
            logger.info(f"Скачивание LibreOffice: {url}")
            urllib.request.urlretrieve(url, dest, reporthook=_report)
            self.install_progress.emit(100, "Скачивание завершено, распаковка...")
            return True
        except Exception as e:
            logger.error(f"Ошибка скачивания LibreOffice: {e}")
            return False

    def _extract_libreoffice(self, archive_path: Path) -> None:
        """Распаковывает архив LibreOffice в App Support."""
        app_support = self.get_app_support_dir()
        app_support.mkdir(parents=True, exist_ok=True)

        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as z:
                z.extractall(app_support)
        else:
            with tarfile.open(archive_path, 'r:gz') as tar:
                # filter='data' запрещает пути вне app_support, симлинки наружу и setuid
                tar.extractall(app_support, filter='data')

        # Удаляем архив
        try:
            archive_path.unlink()
        except OSError:
            pass

        if platform.system().lower() == 'linux':
            self._unpack_linux_debs(app_support)
        elif platform.system().lower() == 'windows':
            self._unpack_windows_msi(app_support)

        # Для macOS снимаем quarantine и ставим права
        if platform.system().lower() == 'darwin':
            for lo_app in (a for a in self._bundled_mac_apps() if a.exists()):
                subprocess.run(['xattr', '-d', '-r', 'com.apple.quarantine', str(lo_app)],
                               stderr=subprocess.DEVNULL)
                subprocess.run(['chmod', '-R', '755', str(lo_app)], stderr=subprocess.DEVNULL)
                subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(lo_app)],
                               capture_output=True)

    def _unpack_linux_debs(self, app_support: Path) -> None:
        """Linux-архив — официальный набор .deb, а не готовая программа: разворачиваем пакеты сами."""
        for bundle in app_support.glob("LibreOffice_*_deb"):
            # «._*.deb» — служебные двойники macOS (AppleDouble), если архив собирали на Mac
            debs = sorted(d for d in bundle.glob("DEBS/*.deb") if not d.name.startswith("._"))
            for i, deb in enumerate(debs, 1):
                self.install_progress.emit(99, f"Установка пакетов LibreOffice {i}/{len(debs)}...")
                unpack_deb(deb, app_support / "linux")
            shutil.rmtree(bundle, ignore_errors=True)   # сами .deb больше не нужны
        for junk in app_support.glob("._*"):
            junk.unlink(missing_ok=True)

    def _unpack_windows_msi(self, app_support: Path) -> None:
        """Windows-архив — это установщик .msi, а не готовая программа.
        msiexec /a — административная распаковка: просто выкладывает файлы в нашу папку,
        ничего не устанавливает в систему и не требует прав администратора."""
        target = app_support / "windows" / "LibreOffice"
        for msi in sorted(app_support.rglob("*.msi")):
            self.install_progress.emit(99, "Распаковка установщика LibreOffice...")
            target.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["msiexec", "/a", str(msi), "/qn", f"TARGETDIR={target}"],
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode != 0:
                logger.error(f"msiexec /a завершился с кодом {result.returncode}: {result.stderr or result.stdout}")
            # Сам установщик и его копия, которую msiexec кладёт рядом с файлами, больше не нужны
            msi.unlink(missing_ok=True)
            for copy in target.glob("*.msi"):
                copy.unlink(missing_ok=True)
        shutil.rmtree(app_support / "resources", ignore_errors=True)

    def start_auto_install(self):
        """
        Запускает фоновую установку LibreOffice, если он не установлен.
        Не блокирует GUI — установка выполняется в отдельном QThread.
        """
        if self._is_available or self._install_thread is not None:
            return

        self.status_changed.emit("LibreOffice не установлен, загрузка...", False)

        self._install_thread = QThread()
        self._install_thread.run = self._do_install_blocking  # type: ignore[method-assign]
        self._install_thread.finished.connect(self._on_install_thread_finished)
        self._install_thread.start()

    def _do_install_blocking(self):
        """Выполняет установку LibreOffice (блокирующий, в потоке)."""
        try:
            logger.info("Начало автоматической установки LibreOffice")
            self.install_progress.emit(0, "Подготовка к загрузке LibreOffice...")

            app_support = self.get_app_support_dir()
            app_support.mkdir(parents=True, exist_ok=True)

            url = self._libreoffice_archive_url()
            ext = url.split('.')[-1]
            archive_path = app_support / f"libreoffice_download.{ext}"

            if not self._download_with_progress(url, archive_path):
                self.install_progress.emit(0, "Ошибка скачивания LibreOffice")
                self.install_finished.emit(False, "Не удалось скачать LibreOffice. Проверьте интернет-соединение.")
                return

            self._extract_libreoffice(archive_path)

            # Проверяем результат
            soffice = self._find_soffice()
            if soffice and soffice.is_file():
                self._soffice_path = soffice
                self._is_available = True
                self.install_progress.emit(100, "LibreOffice установлен!")
                self.install_finished.emit(True, "LibreOffice успешно установлен")
            else:
                logger.error(f"После распаковки soffice не найден в {app_support}")
                self.install_progress.emit(0, "Не удалось найти soffice после установки")
                self.install_finished.emit(False, "LibreOffice установлен, но не найден исполняемый файл")
        except Exception as e:
            logger.exception(f"Ошибка установки LibreOffice: {e}")
            self.install_finished.emit(False, f"Ошибка установки LibreOffice: {e}")

    def _on_install_thread_finished(self):
        """Обработчик завершения потока установки."""
        if self._install_thread:
            self._install_thread.deleteLater()
            self._install_thread = None

        # Перепроверяем доступность
        self._soffice_path = None
        self._check_availability()

    def is_available(self) -> bool:
        """Возвращает статус доступности LibreOffice.

        Ленивая проверка: если проверка ещё не выполнялась (например, конвертер
        вызван вне GUI, где не запускается start_periodic_check), выполняет
        синхронную проверку наличия soffice.
        """
        if not self._check_attempted:
            self._check_attempted = True
            self._soffice_path = self._find_soffice()
            if self._soffice_path:
                self._is_available = True
        return self._is_available

    def get_soffice_path(self) -> Optional[Path]:
        """Возвращает путь к soffice, если доступен."""
        return self._soffice_path if self._is_available else None

    def convert_to_pdf(self, input_path: Path, output_path: Path, progress_callback=None) -> bool:
        """
        Конвертирует документ в PDF через LibreOffice.
        Выполняет блокирующий вызов — должен использоваться в QThread (например, через JobManager).
        """
        # Ленивая проверка: если ещё не искали soffice, ищем сейчас
        if not self._check_attempted:
            self.is_available()

        if not self._is_available:
            logger.error("LibreOffice недоступен для конвертации")
            return False

        if not self._soffice_path:
            logger.error("Путь к soffice не определен")
            return False

        try:
            cmd = self._get_optimized_cmd(input_path, output_path)
            logger.info(f"Запуск оптимизированной конвертации: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                stdin=subprocess.DEVNULL,
            )

            if result.returncode != 0:
                logger.error(f"LibreOffice ошибка: {result.stderr}")
                self._report_missing_libraries(result.stderr)
                return False

            # LibreOffice создает файл с тем же именем, но .pdf в outdir
            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                logger.info(f"Конвертация успешна: {output_path}")
                if progress_callback:
                    progress_callback(100)
                return True
            else:
                logger.error(f"Ожидаемый PDF не найден: {expected_pdf}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации LibreOffice (>300s)")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации через LibreOffice: {e}")
            return False