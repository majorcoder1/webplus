"""Awkward situations for the newest features. Must print ALL GOOD."""
import io
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtWidgets import QApplication

from sitewright import export, imagefx, photolab, shapes
from sitewright.model import Document, new_item, new_page
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
w._sel_guard = True


class Ev:
    def __init__(self, pt, button=Qt.LeftButton):
        self._p = w.view.mapFromScene(QPointF(*pt))
        self._b = button

    def pos(self): return self._p
    def globalPos(self): return QPoint(0, 0)
    def button(self): return self._b
    def modifiers(self): return Qt.NoModifier


# editing a shape, then the page changes / the shape is deleted / undo
w.create_item("shape:star", QRectF(100, 100, 100, 100))
d = w.cur_page()["items"][-1]
w.nodes.start(d)
assert w.nodes.active
w.doc.pages.append(new_page("Two"))
w.page_index = 1
w.reload()
assert not w.nodes.active
w.page_index = 0
w.reload()
w.nodes.start(d)
w.cur_page()["items"].remove(d)
w.reload()
assert not w.nodes.active

# pen with one point, then Enter, then switching tools mid-way
w.set_tool("pen")
w.pen.press(Ev((50, 50)))
w.pen.key(type("K", (), {"key": lambda s: Qt.Key_Return})())
assert w.tool == "select" and not w.pen.pts
w.set_tool("pen")
w.pen.press(Ev((50, 50)))
w.pen.press(Ev((90, 50)))
w.set_tool("select")
assert not w.pen.pts
# straight horizontal line has a box with some height
w.set_tool("pen")
for pt in ((10, 300), (200, 300)):
    w.pen.press(Ev(pt)); w.pen.release(Ev(pt))
w.pen.key(type("K", (), {"key": lambda s: Qt.Key_Return})())
line = w.cur_page()["items"][-1]
assert line["h"] >= 1 and line["w"] > 100

# a rotated shape cannot be point-edited, but exports and paints
r = new_item("shape", 300, 300, preset="heart")
r.update(rot=30, fx=True)
w.cur_page()["items"].append(r)
w.reload()
out = tempfile.mkdtemp()
export.export_site(w.doc, out)
assert "rotate(30deg)" in open(os.path.join(out, "index.html")).read()

# save / reload keeps shapes
p = os.path.join(out, "s.site")
w.doc.save(p)
d2 = Document.load(p)
assert any(i["kind"] == "shape" and i["nodes"] for i in d2.pages[0]["items"])

# empty custom crop falls back to a rectangle
assert shapes.shape_nodes({"nodes": [], "closed": True})[0]
assert shapes.shape_nodes("nonsense")[0]

# photolab on odd picture types
for mode in ("P", "CMYK", "LA", "RGBA", "L", "1", "RGB"):
    im = Image.new(mode, (30, 20))
    buf = io.BytesIO()
    fmt = "JPEG" if mode == "CMYK" else "PNG"
    im.save(buf, fmt)
    photolab.process(Image.open(io.BytesIO(buf.getvalue())), dict(photolab.DEFAULTS, contrast=20, vignette=30, rotate=270, crop=(0.1, 0.1, 0.9, 0.9)))
tiny = Image.new("RGB", (1, 1))
photolab.process(tiny, dict(photolab.DEFAULTS, crop=(0, 0, 1, 1), vignette=50, blur=5))
photolab.process(tiny, dict(photolab.DEFAULTS, crop=(0.5, 0.5, 0.5, 0.5)))

# effects: cache is reused and refreshed
aid = w.doc.add_asset_bytes("a.png", (lambda b: (Image.new("RGB", (40, 40), (200, 0, 0)).save(b, "PNG"), b.getvalue())[1])(io.BytesIO()))
im = new_item("image", 400, 50, asset=aid, effects=dict(blur=3))
im.update(w=100, h=100)
w.cur_page()["items"].append(im)
w.reload()
obj = next(o for o in w.scene.items() if hasattr(o, "d") and o.d is im)
from PyQt5.QtGui import QImage, QPainter
canvas = QImage(300, 300, QImage.Format_ARGB32)
pt = QPainter(canvas); obj.paint(pt, None); first = obj._fxcache[1]; obj.paint(pt, None)
assert obj._fxcache[1] is first
im["effects"] = dict(blur=6)
obj.paint(pt, None)
assert obj._fxcache[1] is not first
pt.end()

# effects on every kind export without breaking markup
for k in ("text", "rect", "button", "navbar", "table", "hotspot", "shape"):
    it = new_item(k, 10, 600)
    it["effects"] = dict(blur=2, grayscale=50)
    w.cur_page()["items"].append(it)
export.export_site(w.doc, out)
html = open(os.path.join(out, "index.html")).read()
assert html.count("filter:") >= 7
print("ALL GOOD")

# an animated GIF with an effect keeps animating in the editor
from PIL import Image as PI
from PyQt5.QtCore import QEventLoop, QTimer
tmpd = tempfile.mkdtemp()
frames = [PI.new("RGB", (40, 40), c) for c in ("#ff0000", "#00ff00", "#0000ff")]
gp = os.path.join(tmpd, "a.gif")
frames[0].save(gp, save_all=True, append_images=frames[1:], duration=40, loop=0)
from sitewright import pageitems
g = pageitems.make_gif(w, gp)
g["effects"] = dict(blur=2)
w.reload()
gobj = next(o for o in w.scene.items() if hasattr(o, "d") and o.d is g)
canvas = QImage(300, 300, QImage.Format_ARGB32)
seen = set()
for _ in range(40):
    loop = QEventLoop(); QTimer.singleShot(30, loop.quit); loop.exec_()
    pt = QPainter(canvas); gobj.paint(pt, None); pt.end()
    seen.add(gobj._fxcache[1].pixelColor(25, 25).name())
assert len(seen) >= 2, seen
print("ALL GOOD")

# phone photos: the hidden rotate note is applied once, at import
import base64
from sitewright.model import upright
im = Image.new("RGB", (200, 100), (255, 0, 0))
im.paste((0, 0, 255), (0, 0, 100, 100))
for orient, size in ((1, (200, 100)), (6, (100, 200)), (8, (100, 200)), (3, (200, 100))):
    ex = im.getexif()
    ex[0x0112] = orient
    pth = os.path.join(tmpd, "o%d.jpg" % orient)
    im.save(pth, exif=ex)
    d2 = Document()
    aid2 = d2.add_asset(pth)
    q = QImage()
    q.loadFromData(d2.asset_bytes(aid2))
    assert (q.width(), q.height()) == size, (orient, q.width(), q.height())
    assert Image.open(io.BytesIO(d2.asset_bytes(aid2))).getexif().get(0x0112, 1) == 1
# rotating by 6 (90 clockwise) moves the blue left half to the top
d3 = Document(); a3 = d3.add_asset(os.path.join(tmpd, "o6.jpg"))
pic = Image.open(io.BytesIO(d3.asset_bytes(a3))).convert("RGB")
assert pic.getpixel((50, 10))[2] > 200 and pic.getpixel((50, 190))[0] > 200
# an old saved site with a sideways photo is fixed when opened
d4 = Document()
raw = open(os.path.join(tmpd, "o6.jpg"), "rb").read()
d4.assets["x"] = dict(name="o6.jpg", data=base64.b64encode(raw).decode())
d4.assets["x"]["data"] = base64.b64encode(open(pth, "rb").read()).decode() if False else d4.assets["x"]["data"]
sp = os.path.join(tmpd, "old.site")
ex = im.getexif(); ex[0x0112] = 6
im.save(os.path.join(tmpd, "raw6.jpg"), exif=ex)
d4.assets["x"] = dict(name="raw6.jpg", data=base64.b64encode(open(os.path.join(tmpd, "raw6.jpg"), "rb").read()).decode())
d4.save(sp)
# save() only keeps used assets, so use the image in a page
d4.pages[0]["items"].append(new_item("image", 0, 0, asset="x"))
d4.save(sp)
q = QImage(); q.loadFromData(Document.load(sp).asset_bytes("x"))
assert (q.width(), q.height()) == (100, 200)
# non-photos and broken data are left alone
assert upright("a.gif", b"GIF89a") == b"GIF89a" and upright("a.jpg", b"not a picture") == b"not a picture"
print("ALL GOOD")
print("ALL GOOD")

# a pop-up menu must not be clipped by its object (text and rounded pictures used to hide it)
dp = Document()
aidp = dp.add_asset_bytes("p.png", (lambda b: (Image.new("RGB", (20, 20)).save(b, "PNG"), b.getvalue())[1])(io.BytesIO()))
tp = new_item("text", 10, 10, text="Menu", popup="One|http://example.com")
ip = new_item("image", 10, 100, asset=aidp, radius=12, popup="A|http://example.com/a")
dp.pages[0]["items"] += [tp, ip]
outp = tempfile.mkdtemp()
export.export_site(dp, outp)
htmlp = open(os.path.join(outp, "index.html")).read()
import re as _re
for m in _re.finditer(r'<div[^>]*class="o pm"[^>]*style="([^"]*)"', htmlp):
    assert "overflow:hidden" not in m.group(1), m.group(1)
assert htmlp.count('class="o pm"') == 2 and "border-radius:12px" in htmlp
print("ALL GOOD")
