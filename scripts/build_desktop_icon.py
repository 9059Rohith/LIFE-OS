"""Render the LIFEOS favicon geometry as a multi-resolution Windows icon."""

from pathlib import Path

from PIL import Image, ImageDraw


def main():
    scale = 8
    image = Image.new("RGBA", (64 * scale, 64 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 64 * scale - 1, 64 * scale - 1), radius=16 * scale, fill="#193c30")
    draw.polygon([(18 * scale, 15 * scale), (26 * scale, 15 * scale), (26 * scale, 42 * scale),
                  (47 * scale, 42 * scale), (47 * scale, 49 * scale), (18 * scale, 49 * scale)], fill="#eaf0df")
    draw.ellipse((38 * scale, 15 * scale, 50 * scale, 27 * scale), fill="#b7d08d")
    output = Path(__file__).resolve().parents[1] / "desktop" / "icon.ico"
    image.save(output, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                          (64, 64), (128, 128), (256, 256)])
    print(output)


if __name__ == "__main__":
    main()
