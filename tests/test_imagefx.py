"""Filter effects, watermark, picture transparency. Must print ALL GOOD."""
import glob
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import export, imagefx
from sitewright.model import Document, new_item

app = QApplication([])

# css
assert imagefx.css_filter({}) == "" and not imagefx.fx_active({})
c = imagefx.css_filter(dict(blur=4, grayscale=50, glow=8, glow_color="#ff0000"))
assert "blur(4px)" in c and "grayscale(0.5)" in c and "drop-shadow(0 0 8px #ff0000)" in c, c

# a red square on white
img = QImage(100, 100, QImage.Format_RGBA8888)
img.fill(QColor("white"))
p = QPainter(img)
p.fillRect(30, 30, 40, 40, QColor("#ff0000"))
p.end()
pil = imagefx.to_pil(img)
k = imagefx.colour_key(pil, "#ffffff", 10, 2)
assert k.getpixel((2, 2))[3] == 0 and k.getpixel((50, 50))[3] == 255
g = imagefx.apply_fx(pil, dict(grayscale=100))
r, gg, b, a = g.getpixel((50, 50))
assert abs(r - gg) < 3 and abs(gg - b) < 3
bl = imagefx.apply_fx(pil, dict(blur=6))
assert 0 < bl.getpixel((30, 50))[1] < 255          # the edge is soft now
inv = imagefx.apply_fx(pil, dict(invert=100))
assert inv.getpixel((2, 2))[:3] == (0, 0, 0)
gl = imagefx.apply_fx(imagefx.colour_key(pil, "#ffffff", 10, 2), dict(glow=10, glow_color="#00ff00"))
assert gl.getpixel((25, 50))[3] > 0 and gl.getpixel((25, 50))[1] > 100   # glow outside the square

# watermark writes pixels
big = QImage(400, 200, QImage.Format_RGBA8888)
big.fill(QColor("#000000"))
before = big.copy()
imagefx.draw_watermark(big, dict(text="hello", pos="bottom-right"), "hello")
assert big != before
t = QImage(400, 200, QImage.Format_RGBA8888)
t.fill(QColor("#000000"))
imagefx.draw_watermark(t, dict(pos="tile"), "hello")
assert t != big

# export: derived file + css filter
doc = Document()
buf = tempfile.mkdtemp()
png = os.path.join(buf, "a.png")
img.save(png)
aid = doc.add_asset(png) if hasattr(doc, "add_asset") else None
assert aid, "no add_asset"
it = new_item("image", 10, 10)
it.update(w=100, h=100)
it["asset"] = aid
it["transp"] = dict(color="#ffffff", tol=10, soft=2)
it["watermark"] = dict(text="%sitename%")
it["effects"] = dict(blur=3)
doc.pages[0]["items"].append(it)
out = tempfile.mkdtemp()
export.export_site(doc, out)
fx = glob.glob(os.path.join(out, "images", "fx-*.png"))
assert len(fx) == 1, fx
html = open(os.path.join(out, "index.html")).read()
assert "images/fx-" in html and "filter:blur(3px)" in html
assert QImage(fx[0]).hasAlphaChannel()
print("ALL GOOD")
