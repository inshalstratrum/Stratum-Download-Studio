"""Regenerate I-DS native and unpacked-browser logo assets from one Qt SVG mark.

Developer-only helper: requires Pillow for .ico export; application runtime
uses only PyQt6. Run from repo root when brand identity changes.
"""
from pathlib import Path
import io
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ids_ui_components import BRAND_SVG, brand_icon

root = Path(__file__).resolve().parents[1]
app = QApplication.instance() or QApplication([])
(root / "stratum-download-studio-logo.svg").write_text(BRAND_SVG + "\n", encoding="utf-8")
brand = brand_icon(1024)
data = QByteArray()
buffer = QBuffer(data)
buffer.open(QIODevice.OpenModeFlag.WriteOnly)
assert brand.save(buffer, "PNG")
image = Image.open(io.BytesIO(bytes(data))).convert("RGBA")
image.save(root / "stratum-download-studio.ico", format="ICO", sizes=[
    (16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)
])
icons = root / "browser_extension" / "icons"
icons.mkdir(parents=True, exist_ok=True)
for size in (16, 32, 48, 128):
    image.resize((size, size), Image.Resampling.LANCZOS).save(
        icons / f"i-ds-{size}.png", optimize=True
    )
print("I-DS brand assets: SVG, ICO, Chrome/Edge/Firefox PNGs (16,32,48,128)")
