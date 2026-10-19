"""Picture library: icons, textures, patterns, shapes all list, tint, add to the site, and save/load.
Must print ALL GOOD."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtWidgets import QApplication

from sitewright import library, starter
from sitewright.panels import StarterDialog
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()

# the drawn shapes
names = starter.names()
assert len(names) >= 30
for grp, name in names:
    assert starter.png_bytes(grp, name)[:4] == b"\x89PNG", (grp, name)

# library contents
assert len(library.icon_names()) > 5000
assert "home" in library.icon_names("home")
assert len(library.textures()) >= 30
assert len(library.patterns()) >= 80
for f in ("CREDITS.md", "LICENSE-tabler-icons.txt"):
    assert os.path.isfile(os.path.join(library.ROOT, f)), f

dlg = StarterDialog(w)
# icons: search narrows, tinting really recolours
dlg.search.setText("home")
n = dlg.list.count()
assert 0 < n < library.icon_names().__len__(), n
dlg.ink = "#ff0000"
img = library.tinted(library.path_for("icon", "home"), "#ff0000")
reds = [img.pixelColor(x, y) for x in range(0, img.width(), 8) for y in range(0, img.height(), 8)]
solid = [c for c in reds if c.alpha() > 200]
assert solid and all(c.red() > 200 and c.green() < 60 for c in solid)
dlg.list.selectAll()
dlg.add_selected()
added_icons = len(w.doc.assets)
assert added_icons == n

# textures, patterns, shapes
for idx, want in ((1, len(library.textures())), (2, len(library.patterns())), (5, len(starter.ICONS))):
    dlg.group.setCurrentIndex(idx)
    assert dlg.list.count() == want, (idx, dlg.list.count(), want)
    before = len(w.doc.assets)
    dlg.list.selectAll()
    dlg.add_selected()
    assert len(w.doc.assets) == before + want

# a picture from the library can be placed and the file saves and reloads
aid = next(iter(w.doc.assets))
w.insert_asset(aid)
path = os.path.join(tempfile.mkdtemp(), "t.sitewright")
w.doc.save(path)
w.open_path(path)
assert aid in w.doc.assets
dlg.close()
dlg.deleteLater()
w.close()
w.deleteLater()
app.processEvents()
del dlg, w
print("ALL GOOD")
