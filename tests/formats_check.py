"""
Проверка всех поддерживаемых конвертаций (src/config/formats.py) на реалистичных файлах: русский текст,
несколько страниц, заголовок, жирный и курсив, таблица, картинка. Каждая пара конвертируется, результат
проверяется по содержимому — внутри действительно нужный формат (а не, скажем, DOCX с расширением .odt),
и текст доехал. Потом — трудные случаи из жизни: поворот фото из EXIF, прозрачность, CMYK, CSV и TXT
из русского Windows, скан без текста, большой PDF, оформление при PDF → DOCX.

    python tests/formats_check.py

Нужен LibreOffice — тот же, что у приложения (его ставит integration_check.py).
Код возврата 0 — всё прошло, 1 — что-то сломано.
"""
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from loguru import logger  # noqa: E402

logger.remove()                                   # логи конвертеров не мешают отчёту

TEXT = "Привет, конвертер! Съешь же ещё этих мягких французских булок — 2026"
TABLE = [["Товар", "Кол-во", "Цена"], ["яблоко", "10", "99,50"], ["груша", "20", "120"]]
FILLER = ("В этом разделе рассказывается о продажах за квартал: объёмы выросли, а склад опустел. " * 6).strip()
IMAGE_FORMATS = ("jpeg", "png", "webp", "bmp", "gif", "tiff")

# Что должно оказаться внутри файла с таким расширением
EXPECTED = {
    "jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "bmp": "bmp", "gif": "gif", "tiff": "tiff",
    "pdf": "pdf", "docx": "docx", "xlsx": "xlsx", "pptx": "pptx", "odt": "odt", "odp": "odp", "rtf": "rtf",
    "doc": "ole", "xls": "ole", "ppt": "ole",     # старые форматы Office — контейнер OLE2
    "txt": "text", "md": "text", "csv": "text", "html": "html", "json": "json", "xml": "xml",
}
ODF = {"application/vnd.oasis.opendocument.text": "odt",
       "application/vnd.oasis.opendocument.presentation": "odp",
       "application/vnd.oasis.opendocument.spreadsheet": "ods"}


def sniff(p: Path) -> str:
    """Формат по содержимому, а не по расширению."""
    data = p.read_bytes()
    head = data[:16]
    for magic, kind in ((b"%PDF", "pdf"), (b"\xff\xd8\xff", "jpeg"), (b"\x89PNG", "png"), (b"BM", "bmp"),
                        (b"GIF8", "gif"), (b"II*\x00", "tiff"), (b"MM\x00*", "tiff"), (b"{\\rtf", "rtf"),
                        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole")):
        if head.startswith(magic):
            return kind
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"PK"):
        with zipfile.ZipFile(p) as z:
            names = set(z.namelist())
            if "mimetype" in names:
                return ODF.get(z.read("mimetype").decode().strip(), "zip")
            for marker, kind in (("word/document.xml", "docx"), ("xl/workbook.xml", "xlsx"),
                                 ("ppt/presentation.xml", "pptx")):
                if marker in names:
                    return kind
        return "zip"
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "binary"
    if "<html" in text[:2000].lower():
        return "html"
    try:
        json.loads(text)
        return "json"
    except ValueError:
        pass
    try:
        ET.fromstring(text)
        return "xml"
    except ET.ParseError:
        return "text"


def text_of(p: Path, kind: str) -> str | None:
    """Текст из результата — где его можно достать без LibreOffice; None — не проверяем."""
    if kind == "pdf":                              # pdfplumber, а не PyMuPDF приложения: тест не должен повторять его ошибки
        import pdfplumber
        with pdfplumber.open(p) as d:
            return "\n".join(page.extract_text() or "" for page in d.pages)
    if kind == "docx":
        from docx import Document
        d = Document(p)
        cells = [c.text for t in d.tables for r in t.rows for c in r.cells]
        return "\n".join([par.text for par in d.paragraphs] + cells)
    if kind == "xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(p, read_only=True)
        return " ".join(str(v) for ws in wb for row in ws.iter_rows(values_only=True) for v in row if v is not None)
    if kind == "pptx":
        from pptx import Presentation
        return " ".join(s.text_frame.text for sl in Presentation(p).slides for s in sl.shapes if s.has_text_frame)
    if kind == "rtf":                              # кириллица в RTF — экранированные \uNNNN; управляющие слова убираем
        raw = p.read_text(encoding="latin-1")
        raw = re.sub(r"\\u(-?\d+)(?:\\'[0-9a-fA-F]{2}|\?)?", lambda m: chr(int(m.group(1)) % 65536), raw)
        raw = re.sub(r"\\'[0-9a-fA-F]{2}|\\[a-zA-Z]+-?\d* ?", "", raw)
        return raw.replace("{", "").replace("}", "")
    if kind in ("text", "html", "json", "xml"):
        return p.read_text(encoding="utf-8-sig", errors="replace")
    return None


def lo_convert(soffice: Path, profile: Path, src: Path, ext: str, outdir: Path) -> Path | None:
    subprocess.run([str(soffice), "--headless", "--norestore", f"-env:UserInstallation={profile.as_uri()}",
                    "--convert-to", ext, "--outdir", str(outdir), str(src)], capture_output=True, timeout=300)
    made = outdir / f"{src.stem}.{ext}"
    return made if made.exists() else None


# --------------------------------------------------------------------------- #
#  Входные файлы
# --------------------------------------------------------------------------- #

def photo(w: int, h: int):
    """Картинка «как фото»: плавные переходы и фигуры (шум сделал бы PNG огромным и медленным)."""
    from PIL import Image, ImageDraw
    ramp = Image.linear_gradient("L").resize((w, h))
    img = Image.merge("RGB", (ramp, ramp.transpose(Image.Transpose.ROTATE_90).resize((w, h)), Image.new("L", (w, h), 160)))
    d = ImageDraw.Draw(img)
    d.ellipse([w // 5, h // 5, w // 2, h // 2], fill=(250, 200, 40))
    d.rectangle([w // 2, h // 2, w - w // 6, h - h // 6], fill=(30, 120, 220))
    return img


def rich_docx(path: Path, pages: int, picture: Path):
    from docx import Document
    from docx.shared import Inches
    doc = Document()
    doc.add_heading("Отчёт о продажах", 0)
    p = doc.add_paragraph(TEXT + " ")
    p.add_run("жирный").bold = True
    p.add_run(" и ")
    p.add_run("курсив").italic = True
    table = doc.add_table(rows=len(TABLE), cols=len(TABLE[0]))
    table.style = "Table Grid"
    for r, row in enumerate(TABLE):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    doc.add_picture(str(picture), width=Inches(3))
    for n in range(2, pages + 1):
        doc.add_page_break()
        doc.add_heading(f"Раздел {n}", 1)
        doc.add_paragraph(FILLER)
    doc.save(path)


def make_inputs(d: Path, soffice: Path, profile: Path) -> dict[str, Path]:
    import csv
    import pillow_heif
    from openpyxl import Workbook
    from pptx import Presentation

    d.mkdir(parents=True)
    lo = d / "lo"
    img = photo(2400, 1600)
    files = {}
    for ext, fmt in (("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG"), ("webp", "WEBP"), ("bmp", "BMP"),
                     ("gif", "GIF"), ("tiff", "TIFF")):
        files[ext] = d / f"sample.{ext}"
        img.save(files[ext], fmt)
    pillow_heif.register_heif_opener()
    for ext in ("heic", "heif"):
        files[ext] = d / f"sample.{ext}"
        img.save(files[ext], "HEIF")

    files["docx"] = d / "sample.docx"
    rich_docx(files["docx"], 3, files["png"])

    prs = Presentation()
    for title, body in ((TEXT, "яблоко и груша"), ("Итоги", "Продажи выросли на 12 %")):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = body
    files["pptx"] = d / "sample.pptx"
    prs.save(files["pptx"])

    wb = Workbook()
    wb.active.title = "Продажи"
    wb.active.append(TABLE[0])
    for name, qty, price in TABLE[1:]:
        wb.active.append([name, int(qty), float(price.replace(",", "."))])
    files["xlsx"] = d / "sample.xlsx"
    wb.save(files["xlsx"])

    files["csv"] = d / "sample.csv"
    with open(files["csv"], "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(TABLE)
    files["txt"] = d / "sample.txt"
    files["txt"].write_text(f"{TEXT}\n{FILLER}\n", encoding="utf-8")

    # PDF — из документа Word через LibreOffice, как у людей; старые и ODF-форматы — тоже им
    for ext, src in (("pdf", "docx"), ("doc", "docx"), ("odt", "docx"), ("rtf", "docx"), ("ppt", "pptx"),
                     ("pps", "pptx"), ("ppsx", "pptx"), ("xls", "xlsx")):
        made = lo_convert(soffice, profile, files[src], ext, lo)
        if made:
            files[ext] = made
    return files


# --------------------------------------------------------------------------- #
#  Проверки
# --------------------------------------------------------------------------- #

def run(src: Path, out: Path, **kwargs) -> tuple[bool, list[str]]:
    from src.converters.factory import ConverterFactory
    errors: list[str] = []
    converter = ConverterFactory.get_converter(src.suffix, out.suffix, **kwargs)
    converter.error_callback = errors.append
    out.parent.mkdir(parents=True, exist_ok=True)
    return bool(converter.convert(src, out)), errors


def why(errors: list[str]) -> str:
    return f"ошибка: {errors[-1][:200]}" if errors else "конвертер вернул ошибку"


def check_pair(src: str, dst: str, files: dict[str, Path], out: Path, pages: int) -> str | None:
    """None — всё хорошо, иначе — что не так."""
    ok, errors = run(files[src], out)
    if not ok:
        return why(errors)
    want = EXPECTED[dst]
    if not out.exists() and src == "pdf" and want in IMAGE_FORMATS and pages > 1:
        # Многостраничный PDF → картинки: архив со всеми страницами
        archive = out.with_suffix(".zip")
        if not archive.exists():
            return "нет архива со страницами"
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            if len(names) != pages:
                return f"в архиве {len(names)} страниц из {pages}"
            out = out.parent / names[0]
            out.write_bytes(z.read(names[0]))
    if not out.exists():
        others = [p.name for p in out.parent.iterdir()]
        return "нет файла результата" + (f" (есть: {', '.join(others)})" if others else "")
    kind = sniff(out)
    if kind != want:
        return f"внутри {kind.upper()}, а не {want.upper()}"
    # Текст должен доехать везде, кроме картинок (в PDF → PPTX он теперь настоящий, редактируемый)
    if src in ("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "heic", "heif") or want in IMAGE_FORMATS:
        return None
    # Фраза целиком, со знаками: так ловится и испорченная кириллица, и разъехавшиеся запятые
    markers = ("яблоко", "Кол-во") if {src, dst} & {"xlsx", "xls", "csv"} else ("Привет, конвертер!",)
    text = text_of(out, kind)
    if text is not None:
        flat = re.sub(r"\s+", " ", text)
        missing = [m for m in markers if m not in flat]
        if missing:
            i = flat.find(missing[0][:4])
            return f"в результате нет «{missing[0]}»" + (f": …{flat[max(0, i - 30):i + 50]}…" if i >= 0 else "")
    return None


def edge_cases(files: dict[str, Path], d: Path, soffice: Path, profile: Path) -> list:
    """Трудные случаи из жизни: (название, функция → None или описание проблемы)."""
    from PIL import Image
    d.mkdir(parents=True)

    def exif_rotation():
        src = d / "rotated.jpg"
        exif = Image.Exif()
        exif[0x0112] = 6                                # «повернуть на 90°» — так снимает телефон
        photo(300, 200).save(src, "JPEG", exif=exif)
        ok, err = run(src, d / "rotated.png")
        size = Image.open(d / "rotated.png").size if ok else None
        return None if size == (200, 300) else (why(err) if not ok else f"размер {size} — фото лежит на боку")

    def transparent_to_jpg(palette: bool):
        def check():
            src = d / f"transparent_{palette}.png"
            im = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
            im.paste((220, 30, 30, 255), (100, 0, 200, 100))
            if palette:
                im = im.convert("P", palette=Image.Palette.ADAPTIVE, colors=8)
                im.info["transparency"] = im.getpixel((10, 10))
                im.save(src, transparency=im.info["transparency"])
            else:
                im.save(src)
            out = d / f"transparent_{palette}.jpg"
            ok, err = run(src, out)
            if not ok:
                return why(err)
            pixel = Image.open(out).convert("RGB").getpixel((20, 50))
            return None if min(pixel) > 230 else f"прозрачный фон стал {pixel}, а не белым"
        return check

    def cmyk(dst: str):
        def check():
            src = d / "cmyk.jpg"
            photo(300, 200).convert("CMYK").save(src, "JPEG")
            ok, err = run(src, d / f"cmyk.{dst}")
            return None if ok and sniff(d / f"cmyk.{dst}") == EXPECTED[dst] else why(err)
        return check

    def png16():
        src = d / "deep.png"
        Image.linear_gradient("L").resize((300, 200)).convert("I;16").save(src)
        ok, err = run(src, d / "deep.jpg")
        return None if ok else why(err)

    def windows_csv(dst: str):
        def check():
            src = d / f"excel_ru_{dst}.csv"             # «CSV (разделители — точка с запятой)» из русского Excel
            src.write_bytes("\r\n".join(";".join(r) for r in TABLE).encode("cp1251") + b"\r\n")
            out = d / f"excel_ru.{dst}"
            ok, err = run(src, out)
            if not ok:
                return why(err)
            if dst == "xlsx":
                from openpyxl import load_workbook
                ws = load_workbook(out).active
                return None if ws["A2"].value == "яблоко" and ws["B2"].value in (10, "10") else \
                    f"ячейки A2={ws['A2'].value!r} B2={ws['B2'].value!r} — кодировка или разделитель не распознаны"
            return None if "яблоко" in (text_of(out, sniff(out)) or "") else "в PDF нет «яблоко»"
        return check

    def windows_txt(dst: str):
        def check():
            src = d / f"notepad_{dst}.txt"
            src.write_bytes(f"{TEXT}\r\n".encode("cp1251"))
            out = d / f"notepad.{dst}"
            ok, err = run(src, out)
            if not ok:
                return why(err)
            return None if "Привет" in (text_of(out, sniff(out)) or "") else "кириллица испорчена"
        return check

    def csv_for_excel():
        out = d / "for_excel.csv"
        ok, err = run(files["xlsx"], out)
        if not ok:
            return why(err)
        return None if out.read_bytes().startswith(b"\xef\xbb\xbf") else "CSV без BOM — русский Excel покажет кракозябры"

    def scan_pdf() -> Path:
        """Скан как со сканера: страница картинкой 200 DPI, текстового слоя нет."""
        import fitz
        src = d / "scan.pdf"
        if not src.exists():
            with fitz.open(files["pdf"]) as pdf:
                png = pdf[0].get_pixmap(dpi=200).tobytes("png")
            Image.open(io.BytesIO(png)).convert("RGB").save(src, "PDF", resolution=200)
        return src

    def scan_to_text():
        out = d / "scan.txt"
        ok, err = run(scan_pdf(), out)
        if not ok:
            return why(err)
        flat = re.sub(r"\s+", " ", out.read_text(encoding="utf-8-sig"))
        missing = [m for m in ("Привет, конвертер!", "яблоко", "Кол-во") if m not in flat]
        return None if not missing else f"не распознано: {', '.join(missing)} (вышло: {flat[:120]}…)"

    def scan_to_docx():
        out = d / "scan.docx"
        ok, err = run(scan_pdf(), out)
        if not ok:
            return why(err)
        from docx import Document
        flat = re.sub(r"\s+", " ", " ".join(p.text for p in Document(out).paragraphs))
        return None if "Привет, конвертер!" in flat else f"текст не распознан: {flat[:120]}…"

    def pdf_to_pptx_editable():
        out = d / "slides.pptx"
        ok, err = run(files["pdf"], out)
        if not ok:
            return why(err)
        from pptx import Presentation
        slide = Presentation(out).slides[0]
        texts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
        pictures = [s for s in slide.shapes if s.shape_type == 13]          # 13 — картинка (фон страницы)
        missing = [what for what, present in (
            ("заголовок надписью", "Отчёт о продажах" in texts),
            ("абзац надписью", any(TEXT in re.sub(r"\s+", " ", t) for t in texts)),
            ("ячейки таблицы на своих местах", "Кол-во" in texts and "яблоко" in texts),
            ("фон страницы", len(pictures) == 1),
        ) if not present]
        return None if not missing else "нет: " + ", ".join(missing)

    def pdf_to_docx_keeps_formatting():
        out = d / "formatted.docx"
        ok, err = run(files["pdf"], out)
        if not ok:
            return why(err)
        from docx import Document
        doc = Document(out)
        runs = [r for p in doc.paragraphs for r in p.runs]
        missing = [what for what, present in (
            ("таблица", any("яблоко" in c.text for t in doc.tables for row in t.rows for c in row.cells)),
            ("«Кол-во» в шапке таблицы", any(c.text == "Кол-во" for t in doc.tables for row in t.rows for c in row.cells)),
            ("текст абзаца по порядку", TEXT in re.sub(r"\s+", " ", " ".join(p.text for p in doc.paragraphs))),
            ("жирный", any(r.bold and "жирный" in r.text for r in runs)),
            ("курсив", any(r.italic and "курсив" in r.text for r in runs)),
            ("картинка", bool(doc.inline_shapes)),
            ("крупный заголовок", any("Отчёт" in r.text and r.font.size and r.font.size.pt >= 18 for r in runs)),
        ) if not present]
        return None if not missing else "потеряно: " + ", ".join(missing)

    def big_pdf_to_png():
        import fitz
        big_docx = d / "big.docx"
        rich_docx(big_docx, 40, files["png"])
        big = lo_convert(soffice, profile, big_docx, "pdf", d)
        with fitz.open(big) as pdf:
            pages = len(pdf)
        try:
            import resource                             # на Windows пиковую память так не померить
            scale = 1 if sys.platform == "darwin" else 1024     # ru_maxrss: байты на Mac, КБ на Linux
            peak = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
        except ImportError:
            peak = lambda: 0
        before = peak()
        ok, err = run(big, d / "big.png", dpi=200)
        grown = (peak() - before) / 1024 ** 2
        if not ok:
            return why(err)
        with zipfile.ZipFile(d / "big.zip") as z:
            n = len(z.namelist())
        if n != pages:
            return f"в архиве {n} страниц из {pages}"
        return None if grown < 300 else f"память выросла на {grown:.0f} МБ — страницы копятся в памяти"

    def page_order():
        import fitz
        ok, err = run(files["pdf"], d / "order.png", dpi=72)
        if not ok:
            return why(err)
        with zipfile.ZipFile(d / "order.zip") as z, fitz.open(files["pdf"]) as pdf:
            for n in range(1, len(pdf) + 1):
                got = Image.open(io.BytesIO(z.read(f"order_page_{n}.png"))).convert("RGB").tobytes()
                if got != pdf[n - 1].get_pixmap(dpi=72, alpha=False).samples:
                    return f"в файле страницы {n} лежит другая страница"
        return None

    def tiff_compressed():
        ok, err = run(files["pdf"], d / "page.tiff")
        if not ok:
            return why(err)
        with zipfile.ZipFile(d / "page.zip") as z:
            size = max(i.file_size for i in z.infolist())
        return None if size < 3 * 1024 ** 2 else f"TIFF {size / 1024 ** 2:.0f} МБ на страницу — без сжатия"

    return [
        ("PDF 40 страниц → PNG: все страницы, без лишней памяти", big_pdf_to_png),
        ("Фото с поворотом в EXIF → PNG", exif_rotation),
        ("PNG с прозрачностью → JPG, фон белый", transparent_to_jpg(False)),
        ("PNG с палитрой и прозрачностью → JPG, фон белый", transparent_to_jpg(True)),
        ("CMYK JPEG → PNG", cmyk("png")),
        ("CMYK JPEG → WEBP", cmyk("webp")),
        ("PNG 16 бит → JPG", png16),
        ("CSV из русского Excel (1251, «;») → XLSX", windows_csv("xlsx")),
        ("CSV из русского Excel (1251, «;») → PDF", windows_csv("pdf")),
        ("TXT из Блокнота (1251) → DOCX", windows_txt("docx")),
        ("TXT из Блокнота (1251) → PDF", windows_txt("pdf")),
        ("XLSX → CSV открывается в русском Excel (BOM)", csv_for_excel),
        ("Скан PDF → TXT: текст распознан (OCR), таблица тоже", scan_to_text),
        ("Скан PDF → DOCX: текст распознан (OCR)", scan_to_docx),
        ("PDF → PPTX: текст редактируемый, таблица по ячейкам", pdf_to_pptx_editable),
        ("PDF → DOCX сохраняет оформление", pdf_to_docx_keeps_formatting),
        ("PDF → PNG: страницы по порядку", page_order),
        ("PDF → TIFF сжат", tiff_compressed),
    ]


# --------------------------------------------------------------------------- #

def main() -> int:
    from src.config.formats import SUPPORTED_CONVERSIONS
    from src.core.libreoffice_manager import LibreOfficeManager

    soffice = LibreOfficeManager()._find_soffice()
    if not soffice:
        print("LibreOffice не найден — сначала запустите tests/integration_check.py (он его ставит)")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="fcp_formats_"))
    pairs = sorted(SUPPORTED_CONVERSIONS)
    failed, started, cases = [], time.time(), []
    try:
        profile = tmp / "lo-profile"
        files = make_inputs(tmp / "in", soffice, profile)
        import fitz
        with fitz.open(files["pdf"]) as pdf:
            pdf_pages = len(pdf)
        print(f"Пар конвертации: {len(pairs)}, страниц в тестовом PDF: {pdf_pages}; LibreOffice: {soffice}\n",
              flush=True)

        cases = edge_cases(files, tmp / "edge", soffice, profile)
        checks = [(f"{s} → {t}", lambda s=s, t=t: check_pair(s, t, files, tmp / "out" / f"{s}_to_{t}" / f"result.{t}",
                                                             pdf_pages) if s in files else f"не удалось создать входной .{s}")
                  for s, t in pairs]
        # Большой PDF — первым: пиковая память процесса ещё не раздута другими конвертациями
        for name, fn in cases[:1] + checks + cases[1:]:
            t = time.time()
            try:
                problem = fn()
            except Exception as e:                      # noqa: BLE001 — нужен отчёт по каждой проверке
                problem = f"исключение {type(e).__name__}: {e}"
            if problem:
                failed.append(name)
                print(f"[FAIL] {name} — {problem}", flush=True)
            else:
                print(f"[OK] {name} ({time.time() - t:.1f} с)", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(pairs) + len(cases)
    print(f"\nИтог: {total - len(failed)} из {total} проверок прошли за {time.time() - started:.0f} с" +
          (f"; не прошли: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
