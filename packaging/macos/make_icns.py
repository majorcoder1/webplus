"""Makes WebPlus.icns (the Mac app icon) from the PNG icons. Needs Pillow: python3 make_icns.py OUT.icns"""
import os
import sys

from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
src = Image.open(os.path.join(here, "..", "..", "icons", "sitewright-512.png")).convert("RGBA")
src.save(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "WebPlus.icns"),
         sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512)])
