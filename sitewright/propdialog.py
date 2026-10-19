"""The Edit Properties dialog: a pop-up with tabs for the chosen object (right-click, then
Edit properties, or Properties > Object properties). Changes are made on a copy and only
applied when you press OK, as one Undo step."""
import copy

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                             QFontComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from . import tablecore as tc
from .model import KIND_NAMES

ALIGNS = ["left", "center", "right"]

# (key, label, type, extra)  types: int(lo,hi) colour colour! (may be none) text multi bool choice font
TEXT_FIELDS = [("font", "Font", "font", None), ("size", "Size (px)", "int", (4, 300)),
               ("bold", "Bold", "bool", None), ("italic", "Italic", "bool", None),
               ("color", "Text colour", "colour", None),
               ("align", "Align", "choice", ALIGNS)]
BOX_FIELDS = [("fill", "Fill colour", "colour!", None), ("stroke", "Outline colour", "colour!", None),
              ("sw", "Outline width", "int", (0, 500)), ("radius", "Corner radius", "int", (0, 500))]

SCHEMA = {
    "text": [("Text", [("text", "Words", "multi", None)] + TEXT_FIELDS
                       + [("listtype", "Bullets and numbering", "list", None),
                          ("overflow", "If the words do not fit", "choice",
                           ["hidden", "visible", "auto", "scroll"]),
                          ("autoh", "Grow the box to fit the text", "bool", None)]),
             ("Box", BOX_FIELDS)],
    "button": [("Button", [("text", "Label", "text", None)] + TEXT_FIELDS),
               ("Colours", [("fill", "Colour", "colour!", None), ("fill2", "Second colour (fade)", "colour!", None),
                            ("hfill", "Colour under the mouse", "colour!", None),
                            ("hcolor", "Text under the mouse", "colour!", None),
                            ("pfill", "Colour while pressed", "colour!", None),
                            ("radius", "Corner radius", "int", (0, 500)), ("shadow", "Shadow", "bool", None)])],
    "rect": [("Shape", BOX_FIELDS)],
    "ellipse": [("Shape", BOX_FIELDS[:3])],
    "line": [("Line", [("stroke", "Colour", "colour", None), ("sw", "Thickness", "int", (1, 100))])],
    "image": [("Picture", [("alt", "Description (for search and screen readers)", "text", None),
                           ("fit", "Fit to frame", "choice", ["cover", "contain", "fill"]),
                           ("radius", "Corner radius", "int", (0, 500)),
                           ("caption", "Caption", "text", None)])],
    "navbar": [("Menu bar", [("orient", "Direction", "choice", ["horizontal", "vertical"]),
                             ("gap", "Space between items", "int", (0, 80)),
                             ("fill", "Bar colour", "colour!", None), ("ihover", "Item under the mouse", "colour!", None),
                             ("active", "Current page", "colour!", None)] + TEXT_FIELDS[:5])],
    "gallery": [("Gallery", [("cols", "Pictures across", "int", (1, 12)), ("gap", "Space between", "int", (0, 80)),
                             ("fit", "Fit", "choice", ["cover", "contain"]),
                             ("radius", "Corner radius", "int", (0, 500))])],
    "video": [("Video", [("url", "YouTube, Vimeo or .mp4 address", "text", None)])],
    "map": [("Map", [("address", "Address", "text", None), ("zoom", "Zoom", "int", (1, 20))])],
    "audio": [("Audio", [("url", "Web address of the sound", "text", None)])],
    "html": [("HTML", [("code", "HTML code", "multi", None)])],
    "frame": [("Document frame", [("url", "Web page to show", "text", None)])],
    "marquee": [("Message", [("text", "Words", "text", None), ("speed", "Speed", "int", (1, 100)),
                             ("fill", "Background", "colour!", None)] + TEXT_FIELDS[:5])],
    "rssreader": [("RSS reader", [("url", "Address of the feed (https://...)", "text", None),
                                  ("count", "How many headlines", "int", (1, 20)),
                                  ("show_date", "Show the date", "bool", None),
                                  ("show_desc", "Show a short description", "bool", None)] + TEXT_FIELDS[:5])],
    "hotspot": [("Hotspot", [("shape", "Shape", "choice", ["rect", "ellipse", "rounded", "triangle", "diamond"]),
                             ("tip", "Words shown when the mouse rests on it", "text", None)])],
    "popup": [("Pop-up", [("side", "Pops up", "choice", ["right", "left", "above", "below"]),
                          ("pop_text", "Words that pop up (if no picture)", "multi", None),
                          ("pop_w", "Pop-up width", "int", (40, 1200)), ("pop_h", "Pop-up height", "int", (30, 1200)),
                          ("alt", "Description of the picture", "text", None),
                          ("fit", "Fit to frame", "choice", ["cover", "contain"])])],
    "arttext": [("Artistic text", [("text", "Words", "text", None), ("shape", "Shape", "choice", ["arc", "wave", "ring"]),
                                   ("curve", "Curve (- bowl, + arch)", "int", (-100, 100))] + TEXT_FIELDS[:5]
                                  + [("stroke", "Outline colour", "colour!", None),
                                     ("sw", "Outline width", "int", (0, 40))])],
    "field": [("Form field", [("label", "Label", "text", None), ("name", "Name", "text", None),
                              ("options", "Choices (one per line)", "multi", None),
                              ("answer", "CAPTCHA: the right answer (capitals do not matter)", "text", None),
                              ("rc_site", "reCAPTCHA site key (public)", "text", None),
                              ("rc_secret", "reCAPTCHA secret key (kept private on your site)", "text", None),
                              ("required", "Required", "bool", None)])],
    "search": [("Search box", [("label", "Label", "text", None), ("btn", "Button words", "text", None)])],
    "subscribe": [("Sign-up", [("label", "Label", "text", None), ("btn", "Button words", "text", None),
                               ("thanks", "Thank-you message", "text", None)])],
    "login": [("Login", [("title", "Title", "text", None), ("btn", "Button words", "text", None)])],
}
from . import webapps  # noqa: E402
SCHEMA.update(webapps.schemas())

COMMON_TABS = [
    ("Position and size", [("x", "Across (px)", "int", (-5000, 20000)), ("y", "Down (px)", "int", (-5000, 50000)),
                           ("w", "Width", "int", (1, 5000)), ("h", "Height", "int", (1, 20000)),
                           ("rot", "Turn (degrees)", "int", (-180, 180)),
                           ("opacity", "Opacity (%)", "int", (0, 100))]),
    ("Link and web", [("link", "Link to (page, web address or email)", "text", None),
                      ("ident", "HTML id (for anchors)", "text", None),
                      ("cls", "CSS class", "text", None),
                      ("hidden", "Hide on the published page", "bool", None),
                      ("locked", "Lock so it cannot be moved", "bool", None)]),
]


class PropertiesDialog(QDialog):
    def __init__(self, win, d):
        super().__init__(win)
        from .window import ColorField
        self.win, self.orig = win, d
        self.d = copy.deepcopy(d)
        self.kind = d["kind"]
        self.getters = {}
        self.setWindowTitle("%s properties" % KIND_NAMES.get(self.kind, self.kind.title()))
        self.resize(560, 520)
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)
        self.ColorField = ColorField
        if self.kind == "table":
            self.table_tabs()
        for title, fields in SCHEMA.get(self.kind, []):
            self.tabs.addTab(self.page(fields), title)
        if self.kind == "image":
            self.tabs.widget(0).layout().insertRow(0, self.picture_row("asset", "Replace picture..."))
        if self.kind == "popup":
            self.tabs.widget(0).layout().insertRow(0, self.picture_row("pop_asset", "Choose the pop-up picture..."))
            self.tabs.widget(0).layout().insertRow(0, self.picture_row("asset", "Choose the picture people see..."))
        if self.kind not in SCHEMA and self.kind != "table":
            note = QLabel("This kind of object is set up in the Properties panel on the right.\\n"
                          "Position, link and web settings are here.")
            note.setWordWrap(True)
            w = QWidget()
            QVBoxLayout(w).addWidget(note)
            self.tabs.addTab(w, "About")
        for title, fields in COMMON_TABS:
            self.tabs.addTab(self.page(fields), title)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    # -- building --------------------------------------------------------
    def page(self, fields):
        w = QWidget()
        form = QFormLayout(w)
        for key, label, typ, extra in fields:
            if key not in self.d and typ not in ("bool", "pick") and key not in ("ident", "cls", "link"):
                if key not in ("text",):
                    continue
            editor = self.editor(key, typ, extra)
            if editor is not None:
                form.addRow(label if typ != "bool" else "", editor if typ != "bool" else editor)
        return w

    def editor(self, key, typ, extra):
        val = self.d.get(key)
        if typ == "int":
            w = QSpinBox()
            w.setRange(*extra)
            w.setValue(int(val or 0))
            self.getters[key] = w.value
        elif typ in ("colour", "colour!"):
            w = self.ColorField(typ == "colour!")
            w.set(val or "")
            self.getters[key] = lambda w=w: w.value
        elif typ == "bool":
            w = QCheckBox(self.label_of(key))
            w.setChecked(bool(val))
            self.getters[key] = w.isChecked
        elif typ == "choice":
            w = QComboBox()
            w.addItems(extra)
            w.setCurrentText(str(val) if val in extra else extra[0])
            self.getters[key] = w.currentText
        elif typ == "pick":                  # a choice made from things in the site (extra(win) gives (name, value) pairs)
            w = QComboBox()
            for name, value in extra(self.win):
                w.addItem(name, value)
            w.setCurrentIndex(max(w.findData(val or ""), 0))
            self.getters[key] = lambda w=w: w.currentData() or ""
        elif typ == "list":
            from .textlayout import LIST_STYLES
            w = QComboBox()
            for value, name, *_ in LIST_STYLES:
                w.addItem(name, value)
            w.setCurrentIndex(max(w.findData(val or ""), 0))
            self.getters[key] = lambda w=w: w.currentData()
        elif typ == "font":
            w = QFontComboBox()
            from PyQt5.QtGui import QFont
            w.setCurrentFont(QFont(val or "Sans Serif"))
            self.getters[key] = lambda w=w: w.currentFont().family()
        elif typ == "multi":
            w = QPlainTextEdit(val or "")
            w.setMinimumHeight(110)
            self.getters[key] = w.toPlainText
        else:
            w = QLineEdit(val or "")
            self.getters[key] = w.text
        return w

    LABELS = {"show_date": "Show the date", "show_desc": "Show a short description", "autoh": "Grow the box to fit the text", "bold": "Bold", "italic": "Italic", "shadow": "Shadow",
              "required": "Required", "hidden": "Hide on the published page",
              "locked": "Lock so it cannot be moved"}

    def label_of(self, key):
        return self.LABELS.get(key, key)

    def picture_row(self, key="asset", button="Replace picture..."):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        pic = QLabel()
        pic.setFixedSize(120, 80)
        pic.setFrameShape(QLabel.Box)
        pic.setAlignment(Qt.AlignCenter)
        h.addWidget(pic)
        btn = QPushButton(button)
        btn.clicked.connect(lambda _=False, k=key: self.replace_picture(k))
        h.addWidget(btn)
        h.addStretch(1)
        if not hasattr(self, "pics"):
            self.pics = {}
        self.pics[key] = pic
        self.show_picture(key)
        return row

    def show_picture(self, key="asset"):
        pic = self.pics[key]
        pm = self.win.pixmap(self.d.get(key, ""))
        if pm is not None and not pm.isNull():
            pic.setPixmap(pm.scaled(116, 76, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            pic.setText("No picture")

    def replace_picture(self, key="asset"):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a picture", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg)")
        if path:
            self.d[key] = self.win.doc.add_asset(path)
            self.show_picture(key)

    # -- the table tabs --------------------------------------------------
    def table_tabs(self):
        w = QWidget()
        form = QFormLayout(w)
        self.t_rows = QSpinBox()
        self.t_rows.setRange(1, 50)
        self.t_rows.setValue(self.d["rows"])
        self.t_cols = QSpinBox()
        self.t_cols.setRange(1, 20)
        self.t_cols.setValue(self.d["cols"])
        self.t_head = QCheckBox("First row is a heading")
        self.t_head.setChecked(bool(self.d.get("header")))
        self.t_look = QComboBox()
        self.t_look.addItems(["(keep my colours)"] + list(tc.AUTOFORMATS))
        form.addRow("Number of rows", self.t_rows)
        form.addRow("Number of columns", self.t_cols)
        form.addRow(self.t_head)
        form.addRow("Look (AutoFormat)", self.t_look)
        self.t_fields = {}
        for key, label, kind in (("hfill", "Heading colour", "colour!"), ("hcolor", "Heading text", "colour!"),
                                 ("fill", "Cell colour", "colour!"), ("band", "Every other row", "colour!"),
                                 ("stroke", "Line colour", "colour!"), ("color", "Text colour", "colour")):
            f = self.ColorField(kind == "colour!")
            f.set(self.d.get(key, ""))
            f.changed.connect(lambda _=None: self.refresh_sample())
            self.t_fields[key] = f
            form.addRow(label, f)
        self.t_sw = QSpinBox()
        self.t_sw.setRange(0, 10)
        self.t_sw.setValue(int(self.d.get("sw", 1) or 0))
        form.addRow("Line width", self.t_sw)
        self.sample = QLabel()
        self.sample.setFixedSize(380, 120)
        self.sample.setFrameShape(QLabel.Box)
        form.addRow("Sample", self.sample)
        self.tabs.addTab(w, "Table")
        for sp in (self.t_rows, self.t_cols, self.t_sw):
            sp.valueChanged.connect(self.table_changed)
        self.t_head.toggled.connect(self.table_changed)
        self.t_look.currentIndexChanged.connect(self.look_picked)
        # cell contents grid
        g = QWidget()
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel("Click a cell and type. Tab moves to the next cell."))
        self.grid = QTableWidget()
        from PyQt5.QtWidgets import QHeaderView
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.grid.itemChanged.connect(self.grid_edited)
        gl.addWidget(self.grid, 1)
        self.tabs.addTab(g, "Contents")
        self.fill_grid()
        self.refresh_sample()

    def fill_grid(self):
        self.grid.blockSignals(True)
        r, c = max(self.d["rows"], 1), max(self.d["cols"], 1)
        self.grid.setRowCount(r)
        self.grid.setColumnCount(c)
        self.grid.setHorizontalHeaderLabels([str(j + 1) for j in range(c)])
        self.grid.setVerticalHeaderLabels([str(i + 1) for i in range(r)])
        for i in range(r):
            for j in range(c):
                self.grid.setItem(i, j, QTableWidgetItem(tc.text_at(self.d, i, j)))
        self.grid.blockSignals(False)

    def grid_edited(self, item):
        self.d["cells"][item.row()][item.column()] = item.text()
        self.refresh_sample()

    def table_changed(self, *_):
        tc.resize(self.d, self.t_rows.value(), self.t_cols.value())
        self.d["header"] = self.t_head.isChecked()
        self.d["sw"] = self.t_sw.value()
        self.fill_grid()
        self.refresh_sample()

    def look_picked(self, i):
        if i <= 0:
            return
        tc.apply_autoformat(self.d, self.t_look.currentText())
        for key, f in self.t_fields.items():
            f.set(self.d.get(key, ""))
        self.t_sw.blockSignals(True)
        self.t_sw.setValue(int(self.d.get("sw", 1) or 0))
        self.t_sw.blockSignals(False)
        self.t_head.blockSignals(True)
        self.t_head.setChecked(bool(self.d.get("header")))
        self.t_head.blockSignals(False)
        self.refresh_sample()

    def refresh_sample(self):
        from .extras import paint_table
        for key, f in self.t_fields.items():
            self.d[key] = f.value
        probe = copy.deepcopy(self.d)
        probe["sel"] = [0, 0, 0, 0]
        img = QImage(380, 120, QImage.Format_ARGB32)
        img.fill(QColor("#ffffff"))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)

        class NoMarks:
            table_marks = None
        paint_table(p, QRectF(6, 6, 368, 108), dict(probe, size=11), NoMarks())
        p.end()
        self.sample.setPixmap(QPixmap.fromImage(img))

    # -- done --------------------------------------------------------------
    def result_values(self):
        """{key: new value} for everything this dialog edits."""
        out = {}
        for key, get in self.getters.items():
            out[key] = get()
        if self.kind == "table":
            for key in ("rows", "cols", "cells", "header", "sw", "merges", "fmt", "colw", "rowh",
                        "sel", "hfill", "hcolor", "fill", "band", "stroke", "color"):
                out[key] = self.d.get(key)
        return out

    def apply(self):
        """Put the changes onto the real object. Returns True if anything changed."""
        new = self.result_values()
        changed = False
        for k, v in new.items():
            if self.orig.get(k) != v:
                self.orig[k] = copy.deepcopy(v)
                changed = True
        for key in ("asset", "pop_asset"):
            if self.kind in ("image", "popup") and self.d.get(key) != self.orig.get(key) and key in self.d:
                self.orig[key] = self.d[key]
                changed = True
        return changed
