"""PhotoLab edits and Crop to shape. Must print ALL GOOD."""
import io
import os
import re
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication

from sitewright import export, photolab
from sitewright.canvas import ItemObj
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w._sel_guard = True

# a 200x100 picture: left half red, right half blue
src = Image.new("RGB", (200, 100), (255, 0, 0))
src.paste((0, 0, 255), (100, 0, 200, 100))
path = os.path.join(tempfile.mkdtemp(), "pic.png")
src.save(path)
D = dict(photolab.DEFAULTS)

r = photolab.process(src, dict(D, rotate=90))
assert r.size == (100, 200) and r.getpixel((50, 10))[:3] == (255, 0, 0) or r.getpixel((50, 10))[2] > 200
r = photolab.process(src, dict(D, flipx=True))
assert r.getpixel((10, 50))[2] > 200
r = photolab.process(src, dict(D, crop=(0.5, 0, 1, 0.5)))
assert r.size == (100, 50) and r.getpixel((5, 5))[2] > 200
r = photolab.process(src, dict(D, gray=True))
assert len({r.getpixel((10, 10))[0], r.getpixel((10, 10))[1], r.getpixel((10, 10))[2]}) == 1
r = photolab.process(Image.new("RGB", (4, 4), (100, 100, 100)), dict(D, brightness=50))
assert r.getpixel((1, 1))[0] > 100
r = photolab.process(src, dict(D, vignette=100))
assert sum(r.getpixel((0, 0))[:3]) < sum(r.getpixel((100, 50))[:3])
for k in ("contrast", "saturation", "warmth", "hue", "sharpness", "blur", "sepia", "auto"):
    photolab.process(src, dict(D, **{k: 30 if k not in ("sepia", "auto") else True}), 80)
big = photolab.process(Image.new("RGB", (3000, 1000)), D, 600)
assert big.width == 600

# the dialog and applying it
aid = w.doc.add_asset(path)
from sitewright.model import new_item
it = new_item("image", 40, 40, asset=aid)
it.update(w=200, h=100)
w.cur_page()["items"].append(it)
w.reload()
dlg = photolab.PhotoLab(w, it)
dlg.p["crop"] = (0.0, 0.0, 0.5, 1.0)
dlg.p["rotate"] = 0
name, data, size = dlg.result_bytes()
assert size == (100, 100) and name == "pic-edited.png"
dlg.apply()
assert it["asset"] != aid and it["h"] == 200 * 1 * 100 // 100 or it["h"] == 200
dlg.set_ratio()
dlg.turn(90)
assert dlg.p["crop"] is None
dlg.reset()

# crop to shape: editor path and export
it["cropshape"] = "heart"
w.reload()
out = tempfile.mkdtemp()
export.export_site(w.doc, out)
html = open(os.path.join(out, "index.html")).read()
assert 'clipPathUnits="objectBoundingBox"' in html and "clip-path:url(#cs-" in html, html[-800:]
it["cropshape"] = dict(nodes=[[0, 0, 0, 0, 0, 0, False], [1, 0, 1, 0, 1, 0, False], [.5, 1, .5, 1, .5, 1, False]], closed=True)
export.export_site(w.doc, out)
assert "clip-path:url(#cs-" in open(os.path.join(out, "index.html")).read()
print("ALL GOOD")
