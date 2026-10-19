"""Dialogs for picture effects: Filter Effects (any object), Watermark and Transparent Colour (pictures)."""
import copy

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                             QLineEdit, QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout)

from . import imagefx


class ColorButton(QPushButton):
    def __init__(self, colour, on_change):
        super().__init__()
        self.colour, self.on_change = colour, on_change
        self.clicked.connect(self.pick)
        self.show_colour()

    def show_colour(self):
        self.setStyleSheet("background:%s;min-width:60px;min-height:22px" % self.colour)

    def pick(self):
        c = QColorDialog.getColor(QColor(self.colour), self, "Choose a colour")
        if c.isValid():
            self.set(c.name())

    def set(self, colour):
        self.colour = colour
        self.show_colour()
        self.on_change()


def slider(lo, hi, val, on_change):
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    s.valueChanged.connect(lambda _=0: on_change())
    return s


def need_pillow(win):
    if imagefx.have_pil():
        return False
    QMessageBox.information(win, "WebPlus", "This needs the Pillow picture library, which is not installed.")
    return True


# -- Filter Effects -------------------------------------------------------------------------------
SLIDERS = [("blur", "Blur", 0, 40), ("brightness", "Brightness", 0, 250), ("contrast", "Contrast", 0, 250),
           ("grayscale", "Black and white", 0, 100), ("sepia", "Sepia (old photo)", 0, 100),
           ("hue", "Colour shift", 0, 360), ("saturate", "Colour strength", 0, 300),
           ("invert", "Invert colours", 0, 100), ("glow", "Glow", 0, 40)]


def filter_effects(win):
    objs = win.selected()
    if not objs:
        win.statusBar().showMessage("Select an object first", 4000)
        return
    if need_pillow(win):
        return
    before = [copy.deepcopy(o.d.get("effects")) for o in objs]
    dlg = QDialog(win)
    dlg.setWindowTitle("Filter effects")
    lay = QFormLayout(dlg)
    cur = imagefx.fx_values(objs[0].d.get("effects"))
    sl = {}

    def apply():
        fx = {k: s.value() for k, s in sl.items()}
        fx["glow_color"] = glow.colour
        for o in objs:
            if imagefx.fx_active(fx):
                o.d["effects"] = dict(fx)
            else:
                o.d.pop("effects", None)
            o.prepareGeometryChange()
            o.update()
        win.scene.update()

    for key, label, lo, hi in SLIDERS:
        sl[key] = slider(lo, hi, cur[key], apply)
        lay.addRow(label, sl[key])
    glow = ColorButton(cur["glow_color"], apply)
    lay.addRow("Glow colour", glow)
    reset = QPushButton("Remove all effects")
    reset.clicked.connect(lambda: [s.setValue(imagefx.FX_DEFAULT[k]) for k, s in sl.items()])
    lay.addRow(reset)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addRow(bb)
    if dlg.exec_() == QDialog.Accepted:
        win.commit_if_changed("Filter effects")
    else:
        for o, b in zip(objs, before):
            if b is None:
                o.d.pop("effects", None)
            else:
                o.d["effects"] = b
            o.prepareGeometryChange()
            o.update()
        win.scene.update()


# -- Watermark ----------------------------------------------------------------------------------------
def pictures(win):
    return [o for o in win.selected() if o.d["kind"] == "image" and o.d.get("asset")]


def watermark(win):
    objs = pictures(win)
    if not objs:
        win.statusBar().showMessage("Select a picture first", 4000)
        return
    if need_pillow(win):
        return
    dlg = QDialog(win)
    dlg.setWindowTitle("Watermark")
    lay = QFormLayout(dlg)
    cur = imagefx.wm_values(objs[0].d.get("watermark"))
    on = QCheckBox("Write a watermark on this picture")
    on.setChecked(bool(objs[0].d.get("watermark")))
    text = QLineEdit(cur["text"])
    pos = QComboBox()
    for k, label in imagefx.POSITIONS:
        pos.addItem(label, k)
    pos.setCurrentIndex(max(pos.findData(cur["pos"]), 0))
    size = QSpinBox()
    size.setRange(1, 40)
    size.setValue(cur["size"])
    size.setSuffix(" % of the width")
    opac = QSpinBox()
    opac.setRange(5, 100)
    opac.setValue(cur["opacity"])
    opac.setSuffix(" %")
    col = ColorButton(cur["color"], lambda: None)
    shadow = QCheckBox("Soft shadow behind the words")
    shadow.setChecked(cur["shadow"])
    lay.addRow(on)
    lay.addRow("Words (%year%, %sitename% work)", text)
    lay.addRow("Place", pos)
    lay.addRow("Size", size)
    lay.addRow("Strength", opac)
    lay.addRow("Colour", col)
    lay.addRow(shadow)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addRow(bb)
    if dlg.exec_() != QDialog.Accepted:
        return
    for o in objs:
        if on.isChecked() and text.text().strip():
            o.d["watermark"] = dict(text=text.text(), pos=pos.currentData(), size=size.value(),
                                    color=col.colour, opacity=opac.value(), shadow=shadow.isChecked())
        else:
            o.d.pop("watermark", None)
        o.update()
    win.scene.update()
    win.commit_if_changed("Watermark")


# -- Transparent colour ----------------------------------------------------------------------------
class PickLabel(QLabel):
    def __init__(self, on_pick):
        super().__init__()
        self.on_pick, self.src = on_pick, None
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, e):
        if self.src is not None and not self.src.isNull():
            x = int(e.x() * self.src.width() / max(self.width(), 1))
            y = int(e.y() * self.src.height() / max(self.height(), 1))
            self.on_pick(QColor(self.src.pixel(min(x, self.src.width() - 1), min(y, self.src.height() - 1))))


def transparent_colour(win):
    objs = pictures(win)
    if not objs:
        win.statusBar().showMessage("Select a picture first", 4000)
        return
    if need_pillow(win):
        return
    d = objs[0].d
    src = QImage()
    src.loadFromData(win.doc.asset_bytes(d["asset"]))
    if src.isNull():
        return
    src = src.scaledToWidth(min(src.width(), 420), Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
    dlg = QDialog(win)
    dlg.setWindowTitle("Picture transparency")
    lay = QVBoxLayout(dlg)
    cur = dict(imagefx.TR_DEFAULT, **(d.get("transp") or {}))
    on = QCheckBox("Make one colour transparent")
    on.setChecked(bool(d.get("transp")))
    lay.addWidget(QLabel("Click the picture to choose the colour that should disappear."))
    prev = PickLabel(lambda c: col.set(c.name()))
    prev.src = src
    prev.setFixedSize(src.width(), src.height())
    form = QFormLayout()
    col = ColorButton(cur["color"], lambda: refresh())
    tol = slider(0, 80, cur["tol"], lambda: refresh())
    soft = slider(0, 40, cur["soft"], lambda: refresh())
    form.addRow("Colour", col)
    form.addRow("How close", tol)
    form.addRow("Soft edge", soft)

    def refresh():
        base = QImage(src.size(), QImage.Format_RGBA8888)
        p = QPainter(base)
        for y in range(0, src.height(), 12):
            for x in range(0, src.width(), 12):
                p.fillRect(x, y, 12, 12, QColor("#ccc" if (x // 12 + y // 12) % 2 else "#fff"))
        out = imagefx.to_qimage(imagefx.colour_key(imagefx.to_pil(src), col.colour, tol.value(), soft.value()))
        p.drawImage(0, 0, out)
        p.end()
        prev.setPixmap(QPixmap.fromImage(base))

    refresh()
    lay.addWidget(on)
    lay.addWidget(prev)
    lay.addLayout(form)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    if dlg.exec_() != QDialog.Accepted:
        return
    for o in objs:
        if on.isChecked():
            o.d["transp"] = dict(color=col.colour, tol=tol.value(), soft=soft.value())
        else:
            o.d.pop("transp", None)
        o.update()
    win.scene.update()
    win.commit_if_changed("Picture transparency")


# -- Crop to shape ----------------------------------------------------------------------------------
def crop_shape(win):
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QIcon, QPen
    from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout
    from . import shapes
    objs = pictures(win)
    sel_shapes = [o.d for o in win.selected() if o.d["kind"] == "shape"]
    if not objs:
        win.statusBar().showMessage("Select a picture first (and, to use your own outline, a drawn shape too)", 6000)
        return
    dlg = QDialog(win)
    dlg.setWindowTitle("Crop to shape")
    dlg.resize(520, 420)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Choose the outline the picture should be cut to."))
    lst = QListWidget()
    lst.setViewMode(QListWidget.IconMode)
    lst.setIconSize(QSize(64, 64))
    lst.setGridSize(QSize(100, 96))
    lst.setResizeMode(QListWidget.Adjust)
    lst.setMovement(QListWidget.Static)

    def icon(nodes, closed=True):
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#1f3a5f"), 1.5))
        p.setBrush(QColor("#9ec5f5"))
        p.drawPath(shapes.qpath(nodes, closed, 56, 56).translated(4, 4))
        p.end()
        return QIcon(pm)

    none = QListWidgetItem(icon(shapes.preset_nodes("rect")), "No crop")
    none.setData(Qt.UserRole, "")
    lst.addItem(none)
    for key, (label, fn) in shapes.PRESETS.items():
        it = QListWidgetItem(icon(fn()), label)
        it.setData(Qt.UserRole, key)
        lst.addItem(it)
    if sel_shapes:
        sd = sel_shapes[0]
        from .extras import shape_nodes_of
        it = QListWidgetItem(icon(shape_nodes_of(sd), sd.get("closed", True)), "Selected shape")
        it.setData(Qt.UserRole, "@custom")
        lst.addItem(it)
    cur = objs[0].d.get("cropshape")
    for i in range(lst.count()):
        if lst.item(i).data(Qt.UserRole) == (cur if isinstance(cur, str) else ""):
            lst.setCurrentRow(i)
    lay.addWidget(lst)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    lst.itemDoubleClicked.connect(lambda _i: dlg.accept())
    if dlg.exec_() != QDialog.Accepted or lst.currentItem() is None:
        return
    choice = lst.currentItem().data(Qt.UserRole)
    for o in objs:
        if choice == "":
            o.d.pop("cropshape", None)
        elif choice == "@custom":
            o.d["cropshape"] = dict(nodes=copy.deepcopy(sel_shapes[0]["nodes"]), closed=sel_shapes[0].get("closed", True))
        else:
            o.d["cropshape"] = choice
        o.update()
    win.scene.update()
    win.commit_if_changed("Crop to shape")
