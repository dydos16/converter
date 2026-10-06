"""
Проверка всех поддерживаемых конвертаций (src/config/formats.py): для каждого входного формата создаётся
настоящий файл, каждая пара конвертируется, а результат проверяется по содержимому — что внутри
действительно нужный формат (а не, скажем, DOCX с расширением .odt) и что текст доехал.

    python tests/formats_check.py

Нужен LibreOffice — тот же, что у приложения (его ставит integration_check.py).
Код возврата 0 — всё прошло, 1 — что-то сломано.
"""
import json
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

HELLO = "Hello Converter 2026"
TABLE = [["Name", "Qty"], ["apple", "10"], ["pear", "20"]]

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
    if kind == "pdf":
        import fitz
        with fitz.open(p) as d:
            return "".join(page.get_text() for page in d)
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
    if kind in ("text", "html", "json", "xml", "rtf"):
        return p.read_text(encoding="utf-8-sig", errors="replace")
    return None


# --------------------------------------------------------------------------- #
#  Входные файлы
# --------------------------------------------------------------------------- #

def make_inputs(d: Path, soffice: Path, profile: Path) -> dict[str, Path]:
    from PIL import Image, ImageDraw
    import pillow_heif

    d.mkdir(parents=True)
    img = Image.new("RGB", (160, 100), (30, 120, 220))
    ImageDraw.Draw(img).rectangle([20, 20, 140, 80], fill=(250, 200, 40))
    files = {}
    for ext, fmt in (("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG"), ("webp", "WEBP"), ("bmp", "BMP"),
                     ("gif", "GIF"), ("tiff", "TIFF")):
        files[ext] = d / f"sample.{ext}"
        img.save(files[ext], fmt)
    pillow_heif.register_heif_opener()
    for ext in ("heic", "heif"):
        files[ext] = d / f"sample.{ext}"
        img.save(files[ext], "HEIF")

    # PDF: абзац текста, таблица с линиями (для PDF → xlsx/csv) и картинка (для сжатия)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Table
    files["pdf"] = d / "sample.pdf"
    SimpleDocTemplate(str(files["pdf"]), pagesize=A4).build([
        Paragraph(HELLO, getSampleStyleSheet()["Title"]),
        Table(TABLE, style=[("GRID", (0, 0), (-1, -1), 1, (0, 0, 0))]),
        RLImage(str(files["png"]), width=160, height=100),
    ])

    from docx import Document
    doc = Document()
    doc.add_paragraph(HELLO)
    files["docx"] = d / "sample.docx"
    doc.save(files["docx"])

    from pptx import Presentation
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[0]).shapes.title.text = HELLO
    files["pptx"] = d / "sample.pptx"
    prs.save(files["pptx"])

    from openpyxl import Workbook
    wb = Workbook()
    for row in TABLE:
        wb.active.append(row)
    files["xlsx"] = d / "sample.xlsx"
    wb.save(files["xlsx"])

    files["csv"] = d / "sample.csv"
    files["csv"].write_text("\n".join(",".join(r) for r in TABLE) + "\n", encoding="utf-8")
    files["txt"] = d / "sample.txt"
    files["txt"].write_text(HELLO + "\n", encoding="utf-8")
    files["rtf"] = d / "sample.rtf"
    files["rtf"].write_text(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Arial;}}\f0\fs24 " + HELLO + r"\par}", encoding="ascii")

    # Старые и ODF-форматы делает сам LibreOffice — настоящие файлы, а не переименованные
    for ext, src in (("doc", "docx"), ("odt", "docx"), ("ppt", "pptx"), ("pps", "pptx"), ("ppsx", "pptx"),
                     ("xls", "xlsx")):
        out = d / "lo"
        subprocess.run([str(soffice), "--headless", "--norestore", f"-env:UserInstallation={profile.as_uri()}",
                        "--convert-to", ext, "--outdir", str(out), str(files[src])],
                       capture_output=True, timeout=180)
        made = out / f"sample.{ext}"
        if made.exists():
            files[ext] = made
    return files


# --------------------------------------------------------------------------- #

def main() -> int:
    from src.config.formats import SUPPORTED_CONVERSIONS
    from src.converters.factory import ConverterFactory
    from src.core.libreoffice_manager import LibreOfficeManager

    soffice = LibreOfficeManager()._find_soffice()
    if not soffice:
        print("LibreOffice не найден — сначала запустите tests/integration_check.py (он его ставит)")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="fcp_formats_"))
    pairs = sorted(SUPPORTED_CONVERSIONS)
    failed, started = [], time.time()
    try:
        files = make_inputs(tmp / "in", soffice, tmp / "lo-profile")
        print(f"Пар конвертации: {len(pairs)}; LibreOffice: {soffice}\n", flush=True)
        for src, dst in pairs:
            name = f"{src} → {dst}"
            if src not in files:
                failed.append(name)
                print(f"[FAIL] {name} — не удалось создать входной .{src}", flush=True)
                continue
            out = tmp / "out" / f"{src}_to_{dst}" / f"result.{dst}"
            out.parent.mkdir(parents=True)
            t = time.time()
            try:
                converter = ConverterFactory.get_converter(src, dst)
                ok = converter is not None and converter.convert(files[src], out)
                problem = None if ok else "конвертер вернул ошибку"
            except Exception as e:                          # noqa: BLE001 — нужен отчёт по каждой паре
                problem = f"исключение {type(e).__name__}: {e}"
            if problem is None and not out.exists():
                others = [p.name for p in out.parent.iterdir()]
                problem = "нет файла результата" + (f" (есть: {', '.join(others)})" if others else "")
            if problem is None:
                kind, want = sniff(out), EXPECTED[dst]
                if kind != want:
                    problem = f"внутри {kind.upper()}, а не {want.upper()}"
                else:
                    # Текст должен доехать везде, кроме картинок и слайдов-картинок (PDF → pptx/ppt/odp)
                    keeps_text = src not in ("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "heic", "heif") \
                        and dst not in ("pptx", "ppt", "odp") \
                        and want not in ("jpeg", "png", "webp", "bmp", "gif", "tiff")
                    marker = "apple" if {src, dst} & {"xlsx", "xls", "csv"} else "Hello"
                    text = text_of(out, kind) if keeps_text else None
                    if text is not None and marker not in text:
                        problem = f"в результате нет текста «{marker}»"
            if problem:
                failed.append(name)
                print(f"[FAIL] {name} — {problem}", flush=True)
            else:
                print(f"[OK] {name} ({max(out.stat().st_size // 1024, 1)} КБ, {time.time() - t:.1f} с)", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nИтог: {len(pairs) - len(failed)} из {len(pairs)} пар прошли за {time.time() - started:.0f} с" +
          (f"; не прошли: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
