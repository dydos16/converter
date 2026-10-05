# File Converter Pro

Конвертер документов, PDF и изображений для Windows, macOS и Linux.

## Возможности

- **Документы Office → PDF:** Word (docx, doc), PowerPoint (pptx, ppt, pps, ppsx), Excel и таблицы (xlsx, xls, csv), odt, rtf, txt.
- **PDF → во что угодно:** Word, Excel, PowerPoint, изображения (png, jpg, webp, tiff…), текст, HTML, Markdown, JSON, XML; сжатие PDF.
- **Изображения:** png, jpg, webp, bmp, gif, tiff, HEIC с iPhone.
- Пакетная конвертация, перетаскивание файлов в окно, отмена на ходу.
- Светлая и тёмная темы (или как в системе), настройки сохраняются сами.
- Горячие клавиши: ⌘1–⌘3 (Ctrl на Windows и Linux) — вкладки, ⌘O — добавить файлы.

## Установка

Готовые сборки — на странице [Releases](../../releases).

### Windows

Скачайте `FileConverterPro_Windows_Setup.exe` и запустите. Программа ставится только для вашей учётной записи, права администратора не нужны. Удалить — через «Параметры → Приложения».

Установщик не подписан, поэтому Windows может показать «Windows защитил ваш компьютер». Нажмите **«Подробнее» → «Выполнить в любом случае»**.

Без установки: `FileConverterPro_Windows.zip` — распакуйте и запустите `FileConverterPro.exe`.

### macOS

Скачайте `FileConverterPro_macOS.zip`, распакуйте и перетащите `FileConverterPro.app` в «Программы». Сборка универсальная: работает и на Apple Silicon, и на Intel.

Приложение не нотаризовано Apple, поэтому при первом запуске macOS может написать, что приложение «повреждено» или что «не удаётся проверить разработчика». Варианты:

- macOS 15 и новее: попробуйте открыть, затем «Системные настройки → Конфиденциальность и безопасность» → **«Всё равно открыть»**;
- macOS 14 и старше: щелчок правой кнопкой по приложению → **«Открыть»** → «Открыть»;
- или одной командой в Терминале:

```bash
xattr -dr com.apple.quarantine /Applications/FileConverterPro.app
```

### Linux

Скачайте `FileConverterPro_Linux.AppImage` (x86-64), разрешите запуск и откройте:

```bash
chmod +x FileConverterPro_Linux.AppImage
./FileConverterPro_Linux.AppImage
```

Если AppImage пишет про FUSE, установите `libfuse2` (на Ubuntu 24.04 и новее пакет называется `libfuse2t64`) или запустите так:

```bash
./FileConverterPro_Linux.AppImage --appimage-extract-and-run
```

Без AppImage: `FileConverterPro_Linux.zip` — распакуйте и запустите `FileConverterPro`. На Linux ARM (aarch64) готовой сборки нет — запускайте из исходников (см. ниже).

## LibreOffice: докачивается автоматически

Для документов Office (Word, Excel, PowerPoint, odt, rtf) нужен LibreOffice. Всё остальное — PDF, изображения, HEIC — работает и без него.

- Если LibreOffice уже установлен в системе, приложение использует его.
- Если нет, при первом запуске приложение **само скачивает его в фоне**: около 500 МБ на macOS, 340 МБ на Windows, 200 МБ на Linux. Прогресс виден во вкладке «Настройки → LibreOffice».
- Скачанный архив проверяется по **sha256**: повреждённый или подменённый архив не распаковывается.
- Ставится только в папку приложения, без прав администратора и без изменений в системе:

| ОС | Где лежит LibreOffice |
|---|---|
| macOS | `~/Library/Application Support/FileConverterPro/libreoffice` |
| Windows | `%LOCALAPPDATA%\FileConverterPro\libreoffice` |
| Linux | `~/.local/share/FileConverterPro/libreoffice` |

Чтобы освободить место, эту папку можно удалить — при следующем запуске LibreOffice скачается заново.

### Linux-серверы и минимальные системы

На обычном рабочем столе Linux всё нужное уже есть. На сервере или в минимальном контейнере LibreOffice может не запуститься из-за нехватки системных библиотек — приложение покажет это в «Журнале» вместе с командой установки:

```bash
sudo apt install libxinerama1 libnss3 libdbus-1-3 libcairo2 libx11-6 libx11-xcb1 libxext6 libcups2 libfontconfig1 libfreetype6 libgssapi-krb5-2 libxrender1 libsm6 libice6 libxrandr2
```

## Где хранятся настройки и журнал

| ОС | Папка |
|---|---|
| macOS | `~/Library/Application Support/FileConverterPro` |
| Windows | `%APPDATA%\FileConverterPro` |
| Linux | `~/.config/file-converter` |

Журнал работы — в подпапке `logs/app.log`.

## Запуск из исходников

Нужен Python 3.12.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

На Windows вместо `.venv/bin/` — `.venv\Scripts\`.

## Сборка

```bash
.venv/bin/pip install pyinstaller
.venv/bin/python build.py
```

Результат — в `dist/`. Установщик для Windows собирается [Inno Setup 6](https://jrsoftware.org/isinfo.php) после `build.py`:

```bash
iscc /DAppVersion=1.1.0 packaging\windows\installer.iss
```

Иконка лежит в `packaging/` и перегенерируется командой `python packaging/make_icon.py`.

Сборки для всех ОС делает GitHub Actions (`.github/workflows/build.yml`): после сборки запускает собранное приложение с самопроверкой (`--self-test`), на Windows ставит, проверяет и удаляет установщик, на Linux проверяет AppImage. При теге `v*` всё публикуется в Releases. macOS собирается только для релизов и при ручном запуске.

## Тесты

```bash
.venv/bin/python tests/test_smoke.py          # быстрые проверки
.venv/bin/python tests/integration_check.py   # окно, конвертации, LibreOffice, DOCX → PDF
.venv/bin/python tests/ui_check.py            # настоящая мышь на экране (двигает курсор!)
```

`Platform check` (`.github/workflows/platform-check.yml`) гоняет их на настоящих Windows и Linux, включая установку LibreOffice от обычного пользователя без прав администратора.

## Сторонние компоненты

| Компонент | Лицензия |
|---|---|
| Qt / PySide6 | LGPL-3.0 |
| PyMuPDF | AGPL-3.0 (или коммерческая лицензия Artifex) |
| LibreOffice (скачивается отдельно) | MPL-2.0 |
| Pillow, pillow-heif, pdfplumber, pypdf, python-docx, python-pptx, openpyxl, reportlab, lxml, loguru | свободные (MIT, BSD, HPND и т. п.) |

PyMuPDF распространяется под AGPL-3.0: при распространении приложения его исходный код должен быть доступен под совместимой лицензией, либо нужна коммерческая лицензия PyMuPDF.
