"""Generate the Dynamic Pro ERP app icon (matches the in-app brand mark).

Creates app.ico (multi-size) used by PyInstaller --icon, plus a PNG preview.
Run: python make_icon.py
"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 256
PRIMARY = (37, 99, 235)      # #2563eb
SKY = (14, 165, 233)         # #0ea5e9
WHITE = (255, 255, 255)
FONT_PATH = r"C:\Windows\Fonts\segoeuib.ttf"
HERE = os.path.dirname(os.path.abspath(__file__))


def _gradient(size):
    top, bottom = PRIMARY, SKY
    base = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(base)
    for y in range(size):
        t = y / (size - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color)
    return base


def _rounded_with_shadow(size, radius):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    # soft drop shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [8, 12, size - 1, size - 1], radius=radius, fill=(10, 20, 40, 90)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    base = _gradient(size).convert("RGBA")
    img.paste(shadow, (0, 0), shadow)
    img.paste(base, (0, 0), mask)
    return img


def _monogram(size):
    img = _rounded_with_shadow(size, int(size * 0.22))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, int(size * 0.42))
    text = "DP"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    # subtle shadow then main glyph
    draw.text((x, y + int(size * 0.02)), text, font=font, fill=(0, 0, 0, 60))
    draw.text((x, y), text, font=font, fill=WHITE)
    return img


if __name__ == "__main__":
    master = _monogram(SIZE)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_path = os.path.join(HERE, "app.ico")
    master.save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    preview = os.path.join(HERE, "icon_preview.png")
    master.save(preview)
    print("icon ->", ico_path)
    print("preview ->", preview)
