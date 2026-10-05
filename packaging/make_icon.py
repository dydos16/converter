"""
Иконка приложения: синий градиентный квадрат со скруглением и белые стрелки ⇄
(как значок вкладки «Конвертер»). Пишет icon.png, icon.ico (Windows), icon.icns (macOS).

    python packaging/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
S = 1024


def draw() -> Image.Image:
    # Градиент сверху вниз: светлее → насыщенный синий (как аватарки и кнопки в интерфейсе)
    top, bottom = (77, 170, 255), (0, 104, 230)
    grad = Image.new("RGB", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        k = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bottom)))

    # Скруглённый квадрат как у иконок macOS: поле ~10% и радиус ~22%
    mask = Image.new("L", (S, S), 0)
    pad = 100
    ImageDraw.Draw(mask).rounded_rectangle([pad, pad, S - pad, S - pad], radius=185, fill=255)
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(grad, (0, 0), mask)

    # Стрелки ⇄ на сетке 24×24, как значок «arrows» в src/gui/glass.py, но разведены шире:
    # на крупной иконке наконечники иначе наезжают на соседнюю стрелку
    d = ImageDraw.Draw(icon)
    u = (S - 2 * pad) / 24
    w = round(1.8 * u)

    def p(x, y):
        return pad + x * u, pad + y * u

    white = (255, 255, 255, 255)
    for line in ([(5.5, 8), (18.5, 8)], [(15, 4.5), (18.5, 8), (15, 11.5)],
                 [(18.5, 16), (5.5, 16)], [(9, 12.5), (5.5, 16), (9, 19.5)]):
        pts = [p(*pt) for pt in line]
        d.line(pts, fill=white, width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):   # круглые концы линий
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=white)
    return icon


if __name__ == "__main__":
    img = draw()
    img.save(OUT / "icon.png")
    img.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(OUT / "icon.icns")
    print("icon.png, icon.ico, icon.icns →", OUT)
