"""Side panels in the WebPlus arrangement: Colour, Transform and Assets, plus
the User Details and Options dialogs."""
from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QImage, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QColorDialog, QDialog, QDialogButtonBox,
                             QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                             QListView, QListWidget, QListWidgetItem,
                             QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

TARGETS = [("Fill", "fill"), ("Line", "stroke"), ("Text", "color")]


def swatch(color, size=18):
    pm = QPixmap(size, size)
    pm.fill(QColor(color) if color else QColor("#ffffff"))
    return QIcon(pm)


class Spectrum(QWidget):
    """Hue across, light-to-dark down: click or drag to choose a colour."""
    picked = pyqtSignal(str, bool)      # colour, final (mouse released)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(90)
        self.setMinimumWidth(100)
        self.setCursor(Qt.CrossCursor)
        self._img = None

    def colour_at(self, x, y):
        w, h = max(self.width() - 1, 1), max(self.height() - 1, 1)
        hue = int(359 * min(max(x, 0), w) / w)
        t = min(max(y, 0), h) / h
        if t < 0.5:
            return QColor.fromHsv(hue, int(255 * t * 2), 255)
        return QColor.fromHsv(hue, 255, int(255 * (1 - (t - 0.5) * 2)))

    def paintEvent(self, e):
        from PyQt5.QtGui import QImage, QPainter
        if self._img is None or self._img.size() != self.size():
            img = QImage(self.size(), QImage.Format_RGB32)
            for y in range(img.height()):
                for x in range(0, img.width()):
                    img.setPixel(x, y, self.colour_at(x, y).rgb())
            self._img = img
        QPainter(self).drawImage(0, 0, self._img)

    def _pick(self, e, final):
        self.picked.emit(self.colour_at(e.x(), e.y()).name(), final)

    def mousePressEvent(self, e):
        self._pick(e, False)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._pick(e, False)

    def mouseReleaseEvent(self, e):
        self._pick(e, True)


class ColourPanel(QWidget):
    """Fill / line / text colour of the selection: spectrum, RGB sliders and the
    scheme swatches."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.target = "fill"
        self.busy = False
        self.setStyleSheet("QPushButton{padding:3px 4px}QSpinBox{min-width:40px}")
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        row = QHBoxLayout()
        self.target_btns = {}
        for label, key in TARGETS:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setChecked(key == "fill")
            b.clicked.connect(lambda _=False, k=key: self.set_target(k))
            self.target_btns[key] = b
            row.addWidget(b)
        v.addLayout(row)
        self.spectrum = Spectrum()
        self.spectrum.picked.connect(self.spectrum_picked)
        v.addWidget(self.spectrum)
        self.sliders = {}
        grid = QGridLayout()
        for i, (ch, col) in enumerate((("R", "#d33"), ("G", "#3a3"), ("B", "#33d"))):
            lab = QLabel(ch)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 255)
            sp = QSpinBox()
            sp.setRange(0, 255)
            sl.valueChanged.connect(sp.setValue)
            sp.valueChanged.connect(sl.setValue)
            sl.valueChanged.connect(lambda _v: self.rgb_changed(False))
            sl.sliderReleased.connect(lambda: self.rgb_changed(True))
            sp.editingFinished.connect(lambda: self.rgb_changed(True))
            grid.addWidget(lab, i, 0)
            grid.addWidget(sl, i, 1)
            grid.addWidget(sp, i, 2)
            self.sliders[ch] = (sl, sp)
        v.addLayout(grid)
        self.hex = QLabel("")
        v.addWidget(self.hex)
        self.grid = QGridLayout()
        self.grid.setSpacing(3)
        v.addLayout(self.grid)
        row = QHBoxLayout()
        pick = QPushButton("Pick...")
        pick.setToolTip("Pick any colour")
        pick.clicked.connect(self.pick)
        none = QPushButton("None")
        none.setToolTip("No colour")
        none.clicked.connect(lambda: self.apply(""))
        row.addWidget(pick)
        row.addWidget(none)
        v.addLayout(row)
        v.addStretch(1)
        self.swatches = []
        self.build_swatches()

    def build_swatches(self):
        for b in self.swatches:
            b.deleteLater()
        self.swatches = []
        for i, c in enumerate(self.win.doc.scheme):
            b = QPushButton()
            b.setMinimumSize(14, 22)
            b.setMaximumHeight(26)
            from PyQt5.QtWidgets import QSizePolicy
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setStyleSheet("background:%s;border:1px solid #777" % c)
            b.setToolTip("%d: %s" % (i + 1, c))
            b.clicked.connect(lambda _=False, c=c: self.apply(c))
            self.grid.addWidget(b, i // 6, i % 6)
            self.swatches.append(b)

    def set_target(self, key):
        self.target = key
        self.refresh()

    def apply(self, color, commit=True):
        self.win.set_prop(self.target, color, commit=commit)
        if commit:
            self.win.props.refresh()

    def spectrum_picked(self, color, final):
        self.apply(color, commit=final)
        if final:
            self.win.props.refresh()

    def rgb_changed(self, final):
        if self.busy or not self.win.selected():
            return
        c = QColor(self.sliders["R"][0].value(), self.sliders["G"][0].value(),
                   self.sliders["B"][0].value())
        self.apply(c.name(), commit=final)
        self.hex.setText(c.name())

    def pick(self):
        c = QColorDialog.getColor(QColor(self.hex.text() or "#ffffff"), self, "Colour")
        if c.isValid():
            self.apply(c.name())

    def refresh(self):
        colours = [c for c in self.win.doc.scheme]
        if [b.toolTip().split(": ")[1] for b in self.swatches] != colours:
            self.build_swatches()
        objs = self.win.selected()
        cur = objs[0].d.get(self.target, "") if objs else ""
        self.hex.setText(cur)
        self.busy = True
        try:
            c = QColor(cur) if cur else QColor("#ffffff")
            for ch, val in (("R", c.red()), ("G", c.green()), ("B", c.blue())):
                self.sliders[ch][0].setValue(val)
                self.sliders[ch][1].setValue(val)
        finally:
            self.busy = False
        for key, b in self.target_btns.items():
            val = objs[0].d.get(key, "") if objs else ""
            b.setIcon(swatch(val) if val else QIcon())


def standard_palette():
    """Greys, then twelve hues in four strengths: a ready palette for every site."""
    out = []
    for i in range(8):
        v = int(255 * i / 7)
        out.append(QColor(v, v, v).name())
    for light in (0.26, 0.45, 0.66, 0.84):
        for hue in range(0, 360, 30):
            out.append(QColor.fromHslF(hue / 360.0, 0.78 if light < 0.8 else 0.85, light).name())
    return out


class SwatchesPanel(QWidget):
    """Site colours, a standard palette, and your own saved colours.
    Click one to use it for the selected object (Fill, Line or Text as set in Colour)."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setStyleSheet("QPushButton{padding:3px 4px}")
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.lists = {}
        for key, title, stretch in (("scheme", "Site colours", 1), ("standard", "Standard", 4),
                                    ("mine", "My swatches", 2)):
            lab = QLabel("<b>%s</b>" % title)
            v.addWidget(lab)
            lw = QListWidget()
            lw.setViewMode(QListView.IconMode)
            lw.setIconSize(QSize(24, 24))
            lw.setGridSize(QSize(30, 30))
            lw.setResizeMode(QListView.Adjust)
            lw.setMovement(QListView.Static)
            lw.setSpacing(0)
            lw.setMinimumWidth(40)
            lw.setMinimumHeight(40)
            lw.itemClicked.connect(lambda it: self.use(it.data(Qt.UserRole)))
            v.addWidget(lw, stretch)
            self.lists[key] = lw
        row = QHBoxLayout()
        add = QPushButton("Add...")
        add.setToolTip("Add a colour to your swatches")
        add.clicked.connect(self.add)
        cur = QPushButton("Current")
        cur.setToolTip("Add the selected object's colour")
        cur.clicked.connect(self.add_current)
        row.addWidget(add)
        row.addWidget(cur)
        v.addLayout(row)
        rem = QPushButton("Remove")
        rem.setToolTip("Remove the chosen swatch from My swatches")
        rem.clicked.connect(self.remove)
        v.addWidget(rem)
        self.list = self.lists["mine"]          # kept for older code and tests
        self._sig = None
        self.refresh(force=True)

    def use(self, colour):
        key = self.win.colour_panel.target
        self.win.set_prop(key, colour)
        self.win.props.refresh()

    def add_colour(self, c):
        sw = self.win.doc.swatches
        if c and c.lower() not in [x.lower() for x in sw]:
            sw.append(c)
            self.win.commit_if_changed("Add swatch")
            self.refresh(force=True)

    def add(self):
        c = QColorDialog.getColor(QColor("#ffffff"), self, "New swatch")
        if c.isValid():
            self.add_colour(c.name())

    def add_current(self):
        objs = self.win.selected()
        if objs:
            self.add_colour(objs[0].d.get(self.win.colour_panel.target, ""))

    def remove(self):
        it = self.lists["mine"].currentItem()
        if it:
            c = it.data(Qt.UserRole)
            self.win.doc.swatches[:] = [x for x in self.win.doc.swatches if x != c]
            self.win.commit_if_changed("Remove swatch")
            self.refresh(force=True)

    def fill(self, key, colours):
        lw = self.lists[key]
        lw.clear()
        for c in colours:
            it = QListWidgetItem(swatch(c, 24), "")
            it.setToolTip(c)
            it.setData(Qt.UserRole, c)
            lw.addItem(it)

    def refresh(self, force=False):
        sig = (tuple(self.win.doc.swatches), tuple(self.win.doc.scheme))
        if sig == self._sig and not force:
            return
        self._sig = sig
        self.fill("scheme", self.win.doc.scheme)
        self.fill("standard", standard_palette())
        self.fill("mine", self.win.doc.swatches)


def _hint(text):
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setStyleSheet("color:#5b6675")
    return lab


class TransparencyPanel(QWidget):
    """How see-through the selected object is, plus its shadow and colour fade."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.busy = False
        self.setStyleSheet("QPushButton{padding:3px 6px}")
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("background:#fff6d6;border:1px solid #e3cf86;padding:5px;"
                                  "color:#6b5a14")
        v.addWidget(self.status)

        v.addWidget(QLabel("<b>Opacity</b>"))
        row = QHBoxLayout()
        self.op = QSlider(Qt.Horizontal)
        self.op.setRange(0, 100)
        self.op.setValue(100)
        self.spin = QSpinBox()
        self.spin.setRange(0, 100)
        self.spin.setValue(100)
        self.spin.setSuffix(" %")
        row.addWidget(self.op, 1)
        row.addWidget(self.spin)
        v.addLayout(row)
        ends = QHBoxLayout()
        ends.addWidget(QLabel("Invisible"))
        ends.addStretch(1)
        ends.addWidget(QLabel("Solid"))
        v.addLayout(ends)
        v.addWidget(_hint("100% is solid. Lower numbers let what is behind the object "
                          "show through, down to 0% which cannot be seen."))
        self.op.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.op.setValue)
        self.op.valueChanged.connect(lambda val: self.set("opacity", val, False))
        self.op.sliderReleased.connect(lambda: self.win.commit_if_changed("Opacity"))
        self.spin.editingFinished.connect(lambda: self.win.commit_if_changed("Opacity"))

        v.addWidget(QLabel("<b>Shadow</b>"))
        self.shadow = QCheckBox("Drop shadow behind the object")
        self.shadow.toggled.connect(lambda val: self.set("shadow", val, True))
        v.addWidget(self.shadow)

        v.addWidget(QLabel("<b>Fade to a second colour</b>"))
        v.addWidget(_hint("Blends the object's fill into another colour, from top to bottom."))
        self.second = QPushButton("Choose the second colour...")
        self.second.clicked.connect(self.grad)
        self.none = QPushButton("Remove the fade")
        self.none.clicked.connect(lambda: self.set("fill2", "", True))
        v.addWidget(self.second)
        v.addWidget(self.none)
        self.fade_info = _hint("")
        v.addWidget(self.fade_info)
        v.addStretch(1)
        self.refresh()

    def set(self, key, val, commit):
        if not self.busy:
            self.win.set_prop(key, val, commit=commit)

    def grad(self):
        c = QColorDialog.getColor(QColor("#ffffff"), self, "Second colour")
        if c.isValid():
            self.set("fill2", c.name(), True)
            self.win.props.refresh()

    def refresh(self):
        objs = self.win.selected()
        has = bool(objs)
        for wd in (self.op, self.spin, self.shadow, self.second, self.none):
            wd.setEnabled(has)
        if not has:
            self.status.setText("Nothing is selected. Click an object on the page, then "
                                "change its transparency here.")
            self.status.show()
        elif len(objs) > 1:
            self.status.setText("%d objects selected: changes apply to all of them." % len(objs))
            self.status.show()
        else:
            self.status.hide()
        self.busy = True
        try:
            d = objs[0].d if has else {}
            val = int(d.get("opacity", 100))
            self.op.setValue(val)
            self.spin.setValue(val)
            self.shadow.setChecked(bool(d.get("shadow")))
            f2 = d.get("fill2", "")
            self.fade_info.setText("Fading to %s." % f2 if f2 else "No fade is set.")
            kind_ok = d.get("kind") in ("rect", "ellipse", "text", "button", None)
            self.second.setEnabled(has and kind_ok)
            self.none.setEnabled(has and kind_ok and bool(f2))
        finally:
            self.busy = False


class LinePanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.busy = False
        f = QFormLayout(self)
        f.setRowWrapPolicy(QFormLayout.WrapAllRows)
        f.setContentsMargins(6, 6, 6, 6)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("background:#fff6d6;border:1px solid #e3cf86;padding:5px;"
                                  "color:#6b5a14")
        f.addRow(self.status)
        self.colour = QPushButton("(none)")
        self.colour.clicked.connect(self.pick)
        f.addRow("Line colour", self.colour)
        self.width = QSpinBox()
        self.width.setRange(0, 40)
        self.width.valueChanged.connect(lambda v: self.set("sw", v))
        f.addRow("Width (px)", self.width)
        self.radius = QSpinBox()
        self.radius.setRange(0, 500)
        self.radius.valueChanged.connect(lambda v: self.set("radius", v))
        f.addRow("Corner radius", self.radius)
        from PyQt5.QtWidgets import QComboBox
        self.style = QComboBox()
        self.style.addItems(["solid", "dashed", "dotted"])
        self.style.activated.connect(lambda i: self.set("sstyle", self.style.itemText(i)))
        f.addRow("Style", self.style)

    def set(self, key, val):
        if self.busy:
            return
        for o in self.win.selected():
            if key == "sw" and val and not o.d.get("stroke"):
                o.d["stroke"] = self.win.doc.scheme[1]
        self.win.set_prop(key, val)

    def pick(self):
        c = QColorDialog.getColor(QColor("#333333"), self, "Line colour")
        if c.isValid():
            self.set("stroke", c.name())
            if not any(o.d.get("sw") for o in self.win.selected()):
                self.set("sw", 2)
            self.win.props.refresh()

    def refresh(self):
        objs = self.win.selected()
        self.setEnabled(True)
        for wd in (self.colour, self.width, self.radius, self.style):
            wd.setEnabled(bool(objs))
        self.status.setText("Nothing is selected. Click an object on the page, then set its "
                            "outline here." if not objs else
                            "Outline colour, thickness and corners of the selected object.")
        self.status.setVisible(True)
        self.busy = True
        try:
            if objs:
                d = objs[0].d
                self.colour.setText(d.get("stroke") or "(none)")
                self.width.setValue(int(d.get("sw", 0)))
                self.radius.setValue(int(d.get("radius", 0)))
                self.style.setCurrentText(d.get("sstyle", "solid"))
        finally:
            self.busy = False


class TransformPanel(QWidget):
    """Position, size, turn and opacity in a compact block, like WebPlus's Transform tab:
    X and W side by side, Y and H under them, then rotation and opacity."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.busy = False
        g = QGridLayout(self)
        g.setContentsMargins(6, 4, 6, 4)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(4)
        self.w = {}
        spec = (("x", "X", -5000, 20000, " pix", 0, 0), ("w", "W", 1, 20000, " pix", 0, 2),
                ("y", "Y", -5000, 20000, " pix", 1, 0), ("h", "H", 0, 20000, " pix", 1, 2),
                ("rot", "Turn", -360, 360, "\u00b0", 2, 0), ("opacity", "Opacity", 0, 100, " %", 2, 2))
        for key, label, lo, hi, suffix, row, col in spec:
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setSuffix(suffix)
            s.setButtonSymbols(QSpinBox.NoButtons)       # compact: type the number
            s.setMinimumWidth(48)
            s.setMaximumHeight(24)
            s.valueChanged.connect(lambda v, k=key: self.changed(k, v))
            self.w[key] = s
            lab = QLabel(label)
            lab.setMinimumWidth(10)
            g.addWidget(lab, row, col)
            g.addWidget(s, row, col + 1)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        g.setRowStretch(3, 1)
        self.setToolTip("Select an object to change its position, size, turn and opacity")

    def changed(self, key, val):
        if not self.busy:
            self.win.set_prop(key, val)

    def refresh(self):
        objs = self.win.selected()
        self.setEnabled(bool(objs))
        self.busy = True
        try:
            if objs:
                d = objs[0].d
                for k, s in self.w.items():
                    s.setValue(int(d.get(k, 0 if k != "opacity" else 100)))
        finally:
            self.busy = False


class AssetsPanel(QWidget):
    """The pictures held by the site; double-click one to place it."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        add = QPushButton("Add pictures...")
        add.clicked.connect(self.add)
        row.addWidget(add)
        starter = QPushButton("Picture library...")
        starter.setToolTip("Pictures drawn by WebPlus: backgrounds, textures, banners, icons")
        starter.clicked.connect(self.starter)
        row.addWidget(starter)
        v.addLayout(row)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(QSize(84, 84))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setSpacing(6)
        self.list.itemDoubleClicked.connect(
            lambda it: self.win.insert_asset(it.data(Qt.UserRole)))
        v.addWidget(self.list, 1)
        v.addWidget(QLabel("Double-click a picture to place it."))
        self._sig = None

    def add(self):
        self.win.add_assets()

    def starter(self):
        StarterDialog(self.win).exec_()

    def refresh(self):
        sig = tuple(self.win.doc.used_assets_all())
        if sig == self._sig:
            return
        self._sig = sig
        self.list.clear()
        for aid in sig:
            pm = self.win.pixmap(aid)
            if pm is None or pm.isNull():
                continue
            it = QListWidgetItem(QIcon(pm.scaled(84, 84, Qt.KeepAspectRatio,
                                                 Qt.SmoothTransformation)),
                                 self.win.doc.assets[aid]["name"][:14])
            it.setData(Qt.UserRole, aid)
            self.list.addItem(it)


class StarterDialog(QDialog):
    """The picture library: icons, textures, patterns and the program's own shapes and backgrounds.
    Pick one or several and they go into the Assets panel."""

    GROUPS = ["Icons (Tabler)", "Textures (real surfaces)", "Patterns (Hero Patterns)",
              "Backgrounds", "Banners", "Shapes"]
    SHOW_LIMIT = 240

    def __init__(self, win):
        super().__init__(win)
        from PyQt5.QtWidgets import QComboBox, QLineEdit
        from . import library, starter
        self.win, self.lib, self.starter = win, library, starter
        self.ink, self.bg = "#2b7de9", "#f4f6f9"
        self.setWindowTitle("Picture library")
        self.resize(640, 600)
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Show:"))
        self.group = QComboBox()
        self.group.addItems(self.GROUPS)
        self.group.currentIndexChanged.connect(self.fill)
        top.addWidget(self.group)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search icons (home, arrow, phone...)")
        self.search.textChanged.connect(self.fill)
        top.addWidget(self.search, 1)
        v.addLayout(top)
        row = QHBoxLayout()
        self.ink_btn = QPushButton("Picture colour")
        self.ink_btn.clicked.connect(lambda: self.pick("ink"))
        self.bg_btn = QPushButton("Behind it")
        self.bg_btn.clicked.connect(lambda: self.pick("bg"))
        row.addWidget(self.ink_btn)
        row.addWidget(self.bg_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(QSize(72, 72))
        self.list.setGridSize(QSize(96, 104))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setWordWrap(True)
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.itemDoubleClicked.connect(lambda _: self.add_selected())
        v.addWidget(self.list, 1)
        self.note = QLabel()
        self.note.setWordWrap(True)
        v.addWidget(self.note)
        bb = QDialogButtonBox()
        bb.addButton("Add selected", QDialogButtonBox.AcceptRole).clicked.connect(self.add_selected)
        bb.addButton(QDialogButtonBox.Close).clicked.connect(self.reject)
        v.addWidget(bb)
        self._icons = {}
        self.fill()

    def swatch(self):
        for btn, col in ((self.ink_btn, self.ink), (self.bg_btn, self.bg)):
            btn.setStyleSheet("border-left:14px solid %s" % col)

    def pick(self, which):
        c = QColorDialog.getColor(QColor(self.ink if which == "ink" else self.bg), self)
        if c.isValid():
            setattr(self, which, c.name())
            self._icons = {}
            self.fill()

    def kind(self):
        return self.group.currentIndex()

    def item_icon(self, key):
        kind = self.kind()
        ck = (kind, key, self.ink, self.bg)
        if ck in self._icons:
            return self._icons[ck]
        lib = self.lib
        if kind == 0:
            img = lib.tinted(lib.path_for("icon", key), self.ink)
        elif kind == 1:
            img = QImage(lib.path_for("texture", key))
        elif kind == 2:
            img = lib.tinted(lib.path_for("pattern", key), self.ink, self.bg)
        else:
            img = self.starter.make(*key)
        pm = QPixmap.fromImage(img).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._icons[ck] = QIcon(pm)
        return self._icons[ck]

    def fill(self, _=None):
        kind = self.kind()
        self.swatch()
        self.search.setVisible(kind == 0)
        self.ink_btn.setVisible(kind in (0, 2))
        self.bg_btn.setVisible(kind == 2)
        self.list.clear()
        lib = self.lib
        entries, msg = [], ""
        if kind == 0:
            names = lib.icon_names(self.search.text())
            entries = [(n, n.replace("-", " ")) for n in names[:self.SHOW_LIMIT]]
            msg = ("%d icons match%s. Icons by Tabler (MIT licence)."
                   % (len(names), "; showing the first %d - type to narrow it down"
                      % self.SHOW_LIMIT if len(names) > self.SHOW_LIMIT else ""))
        elif kind == 1:
            entries = [(k, name) for k, name, _s in lib.textures()]
            msg = "Real surfaces from ambientCG and Poly Haven. Both are CC0: free for anything, no credit needed."
        elif kind == 2:
            entries = [(n, n) for n in lib.patterns()]
            msg = ("Patterns by Steve Schoger, heropatterns.com (CC BY 4.0, credit kept in the "
                   "library folder). Pick the colour and what is behind it.")
        else:
            grp = {3: "Backgrounds", 4: "Banners", 5: "Icons"}[kind]
            entries = [((g, n), n) for g, n in self.starter.names() if g == grp]
            msg = "Drawn by the program itself. Nothing to license."
        for key, label in entries:
            it = QListWidgetItem(self.item_icon(key), label)
            it.setData(Qt.UserRole, key)
            self.list.addItem(it)
        self.note.setText(msg)

    def add_selected(self):
        items = self.list.selectedItems()
        kind, lib = self.kind(), self.lib
        for it in items:
            key = it.data(Qt.UserRole)
            label = it.text()
            if kind == 0:
                data = lib.png_bytes(lib.tinted(lib.path_for("icon", key), self.ink))
                self.win.doc.add_asset_bytes(key + ".png", data)
            elif kind == 1:
                with open(lib.path_for("texture", key), "rb") as f:
                    self.win.doc.add_asset_bytes(key + ".jpg", f.read())
            elif kind == 2:
                data = lib.png_bytes(lib.tinted(lib.path_for("pattern", key), self.ink, self.bg))
                self.win.doc.add_asset_bytes("pattern-" + key + ".png", data)
            else:
                self.win.doc.add_asset_bytes(label + ".png", self.starter.png_bytes(*key))
        if items:
            self.win.side_refresh()
            self.win.statusBar().showMessage("Added %d picture(s) to Assets" % len(items), 4000)


USER_FIELDS = [("name", "Your name"), ("company", "Company"), ("job", "Job title"),
               ("address1", "Address 1"), ("address2", "Address 2"),
               ("address3", "Town / city"), ("address4", "State / zip"),
               ("phone", "Phone"), ("mobile", "Mobile"), ("email", "Email"),
               ("web", "Web address"), ("motto", "Motto")]


class UserDetailsDialog(QDialog):
    """Details that can be dropped into text with tokens like %companyname%."""

    def __init__(self, parent, user):
        super().__init__(parent)
        from PyQt5.QtWidgets import QLineEdit
        self.setWindowTitle("User details")
        f = QFormLayout(self)
        self.edits = {}
        for key, label in USER_FIELDS:
            e = QLineEdit(user.get(key, ""))
            self.edits[key] = e
            f.addRow(label, e)
        f.addRow(QLabel("Use %companyname%, %companyemail%, %companyphone% ... in any text."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def values(self):
        return {k: e.text().strip() for k, e in self.edits.items()}


class OptionsDialog(QDialog):
    def __init__(self, parent, grid, snap, ui_pt):
        super().__init__(parent)
        self.setWindowTitle("Options")
        f = QFormLayout(self)
        self.grid = QCheckBox("Show the grid on the page")
        self.grid.setChecked(grid)
        self.snap = QCheckBox("Snap objects to the grid and guides")
        self.snap.setChecked(snap)
        self.pt = QSpinBox()
        self.pt.setRange(7, 16)
        self.pt.setValue(int(ui_pt))
        f.addRow(self.grid)
        f.addRow(self.snap)
        f.addRow("Interface text size (pt)", self.pt)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


# ---------------------------------------------------------------- left tabs
TEXT_PRESETS = [
    ("Heading 1", dict(size=40, bold=True, italic=False, ci=2)),
    ("Heading 2", dict(size=30, bold=True, italic=False, ci=2)),
    ("Heading 3", dict(size=22, bold=True, italic=False, ci=2)),
    ("Subtitle", dict(size=20, bold=False, italic=True, ci=9)),
    ("Body", dict(size=16, bold=False, italic=False, ci=1)),
    ("Body Small", dict(size=13, bold=False, italic=False, ci=1)),
    ("Emphasis", dict(size=16, bold=False, italic=True, ci=1)),
    ("Strong", dict(size=16, bold=True, italic=False, ci=1)),
    ("Strong Emphasis", dict(size=16, bold=True, italic=True, ci=1)),
    ("Quote", dict(size=20, bold=False, italic=True, ci=3)),
    ("Caption", dict(size=12, bold=False, italic=False, ci=9)),
    ("Code", dict(size=14, bold=False, italic=False, ci=1, font="Monospace")),
    ("Light on dark", dict(size=18, bold=False, italic=False, ci=0)),
]


class TextStylesPanel(QWidget):
    """Ready-made text formats plus the styles you saved. Double-click applies."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.use)
        v.addWidget(self.list, 1)
        hint = QLabel("Double-click to apply to the selected text.")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self._sig = None
        self.refresh()

    def refresh(self):
        from PyQt5.QtGui import QFont
        sig = tuple(sorted(self.win.doc.styles))
        if sig == self._sig:
            return
        self._sig = sig
        self.list.clear()
        for name, props in TEXT_PRESETS:
            it = QListWidgetItem(name)
            f = QFont(props.get("font", "Sans Serif"))
            f.setPixelSize(min(props["size"], 26))
            f.setBold(props["bold"])
            f.setItalic(props["italic"])
            it.setFont(f)
            it.setData(Qt.UserRole, ("preset", name))
            self.list.addItem(it)
        for name in sig:
            it = QListWidgetItem(name + "   (saved)")
            it.setData(Qt.UserRole, ("saved", name))
            self.list.addItem(it)

    def use(self, item):
        kind, name = item.data(Qt.UserRole)
        if kind == "saved":
            self.win.use_style(name)
        else:
            self.win.apply_text_style(dict(TEXT_PRESETS)[name])


class FontsPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        from PyQt5.QtGui import QFont, QFontDatabase
        from PyQt5.QtWidgets import QLineEdit
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search fonts")
        self.search.textChanged.connect(self.filter)
        v.addWidget(self.search)
        self.list = QListWidget()
        for fam in sorted(QFontDatabase().families()):
            it = QListWidgetItem(fam)
            f = QFont(fam)
            f.setPixelSize(16)
            it.setFont(f)
            self.list.addItem(it)
        self.list.itemClicked.connect(lambda it: self.win.set_prop("font", it.text()))
        v.addWidget(self.list, 1)
        v.addWidget(QLabel("Click a font to apply it to the selection."))

    def filter(self, text):
        t = text.lower()
        for i in range(self.list.count()):
            self.list.item(i).setHidden(t not in self.list.item(i).text().lower())

    def refresh(self):
        pass


class QuickBuildPanel(QWidget):
    """Ready-made blocks shown as little pictures. Double-click one to add it."""

    def __init__(self, win):
        super().__init__()
        from . import startup, templates
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(QSize(132, 84))
        self.list.setGridSize(QSize(150, 120))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setWordWrap(True)
        self.list.setSpacing(2)
        self.list.setMinimumWidth(60)
        for name in templates.BLOCKS:
            items, h = templates.block(name, 960)
            width = max([i["x"] + i["w"] for i in items] + [10])
            height = max([i["y"] + i["h"] for i in items] + [10])
            # a tile with the same shape as the block, centred on a soft background
            tw, th = 132, 84
            scale = min((tw - 12) / float(width), (th - 12) / float(height))
            inner_w, inner_h = max(int(width * scale), 8), max(int(height * scale), 8)
            tile = QPixmap(tw, th)
            tile.fill(QColor("#eef1f5"))
            pic = startup.thumbnail([dict(items=items)], width, inner_w, inner_h)
            from PyQt5.QtGui import QPainter
            pt = QPainter(tile)
            pt.drawPixmap((tw - inner_w) // 2, (th - inner_h) // 2, pic)
            pt.setPen(QColor("#c5ccd6"))
            pt.drawRect(0, 0, tw - 1, th - 1)
            pt.end()
            it = QListWidgetItem(QIcon(tile), name)
            it.setToolTip("Double-click to add \"%s\" to the page" % name)
            it.setTextAlignment(Qt.AlignHCenter)
            self.list.addItem(it)
        self.list.itemDoubleClicked.connect(lambda it: self.win.insert_block(it.text()))
        v.addWidget(self.list, 1)
        v.addWidget(QLabel("Double-click a picture to add that block to the page."))

    def refresh(self):
        pass


class CompositionsPanel(QWidget):
    """Your saved groups of objects. Double-click one to put it on the page."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        b = QPushButton("Save selection...")
        b.clicked.connect(win.save_composition)
        d = QPushButton("Delete")
        d.clicked.connect(self.delete)
        row.addWidget(b)
        row.addWidget(d)
        v.addLayout(row)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(QSize(130, 90))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setSpacing(6)
        self.list.itemDoubleClicked.connect(
            lambda it: self.win.insert_composition(it.data(Qt.UserRole)))
        v.addWidget(self.list, 1)
        v.addWidget(QLabel("Select objects, then Save selection. Compositions are kept for "
                           "every site you make."))
        self._sig = None
        self.refresh(force=True)

    def delete(self):
        from . import compositions
        it = self.list.currentItem()
        if it is not None:
            compositions.delete(it.data(Qt.UserRole))
            self.refresh(force=True)

    def refresh(self, force=False):
        from . import compositions, startup
        found = compositions.list_all()
        sig = tuple(p for _n, p in found)
        if sig == self._sig and not force:
            return
        self._sig = sig
        self.list.clear()
        for name, path in found:
            try:
                comp = compositions.load(path)
                items = comp["items"]
                width = max([i["x"] + i["w"] for i in items] + [10])
                pm = startup.thumbnail([dict(items=items)], width, 130, 90)
                it = QListWidgetItem(QIcon(pm), name)
            except Exception:  # noqa: BLE001 - a damaged file should not break the panel
                it = QListWidgetItem(name)
            it.setData(Qt.UserRole, path)
            self.list.addItem(it)
