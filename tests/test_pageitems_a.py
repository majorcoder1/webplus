"""Empty picture frame, rollover, animated GIF, sound and a page's background sound.
Must print ALL GOOD."""
import os
import sys
import tempfile
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import export, pageitems, taskcheck
from sitewright.canvas import ItemObj
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc
tmp = tempfile.mkdtemp()


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


def png(name, colour):
    p = os.path.join(tmp, name)
    img = QImage(60, 40, QImage.Format_RGB32)
    img.fill(QColor(colour))
    img.save(p)
    return p


# ---- empty picture frame
d = pageitems.insert_empty_frame(w, QRectF(30, 30, 200, 120))
assert d["kind"] == "image" and d["asset"] == "" and (d["w"], d["h"]) == (200, 120)
frame = [o for o in objs()][0]
img = QImage(220, 140, QImage.Format_ARGB32)
img.fill(0xffffffff)
pp = QPainter(img)
frame.paint_image(pp, QRectF(0, 0, 200, 120))
pp.end()
assert img.pixelColor(100, 60).lightness() < 250, "the frame is drawn, with its words"
html_ = export.page_source(doc, doc.pages[0]["id"], False)
assert "missing.png" not in html_, "an empty frame is not published"
assert any("Empty picture frame" in m[0] for m in taskcheck.check(doc)) if hasattr(taskcheck, "check") else True
assert pageitems.fill_frame(w, d, png("a.png", "#c33"))
assert doc.pages[0]["items"][0]["asset"] in doc.assets
assert not pageitems.fill_frame(w, doc.pages[0]["items"][0], "")
# the tool made by "Empty picture frame" in the menu
doc.pages[0]["items"].clear()
w.create_item("emptyframe", QRectF(10, 10, 4, 4))
assert doc.pages[0]["items"][0]["asset"] == "" and doc.pages[0]["items"][0]["w"] == 240

# ---- rollover
doc.pages[0]["items"].clear()
r = pageitems.make_rollover(w, png("n.png", "#33c"), png("o.png", "#3c3"), "fade", "https://example.com")
assert r["hover_effect"] == "fade" and r["link"] == "https://example.com" and r["hover_asset"] != r["asset"]
assert r["w"] == 60 and r["h"] == 40
out = tempfile.mkdtemp()
export.export_site(doc, out)
page = open(os.path.join(out, "index.html"), encoding="utf-8").read()
assert 'class="o ro"' in page and 'class="ro-b"' in page and "n.png" in page and "o.png" in page

# ---- animated GIF
frames = [Image.new("RGB", (40, 30), c) for c in ("red", "green", "blue")]
gif = os.path.join(tmp, "spin.gif")
frames[0].save(gif, save_all=True, append_images=frames[1:], duration=80, loop=0)
doc.pages[0]["items"].clear()
g = pageitems.make_gif(w, gif)
assert g["kind"] == "image" and (g["w"], g["h"]) == (40, 30)
assert pageitems.is_gif(doc, g["asset"]) and not pageitems.is_gif(doc, r["asset"])
w.reload()
pm = w.gif_pixmap(g["asset"])
assert pm is not None and not pm.isNull()
assert w._gifs[g["asset"]].frameCount() == 3
seen = set()
for _ in range(40):
    app.processEvents()
    seen.add(w.gif_pixmap(g["asset"]).toImage().pixelColor(5, 5).name())
    import time
    time.sleep(0.03)
assert len(seen) >= 2, "the GIF really plays in the editor: %s" % seen
assert w.gif_pixmap(r["asset"]) is None
# the file goes out untouched so it still animates
out = tempfile.mkdtemp()
export.export_site(doc, out, optimise=True)
name = export.asset_names(doc)[g["asset"]]
assert open(os.path.join(out, "images", name), "rb").read() == open(gif, "rb").read()

# ---- sound object and page sound
wav = os.path.join(tmp, "beep.wav")
with wave.open(wav, "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(8000)
    f.writeframes(b"\x00\x10" * 800)
doc.pages[0]["items"].clear()
s = pageitems.make_sound(w, wav)
assert s["kind"] == "audio" and s["asset"] in doc.assets
out = tempfile.mkdtemp()
export.export_site(doc, out)
assert '<audio src="images/beep.wav" controls' in open(os.path.join(out, "index.html"), encoding="utf-8").read()

page = doc.pages[0]
aid = doc.add_asset(wav)
page["sound"] = dict(asset=aid, loop=True)
html_ = export.page_source(doc, page["id"], False)
assert 'id="pgsnd"' in html_ and "loop" in html_.split('id="pgsnd"')[1].split(">")[0]
page["sound"]["loop"] = False
assert " loop" not in export.page_source(doc, page["id"], False).split('id="pgsnd"')[1].split(">")[0]
assert aid in doc.used_assets()
from sitewright import managers
assert any("sound" in n for n in managers.file_usage(doc)[aid])
# page settings dialog carries the sound choice
from sitewright.window import PageDialog
pd = PageDialog(w, page, doc)
assert pd.sound_label.text() == "beep.wav" and pd.sound_loop.isChecked() is False
pd.drop_sound()
assert pd.sound_clear and pd.sound_label.text() == "none"

# menus
labels = []
def walk(m):
    for a in m.actions():
        if a.menu():
            walk(a.menu())
        else:
            labels.append(a.text().replace("&", ""))
for a in w.menuBar().actions():
    if a.menu():
        walk(a.menu())
for want in ("Empty picture frame", "Rollover (picture that changes)...", "Animated GIF...", "Sound..."):
    assert want in labels, want
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
