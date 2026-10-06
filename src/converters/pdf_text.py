"""
Текст страницы PDF так, как он виден: строка за строкой, слева направо.

Буквы и знаки в одной строке бывают разными шрифтами (например, кириллица из запасного шрифта, а запятые,
дефисы и цифры — из основного). Тогда PyMuPDF раскладывает их по разным «строкам», а на месте символов
другого шрифта вставляет пробелы-заглушки — и get_text() выдаёт «, ! — 2026 Привет конвертер» вместо
«Привет, конвертер! — 2026» и «Кол во» вместо «Кол-во». Поэтому строки собираем заново по символам.
Блоки и спаны — из page.get_text("rawdict"), где у каждого символа есть свои координаты.
"""
import io
import re
import sys
from pathlib import Path

import fitz
from loguru import logger
from PIL import Image, ImageChops, ImageOps


def block_lines(block: dict) -> list[list[dict]]:
    """Спаны текстового блока, сгруппированные в видимые строки (по базовой линии) сверху вниз."""
    rows: list[list] = []
    for span in (s for line in block["lines"] for s in line["spans"]):
        y = span["origin"][1]
        row = next((r for r in rows if abs(r[0] - y) < span["size"] * 0.5), None)
        if row is None:
            rows.append([y, [span]])
        else:
            row[1].append(span)
    return [spans for _, spans in sorted(rows, key=lambda r: r[0])]


def _row_chars(spans: list[dict]) -> list:
    """Символы строки слева направо (с их спанами), без пробелов-заглушек поверх символов другого шрифта."""
    chars = [(c, s) for s in spans for c in s["chars"]]
    solid = [c["bbox"] for c, _ in chars if not c["c"].isspace()]

    def filler(c) -> bool:
        # Заглушка лежит поверх чужого символа (часто — поверх запятой и пробела за ней, то есть на половину);
        # настоящий пробел видимые символы почти не задевает
        x0, x1 = c["bbox"][0], c["bbox"][2]
        return any(min(x1, b[2]) - max(x0, b[0]) > (x1 - x0) * 0.25 for b in solid)

    return sorted(((c, s) for c, s in chars if not (c["c"].isspace() and filler(c))), key=lambda cs: cs[0]["bbox"][0])


def line_segments(spans: list[dict]) -> list[tuple[float, float, list]]:
    """Строка, разрезанная по большим разрывам (столбцы таблицы): [(x0, x1, куски)]."""
    segments: list[list] = []
    for c, s in _row_chars(spans):
        if c["c"].isspace() and not segments:
            continue
        if not segments or (not c["c"].isspace() and c["bbox"][0] - segments[-1][1] > s["size"] * 1.5):
            segments.append([c["bbox"][0], c["bbox"][2], []])
        segment = segments[-1]
        segment[2].append((c, s))
        if not c["c"].isspace():
            segment[1] = max(segment[1], c["bbox"][2])
    return [(x0, x1, _pieces(chars)) for x0, x1, chars in segments]


def line_pieces(spans: list[dict]) -> list[tuple[str, dict]]:
    """Текст строки слева направо кусками со своими спанами (для оформления). Пробелы-заглушки поверх символов
    другого шрифта выброшены, двойные пробелы схлопнуты, пропущенные между словами — добавлены по зазору."""
    return _pieces(_row_chars(spans))


def _pieces(chars: list) -> list[tuple[str, dict]]:
    pieces: list[list] = []
    end = None
    for c, span in chars:
        ch = " " if c["c"].isspace() else c["c"]
        text = "".join(p[0] for p in pieces[-1:])
        if ch != " " and end is not None and c["bbox"][0] - end > span["size"] * 0.25 and not text.endswith(" "):
            ch = " " + ch                               # видимый зазор между словами — это пробел
        if ch == " " and (not pieces or text.endswith(" ")):
            continue                                    # без пробела в начале строки и двойных пробелов
        if pieces and pieces[-1][1] is span:
            pieces[-1][0] += ch
        else:
            pieces.append([ch, span])
        end = c["bbox"][2] if end is None else max(end, c["bbox"][2])
    return [(text, span) for text, span in pieces]


def page_text(page: "fitz.Page", clip=None) -> str:
    """Текст страницы (или её области): блоки в порядке PDF, строки блока — каждая с новой строки.
    У скана текстового слоя нет — тогда текст распознаём (OCR)."""
    if clip is None and not has_text(page):
        return "\n".join("".join(text for text, _ in pieces) for _, pieces in ocr_lines(page))
    lines = []
    for block in page.get_text("rawdict", clip=clip)["blocks"]:
        if block["type"] == 0:
            lines += [re.sub(r" +$", "", "".join(text for text, _ in line_pieces(row))) for row in block_lines(block)]
    return "\n".join(line for line in lines if line)


def pdf_problem(path: Path) -> str | None:
    """Почему PDF не обработать: под паролем, пустой или повреждён. None — всё в порядке (и для не-PDF)."""
    if Path(path).suffix.lower() != ".pdf":
        return None
    try:
        with fitz.open(path) as doc:
            if doc.needs_pass:
                return ("PDF защищён паролем. Откройте его в программе для просмотра PDF, сохраните копию "
                        "без пароля и сконвертируйте её.")
            if doc.page_count == 0:
                return "В PDF нет ни одной страницы."
    except Exception:
        return "Не удалось открыть PDF — файл повреждён или это не PDF."
    return None


def has_text(page: "fitz.Page") -> bool:
    """Есть ли у страницы текстовый слой (у скана — нет)."""
    return bool(page.get_text().strip())


# --------------------------------------------------------------------------- #
#  OCR сканов: Tesseract встроен в PyMuPDF, нужны только языковые модели (packaging/tessdata)
# --------------------------------------------------------------------------- #

OCR_LANGUAGES = "rus+eng"
OCR_DPI = 300
_JUNK = "|[]`_~"            # так OCR читает обрезки линий таблиц


def tessdata_dir() -> Path:
    """Модели Tesseract: в собранном приложении — рядом с программой, при запуске из исходников — в packaging/."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2] / "packaging"))
    return base / "tessdata"


def ocr_available() -> bool:
    return (tessdata_dir() / "rus.traineddata").exists()


def _erase_rules(img: Image.Image) -> Image.Image:
    """Стирает длинные линии (рамки таблиц): Tesseract принимает таблицу с рамкой за картинку и пропускает её.
    Ужимаем картинку вдоль строки с усреднением — тёмным остаётся только сплошная линия длиннее порога."""
    gray = img.convert("L")
    ink = ImageOps.invert(gray).point(lambda v: 255 if v > 96 else 0)
    w, h = gray.size
    masks = []
    for size in ((max(1, w // max(8, w // 20)), h), (w, max(1, h // max(8, h // 25)))):
        small = ink.resize(size, Image.Resampling.BOX).point(lambda v: 255 if v > 200 else 0)
        masks.append(small.resize((w, h), Image.Resampling.NEAREST))
    return ImageChops.lighter(gray, ImageChops.lighter(*masks))


def _ocr_page_lines(page: "fitz.Page") -> list:
    textpage = page.get_textpage_ocr(language=OCR_LANGUAGES, dpi=OCR_DPI, full=True, tessdata=str(tessdata_dir()))
    lines = []
    for block in page.get_text("rawdict", textpage=textpage)["blocks"]:
        if block["type"] == 0:
            for row in block_lines(block):
                text = _clean_ocr("".join(t for t, _ in line_pieces(row)))
                if text:
                    rect = fitz.Rect(row[0]["bbox"])
                    for span in row[1:]:
                        rect |= span["bbox"]
                    lines.append((rect, [(text, row[0])]))
    return lines


def _clean_ocr(text: str) -> str:
    """Убирает обрезки линий («|», «[», «_») и строки без смысла (мусор с фотографий)."""
    text = re.sub(rf"(?<!\S)[{re.escape(_JUNK)}]+(?!\S)", " ", text)                     # отдельные «|», «_»
    text = re.sub(rf"(?<!\S)[{re.escape(_JUNK)}]+(?=\w)|(?<=\w)[{re.escape(_JUNK)}]+(?!\S)", "", text)   # приклеенные
    text = re.sub(r"\s+", " ", text).strip()
    meaningful = re.search(r"\d", text) or any(sum(ch.isalpha() for ch in word) >= 3 for word in text.split())
    return text if meaningful else ""


def _score(line) -> int:
    return sum(ch.isalnum() for text, _ in line[1] for ch in text)


def ocr_lines(page: "fitz.Page") -> list:
    """Строки скана, распознанные OCR: [(рамка, [(текст, спан)])] сверху вниз.
    Два прохода — по исходной картинке и по картинке без линий таблиц; для каждого места берём прочтение,
    в котором больше букв и цифр (стирание линий иногда задевает буквы, касающиеся линии)."""
    if not ocr_available():
        return []
    try:
        lines = _ocr_page_lines(page)
        pix = page.get_pixmap(dpi=OCR_DPI)
        cleaned = _erase_rules(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        buffer = io.BytesIO()
        cleaned.save(buffer, "PNG")
        with fitz.open() as scratch:
            clean_page = scratch.new_page(width=page.rect.width, height=page.rect.height)
            clean_page.insert_image(clean_page.rect, stream=buffer.getvalue())
            for line in _ocr_page_lines(clean_page):
                rivals = [other for other in lines if other[0].intersects(line[0])]
                if _score(line) > sum(_score(other) for other in rivals):
                    lines = [other for other in lines if all(other is not r for r in rivals)] + [line]
    except Exception as e:                                  # OCR — бонус: без него страница просто без текста
        logger.warning(f"Не удалось распознать текст страницы: {e}")
        return []
    return sorted(lines, key=lambda line: (round(line[0].y0 / 4), line[0].x0))
