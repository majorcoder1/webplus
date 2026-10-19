"""Main window: menus, tools, pages panel, properties panel."""
import copy
import os
import tempfile

from PyQt5.QtCore import QBuffer, QByteArray, QPoint, QRectF, QSettings, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QKeySequence, QMovie, QPixmap
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import (QAction, QActionGroup, QCheckBox, QColorDialog,
                             QComboBox, QDialog, QDialogButtonBox, QDockWidget,
                             QFileDialog, QFontComboBox, QFormLayout,
                             QApplication, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                             QMenu, QMessageBox, QPlainTextEdit,
                             QPushButton, QScrollArea, QSlider, QSpinBox, QToolBar,
                             QToolButton, QTreeWidget, QTreeWidgetItem,
                             QUndoCommand, QUndoStack, QVBoxLayout, QWidget)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl

from . import export
from .canvas import ItemObj, SiteScene, SiteView
from .model import (FIELD_LABELS, FIELD_SIZES, FIELD_TYPES, KIND_NAMES,
                    Document, new_id, new_item, new_page, ordered_pages,
                    real_pages, remap_assets)
from .extras import NETS
from .styles import BUTTON_STYLES, NAV_STYLES, preview_button, preview_nav
from .schemes import (SCHEME_LABELS, SCHEMES, THEMES, apply_scheme, apply_theme,
                      preview_theme)

STYLE_KEYS = ("fill", "fill2", "stroke", "sw", "radius", "shadow", "font", "size",
              "bold", "italic", "color", "align", "opacity", "hfill", "hcolor",
              "pfill", "ifill", "ihover", "active", "acolor", "uline", "iradius",
              "ipad")
from . import objectprops, pageitems, pagetools, rulers, templates, textlayout
from .panels import (StarterDialog, AssetsPanel, ColourPanel, CompositionsPanel, FontsPanel, LinePanel,
                     OptionsDialog, QuickBuildPanel, SwatchesPanel,
                     TextStylesPanel, TransformPanel, TransparencyPanel,
                     UserDetailsDialog, swatch)
from . import compositions, dialogs, spell, startup
from .uiicons import ui_icon
from .hovernames import HoverNames
from . import publish, taskcheck

APP = "WebPlus"
STATE_VERSION = 4          # bump when toolbars or panels are added or renamed
DEFAULT_UI_PT = 9


def apply_ui_font(pt):
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    f = app.font()
    f.setPointSizeF(pt)
    app.setFont(f)


def saved_ui_pt():
    try:
        return float(QSettings("4ThePeopleMedia", "Sitewright").value("ui_pt", DEFAULT_UI_PT))
    except (TypeError, ValueError):
        return DEFAULT_UI_PT
FILTER = ("Web page (*.site *.sitewright *.wpp *.wpack);;Web page (*.site);;"
          "Old Sitewright file (*.sitewright);;Serif WebPlus site (*.wpp *.wpack)")
from .toolbox import TOOLS, tool_icon


class SnapCommand(QUndoCommand):
    def __init__(self, win, before, after, label):
        super().__init__(label)
        self.win, self.before, self.after = win, before, after
        self.first = True

    def redo(self):
        if self.first:
            self.first = False
            return
        self.win.apply_snapshot(self.after)

    def undo(self):
        self.win.apply_snapshot(self.before)


class ColorField(QWidget):
    changed = pyqtSignal(str)
    scheme_source = None        # set by the window: returns the 12 scheme colours

    def __init__(self, allow_none=True):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.btn = QPushButton()
        self.btn.setFixedHeight(22)
        self.btn.clicked.connect(self.pick)
        h.addWidget(self.btn, 1)
        self.value = ""
        if allow_none:
            x = QToolButton()
            x.setText("none")
            x.clicked.connect(lambda: self.set_and_emit(""))
            h.addWidget(x)
        self.set("")

    def set(self, c):
        self.value = c or ""
        if self.value:
            lum = QColor(self.value).lightness()
            self.btn.setStyleSheet("background:%s;color:%s;border:1px solid #666"
                                   % (self.value, "#000" if lum > 128 else "#fff"))
            self.btn.setText(self.value)
        else:
            self.btn.setStyleSheet("")
            self.btn.setText("(none)")

    def set_and_emit(self, c):
        self.set(c)
        self.changed.emit(self.value)

    def pick(self):
        scheme = ColorField.scheme_source() if ColorField.scheme_source else None
        if scheme:
            m = QMenu(self)
            for i, c in enumerate(scheme):
                pm = QPixmap(18, 18)
                pm.fill(QColor(c))
                a = m.addAction(QIcon(pm), "%d  %s  %s" % (i + 1, SCHEME_LABELS[i], c))
                a.setData(c)
            m.addSeparator()
            more = m.addAction("More colours...")
            act = m.exec_(self.btn.mapToGlobal(QPoint(0, self.btn.height())))
            if act is None:
                return
            if act is not more:
                self.set_and_emit(act.data())
                return
        c = QColorDialog.getColor(QColor(self.value or "#ffffff"), self, "Colour")
        if c.isValid():
            self.set_and_emit(c.name())


def spin(lo, hi):
    s = QSpinBox()
    s.setRange(lo, hi)
    return s


class Properties(QWidget):
    """Edits the selected items. Every control maps to one key of the item dict."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.busy = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: win.commit_if_changed("Edit text"))
        lay = QVBoxLayout(self)
        self.title = QLabel("Nothing selected")
        self.title.setStyleSheet("font-weight:bold")
        lay.addWidget(self.title)
        self.empty_hint = QLabel(
            "Click an object on the page and its details appear here: size and position, "
            "colours, text, fonts, links, and extras such as a rollover picture or a "
            "heading level.\n\nTo make something new, pick a tool from the Tools panel on "
            "the left, then drag on the page.")
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setStyleSheet("color:#5b6675")
        lay.addWidget(self.empty_hint)
        self.groups, self.w = {}, {}

        def group(name, label):
            g = QGroupBox(label)
            f = QFormLayout(g)
            lay.addWidget(g)
            self.groups[name] = g
            return f

        f = group("geom", "Position and size")
        for k, lab in (("x", "X"), ("y", "Y"), ("w", "Width"), ("h", "Height")):
            s = spin(-5000, 20000)
            s.valueChanged.connect(lambda v, k=k: self.set(k, v))
            self.w[k] = s
            f.addRow(lab, s)
        s = spin(0, 100)
        s.valueChanged.connect(lambda v: self.set("opacity", v))
        self.w["opacity"] = s
        f.addRow("Opacity %", s)
        s = spin(-360, 360)
        s.valueChanged.connect(lambda v: self.set("rot", v))
        self.w["rot"] = s
        f.addRow("Rotation", s)
        c = QCheckBox("Locked")
        c.toggled.connect(lambda v: self.set("locked", v))
        self.w["locked"] = c
        f.addRow(c)

        f = group("look", "Appearance")
        for k, lab in (("fill", "Fill"), ("stroke", "Outline")):
            c = ColorField()
            c.changed.connect(lambda v, k=k: self.set(k, v))
            self.w[k] = c
            f.addRow(lab, c)
        s = spin(0, 60)
        s.valueChanged.connect(lambda v: self.set("sw", v))
        self.w["sw"] = s
        f.addRow("Outline width", s)
        s = spin(0, 500)
        s.valueChanged.connect(lambda v: self.set("radius", v))
        self.w["radius"] = s
        f.addRow("Corner radius", s)

        f = group("text", "Text")
        t = QPlainTextEdit()
        t.setFixedHeight(70)
        t.textChanged.connect(self.text_changed)
        self.w["text"] = t
        f.addRow(t)
        fc = QFontComboBox()
        fc.currentFontChanged.connect(lambda fnt: self.set("font", fnt.family()))
        self.w["font"] = fc
        f.addRow("Font", fc)
        s = spin(4, 300)
        s.valueChanged.connect(lambda v: self.set("size", v))
        self.w["size"] = s
        f.addRow("Size (px)", s)
        for k, lab in (("bold", "Bold"), ("italic", "Italic")):
            c = QCheckBox(lab)
            c.toggled.connect(lambda v, k=k: self.set(k, v))
            self.w[k] = c
            f.addRow(c)
        c = ColorField(False)
        c.changed.connect(lambda v: self.set("color", v))
        self.w["color"] = c
        f.addRow("Colour", c)
        a = QComboBox()
        a.addItems(["left", "center", "right"])
        a.currentTextChanged.connect(lambda v: self.set("align", v))
        self.w["align"] = a
        f.addRow("Align", a)

        f = group("nav", "Navigation bar")
        o = QComboBox()
        o.addItems(["horizontal", "vertical", "dropdown"])
        o.currentTextChanged.connect(lambda v: self.set("orient", v))
        self.w["orient"] = o
        f.addRow("Direction", o)
        s = spin(0, 200)
        s.valueChanged.connect(lambda v: self.set("gap", v))
        self.w["gap"] = s
        f.addRow("Spacing", s)

        self.build_extra_groups(group)

        f = group("advanced", "HTML options")
        hl = QComboBox()
        hl.addItem("Paragraph", "")
        for n in range(1, 7):
            hl.addItem("Heading %d" % n, "h%d" % n)
        hl.activated.connect(lambda i: self.set("htag", hl.itemData(i)))
        self.w["htag"] = hl
        f.addRow("Text type", hl)
        for key, label in (("ident", "HTML id"), ("cls", "CSS class")):
            e = QLineEdit()
            e.editingFinished.connect(lambda e=e, k=key: self.set(k, e.text().strip()))
            self.w[key] = e
            f.addRow(label, e)
        c = QCheckBox("Hidden when the page opens")
        c.toggled.connect(lambda v: self.set("hidden", v))
        self.w["hidden"] = c
        f.addRow(c)

        f = group("image", "Picture")
        fit = QComboBox()
        fit.addItems(["cover", "contain", "fill"])
        fit.currentTextChanged.connect(lambda v: self.set("fit", v))
        self.w["fit"] = fit
        f.addRow("Fit", fit)
        alt = QLineEdit()
        alt.editingFinished.connect(lambda: self.set("alt", alt.text()))
        self.w["alt"] = alt
        f.addRow("Alt text", alt)
        b = QPushButton("Replace picture...")
        b.clicked.connect(win.replace_picture)
        f.addRow(b)
        b = QPushButton("Rollover picture (shown on mouse over)...")
        b.clicked.connect(lambda: win.pick_asset_prop("hover_asset"))
        f.addRow(b)
        ef = QComboBox()
        for label, key in (("Swap to the rollover picture", "swap"), ("Grow a little", "zoom"),
                           ("Brighten", "bright")):
            ef.addItem(label, key)
        ef.activated.connect(lambda i: self.set("hover_effect", ef.itemData(i)))
        self.w["hover_effect"] = ef
        f.addRow("Mouse over", ef)
        c = QCheckBox("Show larger in a lightbox when clicked")
        c.toggled.connect(lambda v: self.set("lightbox", v))
        self.w["lightbox"] = c
        f.addRow(c)
        b = QPushButton("Larger picture for the lightbox...")
        b.clicked.connect(lambda: win.pick_asset_prop("lightbox_asset"))
        f.addRow(b)
        cap = QLineEdit()
        cap.setPlaceholderText("Caption shown in the lightbox")
        cap.editingFinished.connect(lambda: self.set("caption", cap.text()))
        self.w["caption"] = cap
        f.addRow("Caption", cap)

        f = group("link", "Hyperlink")
        lk = QComboBox()
        lk.setEditable(True)
        lk.activated.connect(self.link_chosen)
        lk.lineEdit().editingFinished.connect(self.link_typed)
        self.w["link"] = lk
        f.addRow("Link to", lk)
        an = QLineEdit()
        an.setPlaceholderText("Anchor name (so other links can jump here)")
        an.editingFinished.connect(lambda: self.set("anchor", an.text().strip()))
        self.w["anchor"] = an
        f.addRow("Anchor", an)
        pu = QPlainTextEdit()
        pu.setFixedHeight(64)
        pu.setPlaceholderText("Pop-up menu: one 'Label|address' per line")
        pu.textChanged.connect(lambda: self.set("popup", self.w["popup"].toPlainText()))
        self.w["popup"] = pu
        f.addRow(pu)
        lay.addStretch(1)

    def build_extra_groups(self, group):
        def line(f, key, label):
            e = QLineEdit()
            e.editingFinished.connect(lambda e=e, k=key: self.set(k, e.text()))
            self.w[key] = e
            f.addRow(label, e)

        def number(f, key, label, lo, hi):
            s = spin(lo, hi)
            s.valueChanged.connect(lambda v, k=key: self.set(k, v))
            self.w[key] = s
            f.addRow(label, s)

        def color(f, key, label, none=False):
            c = ColorField(none)
            c.changed.connect(lambda v, k=key: self.set(k, v))
            self.w[key] = c
            f.addRow(label, c)

        f = group("table", "Table")
        number(f, "rows", "Rows", 1, 50)
        number(f, "tcols", "Columns", 1, 20)
        c = QCheckBox("Header row")
        c.toggled.connect(lambda v: self.set("header", v))
        self.w["header"] = c
        f.addRow(c)
        color(f, "hfill", "Header colour")
        color(f, "hcolor", "Header text")
        rng = QWidget()
        rl = QHBoxLayout(rng)
        rl.setContentsMargins(0, 0, 0, 0)
        self.range_spins = []
        for lab in ("Cells: rows", "to", "cols", "to"):
            rl.addWidget(QLabel(lab))
            sp_ = spin(1, 50)
            sp_.setFixedWidth(52)
            sp_.valueChanged.connect(lambda v, i=len(self.range_spins): self.win.table_sel_changed(i, v))
            rl.addWidget(sp_)
            self.range_spins.append(sp_)
        f.addRow(rng)
        t = QPlainTextEdit()
        t.setFixedHeight(90)
        t.setPlaceholderText("One row per line, cells separated by |")
        t.textChanged.connect(self.cells_changed)
        self.w["celltext"] = t
        f.addRow(t)

        f = group("gallery", "Photo gallery")
        self.gal_count = QLabel("0 pictures")
        f.addRow(self.gal_count)
        b = QPushButton("Add pictures...")
        b.clicked.connect(self.win.add_gallery_pictures)
        f.addRow(b)
        b = QPushButton("Remove all pictures")
        b.clicked.connect(self.win.clear_gallery)
        f.addRow(b)
        number(f, "cols", "Columns", 1, 12)
        number(f, "gap", "Gap (px)", 0, 80)
        fit = QComboBox()
        fit.addItems(["cover", "contain"])
        fit.currentTextChanged.connect(lambda v: self.set("fit", v))
        self.w["gal_fit"] = fit
        f.addRow("Fit", fit)

        f = group("video", "Video")
        line(f, "url", "YouTube, Vimeo or .mp4 address")
        for key, label in (("autoplay", "Autoplay (starts muted)"), ("loop", "Loop"),
                           ("fullscreen", "Allow full screen"), ("related", "Show related videos"),
                           ("showinfo", "Show video info"), ("hd", "Play in HD")):
            cb = QCheckBox(label)
            cb.toggled.connect(lambda v, k=key: self.set("v_" + k, v))
            self.w["v_" + key] = cb
            f.addRow(cb)
        f = group("map", "Map")
        line(f, "address", "Address")
        number(f, "zoom", "Zoom (1-20)", 1, 20)
        f = group("slider", "Slider")
        self.slider_info = QLabel("")
        f.addRow(self.slider_info)
        b = QPushButton("Open Slider Studio...")
        b.clicked.connect(self.win.slider_studio)
        f.addRow(b)

        f = group("frame", "Document frame")
        line(f, "f_url", "Web page address (https://...)")
        f = group("audio", "Audio")
        line(f, "audio_url", "Address (or pick a file)")
        b = QPushButton("Choose audio file...")
        b.clicked.connect(self.win.pick_audio)
        f.addRow(b)
        f = group("html", "HTML fragment")
        t = QPlainTextEdit()
        t.setFixedHeight(120)
        t.textChanged.connect(self.code_changed)
        self.w["code"] = t
        f.addRow(t)

        f = group("field", "Form field")
        ft = QComboBox()
        for k in FIELD_TYPES:
            ft.addItem(FIELD_LABELS[k], k)
        ft.activated.connect(lambda i: self.set("ftype", ft.itemData(i)))
        self.w["ftype"] = ft
        f.addRow("Type", ft)
        line(f, "name", "Field name")
        line(f, "label", "Label / placeholder")
        t = QPlainTextEdit()
        t.setFixedHeight(60)
        t.setPlaceholderText("Choices, one per line")
        t.textChanged.connect(lambda: self.set("options", self.w["options"].toPlainText()))
        self.w["options"] = t
        f.addRow(t)
        c = QCheckBox("Required")
        c.toggled.connect(lambda v: self.set("required", v))
        self.w["required"] = c
        f.addRow(c)

        f = group("social", "Social buttons")
        self.net_boxes = {}
        for n, (_ch, _col, title) in NETS.items():
            c = QCheckBox(title)
            c.toggled.connect(self.nets_changed)
            self.net_boxes[n] = c
            f.addRow(c)

        f = group("effects", "Gradient and shadow")
        color(f, "g_fill2", "Gradient to", True)
        c = QCheckBox("Drop shadow")
        c.toggled.connect(lambda v: self.set("g_shadow", v))
        self.w["g_shadow"] = c
        f.addRow(c)

        f = group("button", "Button states and style")
        b = QPushButton("Choose from the button gallery...")
        b.clicked.connect(self.win.button_gallery)
        f.addRow(b)
        color(f, "b_fill2", "Gradient to", True)
        color(f, "b_hfill", "Hover colour", True)
        color(f, "b_hcolor", "Hover text", True)
        color(f, "b_pfill", "Pressed colour", True)
        c = QCheckBox("Drop shadow")
        c.toggled.connect(lambda v: self.set("shadow", v))
        self.w["shadow"] = c
        f.addRow(c)

        f = group("navstyle", "Navigation style")
        b = QPushButton("Choose from the navigation gallery...")
        b.clicked.connect(self.win.nav_gallery)
        f.addRow(b)
        color(f, "n_ifill", "Item colour", True)
        color(f, "n_ihover", "Hover colour", True)
        color(f, "n_hcolor", "Hover text", True)
        color(f, "n_active", "Current page", True)
        color(f, "n_acolor", "Current text", True)
        color(f, "n_uline", "Underline", True)
        number(f, "n_iradius", "Item corners", 0, 60)
        number(f, "n_ipad", "Item padding", 0, 60)

        line(f_social := self.groups["social"].layout(), "instagram_url", "Instagram page")
        line(f_social, "youtube_url", "YouTube channel")

        f = group("special", "Search, sign-up and login")
        line(f, "s_label", "Hint text")
        line(f, "s_btn", "Button text")
        line(f, "s_title", "Heading")
        line(f, "s_empty", "Message when nothing is found")
        color(f, "s_btnfill", "Button colour")
        color(f, "s_btncolor", "Button text colour")

        f = group("marquee", "Scrolling message")
        number(f, "speed", "Seconds per pass", 2, 120)
        color(f, "fill", "Background", True)

        f = group("hotspot", "Hotspot")
        hs = QComboBox()
        hs.addItems(["rect", "ellipse", "rounded", "triangle", "diamond"])
        hs.currentTextChanged.connect(lambda v: self.set("shape", v))
        self.w["hs_shape"] = hs
        f.addRow("Shape", hs)
        line(f, "tip", "Words shown when the mouse rests on it")

        f = group("arttext", "Artistic text")
        number(f, "curve", "Curve (- bowl, + arch)", -100, 100)
        sh = QComboBox()
        sh.addItems(["arc", "wave", "ring"])
        sh.currentTextChanged.connect(lambda v: self.set("shape", v))
        self.w["shape"] = sh
        f.addRow("Shape", sh)

    def cells_changed(self):
        if self.busy:
            return
        self.win.set_table_cells(self.w["celltext"].toPlainText())

    def code_changed(self):
        if self.busy:
            return
        self.win.set_prop("code", self.w["code"].toPlainText(), commit=False)
        self.timer.start(500)

    def nets_changed(self):
        if self.busy:
            return
        self.set("nets", [n for n, c in self.net_boxes.items() if c.isChecked()])

    def refresh_cell_range(self):
        from . import tablecore as tc
        objs = [o for o in self.win.selected() if o.d["kind"] == "table"]
        if not objs:
            return
        sel = tc.clamp_sel(objs[0].d)
        was, self.busy = self.busy, True
        try:
            for sp_, v in zip(self.range_spins, (sel[0], sel[2], sel[1], sel[3])):
                sp_.setValue(v + 1)
        finally:
            self.busy = was

    def set(self, key, val):
        if self.busy:
            return
        if key == "audio_url":
            key = "url"
        if key[:2] in ("b_", "n_", "g_", "f_", "v_", "s_"):
            key = key[2:]
        if key in ("rows", "tcols"):
            self.win.set_table_dims(**{("cols" if key == "tcols" else "rows"): val})
            return
        self.win.set_prop(key, val)

    def text_changed(self):
        if self.busy:
            return
        self.win.set_prop("text", self.w["text"].toPlainText(), commit=False)
        self.timer.start(500)

    def link_chosen(self, i):
        if self.busy:
            return
        self.set("link", self.w["link"].itemData(i) or "")

    def link_typed(self):
        if self.busy:
            return
        txt = self.w["link"].currentText().strip()
        for i in range(self.w["link"].count()):
            if self.w["link"].itemText(i) == txt:
                self.set("link", self.w["link"].itemData(i) or "")
                return
        self.set("link", txt)

    def refresh(self):
        self._refresh()
        side = getattr(self.win, "side_refresh", None)
        if side:
            side()

    def _refresh(self):
        self.busy = True
        try:
            try:
                objs = [i for i in self.win.scene.selectedItems() if isinstance(i, ItemObj)]
            except RuntimeError:    # scene already deleted at shutdown
                return
            kinds = {o.d["kind"] for o in objs}
            for g in self.groups.values():
                g.setVisible(bool(objs))
            self.empty_hint.setVisible(not objs)
            if not objs:
                self.title.setText("Nothing selected")
                return
            self.title.setText(KIND_NAMES[next(iter(kinds))] if len(kinds) == 1
                               else "%d objects" % len(objs))
            self.groups["look"].setVisible(bool(kinds & {"text", "rect", "ellipse", "button", "line", "image"}))
            self.groups["text"].setVisible(bool(kinds & {"text", "button", "navbar"}))
            self.w["text"].setVisible(bool(kinds & {"text", "button"}))
            self.groups["nav"].setVisible("navbar" in kinds)
            self.groups["advanced"].setVisible(True)
            self.groups["special"].setVisible(bool(kinds & {"search", "subscribe", "login",
                                                            "searchresults"}))
            d0 = objs[0].d
            if d0["kind"] in ("search", "subscribe", "login", "searchresults"):
                for k in ("label", "btn", "title", "empty"):
                    self.w["s_" + k].setText(d0.get(k, ""))
                    self.w["s_" + k].setEnabled(k in d0)
                self.w["s_btnfill"].set(d0.get("btnfill", ""))
                self.w["s_btncolor"].set(d0.get("btncolor", ""))
            self.groups["frame"].setVisible("frame" in kinds)
            self.groups["slider"].setVisible("slider" in kinds)
            if "slider" in kinds:
                dd = objs[0].d
                self.slider_info.setText("%d panel(s), %s" % (
                    len(dd.get("panels") or []), "plays automatically" if dd.get("autoplay", True)
                    else "manual"))
            self.w["htag"].setEnabled(kinds == {"text"})
            for g in ("table", "gallery", "video", "map", "audio", "html",
                      "field", "social", "marquee", "arttext", "hotspot"):
                self.groups[g].setVisible(g in kinds)
            self.groups["look"].setVisible(bool(kinds & {"text", "rect", "ellipse",
                                                         "button", "navbar", "line", "image", "field", "shape"}))
            self.w["text"].setVisible(bool(kinds & {"text", "button", "marquee", "arttext"}))
            self.groups["text"].setVisible(bool(kinds & {"text", "button", "navbar", "table",
                                                         "field", "marquee", "arttext"}))
            self.groups["image"].setVisible("image" in kinds)
            self.groups["link"].setVisible(bool(kinds - {"line"}))
            d = objs[0].d
            for k in ("x", "y", "w", "h", "opacity", "sw", "radius", "size",
                      "rot", "gap"):
                if k in d:
                    self.w[k].setValue(int(d[k]))
            self.w["locked"].setChecked(bool(d.get("locked")))
            for k in ("fill", "stroke", "color"):
                if k in d:
                    self.w[k].set(d[k])
            for k in ("bold", "italic"):
                self.w[k].setChecked(bool(d.get(k)))
            if "text" in d and self.w["text"].toPlainText() != d["text"]:
                self.w["text"].setPlainText(d["text"])
            if "font" in d:
                self.w["font"].setCurrentFont(QFont(d["font"]))
            for k in ("align", "fit", "orient", "shape"):
                if k in d and k in self.w:
                    self.w[k].setCurrentText(d[k])
            if d["kind"] == "hotspot":
                self.w["hs_shape"].setCurrentText(d.get("shape", "rect"))
            if "alt" in d:
                self.w["alt"].setText(d["alt"])
            if d["kind"] == "table":
                self.w["celltext"].setPlainText("\n".join("|".join(r) for r in d["cells"]))
            if d["kind"] == "gallery":
                self.gal_count.setText("%d pictures" % len(d.get("assets", [])))
                self.w["gal_fit"].setCurrentText(d.get("fit", "cover"))
            if d["kind"] == "table":
                self.w["rows"].setValue(d["rows"])
                self.w["tcols"].setValue(d["cols"])
                self.refresh_cell_range()
            for k in ("cols", "gap", "zoom", "speed", "curve"):
                if k in d and k in self.w:
                    self.w[k].setValue(int(d[k]))
            for k in ("url", "address", "name", "label", "instagram_url", "youtube_url", "tip"):
                if k in d and k in self.w:
                    self.w[k].setText(d[k])
            if d["kind"] == "audio":
                self.w["audio_url"].setText(d.get("url", ""))
            self.w["htag"].setCurrentIndex(max(self.w["htag"].findData(d.get("htag", "")), 0))
            self.w["ident"].setText(d.get("ident", ""))
            self.w["cls"].setText(d.get("cls", ""))
            self.w["hidden"].setChecked(bool(d.get("hidden")))
            if d["kind"] == "frame":
                self.w["f_url"].setText(d.get("url", ""))
            if d["kind"] == "image":
                self.w["hover_effect"].setCurrentIndex(
                    max(self.w["hover_effect"].findData(d.get("hover_effect", "swap")), 0))
                self.w["lightbox"].setChecked(bool(d.get("lightbox")))
                self.w["caption"].setText(d.get("caption", ""))
            if d["kind"] == "video":
                for k, dv in (("autoplay", False), ("loop", False), ("fullscreen", True),
                              ("related", True), ("showinfo", True), ("hd", False)):
                    self.w["v_" + k].setChecked(bool(d.get(k, dv)))
            if d["kind"] == "html" and self.w["code"].toPlainText() != d.get("code", ""):
                self.w["code"].setPlainText(d.get("code", ""))
            if d["kind"] == "field":
                self.w["ftype"].setCurrentIndex(max(self.w["ftype"].findData(d["ftype"]), 0))
                self.w["options"].setPlainText(d.get("options", ""))
                self.w["required"].setChecked(bool(d.get("required")))
            if d["kind"] == "table":
                self.w["header"].setChecked(bool(d.get("header")))
                self.w["hfill"].set(d.get("hfill", ""))
                self.w["hcolor"].set(d.get("hcolor", ""))
            self.groups["button"].setVisible("button" in kinds)
            self.groups["effects"].setVisible(bool(kinds & {"rect", "ellipse", "text"}))
            if d["kind"] in ("rect", "ellipse", "text"):
                self.w["g_fill2"].set(d.get("fill2", ""))
                self.w["g_shadow"].setChecked(bool(d.get("shadow")))
            self.groups["navstyle"].setVisible("navbar" in kinds)
            if d["kind"] == "button":
                for k in ("fill2", "hfill", "hcolor", "pfill"):
                    self.w["b_" + k].set(d.get(k, ""))
                self.w["shadow"].setChecked(bool(d.get("shadow")))
            if d["kind"] == "navbar":
                for k in ("ifill", "ihover", "hcolor", "active", "acolor", "uline"):
                    self.w["n_" + k].set(d.get(k, ""))
                self.w["n_iradius"].setValue(int(d.get("iradius", 0)))
                self.w["n_ipad"].setValue(int(d.get("ipad", 14)))
            if self.w["popup"].toPlainText() != d.get("popup", ""):
                self.w["popup"].setPlainText(d.get("popup", ""))
            if d["kind"] == "social":
                for n, c in self.net_boxes.items():
                    c.setChecked(n in d.get("nets", []))
            lk = self.w["link"]
            lk.clear()
            lk.addItem("(no link)", "")
            for p in self.win.doc.pages:
                lk.addItem("Page: " + p["name"], "page:" + p["id"])
            for pid, pname, aname, _it in self.win.anchors():
                lk.addItem("Anchor: %s  (%s)" % (aname, pname), "anchor:%s#%s" % (pid, aname))
            self.w["anchor"].setText(d.get("anchor", ""))
            for pid, pname, aname, _it in ():
                pass
            names = set()
            for lst in [p["items"] for p in self.win.doc.pages] + self.win.doc.all_master_lists():
                for it2 in lst:
                    if it2.get("ident"):
                        names.add(it2["ident"])
                    if it2.get("anchor"):
                        names.add(it2["anchor"])
            for n in sorted(names):
                lk.addItem("Show / hide: " + n, "toggle:" + n)
            groups = {}
            for it2 in self.win.target_list():
                if it2.get("group"):
                    groups.setdefault(it2["group"], []).append(it2)
            for gid, members in groups.items():
                lk.addItem("Show / hide the group of %d objects (%s...)"
                           % (len(members), KIND_NAMES.get(members[0]["kind"], "")), "toggle:" + gid)
            cur = d.get("link", "")
            idx = lk.findData(cur)
            if idx >= 0:
                lk.setCurrentIndex(idx)
            else:
                lk.setCurrentText(cur)
        finally:
            self.busy = False


class PageDialog(QDialog):
    def pick_sound(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a sound", "", pageitems.SOUNDS)
        if path:
            self.sound_path, self.sound_clear = path, False
            self.sound_label.setText(os.path.basename(path))

    def drop_sound(self):
        self.sound_path, self.sound_clear = "", True
        self.sound_label.setText("none")

    def __init__(self, parent, page, doc):
        super().__init__(parent)
        self.setWindowTitle("Page settings")
        f = QFormLayout(self)
        self.name = QLineEdit(page["name"])
        self.title = QLineEdit(page.get("title", ""))
        self.h = spin(100, 20000)
        self.h.setValue(page["h"])
        self.bg = ColorField(False)
        self.bg.set(page.get("bg", "#ffffff"))
        self.master = QComboBox()
        self.master.addItem("No master page", False)
        for mid, mname, _items in doc.all_masters():
            self.master.addItem(mname, mid if mid else True)
        cur = page.get("master", True)
        i = self.master.findData(cur)
        self.master.setCurrentIndex(i if i >= 0 else 1)
        snd = page.get("sound") or {}
        self.sound_path, self.sound_clear = "", False
        self.sound_label = QLabel(doc.assets[snd["asset"]]["name"] if snd.get("asset") in doc.assets else "none")
        sb = QPushButton("Choose...")
        sb.clicked.connect(self.pick_sound)
        sx = QPushButton("Remove")
        sx.clicked.connect(self.drop_sound)
        self.sound_row = QHBoxLayout()
        self.sound_row.addWidget(self.sound_label, 1)
        self.sound_row.addWidget(sb)
        self.sound_row.addWidget(sx)
        self.sound_loop = QCheckBox("Play it again and again")
        self.sound_loop.setChecked(snd.get("loop", True))
        self.protect = QCheckBox("Members only: ask visitors to sign in to see this page")
        self.protect.setChecked(bool(page.get("protect")))
        self.allow = QLineEdit(", ".join(page.get("allow") or []))
        self.allow.setPlaceholderText("Leave empty to let every member in, or list names")
        self.site = QLineEdit(doc.site_title)
        self.w = spin(320, 4000)
        self.w.setValue(doc.width)
        f.addRow("Page name", self.name)
        f.addRow("Browser title", self.title)
        f.addRow("Page height", self.h)
        f.addRow("Background", self.bg)
        f.addRow("Master page", self.master)
        f.addRow("Background sound", self.sound_row)
        f.addRow(self.sound_loop)
        f.addRow(self.protect)
        f.addRow("Allowed members", self.allow)
        f.addRow("Site name", self.site)
        f.addRow("Site width", self.w)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class PageTree(QTreeWidget):
    dropped = pyqtSignal()

    def dropEvent(self, e):
        super().dropEvent(e)
        self.dropped.emit()


class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.doc = Document()
        self.page_index = 0
        self._gifs = {}
        self.popup_preview = None
        from .pentool import NodeEditor, PenController
        self.pen = PenController(self)
        self.nodes = NodeEditor(self)
        self.master_mode = False
        self.master_edit = ""          # which master page 'Edit master page' is editing
        self.tool = "select"
        self.snap_on = True
        self.grid_on = True
        self.clip = []
        self.pending_style = None
        self._pix = {}
        self._derived = {}
        self.undo = QUndoStack(self)
        ColorField.scheme_source = lambda: self.doc.scheme
        self.scene = SiteScene(self)
        self.view = SiteView(self.scene, self)
        self.guide_drag = None            # a guide being dragged: {axis, value, old}
        self.dyn_lines = []               # dynamic guide lines to show while moving an object
        self.guide_snap = True
        self.dynamic_snap = True
        self.setCentralWidget(rulers.build(self, self.view))
        self.props = Properties(self)
        self.build_docks()
        self.build_actions()
        self._sel_guard = False
        self.scene.selectionChanged.connect(self.selection_changed)
        self.undo.cleanChanged.connect(self.update_title)
        self.resize(1280, 820)
        if path:
            self.open_path(path)
        else:
            self.reload()
        self.last = self.doc.snapshot()
        self.update_title()

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_shown", False):
            self._shown = True
            self.resizeDocks([self.toolbox_dock, self.assets_dock, self.props_dock],
                             [50, 170, 240], Qt.Horizontal)
            QTimer.singleShot(150, lambda: self.resizeDocks(
                [self.toolbox_dock, self.assets_dock, self.props_dock], [50, 170, 240],
                Qt.Horizontal))
            self.resizeDocks([self.task_dock], [90], Qt.Vertical)
            QTimer.singleShot(50, self.fit_page)
            QTimer.singleShot(120, lambda: setattr(self, "default_state",
                                                   self.saveState(STATE_VERSION)))
            QTimer.singleShot(220, self.restore_window_state)

    # -- structure -------------------------------------------------------
    def build_docks(self):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(self.props)
        d = QDockWidget("Objects", self)
        d.setObjectName("props")
        self.props_dock = d
        d.setWidget(sc)
        from PyQt5.QtWidgets import QSizePolicy as _SP
        sc.setSizePolicy(_SP.Ignored, _SP.Expanding)
        d.setMinimumWidth(190)          # drag the edge to make any panel as narrow as you like
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)   # lets the panel be dragged narrow
        self.addDockWidget(Qt.RightDockWidgetArea, d)

        w = QWidget()
        w.setStyleSheet("QPushButton{padding:3px 5px}")
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        self.master_btn = QPushButton("Edit master page")
        self.master_btn.setCheckable(True)
        self.master_btn.toggled.connect(self.toggle_master)
        v.addWidget(self.master_btn)
        self.pages = PageTree()
        self.pages.setHeaderHidden(True)
        self.pages.setDragDropMode(QTreeWidget.InternalMove)
        self.pages.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pages.customContextMenuRequested.connect(self.page_menu)
        self.pages.currentItemChanged.connect(self.page_picked)
        self.pages.dropped.connect(self.pages_reordered)
        self.pages.itemDoubleClicked.connect(lambda *_: self.page_settings())
        v.addWidget(self.pages)
        h = QHBoxLayout()
        for text, fn in (("Add", self.add_page), ("Copy", self.dup_page),
                         ("Delete", self.del_page)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            h.addWidget(b)
        v.addLayout(h)
        d2 = QDockWidget("Site", self)
        d2.setObjectName("pages")
        self.pages_dock = d2
        d2.setMinimumWidth(120)
        d2.setWidget(w)
        from PyQt5.QtWidgets import QTabWidget
        self.colour_panel = ColourPanel(self)
        self.swatches_panel = SwatchesPanel(self)
        self.transp_panel = TransparencyPanel(self)
        self.line_panel = LinePanel(self)
        self.colour_tabs = QTabWidget()
        self.colour_tabs.setUsesScrollButtons(True)
        self.colour_tabs.setElideMode(Qt.ElideRight)
        self.colour_tabs.tabBar().setExpanding(False)
        for panel, title in ((self.colour_panel, "Colour"), (self.swatches_panel, "Swatches"),
                             (self.transp_panel, "Transparency"), (self.line_panel, "Line")):
            self.colour_tabs.addTab(panel, title)
        self.transform_panel = TransformPanel(self)
        self.assets_panel = AssetsPanel(self)
        self.styles_panel = TextStylesPanel(self)
        self.fonts_panel = FontsPanel(self)
        self.quick_panel = QuickBuildPanel(self)
        self.comp_panel = CompositionsPanel(self)
        docks = {}
        for key, title, panel in (("colour", "Colour", self.colour_tabs),
                                  ("transform", "Transform", self.transform_panel),
                                  ("assets", "Assets", self.assets_panel),
                                  ("textstyles", "Text Styles", self.styles_panel),
                                  ("fonts", "Fonts", self.fonts_panel),
                                  ("quickbuild", "Quick Build", self.quick_panel),
                                  ("compositions", "Compositions", self.comp_panel)):
            dk = QDockWidget(title, self)
            dk.setObjectName(key)
            dk.setWidget(panel)
            docks[key] = dk
        self.colour_dock, self.transform_dock = docks["colour"], docks["transform"]
        self.assets_dock = docks["assets"]
        self.addDockWidget(Qt.RightDockWidgetArea, self.colour_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, d2)
        self.tabifyDockWidget(d2, d)
        self.addDockWidget(Qt.RightDockWidgetArea, self.transform_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.assets_dock)
        self.left_tabs = [docks["textstyles"], docks["fonts"], docks["quickbuild"],
                          docks["compositions"]]
        for dk in self.left_tabs:
            self.addDockWidget(Qt.LeftDockWidgetArea, dk)
            self.tabifyDockWidget(dk, self.assets_dock)
        for dk in [self.assets_dock] + self.left_tabs + [self.colour_dock, self.transform_dock]:
            dk.setMinimumWidth(120)
            dk.setMaximumWidth(16777215)    # and as wide as you like
            # the panel's own preferred width must not decide the dock's width
            dk.widget().setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        # the Transform block is small and stays small
        self.transform_dock.setMaximumHeight(120)
        docks["textstyles"].raise_()
        # Task Monitor along the bottom
        self.task_list = QListWidget()
        self.task_list.itemDoubleClicked.connect(self.goto_task)
        self.task_dock = QDockWidget("Task Monitor", self)
        self.task_dock.setObjectName("tasks")
        self.task_dock.setWidget(self.task_list)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.task_dock)
        self.task_dock.hide()           # out of the way until you ask for it
        self.task_timer = QTimer(self)
        self.task_timer.setSingleShot(True)
        self.task_timer.timeout.connect(self.refresh_tasks)
        self.tasks = []
        d2.raise_()

    def act(self, menu, text, fn, key=None, checkable=False):
        a = QAction(text, self)
        if key:
            a.setShortcut(QKeySequence(key))
        a.setCheckable(checkable)
        a.triggered.connect(fn)
        menu.addAction(a)
        return a

    def build_actions(self):
        mb = self.menuBar()
        self.menus = {}
        m = mb.addMenu("&File")
        self.menus["File"] = m
        self.act(m, "&Startup Assistant...", self.startup_assistant)
        self.act(m, "&New site", self.new_site, "Ctrl+N")
        self.act(m, "&Open...", self.open_dialog, "Ctrl+O")
        self.act(m, "Import &Serif WebPlus pack...", self.import_wpack)
        self.act(m, "&Save", self.save, "Ctrl+S")
        self.act(m, "Save &as...", self.save_as, "Ctrl+Shift+S")
        m.addSeparator()
        self.act(m, "Pre&view in browser", self.preview, "F5")
        self.act(m, "&Publish site to the web (FTP)...", self.publish_ftp, "Ctrl+Shift+U")
        self.act(m, "&Quick publish (changed files only)...",
                 lambda: self.publish_ftp(quick=True), "Ctrl+Shift+Y")
        self.act(m, "Estimate &download time...", self.estimate_download)
        self.act(m, "&Export website...", self.export_dialog, "Ctrl+E")
        from . import outputs
        self.act(m, "Publish as &PDF...", lambda: outputs.publish_pdf(self))
        self.act(m, "Export as &widget...", lambda: outputs.export_widget(self))
        self.act(m, "Export as pic&ture...", lambda: outputs.export_picture(self))
        self.act(m, "&Back up site...", self.backup_site)
        from . import formtools as ft
        self.act(m, "&View site online", lambda: ft.view_online(self))
        self.act(m, "Save &default settings", lambda: ft.save_defaults(self))
        m.addSeparator()
        self.act(m, "&Quit", self.close, "Ctrl+Q")

        m = mb.addMenu("&Edit")
        self.menus["Edit"] = m
        u = self.undo.createUndoAction(self, "&Undo")
        u.setShortcut(QKeySequence.Undo)
        r = self.undo.createRedoAction(self, "&Redo")
        r.setShortcut(QKeySequence.Redo)
        m.addAction(u)
        m.addAction(r)
        m.addSeparator()
        self.act(m, "Cu&t", self.cut, "Ctrl+X")
        self.act(m, "&Copy", self.copy, "Ctrl+C")
        self.act(m, "&Paste", self.paste, "Ctrl+V")
        self.act(m, "&Duplicate", self.duplicate, "Ctrl+D")
        self.act(m, "De&lete", self.delete, "Delete")
        self.act(m, "Select &all", self.select_all, "Ctrl+A")
        m.addSeparator()
        self.act(m, "Edit &text", self.edit_text, "F2")

        m = mb.addMenu("&Arrange")
        self.menus["Arrange"] = m
        self.act(m, "Bring to &front", lambda: self.arrange("front"), "Ctrl+Shift+]")
        self.act(m, "Bring &forward", lambda: self.arrange("up"), "Ctrl+]")
        self.act(m, "Send &backward", lambda: self.arrange("down"), "Ctrl+[")
        self.act(m, "Send to &back", lambda: self.arrange("back"), "Ctrl+Shift+[")
        m.addSeparator()
        self.act(m, "Centre on page", self.centre, "Ctrl+Shift+C")

        m = mb.addMenu("&View")
        self.menus["View"] = m
        self.act(m, "Zoom &in", lambda: self.view.set_zoom(self.view.zoom * 1.25), "Ctrl+=")
        self.act(m, "Zoom &out", lambda: self.view.set_zoom(self.view.zoom / 1.25), "Ctrl+-")
        self.act(m, "&Actual size", lambda: self.view.set_zoom(1.0), "Ctrl+0")
        self.act(m, "&Fit page", self.fit_page, "Ctrl+9")
        m.addSeparator()
        a = self.act(m, "Show &grid", self.toggle_grid, checkable=True)
        a.setChecked(True)
        a = self.act(m, "&Snap to grid", self.toggle_snap, checkable=True)
        a.setChecked(True)

        m = mb.addMenu("&Site")
        self.menus["Site"] = m
        self.act(m, "&Page settings...", self.page_settings, "Ctrl+Shift+P")
        self.act(m, "&Add page", self.add_page, "Ctrl+Shift+N")
        self.act(m, "&Duplicate page", self.dup_page)
        self.act(m, "De&lete page", self.del_page)

        m = mb.addMenu("&Help")
        self.menus["Help"] = m
        self.act(m, "Help &articles...", self.help_articles, "F1")
        self.act(m, "&About", lambda: QMessageBox.about(
            self, "About " + APP, "%s %s\nA website designer.\n\nMade by 4ThePeople Media."
            % (APP, __import__("sitewright").__version__)))

        dock = QDockWidget("Tools", self)
        dock.setObjectName("toolbox")
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setStyleSheet("QToolButton{border:1px solid transparent;border-radius:4px}"
                           "QToolButton:hover{background:#e3edf9}"
                           "QToolButton:checked{background:#cfe3fb;border:1px solid #6aa0e0}")
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(2)
        grp = QActionGroup(self)
        self.tool_actions = {}
        self.tool_buttons = []
        for n, (key, name, sc) in enumerate(TOOLS):
            a = QAction(tool_icon(key), name, self)
            a.setCheckable(True)
            if sc:
                a.setShortcut(sc)
            a.setToolTip("%s (%s)" % (name, sc) if sc else name)
            a.setStatusTip("%s tool: %s" % (name, "drag on the page to draw it"
                                            if key != "select" else "click and drag to select and move"))
            a.triggered.connect(lambda _, k=key: self.set_tool(k))
            grp.addAction(a)
            self.tool_actions[key] = a
            b = QToolButton()
            b.setDefaultAction(a)
            b.setIconSize(QSize(26, 26))
            b.setFixedSize(40, 38)
            self.tool_buttons.append(b)
        self.tool_grid = grid
        self.tool_actions["select"].setChecked(True)
        dock.setWidget(box)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.toolbox_dock = dock
        from PyQt5.QtWidgets import QTabWidget
        self.setTabPosition(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea, QTabWidget.North)
        self.setStyleSheet("QMainWindow::separator{width:2px;height:2px;background:#c9ced6}"
                           "QMainWindow::separator:hover{background:#6aa0e0}")
        # all the tools in one line: a single column on the left or right edge,
        # a single row along the top or bottom
        self.layout_toolbox(Qt.LeftDockWidgetArea)
        dock.dockLocationChanged.connect(self.layout_toolbox)
        # tool column on the far left, the studio tabs (one tab group) beside it
        self.splitDockWidget(dock, self.assets_dock, Qt.Horizontal)
        for dk in self.left_tabs:
            self.tabifyDockWidget(self.assets_dock, dk)
        self.left_tabs[0].raise_()
        self.build_more_actions()
        self.build_toolbars()
        self.build_statusbar()


    # -- WebPlus-style window furniture -----------------------------------
    def colour_button(self, label, key):
        b = QToolButton()
        b.setText(label)
        b.setPopupMode(QToolButton.InstantPopup)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        m = QMenu(b)

        def fill():
            m.clear()
            for i, c in enumerate(self.doc.scheme):
                m.addAction(swatch(c), "%d  %s" % (i + 1, c),
                            lambda _=False, c=c: self.set_prop(key, c))
            m.addSeparator()
            m.addAction("No colour", lambda: self.set_prop(key, ""))
            m.addAction("More colours...", lambda: self.pick_colour_for(key))
        m.aboutToShow.connect(fill)
        b.setMenu(m)
        return b

    def pick_colour_for(self, key):
        objs = self.selected()
        if not objs:
            return
        c = QColorDialog.getColor(QColor(objs[0].d.get(key) or "#ffffff"), self, "Colour")
        if c.isValid():
            self.set_prop(key, c.name())
            self.props.refresh()

    def set_toolbar_style(self, style):
        """icons: pictures only. both: picture with words. text: words only."""
        qt = {"icons": Qt.ToolButtonIconOnly, "both": Qt.ToolButtonTextBesideIcon,
              "text": Qt.ToolButtonTextOnly}[style]
        for tb in self.toolbars:
            tb.setToolButtonStyle(qt)
        for cb in self.colour_buttons:
            cb.setToolButtonStyle(qt)
        self.ws_label_action.setVisible(style != "icons")
        self.toolbar_style = style
        QSettings("4ThePeopleMedia", "Sitewright").setValue("toolbar_style", style)
        if hasattr(self, "toolbar_style_actions"):
            for k, a in self.toolbar_style_actions.items():
                a.setChecked(k == style)

    def build_toolbars(self):
        css = "QToolButton{padding:3px 4px;margin:0px}"
        self.toolbars = []
        self.colour_buttons = []
        t1 = QToolBar("Standard")
        t1.setObjectName("standard")
        t1.setMovable(False)
        t1.setStyleSheet(css)
        t1.setIconSize(QSize(22, 22))
        self.toolbars.append(t1)
        for item in (
                ("New", "new", "New site (Ctrl+N)", self.new_site),
                ("Open", "open", "Open a site (Ctrl+O)", self.open_dialog),
                ("Save", "save", "Save (Ctrl+S)", self.save), None,
                ("Cut", "cut", "Cut (Ctrl+X)", self.cut),
                ("Copy", "copy", "Copy (Ctrl+C)", self.copy),
                ("Paste", "paste", "Paste (Ctrl+V)", self.paste), None,
                ("Undo", "undo", "Undo (Ctrl+Z)", self.undo.undo),
                ("Redo", "redo", "Redo (Ctrl+Shift+Z)", self.undo.redo), None,
                ("Front", "front", "Bring to front", lambda: self.arrange("front")),
                ("Back", "back", "Send to back", lambda: self.arrange("back")),
                ("Group", "group", "Group objects (Ctrl+G)", self.group),
                ("Align left", "align-left", "Align left", lambda: self.align("l")),
                ("Centre", "align-centre", "Align centre", lambda: self.align("c")),
                ("Align right", "align-right", "Align right", lambda: self.align("r")), None):
            if item is None:
                t1.addSeparator()
                continue
            text, icon, tip, fn = item
            a = QAction(ui_icon(icon), text, self)
            a.setToolTip(tip)
            a.setStatusTip(tip)             # also shown in the status bar the moment you point
            a.triggered.connect(lambda _=False, f=fn: f())
            t1.addAction(a)
        for label, key, icon in (("Fill", "fill", "fill"), ("Line", "stroke", "line"),
                                 ("Text", "color", "text")):
            cb = self.colour_button(label, key)
            cb.setIcon(ui_icon(icon))
            cb.setIconSize(QSize(22, 22))
            cb.setToolTip("%s colour" % label)
            cb.setStatusTip("%s colour: choose a colour for the selected object" % label)
            t1.addWidget(cb)
            self.colour_buttons.append(cb)
        self.addToolBar(Qt.TopToolBarArea, t1)
        self.addToolBarBreak(Qt.TopToolBarArea)

        t2 = QToolBar("Site")
        t2.setObjectName("sitebar")
        t2.setMovable(False)
        t2.setStyleSheet(css)
        t2.setIconSize(QSize(22, 22))
        self.toolbars.append(t2)
        for item in (
                ("Page Properties", "page-properties",
                 "Page properties: name, title, size and colour (Ctrl+Shift+P)", self.page_settings),
                ("Site Properties", "site-properties", "Site properties: name, width and form email",
                 self.site_properties),
                ("Site Structure", "site-structure", "Show the site structure", self.show_site),
                ("Site Manager", "site-manager", "Site manager: pages, pictures and links",
                 self.site_manager),
                ("Colour Scheme", "colour-scheme", "Colour scheme designer: the 12 site colours",
                 self.scheme_dialog),
                ("User Details", "user", "Your name, company and contact details",
                 self.user_details),
                ("Options", "options", "Options: grid, snapping and text size",
                 self.options_dialog), None,
                ("Fit page", "fit", "Fit the page in the window (Ctrl+9)", self.fit_page),
                ("Preview", "preview", "Preview in your browser (F5)", self.preview),
                ("Publish", "publish", "Publish: upload the site to your web host (FTP)",
                 self.publish_ftp)):
            if item is None:
                t2.addSeparator()
                continue
            text, icon, tip, fn = item
            a = QAction(ui_icon(icon), text, self)
            a.setToolTip(tip)
            a.setStatusTip(tip)
            a.triggered.connect(lambda _=False, f=fn: f())
            t2.addAction(a)
        self.ws_label = QLabel(" Workspace ")
        self.ws_label_action = t2.addWidget(self.ws_label)
        self.ws_combo = QComboBox()
        self.ws_combo.activated.connect(self.workspace_picked)
        t2.addWidget(self.ws_combo)
        self.addToolBar(Qt.TopToolBarArea, t2)
        for tb in self.toolbars:
            tb.setMovable(True)             # grab the dotted handle and drag it anywhere
            tb.setFloatable(True)           # ...or pull it right off the window
            tb.setAllowedAreas(Qt.AllToolBarAreas)
        self.fill_workspaces()
        self.finish_menus()
        st = QSettings("4ThePeopleMedia", "Sitewright").value("toolbar_style", "icons")
        self.set_toolbar_style(st if st in ("icons", "both", "text") else "icons")
        # names that appear when you point at a button (drawn inside the window)
        self.hover_names = HoverNames(self)
        for tb in self.toolbars:
            for b in tb.findChildren(QToolButton):
                self.hover_names.watch(b)
        for b in self.tool_buttons:
            self.hover_names.watch(b)

    def build_statusbar(self):
        sb = self.statusBar()
        self.page_combo = QComboBox()
        self.page_combo.setMinimumWidth(130)
        self.page_combo.activated.connect(self.page_combo_picked)
        prev, nxt = QToolButton(), QToolButton()
        prev.setText("<")
        nxt.setText(">")
        prev.clicked.connect(lambda: self.step_page(-1))
        nxt.clicked.connect(lambda: self.step_page(1))
        sb.addWidget(prev)
        sb.addWidget(self.page_combo)
        sb.addWidget(nxt)
        self.hint = QLabel("Click to select. Ctrl-click to add to the selection. "
                           "Drag to select several objects.")
        sb.addWidget(self.hint, 1)
        self.task_btn = QToolButton()
        self.task_btn.setText("Checks")
        self.task_btn.setToolTip("Show the Task Monitor: things to fix before you publish")
        self.task_btn.setAutoRaise(True)
        self.task_btn.clicked.connect(self.show_tasks)
        sb.addPermanentWidget(self.task_btn)
        self.coords = QLabel("0, 0 px")
        self.coords.setMinimumWidth(110)
        sb.addPermanentWidget(self.coords)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(140)
        self.zoom_slider.valueChanged.connect(lambda v: self.view.set_zoom(v / 100))
        sb.addPermanentWidget(self.zoom_slider)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(44)
        sb.addPermanentWidget(self.zoom_label)
        self.refresh_pages()

    def show_coords(self, pt):
        self.coords.setText("%d, %d px" % (round(pt.x()), round(pt.y())))

    def refresh_tasks(self):
        self.tasks = taskcheck.check(self.doc)
        self.task_list.clear()
        if not self.tasks:
            self.task_list.addItem("No problems found.")
        for msg, pid, iid in self.tasks:
            it = QListWidgetItem(msg)
            it.setData(Qt.UserRole, (pid, iid))
            self.task_list.addItem(it)
        self.task_dock.setWindowTitle("Task Monitor (%d)" % len(self.tasks)
                                      if self.tasks else "Task Monitor")
        btn = getattr(self, "task_btn", None)
        if btn is not None:
            btn.setText("Checks (%d)" % len(self.tasks) if self.tasks else "Checks: none")

    def show_tasks(self):
        self.task_dock.show()
        self.task_dock.raise_()
        self.refresh_tasks()

    def goto_task(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        pid, iid = data
        if pid:
            j = self.page_index_of(pid)
            if j >= 0:
                self.page_index = j
                self.reload({iid} if iid else ())

    def side_refresh(self):
        if hasattr(self, "task_timer"):
            self.task_timer.start(250)
        for name in ("colour_panel", "swatches_panel", "transp_panel", "line_panel",
                     "transform_panel", "assets_panel", "styles_panel"):
            panel = getattr(self, name, None)
            if panel is not None:
                panel.refresh()

    def page_combo_picked(self, i):
        pid = self.page_combo.itemData(i)
        j = self.page_index_of(pid)
        if j >= 0 and j != self.page_index:
            self.page_index = j
            self.reload()

    def step_page(self, step):
        i = self.page_combo.currentIndex() + step
        if 0 <= i < self.page_combo.count():
            self.page_combo.setCurrentIndex(i)
            self.page_combo_picked(i)

    def show_site(self):
        self.pages_dock.show()
        self.pages_dock.raise_()

    def insert_asset(self, aid):
        pm = self.pixmap(aid)
        if pm is None or pm.isNull():
            return
        k = min(1.0, 400 / pm.width())
        d = new_item("image", 40, 40, asset=aid, w=round(pm.width() * k),
                     h=round(pm.height() * k))
        self.target_list().append(d)
        self.reload({d["id"]})
        self.commit_if_changed("Place picture")

    def add_assets(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add pictures", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg)")
        for path in paths:
            self.doc.add_asset(path)
        self.side_refresh()

    def members_dialog(self):
        from .phpgen import hash_password
        dlg = QDialog(self)
        dlg.setWindowTitle("Members and protected pages")
        dlg.resize(460, 420)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("People who can sign in to members-only pages. Passwords are "
                           "scrambled as soon as you type them and are never saved in the file."))
        lst = QListWidget()
        v.addWidget(lst, 1)
        members = [dict(m) for m in self.doc.members]

        def fill():
            lst.clear()
            for m in members:
                lst.addItem(m["name"])
        fill()

        def add():
            name, ok = QInputDialog.getText(dlg, "New member", "User name:")
            name = name.strip()
            if not ok or not name or any(m["name"] == name for m in members):
                return
            pw, ok = QInputDialog.getText(dlg, "New member", "Password for %s:" % name,
                                          QLineEdit.Password)
            if ok and len(pw) >= 6:
                salt, h = hash_password(pw)
                members.append(dict(name=name, salt=salt, hash=h))
                fill()
            elif ok:
                QMessageBox.information(dlg, APP, "Please use at least 6 characters.")

        def change():
            it = lst.currentItem()
            if it is None:
                return
            pw, ok = QInputDialog.getText(dlg, "New password", "New password for %s:" % it.text(),
                                          QLineEdit.Password)
            if ok and len(pw) >= 6:
                salt, h = hash_password(pw)
                for m in members:
                    if m["name"] == it.text():
                        m["salt"], m["hash"] = salt, h

        def remove():
            it = lst.currentItem()
            if it is not None:
                members[:] = [m for m in members if m["name"] != it.text()]
                fill()
        row = QHBoxLayout()
        for text, fn in (("Add member...", add), ("Change password...", change), ("Remove", remove)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        prot = [p["name"] for p in self.doc.pages if p.get("protect")]
        v.addWidget(QLabel("Members-only pages: " + (", ".join(prot) if prot else
                           "none yet. Open Page Properties and tick \"Members only\".")))
        v.addWidget(QLabel("Your web host must run PHP for these pages to work."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec_() == QDialog.Accepted:
            self.doc.members = members
            self.commit_if_changed("Members")

    def list_dialog(self):
        import secrets
        if not self.doc.list_key:
            self.doc.list_key = secrets.token_hex(12)
            self.commit_if_changed("Mailing list key")
        base = (self.doc.seo.get("site_url") or "https://www.example.com").rstrip("/")
        url = "%s/subscribers.php?key=%s" % (base, self.doc.list_key)
        dlg = QDialog(self)
        dlg.setWindowTitle("Mailing list address")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("After you publish, open this private address to see and download "
                           "your subscribers:"))
        e = QLineEdit(url)
        e.setReadOnly(True)
        e.setMinimumWidth(520)
        v.addWidget(e)
        v.addWidget(QLabel("Keep it to yourself: anyone with this address can see the list. "
                           "Each sign-up is also emailed to your form email address."))
        row = QHBoxLayout()
        cp = QPushButton("Copy")
        cp.clicked.connect(lambda: QApplication.clipboard().setText(url))
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        row.addWidget(cp)
        row.addStretch(1)
        row.addWidget(close)
        v.addLayout(row)
        dlg.exec_()

    def slider_studio(self):
        objs = [o for o in self.selected() if o.d["kind"] == "slider"]
        if not objs:
            return
        dlg = dialogs.SliderStudio(self, self.doc, objs[0].d)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply()
            objs[0].sync()
            self.props.refresh()
            self.commit_if_changed("Slider")

    def pick_asset_prop(self, key):
        objs = [o for o in self.selected() if o.d["kind"] == "image"]
        if not objs:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a picture", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp)")
        if path:
            aid = self.doc.add_asset(path)
            for o in objs:
                o.d[key] = aid
                if key == "hover_asset" and o.d.get("hover_effect") not in ("swap", "fade"):
                    o.d["hover_effect"] = "swap"
                if key == "lightbox_asset":
                    o.d["lightbox"] = True
            self.props.refresh()
            self.commit_if_changed("Picture")

    def save_composition(self):
        objs = self.selected()
        if not objs:
            QMessageBox.information(self, APP, "Select the objects you want to keep, then try again.")
            return
        name, ok = QInputDialog.getText(self, "Save composition", "Name for this composition:")
        name = name.strip()
        if not ok or not name:
            return
        items = [copy.deepcopy(o.d) for o in objs]
        x0 = min(i["x"] for i in items)
        y0 = min(i["y"] for i in items)
        for i in items:
            i["x"] -= x0
            i["y"] -= y0
        compositions.save(name, items, self.doc.assets)
        self.comp_panel.refresh(force=True)
        self.statusBar().showMessage("Saved composition '%s'" % name, 6000)

    def insert_composition(self, path):
        try:
            comp = compositions.load(path)
        except (OSError, ValueError):
            return
        mapping = {}
        for old, a in comp.get("assets", {}).items():
            aid = new_id()
            self.doc.assets[aid] = dict(a)
            mapping[old] = aid
        lst = self.target_list()
        y0 = max([d["y"] + d["h"] for d in lst] + [10]) + 30
        groups, ids = {}, set()
        for it in comp["items"]:
            it["id"] = new_id()
            if it.get("group"):
                it["group"] = groups.setdefault(it["group"], new_id())
            remap_assets(it, mapping)
            it["x"] += 40
            it["y"] += y0
            lst.append(it)
            ids.add(it["id"])
        page = self.cur_page()
        bottom = max([i["y"] + i["h"] for i in comp["items"]] + [0]) + 40
        if not self.master_mode and bottom > page["h"]:
            page["h"] = bottom
        self._pix = {}
        self.reload(ids)
        self.commit_if_changed("Insert composition")

    def seo_dialog(self):
        page = self.cur_page()
        if page.get("type") == "link":
            return
        dlg = dialogs.SeoDialog(self, self.doc, page)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply()
            self.reload()
            self.commit_if_changed("Search engine settings")

    def feed_dialog(self):
        dlg = dialogs.FeedDialog(self, self.doc)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply()
            self.commit_if_changed("RSS feed")

    def youtube_dialog(self):
        objs = [o for o in self.selected() if o.d["kind"] == "video"]
        dlg = dialogs.YouTubeDialog(self, objs[0].d if objs else None)
        if dlg.exec_() != QDialog.Accepted:
            return
        vals = dlg.values()
        if objs:
            for o in objs:
                o.d.update(vals)
                o.sync()
            self.props.refresh()
            self.commit_if_changed("YouTube video")
        else:
            self.pending_style = vals
            self.set_tool("video")
            self.statusBar().showMessage("Drag on the page to place the video", 5000)

    def form_designer(self):
        dlg = dialogs.FormDesigner(self, self.doc)
        if dlg.exec_() != QDialog.Accepted:
            return
        dlg.apply_mail()
        lst = self.target_list()
        y0 = max([d["y"] + d["h"] for d in lst] + [10]) + 30
        items, bottom = dlg.build(60, y0)
        lst.extend(items)
        page = self.cur_page()
        if not self.master_mode and bottom + 40 > page["h"]:
            page["h"] = bottom + 40
        self.reload({d["id"] for d in items})
        self.commit_if_changed("Form")

    def insert_symbol(self):
        dlg = dialogs.SymbolDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.chosen:
            return
        objs = [o for o in self.selected() if "text" in o.d]
        if not objs:
            QApplication.clipboard().setText(dlg.chosen)
            self.statusBar().showMessage("Copied %s - paste it into a text box" % dlg.chosen, 5000)
            return
        for o in objs:
            o.d["text"] += dlg.chosen
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Insert symbol")

    def html_source(self):
        page = self.cur_page()
        if page.get("type") == "link":
            return
        dialogs.SourceDialog(self, export.page_source(self.doc, page["id"], False)).exec_()

    def help_articles(self, start=0):
        dialogs.HelpDialog(self, start).exec_()

    def backup_site(self):
        import zipfile
        path, _ = QFileDialog.getSaveFileName(self, "Back up the site", "site-backup.zip",
                                              "Zip file (*.zip)")
        if not path:
            return
        tmp = tempfile.mkdtemp(prefix="sitewright-bak-")
        proj = os.path.join(tmp, "project.sitewright")
        self.doc.save(proj)
        self.doc.path = self.doc.path     # saving a backup does not rename the open site
        site = os.path.join(tmp, "site")
        export.export_site(self.doc, site)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(proj, "project.sitewright")
            for root, _d, names in os.walk(site):
                for n in names:
                    ap = os.path.join(root, n)
                    z.write(ap, "site/" + os.path.relpath(ap, site))
        self.statusBar().showMessage("Backup saved to " + path, 8000)

    def anchors(self):
        for p in self.doc.pages:
            for it in p["items"]:
                if it.get("anchor"):
                    yield p["id"], p["name"], it["anchor"], it

    def anchor_manager(self):
        links = [it.get("link", "") for p in self.doc.pages for it in p["items"]]
        dlg = QDialog(self)
        dlg.setWindowTitle("Anchor Manager")
        dlg.resize(520, 340)
        v = QVBoxLayout(dlg)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Anchor", "Page", "Object", "Links to it"])
        tree.setRootIsDecorated(False)
        for pid, pname, name, it in self.anchors():
            n = sum(1 for lk in links if lk == "anchor:%s#%s" % (pid, name))
            row = QTreeWidgetItem([name, pname, KIND_NAMES.get(it["kind"], it["kind"]), str(n)])
            row.setData(0, Qt.UserRole, (pid, it["id"]))
            tree.addTopLevelItem(row)
        for i in range(4):
            tree.resizeColumnToContents(i)

        def go(row, _col=0):
            pid, iid = row.data(0, Qt.UserRole)
            dlg.accept()
            self.goto_task(type("T", (), {"data": lambda s, r: (pid, iid)})())
        tree.itemDoubleClicked.connect(go)
        v.addWidget(tree)
        v.addWidget(QLabel("Name an object in Objects > Hyperlink > Anchor, then link to it "
                           "from any other object. Double-click a row to go there."))
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        dlg.exec_()

    def spell_check(self):
        if not spell.available():
            QMessageBox.information(self, APP, "The spell checker needs the 'aspell' program, "
                                    "which is not installed.")
            return
        dlg = spell.SpellDialog(self, self.doc, lambda label: self.after_text_edit(label))
        dlg.exec_()

    def after_text_edit(self, label):
        self.reload()
        self.commit_if_changed(label)

    def estimate_download(self):
        import os
        import re as _re
        out = publish.export_temp(self.doc, export.export_site)
        files = export.page_files(self.doc)
        css = os.path.getsize(os.path.join(out, "style.css"))
        dlg = QDialog(self)
        dlg.setWindowTitle("Estimated download time")
        dlg.resize(520, 300)
        v = QVBoxLayout(dlg)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Page", "Size", "56 Kbps modem", "1 Mbps"])
        tree.setRootIsDecorated(False)
        for p in self.doc.pages:
            f = files.get(p["id"])
            if p.get("type") == "link" or not f:
                continue
            path = os.path.join(out, f)
            html_txt = open(path, encoding="utf-8").read()
            size = os.path.getsize(path) + css
            for img in set(_re.findall(r'images/([^"\')]+)', html_txt)):
                ip = os.path.join(out, "images", img)
                if os.path.exists(ip):
                    size += os.path.getsize(ip)
            tree.addTopLevelItem(QTreeWidgetItem([
                p["name"], "%.0f KB" % (size / 1024), "%.1f s" % (size * 8 / 56000),
                "%.1f s" % (size * 8 / 1000000)]))
        for i in range(4):
            tree.resizeColumnToContents(i)
        v.addWidget(tree)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        dlg.exec_()

    def apply_text_style(self, props):
        n = 0
        for o in self.selected():
            d = o.d
            if "size" not in d:
                continue
            for k in ("size", "bold", "italic"):
                if k in props:
                    d[k] = props[k]
            if "ci" in props:
                d["color"] = self.doc.scheme[props["ci"]]
            if "font" in props:
                d["font"] = props["font"]
            o.sync()
            n += 1
        if n:
            self.props.refresh()
            self.commit_if_changed("Text style")

    def insert_block(self, name):
        items, h = templates.block(name, self.doc.width)
        lst = self.target_list()
        y0 = max([d["y"] + d["h"] for d in lst] + [10]) + 30
        ids = set()
        for d in items:
            d["x"] += 40
            d["y"] += y0
            lst.append(d)
            ids.add(d["id"])
        page = self.cur_page()
        if not self.master_mode and y0 + h + 40 > page["h"]:
            page["h"] = y0 + h + 40
        self.reload(ids)
        self.commit_if_changed("Quick build: " + name)

    def site_properties(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Site properties")
        f = QFormLayout(dlg)
        name = QLineEdit(self.doc.site_title)
        width = spin(320, 4000)
        width.setValue(self.doc.width)
        mail = QLineEdit(self.doc.form_email)
        f.addRow("Site name", name)
        f.addRow("Site width (px)", width)
        f.addRow("Form email address", mail)
        b = QPushButton("Colour scheme...")
        b.clicked.connect(self.scheme_dialog)
        f.addRow(b)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec_() == QDialog.Accepted:
            self.doc.site_title = name.text() or self.doc.site_title
            self.doc.width = width.value()
            self.doc.form_email = mail.text().strip()
            self.reload()
            self.commit_if_changed("Site properties")

    def site_manager(self, start="pages"):
        """The Site Manager: pages, hyperlinks, fonts, files and text in tabs."""
        from .managers import SiteManagerDialog
        d = getattr(self, "_site_manager", None)
        if d is not None:
            d.deleteLater()
        d = self._site_manager = SiteManagerDialog(self, start)
        d.show()
        d.raise_()
        d.activateWindow()

    def insert_html_page(self, parent=""):
        from .htmlpage import HtmlPageDialog, new_html_page
        page = new_html_page("HTML page %d" % (sum(1 for q in self.doc.pages if q.get("type") == "html") + 1))
        page["parent"] = parent
        dlg = HtmlPageDialog(self, page, creating=True)
        if dlg.exec_() != QDialog.Accepted:
            return
        dlg.apply()
        self.doc.pages.append(page)
        self.normalize_pages()
        self.page_index = self.page_index_of(page["id"])
        self.reload()
        self.commit_if_changed("Insert HTML page")

    def html_page_properties(self):
        """Tools > Site Manager > HTML Page Properties: the page you are on, or pick one."""
        cur = self.cur_page()
        if cur.get("type") == "html":
            return self.html_page_properties_for(cur)
        pages = [p for p in self.doc.pages if p.get("type") == "html"]
        if not pages:
            r = QMessageBox.question(self, APP, "There are no HTML pages yet. Add one now?")
            if r == QMessageBox.Yes:
                self.insert_html_page()
            return
        if len(pages) == 1:
            return self.html_page_properties_for(pages[0])
        name, ok = QInputDialog.getItem(self, "HTML Page Properties", "Which page?",
                                        [p["name"] for p in pages], 0, False)
        if ok:
            self.html_page_properties_for(next(p for p in pages if p["name"] == name))

    def html_page_properties_for(self, page):
        from .htmlpage import HtmlPageDialog
        dlg = HtmlPageDialog(self, page)
        if dlg.exec_() == QDialog.Accepted:
            dlg.apply()
            self.normalize_pages()
            self.reload()
            self.commit_if_changed("HTML page properties")

    def master_manager(self):
        from .managers import MasterManagerDialog
        MasterManagerDialog(self).exec_()

    def publish_ftp(self, checked=False, quick=False, ftp_factory=None):
        if self.tasks:
            r = QMessageBox.question(
                self, APP, "The Task Monitor lists %d thing(s) to check. Publish anyway?"
                % len(self.tasks))
            if r != QMessageBox.Yes:
                return
        st = QSettings("4ThePeopleMedia", "Sitewright")
        t = publish.Target(st.value("ftp/host", ""), int(st.value("ftp/port", 21) or 21),
                           st.value("ftp/user", ""), "", st.value("ftp/dir", "/"),
                           str(st.value("ftp/tls", "true")).lower() in ("true", "1"))
        sd = publish.SettingsDialog(self, t)
        if sd.exec_() != QDialog.Accepted:
            return
        t = sd.target()
        if not t.host:
            QMessageBox.information(self, APP, "Enter the web host's FTP server name.")
            return
        st.setValue("ftp/host", t.host)
        st.setValue("ftp/port", t.port)
        st.setValue("ftp/user", t.user)
        st.setValue("ftp/dir", t.directory)
        st.setValue("ftp/tls", t.tls)
        outdir = publish.export_temp(self.doc, export.export_site)
        self.statusBar().showMessage("Exporting site...", 3000)
        hashes = publish.file_hashes(outdir)
        key = "%s|%s" % (t.host, t.directory)
        only = None
        last = self.doc.publish.get(key)
        if quick and last:
            only = {rel for rel, h in hashes.items() if last.get(rel) != h}
            if not only:
                QMessageBox.information(self, APP, "Nothing has changed since the last publish.")
                return
        dlg = publish.FileOperationDialog(self, t, outdir, ftp_factory, only)
        dlg.start()
        dlg.exec_()
        if dlg.result_ok:
            self.doc.publish[key] = hashes
            self.statusBar().showMessage(
                "Published %s to %s" % ("%d changed file(s)" % len(only) if only is not None
                                        else "the whole site", t.host), 8000)
        elif dlg.message and dlg.message != "Cancelled":
            QMessageBox.warning(self, APP, "Publishing stopped:\n%s" % dlg.message)

    def user_details(self):
        dlg = UserDetailsDialog(self, self.doc.user)
        if dlg.exec_() == QDialog.Accepted:
            self.doc.user = dlg.values()
            self.commit_if_changed("User details")

    def options_dialog(self):
        dlg = OptionsDialog(self, self.grid_on, self.snap_on, saved_ui_pt())
        if dlg.exec_() == QDialog.Accepted:
            self.grid_on, self.snap_on = dlg.grid.isChecked(), dlg.snap.isChecked()
            self.set_ui_pt(dlg.pt.value())
            self.scene.update()

    def bullets_dialog(self):
        """Choose a list style for the chosen text boxes: every line becomes one item."""
        from .textlayout import LIST_STYLES
        objs = [o for o in self.selected() if o.d["kind"] == "text"]
        if not objs:
            self.statusBar().showMessage("Select a text box first", 4000)
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Bullets and numbering")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Every line of the text becomes one item in the list."))
        lst = QListWidget()
        cur = objs[0].d.get("listtype", "")
        for value, name, *_ in LIST_STYLES:
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, value)
            lst.addItem(it)
            if value == cur:
                lst.setCurrentItem(it)
        lst.itemDoubleClicked.connect(lambda _: dlg.accept())
        v.addWidget(lst)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec_() == QDialog.Accepted and lst.currentItem() is not None:
            self.set_prop("listtype", lst.currentItem().data(Qt.UserRole))

    def clear_text_format(self):
        """Put the selected text objects back to the plain default look (words stay)."""
        from .model import TEXT_BASE
        n = 0
        for o in self.selected():
            if "text" not in o.d or o.d["kind"] not in ("text", "button", "marquee"):
                continue
            for k, v in TEXT_BASE.items():
                if k in o.d:
                    o.d[k] = v
            o.sync()
            n += 1
        if n:
            self.props.refresh()
            self.commit_if_changed("Clear text formatting")

    def change_case(self, mode):
        n = 0
        for o in self.selected():
            t = o.d.get("text")
            if not t:
                continue
            o.d["text"] = {
                "lower": t.lower(), "upper": t.upper(), "title": t.title(),
                "sentence": (t[:1].upper() + t[1:].lower()) if t else t,
                "toggle": t.swapcase(),
            }[mode]
            o.sync()
            n += 1
        if n:
            self.props.refresh()
            self.commit_if_changed("Change case")

    def table_edit(self, what):
        for o in self.selected():
            d = o.d
            if d["kind"] != "table":
                continue
            r, c = d["rows"], d["cols"]
            r += {"row+": 1, "row-": -1}.get(what, 0)
            c += {"col+": 1, "col-": -1}.get(what, 0)
            if r < 1 or c < 1:
                continue
            self.set_table_dims(rows=r, cols=c)

    # -- right-click menus (laid out like WebPlus's own pop-up menus) -----
    def cact(self, menu, text, fn, checkable=False):
        """An action for a pop-up menu: owned by the menu, so it goes when the menu does,
        and with no shortcut of its own (the menu bar already owns the shortcuts)."""
        a = QAction(text, menu)
        a.setCheckable(checkable)
        a.triggered.connect(fn)
        menu.addAction(a)
        return a

    def canvas_menu(self, gpos, item, spos):
        from . import tablecore as tc
        m = QMenu(self)
        if item is None or not item.editable:
            self.page_context_menu(m)
        else:
            if not item.isSelected():
                for i in self.scene.selectedItems():
                    i.setSelected(False)
                item.setSelected(True)
            if item.d["kind"] == "table":
                local = item.mapFromScene(spos)
                r, c = item.cell_at(local)
                s = tc.clamp_sel(item.d)
                if not (s[0] <= r <= s[2] and s[1] <= c <= s[3]):
                    item.d["sel"] = [r, c, r, c]
                    item.update()
                    self.props.refresh_cell_range()
            self.object_context_menu(m, item.d["kind"])
        m.exec_(gpos)

    def object_context_menu(self, m, kind):
        from . import formtools as ft
        self.cact(m, "Cu&t", self.cut)
        self.cact(m, "&Copy", self.copy)
        self.cact(m, "&Paste", self.paste)
        self.cact(m, "&Duplicate", self.duplicate)
        self.cact(m, "De&lete", self.delete)
        m.addSeparator()
        if kind == "shape":
            self.cact(m, "Edit &points", self.edit_points)
        self.cact(m, "Edit &properties...", self.show_properties)
        self.cact(m, "&Hyperlink...", self.focus_link)
        self.cact(m, "HTML &source...", self.html_source)
        self.cact(m, "&Actions...", self.edit_actions)
        self.cact(m, "Pop-up &menu...", lambda: ft.popup_menu(self))
        if kind == "image":
            self.cact(m, "&Frame properties...", lambda: ft.frame_properties(self))
        self.cact(m, "CSS &properties...", self.edit_css)
        self.cact(m, "HTML a&ttributes...", self.edit_attrs)
        m.addSeparator()
        from . import fxdialogs
        self.cact(m, "Filter &effects...", lambda: fxdialogs.filter_effects(self))
        if kind == "image":
            self.cact(m, "&Watermark...", lambda: fxdialogs.watermark(self))
            self.cact(m, "Picture &transparency...", lambda: fxdialogs.transparent_colour(self))
            self.cact(m, "Crop to &shape...", lambda: fxdialogs.crop_shape(self))
            from . import photolab
            self.cact(m, "Edit &photo (PhotoLab)...", lambda: photolab.edit_photo(self))
        m.addSeparator()
        if kind == "table":
            self.table_context_menu(m.addMenu("&Table"))
        if kind in ("text", "button", "marquee"):
            t = m.addMenu("T&ext")
            self.cact(t, "Edit &text", self.edit_text)
            cs = t.addMenu("Change &case")
            for label, mode in (("Sentence case", "sentence"), ("lower case", "lower"),
                                ("UPPER CASE", "upper"), ("Title Case", "title"),
                                ("tOGGLE cASE", "toggle")):
                self.cact(cs, label, lambda _=False, md=mode: self.change_case(md))
            self.cact(t, "Insert &symbol...", self.insert_symbol)
            self.cact(t, "C&lear text formatting", self.clear_text_format)
            self.cact(t, "&Bullets and numbering...", self.bullets_dialog)
            ti = t.addMenu("&Insert")
            for label, kind in (("Date or time...", "datetime"), ("Page info...", "page"),
                                ("Site info...", "site"), ("Variable...", "variable")):
                self.cact(ti, label, lambda _=False, k=kind: self.insert_info(k))
            self.cact(ti, "Fill with placeholder text...", self.insert_placeholder)
        if kind == "image":
            self.cact(m, "&Replace picture...", self.replace_picture)
        a = m.addMenu("&Arrange")
        for label, how in (("Send to back", "back"), ("Bring to front", "front"),
                           ("Back one", "down"), ("Forward one", "up")):
            self.cact(a, label, lambda _=False, h=how: self.arrange(h))
        a.addSeparator()
        al = a.addMenu("Align objects")
        for text, how in (("Left", "l"), ("Centre", "c"), ("Right", "r"),
                          ("Top", "t"), ("Middle", "m"), ("Bottom", "b")):
            self.cact(al, text, lambda _=False, h=how: self.align(h))
        sz = a.addMenu("Size objects")
        for text, how in (("Same width", "w"), ("Same height", "h"), ("Same size", "wh")):
            self.cact(sz, text, lambda _=False, h=how: self.same_size(h))
        a.addSeparator()
        self.cact(a, "Set object order...", lambda: pagetools.set_object_order(self))
        at = a.addMenu("Attach to text")
        self.cact(at, "Attach under the text box", lambda: pagetools.attach(self, "bottom"))
        self.cact(at, "Attach beside it", lambda: pagetools.attach(self, "top"))
        self.cact(at, "Detach from text", lambda: pagetools.detach(self))
        self.cact(a, "Select parent", lambda: pagetools.select_parent(self))
        a.addSeparator()
        self.cact(a, "Group objects", self.group)
        self.cact(a, "Ungroup objects", self.ungroup)
        self.cact(a, "Lock / unlock object", self.toggle_lock)
        f = m.addMenu("&Flip and rotate")
        self.cact(f, "Flip horizontal", lambda: self.flip("fx"))
        self.cact(f, "Flip vertical", lambda: self.flip("fy"))
        self.cact(f, "Rotate left", lambda: self.rotate(-90))
        self.cact(f, "Rotate right", lambda: self.rotate(90))

    def table_context_menu(self, t):
        """The Table submenu: AutoFormat, Insert, Select, Delete, Merge, sizes, Cell properties, Sort."""
        self.cact(t, "AutoFormat...", self.table_autoformat)
        t.addSeparator()
        ins = t.addMenu("Insert")
        self.cact(ins, "Rows...", lambda: self.table_insert("rows"))
        self.cact(ins, "Columns...", lambda: self.table_insert("cols"))
        sel = t.addMenu("Select")
        self.cact(sel, "Row(s)", lambda: self.table_select("rows"))
        self.cact(sel, "Column(s)", lambda: self.table_select("cols"))
        self.cact(sel, "All", lambda: self.table_select("all"))
        de = t.addMenu("Delete")
        self.cact(de, "Row(s)", lambda: self.table_delete("rows"))
        self.cact(de, "Column(s)", lambda: self.table_delete("cols"))
        self.cact(de, "All (the whole table)", self.delete)
        t.addSeparator()
        self.cact(t, "Merge cells", self.table_merge)
        self.cact(t, "Separate cells", self.table_separate)
        t.addSeparator()
        self.cact(t, "Evenly distribute rows", lambda: self.table_sizes("dist_rows"))
        self.cact(t, "Evenly distribute columns", lambda: self.table_sizes("dist_cols"))
        t.addSeparator()
        self.cact(t, "AutoFit column(s) to contents", lambda: self.table_sizes("fit_cols"))
        self.cact(t, "AutoFit row(s) to contents", lambda: self.table_sizes("fit_rows"))
        t.addSeparator()
        self.cact(t, "Set column width(s)...", lambda: self.table_sizes("set_cols"))
        self.cact(t, "Set row height(s)...", lambda: self.table_sizes("set_rows"))
        t.addSeparator()
        self.cact(t, "Fill down", lambda: self.table_fill("down"))
        self.cact(t, "Fill right", lambda: self.table_fill("right"))
        t.addSeparator()
        self.cact(t, "Cell properties...", self.table_cell_props)
        self.cact(t, "Sort...", self.table_sort)

    def page_context_menu(self, m):
        self.cact(m, "&Paste", self.paste)
        self.cact(m, "Paste in &place", self.paste_in_place)
        self.cact(m, "Paste as &unformatted text", self.paste_plain)
        m.addSeparator()
        ins = m.addMenu("&Insert")
        for kind, label in (("text", "Text"), ("image", "Picture..."), ("rect", "Rectangle"),
                            ("ellipse", "Ellipse"), ("button", "Button"), ("table", "Table"),
                            ("gallery", "Photo gallery"), ("video", "Video"), ("map", "Map")):
            self.cact(ins, label, lambda _=False, k=kind: self.set_tool(k))
        self.cact(ins, "Calendar...", self.insert_calendar)
        self.cact(ins, "RSS reader", lambda: self.set_tool("rssreader"))
        self.cact(ins, "Picture library...", lambda: StarterDialog(self).exec_())
        m.addSeparator()
        self.cact(m, "&Page properties...", self.page_settings)
        self.cact(m, "View &HTML source", self.html_source)
        v = m.addMenu("&View")
        g = self.cact(v, "Show grid", lambda on: self.toggle_grid(on), checkable=True)
        g.setChecked(self.grid_on)
        sn = self.cact(v, "Snap to grid and guides", lambda on: self.toggle_snap(on), checkable=True)
        sn.setChecked(self.snap_on)
        self.cact(v, "Fit page", self.fit_page)
        self.cact(v, "Show hidden objects", self.toggle_hidden_objects_menu, checkable=False)

    def toggle_rulers(self, on):
        rulers.show_rulers(self, on)
        QSettings("4ThePeopleMedia", "Sitewright").setValue("rulers", bool(on))

    def set_snapping(self, attr, on):
        setattr(self, attr, bool(on))
        if attr == "dynamic_snap" and not on:
            self.dyn_lines = []
            self.scene.update()

    def toggle_hidden_objects_menu(self):
        self.hidden_action.setChecked(not self.hidden_action.isChecked())
        self.toggle_hidden_objects()

    def set_overflow(self, value):
        """What a text box does with words that do not fit. A fixed box height is kept."""
        objs = [o for o in self.selected() if o.d["kind"] == "text"]
        if not objs:
            self.statusBar().showMessage("Select a text box first", 4000)
            return
        for o in objs:
            o.d["autoh"] = False
            o.d["overflow"] = value
            o.prepareGeometryChange()
            o.sync()
        self.props.refresh()
        self.scene.update()
        self.commit_if_changed("Overflowing text")

    def fit_text_to_path(self):
        """Turn the chosen text box into artistic text set along a curve."""
        from .model import DEFAULTS
        objs = [o for o in self.selected() if o.d["kind"] in ("text", "button", "marquee")]
        if not objs:
            self.statusBar().showMessage("Select a text box first", 4000)
            return
        for o in objs:
            d = o.d
            for k, v in DEFAULTS["arttext"].items():
                if k not in ("text", "w", "h"):
                    d.setdefault(k, v)
            d["kind"] = "arttext"
            d["shape"], d["curve"] = "arc", 45
            d["h"] = max(d["h"], int(d["size"] * 3.2))
            d["w"] = max(d["w"], 300)
        self.reload({o.d["id"] for o in objs})
        self.commit_if_changed("Fit text to path")

    def insert_info(self, kind):
        from .insertinfo import run_info
        run_info(self, kind)

    def insert_placeholder(self):
        from .insertinfo import run_placeholder
        run_placeholder(self)

    def proof_reader(self):
        from .proofread import ProofReaderDialog
        ProofReaderDialog(self).exec_()

    def thesaurus_dialog(self):
        from .thesaurus import ThesaurusDialog
        word = ""
        box = self.props.w.get("text")
        if box is not None and box.isVisible():
            word = box.textCursor().selectedText().strip()
        if len(word.split()) != 1:
            word = ""
        ThesaurusDialog(self, word).exec_()

    def find_replace(self):
        from .findreplace import FindReplaceDialog
        d = getattr(self, "_find_dialog", None)
        if d is None:
            d = self._find_dialog = FindReplaceDialog(self)
        d.show()
        d.raise_()
        d.activateWindow()
        d.find.setFocus()
        d.find.selectAll()

    def edit_actions(self):
        objectprops.edit_rows(self, "actions", objectprops.ActionsDialog, objectprops.clean_actions,
                              "Actions", True)

    def edit_css(self):
        objectprops.edit_rows(self, "cssp", objectprops.CssDialog, objectprops.clean_css, "CSS properties")

    def edit_attrs(self):
        objectprops.edit_rows(self, "attrs", objectprops.AttrsDialog, objectprops.clean_attrs, "HTML attributes")

    def show_properties(self):
        """Edit properties: a pop-up with tabs for the chosen object."""
        from .propdialog import PropertiesDialog
        objs = [o for o in self.selected()]
        if not objs:
            self.statusBar().showMessage("Select an object first", 4000)
            return
        o = objs[0]
        dlg = PropertiesDialog(self, o.d)
        if dlg.exec_() == QDialog.Accepted and dlg.apply():
            textlayout.fit_height(o.d)
            o.sync()
            self.reload({o.d["id"]})
            self.commit_if_changed("Edit properties")

    def focus_link(self):
        self.show_properties()
        w = self.props.w.get("link")
        if w is not None:
            w.setFocus()
            if hasattr(w, "selectAll"):
                w.selectAll()

    def table_insert(self, what):
        from . import tablecore as tc
        objs = self.tables()
        if not objs:
            return
        d0 = objs[0].d
        sel = tc.clamp_sel(d0)
        dlg = QDialog(self)
        dlg.setWindowTitle("Insert " + ("rows" if what == "rows" else "columns"))
        form = QFormLayout(dlg)
        n = QSpinBox()
        n.setRange(1, 50)
        n.setValue(1)
        form.addRow("How many", n)
        where = QComboBox()
        where.addItems(["Before the chosen cells", "After the chosen cells"])
        where.setCurrentIndex(1)
        form.addRow("Where", where)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() != QDialog.Accepted:
            return
        after = where.currentIndex() == 1

        def run(d):
            s = tc.clamp_sel(d)
            if what == "rows":
                tc.insert_rows(d, (s[2] + 1) if after else s[0], n.value())
            else:
                tc.insert_cols(d, (s[3] + 1) if after else s[1], n.value())
        self.table_do("Insert " + what, run)
        self.props.refresh_cell_range()

    def table_fill(self, how):
        from . import tablecore as tc
        fn = tc.fill_down if how == "down" else tc.fill_right
        self.table_do("Fill " + how, lambda d: fn(d, *tc.clamp_sel(d)))

    # -- table tools (see tablecore.py) --------------------------------
    @property
    def table_marks(self):
        """The one selected table whose chosen cells are shown on screen."""
        sel = [o for o in self.scene.selectedItems()
               if isinstance(o, ItemObj) and o.d["kind"] == "table"]
        return sel[0].d if len(sel) == 1 else None

    def tables(self):
        return [o for o in self.selected() if o.d["kind"] == "table"]

    def table_do(self, label, fn):
        """Run fn(table dict) on each selected table, then redraw and make it one Undo step."""
        objs = self.tables()
        if not objs:
            self.statusBar().showMessage("Select a table first", 4000)
            return False
        done = False
        for o in objs:
            if fn(o.d) is not False:
                done = True
            o.sync()
        self.props.refresh()
        self.scene.update()
        if done:
            self.commit_if_changed(label)
        return done

    def table_sel_changed(self, i, v):
        from . import tablecore as tc
        order = (0, 2, 1, 3)           # rows from/to, cols from/to -> positions in d["sel"]
        for o in self.tables():
            s = tc.clamp_sel(o.d)
            s[order[i]] = v - 1
            o.d["sel"] = s
            tc.clamp_sel(o.d)
            o.update()

    def table_select(self, what):
        from . import tablecore as tc
        fn = {"rows": tc.select_rows, "cols": tc.select_cols, "all": tc.select_all}[what]
        for o in self.tables():
            fn(o.d)
            o.update()
        self.props.refresh_cell_range()

    def table_merge(self):
        from . import tablecore as tc
        self.table_do("Merge cells", lambda d: tc.merge_cells(d, *tc.clamp_sel(d)))

    def table_separate(self):
        from . import tablecore as tc
        self.table_do("Separate cells", lambda d: tc.separate_cells(d, *tc.clamp_sel(d)) > 0 or False)

    def table_delete(self, what):
        from . import tablecore as tc

        def run(d):
            r1, c1, r2, c2 = tc.clamp_sel(d)
            return tc.delete_rows(d, r1, r2) if what == "rows" else tc.delete_cols(d, c1, c2)
        if not self.table_do("Delete " + what, run):
            return
        self.props.refresh_cell_range()

    def table_sizes(self, what):
        from PyQt5.QtGui import QFontMetrics
        from . import tablecore as tc
        from .extras import font_for
        value = None
        if what in ("set_cols", "set_rows"):
            objs = self.tables()
            if not objs:
                self.statusBar().showMessage("Select a table first", 4000)
                return
            d0 = objs[0].d
            r1, c1, r2, c2 = tc.clamp_sel(d0)
            cur = int(d0["w"] * tc.fractions(d0, "colw", max(d0["cols"], 1))[c1]) if what == "set_cols" \
                else int(d0["h"] * tc.fractions(d0, "rowh", max(d0["rows"], 1))[r1])
            value, ok = QInputDialog.getInt(
                self, "Table", "Width of the chosen column(s), in pixels:" if what == "set_cols"
                else "Height of the chosen row(s), in pixels:", cur, 8, 4000)
            if not ok:
                return

        def run(d):
            r1, c1, r2, c2 = tc.clamp_sel(d)
            if what == "dist_rows":
                tc.distribute_rows(d)
            elif what == "dist_cols":
                tc.distribute_cols(d)
            elif what == "fit_cols":
                tc.autofit_cols(d, QFontMetrics(font_for(d)), c1, c2)
            elif what == "fit_rows":
                tc.autofit_rows(d, QFontMetrics(font_for(d)), r1, r2)
            elif what == "set_cols":
                tc.set_col_width(d, c1, c2, value)
            else:
                tc.set_row_height(d, r1, r2, value)
        self.table_do("Table sizes", run)

    def table_cell_props(self):
        from . import tablecore as tc
        objs = self.tables()
        if not objs:
            self.statusBar().showMessage("Select a table first", 4000)
            return
        d0 = objs[0].d
        r1, c1, r2, c2 = tc.clamp_sel(d0)
        cur = tc.cell_fmt(d0, r1, c1)
        dlg = QDialog(self)
        dlg.setWindowTitle("Cell properties")
        form = QFormLayout(dlg)
        form.addRow(QLabel("Changes the chosen cells: rows %d-%d, columns %d-%d"
                           % (r1 + 1, r2 + 1, c1 + 1, c2 + 1)))
        picked = {"fill": cur.get("fill", ""), "color": cur.get("color", "")}
        btns = {}

        def colour_row(key, label):
            b = QPushButton()
            btns[key] = b

            def paint():
                b.setText(picked[key] or "Not set")
                b.setStyleSheet("border-left:16px solid %s" % (picked[key] or "transparent"))

            def pick():
                c = QColorDialog.getColor(QColor(picked[key] or "#ffffff"), dlg)
                if c.isValid():
                    picked[key] = c.name()
                    paint()
            b.clicked.connect(pick)
            clr = QPushButton("Clear")
            clr.clicked.connect(lambda: (picked.__setitem__(key, ""), paint()))
            row = QHBoxLayout()
            row.addWidget(b, 1)
            row.addWidget(clr)
            form.addRow(label, row)
            paint()
        colour_row("fill", "Cell colour")
        colour_row("color", "Text colour")
        al = QComboBox()
        al.addItems(["As the table", "Left", "Centre", "Right"])
        al.setCurrentIndex({"left": 1, "center": 2, "right": 3}.get(cur.get("align", ""), 0))
        form.addRow("Text across", al)
        va = QComboBox()
        va.addItems(["As the table", "Top", "Middle", "Bottom"])
        va.setCurrentIndex({"top": 1, "middle": 2, "bottom": 3}.get(cur.get("valign", ""), 0))
        form.addRow("Text up and down", va)
        bold = QComboBox()
        bold.addItems(["As the table", "Bold", "Not bold"])
        bold.setCurrentIndex(0 if "bold" not in cur else (1 if cur["bold"] else 2))
        form.addRow("Bold", bold)
        ital = QComboBox()
        ital.addItems(["As the table", "Italic", "Not italic"])
        ital.setCurrentIndex(0 if "italic" not in cur else (1 if cur["italic"] else 2))
        form.addRow("Italic", ital)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() != QDialog.Accepted:
            return
        kw = dict(fill=picked["fill"] or None, color=picked["color"] or None,
                  align=[None, "left", "center", "right"][al.currentIndex()],
                  valign=[None, "top", "middle", "bottom"][va.currentIndex()],
                  bold=[None, True, False][bold.currentIndex()],
                  italic=[None, True, False][ital.currentIndex()])
        # False must be kept (it means "not bold"); only None clears a look
        self.table_do("Cell properties", lambda d: tc.set_fmt(d, *tc.clamp_sel(d), **kw))

    def table_sort(self):
        from . import tablecore as tc
        objs = self.tables()
        if not objs:
            self.statusBar().showMessage("Select a table first", 4000)
            return
        d0 = objs[0].d
        if d0.get("merges"):
            QMessageBox.information(self, APP, "Separate the merged cells first. A table "
                                    "with merged cells cannot be sorted.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Sort")
        form = QFormLayout(dlg)
        col = QComboBox()
        for j in range(max(d0["cols"], 1)):
            head = tc.text_at(d0, 0, j) if d0.get("header") else ""
            col.addItem("Column %d%s" % (j + 1, ("  (%s)" % head[:18]) if head else ""))
        col.setCurrentIndex(tc.clamp_sel(d0)[1])
        form.addRow("Sort by", col)
        order = QComboBox()
        order.addItems(["A to Z, smallest first", "Z to A, largest first"])
        form.addRow("Order", order)
        form.addRow(QLabel("The header row stays on top." if d0.get("header")
                           else "Every row is sorted (there is no header row)."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() == QDialog.Accepted:
            self.table_do("Sort table", lambda d: tc.sort_rows(d, col.currentIndex(),
                                                              order.currentIndex() == 0))

    def table_autoformat(self):
        from . import tablecore as tc
        if not self.tables():
            self.statusBar().showMessage("Select a table first", 4000)
            return
        name, ok = QInputDialog.getItem(self, "AutoFormat", "Look for the whole table:",
                                        list(tc.AUTOFORMATS), 0, False)
        if ok:
            self.table_do("AutoFormat", lambda d: tc.apply_autoformat(d, name))

    def insert_calendar(self):
        import datetime
        from . import tablecore as tc
        from .model import new_item
        dlg = QDialog(self)
        dlg.setWindowTitle("Calendar")
        form = QFormLayout(dlg)
        today = datetime.date.today()
        month = QComboBox()
        import calendar as cal_
        month.addItems([cal_.month_name[i] for i in range(1, 13)])
        month.setCurrentIndex(today.month - 1)
        year = QSpinBox()
        year.setRange(1900, 2200)
        year.setValue(today.year)
        monday = QCheckBox("Week starts on Monday")
        form.addRow("Month", month)
        form.addRow("Year", year)
        form.addRow(monday)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() != QDialog.Accepted:
            return
        d = new_item("table", 80, 80, w=490, h=336)
        tc.make_calendar(d, year.value(), month.currentIndex() + 1, monday.isChecked())
        self.target_list().append(d)
        self.reload({d["id"]})
        self.commit_if_changed("Insert calendar")

    # -- workspaces ----------------------------------------------------
    def fill_workspaces(self):
        st = QSettings("4ThePeopleMedia", "Sitewright")
        names = st.value("workspace_names", []) or []
        if isinstance(names, str):
            names = [names]
        self.ws_combo.blockSignals(True)
        self.ws_combo.clear()
        self.ws_combo.addItem("Default")
        for n in names:
            self.ws_combo.addItem(n)
        self.ws_combo.blockSignals(False)

    def workspace_picked(self, i):
        name = self.ws_combo.itemText(i)
        if name == "Default":
            if getattr(self, "default_state", None):
                self.restoreState(self.default_state, STATE_VERSION)
            return
        data = QSettings("4ThePeopleMedia", "Sitewright").value("ws/" + name)
        if data:
            self.restoreState(data, STATE_VERSION)

    def save_workspace(self):
        name, ok = QInputDialog.getText(self, "Save workspace", "Workspace name:")
        name = name.strip()
        if not ok or not name or name == "Default":
            return
        st = QSettings("4ThePeopleMedia", "Sitewright")
        names = st.value("workspace_names", []) or []
        if isinstance(names, str):
            names = [names]
        if name not in names:
            names.append(name)
        st.setValue("workspace_names", names)
        st.setValue("ws/" + name, self.saveState(STATE_VERSION))
        self.fill_workspaces()
        self.ws_combo.setCurrentIndex(self.ws_combo.findText(name))

    def finish_menus(self):
        from . import formtools as ft
        """Put the menus in WebPlus order and add the ones it has that we lacked."""
        m = self.menus
        txt = QMenu("&Text", self)
        self.act(txt, "Edit &text", self.edit_text, "F2")
        self.act(txt, "&Spell checker...", self.spell_check, "F7")
        self.act(txt, "&Find and Replace...", self.find_replace)
        self.act(txt, "&Proof reader...", self.proof_reader, "Shift+F7")
        self.act(txt, "&Thesaurus...", self.thesaurus_dialog, "Alt+F7")
        self.act(txt, "Insert &symbol...", self.insert_symbol)
        self.act(txt, "C&lear text formatting", self.clear_text_format)
        self.act(txt, "&Bullets and numbering...", self.bullets_dialog)
        self.act(txt, "Artistic te&xt (curved words)", lambda: self.set_tool("arttext"))
        self.act(txt, "Fit text to &path", self.fit_text_to_path)
        ov = txt.addMenu("Overflowing te&xt")
        from .textlayout import OVERFLOWS
        for value, label in OVERFLOWS:
            self.act(ov, label, lambda _=False, v=value: self.set_overflow(v))
        ti = txt.addMenu("I&nsert")
        for label, kind in (("&Date or time...", "datetime"), ("&Page info...", "page"),
                            ("&Site info...", "site"), ("&Object info...", "object"),
                            ("&Variable...", "variable")):
            self.act(ti, label, lambda _=False, k=kind: self.insert_info(k))
        self.act(ti, "&Fill with placeholder text...", self.insert_placeholder)
        cs = txt.addMenu("&Change case")
        for label, mode in (("Sentence case", "sentence"), ("lower case", "lower"),
                            ("UPPER CASE", "upper"), ("Title Case", "title"),
                            ("tOGGLE cASE", "toggle")):
            self.act(cs, label, lambda _=False, md=mode: self.change_case(md))
        tbl = QMenu("T&able", self)
        self.act(tbl, "&Insert table", lambda: self.set_tool("table"))
        tbl.addSeparator()
        for label, what in (("Add &row", "row+"), ("Add &column", "col+")):
            self.act(tbl, label, lambda _=False, w_=what: self.table_edit(w_))
        self.act(tbl, "Insert rows...", lambda: self.table_insert("rows"))
        self.act(tbl, "Insert columns...", lambda: self.table_insert("cols"))
        self.act(tbl, "Delete r&ow(s)", lambda: self.table_delete("rows"))
        self.act(tbl, "Delete c&olumn(s)", lambda: self.table_delete("cols"))
        tbl.addSeparator()
        sel = tbl.addMenu("&Select")
        self.act(sel, "&Row(s)", lambda: self.table_select("rows"))
        self.act(sel, "&Column(s)", lambda: self.table_select("cols"))
        self.act(sel, "&All", lambda: self.table_select("all"))
        self.act(tbl, "&Merge cells", self.table_merge)
        self.act(tbl, "Se&parate cells", self.table_separate)
        tbl.addSeparator()
        self.act(tbl, "Evenly distribute r&ows", lambda: self.table_sizes("dist_rows"))
        self.act(tbl, "Evenly distribute co&lumns", lambda: self.table_sizes("dist_cols"))
        self.act(tbl, "AutoFit column(s) to contents", lambda: self.table_sizes("fit_cols"))
        self.act(tbl, "AutoFit row(s) to contents", lambda: self.table_sizes("fit_rows"))
        self.act(tbl, "Set column &width(s)...", lambda: self.table_sizes("set_cols"))
        self.act(tbl, "Set row &height(s)...", lambda: self.table_sizes("set_rows"))
        tbl.addSeparator()
        self.act(tbl, "Fill down", lambda: self.table_fill("down"))
        self.act(tbl, "Fill right", lambda: self.table_fill("right"))
        self.act(tbl, "Cell &properties...", self.table_cell_props)
        self.act(tbl, "&Sort...", self.table_sort)
        self.act(tbl, "Auto&Format...", self.table_autoformat)
        self.act(tbl, "Insert c&alendar...", self.insert_calendar)
        tools = QMenu("&Tools", self)
        self.act(tools, "&Colour scheme designer...", self.scheme_dialog)
        self.act(tools, "Site &theme...", self.theme_dialog)
        self.act(tools, "&User details...", self.user_details)
        self.act(tools, "&Anchor manager...", self.anchor_manager)
        sm = tools.addMenu("Site &Manager")
        for label, tab in (("&Pages...", "pages"), ("&Hyperlink Manager...", "links"),
                           ("&Font Manager...", "fonts"), ("F&ile Manager...", "files"),
                           ("&Text Manager...", "text")):
            self.act(sm, label, lambda _=False, t=tab: self.site_manager(t))
        self.act(sm, "H&TML Page Properties...", self.html_page_properties)
        self.act(tools, "&Master Page Manager...", self.master_manager)
        self.act(tools, "&Variables...", lambda: ft.view_variables(self))
        from . import blogdialog
        self.act(tools, "B&log manager...", lambda: blogdialog.blog_manager(self))
        from . import shopdialog
        self.act(tools, "S&hop manager...", lambda: shopdialog.shop_manager(self))
        fm = tools.addMenu("F&orm")
        self.act(fm, "Set &tab order...", lambda: ft.tab_order(self))
        self.act(fm, "Form &action...", lambda: ft.form_action(self))
        self.act(fm, "&Lock form", lambda: ft.lock_form(self, True))
        self.act(fm, "&Unlock form", lambda: ft.lock_form(self, False))
        from . import dbdialogs as dbd
        dbm = tools.addMenu("&Database Merge")
        self.act(dbm, "&Create Database...", lambda: dbd.create_database(self))
        self.act(dbm, "Create &Photo Database...", lambda: dbd.create_photo_database(self))
        self.act(dbm, "&Edit Database...", lambda: dbd.edit_database(self))
        dbm.addSeparator()
        self.act(dbm, "Insert &Repeating Area", lambda: dbd.insert_repeating_area(self))
        self.act(dbm, "Repeating Area &Layout...", lambda: dbd.layout_dialog(self))
        self.act(dbm, "Insert &Text Field...", lambda: dbd.insert_field(self))
        self.act(dbm, "Insert Pic&ture Field...", lambda: dbd.insert_field(self, True))
        self.act(tools, "&RSS feed / podcast...", self.feed_dialog)
        self.act(tools, "&Members and protected pages...", self.members_dialog)
        self.act(tools, "Mailing &list address...", self.list_dialog)
        self.act(tools, "&Search engine optimisation...", self.seo_dialog)
        self.act(tools, "&Spell checker...", self.spell_check)
        self.act(tools, "&Form email address...", self.form_email_dialog)
        tools.addSeparator()
        self.act(tools, "Pre&view in browser", self.preview, "Ctrl+F5")
        self.act(tools, "&Export website...", self.export_dialog)
        tools.addSeparator()
        self.act(tools, "&Options...", self.options_dialog)
        win = QMenu("&Window", self)
        for dk in (self.toolbox_dock, self.assets_dock, *self.left_tabs, self.colour_dock,
                   self.pages_dock, self.props_dock, self.transform_dock, self.task_dock):
            win.addAction(dk.toggleViewAction())
        win.addSeparator()
        for tb in self.toolbars:
            win.addAction(tb.toggleViewAction())
        lock = self.act(win, "&Lock toolbars in place", self.lock_toolbars, checkable=True)
        lock.setChecked(str(QSettings("4ThePeopleMedia", "Sitewright").value(
            "toolbars_locked", False)).lower() in ("true", "1"))
        self.lock_toolbars(lock.isChecked())
        self.act(win, "&Reset toolbars and panels", self.reset_layout)
        win.addSeparator()
        self.act(win, "&Save workspace...", self.save_workspace)
        self.act(win, "&Default workspace", lambda: self.workspace_picked(0))
        m["Site"].setTitle("&Properties")
        order = [m["File"], m["Edit"], m["View"], m["Insert"], m["Site"], m["Format"],
                 txt, tbl, m["Arrange"], tools, win, m["Help"]]
        mb = self.menuBar()
        mb.clear()
        for menu in order:
            mb.addMenu(menu)

    # -- phase 1/2 extras ------------------------------------------------
    def build_more_actions(self):
        from . import formtools as ft
        m = self.menus["Edit"]
        m.addSeparator()
        self.act(m, "Paste in &place", self.paste_in_place, "Ctrl+Shift+V")
        self.act(m, "&Find and Replace...", self.find_replace, "Ctrl+F")
        self.act(m, "Paste as &unformatted text", self.paste_plain, "Ctrl+Alt+Shift+V")
        self.act(m, "&Replicate...", self.replicate_dialog, "Ctrl+Shift+R")
        self.act(m, "Select &similar", self.select_similar)
        self.act(m, "Select pa&rent (the whole group)", lambda: pagetools.select_parent(self))
        self.act(m, "&Lock / unlock object", self.toggle_lock, "Ctrl+L")

        ins = QMenu("&Insert", self)
        self.menus["Insert"] = ins
        for kind, label in (("table", "&Table"), ("gallery", "Photo &gallery..."),
                            ("video", "&Video (YouTube, Vimeo, mp4)"), ("map", "&Map"),
                            ("audio", "&Audio player"), ("social", "&Social buttons"),
                            ("marquee", "Scrolling &message"), ("html", "&HTML fragment")):
            self.act(ins, label, lambda _=False, k=kind: self.set_tool(k))
        sub = ins.addMenu("&Form field")
        for k in FIELD_TYPES:
            self.act(sub, FIELD_LABELS[k], lambda _=False, k=k: self.set_tool("field:" + k))
        self.act(ins, "&YouTube video...", self.youtube_dialog)
        self.act(ins, "Document &frame (another web page)", lambda: self.set_tool("frame"))
        self.act(ins, "S&lider...", lambda: self.set_tool("slider"))
        self.act(ins, "Save selection as &composition...", self.save_composition)
        self.act(ins, "Picture &library...", lambda: StarterDialog(self).exec_())
        self.act(ins, "Empty picture &frame", lambda: self.set_tool("emptyframe"))
        self.act(ins, "&Rollover (picture that changes)...", lambda: pageitems.insert_rollover(self))
        self.act(ins, "&Pop-up rollover...", lambda: pageitems.insert_popup(self))
        self.act(ins, "&Hotspot (clickable area)", lambda: self.set_tool("hotspot"))
        from . import shapes as _shapes
        sm_ = ins.addMenu("&Shape")
        for key, (label, _f) in _shapes.PRESETS.items():
            self.act(sm_, label, lambda _=False, k=key: self.set_tool("shape:" + k))
        self.act(ins, "Pe&n (draw curves)", lambda: self.set_tool("pen"))
        from . import webapps as _wa
        self.act(ins, "Web &poll", lambda: _wa.insert(self, "poll"))
        self.act(ins, "&Blog", lambda: _wa.insert(self, "blog"))
        shopm = ins.addMenu("&Shop")
        self.act(shopm, "&Product", lambda: _wa.insert(self, "product"))
        self.act(shopm, "Product &grid (all products)", lambda: _wa.insert(self, "productgrid"))
        self.act(shopm, "Shopping &cart button", lambda: _wa.insert(self, "cart"))
        self.act(ins, "&Edit points of the shape", self.edit_points)
        self.act(ins, "RSS rea&der (headlines from a feed)", lambda: self.set_tool("rssreader"))
        self.act(ins, "Animated &GIF...", lambda: pageitems.insert_gif(self))
        self.act(ins, "S&ound...", lambda: pageitems.insert_sound(self))
        self.act(ins, "Cal&endar...", self.insert_calendar)
        self.act(ins, "Form &designer...", self.form_designer)
        sub = ins.addMenu("Site &search and members")
        for kind, label in (("search", "Search &box"), ("searchresults", "Search &results"),
                            ("subscribe", "Mailing list &sign-up"), ("login", "Member &login")):
            self.act(sub, label, lambda _=False, k=kind: self.set_tool(k))
        ins.addSeparator()
        self.act(ins, "Gallery &button...", self.button_gallery)
        self.act(ins, "&Navigation bar from gallery...", self.nav_gallery)
        ins.addSeparator()
        self.act(ins, "Form &email address...", self.form_email_dialog)

        fm = QMenu("F&ormat", self)
        self.menus["Format"] = fm
        self.act(fm, "Colour &scheme...", self.scheme_dialog)
        self.act(fm, "Site &theme...", self.theme_dialog)
        fm.addSeparator()
        self.act(fm, "&Save selection as a style...", self.save_style)
        self.apply_menu = fm.addMenu("&Apply style")
        self.apply_menu.aboutToShow.connect(self.fill_style_menu)
        self.delete_menu = fm.addMenu("&Delete style")
        self.delete_menu.aboutToShow.connect(self.fill_style_menu)

        m = self.menus["Arrange"]
        m.addSeparator()
        sn = m.addMenu("S&napping")
        self.snap_actions = {}
        for key, label, attr in (("grid", "Snap to the &grid", "snap_on"), ("guides", "Snap to &guide lines", "guide_snap"),
                                 ("dynamic", "&Dynamic guides (line up with other objects)", "dynamic_snap")):
            a = self.act(sn, label, lambda on, at=attr: self.set_snapping(at, on), checkable=True)
            a.setChecked(getattr(self, attr))
            self.snap_actions[attr] = a
        self.act(m, "Set object &order...", lambda: pagetools.set_object_order(self))
        at = m.addMenu("Attach to &text")
        self.act(at, "Attach &under the text box (follows it as it grows)", lambda: pagetools.attach(self, "bottom"))
        self.act(at, "Attach &beside it (same distance from its top)", lambda: pagetools.attach(self, "top"))
        self.act(at, "&Detach from text", lambda: pagetools.detach(self))
        self.act(m, "&Group objects", self.group, "Ctrl+G")
        self.act(m, "&Ungroup objects", self.ungroup, "Ctrl+Shift+G")
        m.addSeparator()
        sub = m.addMenu("&Align objects")
        for text, how in (("Left", "l"), ("Centre", "c"), ("Right", "r"),
                          ("Top", "t"), ("Middle", "m"), ("Bottom", "b")):
            self.act(sub, text, lambda _=False, h=how: self.align(h))
        sub = m.addMenu("&Size objects")
        for text, how in (("Same width", "w"), ("Same height", "h"), ("Same size", "wh")):
            self.act(sub, text, lambda _=False, h=how: self.same_size(h))
        m.addSeparator()
        self.act(m, "Rotate &left", lambda: self.rotate(-90))
        self.act(m, "Rotate &right", lambda: self.rotate(90))
        self.act(m, "Flip &horizontal", lambda: self.flip("fx"))
        self.act(m, "Flip &vertical", lambda: self.flip("fy"))

        m = self.menus["View"]
        m.addSeparator()
        self.act(m, "&Previous page", lambda: self.step_page(-1), "Ctrl+PgUp")
        self.act(m, "&Next page", lambda: self.step_page(1), "Ctrl+PgDown")
        self.act(m, "Zoom to &selection", self.zoom_selection, "Ctrl+Alt+0")
        self.show_hidden = True
        self.rulers_action = self.act(m, "&Rulers", lambda on: self.toggle_rulers(on), checkable=True)
        on = str(QSettings("4ThePeopleMedia", "Sitewright").value("rulers", True)).lower() in ("true", "1")
        self.rulers_action.setChecked(on)
        rulers.show_rulers(self, on)
        self.hidden_action = self.act(m, "Show &hidden objects", self.toggle_hidden_objects,
                                      checkable=True)
        self.hidden_action.setChecked(True)
        self.show_records = True
        self.records_action = self.act(m, "Show other &records in repeating areas", self.toggle_records,
                                       checkable=True)
        self.records_action.setChecked(True)
        m.addSeparator()
        sub = m.addMenu("&Toolbar buttons")
        grp2 = QActionGroup(self)
        self.toolbar_style_actions = {}
        for key, label in (("icons", "Pictures only"), ("both", "Pictures with words"),
                           ("text", "Words only")):
            a = QAction(label, self)
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, k=key: self.set_toolbar_style(k))
            grp2.addAction(a)
            sub.addAction(a)
            self.toolbar_style_actions[key] = a
        sub = m.addMenu("Interface &text size")
        grp = QActionGroup(self)
        cur = saved_ui_pt()
        for pt in (7, 8, 9, 10, 11, 12, 14):
            a = QAction("%d pt%s" % (pt, "  (default)" if pt == DEFAULT_UI_PT else ""), self)
            a.setCheckable(True)
            a.setChecked(abs(cur - pt) < 0.1)
            a.triggered.connect(lambda _=False, pt=pt: self.set_ui_pt(pt))
            grp.addAction(a)
            sub.addAction(a)
        self.act(m, "Page HTML &source...", self.html_source, "Ctrl+U")
        self.act(m, "&Hide or show all panels", self.toggle_panels, "F4")
        sub = m.addMenu("&Panels")
        for dk in (self.toolbox_dock, self.pages_dock, self.props_dock):
            sub.addAction(dk.toggleViewAction())
        sub = m.addMenu("&Zoom to")
        self.act(sub, "Page &width", self.zoom_width)
        for z in (50, 75, 100, 200, 400, 800):
            self.act(sub, "%d%%" % z, lambda _=False, z=z: self.view.set_zoom(z / 100))
        sub = m.addMenu("&Guides")
        self.act(sub, "Add &vertical guide...", lambda: self.add_guide("v"))
        self.act(sub, "Add &horizontal guide...", lambda: self.add_guide("h"))
        self.act(sub, "&Clear guides", self.clear_guides)

        m = self.menus["File"]
        acts = m.actions()
        self.recent_menu = QMenu("Open &recent", self)
        m.insertMenu(acts[2], self.recent_menu)
        rv = QAction("Re&vert", self)
        rv.triggered.connect(self.revert)
        m.insertAction(acts[3], rv)
        self.fill_recent()

        from . import fxdialogs
        m = self.menus["Format"]
        m.addSeparator()
        self.act(m, "Filter &effects (blur, glow)...", lambda: fxdialogs.filter_effects(self))
        self.act(m, "Picture &watermark...", lambda: fxdialogs.watermark(self))
        self.act(m, "Picture &transparency...", lambda: fxdialogs.transparent_colour(self))
        self.act(m, "Crop to &shape...", lambda: fxdialogs.crop_shape(self))
        from . import photolab
        self.act(m, "Edit &photo (PhotoLab)...", lambda: photolab.edit_photo(self))

        m = self.menus["Site"]
        self.act(m, "&Object properties...", self.show_properties, "Alt+Return")
        self.act(m, "&Actions...", self.edit_actions)
        self.act(m, "&Pop-up menu...", lambda: ft.popup_menu(self))
        self.act(m, "&Frame properties...", lambda: ft.frame_properties(self))
        self.act(m, "&CSS properties...", self.edit_css)
        self.act(m, "HTML &attributes...", self.edit_attrs)
        m.addSeparator()
        sub = m.addMenu("Page from &template")
        for name in templates.TEMPLATES:
            self.act(sub, name, lambda _=False, n=name: self.add_page(template=n))
        self.act(m, "Insert &offsite link...", lambda: self.offsite_dialog())
        self.act(m, "Insert H&TML page...", self.insert_html_page)
        self.act(m, "Set as &home page", lambda: self.set_home(self.cur_page()))
        m.addSeparator()
        self.act(m, "Search engine &optimisation...", self.seo_dialog, "Ctrl+Shift+O")

    def pick_style(self, title, styles, preview):
        from PyQt5.QtGui import QIcon
        from PyQt5.QtCore import QSize
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(760, 520)
        lay = QVBoxLayout(dlg)
        lst = QTreeWidget()
        lst.setHeaderHidden(True)
        lst.setColumnCount(1)
        lst.setIconSize(QSize(300, 72))
        lst.setRootIsDecorated(False)
        for name, props in styles.items():
            it = QTreeWidgetItem([name])
            it.setIcon(0, QIcon(preview(props)))
            lst.addTopLevelItem(it)
        lay.addWidget(lst)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        lst.itemDoubleClicked.connect(lambda *_: dlg.accept())
        if dlg.exec_() != QDialog.Accepted or lst.currentItem() is None:
            return None
        return dict(styles[lst.currentItem().text(0)])

    def apply_style(self, kind, props):
        objs = [o for o in self.selected() if o.d["kind"] == kind]
        for o in objs:
            o.d.update(props)
            o.sync()
        self.props.refresh()
        if objs:
            self.commit_if_changed("Apply style")
        return bool(objs)

    def button_gallery(self):
        props = self.pick_style("Button gallery", BUTTON_STYLES,
                                lambda p: preview_button(p, "Button"))
        if props and not self.apply_style("button", props):
            self.pending_style = props
            self.set_tool("button")
            self.statusBar().showMessage("Drag on the page to place the button", 5000)

    def nav_gallery(self):
        props = self.pick_style("Navigation bar gallery", NAV_STYLES, preview_nav)
        if props and not self.apply_style("navbar", props):
            self.pending_style = props
            self.set_tool("navbar")
            self.statusBar().showMessage("Drag on the page to place the navigation bar", 5000)

    def set_ui_pt(self, pt):
        apply_ui_font(pt)
        QSettings("4ThePeopleMedia", "Sitewright").setValue("ui_pt", pt)

    def recolor_everything(self, label):
        self._pix = {}
        self.reload()
        self.commit_if_changed(label)

    def scheme_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Colour scheme")
        v = QVBoxLayout(dlg)
        pre = QComboBox()
        pre.addItem("Current scheme")
        pre.addItems(list(SCHEMES))
        v.addWidget(pre)
        g = QGridLayout()
        fields = []
        for i in range(12):
            cf = ColorField(False)
            cf.set(self.doc.scheme[i])
            fields.append(cf)
            g.addWidget(QLabel("%d  %s" % (i + 1, SCHEME_LABELS[i])), i % 6, (i // 6) * 2)
            g.addWidget(cf, i % 6, (i // 6) * 2 + 1)
        v.addLayout(g)
        v.addWidget(QLabel("Colours in your pages that match the old scheme change to the new one."))

        def load(n):
            if n > 0:
                for cf, c in zip(fields, SCHEMES[pre.itemText(n)]):
                    cf.set(c)
        pre.currentIndexChanged.connect(load)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec_() != QDialog.Accepted:
            return
        apply_scheme(self.doc, [cf.value for cf in fields])
        self.recolor_everything("Colour scheme")

    def theme_dialog(self):
        styles = {n: dict(t, name=n) for n, t in THEMES.items()}
        props = self.pick_style("Site theme", styles, lambda p: preview_theme(p["name"]))
        if props:
            apply_theme(self.doc, props["name"])
            self.recolor_everything("Theme " + props["name"])

    def save_style(self):
        objs = self.selected()
        if not objs:
            QMessageBox.information(self, APP, "Select an object first.")
            return
        name, ok = QInputDialog.getText(self, "Save style", "Style name:")
        if ok and name.strip():
            self.doc.styles[name.strip()] = {k: v for k, v in objs[0].d.items()
                                             if k in STYLE_KEYS}
            self.commit_if_changed("Save style")

    def fill_style_menu(self):
        for menu, fn in ((self.apply_menu, self.use_style), (self.delete_menu, self.drop_style)):
            menu.clear()
            for n in sorted(self.doc.styles):
                menu.addAction(n, lambda _=False, n=n, fn=fn: fn(n))
            menu.setEnabled(bool(self.doc.styles))

    def use_style(self, name):
        st = self.doc.styles.get(name, {})
        for o in self.selected():
            o.d.update({k: v for k, v in st.items() if k in o.d})
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Apply style")

    def drop_style(self, name):
        self.doc.styles.pop(name, None)
        self.commit_if_changed("Delete style")

    def form_email_dialog(self):
        v, ok = QInputDialog.getText(self, "Form email",
                                     "Send form messages to this email address:",
                                     text=self.doc.form_email)
        if ok:
            self.doc.form_email = v.strip()
            self.commit_if_changed("Form email")

    def fill_recent(self):
        self.recent_menu.clear()
        files = QSettings("4ThePeopleMedia", "Sitewright").value("recent", []) or []
        if isinstance(files, str):
            files = [files]
        for f in files:
            if os.path.isfile(f):
                self.recent_menu.addAction(os.path.basename(f),
                                           lambda _=False, f=f: self.maybe_open(f))
        self.recent_menu.setEnabled(not self.recent_menu.isEmpty())

    def remember(self, path):
        st = QSettings("4ThePeopleMedia", "Sitewright")
        files = st.value("recent", []) or []
        if isinstance(files, str):
            files = [files]
        files = [path] + [f for f in files if f != path]
        st.setValue("recent", files[:8])
        self.fill_recent()

    def maybe_open(self, path):
        if self.maybe_discard():
            self.open_path(path)

    def revert(self):
        if self.doc.path and os.path.isfile(self.doc.path):
            r = QMessageBox.question(self, APP, "Throw away changes and reload the saved file?")
            if r == QMessageBox.Yes:
                self.open_path(self.doc.path)

    def paste_in_place(self):
        if not self.clip:
            return
        for c in self.clip:
            c["x"] -= 20
            c["y"] -= 20
        self.paste()

    def paste_plain(self):
        """Paste the copied objects, but give text back its plain default look."""
        if not self.clip:
            return
        saved = copy.deepcopy(self.clip)
        from .model import TEXT_BASE
        for c in self.clip:
            if c.get("kind") == "text":
                for k, v in TEXT_BASE.items():
                    c[k] = v
        self.paste()
        self.clip = saved

    def replicate_dialog(self):
        objs = self.selected()
        if not objs:
            QMessageBox.information(self, APP, "Select one or more objects to replicate.")
            return
        from PyQt5.QtWidgets import QDialog, QFormLayout, QSpinBox, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Replicate")
        form = QFormLayout(dlg)
        box = QRectF()
        for o in objs:
            box = box.united(QRectF(o.d["x"], o.d["y"], o.d["w"], max(o.d["h"], 1)))
        sp = {}
        for key, label, lo, hi, val in (("cols", "Copies across", 1, 50, 3),
                                        ("rows", "Copies down", 1, 50, 1),
                                        ("dx", "Space across (px)", -2000, 4000, 20),
                                        ("dy", "Space down (px)", -2000, 4000, 20)):
            w = QSpinBox()
            w.setRange(lo, hi)
            w.setValue(val)
            form.addRow(label, w)
            sp[key] = w
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() != QDialog.Accepted:
            return
        self.replicate(sp["cols"].value(), sp["rows"].value(),
                       box.width() + sp["dx"].value(), box.height() + sp["dy"].value())

    def replicate(self, cols, rows, stepx, stepy):
        from .model import new_id
        src = [copy.deepcopy(o.d) for o in self.selected()]
        new = []
        for r in range(rows):
            for c in range(cols):
                if r == 0 and c == 0:
                    continue
                gid = new_id() if any(d.get("group") for d in src) else ""
                for d in src:
                    n = copy.deepcopy(d)
                    n["id"] = new_id()
                    n["x"] = d["x"] + c * stepx
                    n["y"] = d["y"] + r * stepy
                    if d.get("group"):
                        n["group"] = gid
                    new.append(n)
        self.target_list().extend(new)
        self.reload({n["id"] for n in new})
        self.commit_if_changed("Replicate")

    def zoom_selection(self):
        objs = self.selected()
        if not objs:
            self.fit_page()
            return
        r = QRectF()
        for o in objs:
            r = r.united(o.sceneBoundingRect())
        self.view.fitInView(r.adjusted(-30, -30, 30, 30), Qt.KeepAspectRatio)
        self.view.zoom = max(0.1, min(4.0, self.view.transform().m11()))
        self.view.resetTransform()
        self.view.scale(self.view.zoom, self.view.zoom)
        self.view.centerOn(r.center())
        self.zoom_changed(self.view.zoom)

    def toggle_records(self):
        self.show_records = self.records_action.isChecked()
        self.reload({o.d["id"] for o in self.selected()})

    def toggle_hidden_objects(self):
        self.show_hidden = self.hidden_action.isChecked()
        for i in self.scene.items():
            if isinstance(i, ItemObj):
                i.sync()

    def select_similar(self):
        kinds = {o.d["kind"] for o in self.selected()}
        for i in self.scene.items():
            if isinstance(i, ItemObj) and i.editable and i.d["kind"] in kinds:
                i.setSelected(True)

    def toggle_lock(self):
        objs = self.selected()
        if not objs:
            return
        new = not all(o.d.get("locked") for o in objs)
        for o in objs:
            o.d["locked"] = new
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Lock" if new else "Unlock")

    def group(self):
        objs = self.selected()
        if len(objs) < 2:
            return
        gid = new_id()
        for o in objs:
            o.d["group"] = gid
        self.commit_if_changed("Group")

    def ungroup(self):
        for o in self.selected():
            o.d["group"] = ""
        self.commit_if_changed("Ungroup")

    def align(self, how):
        objs = self.selected()
        if not objs:
            return
        if len(objs) == 1:
            L, T, R, B = 0, 0, self.doc.width, self.cur_page()["h"]
        else:
            L = min(o.d["x"] for o in objs)
            T = min(o.d["y"] for o in objs)
            R = max(o.d["x"] + o.d["w"] for o in objs)
            B = max(o.d["y"] + o.d["h"] for o in objs)
        for o in objs:
            d = o.d
            if how == "l":
                d["x"] = L
            elif how == "r":
                d["x"] = R - d["w"]
            elif how == "c":
                d["x"] = round((L + R - d["w"]) / 2)
            elif how == "t":
                d["y"] = T
            elif how == "b":
                d["y"] = B - d["h"]
            elif how == "m":
                d["y"] = round((T + B - d["h"]) / 2)
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Align")

    def same_size(self, how):
        objs = self.selected()
        if len(objs) < 2:
            return
        w = max(o.d["w"] for o in objs)
        h = max(o.d["h"] for o in objs)
        for o in objs:
            if "w" in how:
                o.d["w"] = w
            if "h" in how:
                o.d["h"] = h
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Size")

    def rotate(self, deg):
        for o in self.selected():
            o.d["rot"] = ((o.d.get("rot", 0) + deg + 180) % 360) - 180
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Rotate")

    def flip(self, key):
        for o in self.selected():
            o.d[key] = not o.d.get(key)
            o.sync()
        self.commit_if_changed("Flip")

    def zoom_width(self):
        self.view.set_zoom((self.view.viewport().width() - 20) / (self.doc.width + 160))

    def add_guide(self, axis):
        v, ok = QInputDialog.getInt(self, "Guide", "Position (px):", 100, 0, 20000)
        if ok:
            g = self.cur_page().setdefault("guides", dict(v=[], h=[]))
            g.setdefault(axis, []).append(v)
            self.scene.update()
            self.commit_if_changed("Add guide")

    def clear_guides(self):
        self.cur_page()["guides"] = dict(v=[], h=[])
        self.scene.update()
        self.commit_if_changed("Clear guides")

    # -- state helpers ---------------------------------------------------
    def _snap(self, v, axis):
        tol = 6 / max(self.view.zoom, 0.1)
        if self.guide_snap:
            for g in (self.cur_page().get("guides") or {}).get(axis, []):
                if abs(g - v) <= tol:
                    return g
        return round(v / 10) * 10 if self.snap_on else v

    def finish_guide_drag(self, inside):
        """A guide dropped: kept (new or moved) if it ended on the page, dropped if it went back out."""
        d, self.guide_drag = self.guide_drag, None
        if d is None:
            return
        page = self.cur_page()
        val = round(d["value"] / 10) * 10 if self.snap_on and not d.get("free") else round(d["value"])
        changed = False
        if d["old"] is None:
            if inside:
                changed = rulers.add_guide(page, d["axis"], val)
        elif inside:
            changed = rulers.move_guide(page, d["axis"], d["old"], val)
        else:
            changed = rulers.remove_guide(page, d["axis"], d["old"])
        self.scene.update()
        self.ruler_h.update()
        self.ruler_v.update()
        if changed:
            self.commit_if_changed("Guide")

    def snap_x(self, v):
        return self._snap(v, "v")

    def snap_y(self, v):
        return self._snap(v, "h")

    def selection_changed(self):
        if self._sel_guard:
            return
        gids = {o.d.get("group") for o in self.selected() if o.d.get("group")}
        if gids:
            self._sel_guard = True
            for i in self.scene.items():
                if isinstance(i, ItemObj) and i.editable and i.d.get("group") in gids:
                    i.setSelected(True)
            self._sel_guard = False
        self.props.refresh()

    def cur_page(self):
        return self.doc.pages[self.page_index]

    def target_list(self):
        return self.doc.master_list(self.master_edit) if self.master_mode else self.cur_page()["items"]

    def selected(self):
        try:
            return [i for i in self.scene.selectedItems() if isinstance(i, ItemObj)]
        except RuntimeError:        # scene already deleted at shutdown
            return []

    def update_title(self):
        name = os.path.basename(self.doc.path) if self.doc.path else "Untitled"
        star = "" if self.undo.isClean() else " *"
        self.setWindowTitle("%s%s - %s" % (name, star, APP))

    def zoom_changed(self, z):
        self.zoom_label.setText("%d%%" % round(z * 100))
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(round(z * 100))
        self.zoom_slider.blockSignals(False)

    def gif_pixmap(self, aid):
        """The current picture of an animated GIF (None for anything else). One QMovie per file."""
        if not aid or not pageitems.is_gif(self.doc, aid):
            return None
        mv = self._gifs.get(aid)
        if mv is None:
            data = QByteArray(self.doc.asset_bytes(aid))
            buf = QBuffer(self)
            buf.setData(data)
            buf.open(QBuffer.ReadOnly)
            mv = QMovie(buf, QByteArray(), self)
            if not mv.isValid() or mv.frameCount() == 1:
                self._gifs[aid] = False
                return None
            mv.frameChanged.connect(lambda _n: self.view.viewport().update())
            mv.start()
            self._gifs[aid] = mv
        return mv.currentPixmap() if mv else None

    def gif_frame(self, aid):
        """Which frame an animated GIF is showing now (-1 when the picture is not animated)."""
        if not self.gif_pixmap(aid):
            return -1
        mv = self._gifs.get(aid)
        return mv.currentFrameNumber() if mv else -1

    def derived_pixmap(self, d):
        from . import imagefx
        from .export import token_values
        key = imagefx.cache_key(self.doc, d, 1200)
        hit = self._derived.get(id(d))
        if not hit or hit[0] != key:
            img = imagefx.derive(self.doc, d, token_values(self.doc), 1200)
            hit = (key, QPixmap.fromImage(img) if img else None)
            self._derived[id(d)] = hit
        return hit[1]

    def pixmap(self, aid):
        if not aid:
            return None
        if aid not in self._pix:
            pm = QPixmap()
            pm.loadFromData(self.doc.asset_bytes(aid))
            self._pix[aid] = pm
        return self._pix[aid]

    # -- scene -----------------------------------------------------------
    def reload(self, keep=()):
        keep = set(keep)
        self.scene.blockSignals(True)
        self.scene.clear()
        page = self.cur_page()
        ne = getattr(self, "nodes", None)
        if ne is not None and ne.d is not None and not any(x is ne.d for x in self.target_list()):
            ne.stop()                            # the shape being edited is gone (page changed, deleted, undone)
        shown = self.doc.master_items(page) if not self.master_mode else page["items"]
        for d in shown:
            self.scene.addItem(ItemObj(d, self, editable=False))
        for d in self.target_list():
            o = ItemObj(d, self, editable=True)
            self.scene.addItem(o)
            o.setSelected(d["id"] in keep)
        if getattr(self, "show_records", True) and not self.master_mode:
            from . import databasemerge
            for g in databasemerge.ghosts(self.doc, page):      # the other records, for looking at only
                o = ItemObj(g, self, editable=False)
                o.setOpacity(0.85)
                self.scene.addItem(o)
        for z, o in enumerate(self.scene.items(order=Qt.AscendingOrder)):
            o.setZValue(z)
        self.scene.setSceneRect(QRectF(-80, -80, self.doc.width + 160,
                                       page["h"] + 160))
        self.scene.blockSignals(False)
        self.props.refresh()
        self.refresh_pages()
        self.scene.update()

    def normalize_pages(self):
        """Keep doc.pages in depth-first order so tree rows match list indexes."""
        order = [p for p, _ in ordered_pages(self.doc.pages)]
        if [p["id"] for p in order] != [p["id"] for p in self.doc.pages]:
            cur = self.cur_page()["id"]
            self.doc.pages = order
            self.page_index = next(i for i, p in enumerate(order) if p["id"] == cur)

    def refresh_pages(self):
        self.normalize_pages()
        self.pages.blockSignals(True)
        self.pages.clear()
        nodes, home_done = {}, False
        cur_node = None
        for p, depth in ordered_pages(self.doc.pages):
            label = p["name"]
            if p.get("type") == "link":
                label = "\u2197 " + label
            elif not home_done:
                label, home_done = "\u2302 " + label, True
            if not p.get("nav", True):
                label += "  (not in menu)"
            it = QTreeWidgetItem([label])
            it.setData(0, Qt.UserRole, p["id"])
            par = nodes.get(p.get("parent", ""))
            (par.addChild if par is not None else self.pages.addTopLevelItem)(it)
            nodes[p["id"]] = it
            if p["id"] == self.cur_page()["id"]:
                cur_node = it
        self.pages.expandAll()
        if cur_node is not None:
            self.pages.setCurrentItem(cur_node)
        self.pages.blockSignals(False)
        pc = getattr(self, "page_combo", None)
        if pc is not None:
            pc.blockSignals(True)
            pc.clear()
            for p in self.doc.pages:
                if p.get("type", "page") == "page":
                    pc.addItem(p["name"], p["id"])
            pc.setCurrentIndex(max(pc.findData(self.cur_page()["id"]), 0))
            pc.blockSignals(False)

    def page_index_of(self, pid):
        for i, p in enumerate(self.doc.pages):
            if p["id"] == pid:
                return i
        return -1

    def item_moved(self, item=None):
        pagetools.follow(self, item.d if item is not None else None)
        self.props.refresh()

    # -- undo ------------------------------------------------------------
    def commit_if_changed(self, label="Edit"):
        now = self.doc.snapshot()
        if now != self.last:
            self.undo.push(SnapCommand(self, self.last, now, label))
            self.last = now
            self.update_title()

    def apply_snapshot(self, snap):
        self.nodes.stop()
        ids = {o.d["id"] for o in self.selected()}
        self.doc.restore(snap)
        self.page_index = min(self.page_index, len(self.doc.pages) - 1)
        self.last = snap
        self.reload(ids)
        self.update_title()

    # -- editing ---------------------------------------------------------
    def edit_points(self):
        objs = [o for o in self.selected() if o.d["kind"] == "shape"]
        if not objs:
            self.statusBar().showMessage("Select a drawn shape first", 4000)
            return
        self.nodes.start(objs[0].d)

    def set_tool(self, k):
        if getattr(self, "pen", None) is not None and k != "pen":
            self.pen.reset()
        if k != "select" and getattr(self, "nodes", None) is not None:
            self.nodes.stop()
        self.tool = k
        self.hint.setText(
            "Click to select. Ctrl-click to add to the selection. Drag to select several objects."
            if k == "select" else
            "Click for a corner, drag for a curve. Double-click or Enter to finish, click the first point to close, "
            "Esc cancels." if k == "pen" else "Drag on the page to draw. Esc cancels.")
        a = self.tool_actions.get(k)
        if a is not None:
            a.setChecked(True)
        self.view.setDragMode(self.view.RubberBandDrag if k == "select" else self.view.NoDrag)
        self.view.viewport().setCursor(Qt.ArrowCursor if k == "select" else Qt.CrossCursor)

    def create_item(self, kind, r):
        self.set_tool("select")
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        over = {}
        if kind.startswith("shape:"):
            kind, over["preset"] = "shape", kind[6:]
            if w < 8 or h < 8:
                w, h = 160, 160
        if kind.startswith("field:"):
            kind, ft = "field", kind[6:]
            over["ftype"] = ft
            over["name"] = ft if ft != "text" else "name"
            if ft == "submit":
                over.update(label="Send", fill="#2b7de9", color="#ffffff", stroke="", sw=0)
            elif ft in ("checkbox", "radio"):
                over["label"] = "I agree"
                over.update(fill="", stroke="", sw=0)
            elif ft == "select":
                over["options"] = "First choice\nSecond choice"
            elif ft == "captcha":
                over.update(label="What is 3 plus 4?", answer="7", name="captcha_answer", required=True)
            elif ft == "recaptcha":
                over.update(label="I'm not a robot", name="g-recaptcha", fill="#f9f9f9", radius=3)
            if ft in FIELD_SIZES and (w < 8 or h < 8):
                w, h = FIELD_SIZES[ft]
        if kind == "emptyframe":
            kind, over["asset"] = "image", ""
            if w < 8 or h < 8:
                w, h = 240, 160
        if kind == "image" and "asset" not in over:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose a picture", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg)")
            if not path:
                return
            over["asset"] = self.doc.add_asset(path)
            pm = self.pixmap(over["asset"])
            if pm is not None and not pm.isNull() and (w < 8 or h < 8):
                k = min(1.0, 400 / pm.width())
                w, h = pm.width() * k, pm.height() * k
        if self.pending_style and kind in ("button", "navbar", "video"):
            over.update(self.pending_style)
            self.pending_style = None
        d = new_item(kind, round(x), round(y), **over)
        if w >= 8 or (kind == "line" and w >= 4):
            d["w"] = round(w)
        if kind == "line":
            d["h"] = round(h) if h >= 4 else 0
        elif h >= 8:
            d["h"] = round(h)
        if kind == "image" and "asset" in over and (r.width() < 8 or r.height() < 8):
            d["w"], d["h"] = round(w), round(h)
        textlayout.fit_height(d)
        self.target_list().append(d)
        self.reload({d["id"]})
        if kind == "gallery":
            self.add_gallery_pictures()
        if kind == "slider":
            self.slider_studio()
        self.commit_if_changed("Add " + KIND_NAMES[kind].lower())

    def set_prop(self, key, val, commit=True):
        objs = self.selected()
        for o in objs:
            if key in o.d or key in ("fill", "stroke", "opacity", "rot", "locked", "fill2",
                                      "hfill", "hcolor", "pfill", "shadow", "popup", "anchor", "sstyle",
                                      "instagram_url", "youtube_url", "htag", "ident", "cls", "hidden",
                                      "btn", "title", "empty", "btnfill", "btncolor",
                                      "hover_effect", "lightbox", "caption", "hover_asset",
                                      "lightbox_asset",
                                      "autoplay", "loop", "fullscreen", "related", "showinfo", "hd",
                                      "url",
                                      "ifill", "ihover", "active", "acolor", "uline",
                                      "iradius", "ipad", "listtype", "autoh", "overflow", "effects", "watermark", "transp", "field", "rep", "bw", "bcolor", "fit", "alt",
                                      "closed", "preset", "cropshape"):
                o.d[key] = val
                if key in textlayout.FIT_KEYS or key == "autoh":
                    textlayout.fit_height(o.d)
                o.sync()
        pagetools.follow(self)
        self.scene.update()
        if commit and objs:
            self.commit_if_changed("Change " + key)

    def nudge(self, dx, dy):
        for o in self.selected():
            o.d["x"] += dx
            o.d["y"] += dy
            o.sync()
        pagetools.follow(self)
        self.props.refresh()
        self.commit_if_changed("Move")

    def edit_text(self):
        objs = self.selected()
        if objs and "text" in objs[0].d:
            self.props.w["text"].setFocus()
            self.props.w["text"].selectAll()

    def replace_picture(self):
        objs = [o for o in self.selected() if o.d["kind"] == "image"]
        if not objs:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a picture", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg)")
        if path:
            aid = self.doc.add_asset(path)
            for o in objs:
                o.d["asset"] = aid
                o.sync()
            self.commit_if_changed("Replace picture")

    def add_gallery_pictures(self):
        objs = [o for o in self.selected() if o.d["kind"] == "gallery"]
        if not objs:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose pictures", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp)")
        for path in paths:
            aid = self.doc.add_asset(path)
            for o in objs:
                o.d.setdefault("assets", []).append(aid)
        for o in objs:
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Add pictures")

    def clear_gallery(self):
        for o in self.selected():
            if o.d["kind"] == "gallery":
                o.d["assets"] = []
                o.sync()
        self.props.refresh()
        self.commit_if_changed("Clear gallery")

    def pick_audio(self):
        objs = [o for o in self.selected() if o.d["kind"] == "audio"]
        if not objs:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose an audio file", "", "Audio (*.mp3 *.ogg *.wav *.m4a)")
        if path:
            aid = self.doc.add_asset(path)
            for o in objs:
                o.d["asset"], o.d["url"] = aid, ""
            self.props.refresh()
            self.commit_if_changed("Audio file")

    def set_table_dims(self, rows=None, cols=None):
        for o in self.selected():
            d = o.d
            if d["kind"] != "table":
                continue
            from . import tablecore as tc
            tc.resize(d, rows or d["rows"], cols or d["cols"])
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Table size")

    def set_table_cells(self, text):
        rows = [line.split("|") for line in text.split("\n")] or [[""]]
        cols = max(len(r) for r in rows)
        rows = [[c.strip() for c in r] + [""] * (cols - len(r)) for r in rows]
        for o in self.selected():
            if o.d["kind"] == "table":
                from . import tablecore as tc
                o.d["cells"] = rows
                tc.resize(o.d, len(rows), cols)
                o.sync()
        self.props.timer.start(500)

    def delete(self):
        ids = {o.d["id"] for o in self.selected()}
        if ids:
            lst = self.target_list()
            lst[:] = [d for d in lst if d["id"] not in ids]
            self.reload()
            self.commit_if_changed("Delete")

    def select_all(self):
        for i in self.scene.items():
            if isinstance(i, ItemObj) and i.editable:
                i.setSelected(True)

    def copy(self):
        self.clip = [copy.deepcopy(o.d) for o in self.selected()]

    def cut(self):
        self.copy()
        self.delete()

    def paste(self):
        if not self.clip:
            return
        from .model import new_id
        new = []
        for d in self.clip:
            c = copy.deepcopy(d)
            c["id"] = new_id()
            c["x"] += 20
            c["y"] += 20
            new.append(c)
        self.target_list().extend(new)
        self.clip = [copy.deepcopy(c) for c in new]
        self.reload({c["id"] for c in new})
        self.commit_if_changed("Paste")

    def duplicate(self):
        self.copy()
        self.paste()

    def arrange(self, how):
        sel = {o.d["id"] for o in self.selected()}
        lst = self.target_list()
        if not sel:
            return
        mine = [d for d in lst if d["id"] in sel]
        rest = [d for d in lst if d["id"] not in sel]
        if how == "front":
            lst[:] = rest + mine
        elif how == "back":
            lst[:] = mine + rest
        else:
            step = 1 if how == "up" else -1
            order = list(lst)
            rng = range(len(order) - 2, -1, -1) if step == 1 else range(1, len(order))
            for i in rng:
                if order[i]["id"] in sel and order[i + step]["id"] not in sel:
                    order[i], order[i + step] = order[i + step], order[i]
            lst[:] = order
        self.reload(sel)
        self.commit_if_changed("Arrange")

    def centre(self):
        for o in self.selected():
            o.d["x"] = round((self.doc.width - o.d["w"]) / 2)
            o.sync()
        self.props.refresh()
        self.commit_if_changed("Centre")

    # -- pages -----------------------------------------------------------
    def page_picked(self, cur, prev=None):
        if cur is None:
            return
        i = self.page_index_of(cur.data(0, Qt.UserRole))
        if i < 0 or i == self.page_index or self.doc.pages[i].get("type") == "link":
            return
        self.page_index = i
        self.reload()

    def pages_reordered(self):
        by = {p["id"]: p for p in self.doc.pages}
        cur = self.cur_page()["id"]
        flat = []

        def walk(node, parent):
            pid = node.data(0, Qt.UserRole)
            by[pid]["parent"] = parent
            flat.append(by[pid])
            for k in range(node.childCount()):
                walk(node.child(k), pid)
        for k in range(self.pages.topLevelItemCount()):
            walk(self.pages.topLevelItem(k), "")
        if len(flat) == len(self.doc.pages):
            self.doc.pages = flat
            self.page_index = self.page_index_of(cur)
        self.reload()
        self.commit_if_changed("Move page")

    def clicked_page(self):
        it = self.pages.currentItem()
        i = self.page_index_of(it.data(0, Qt.UserRole)) if it else self.page_index
        return self.doc.pages[i if i >= 0 else self.page_index]

    def page_menu(self, pos):
        p = self.clicked_page()
        m = QMenu(self)
        m.addAction("Add child page", lambda: self.add_page(parent=p["id"]))
        m.addAction("Insert offsite link...", lambda: self.offsite_dialog(None, p["id"]))
        m.addAction("Insert HTML page...", lambda: self.insert_html_page(p["id"]))
        m.addSeparator()
        if p.get("type") != "link":
            m.addAction("Set as home page", lambda: self.set_home(p))
        a = m.addAction("Include in navigation")
        a.setCheckable(True)
        a.setChecked(p.get("nav", True))
        a.toggled.connect(lambda on: self.set_nav(p, on))
        m.addAction("Page settings...", self.page_settings)
        m.addAction("Delete", self.del_page)
        m.exec_(self.pages.viewport().mapToGlobal(pos))

    def set_home(self, p):
        p["parent"] = ""
        self.doc.pages.remove(p)
        self.doc.pages.insert(0, p)
        self.page_index = 0
        self.reload()
        self.commit_if_changed("Set home page")

    def set_nav(self, p, on):
        p["nav"] = on
        self.reload()
        self.commit_if_changed("Navigation")

    def offsite_dialog(self, page=None, parent=""):
        name, ok = QInputDialog.getText(self, "Offsite link", "Link name:",
                                        text=page["name"] if page else "Link")
        if not ok or not name.strip():
            return
        url, ok = QInputDialog.getText(self, "Offsite link", "Web address:",
                                       text=page.get("url", "https://") if page else "https://")
        if not ok:
            return
        if page is None:
            page = new_page(name.strip(), type="link", url=url.strip(), parent=parent)
            self.doc.pages.append(page)
        else:
            page.update(name=name.strip(), url=url.strip())
        self.reload()
        self.commit_if_changed("Offsite link")

    def toggle_master(self, on):
        self.master_mode = on
        if on:
            m = self.cur_page().get("master", True)
            self.master_edit = m if isinstance(m, str) else ""
        self.master_btn.setText("Back to page" if on else "Edit master page")
        self.reload()

    def edit_master(self, mid):
        """Open one master page for editing (from the Master Page Manager)."""
        self.master_edit = mid or ""
        if self.master_btn.isChecked():
            self.master_btn.setText("Back to page")
            self.master_mode = True
            self.reload()
        else:
            self.master_btn.setChecked(True)          # runs toggle_master, which would pick the page's own
            self.master_edit = mid or ""
            self.reload()

    def add_page(self, checked=False, parent="", template=None):
        p = new_page("Page %d" % (len(real_pages(self.doc)) + 1), parent=parent)
        if template:
            p["items"], p["h"] = templates.build(template, self.doc.width)
            p["name"] = p["title"] = template
        self.doc.pages.append(p)
        self.normalize_pages()
        self.page_index = self.page_index_of(p["id"])
        self.reload()
        self.commit_if_changed("Add page")

    def dup_page(self):
        from .model import new_id
        p = copy.deepcopy(self.cur_page())
        p["id"], p["name"] = new_id(), p["name"] + " copy"
        for d in p["items"]:
            d["id"] = new_id()
        self.doc.pages.insert(self.page_index + 1, p)
        self.page_index += 1
        self.reload()
        self.commit_if_changed("Duplicate page")

    def del_page(self):
        p = self.clicked_page()
        if p.get("type", "page") == "page" and len(real_pages(self.doc)) < 2:
            QMessageBox.information(self, APP, "A site needs at least one page.")
            return
        for q in self.doc.pages:
            if q.get("parent") == p["id"]:
                q["parent"] = p.get("parent", "")
        self.doc.pages.remove(p)
        if self.page_index >= len(self.doc.pages) or \
                self.doc.pages[self.page_index].get("type") == "link":
            self.page_index = next(i for i, q in enumerate(self.doc.pages)
                                   if q.get("type", "page") == "page")
        self.reload()
        self.commit_if_changed("Delete page")

    def page_settings(self):
        self.page_settings_for(self.clicked_page())

    def page_settings_for(self, p):
        if p.get("type") == "link":
            self.offsite_dialog(p)
            return
        if p.get("type") == "html":
            self.html_page_properties_for(p)
            return
        dlg = PageDialog(self, p, self.doc)
        if dlg.exec_() != QDialog.Accepted:
            return
        p.update(name=dlg.name.text().strip() or p["name"], title=dlg.title.text(),
                 h=dlg.h.value(), bg=dlg.bg.value or "#ffffff",
                 master=dlg.master.currentData(), protect=dlg.protect.isChecked(),
                 allow=[n.strip() for n in dlg.allow.text().split(",") if n.strip()])
        if dlg.sound_path:
            p["sound"] = dict(asset=self.doc.add_asset(dlg.sound_path), loop=dlg.sound_loop.isChecked())
        elif dlg.sound_clear:
            p.pop("sound", None)
        elif p.get("sound"):
            p["sound"]["loop"] = dlg.sound_loop.isChecked()
        self.doc.site_title = dlg.site.text() or self.doc.site_title
        self.doc.width = dlg.w.value()
        self.reload()
        self.commit_if_changed("Page settings")

    # -- view ------------------------------------------------------------
    def toggle_grid(self, on):
        self.grid_on = on
        self.scene.update()

    def toggle_snap(self, on):
        self.snap_on = on

    def fit_page(self):
        # real size (100%) whenever the page fits; only shrink when the room is too small
        vw = self.view.viewport().width()
        self.view.set_zoom(max(0.25, min(1.0, (vw - 24) / float(self.doc.width + 24))))
        self.view.centerOn(self.doc.width / 2.0, min(self.cur_page()["h"], 600) / 2.0)

    # -- files -----------------------------------------------------------
    def maybe_discard(self):
        if self.undo.isClean():
            return True
        r = QMessageBox.question(self, APP, "Save changes to this site first?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def lock_toolbars(self, on):
        for tb in self.toolbars:
            tb.setMovable(not on)
        QSettings("4ThePeopleMedia", "Sitewright").setValue("toolbars_locked", bool(on))

    def reset_layout(self):
        """Put every toolbar and panel back where they started."""
        if getattr(self, "default_state", None):
            self.restoreState(self.default_state, STATE_VERSION)
        QSettings("4ThePeopleMedia", "Sitewright").remove("window/state")

    def restore_window_state(self):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        st = QSettings("4ThePeopleMedia", "Sitewright")
        state = st.value("window/state")
        if state:
            self.restoreState(state, STATE_VERSION)
        QTimer.singleShot(80, self.fit_page)

    def toggle_panels(self):
        """F4: hide every panel so the page gets the whole window; press again to bring
        them back exactly as they were."""
        docks = [self.toolbox_dock, self.assets_dock, *self.left_tabs, self.colour_dock,
                 self.pages_dock, self.props_dock, self.transform_dock, self.task_dock]
        saved = getattr(self, "_hidden_docks", None)
        if saved is None:
            self._hidden_docks = [d for d in docks if d.isVisible()]
            for d in self._hidden_docks:
                d.hide()
        else:
            for d in saved:
                d.show()
            self._hidden_docks = None
        QTimer.singleShot(50, self.fit_page)

    def layout_toolbox(self, area):
        grid = self.tool_grid
        while grid.count():
            grid.takeAt(0)
        vertical = area in (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea, Qt.NoDockWidgetArea)
        for n, b in enumerate(self.tool_buttons):
            grid.addWidget(b, n if vertical else 0, 0 if vertical else n)
        if vertical:
            grid.setRowStretch(len(self.tool_buttons), 1)
            grid.setColumnStretch(1, 0)
        else:
            grid.setColumnStretch(len(self.tool_buttons), 1)
            grid.setRowStretch(1, 0)
        self.lock_toolbox_size(vertical)

    def lock_toolbox_size(self, vertical):
        """The Tools panel is exactly as wide as one column of tools and cannot be
        stretched. It can still be floated or docked on any edge."""
        d = self.toolbox_dock
        big = 16777215
        n = len(self.tool_buttons)
        bw, bh = 40, 38                       # one button, matches the buttons made above
        pad = 4
        if vertical:
            w = bw + pad + 6                  # buttons + margins + the dock's own frame
            d.setMinimumWidth(w)
            d.setMaximumWidth(w)
            d.setMinimumHeight(0)
            d.setMaximumHeight(big)
        else:
            h = bh + pad + 24                 # buttons + margins + the title strip
            d.setMinimumHeight(h)
            d.setMaximumHeight(h)
            d.setMinimumWidth(0)
            d.setMaximumWidth(big)
        d.widget().setSizePolicy(QSizePolicy.Fixed if vertical else QSizePolicy.Expanding,
                                 QSizePolicy.Expanding if vertical else QSizePolicy.Fixed)

    def recent_files(self):
        files = QSettings("4ThePeopleMedia", "Sitewright").value("recent", []) or []
        if isinstance(files, str):
            files = [files]
        return [f for f in files if os.path.isfile(f)]

    def startup_assistant(self):
        dlg = startup.StartupDialog(self, self.recent_files())
        if dlg.exec_() != QDialog.Accepted or not dlg.action:
            return
        kind, arg = dlg.action
        if kind == "open":
            self.maybe_open(arg)
            return
        if not self.maybe_discard():
            return
        self.load_document(startup.make_document(kind, arg))

    def load_document(self, doc):
        self.doc = doc
        self.page_index, self._pix = 0, {}
        self.undo.clear()
        self.master_btn.setChecked(False)
        self.reload()
        self.last = self.doc.snapshot()
        self.update_title()
        QTimer.singleShot(50, self.fit_page)

    def new_site(self):
        if not self.maybe_discard():
            return
        self.doc = Document()
        from . import formtools
        formtools.apply_defaults(self.doc)
        self.page_index, self._pix = 0, {}
        self.undo.clear()
        self.master_btn.setChecked(False)
        self.reload()
        self.last = self.doc.snapshot()
        self.update_title()

    def open_dialog(self):
        if not self.maybe_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open site", "", FILTER)
        if path:
            self.open_path(path)

    def import_wpack(self):
        if not self.maybe_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import a WebPlus pack", "",
                                              "WebPlus pack (*.wpack *.zip);;All files (*)")
        if path:
            self.import_wpack_path(path)

    def import_wpack_path(self, path):
        from . import wpimport
        dirs = [os.path.expanduser("~/projects/webplus-extract")]
        try:
            doc, rep = wpimport.import_pack(path, dirs)
        except Exception as e:  # noqa: BLE001 - tell the user why it was not readable
            QMessageBox.warning(self, APP, "Could not import that file:\n%s" % e)
            return
        self.doc = doc
        self.page_index, self._pix = 0, {}
        self.undo.clear()
        self.reload()
        self.last = self.doc.snapshot()
        self.update_title()
        self.statusBar().showMessage("Imported: " + wpimport.describe(rep), 10000)

    def open_path(self, path):
        if path.lower().endswith((".wpp", ".wpack")):
            self.import_wpack_path(path)
            self.doc.path = ""          # saving asks for a new .site name, never overwrites the WebPlus file
            self.update_title()
            return
        try:
            self.doc = Document.load(path)
        except Exception as e:  # noqa: BLE001 - show any load problem to the user
            QMessageBox.warning(self, APP, "Could not open that file:\n%s" % e)
            return
        self.page_index, self._pix = 0, {}
        self.undo.clear()
        self.reload()
        self.last = self.doc.snapshot()
        self.update_title()
        self.remember(path)

    def save(self):
        if not self.doc.path:
            return self.save_as()
        self.doc.save(self.doc.path)
        self.undo.setClean()
        self.update_title()
        return True

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save web page", "my-website.site", FILTER)
        if not path:
            return False
        if not path.endswith((".site", ".sitewright")):
            path += ".site"
        self.doc.save(path)
        self.undo.setClean()
        self.update_title()
        self.remember(path)
        return True

    def export_dialog(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder for the website")
        if d:
            n = len(export.export_site(self.doc, d))
            self.statusBar().showMessage("Exported %d files to %s" % (n, d), 6000)

    def preview(self):
        d = tempfile.mkdtemp(prefix="sitewright-")
        export.export_site(self.doc, d, clean=False, preview=True)  # no folders, no PHP from a file
        first = export.page_files(self.doc, False, php=False)[self.cur_page()["id"]]
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.join(d, first)))

    def closeEvent(self, e):
        if self.maybe_discard():
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                st = QSettings("4ThePeopleMedia", "Sitewright")
                st.setValue("window/state", self.saveState(STATE_VERSION))
            e.accept()
        else:
            e.ignore()
