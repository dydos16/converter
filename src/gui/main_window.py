"""
Главное окно приложения для PySide6
"""
import os
import re
import subprocess
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLabel,
    QFileDialog, QTextEdit, QApplication, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFontDatabase, QShortcut, QKeySequence, QPalette

from src.converters.factory import ConverterFactory
from src.core.job_manager import JobManager, ConversionJob, JobStatus
from src.core.libreoffice_manager import LibreOfficeManager
from src.core.settings import Settings
from src.gui.styles import get_stylesheet_for, get_palette_for, RED
from src.gui.mac_titlebar import style_titlebar
from src.gui.glass import (
    PrimaryButton, IconButton, GlassCombo, GlassSpin, GlassSlider, Toggle, GlassProgress,
    TabBar, FadeStack, FileList, Toast, GlassPopup, InsetSection, Row, SliderRow, PageHeader,
    PROGRESS_ROLE, META_ROLE,
)
from src.utils.helpers import get_file_size_str, get_unique_filename, ensure_output_directory
from loguru import logger


def files_word(n: int) -> str:
    """3 файла, 5 файлов, 21 файл"""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} файл"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} файла"
    return f"{n} файлов"


class ConversionWorker(QThread):
    """Поток для выполнения конвертации"""
    progress_updated = Signal(str, int)
    job_completed = Signal(str, bool, str)
    job_finished = Signal()

    def __init__(self, job_manager: JobManager):
        super().__init__()
        self.job_manager = job_manager

    def run(self):
        self.job_manager.start()
        self.exec()


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    # Сигналы для безопасного вызова из потоков
    show_info_signal = Signal(str, str)
    show_warning_signal = Signal(str, str)
    show_error_signal = Signal(str, str)

    # Сигналы для обновления UI из рабочих потоков
    update_file_item_signal = Signal(str, int)  # file_path, progress
    update_status_signal = Signal()
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.job_manager = JobManager(max_concurrent=self.settings.get('max_concurrent_jobs', 3))
        self.libreoffice_manager = LibreOfficeManager()
        self.libreoffice_manager.status_changed.connect(self._on_libreoffice_status_changed)
        self.libreoffice_manager.install_progress.connect(self._on_libreoffice_install_progress)
        self.libreoffice_manager.install_finished.connect(self._on_libreoffice_install_finished)
        self.libreoffice_manager.libraries_missing.connect(self._on_libreoffice_libraries_missing)
        self.worker = ConversionWorker(self.job_manager)

        # Единый таймер для обновления статуса
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.setInterval(500)  # 500ms для плавности

        # Флаг для блокировки повторного запуска
        self.conversion_in_progress = False

        # Подключаем сигналы
        self.show_info_signal.connect(self._show_info_message)
        self.show_warning_signal.connect(self._show_warning_message)
        self.show_error_signal.connect(self._show_error_message)
        self.update_file_item_signal.connect(self._update_file_item_progress)
        self.update_status_signal.connect(self._update_status_forced)
        self.log_signal.connect(self._append_log)

        self.setup_ui()
        self.setup_callbacks()
        self.load_settings()
        self.apply_theme_from_settings()

        self.worker.start()

    # Уведомления — ненавязчивый тост внизу окна, а не модальное окно на каждый файл
    @Slot(str, str)
    def _show_info_message(self, title: str, message: str):
        self.toast.show_message(message, "success")

    @Slot(str, str)
    def _show_warning_message(self, title: str, message: str):
        self.toast.show_message(message, "info")

    @Slot(str, str)
    def _show_error_message(self, title: str, message: str):
        self.toast.show_message(message.replace("\n\n", ": "), "error", 5000)

    @Slot(str, int)
    def _update_file_item_progress(self, file_path: str, progress: int):
        """Обновляет прогресс в элементе списка (вызывается из сигнала)"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item_path = item.data(Qt.ItemDataRole.UserRole)
            if item_path == file_path:
                item.setData(PROGRESS_ROLE, progress)
                break

    @Slot()
    def _update_status_forced(self):
        """Принудительное обновление статуса"""
        self.update_status()

    @staticmethod
    def _short_lo_status(message: str, available: bool) -> str:
        """«LibreOffice готов: LibreOffice 26.2.2.2 1f77…» → «Готов · 26.2.2.2» — чтобы влезло в строку настроек."""
        if available:
            version = re.search(r"\d+(?:\.\d+)+", message)
            return f"Готов · {version.group(0)}" if version else "Готов"
        text = re.sub(r"\s*LibreOffice\b:?", "", message).strip()
        return text[:1].upper() + text[1:]

    @Slot(str, bool)
    def _on_libreoffice_status_changed(self, message: str, is_available: bool):
        """Обновляет состояние LibreOffice в настройках"""
        self.libreoffice_status_label.setText(self._short_lo_status(message, is_available))
        if is_available:
            self.libreoffice_status_label.setStyleSheet("color: #34C759;")
            self.status_progress_bar.hide()
        else:
            self.libreoffice_status_label.setStyleSheet("color: #FF3B30;")

    @Slot(int, str)
    def _on_libreoffice_install_progress(self, percent: int, message: str):
        """Обновляет прогресс автоматической установки LibreOffice."""
        self.libreoffice_status_label.setText(self._short_lo_status(message, False))
        self.status_progress_bar.setValue(percent)
        self.status_progress_bar.show()

    @Slot(bool, str)
    def _on_libreoffice_install_finished(self, success: bool, message: str):
        """Обрабатывает завершение установки LibreOffice."""
        if success:
            self.status_progress_bar.hide()
            self.libreoffice_status_label.setText("Готов")
            self.libreoffice_status_label.setStyleSheet("color: #34C759;")
        else:
            self.status_progress_bar.setValue(0)
            self.status_progress_bar.hide()
            self.libreoffice_status_label.setText("Недоступен")
            self.libreoffice_status_label.setStyleSheet("color: #FF3B30;")

    @Slot(str)
    def _on_libreoffice_libraries_missing(self, libs: str):
        """LibreOffice скачан, но не запускается: в системе нет нужных библиотек (бывает на серверах)."""
        from src.core.libreoffice_manager import LINUX_DEPS_COMMAND
        self._append_log(f"LibreOffice не запускается: в системе нет библиотек {libs}.\n"
                         f"Установите их командой:\n{LINUX_DEPS_COMMAND}")
        self.toast.show_message("LibreOffice не хватает системных библиотек — команда установки в «Журнале»",
                                "error", 10000)

    def maybe_start_libreoffice_install(self):
        """Запускает автоустановку LibreOffice при его отсутствии (не блокирует GUI)."""
        if not self.libreoffice_manager.is_available():
            # Даём GUI отрисоваться, затем запускаем загрузку в фоне
            QTimer.singleShot(500, self.libreoffice_manager.start_auto_install)

    def apply_theme(self, mode: str):
        """
        Применяет тему ('system'|'light'|'dark') ко всему приложению.
        В режиме 'system' тема определяется автоматически по ОС.
        """
        self.settings.set('theme', mode)
        app = QApplication.instance()
        if app is None:
            return
        app.setPalette(get_palette_for(mode))
        app.setStyleSheet(get_stylesheet_for(mode))
        self._style_titlebar()

    def apply_theme_from_settings(self):
        """Применяет тему из сохранённых настроек при запуске."""
        mode = self.settings.get('theme', 'system')
        app = QApplication.instance()
        if app is not None:
            app.setPalette(get_palette_for(mode))
            app.setStyleSheet(get_stylesheet_for(mode))

    def on_theme_changed(self, mode: str):
        """Обработчик смены темы в настройках — применяет сразу."""
        self.apply_theme(mode)

    def _style_titlebar(self):
        """На маке — родная шапка окна цвета фона: перетаскивание и двойной клик делает сама macOS."""
        mode = self.settings.get('theme', 'system')
        style_titlebar(self, get_palette_for(mode).color(QPalette.ColorRole.Window),
                       None if mode == 'system' else mode == 'dark')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_overlays()

    def _place_overlays(self):
        """Панель вкладок и уведомления плавают поверх страниц у нижнего края."""
        c = self.centralWidget()
        self.tabs.move((c.width() - self.tabs.width()) // 2, c.height() - self.tabs.height() - 8)
        self.tabs.raise_()
        self.toast.reposition()

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_shown_once", False):
            return
        self._shown_once = True
        self._place_overlays()
        # Внутри цикла событий: у AppKit там есть autorelease pool
        QTimer.singleShot(0, self._style_titlebar)
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(260)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in.setEndValue(1.0)
        self._fade_in.start()

    def setup_ui(self):
        """Настраивает интерфейс"""
        self.setWindowTitle("File Converter Pro")
        self.resize(980, 780)
        self.setMinimumSize(760, 620)
        mac = sys.platform == 'darwin'

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 4 if mac else 14, 0, 0)   # на маке сверху родная шапка окна

        self.pages = FadeStack()
        main_layout.addWidget(self.pages)
        for setup in (self.setup_conversion_tab, self.setup_settings_tab, self.setup_log_tab):
            page = QWidget()
            setup(page)
            self.pages.addWidget(page)

        self.tabs = TabBar([("Конвертер", "arrows"), ("Настройки", "gear"), ("Журнал", "list")], central)
        self.tabs.currentChanged.connect(self.pages.setCurrentIndex)
        self.tabs.backdrop_source = self.pages      # стекло панели преломляет содержимое страниц
        self.toast = Toast(central)

        # ⌘1–⌘3 — вкладки, ⌘O — добавить файлы (Ctrl на Windows и Linux)
        for i in range(3):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.tabs.setCurrentIndex(i))
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.add_files)

    def setup_conversion_tab(self, parent: QWidget):
        """Страница конвертации: формат, очередь как список чатов, кнопка действия"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(24, 0, 24, 100)
        layout.setSpacing(18)

        self.add_files_btn = IconButton("plus", "Добавить файлы (⌘O)")
        # Диалог открываем после того, как кнопка отрисовала отпускание
        self.add_files_btn.clicked.connect(lambda: QTimer.singleShot(0, self.add_files))
        self.add_folder_btn = IconButton("folder", "Добавить папку")
        self.add_folder_btn.clicked.connect(lambda: QTimer.singleShot(0, self.add_folder))
        self.clear_btn = IconButton("trash", "Очистить список")
        self.clear_btn.clicked.connect(self.clear_files)
        self.header = PageHeader("Конвертер", [self.clear_btn, self.add_folder_btn, self.add_files_btn])
        self.header.setSubtitle("Готов к работе")
        self.status_label = self.header.subtitle
        layout.addWidget(self.header)

        self.input_format_combo = GlassCombo()
        self.input_format_combo.addItems(['Все'] + ConverterFactory.get_input_formats())
        self.input_format_combo.currentTextChanged.connect(self.on_input_format_changed)
        self.output_format_combo = GlassCombo()
        self.output_format_combo.setEnabled(False)
        self.output_format_combo.currentTextChanged.connect(self.update_convert_button)

        formats = InsetSection("Формат")
        formats.add(Row("Из", self.input_format_combo, "doc", "#007AFF"))
        formats.add(Row("В", self.output_format_combo, "arrows", "#34C759"))
        layout.addWidget(formats)

        self.file_group = InsetSection("Очередь")
        self.file_group.rows.setContentsMargins(0, 4, 0, 4)
        self.file_list = FileList()
        self.file_list.setAcceptDrops(True)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(200)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_context_menu)
        self.file_list.browseRequested.connect(lambda: QTimer.singleShot(0, self.add_files))
        self.file_group.add(self.file_list, 1)
        layout.addWidget(self.file_group, 1)

        self.total_progress = GlassProgress()
        self.total_progress.hide()           # показываем только пока идёт конвертация
        layout.addWidget(self.total_progress)

        self.convert_btn = PrimaryButton("Конвертировать")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setEnabled(False)
        self.convert_btn.setFixedSize(self.convert_btn.sizeHint())   # с полем под «подъём» при нажатии
        layout.addWidget(self.convert_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # Включаем Drag & Drop
        self.setAcceptDrops(True)

    def setup_settings_tab(self, parent: QWidget):
        """Страница настроек: сгруппированные списки, всё сохраняется сразу"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 0, 24, 100)
        layout.setSpacing(22)
        layout.addWidget(PageHeader("Настройки"))

        # Оформление
        self.theme_combo = GlassCombo()
        for label, val in [("Системная", "system"), ("Светлая", "light"), ("Тёмная", "dark")]:
            self.theme_combo.addItem(label, val)
        self.theme_combo.setCurrentIndex({"system": 0, "light": 1, "dark": 2}.get(self.settings.get('theme', 'system'), 0))
        self.theme_combo.currentIndexChanged.connect(lambda idx: self.on_theme_changed(self.theme_combo.itemData(idx)))
        appear = InsetSection("Оформление", "«Системная» следует за светлой или тёмной темой ОС.")
        appear.add(Row("Тема", self.theme_combo, "moon", "#5856D6"))
        layout.addWidget(appear)

        # Изображения
        self.quality_slider = GlassSlider()
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(int(self.settings.get('image_quality') or 85))
        self.max_width_spin = GlassSpin()
        self.max_width_spin.setRange(0, 10000)
        self.max_width_spin.setSpecialValueText("Без ограничений")
        self.max_width_spin.setValue(int(self.settings.get('image_max_width') or 0))
        self.max_height_spin = GlassSpin()
        self.max_height_spin.setRange(0, 10000)
        self.max_height_spin.setSpecialValueText("Без ограничений")
        self.max_height_spin.setValue(int(self.settings.get('image_max_height') or 0))
        images = InsetSection("Изображения", "Качество применяется при сохранении в JPG и WebP.")
        images.add(SliderRow("Качество JPEG и WebP", self.quality_slider))
        images.add(Row("Максимальная ширина", self.max_width_spin))
        images.add(Row("Максимальная высота", self.max_height_spin))
        layout.addWidget(images)

        # PDF
        self.pdf_dpi_spin = GlassSpin()
        self.pdf_dpi_spin.setRange(72, 600)
        self.pdf_dpi_spin.setSuffix(" DPI")
        self.pdf_dpi_spin.setValue(self.settings.get('pdf_dpi', 200))
        self.pdf_quality_slider = GlassSlider()
        self.pdf_quality_slider.setRange(1, 100)
        self.pdf_quality_slider.setValue(self.settings.get('pdf_quality', 85))
        self.pdf_compress_spin = GlassSpin()
        self.pdf_compress_spin.setRange(0, 9)
        self.pdf_compress_spin.setValue(self.settings.get('pdf_compress_level', 6))
        self.pdf_compress_spin.setToolTip("0 — без сжатия, 9 — максимальное сжатие")
        self.pdf_remove_metadata_check = Toggle()
        self.pdf_remove_metadata_check.setChecked(self.settings.get('pdf_remove_metadata', False))
        self.pdf_optimize_images_check = Toggle()
        self.pdf_optimize_images_check.setChecked(self.settings.get('pdf_optimize_images', True))
        self.table_strategy_combo = GlassCombo()
        self.table_strategy_combo.addItems(['auto', 'lattice', 'stream'])
        self.table_strategy_combo.setCurrentText(self.settings.get('pdf_table_strategy', 'auto'))
        pdf = InsetSection("PDF", "Таблицы: lattice — с сеткой, stream — без сетки, auto — определить самому.")
        pdf.add(Row("Разрешение страниц", self.pdf_dpi_spin))
        pdf.add(SliderRow("Качество изображений", self.pdf_quality_slider))
        pdf.add(Row("Уровень сжатия", self.pdf_compress_spin))
        pdf.add(Row("Удалять метаданные", self.pdf_remove_metadata_check))
        pdf.add(Row("Оптимизировать изображения", self.pdf_optimize_images_check))
        pdf.add(Row("Извлечение таблиц", self.table_strategy_combo))
        layout.addWidget(pdf)

        # HEIC
        self.heic_quality_slider = GlassSlider()
        self.heic_quality_slider.setRange(1, 100)
        self.heic_quality_slider.setValue(self.settings.get('heic_quality', 85))
        heic = InsetSection("Фото HEIC с iPhone")
        heic.add(SliderRow("Качество", self.heic_quality_slider))
        layout.addWidget(heic)

        # Общие
        self.max_jobs_spin = GlassSpin()
        self.max_jobs_spin.setRange(1, 10)
        self.max_jobs_spin.setValue(self.settings.get('max_concurrent_jobs', 3))
        self.max_jobs_spin.valueChanged.connect(self._update_max_concurrent)
        self.auto_open_check = Toggle()
        self.auto_open_check.setChecked(self.settings.get('auto_open_folder', True) is not False)
        self.keep_name_check = Toggle()
        self.keep_name_check.setChecked(self.settings.get('keep_original_name', True) is not False)
        self.notifications_check = Toggle()
        self.notifications_check.setChecked(self.settings.get('show_notifications', True) is not False)
        general = InsetSection("Общие")
        general.add(Row("Одновременных задач", self.max_jobs_spin, "bolt", "#FF9500"))
        general.add(Row("Открывать папку после конвертации", self.auto_open_check, "folder", "#007AFF"))
        general.add(Row("Сохранять исходное имя файла", self.keep_name_check, "tag", "#34C759"))
        general.add(Row("Уведомления", self.notifications_check, "bell", "#FF3B30"))
        layout.addWidget(general)

        # LibreOffice: состояние и прогресс автоустановки
        self.libreoffice_status_label = QLabel("Проверка…")
        self.libreoffice_status_label.setProperty("value", True)
        self.status_progress_bar = GlassProgress()
        self.status_progress_bar.setFixedWidth(110)
        self.status_progress_bar.hide()
        lo_state = QWidget()
        lo_layout = QHBoxLayout(lo_state)
        lo_layout.setContentsMargins(0, 0, 0, 0)
        lo_layout.setSpacing(10)
        lo_layout.addWidget(self.status_progress_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        lo_layout.addWidget(self.libreoffice_status_label)
        office = InsetSection("LibreOffice", "Нужен для документов Word, Excel и PowerPoint. Скачивается автоматически.")
        office.add(Row("Состояние", lo_state, "box", "#8E8E93"))
        layout.addWidget(office)
        layout.addStretch()

        scroll.setWidget(content)
        parent_layout = QVBoxLayout(parent)
        parent_layout.setContentsMargins(0, 0, 0, 0)
        parent_layout.addWidget(scroll)

        # Настройки сохраняются сами, как в iOS: через 0,4 с после последнего изменения
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self.save_settings)
        schedule = lambda *_: self._save_timer.start()  # noqa: E731 — сигналы передают значение, start(int) его бы принял
        for w in (self.quality_slider, self.pdf_quality_slider, self.heic_quality_slider, self.max_width_spin,
                  self.max_height_spin, self.pdf_dpi_spin, self.pdf_compress_spin, self.max_jobs_spin):
            w.valueChanged.connect(schedule)
        for w in (self.pdf_remove_metadata_check, self.pdf_optimize_images_check, self.auto_open_check,
                  self.keep_name_check, self.notifications_check):
            w.toggled.connect(schedule)
        self.table_strategy_combo.currentIndexChanged.connect(schedule)

    def setup_log_tab(self, parent: QWidget):
        """Страница журнала"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(24, 0, 24, 100)
        layout.setSpacing(18)
        clear_log_btn = IconButton("trash", "Очистить журнал")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        layout.addWidget(PageHeader("Журнал", [clear_log_btn]))

        section = InsetSection()
        section.rows.setContentsMargins(14, 10, 14, 10)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPixelSize(12)
        self.log_text.setFont(mono)
        section.add(self.log_text, 1)
        layout.addWidget(section, 1)

    def setup_callbacks(self):
        """Настраивает callback'и менеджера задач"""
        self.job_manager.register_callback('on_job_started', self.on_job_started)
        self.job_manager.register_callback('on_job_progress', self.on_job_progress)
        self.job_manager.register_callback('on_job_completed', self.on_job_completed)
        self.job_manager.register_callback('on_job_failed', self.on_job_failed)

    def load_settings(self):
        """Загружает настройки"""
        recent_formats = self.settings.get('recent_formats', [])
        if recent_formats:
            last_format = recent_formats[0]
            if '→' in last_format:
                inp, out = last_format.split('→')
                index = self.input_format_combo.findText(inp)
                if index >= 0:
                    self.input_format_combo.setCurrentIndex(index)

    def save_settings(self):
        """Сохраняет настройки"""
        self.settings.update({
            # Настройки изображений
            'image_quality': self.quality_slider.value(),
            'image_max_width': self.max_width_spin.value() if self.max_width_spin.value() > 0 else None,
            'image_max_height': self.max_height_spin.value() if self.max_height_spin.value() > 0 else None,

            # Настройки PDF
            'pdf_dpi': self.pdf_dpi_spin.value(),
            'pdf_quality': self.pdf_quality_slider.value(),
            'pdf_compress_level': self.pdf_compress_spin.value(),
            'pdf_remove_metadata': self.pdf_remove_metadata_check.isChecked(),
            'pdf_optimize_images': self.pdf_optimize_images_check.isChecked(),
            'pdf_table_strategy': self.table_strategy_combo.currentText(),

            # Настройки HEIC
            'heic_quality': self.heic_quality_slider.value(),

            # Общие настройки
            'max_concurrent_jobs': self.max_jobs_spin.value(),
            'auto_open_folder': self.auto_open_check.isChecked(),
            'keep_original_name': self.keep_name_check.isChecked(),
            'show_notifications': self.notifications_check.isChecked(),
        })

    def _update_max_concurrent(self, value: int):
        """Обновляет максимальное количество одновременных задач"""
        self.job_manager.max_concurrent = value

    def on_input_format_changed(self, format_name: str):
        """Обработчик изменения входного формата"""
        if format_name == 'Все' or not format_name:
            self.output_format_combo.clear()
            self.output_format_combo.setEnabled(False)
            self.output_format_combo.addItem("Сначала выберите формат")
            self.convert_btn.setEnabled(False)
            return

        self.output_format_combo.setEnabled(True)
        self.output_format_combo.clear()

        formats = ConverterFactory.get_output_formats_for_input(format_name)
        if formats:
            self.output_format_combo.addItems(formats)
            if len(formats) > 0:
                self.output_format_combo.setCurrentIndex(0)
        else:
            self.output_format_combo.addItem("Нет доступных форматов")
            self.output_format_combo.setEnabled(False)

        self.check_file_formats()
        self.update_convert_button()

    def detect_file_format(self, file_path: Path) -> str:
        """Определяет формат файла по расширению"""
        ext = file_path.suffix.lower().lstrip('.')

        supported_formats = {
            'docx': 'docx', 'doc': 'doc', 'pdf': 'pdf',
            'pptx': 'pptx', 'ppt': 'ppt', 'pps': 'pps', 'ppsx': 'ppsx',
            'png': 'png', 'jpg': 'jpg', 'jpeg': 'jpg',
            'webp': 'webp', 'bmp': 'bmp', 'gif': 'gif', 'tiff': 'tiff',
            'heic': 'heic', 'heif': 'heif',
            'xlsx': 'xlsx', 'xls': 'xls', 'csv': 'csv',
            'odt': 'odt', 'rtf': 'rtf', 'txt': 'txt'
        }

        return supported_formats.get(ext, ext)

    def check_file_formats(self):
        """Проверяет соответствие форматов файлов выбранному формату"""
        input_format = self.input_format_combo.currentText()
        if input_format == 'Все' or not input_format:
            return True

        all_valid = True
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = Path(item.data(Qt.ItemDataRole.UserRole))
            ext = file_path.suffix.lower().lstrip('.')

            if ext != input_format:
                item.setForeground(RED)
                all_valid = False
            else:
                item.setData(Qt.ItemDataRole.ForegroundRole, None)

        return all_valid

    def update_convert_button(self):
        """Обновляет состояние кнопки конвертации"""
        # Если конвертация уже идет, не даем нажать
        if self.conversion_in_progress:
            self.convert_btn.setEnabled(False)
            return

        has_files = self.file_list.count() > 0
        has_format = self.input_format_combo.currentText() != 'Все' and self.input_format_combo.currentText()
        has_output = bool(self.output_format_combo.currentText())

        valid_files = True
        if has_files and has_format:
            input_format = self.input_format_combo.currentText()
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = Path(item.data(Qt.ItemDataRole.UserRole))
                ext = file_path.suffix.lower().lstrip('.')
                if ext != input_format:
                    valid_files = False
                    break

        enabled = has_files and has_format and has_output and valid_files
        self.convert_btn.setEnabled(enabled)

    def add_files(self):
        """Добавляет файлы через диалог"""
        # Фильтр по реальным расширениям: Finder фильтрует сам. С «*.*» Qt проверяет
        # каждый файл папки колбэком в наше приложение — отсюда лаги в окне выбора.
        patterns = " ".join(f"*.{ext}" for ext in ConverterFactory.get_input_formats())
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для конвертации",
            self.settings.get('last_input_dir') or str(Path.home()),
            f"Поддерживаемые файлы ({patterns})"
        )
        if files:
            self.settings.set('last_input_dir', str(Path(files[0]).parent))
            self.add_paths(Path(f) for f in files)

    def add_folder(self):
        """Добавляет папку с файлами"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с файлами",
            self.settings.get('last_input_dir') or str(Path.home())
        )

        if folder:
            self.settings.set('last_input_dir', folder)
            self.add_paths(self._files_in(Path(folder)))

    def add_paths(self, paths):
        """Добавляет много файлов, пересчитывая состояние списка один раз."""
        self.file_list.setUpdatesEnabled(False)
        try:
            for path in paths:
                self.add_file_to_list(path, refresh=False)
        finally:
            self.file_list.setUpdatesEnabled(True)
        self.check_file_formats()
        self.update_convert_button()
        self.update_file_count()

    def add_file_to_list(self, file_path: Path, refresh: bool = True):
        """Добавляет файл в список"""
        ext = file_path.suffix.lower().lstrip('.')
        if ext not in ConverterFactory.get_input_formats():
            size_str = get_file_size_str(file_path)
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            item.setData(META_ROLE, f"{size_str}  ·  формат {ext} не поддерживается")
            item.setForeground(RED)
            self.file_list.addItem(item)
            return

        size_str = get_file_size_str(file_path)
        item = QListWidgetItem(file_path.name)
        item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        item.setData(META_ROLE, f"{size_str}  ·  {file_path.parent.name or file_path.parent}")
        self.file_list.addItem(item)

        current_format = self.input_format_combo.currentText()
        if current_format == 'Все' or not current_format:
            detected_format = self.detect_file_format(file_path)
            if detected_format in ConverterFactory.get_input_formats():
                index = self.input_format_combo.findText(detected_format)
                if index >= 0:
                    self.input_format_combo.setCurrentIndex(index)

        if refresh:
            self.check_file_formats()
            self.update_convert_button()
            self.update_file_count()

    def clear_files(self):
        """Очищает список файлов"""
        self.file_list.clear()
        self.update_convert_button()
        self.update_file_count()
        self.status_label.setText("Готов к работе")

    def update_file_count(self):
        """Обновляет счетчик файлов"""
        count = self.file_list.count()
        if count == 0:
            self.status_label.setText("Готов к работе")
        else:
            valid_count = 0
            input_format = self.input_format_combo.currentText()
            for i in range(count):
                item = self.file_list.item(i)
                file_path = Path(item.data(Qt.ItemDataRole.UserRole))
                ext = file_path.suffix.lower().lstrip('.')
                if ext == input_format or input_format == 'Все':
                    valid_count += 1
            text = f"{files_word(count)} в очереди"
            if valid_count < count:
                text += f", подходят по формату: {valid_count}"
            self.status_label.setText(text)

    def show_file_context_menu(self, position):
        """Показывает контекстное меню для файлов"""
        if self.file_list.itemAt(position) is None and self.file_list.count() == 0:
            return
        menu = GlassPopup(["Удалить из списка", "Удалить все", "Удалить файлы другого формата"], -1, self)
        menu.triggered.connect(self._on_file_menu)
        menu.popup_at(self.file_list.viewport().mapToGlobal(position))

    def _on_file_menu(self, action: int):
        remove_action, remove_all_action, clear_invalid_action = 0, 1, 2

        if action == remove_action:
            for item in self.file_list.selectedItems():
                self.file_list.takeItem(self.file_list.row(item))
            self.update_convert_button()
            self.update_file_count()

        elif action == remove_all_action:
            self.file_list.clear()
            self.update_convert_button()
            self.update_file_count()

        elif action == clear_invalid_action:
            input_format = self.input_format_combo.currentText()
            if input_format != 'Все':
                for i in range(self.file_list.count() - 1, -1, -1):
                    item = self.file_list.item(i)
                    file_path = Path(item.data(Qt.ItemDataRole.UserRole))
                    ext = file_path.suffix.lower().lstrip('.')
                    if ext != input_format:
                        self.file_list.takeItem(i)
                self.update_convert_button()
                self.update_file_count()

    def start_conversion(self):
        """Запускает конвертацию"""
        if self.file_list.count() == 0:
            self.show_warning_signal.emit("Ошибка", "Нет файлов для конвертации")
            return

        input_format = self.input_format_combo.currentText()
        output_format = self.output_format_combo.currentText()

        if input_format == 'Все':
            self.show_warning_signal.emit(
                "Ошибка",
                "Пожалуйста, выберите конкретный входной формат"
            )
            return

        if not output_format:
            self.show_warning_signal.emit("Ошибка", "Выберите выходной формат")
            return

        # can_convert — проверка по таблице; get_converter импортировал бы PyMuPDF и т.п. прямо в GUI-потоке
        if not ConverterFactory.can_convert(input_format, output_format):
            self.show_warning_signal.emit(
                "Ошибка",
                f"Конвертация из {input_format} в {output_format} не поддерживается"
            )
            return

        self.settings.add_recent_format(input_format, output_format)

        output_dir = self.settings.get('output_directory')
        if not output_dir:
            output_dir = str(Path.home() / 'Downloads')

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения",
            output_dir
        )

        if not output_dir:
            return

        self.settings.set('output_directory', output_dir)

        for i in range(self.file_list.count()):
            self.file_list.item(i).setData(PROGRESS_ROLE, None)

        added_count = 0
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            input_path = Path(item.data(Qt.ItemDataRole.UserRole))

            ext = input_path.suffix.lower().lstrip('.')
            if ext != input_format:
                continue

            if self.settings.get('keep_original_name', True):
                output_name = f"{input_path.stem}.{output_format}"
            else:
                output_name = f"converted_{added_count+1}.{output_format}"

            output_path = Path(output_dir) / output_name
            output_path = get_unique_filename(output_path)

            ensure_output_directory(output_path)

            # Передаем настройки в конвертер
            kwargs = {}

            # Настройки для изображений
            if output_format in ['jpg', 'jpeg', 'webp']:
                kwargs['quality'] = self.settings.get('image_quality', 85)

            # Настройки для PDF
            if input_format == 'pdf':
                if output_format in ['png', 'jpg', 'jpeg', 'webp']:
                    kwargs['dpi'] = self.settings.get('pdf_dpi', 200)
                    kwargs['quality'] = self.settings.get('pdf_quality', 85)
                elif output_format in ['xlsx', 'xls', 'csv']:
                    kwargs['table_strategy'] = self.settings.get('pdf_table_strategy', 'auto')
                elif output_format == 'pdf':
                    kwargs['compression_level'] = self.settings.get('pdf_compress_level', 6)
                    kwargs['remove_metadata'] = self.settings.get('pdf_remove_metadata', False)
                    kwargs['optimize_images'] = self.settings.get('pdf_optimize_images', True)
                elif output_format in ['pptx', 'ppt']:
                    kwargs['dpi'] = self.settings.get('pdf_dpi', 150)
                    kwargs['quality'] = self.settings.get('pdf_quality', 85)

            # Настройки для HEIC
            if input_format in ['heic', 'heif']:
                kwargs['quality'] = self.settings.get('heic_quality', 85)

            self.file_list.item(i).setData(PROGRESS_ROLE, 0)
            self.job_manager.add_job(
                input_path,
                output_path,
                input_format,
                output_format,
                **kwargs
            )
            added_count += 1

        if added_count == 0:
            self.show_warning_signal.emit(
                "Ошибка",
                f"Нет файлов формата {input_format} для конвертации"
            )
            return

        # Блокируем кнопку и запускаем таймер
        self.conversion_in_progress = True
        self.convert_btn.setEnabled(False)
        self.total_progress.setValue(0)
        self.total_progress.show()
        self.status_label.setText(f"Конвертация: {files_word(added_count)}")

        # Запускаем таймер если еще не запущен
        if not self.status_timer.isActive():
            self.status_timer.start()

    def update_status(self):
        """Обновляет статус"""
        active = self.job_manager.get_active_jobs_count()
        jobs = self.job_manager.get_all_jobs()

        if not jobs:
            return

        total = len(jobs)
        completed = sum(1 for job in jobs if job.get_status() == JobStatus.COMPLETED)
        failed = sum(1 for job in jobs if job.get_status() == JobStatus.FAILED)

        # Считаем средний прогресс
        if total > 0:
            total_progress = sum(job.get_progress() for job in jobs) // total
            self.total_progress.setValue(total_progress)

        self.status_label.setText(f"Готово {completed} из {total}" + (f" · в работе: {active}" if active else ""))

        # Проверяем завершение всех задач
        active_jobs = [j for j in jobs if j.get_status() in [JobStatus.PENDING, JobStatus.PROCESSING]]

        if not active_jobs and total > 0:
            self.status_timer.stop()
            self.conversion_in_progress = False
            self.update_convert_button()
            self.status_label.setText(f"Готово: {files_word(completed)}" + (f", ошибок: {failed}" if failed else ""))
            self.total_progress.setValue(100)
            QTimer.singleShot(1500, lambda: self.conversion_in_progress or self.total_progress.hide())

            if self.settings.get('show_notifications', True):
                if failed:
                    self.toast.show_message(f"Готово: {files_word(completed)}, ошибок: {failed}", "error", 5000)
                else:
                    self.toast.show_message(f"Готово: {files_word(completed)}", "success")

            if self.settings.get('auto_open_folder', True) and completed > 0:
                output_dir = self.settings.get('output_directory')
                if output_dir:
                    try:
                        if sys.platform == 'win32':
                            os.startfile(output_dir)
                        elif sys.platform == 'darwin':
                            subprocess.Popen(['open', output_dir])
                        else:
                            subprocess.Popen(['xdg-open', output_dir])
                    except Exception as e:
                        logger.error(f"Не удалось открыть папку: {e}")

    @Slot(str)
    def _append_log(self, line: str):
        self.log_text.append(line)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    # on_job_* вызываются из рабочих потоков JobManager — виджеты трогаем только через сигналы
    def on_job_started(self, job: ConversionJob):
        """Обработчик начала задачи"""
        self.log_signal.emit(f"Начато   {job.input_path.name}")

    def on_job_progress(self, job: ConversionJob):
        """Обработчик прогресса задачи"""
        # Используем сигнал для безопасного обновления UI
        self.update_file_item_signal.emit(str(job.input_path), job.get_progress())
        self.update_status_signal.emit()

    def on_job_completed(self, job: ConversionJob):
        """Обработчик завершения задачи"""
        self.log_signal.emit(f"Готово   {job.input_path.name} → {job.output_path.name}")

        self.update_file_item_signal.emit(str(job.input_path), 100)
        self.update_status_signal.emit()

    def on_job_failed(self, job: ConversionJob):
        """Обработчик ошибки задачи"""
        self.log_signal.emit(f"Ошибка   {job.input_path.name}: {job.error_message}")

        self.update_file_item_signal.emit(str(job.input_path), -1)
        self.update_status_signal.emit()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработчик перетаскивания файлов"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.file_group.setHighlighted(True)

    def dropEvent(self, event: QDropEvent):
        """Обработчик сброса файлов"""
        self.file_group.setHighlighted(False)
        paths = []
        for url in event.mimeData().urls():
            file_path = Path(url.toLocalFile())
            if file_path.is_file():
                paths.append(file_path)
            elif file_path.is_dir():
                paths.extend(self._files_in(file_path))
        self.add_paths(paths)

    def dragLeaveEvent(self, event):
        self.file_group.setHighlighted(False)

    @staticmethod
    def _files_in(folder: Path) -> list:
        formats = set(ConverterFactory.get_input_formats())
        return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower().lstrip('.') in formats)

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        try:
            self.status_timer.stop()
        except RuntimeError:
            pass
        self.job_manager.stop()
        # Останавливаем фоновую проверку LibreOffice
        try:
            self.libreoffice_manager.stop_periodic_check()
        except RuntimeError:
            pass
        # Плавно останавливаем worker
        self.worker.quit()
        if self.worker.wait(3000):
            event.accept()
        else:
            # Не блокируем закрытие, если worker завис
            self.worker.terminate()
            self.worker.wait(500)
            event.accept()