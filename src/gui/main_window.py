"""
Главное окно приложения для PySide6
"""
import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLabel,
    QFileDialog, QTextEdit, QApplication, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QDragEnterEvent, QDropEvent, QPainter, QPalette, QPixmap, QFontDatabase,
)

from src.converters.factory import ConverterFactory
from src.core.job_manager import JobManager, ConversionJob, JobStatus
from src.core.libreoffice_manager import LibreOfficeManager
from src.core.settings import Settings
from src.gui.styles import get_stylesheet_for, get_palette_for, paint_backdrop, RED
from src.gui.glass import (
    GlassGroup, GlassButton, GlassCombo, GlassSpin, GlassSlider, Toggle, GlassProgress,
    Segmented, FadeStack, FileList, Toast, GlassPopup, PROGRESS_ROLE, META_ROLE,
)
from src.utils.helpers import get_file_size_str, get_unique_filename, ensure_output_directory
from loguru import logger


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

    @Slot(str, bool)
    def _on_libreoffice_status_changed(self, message: str, is_available: bool):
        """Обновляет индикатор статуса LibreOffice в статус-баре"""
        self.libreoffice_status_label.setText(message)
        if is_available:
            self.libreoffice_status_label.setStyleSheet("color: #34C759;")
            self.status_progress_bar.hide()
        else:
            self.libreoffice_status_label.setStyleSheet("color: #FF3B30;")

    @Slot(int, str)
    def _on_libreoffice_install_progress(self, percent: int, message: str):
        """Обновляет прогресс автоматической установки LibreOffice."""
        self.libreoffice_status_label.setText(message[:40])
        self.status_progress_bar.setValue(percent)
        self.status_progress_bar.show()

    @Slot(bool, str)
    def _on_libreoffice_install_finished(self, success: bool, message: str):
        """Обрабатывает завершение установки LibreOffice."""
        if success:
            self.status_progress_bar.hide()
            self.libreoffice_status_label.setText("LibreOffice готов")
            self.libreoffice_status_label.setStyleSheet("color: #34C759;")
        else:
            self.status_progress_bar.setValue(0)
            self.status_progress_bar.hide()
            self.libreoffice_status_label.setText("LibreOffice недоступен")
            self.libreoffice_status_label.setStyleSheet("color: #FF3B30;")

    @Slot(str)
    def _on_libreoffice_libraries_missing(self, libs: str):
        """LibreOffice скачан, но не запускается: в системе нет нужных библиотек (бывает на серверах)."""
        from src.core.libreoffice_manager import LINUX_DEPS_COMMAND
        self._append_log(f"LibreOffice не запускается: в системе нет библиотек {libs}.\n"
                         f"Установите их командой:\n{LINUX_DEPS_COMMAND}")
        self.toast.show_message("LibreOffice не хватает системных библиотек — команда установки во вкладке «Лог»",
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

    def paintEvent(self, event):
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        dpr = self.devicePixelRatioF()
        key = (self.size(), dark, dpr)
        if getattr(self, "_backdrop_key", None) != key:
            pm = QPixmap(self.size() * dpr)
            pm.setDevicePixelRatio(dpr)
            paint_backdrop(QPainter(pm), QRectF(self.rect()), dark)
            self._backdrop, self._backdrop_key = pm, key
        QPainter(self).drawPixmap(0, 0, self._backdrop)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.toast.reposition()

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_shown_once", False):
            return
        self._shown_once = True
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(260)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in.setEndValue(1.0)
        self._fade_in.start()

    def setup_ui(self):
        """Настраивает интерфейс"""
        self.setWindowTitle("File Converter Pro")
        self.resize(1080, 760)
        self.setMinimumSize(820, 600)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(28, 22, 28, 6)
        main_layout.setSpacing(4)

        title = QLabel("File Converter Pro")
        title.setProperty("title", True)
        subtitle = QLabel("Документы, PDF и изображения. Перетащите файлы прямо в окно.")
        subtitle.setProperty("subtitle", True)
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(10)

        # Вкладки: сегментированный переключатель + страницы с плавной сменой
        self.tabs = Segmented(["Конвертация", "Настройки", "Лог"])
        main_layout.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignHCenter)
        main_layout.addSpacing(8)
        self.pages = FadeStack()
        main_layout.addWidget(self.pages, 1)
        self.tabs.currentChanged.connect(self.pages.setCurrentIndex)

        for setup in (self.setup_conversion_tab, self.setup_settings_tab, self.setup_log_tab):
            page = QWidget()
            setup(page)
            self.pages.addWidget(page)

        # Единые отступы внутри всех карточек
        for group in self.findChildren(GlassGroup):
            if group.layout():
                group.layout().setContentsMargins(16, 12, 16, 14)

        self.toast = Toast(self)

        # Статус бар
        self.status_label = QLabel("Готов к работе")
        self.statusBar().addWidget(self.status_label)

        self.libreoffice_status_label = QLabel("LibreOffice: проверка...")
        self.libreoffice_status_label.setMinimumWidth(180)
        self.libreoffice_status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.statusBar().addPermanentWidget(self.libreoffice_status_label)

        # Прогресс автоматической установки LibreOffice (скрыт до начала докачки)
        self.status_progress_bar = GlassProgress()
        self.status_progress_bar.setFixedWidth(140)
        self.status_progress_bar.hide()
        self.statusBar().addPermanentWidget(self.status_progress_bar)

        self.active_jobs_label = QLabel("Активных: 0")
        self.statusBar().addPermanentWidget(self.active_jobs_label)

    def setup_conversion_tab(self, parent: QWidget):
        """Настраивает вкладку конвертации"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ---- Верхняя панель: форматы + выбор файлов ----
        top_panel = QHBoxLayout()
        top_panel.setSpacing(12)

        # Выбор форматов
        format_group = GlassGroup("Формат")
        format_layout = QHBoxLayout(format_group)
        format_layout.setContentsMargins(14, 14, 14, 14)
        format_layout.setSpacing(8)

        self.input_format_combo = GlassCombo()
        input_formats = ['Все'] + ConverterFactory.get_input_formats()
        self.input_format_combo.addItems(input_formats)
        self.input_format_combo.currentTextChanged.connect(self.on_input_format_changed)

        self.output_format_combo = GlassCombo()
        self.output_format_combo.setEnabled(False)
        self.output_format_combo.currentTextChanged.connect(self.update_convert_button)

        # Комбобоксы не должны растягиваться по вертикали — фиксируем высоту
        for combo in (self.input_format_combo, self.output_format_combo):
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.setFixedHeight(40)

        lbl_from = QLabel("Из")
        lbl_from.setProperty("big", True)
        format_layout.addWidget(lbl_from)
        format_layout.addWidget(self.input_format_combo, 1)
        lbl_to = QLabel("в")
        lbl_to.setProperty("big", True)
        format_layout.addWidget(lbl_to)
        format_layout.addWidget(self.output_format_combo, 1)

        top_panel.addWidget(format_group, 3)

        # Кнопки управления файлами (крупные пилюли)
        buttons_group = GlassGroup("Файлы")
        buttons_layout = QHBoxLayout(buttons_group)
        buttons_layout.setContentsMargins(14, 14, 14, 14)
        buttons_layout.setSpacing(8)

        # Две крупные кнопки в строку
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.add_files_btn = GlassButton("Добавить файлы")
        # Диалог открываем после того, как кнопка отрисовала отпускание
        self.add_files_btn.clicked.connect(lambda: QTimer.singleShot(0, self.add_files))
        self.add_files_btn.setFixedHeight(40)
        row1.addWidget(self.add_files_btn, 1)

        self.add_folder_btn = GlassButton("Добавить папку")
        self.add_folder_btn.clicked.connect(lambda: QTimer.singleShot(0, self.add_folder))
        self.add_folder_btn.setFixedHeight(40)
        row1.addWidget(self.add_folder_btn, 1)
        buttons_layout.addLayout(row1)
        format_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.clear_btn = GlassButton("Очистить")
        self.clear_btn.clicked.connect(self.clear_files)
        self.clear_btn.setFixedHeight(40)
        row1.addWidget(self.clear_btn)

        top_panel.addWidget(buttons_group, 2)

        layout.addLayout(top_panel)

        # ---- Список файлов ----
        file_group = GlassGroup("Очередь")
        self.file_group = file_group
        file_layout = QVBoxLayout(file_group)

        self.file_list = FileList()
        self.file_list.setAcceptDrops(True)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(220)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_context_menu)
        file_layout.addWidget(self.file_list)

        layout.addWidget(file_group, 1)

        # ---- Нижняя панель: общий прогресс + большая кнопка конвертации ----
        bottom_panel = QHBoxLayout()
        bottom_panel.setContentsMargins(6, 14, 0, 0)
        bottom_panel.setSpacing(24)

        progress_area = QVBoxLayout()
        progress_area.setSpacing(8)
        progress_area.addStretch()
        progress_label = QLabel("Прогресс")
        progress_label.setProperty("secondary", True)
        progress_area.addWidget(progress_label)
        self.total_progress = GlassProgress()
        progress_area.addWidget(self.total_progress)
        progress_area.addStretch()
        bottom_panel.addLayout(progress_area, 2)

        self.convert_btn = GlassButton("Конвертировать")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setEnabled(False)
        self.convert_btn.setFixedSize(230, 56)
        self.convert_btn.setProperty("primary", True)
        bottom_panel.addWidget(self.convert_btn)

        layout.addLayout(bottom_panel)

        # Включаем Drag & Drop
        self.setAcceptDrops(True)

    def setup_settings_tab(self, parent: QWidget):
        """Настраивает вкладку настроек"""
        # Создаем скролл область
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        # Контейнер для содержимого
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 10, 10)
        layout.setSpacing(6)

        # Внешний вид (тема)
        appear_group = GlassGroup("Внешний вид")
        appear_layout = QVBoxLayout(appear_group)

        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Тема:", self))
        self.theme_combo = GlassCombo()
        for label, val in [
            ("Системная", "system"),
            ("Светлая", "light"),
            ("Тёмная", "dark"),
        ]:
            self.theme_combo.addItem(label, val)
        current_theme = self.settings.get('theme', 'system')
        self.theme_combo.setCurrentIndex(
            {"system": 0, "light": 1, "dark": 2}.get(current_theme, 0)
        )
        self.theme_combo.currentIndexChanged.connect(
            lambda idx: self.on_theme_changed(self.theme_combo.itemData(idx))
        )
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        appear_layout.addLayout(theme_layout)

        theme_hint = QLabel("Системная тема следует за настройками ОС", self)
        theme_hint.setProperty("secondary", True)
        appear_layout.addWidget(theme_hint)

        layout.addWidget(appear_group)

        # Настройки изображений
        image_group = GlassGroup("Настройки изображений")
        image_layout = QVBoxLayout(image_group)

        # Качество
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Качество JPEG/WebP:"))
        self.quality_slider = GlassSlider()
        self.quality_slider.setRange(1, 100)
        quality_value = self.settings.get('image_quality', 85)
        if quality_value is None:
            quality_value = 85
        self.quality_slider.setValue(int(quality_value))
        self.quality_label = QLabel(f"{self.quality_slider.value()}%")
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_label.setText(f"{v}%")
        )
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_label)
        image_layout.addLayout(quality_layout)

        # Максимальный размер
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Макс. ширина:"))
        self.max_width_spin = GlassSpin()
        self.max_width_spin.setRange(0, 10000)
        self.max_width_spin.setSpecialValueText("Без ограничений")
        width_value = self.settings.get('image_max_width', 0)
        if width_value is None:
            width_value = 0
        self.max_width_spin.setValue(int(width_value))

        size_layout.addWidget(self.max_width_spin)
        size_layout.addWidget(QLabel("Макс. высота:"))
        self.max_height_spin = GlassSpin()
        self.max_height_spin.setRange(0, 10000)
        self.max_height_spin.setSpecialValueText("Без ограничений")
        height_value = self.settings.get('image_max_height', 0)
        if height_value is None:
            height_value = 0
        self.max_height_spin.setValue(int(height_value))
        size_layout.addWidget(self.max_height_spin)
        size_layout.addStretch()

        image_layout.addLayout(size_layout)
        layout.addWidget(image_group)

        # Настройки PDF
        pdf_group = GlassGroup("Настройки PDF")
        pdf_layout = QVBoxLayout(pdf_group)

        # DPI для PDF
        dpi_layout = QHBoxLayout()
        dpi_layout.addWidget(QLabel("DPI (качество PDF → изображения):"))
        self.pdf_dpi_spin = GlassSpin()
        self.pdf_dpi_spin.setRange(72, 600)
        self.pdf_dpi_spin.setValue(self.settings.get('pdf_dpi', 200))
        self.pdf_dpi_spin.setSuffix(" DPI")
        dpi_layout.addWidget(self.pdf_dpi_spin)
        dpi_layout.addStretch()
        pdf_layout.addLayout(dpi_layout)

        # Качество для PDF в изображения
        pdf_quality_layout = QHBoxLayout()
        pdf_quality_layout.addWidget(QLabel("Качество изображений:"))
        self.pdf_quality_slider = GlassSlider()
        self.pdf_quality_slider.setRange(1, 100)
        self.pdf_quality_slider.setValue(self.settings.get('pdf_quality', 85))
        self.pdf_quality_label = QLabel(f"{self.pdf_quality_slider.value()}%")
        self.pdf_quality_slider.valueChanged.connect(
            lambda v: self.pdf_quality_label.setText(f"{v}%")
        )
        pdf_quality_layout.addWidget(self.pdf_quality_slider)
        pdf_quality_layout.addWidget(self.pdf_quality_label)
        pdf_layout.addLayout(pdf_quality_layout)

        # Сжатие PDF
        compress_layout = QHBoxLayout()
        compress_layout.addWidget(QLabel("Уровень сжатия PDF:"))
        self.pdf_compress_spin = GlassSpin()
        self.pdf_compress_spin.setRange(0, 9)
        self.pdf_compress_spin.setValue(self.settings.get('pdf_compress_level', 6))
        self.pdf_compress_spin.setToolTip("0 - без сжатия, 9 - максимальное сжатие")
        compress_layout.addWidget(self.pdf_compress_spin)
        compress_layout.addStretch()
        pdf_layout.addLayout(compress_layout)

        # Чекбоксы для PDF
        self.pdf_remove_metadata_check = Toggle("Удалять метаданные")
        self.pdf_remove_metadata_check.setChecked(self.settings.get('pdf_remove_metadata', False))
        pdf_layout.addWidget(self.pdf_remove_metadata_check)

        self.pdf_optimize_images_check = Toggle("Оптимизировать изображения")
        self.pdf_optimize_images_check.setChecked(self.settings.get('pdf_optimize_images', True))
        pdf_layout.addWidget(self.pdf_optimize_images_check)

        # Стратегия извлечения таблиц
        table_strategy_layout = QHBoxLayout()
        table_strategy_layout.addWidget(QLabel("Стратегия извлечения таблиц:"))
        self.table_strategy_combo = GlassCombo()
        self.table_strategy_combo.addItems(['auto', 'lattice', 'stream'])
        self.table_strategy_combo.setCurrentText(self.settings.get('pdf_table_strategy', 'auto'))
        self.table_strategy_combo.setToolTip(
            "auto - автоматический выбор\n"
            "lattice - для таблиц с сеткой\n"
            "stream - для таблиц без сетки"
        )
        table_strategy_layout.addWidget(self.table_strategy_combo)
        table_strategy_layout.addStretch()
        pdf_layout.addLayout(table_strategy_layout)

        layout.addWidget(pdf_group)

        # Настройки HEIC
        heic_group = GlassGroup("Настройки HEIC (iPhone фото)")
        heic_layout = QVBoxLayout(heic_group)

        heic_quality_layout = QHBoxLayout()
        heic_quality_layout.addWidget(QLabel("Качество:"))
        self.heic_quality_slider = GlassSlider()
        self.heic_quality_slider.setRange(1, 100)
        self.heic_quality_slider.setValue(self.settings.get('heic_quality', 85))
        self.heic_quality_label = QLabel(f"{self.heic_quality_slider.value()}%")
        self.heic_quality_slider.valueChanged.connect(
            lambda v: self.heic_quality_label.setText(f"{v}%")
        )
        heic_quality_layout.addWidget(self.heic_quality_slider)
        heic_quality_layout.addWidget(self.heic_quality_label)
        heic_layout.addLayout(heic_quality_layout)

        layout.addWidget(heic_group)

        # Общие настройки
        general_group = GlassGroup("Общие настройки")
        general_layout = QVBoxLayout(general_group)

        self.auto_open_check = Toggle("Открывать папку после конвертации")
        auto_open = self.settings.get('auto_open_folder', True)
        self.auto_open_check.setChecked(auto_open if auto_open is not None else True)

        self.keep_name_check = Toggle("Сохранять оригинальное имя файла")
        keep_name = self.settings.get('keep_original_name', True)
        self.keep_name_check.setChecked(keep_name if keep_name is not None else True)

        self.notifications_check = Toggle("Показывать уведомления")
        show_notifications = self.settings.get('show_notifications', True)
        self.notifications_check.setChecked(show_notifications if show_notifications is not None else True)

        # Максимум одновременных задач
        max_jobs_layout = QHBoxLayout()
        max_jobs_layout.addWidget(QLabel("Максимум одновременных задач:"))
        self.max_jobs_spin = GlassSpin()
        self.max_jobs_spin.setRange(1, 10)
        self.max_jobs_spin.setValue(self.settings.get('max_concurrent_jobs', 3))

        # Обновляем менеджер при изменении
        self.max_jobs_spin.valueChanged.connect(self._update_max_concurrent)

        max_jobs_layout.addWidget(self.max_jobs_spin)
        max_jobs_layout.addStretch()
        general_layout.addLayout(max_jobs_layout)

        general_layout.addWidget(self.auto_open_check)
        general_layout.addWidget(self.keep_name_check)
        general_layout.addWidget(self.notifications_check)

        layout.addWidget(general_group)

        # Кнопка сохранения
        save_btn = GlassButton("Сохранить настройки")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setFixedHeight(52)
        save_btn.setProperty("primary", True)
        layout.addWidget(save_btn)

        layout.addStretch()

        # Устанавливаем содержимое в скролл
        scroll.setWidget(content_widget)

        # Добавляем скролл в родительский виджет
        parent_layout = QVBoxLayout(parent)
        parent_layout.setContentsMargins(0, 0, 0, 0)
        parent_layout.addWidget(scroll)

    def setup_log_tab(self, parent: QWidget):
        """Настраивает вкладку лога"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        log_group = GlassGroup("Журнал")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPixelSize(12)
        self.log_text.setFont(mono)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group, 1)

        # Кнопки управления логом
        log_buttons_layout = QHBoxLayout()

        clear_log_btn = GlassButton("Очистить лог")
        clear_log_btn.setFixedHeight(36)
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_buttons_layout.addWidget(clear_log_btn)

        log_buttons_layout.addStretch()
        layout.addLayout(log_buttons_layout)

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

        self.show_info_signal.emit("Успех", "Настройки сохранены")

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
            self.status_label.setText(f"Готов к работе ({valid_count}/{count} файл(ов) соответствуют формату)")

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
        self.status_label.setText(f"Конвертация запущена ({added_count} файлов)")

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

        self.status_label.setText(f"Активных: {active}, Завершено: {completed}/{total}")
        self.active_jobs_label.setText(f"Активных: {active}")

        # Проверяем завершение всех задач
        active_jobs = [j for j in jobs if j.get_status() in [JobStatus.PENDING, JobStatus.PROCESSING]]

        if not active_jobs and total > 0:
            self.status_timer.stop()
            self.conversion_in_progress = False
            self.update_convert_button()
            self.status_label.setText(f"Конвертация завершена! ({completed} успешно, {failed} с ошибками)")
            self.total_progress.setValue(100)
            self.active_jobs_label.setText("Активных: 0")

            if self.settings.get('show_notifications', True):
                if failed:
                    self.toast.show_message(f"Готово: {completed}, с ошибками: {failed}", "error", 5000)
                else:
                    self.toast.show_message(f"Готово: {completed} файл(ов)", "success")

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