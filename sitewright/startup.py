"""Startup Assistant: Home / Open / Learn / New Site / Templates / News, with the
4ThePeople Media mark at the top left and the program name at the top right."""
from PyQt5.QtCore import QPointF, QRectF, QSettings, QSize, Qt, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF)
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                             QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QListView, QListWidget, QListWidgetItem,
                             QPushButton, QSpinBox, QStackedWidget,
                             QTextBrowser, QVBoxLayout, QWidget)

from . import helpdocs, templates
from .model import Document, new_item
from .schemes import SCHEMES, apply_scheme
from .styles import NAV_STYLES

BRAND = "4ThePeople Media"
PROGRAM = "WebPlus"
HEADLINE_NAME = "WebPlus"          # the name shown big in the welcome headline and the top-right corner
NAVY, RED, WHITE = QColor("#0a2a5e"), QColor("#c8102e"), QColor("#ffffff")
# the Startup Assistant wears the flag: red for what is chosen, navy for the rest
GREEN = RED
GREY = NAVY

SIZES = [("Desktop (960 wide)", 960), ("Small desktop (800 wide)", 800),
         ("Wide desktop (1200 wide)", 1200), ("Tablet (768 wide)", 768)]

TIPS = [
    ("Place things on the page", "Pick a tool in the Tools panel, then drag on the page. "
     "Use the pointer to move things and the handles to resize."),
    ("Add pages", "Use Add in the Site panel, or Properties > Page from template. "
     "Drag pages in the list to nest them under another page."),
    ("Make a menu", "Insert > Navigation bar from gallery builds a menu from your pages "
     "and keeps it up to date."),
    ("Change all the colours", "Tools > Colour scheme designer swaps the site's 12 colours "
     "everywhere at once. Site themes change fonts and buttons too."),
    ("Work on phones", "Your site is laid out for phones and tablets automatically. "
     "Set the design width in Site Properties."),
    ("Add a contact form", "Insert > Form field, then set the email address in "
     "Tools > Form email address."),
    ("Check before you publish", "The Task Monitor along the bottom lists things to fix, "
     "such as pictures without a description."),
    ("Publish", "File > Publish site to the web (FTP) uploads your site. "
     "Quick publish sends only what changed."),
]

NEWS = """<h3>What's new</h3>
<p><b>WebPlus</b> is a website designer made by %s.</p>
<ul>
<li>Pages, a site tree, master pages and starter templates</li>
<li>Photo galleries, tables, maps, video, audio and forms that really send email</li>
<li>30 gallery buttons, 10 navigation styles, colour schemes and themes</li>
<li>Sites that fit phones, tablets and any browser window</li>
<li>Spell checker, anchors, Task Monitor and FTP publishing</li>
<li>Pen tool, shapes, crop to shape, PhotoLab and picture effects</li>
<li>Database Merge, PDF export and one-file widgets</li>
<li>A blog with comments, web polls, and a shop with PayPal, Stripe, Shopify and WooCommerce</li>
</ul>""" % BRAND


class LogoBadge(QWidget):
    """The 4ThePeople Media mark: navy field, stars, red and white stripes."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(138, 74)          # about 1.4 inches wide: a small mark, not a banner

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setBrush(NAVY)
        p.drawRoundedRect(r, 5, 5)
        # stripes along the bottom
        h = 4.0
        y = r.bottom() - 3 * h - 4
        for i, c in enumerate((RED, WHITE, RED)):
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRect(QRectF(r.left() + 8, y + i * h, r.width() - 16, h))
        # a row of stars
        p.setBrush(WHITE)
        for i in range(5):
            self.star(p, QPointF(r.center().x() + (i - 2) * 19, r.top() + 11), 5.5)
        f = QFont("DejaVu Serif")
        f.setPixelSize(17)
        f.setBold(True)
        p.setFont(f)
        p.setPen(WHITE)
        first, _, second = BRAND.partition(" ")
        p.drawText(QRectF(r.left(), r.top() + 19, r.width(), 22), int(Qt.AlignCenter), first)
        p.drawText(QRectF(r.left(), r.top() + 37, r.width(), 22), int(Qt.AlignCenter), second)

    @staticmethod
    def star(p, c, r):
        import math
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rad = r if i % 2 == 0 else r * 0.42
            pts.append(QPointF(c.x() + rad * math.cos(ang), c.y() + rad * math.sin(ang)))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF(pts))


class Banner(QWidget):
    """A simple flag-style picture for the Home page."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(250)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, Hh = self.width(), self.height()
        # the flag keeps its real shape (10 : 19) and sits at the left of the space
        H = min(Hh - 44, W / 1.9)
        w = H * 1.9
        sh = H / 13.0
        for i in range(13):
            p.fillRect(QRectF(0, i * sh, w, sh + 1), RED if i % 2 == 0 else WHITE)
        cw, ch = H * 0.76, sh * 7
        p.fillRect(QRectF(0, 0, cw, ch), NAVY)
        p.setBrush(WHITE)
        # fifty stars: nine rows, alternately six and five (the official layout)
        r = H * 0.0616 / 2
        for row in range(9):
            y = H * 0.054 * (row + 1)
            if row % 2 == 0:
                xs = [H * 0.063 * (2 * j + 1) for j in range(6)]
            else:
                xs = [H * 0.063 * (2 * j + 2) for j in range(5)]
            for x in xs:
                LogoBadge.star(p, QPointF(x, y), r)
        p.fillRect(QRectF(0, Hh - 40, W, 40), QColor(255, 255, 255, 215))
        f = QFont()
        f.setPixelSize(15)
        p.setFont(f)
        p.setPen(QColor("#555555"))
        p.drawText(QRectF(10, Hh - 38, W - 20, 36), int(Qt.AlignVCenter | Qt.AlignRight),
                   "Design it. Build it. Put it on the web.")


class NavTile(QWidget):
    clicked = pyqtSignal()

    def __init__(self, text, badge=0):
        super().__init__()
        self.text, self.badge, self.active, self.hover = text, badge, False, False
        self.setFixedSize(128, 62 if not badge else 78)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def colour(self):
        """Red when chosen, navy otherwise; under the mouse each turns into the other."""
        red = self.active != self.hover
        return RED if red else NAVY

    def set_active(self, on):
        self.active = on
        self.update()

    def mousePressEvent(self, e):
        self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), self.colour())
        p.setPen(WHITE)
        f = QFont()
        f.setPixelSize(13)
        p.setFont(f)
        if self.badge:
            f2 = QFont()
            f2.setPixelSize(20)
            p.setFont(f2)
            p.drawText(QRectF(0, 6, self.width() - 10, 26), int(Qt.AlignRight), str(self.badge))
            p.setFont(f)
        p.drawText(QRectF(0, 0, self.width(), self.height() - (6 if self.badge else 0)),
                   int(Qt.AlignHCenter | Qt.AlignBottom if self.badge else Qt.AlignCenter),
                   self.text)


def thumbnail(pages, width, w=210, h=150, bg="#ffffff"):
    """A small schematic picture of the first page of a template."""
    pm = QPixmap(w, h)
    pm.fill(QColor("#ffffff"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    page = pages[0]
    k = (w - 2) / width
    p.fillRect(QRectF(0, 0, w, h), QColor(bg))
    for it in page["items"]:
        r = QRectF(it["x"] * k, it["y"] * k, max(it["w"] * k, 1.5), max(it.get("h", 2) * k, 1.5))
        kind = it["kind"]
        col = QColor(it.get("fill") or "#b8c2cf")
        if kind in ("rect", "button", "navbar"):
            p.fillRect(r, col if it.get("fill") else QColor("#c9d2dd"))
        elif kind == "ellipse":
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            p.drawEllipse(r)
        elif kind in ("image", "gallery", "video", "map", "slider", "frame"):
            p.fillRect(r, QColor("#cfe0f1"))
            if kind in ("image", "gallery"):
                p.setPen(QPen(QColor("#9fb8d3"), max(r.height() * 0.06, 1)))
                p.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.center().x(), r.center().y()))
                p.drawLine(QPointF(r.center().x(), r.center().y()), QPointF(r.right(), r.bottom()))
        elif kind == "social":
            p.setPen(Qt.NoPen)
            n = len(it.get("nets") or [1, 2, 3])
            d = max(min(r.height(), 12), 5)
            for i, c in enumerate(("#3b5998", "#c13584", "#111111", "#5b6b7c")[:n]):
                p.setBrush(QColor(c))
                p.drawRoundedRect(QRectF(r.left() + i * (d + 3), r.top(), d, d), d * .25, d * .25)
        elif kind in ("field", "search", "subscribe", "login"):
            p.setBrush(QColor("#ffffff"))
            p.setPen(QPen(QColor("#9aa7b6"), 0.8))
            p.drawRect(r)
        elif kind in ("html", "marquee", "audio"):
            p.fillRect(r, QColor("#e6e9ee"))
        elif kind == "table":
            p.setPen(QPen(QColor("#9aa7b6"), 0.7))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)
            for i in range(1, it.get("rows", 3)):
                y = r.top() + r.height() * i / it["rows"]
                p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        elif kind == "text":
            size = max(it.get("size", 16) * k, 1.2)
            p.setPen(QPen(QColor(it.get("color") or "#444444"), size * 0.7))
            lines = max(1, min(3, int(r.height() / (size * 2.2)) + 1))
            for i in range(lines):
                y = r.top() + size + i * size * 2
                p.drawLine(QPointF(r.left(), y), QPointF(r.left() + r.width() * (0.9 - i * 0.2), y))
    p.setPen(QPen(QColor("#b0b8c2"), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRect(0, 0, w - 1, h - 1)
    p.end()
    return pm


def make_document(kind, spec):
    """Build a new site from the Startup Assistant's choices."""
    doc = Document()
    width = spec.get("width", 960)
    doc.width = width
    if kind == "template":
        pages = templates.build_site(spec["template"], width)
        doc.site_title = spec.get("name") or spec["template"]
    else:
        n = max(1, spec.get("pages", 1))
        names = ["Home"] + ["Page %d" % (i + 2) for i in range(n - 1)]
        pages = [dict(name=nm, items=[], h=700) for nm in names]
        doc.site_title = spec.get("name") or "My Website"
    from .model import new_page
    doc.pages = []
    for pg in pages:
        doc.pages.append(new_page(pg["name"], items=pg["items"], h=pg["h"]))
    if spec.get("nav", True):
        nb = new_item("navbar", 0, 0, w=width, h=48)
        nb.update(NAV_STYLES["Classic bar"])
        doc.master = [nb]
    scheme = SCHEMES.get(spec.get("scheme", "Default"), SCHEMES["Default"])
    apply_scheme(doc, scheme)
    for p in doc.pages:
        p["bg"] = scheme[0]
    return doc


class StartupDialog(QDialog):
    def __init__(self, parent=None, recent=()):
        super().__init__(parent)
        self.setWindowTitle("Startup Assistant - " + PROGRAM)
        self.resize(960, 600)
        self.setStyleSheet("StartupDialog{background:#ffffff}")
        self.action = None
        self.recent = [r for r in recent]
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 8)
        head = QHBoxLayout()
        head.addWidget(LogoBadge())
        head.addStretch(1)
        name = QLabel(HEADLINE_NAME)
        f = QFont()
        f.setPixelSize(30)
        name.setFont(f)
        name.setStyleSheet("color:#0a2a5e")
        head.addWidget(name)
        mark = QLabel()
        pm = QPixmap(34, 34)
        pm.fill(Qt.transparent)
        pp = QPainter(pm)
        pp.setRenderHint(QPainter.Antialiasing)
        pp.setBrush(NAVY)
        pp.setPen(Qt.NoPen)
        pp.drawRoundedRect(0, 0, 34, 34, 8, 8)
        pp.setBrush(WHITE)
        LogoBadge.star(pp, QPointF(17, 17.5), 11)
        pp.end()
        mark.setPixmap(pm)
        head.addWidget(mark)
        outer.addLayout(head)

        body = QHBoxLayout()
        nav = QVBoxLayout()
        nav.setSpacing(6)
        self.tiles = []
        for text, badge in (("Home", 0), ("Open", 0), ("Learn", len(TIPS) + len(helpdocs.ARTICLES)),
                            ("New Site", 0), ("Templates", 0), ("News", 3)):
            t = NavTile(text, badge)
            t.clicked.connect(lambda i=len(self.tiles): self.show_page(i))
            self.tiles.append(t)
            nav.addWidget(t)
        nav.addStretch(1)
        body.addLayout(nav)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)
        foot = QHBoxLayout()
        self.show_again = QCheckBox("Show this window when %s starts" % PROGRAM)
        self.show_again.setChecked(True)
        foot.addWidget(self.show_again)
        foot.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        foot.addWidget(close)
        outer.addLayout(foot)

        self.build_home()
        self.build_open()
        self.build_learn()
        self.build_new()
        self.build_templates()
        self.build_news()
        self.show_page(0)

    # -- pages -----------------------------------------------------------
    def show_page(self, i):
        self.stack.setCurrentIndex(i)
        for n, t in enumerate(self.tiles):
            t.set_active(n == i)

    def go_button(self, text, fn):
        b = QPushButton(text + "  ➜")
        b.setFixedSize(180, 56)
        b.setStyleSheet("QPushButton{background:#c8102e;color:white;font-size:22px;border:0}"
                        "QPushButton:hover{background:#0a2a5e}")
        b.clicked.connect(fn)
        return b

    def build_home(self):
        w = QWidget()
        v = QVBoxLayout(w)
        title = QLabel('Get started with <span style="color:#c8102e">%s</span> today…' % HEADLINE_NAME)
        f = QFont()
        f.setPixelSize(32)
        title.setFont(f)
        title.setStyleSheet("color:#0a2a5e")
        v.addWidget(title)
        sub = QLabel("New here? Start a new site, or pick a template and make it yours.")
        sub.setStyleSheet("color:#3c4b66;font-size:16px")
        v.addWidget(sub)
        v.addWidget(Banner(), 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.go_button("Go", lambda: self.show_page(3)))
        v.addLayout(row)
        self.stack.addWidget(w)

    def build_open(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>Open a site</h2>"))
        self.recent_list = QListWidget()
        for path in self.recent:
            it = QListWidgetItem(path.split("/")[-1])
            it.setToolTip(path)
            it.setData(Qt.UserRole, path)
            self.recent_list.addItem(it)
        self.recent_list.itemDoubleClicked.connect(
            lambda it: self.choose(("open", it.data(Qt.UserRole))))
        v.addWidget(self.recent_list, 1)
        row = QHBoxLayout()
        b = QPushButton("Browse for a site...")
        b.clicked.connect(self.browse)
        row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        self.stack.addWidget(w)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open site", "",
                                              "Web page (*.site *.sitewright)")
        if path:
            self.choose(("open", path))

    def build_learn(self):
        w = QWidget()
        v = QHBoxLayout(w)
        lst = QListWidget()
        topics = [(t, "<p style='font-size:15px'>%s</p>" % x) for t, x in TIPS] + \
            list(helpdocs.ARTICLES)
        for title, _text in topics:
            lst.addItem(title)
        view = QTextBrowser()
        lst.currentRowChanged.connect(
            lambda i: view.setHtml("<h2>%s</h2>%s" % topics[i]))
        v.addWidget(lst, 1)
        v.addWidget(view, 2)
        lst.setCurrentRow(0)
        self.stack.addWidget(w)

    def build_new(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>Start a new site</h2>"))
        f = QFormLayout()
        self.n_name = QLineEdit("My Website")
        self.n_scheme = QComboBox()
        self.n_scheme.addItems(list(SCHEMES))
        self.n_size = QComboBox()
        for label, _w in SIZES:
            self.n_size.addItem(label)
        self.n_pages = QSpinBox()
        self.n_pages.setRange(1, 30)
        self.n_pages.setValue(3)
        self.n_nav = QCheckBox("Add a navigation bar")
        self.n_nav.setChecked(True)
        f.addRow("Site name", self.n_name)
        f.addRow("Colour scheme", self.n_scheme)
        f.addRow("Default page size", self.n_size)
        f.addRow("Initial number of pages", self.n_pages)
        f.addRow(self.n_nav)
        v.addLayout(f)
        v.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton("Start new site")
        b.setStyleSheet("QPushButton{background:#c8102e;color:white;padding:10px 18px;border:0;"
                        "font-size:15px}QPushButton:hover{background:#0a2a5e}")
        b.clicked.connect(self.start_new)
        row.addWidget(b)
        v.addLayout(row)
        self.stack.addWidget(w)

    def start_new(self):
        self.choose(("new", dict(name=self.n_name.text().strip() or "My Website",
                                 scheme=self.n_scheme.currentText(),
                                 width=SIZES[self.n_size.currentIndex()][1],
                                 pages=self.n_pages.value(), nav=self.n_nav.isChecked())))

    def build_templates(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>Templates</h2>"))
        self.t_list = QListWidget()
        self.t_list.setViewMode(QListView.IconMode)
        self.t_list.setIconSize(QSize(210, 150))
        self.t_list.setResizeMode(QListView.Adjust)
        self.t_list.setMovement(QListView.Static)
        self.t_list.setSpacing(12)
        for name in templates.SITE_TEMPLATES:
            pages = templates.build_site(name, 960)
            it = QListWidgetItem(QIcon(thumbnail(pages, 960)), name)
            it.setData(Qt.UserRole, name)
            self.t_list.addItem(it)
        self.t_list.itemDoubleClicked.connect(lambda *_: self.use_template())
        v.addWidget(self.t_list, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Colour scheme:"))
        self.t_scheme = QComboBox()
        self.t_scheme.addItems(list(SCHEMES))
        row.addWidget(self.t_scheme)
        row.addStretch(1)
        b = QPushButton("Use this template")
        b.setStyleSheet("QPushButton{background:#0a2a5e;color:white;padding:10px 18px;border:0}"
                        "QPushButton:hover{background:#c8102e}")
        b.clicked.connect(self.use_template)
        row.addWidget(b)
        v.addLayout(row)
        self.stack.addWidget(w)

    def use_template(self):
        it = self.t_list.currentItem()
        if it is None:
            return
        self.choose(("template", dict(template=it.data(Qt.UserRole),
                                      scheme=self.t_scheme.currentText(), width=960,
                                      nav=True)))

    def build_news(self):
        w = QWidget()
        v = QVBoxLayout(w)
        view = QTextBrowser()
        view.setHtml(NEWS)
        v.addWidget(view)
        self.stack.addWidget(w)

    def choose(self, action):
        self.action = action
        QSettings("4ThePeopleMedia", "Sitewright").setValue(
            "show_start", self.show_again.isChecked())
        self.accept()

    def done(self, r):
        QSettings("4ThePeopleMedia", "Sitewright").setValue(
            "show_start", self.show_again.isChecked())
        super().done(r)
