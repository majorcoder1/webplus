"""PhotoLab: touch up a picture - crop, turn, light and colour, sharpen, soften, vignette."""
import io
import os

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

from . import imagefx

DEFAULTS = dict(rotate=0, flipx=False, flipy=False, crop=None, brightness=0, contrast=0, saturation=0,
                sharpness=0, warmth=0, hue=0, vignette=0, blur=0, gray=False, sepia=False, auto=False)

ADJUST = [("brightness", "Brightness", -100, 100), ("contrast", "Contrast", -100, 100),
          ("saturation", "Colour strength", -100, 100), ("warmth", "Warm / cool", -100, 100),
          ("hue", "Colour shift", -180, 180), ("sharpness", "Sharpen (+) or soften (-)", -100, 100),
          ("vignette", "Dark edges (vignette)", 0, 100), ("blur", "Blur", 0, 20)]
RATIOS = [("Free", 0), ("Square", 1.0), ("4 : 3", 4 / 3.0), ("3 : 2", 1.5), ("16 : 9", 16 / 9.0),
          ("3 : 4 (tall)", 3 / 4.0), ("2 : 3 (tall)", 2 / 3.0)]


def process(img, p, max_side=0):
    """The edited picture (Pillow RGBA) for these settings. max_side > 0 makes a small preview."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
    img = img.convert("RGBA")
    if max_side and max(img.size) > max_side:
        k = max_side / float(max(img.size))
        img = img.resize((max(int(img.width * k), 1), max(int(img.height * k), 1)), Image.LANCZOS)
    if p["rotate"]:
        img = img.rotate(-p["rotate"], expand=True)
    if p["flipx"]:
        img = ImageOps.mirror(img)
    if p["flipy"]:
        img = ImageOps.flip(img)
    if p["crop"]:
        x0, y0, x1, y1 = p["crop"]
        box = (int(round(x0 * img.width)), int(round(y0 * img.height)),
               max(int(round(x1 * img.width)), int(round(x0 * img.width)) + 1),
               max(int(round(y1 * img.height)), int(round(y0 * img.height)) + 1))
        img = img.crop(box)
    r, g, b, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))
    if p["auto"]:
        rgb = ImageOps.autocontrast(rgb, cutoff=1)
    if p["brightness"]:
        rgb = ImageEnhance.Brightness(rgb).enhance(1 + p["brightness"] / 100.0)
    if p["contrast"]:
        rgb = ImageEnhance.Contrast(rgb).enhance(1 + p["contrast"] / 100.0)
    if p["saturation"]:
        rgb = ImageEnhance.Color(rgb).enhance(1 + p["saturation"] / 100.0)
    if p["warmth"]:
        k = p["warmth"] / 100.0 * 0.25
        rr, gg, bb = rgb.split()
        rr = rr.point(lambda v: max(0, min(255, int(v * (1 + k)))))
        bb = bb.point(lambda v: max(0, min(255, int(v * (1 - k)))))
        rgb = Image.merge("RGB", (rr, gg, bb))
    if p["hue"]:
        h, s, v = rgb.convert("HSV").split()
        shift = int(round(p["hue"] * 255 / 360.0))
        h = h.point(lambda x: (x + shift) % 256)
        rgb = Image.merge("HSV", (h, s, v)).convert("RGB")
    if p["sharpness"]:
        rgb = ImageEnhance.Sharpness(rgb).enhance(1 + p["sharpness"] / 25.0)
    if p["blur"]:
        rgb = rgb.filter(ImageFilter.GaussianBlur(p["blur"]))
    if p["gray"]:
        rgb = rgb.convert("L").convert("RGB")
    if p["sepia"]:
        rgb = rgb.convert("RGB", (0.393, 0.769, 0.189, 0, 0.349, 0.686, 0.168, 0, 0.272, 0.534, 0.131, 0))
    if p["vignette"]:
        w, h = rgb.size
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).ellipse((-w * 0.18, -h * 0.18, w * 1.18, h * 1.18), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(max(w, h) * 0.18))
        dark = ImageEnhance.Brightness(rgb).enhance(1 - 0.85 * p["vignette"] / 100.0)
        rgb = Image.composite(rgb, dark, mask)
    return Image.merge("RGBA", (*rgb.split(), a))


def to_qpixmap(pil):
    return QPixmap.fromImage(imagefx.to_qimage(pil))


class CropLabel(QWidget):
    """Shows the picture and lets you drag a crop rectangle over it."""

    def __init__(self, on_change):
        super().__init__()
        self.pm = None
        self.crop = None            # normalised x0, y0, x1, y1
        self.ratio = 0.0            # width / height of the picture shape wanted; 0 = free
        self.on_change = on_change
        self.start = None
        self.setMinimumSize(460, 340)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(False)

    def set_pixmap(self, pm):
        self.pm = pm
        self.update()

    def area(self):
        if self.pm is None or self.pm.isNull():
            return QRectF()
        k = min((self.width() - 8) / self.pm.width(), (self.height() - 8) / self.pm.height())
        w, h = self.pm.width() * k, self.pm.height() * k
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def norm(self, pos):
        a = self.area()
        return (min(max((pos.x() - a.left()) / max(a.width(), 1), 0), 1),
                min(max((pos.y() - a.top()) / max(a.height(), 1), 0), 1))

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2b2f36"))
        a = self.area()
        if a.isEmpty():
            return
        for y in range(int(a.top()), int(a.bottom()), 12):          # a chequerboard shows see-through areas
            for x in range(int(a.left()), int(a.right()), 12):
                p.fillRect(QRectF(x, y, 12, 12).intersected(a),
                           QColor("#cfcfcf" if ((x - int(a.left())) // 12 + (y - int(a.top())) // 12) % 2 else "#ffffff"))
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(a, self.pm, QRectF(self.pm.rect()))
        if self.crop:
            x0, y0, x1, y1 = self.crop
            c = QRectF(a.left() + x0 * a.width(), a.top() + y0 * a.height(),
                       (x1 - x0) * a.width(), (y1 - y0) * a.height())
            shade = QColor(0, 0, 0, 140)
            for r in (QRectF(a.left(), a.top(), a.width(), c.top() - a.top()),
                      QRectF(a.left(), c.bottom(), a.width(), a.bottom() - c.bottom()),
                      QRectF(a.left(), c.top(), c.left() - a.left(), c.height()),
                      QRectF(c.right(), c.top(), a.right() - c.right(), c.height())):
                p.fillRect(r, shade)
            p.setPen(QPen(QColor("#ffffff"), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRect(c)
            p.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.DashLine))
            for i in (1, 2):                                          # rule-of-thirds guides
                p.drawLine(QPointF(c.left() + c.width() * i / 3, c.top()), QPointF(c.left() + c.width() * i / 3, c.bottom()))
                p.drawLine(QPointF(c.left(), c.top() + c.height() * i / 3), QPointF(c.right(), c.top() + c.height() * i / 3))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.area().isEmpty():
            self.start = self.norm(e.pos())

    def mouseMoveEvent(self, e):
        if self.start is None:
            return
        x0, y0 = self.start
        x1, y1 = self.norm(e.pos())
        if self.ratio and self.pm:
            # keep the shape: the box is as wide as the mouse went, and as tall as the ratio allows
            pw, ph = self.pm.width(), self.pm.height()
            dx = abs(x1 - x0)
            dy = dx * pw / (self.ratio * ph)
            y1 = y0 + (dy if y1 >= y0 else -dy)
            if not 0 <= y1 <= 1:
                y1 = 0.0 if y1 < 0 else 1.0
                dy = abs(y1 - y0)
                dx = dy * self.ratio * ph / pw
                x1 = x0 + (dx if x1 >= x0 else -dx)
        self.crop = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self.update()

    def mouseReleaseEvent(self, e):
        if self.start is None:
            return
        self.start = None
        if self.crop and (self.crop[2] - self.crop[0] < 0.02 or self.crop[3] - self.crop[1] < 0.02):
            self.crop = None
        self.update()
        self.on_change()


class PhotoLab(QDialog):
    def __init__(self, win, d):
        super().__init__(win)
        self.win, self.d = win, d
        self.setWindowTitle("PhotoLab")
        self.resize(900, 620)
        from PIL import Image
        raw = win.doc.asset_bytes(d["asset"])
        self.src = Image.open(io.BytesIO(raw))
        self.src.load()
        self.name = win.doc.assets[d["asset"]]["name"]
        self.p = dict(DEFAULTS)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self.view = CropLabel(self.changed_crop)
        left.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Crop: drag on the picture."))
        self.ratio = QComboBox()
        for label, k in RATIOS:
            self.ratio.addItem(label, k)
        self.ratio.addItem("Match the frame", -1)
        self.ratio.currentIndexChanged.connect(self.set_ratio)
        row.addWidget(self.ratio)
        b = QPushButton("Clear crop")
        b.clicked.connect(self.clear_crop)
        row.addWidget(b)
        left.addLayout(row)
        self.info = QLabel("")
        left.addWidget(self.info)
        lay.addLayout(left, 3)
        side = QVBoxLayout()
        turn = QHBoxLayout()
        for label, fn in (("Turn left", lambda: self.turn(-90)), ("Turn right", lambda: self.turn(90)),
                          ("Flip across", lambda: self.flip("flipx")), ("Flip down", lambda: self.flip("flipy"))):
            b = QPushButton(label)
            b.clicked.connect(fn)
            turn.addWidget(b)
        side.addLayout(turn)
        form = QFormLayout()
        self.sliders = {}
        for key, label, lo, hi in ADJUST:
            s = QSlider(Qt.Horizontal)
            s.setRange(lo, hi)
            s.setValue(0)
            s.valueChanged.connect(lambda v, k=key: self.set(k, v))
            self.sliders[key] = s
            form.addRow(label, s)
        side.addLayout(form)
        self.checks = {}
        for key, label in (("auto", "Auto-fix the light (stretch the contrast)"),
                           ("gray", "Black and white"), ("sepia", "Old-photo brown (sepia)")):
            c = QCheckBox(label)
            c.toggled.connect(lambda v, k=key: self.set(k, v))
            self.checks[key] = c
            side.addWidget(c)
        self.fit_frame = QCheckBox("Resize the frame to the new shape after cropping")
        self.fit_frame.setChecked(True)
        side.addWidget(self.fit_frame)
        reset = QPushButton("Undo all changes")
        reset.clicked.connect(self.reset)
        side.addWidget(reset)
        side.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Save changes")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        side.addWidget(bb)
        lay.addLayout(side, 2)
        self.refresh()

    # -- settings
    def set(self, k, v):
        self.p[k] = v
        self.refresh()

    def turn(self, deg):
        self.p["rotate"] = (self.p["rotate"] + deg) % 360
        self.p["crop"] = self.view.crop = None
        self.refresh()

    def flip(self, k):
        self.p[k] = not self.p[k]
        self.p["crop"] = self.view.crop = None
        self.refresh()

    def set_ratio(self):
        k = self.ratio.currentData()
        if k == -1:
            k = self.d["w"] / max(self.d["h"], 1)
        self.view.ratio = k or 0.0

    def clear_crop(self):
        self.p["crop"] = self.view.crop = None
        self.refresh()

    def changed_crop(self):
        self.p["crop"] = self.view.crop
        self.refresh()

    def reset(self):
        self.p = dict(DEFAULTS)
        self.view.crop = None
        for s in self.sliders.values():
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)
        for c in self.checks.values():
            c.blockSignals(True)
            c.setChecked(False)
            c.blockSignals(False)
        self.refresh()

    def refresh(self):
        # the preview shows the whole picture (turned and edited) with the crop box drawn on top
        q = dict(self.p, crop=None)
        self.view.set_pixmap(to_qpixmap(process(self.src, q, 900)))
        w, h = self.src.size
        if self.p["rotate"] in (90, 270):
            w, h = h, w
        if self.p["crop"]:
            x0, y0, x1, y1 = self.p["crop"]
            w, h = int((x1 - x0) * w), int((y1 - y0) * h)
        self.info.setText("Result: %d x %d pixels" % (w, h))

    # -- result
    def result_bytes(self):
        out = process(self.src, self.p)
        buf = io.BytesIO()
        jpeg = os.path.splitext(self.name)[1].lower() in (".jpg", ".jpeg") and out.getextrema()[3][0] == 255
        if jpeg:
            out.convert("RGB").save(buf, "JPEG", quality=92)
        else:
            out.save(buf, "PNG")
        stem = os.path.splitext(self.name)[0]
        return "%s-edited.%s" % (stem, "jpg" if jpeg else "png"), buf.getvalue(), out.size

    def apply(self):
        name, data, size = self.result_bytes()
        aid = self.win.doc.add_asset_bytes(name, data)
        self.d["asset"] = aid
        if self.p["crop"] and self.fit_frame.isChecked():
            self.d["h"] = max(round(self.d["w"] * size[1] / float(size[0])), 8)
        return aid


def edit_photo(win):
    objs = [o for o in win.selected() if o.d["kind"] == "image" and o.d.get("asset")]
    if not objs:
        win.statusBar().showMessage("Select a picture first", 4000)
        return
    if not imagefx.have_pil():
        QMessageBox.information(win, "WebPlus", "PhotoLab needs the Pillow picture library, which is not installed.")
        return
    d = objs[0].d
    if win.doc.assets[d["asset"]]["name"].lower().endswith((".gif", ".svg")):
        QMessageBox.information(win, "WebPlus", "PhotoLab edits photos (JPEG, PNG, WebP, BMP), not GIF or SVG pictures.")
        return
    try:
        dlg = PhotoLab(win, d)
    except Exception as ex:             # a picture Pillow cannot read
        QMessageBox.warning(win, "WebPlus", "That picture could not be opened for editing:\n%s" % ex)
        return
    if dlg.exec_() == QDialog.Accepted:
        dlg.apply()
        win._pix.pop(d["asset"], None)
        win.reload({d["id"]})
        win.commit_if_changed("Edit photo")
