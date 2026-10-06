"""
Текст страницы PDF так, как он виден: строка за строкой, слева направо.

Буквы и знаки в одной строке бывают разными шрифтами (например, кириллица из запасного шрифта, а запятые,
дефисы и цифры — из основного). Тогда PyMuPDF раскладывает их по разным «строкам», а на месте символов
другого шрифта вставляет пробелы-заглушки — и get_text() выдаёт «, ! — 2026 Привет конвертер» вместо
«Привет, конвертер! — 2026» и «Кол во» вместо «Кол-во». Поэтому строки собираем заново по символам.
Блоки и спаны — из page.get_text("rawdict"), где у каждого символа есть свои координаты.
"""
import re

import fitz


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


def line_pieces(spans: list[dict]) -> list[tuple[str, dict]]:
    """Текст строки слева направо кусками со своими спанами (для оформления). Пробелы-заглушки поверх символов
    другого шрифта выброшены, двойные пробелы схлопнуты, пропущенные между словами — добавлены по зазору."""
    chars = [(c, s) for s in spans for c in s["chars"]]
    solid = [c["bbox"] for c, _ in chars if not c["c"].isspace()]

    def filler(c) -> bool:
        # Заглушка лежит поверх чужого символа (часто — поверх запятой и пробела за ней, то есть на половину);
        # настоящий пробел видимые символы почти не задевает
        x0, x1 = c["bbox"][0], c["bbox"][2]
        return any(min(x1, b[2]) - max(x0, b[0]) > (x1 - x0) * 0.25 for b in solid)

    chars = sorted(((c, s) for c, s in chars if not (c["c"].isspace() and filler(c))), key=lambda cs: cs[0]["bbox"][0])
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
    """Текст страницы (или её области): блоки в порядке PDF, строки блока — каждая с новой строки."""
    lines = []
    for block in page.get_text("rawdict", clip=clip)["blocks"]:
        if block["type"] == 0:
            lines += [re.sub(r" +$", "", "".join(text for text, _ in line_pieces(row))) for row in block_lines(block)]
    return "\n".join(line for line in lines if line)
