"""Dialogs for search-engine settings, feeds, YouTube, forms, symbols, source, help."""
import datetime

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QPlainTextEdit,
                             QPushButton, QSpinBox, QTabWidget, QTextBrowser,
                             QToolButton, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from . import forms, helpdocs

PICTURES = "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg *.ico)"


def buttons(dlg, ok="OK"):
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.button(QDialogButtonBox.Ok).setText(ok)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


# --------------------------------------------------------------- SEO
class SeoDialog(QDialog):
    """Search engine settings. Each page's description lives in ONE place here."""

    def __init__(self, parent, doc, page):
        super().__init__(parent)
        self.doc, self.page = doc, page
        self.og_asset, self.site_og, self.favicon = (page.get("og_image", ""),
                                                      doc.seo.get("og_image", ""),
                                                      doc.seo.get("favicon", ""))
        self.setWindowTitle("Search engine optimisation")
        self.resize(560, 560)
        v = QVBoxLayout(self)
        tabs = QTabWidget()
        v.addWidget(tabs)

        # this page
        w = QWidget()
        f = QFormLayout(w)
        self.title = QLineEdit(page.get("title") or page["name"])
        self.desc = QPlainTextEdit(page.get("description", ""))
        self.desc.setFixedHeight(80)
        self.count = QLabel("")
        self.keywords = QLineEdit(page.get("keywords", ""))
        self.noindex = QCheckBox("Ask search engines not to list this page")
        self.noindex.setChecked("noindex" in page.get("robots", ""))
        self.og_btn = QPushButton("Choose a picture for social sites...")
        self.og_btn.clicked.connect(self.pick_page_og)
        self.preview = QLabel("")
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("background:white;border:1px solid #ccc;padding:8px")
        f.addRow("Page title", self.title)
        f.addRow("Description", self.desc)
        f.addRow("", self.count)
        f.addRow("Keywords", self.keywords)
        f.addRow(self.noindex)
        f.addRow(self.og_btn)
        f.addRow("How it may look in search results:", self.preview)
        tabs.addTab(w, "This page")

        # whole site
        w2 = QWidget()
        g = QFormLayout(w2)
        s = doc.seo
        self.url = QLineEdit(s.get("site_url", ""))
        self.url.setPlaceholderText("https://www.example.com")
        self.site_desc = QPlainTextEdit(s.get("description", ""))
        self.site_desc.setFixedHeight(60)
        self.author = QLineEdit(s.get("author", ""))
        self.lang = QLineEdit(s.get("lang", "en"))
        self.ga = QLineEdit(s.get("analytics", ""))
        self.ga.setPlaceholderText("G-XXXXXXXXXX")
        self.gv = QLineEdit(s.get("google_verify", ""))
        self.bv = QLineEdit(s.get("bing_verify", ""))
        self.clean = QCheckBox("Clean addresses (/about/ instead of /about.html)")
        self.clean.setChecked(doc.clean_urls)
        self.head = QPlainTextEdit(s.get("head_code", ""))
        self.head.setFixedHeight(70)
        b1 = QPushButton("Site icon (favicon)...")
        b1.clicked.connect(self.pick_favicon)
        b2 = QPushButton("Default picture for social sites...")
        b2.clicked.connect(self.pick_site_og)
        g.addRow("Site web address", self.url)
        g.addRow("Default description", self.site_desc)
        g.addRow("Author", self.author)
        g.addRow("Language code", self.lang)
        g.addRow("Google Analytics ID", self.ga)
        g.addRow("Google verification code", self.gv)
        g.addRow("Bing verification code", self.bv)
        g.addRow(self.clean)
        g.addRow(b1)
        g.addRow(b2)
        g.addRow("Extra code for every page's head", self.head)
        tabs.addTab(w2, "Whole site")

        # this page: head code + CSS
        w3 = QWidget()
        h = QFormLayout(w3)
        self.page_head = QPlainTextEdit(page.get("head_code", ""))
        self.page_head.setFixedHeight(110)
        self.page_css = QPlainTextEdit(page.get("css", ""))
        self.page_css.setFixedHeight(150)
        h.addRow("Extra head code (meta tags, scripts)", self.page_head)
        h.addRow("Page CSS", self.page_css)
        tabs.addTab(w3, "Page code")

        v.addWidget(buttons(self))
        for wd in (self.title, self.keywords, self.url):
            wd.textChanged.connect(self.update_preview)
        self.desc.textChanged.connect(self.update_preview)
        self.update_preview()

    def pick_page_og(self):
        p, _ = QFileDialog.getOpenFileName(self, "Picture", "", PICTURES)
        if p:
            self.og_asset = self.doc.add_asset(p)
            self.og_btn.setText("Social picture: " + p.split("/")[-1])

    def pick_site_og(self):
        p, _ = QFileDialog.getOpenFileName(self, "Picture", "", PICTURES)
        if p:
            self.site_og = self.doc.add_asset(p)

    def pick_favicon(self):
        p, _ = QFileDialog.getOpenFileName(self, "Site icon", "", PICTURES)
        if p:
            self.favicon = self.doc.add_asset(p)

    def update_preview(self):
        n = len(self.desc.toPlainText())
        colour = "#2e7d32" if 70 <= n <= 160 else ("#c62828" if n > 160 else "#8a6d00")
        self.count.setText('<span style="color:%s">%d characters (aim for 120 to 160)</span>' % (colour, n))
        title = self.title.text() or self.page["name"]
        url = (self.url.text().rstrip("/") or "https://www.example.com") + "/"
        desc = self.desc.toPlainText() or self.site_desc.toPlainText() or \
            "No description yet - search engines will pick text from the page."
        warn = "" if len(title) <= 60 else '<br><i style="color:#c62828">Title is long; it may be cut off.</i>'
        self.preview.setText(
            '<div style="color:#1a0dab;font-size:16px">%s</div>'
            '<div style="color:#006621">%s</div><div style="color:#545454">%s</div>%s'
            % (title, url, desc[:170] + ("..." if len(desc) > 170 else ""), warn))

    def apply(self):
        p, d = self.page, self.doc
        p["title"] = self.title.text().strip() or p["name"]
        p["description"] = self.desc.toPlainText().strip()
        p["keywords"] = self.keywords.text().strip()
        p["robots"] = "noindex,nofollow" if self.noindex.isChecked() else ""
        p["og_image"] = self.og_asset
        p["head_code"] = self.page_head.toPlainText()
        p["css"] = self.page_css.toPlainText()
        d.seo.update(site_url=self.url.text().strip(), description=self.site_desc.toPlainText().strip(),
                     author=self.author.text().strip(), lang=self.lang.text().strip() or "en",
                     analytics=self.ga.text().strip(), google_verify=self.gv.text().strip(),
                     bing_verify=self.bv.text().strip(), head_code=self.head.toPlainText(),
                     og_image=self.site_og, favicon=self.favicon)
        d.clean_urls = self.clean.isChecked()


# --------------------------------------------------------------- RSS / podcast
class FeedItemDialog(QDialog):
    def __init__(self, parent, doc, item=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Feed item")
        it = item or {}
        self.asset = it.get("asset", "")
        f = QFormLayout(self)
        self.title = QLineEdit(it.get("title", ""))
        self.desc = QPlainTextEdit(it.get("description", ""))
        self.desc.setFixedHeight(80)
        self.date = QLineEdit(it.get("date") or datetime.date.today().isoformat())
        self.link = QComboBox()
        self.link.setEditable(True)
        self.link.addItem("", "")
        for p in doc.pages:
            if p.get("type", "page") == "page":
                self.link.addItem("Page: " + p["name"], "page:" + p["id"])
        cur = it.get("link", "")
        i = self.link.findData(cur)
        if i >= 0:
            self.link.setCurrentIndex(i)
        else:
            self.link.setCurrentText(cur)
        self.audio_url = QLineEdit(it.get("audio_url", ""))
        self.audio_btn = QPushButton("Audio file..." if not self.asset
                                     else "Audio: " + doc.assets.get(self.asset, {}).get("name", ""))
        self.audio_btn.clicked.connect(self.pick)
        f.addRow("Title", self.title)
        f.addRow("Description", self.desc)
        f.addRow("Date (YYYY-MM-DD)", self.date)
        f.addRow("Links to", self.link)
        f.addRow("Audio web address", self.audio_url)
        f.addRow(self.audio_btn)
        f.addRow(buttons(self))

    def pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "Audio", "", "Audio (*.mp3 *.m4a *.ogg *.wav)")
        if p:
            self.asset = self.doc.add_asset(p)
            self.audio_btn.setText("Audio: " + p.split("/")[-1])

    def values(self):
        i = self.link.currentIndex()
        link = self.link.itemData(i) if self.link.itemText(i) == self.link.currentText() \
            else self.link.currentText()
        import uuid
        return dict(title=self.title.text().strip(), description=self.desc.toPlainText().strip(),
                    date=self.date.text().strip(), link=link or "", asset=self.asset,
                    audio_url=self.audio_url.text().strip(), id=uuid.uuid4().hex[:10])


class FeedDialog(QDialog):
    def __init__(self, parent, doc):
        super().__init__(parent)
        self.doc = doc
        self.feed = dict(doc.feed)
        self.feed["items"] = [dict(i) for i in doc.feed.get("items", [])]
        self.setWindowTitle("RSS feed / podcast")
        self.resize(560, 560)
        v = QVBoxLayout(self)
        self.enabled = QCheckBox("Publish a feed (feed.xml) with this site")
        self.enabled.setChecked(self.feed.get("enabled", False))
        v.addWidget(self.enabled)
        f = QFormLayout()
        fd = self.feed
        self.title = QLineEdit(fd.get("title", ""))
        self.desc = QLineEdit(fd.get("description", ""))
        self.author = QLineEdit(fd.get("author", ""))
        self.email = QLineEdit(fd.get("email", ""))
        self.category = QLineEdit(fd.get("category", ""))
        self.explicit = QCheckBox("Contains explicit content")
        self.explicit.setChecked(fd.get("explicit", False))
        self.cover = QPushButton("Cover picture..." if not fd.get("image") else "Cover picture set")
        self.cover.clicked.connect(self.pick_cover)
        f.addRow("Title", self.title)
        f.addRow("Description", self.desc)
        f.addRow("Author", self.author)
        f.addRow("Contact email", self.email)
        f.addRow("Podcast category", self.category)
        f.addRow(self.explicit)
        f.addRow(self.cover)
        v.addLayout(f)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Title", "Date", "Audio"])
        self.tree.setRootIsDecorated(False)
        v.addWidget(self.tree, 1)
        row = QHBoxLayout()
        for text, fn in (("Add item...", self.add), ("Edit...", self.edit), ("Remove", self.remove)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(QLabel("Podcast apps need full web addresses: set your site address in "
                           "Search engine optimisation."))
        v.addWidget(buttons(self))
        self.fill()

    def fill(self):
        self.tree.clear()
        for it in self.feed["items"]:
            a = self.doc.assets.get(it.get("asset"), {}).get("name") or it.get("audio_url", "")
            self.tree.addTopLevelItem(QTreeWidgetItem([it.get("title", ""), it.get("date", ""), a]))

    def pick_cover(self):
        p, _ = QFileDialog.getOpenFileName(self, "Cover picture", "", PICTURES)
        if p:
            self.feed["image"] = self.doc.add_asset(p)
            self.cover.setText("Cover picture set")

    def add(self):
        d = FeedItemDialog(self, self.doc)
        if d.exec_() == QDialog.Accepted:
            self.feed["items"].insert(0, d.values())
            self.fill()

    def edit(self):
        i = self.tree.indexOfTopLevelItem(self.tree.currentItem())
        if i < 0:
            return
        d = FeedItemDialog(self, self.doc, self.feed["items"][i])
        if d.exec_() == QDialog.Accepted:
            self.feed["items"][i] = d.values()
            self.fill()

    def remove(self):
        i = self.tree.indexOfTopLevelItem(self.tree.currentItem())
        if i >= 0:
            del self.feed["items"][i]
            self.fill()

    def apply(self):
        self.feed.update(enabled=self.enabled.isChecked(), title=self.title.text().strip(),
                         description=self.desc.text().strip(), author=self.author.text().strip(),
                         email=self.email.text().strip(), category=self.category.text().strip(),
                         explicit=self.explicit.isChecked())
        self.doc.feed = self.feed


# --------------------------------------------------------------- YouTube
class YouTubeDialog(QDialog):
    def __init__(self, parent, values=None):
        super().__init__(parent)
        self.setWindowTitle("Embed YouTube Video")
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Enter the ID of the YouTube video, or paste the video's link here:"))
        self.url = QLineEdit((values or {}).get("url", ""))
        v.addWidget(self.url)
        v.addWidget(QLabel("The ID is the 11 letters, numbers and dashes after v= in the link."))
        g = QGridLayout()
        vals = dict(autoplay=False, loop=False, showinfo=True, fullscreen=True,
                    related=True, hd=False, border=False)
        vals.update(values or {})
        self.opts = {}
        labels = [("autoplay", "Autoplay (starts muted)"), ("fullscreen", "Allow full screen mode"),
                  ("loop", "Loop"), ("related", "Include related videos"),
                  ("showinfo", "Show video info"), ("hd", "Play in HD"),
                  ("border", "Show border")]
        for i, (k, text) in enumerate(labels):
            c = QCheckBox(text)
            c.setChecked(bool(vals[k]))
            self.opts[k] = c
            g.addWidget(c, i // 2, i % 2)
        v.addLayout(g)
        v.addWidget(buttons(self))

    def values(self):
        d = {k: c.isChecked() for k, c in self.opts.items()}
        d["url"] = self.url.text().strip()
        return d


# --------------------------------------------------------------- forms
class FieldDialog(QDialog):
    def __init__(self, parent, field=None):
        super().__init__(parent)
        self.setWindowTitle("Form field")
        f = QFormLayout(self)
        fd = field or dict(label="", type="text")
        self.label = QLineEdit(fd.get("label", ""))
        self.type = QComboBox()
        from .model import FIELD_LABELS, FIELD_TYPES
        for t in FIELD_TYPES:
            if t not in ("submit", "captcha", "recaptcha"):
                self.type.addItem(FIELD_LABELS[t], t)
        self.type.setCurrentIndex(max(self.type.findData(fd.get("type", "text")), 0))
        self.required = QCheckBox("Visitors must fill this in")
        self.required.setChecked(bool(fd.get("required")))
        self.options = QPlainTextEdit(fd.get("options", ""))
        self.options.setFixedHeight(70)
        self.options.setPlaceholderText("Choices, one per line (combo box only)")
        f.addRow("Label", self.label)
        f.addRow("Type", self.type)
        f.addRow(self.required)
        f.addRow(self.options)
        f.addRow(buttons(self))

    def values(self):
        d = dict(label=self.label.text().strip() or "Field", type=self.type.currentData(),
                 required=self.required.isChecked())
        if d["type"] == "select":
            d["options"] = self.options.toPlainText()
        return d


class FormDesigner(QDialog):
    """Pick fields, order and a look; the result is placed on the page as real fields."""

    def __init__(self, parent, doc):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Form Designer")
        self.resize(820, 560)
        self.fields = [dict(f) for f in forms.FORM_TEMPLATES["Contact"]]
        outer = QHBoxLayout(self)
        left = QVBoxLayout()
        outer.addLayout(left, 1)
        self.template = QComboBox()
        self.template.addItems(list(forms.FORM_TEMPLATES) + ["Start empty"])
        self.template.currentTextChanged.connect(self.load_template)
        left.addWidget(QLabel("Start from"))
        left.addWidget(self.template)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Field", "Type", "Required"])
        self.tree.setRootIsDecorated(False)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit())
        left.addWidget(self.tree, 1)
        row = QHBoxLayout()
        for text, fn in (("Add", self.add), ("Edit", self.edit), ("Remove", self.remove),
                         ("Up", lambda: self.move(-1)), ("Down", lambda: self.move(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        left.addLayout(row)
        f = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItems(list(forms.THEMES))
        self.theme.currentTextChanged.connect(self.refresh_preview)
        self.title = QLineEdit("Contact us")
        self.submit = QLineEdit("Send message")
        self.width = QSpinBox()
        self.width.setRange(240, 900)
        self.width.setValue(420)
        self.mail = QLineEdit(doc.form_email)
        self.mode = QComboBox()
        self.mode.addItems(["Send by email from my web host (PHP)",
                            "Open the visitor's email program",
                            "Send to another form service (address below)"])
        self.mode.setCurrentIndex({"php": 0, "mailto": 1, "custom": 2}.get(doc.form_mode, 0))
        self.action = QLineEdit(doc.form_action)
        for wd in (self.title, self.submit):
            wd.textChanged.connect(self.refresh_preview)
        f.addRow("Theme", self.theme)
        f.addRow("Heading", self.title)
        f.addRow("Button text", self.submit)
        f.addRow("Width (px)", self.width)
        f.addRow("Send messages to", self.mail)
        f.addRow("How to send", self.mode)
        f.addRow("Service address", self.action)
        left.addLayout(f)
        right = QVBoxLayout()
        outer.addLayout(right, 1)
        right.addWidget(QLabel("Preview"))
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.preview.setStyleSheet("background:white;border:1px solid #bbb")
        right.addWidget(self.preview, 1)
        right.addWidget(buttons(self, "Place on page"))
        self.fill()

    def load_template(self, name):
        self.fields = [dict(f) for f in forms.FORM_TEMPLATES.get(name, [])]
        self.fill()

    def fill(self):
        self.tree.clear()
        from .model import FIELD_LABELS
        for f in self.fields:
            self.tree.addTopLevelItem(QTreeWidgetItem(
                [f["label"], FIELD_LABELS.get(f["type"], f["type"]),
                 "yes" if f.get("required") else ""]))
        self.refresh_preview()

    def add(self):
        d = FieldDialog(self)
        if d.exec_() == QDialog.Accepted:
            self.fields.append(d.values())
            self.fill()

    def edit(self):
        i = self.tree.indexOfTopLevelItem(self.tree.currentItem())
        if i >= 0:
            d = FieldDialog(self, self.fields[i])
            if d.exec_() == QDialog.Accepted:
                self.fields[i] = dict(self.fields[i], **d.values())
                self.fill()

    def remove(self):
        i = self.tree.indexOfTopLevelItem(self.tree.currentItem())
        if i >= 0:
            del self.fields[i]
            self.fill()

    def move(self, step):
        i = self.tree.indexOfTopLevelItem(self.tree.currentItem())
        j = i + step
        if i >= 0 and 0 <= j < len(self.fields):
            self.fields[i], self.fields[j] = self.fields[j], self.fields[i]
            self.fill()
            self.tree.setCurrentItem(self.tree.topLevelItem(j))

    def build(self, x=60, y=60):
        return forms.build_form(self.fields, self.theme.currentText(), x=x, y=y,
                                w=self.width.value(), title=self.title.text().strip(),
                                submit=self.submit.text().strip() or "Send")

    def refresh_preview(self, *_):
        items, h = self.build(10, 10)
        W = self.width.value() + 20
        pm = QPixmap(W, max(h, 60))
        pm.fill(QColor("#ffffff"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        for it in items:
            r = QRectF(it["x"], it["y"], it["w"], it["h"])
            if it["kind"] == "text":
                f = QFont()
                f.setPixelSize(int(it.get("size", 14)))
                f.setBold(bool(it.get("bold")))
                p.setFont(f)
                p.setPen(QColor(it.get("color", "#222")))
                p.drawText(r, int(Qt.AlignLeft | Qt.AlignVCenter), it.get("text", ""))
                continue
            t = it.get("ftype")
            if t in ("checkbox", "radio"):
                p.setPen(QPen(QColor("#6b7480"), 1.5))
                p.setBrush(Qt.white)
                p.drawRect(QRectF(r.left(), r.top() + 6, 16, 16))
                p.setPen(QColor("#222"))
                p.drawText(QRectF(r.left() + 24, r.top(), r.width(), 28),
                           int(Qt.AlignLeft | Qt.AlignVCenter), it.get("label", ""))
            elif t == "submit":
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(it.get("fill") or "#2b7de9"))
                p.drawRoundedRect(r, it.get("radius", 4), it.get("radius", 4))
                p.setPen(QColor("white"))
                p.drawText(r, int(Qt.AlignCenter), it.get("label", ""))
            else:
                p.setBrush(QColor(it.get("fill") or "#ffffff"))
                p.setPen(QPen(QColor(it["stroke"]), it.get("sw", 1)) if it.get("stroke") and it.get("sw")
                         else Qt.NoPen)
                p.drawRoundedRect(r, it.get("radius", 4), it.get("radius", 4))
        p.end()
        self.preview.setPixmap(pm)

    def apply_mail(self):
        d = self.doc
        d.form_email = self.mail.text().strip()
        d.form_mode = ("php", "mailto", "custom")[self.mode.currentIndex()]
        d.form_action = self.action.text().strip()


# --------------------------------------------------------------- symbols, source, help
SYMBOLS = ("© ® ™ ° ± × ÷ ½ ⅓ ¼ ¾ … "
           "• – — « » ‘ ’ “ ” € £ ¥ ¢ "
           "← ↑ → ↓ ✓ ✗ ★ ☆ ♥ ☎ ✉ "
           "¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁰ ⁺ ⁻ "
           "₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉").split()


class SymbolDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Insert symbol")
        self.chosen = ""
        g = QGridLayout(self)
        for i, ch in enumerate(SYMBOLS):
            b = QToolButton()
            b.setText(ch)
            b.setFixedSize(38, 38)
            f = b.font()
            f.setPixelSize(18)
            b.setFont(f)
            b.clicked.connect(lambda _=False, c=ch: self.pick(c))
            g.addWidget(b, i // 12, i % 12)

    def pick(self, c):
        self.chosen = c
        self.accept()


class SourceDialog(QDialog):
    def __init__(self, parent, text, title="Page HTML source"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 560)
        v = QVBoxLayout(self)
        ed = QPlainTextEdit(text)
        ed.setReadOnly(True)
        f = QFont("Monospace")
        f.setStyleHint(QFont.TypeWriter)
        f.setPixelSize(13)
        ed.setFont(f)
        ed.setLineWrapMode(QPlainTextEdit.NoWrap)
        v.addWidget(ed)
        row = QHBoxLayout()
        cp = QPushButton("Copy all")
        cp.clicked.connect(lambda: __import__("PyQt5.QtWidgets", fromlist=["QApplication"])
                           .QApplication.clipboard().setText(text))
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(cp)
        row.addStretch(1)
        row.addWidget(close)
        v.addLayout(row)


class HelpDialog(QDialog):
    def __init__(self, parent, start=0):
        super().__init__(parent)
        self.setWindowTitle("Help articles")
        self.resize(820, 560)
        h = QHBoxLayout(self)
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search help")
        self.search.textChanged.connect(self.filter)
        left.addWidget(self.search)
        self.list = QListWidget()
        for title, _body in helpdocs.ARTICLES:
            self.list.addItem(title)
        left.addWidget(self.list, 1)
        h.addLayout(left, 1)
        self.view = QTextBrowser()
        h.addWidget(self.view, 2)
        self.list.currentRowChanged.connect(self.show_article)
        self.list.setCurrentRow(start)

    def show_article(self, i):
        if 0 <= i < len(helpdocs.ARTICLES):
            t, body = helpdocs.ARTICLES[i]
            self.view.setHtml("<h2>%s</h2>%s" % (t, body))

    def filter(self, text):
        t = text.lower()
        for i, (title, body) in enumerate(helpdocs.ARTICLES):
            self.list.item(i).setHidden(bool(t) and t not in (title + body).lower())


# --------------------------------------------------------------- slider studio
class _PreviewWin:
    """Just enough of the main window for the canvas drawing code to preview a slider."""

    def __init__(self, doc):
        self.doc, self._pix = doc, {}

    def pixmap(self, aid):
        if aid and aid not in self._pix:
            pm = QPixmap()
            pm.loadFromData(self.doc.asset_bytes(aid))
            self._pix[aid] = pm
        return self._pix.get(aid)


class ColourButton(QPushButton):
    def __init__(self, colour="#ffffff"):
        super().__init__()
        self.value = colour
        self.clicked.connect(self.pick)
        self.show_colour()

    def show_colour(self):
        lum = QColor(self.value).lightness()
        self.setText(self.value)
        self.setStyleSheet("background:%s;color:%s" % (self.value, "#000" if lum > 128 else "#fff"))

    def pick(self):
        from PyQt5.QtWidgets import QColorDialog
        c = QColorDialog.getColor(QColor(self.value), self, "Colour")
        if c.isValid():
            self.value = c.name()
            self.show_colour()
            self.changed()

    def changed(self):
        pass


ANIMS = [("Slide sideways", "slide"), ("Slide up and down", "vslide"),
         ("Fade", "fade"), ("Zoom and fade", "zoom")]


class SliderStudio(QDialog):
    """Edit a slider's panels and options, with a live preview."""

    def __init__(self, parent, doc, item):
        super().__init__(parent)
        import copy
        self.doc, self.item = doc, item
        self.panels = copy.deepcopy(item.get("panels") or [])
        self.opts = {k: item.get(k) for k in ("anim", "autoplay", "loop", "speed", "arrows",
                                             "dots", "pause", "start")}
        self.setWindowTitle("Slider Studio")
        self.resize(900, 640)
        self.busy = False
        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        outer.addLayout(top, 1)

        left = QVBoxLayout()
        top.addLayout(left, 1)
        left.addWidget(QLabel("Panels"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.select)
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, fn in (("Add", self.add), ("Copy", self.dup), ("Remove", self.remove),
                         ("Up", lambda: self.move(-1)), ("Down", lambda: self.move(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        left.addLayout(row)

        right = QVBoxLayout()
        top.addLayout(right, 2)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(250)
        self.preview.setStyleSheet("background:#e9edf2;border:1px solid #bbb")
        right.addWidget(self.preview)
        tabs = QTabWidget()
        right.addWidget(tabs)

        w = QWidget()
        f = QFormLayout(w)
        self.heading = QLineEdit()
        self.text = QPlainTextEdit()
        self.text.setFixedHeight(60)
        self.btn = QLineEdit()
        self.link = QComboBox()
        self.link.setEditable(True)
        self.link.addItem("", "")
        for p in doc.pages:
            if p.get("type", "page") == "page":
                self.link.addItem("Page: " + p["name"], "page:" + p["id"])
        self.align = QComboBox()
        self.align.addItems(["left", "center", "right"])
        self.pic = QPushButton("Choose picture...")
        self.pic.clicked.connect(self.pick_pic)
        clr = QPushButton("No picture")
        clr.clicked.connect(self.clear_pic)
        pr = QHBoxLayout()
        pr.addWidget(self.pic, 1)
        pr.addWidget(clr)
        self.bg = ColourButton("#1f3a5f")
        self.color = ColourButton("#ffffff")
        self.overlay = ColourButton("#000000")
        self.op = QSpinBox()
        self.op.setRange(0, 90)
        self.op.setSuffix(" % dark layer")
        f.addRow("Picture", pr)
        f.addRow("Background colour", self.bg)
        f.addRow("Heading", self.heading)
        f.addRow("Text", self.text)
        f.addRow("Button text", self.btn)
        f.addRow("Button goes to", self.link)
        f.addRow("Text position", self.align)
        f.addRow("Text colour", self.color)
        f.addRow("Layer over picture", self.overlay)
        f.addRow("", self.op)
        tabs.addTab(w, "Panel")

        w2 = QWidget()
        g = QFormLayout(w2)
        self.anim = QComboBox()
        for label, key in ANIMS:
            self.anim.addItem(label, key)
        self.anim.setCurrentIndex(max(self.anim.findData(self.opts["anim"]), 0))
        self.auto = QCheckBox("Play automatically")
        self.auto.setChecked(bool(self.opts["autoplay"]))
        self.pause = QCheckBox("Pause while the mouse is over it")
        self.pause.setChecked(bool(self.opts["pause"]))
        self.arrows = QCheckBox("Show arrows")
        self.arrows.setChecked(bool(self.opts["arrows"]))
        self.dots = QCheckBox("Show dots")
        self.dots.setChecked(bool(self.opts["dots"]))
        self.loop = QSpinBox()
        self.loop.setRange(1000, 60000)
        self.loop.setSingleStep(500)
        self.loop.setValue(int(self.opts["loop"] or 5000))
        self.loop.setSuffix(" ms between panels")
        self.speed = QSpinBox()
        self.speed.setRange(100, 5000)
        self.speed.setSingleStep(100)
        self.speed.setValue(int(self.opts["speed"] or 600))
        self.speed.setSuffix(" ms to change")
        self.start = QSpinBox()
        self.start.setRange(1, 99)
        self.start.setValue(int(self.opts["start"] or 1))
        g.addRow("Animation", self.anim)
        g.addRow(self.auto)
        g.addRow("Time on each panel", self.loop)
        g.addRow("Change takes", self.speed)
        g.addRow(self.pause)
        g.addRow(self.arrows)
        g.addRow(self.dots)
        g.addRow("Start on panel", self.start)
        g.addRow(QLabel("Visitors can also swipe on a touch screen or use the arrow keys."))
        tabs.addTab(w2, "Slider options")

        for wd in (self.heading, self.btn):
            wd.textEdited.connect(self.store)
        self.text.textChanged.connect(self.store)
        self.align.activated.connect(self.store)
        self.link.activated.connect(self.store)
        self.link.lineEdit().editingFinished.connect(self.store)
        self.op.valueChanged.connect(self.store)
        for cb in (self.bg, self.color, self.overlay):
            cb.changed = self.store
        for wd in (self.anim, ):
            wd.activated.connect(self.store)
        for wd in (self.auto, self.pause, self.arrows, self.dots):
            wd.toggled.connect(self.store)
        for wd in (self.loop, self.speed, self.start):
            wd.valueChanged.connect(self.store)
        outer.addWidget(buttons(self, "Done"))
        self.fill()
        self.list.setCurrentRow(0)

    # -- list handling ---------------------------------------------------
    def fill(self, keep=None):
        self.list.blockSignals(True)
        self.list.clear()
        for i, p in enumerate(self.panels):
            self.list.addItem("%d  %s" % (i + 1, p.get("heading") or "(no heading)"))
        self.list.blockSignals(False)
        if keep is not None and self.panels:
            self.list.setCurrentRow(min(keep, len(self.panels) - 1))

    def cur(self):
        i = self.list.currentRow()
        return self.panels[i] if 0 <= i < len(self.panels) else None

    def select(self, _row=None):
        p = self.cur()
        self.busy = True
        try:
            self.setEnabled(True)
            if p is None:
                return
            self.heading.setText(p.get("heading", ""))
            self.text.setPlainText(p.get("text", ""))
            self.btn.setText(p.get("btn", ""))
            i = self.link.findData(p.get("link", ""))
            if i >= 0:
                self.link.setCurrentIndex(i)
            else:
                self.link.setCurrentText(p.get("link", ""))
            self.align.setCurrentText(p.get("align", "left"))
            self.bg.value = p.get("bg", "#1f3a5f")
            self.bg.show_colour()
            self.color.value = p.get("color", "#ffffff")
            self.color.show_colour()
            self.overlay.value = p.get("overlay", "#000000")
            self.overlay.show_colour()
            self.op.setValue(int(p.get("overlay_op", 0)))
            a = p.get("asset")
            self.pic.setText("Picture: " + self.doc.assets[a]["name"] if a in self.doc.assets
                             else "Choose picture...")
        finally:
            self.busy = False
        self.draw()

    def store(self, *_):
        if self.busy:
            return
        p = self.cur()
        if p is not None:
            i = self.link.currentIndex()
            link = self.link.itemData(i) if self.link.itemText(i) == self.link.currentText() \
                else self.link.currentText()
            p.update(heading=self.heading.text(), text=self.text.toPlainText(),
                     btn=self.btn.text(), link=link or "", align=self.align.currentText(),
                     bg=self.bg.value, color=self.color.value, overlay=self.overlay.value,
                     overlay_op=self.op.value())
            row = self.list.currentRow()
            it = self.list.item(row)
            if it:
                it.setText("%d  %s" % (row + 1, p.get("heading") or "(no heading)"))
        self.opts.update(anim=self.anim.currentData(), autoplay=self.auto.isChecked(),
                         pause=self.pause.isChecked(), arrows=self.arrows.isChecked(),
                         dots=self.dots.isChecked(), loop=self.loop.value(),
                         speed=self.speed.value(), start=self.start.value())
        self.draw()

    def draw(self):
        from .extras import paint_slider
        W, H = 480, int(480 * self.item.get("h", 340) / max(self.item.get("w", 760), 1))
        pm = QPixmap(W, H)
        pm.fill(QColor("#222"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        d = dict(self.item, panels=self.panels, **self.opts)
        d["start"] = max(1, self.list.currentRow() + 1)
        paint_slider(p, QRectF(0, 0, W, H), d, _PreviewWin(self.doc))
        p.end()
        self.preview.setPixmap(pm)

    # -- actions -----------------------------------------------------------
    def pick_pic(self):
        p = self.cur()
        if p is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Picture", "", PICTURES)
        if path:
            p["asset"] = self.doc.add_asset(path)
            self.pic.setText("Picture: " + path.split("/")[-1])
            self.draw()

    def clear_pic(self):
        p = self.cur()
        if p is not None:
            p["asset"] = ""
            self.pic.setText("Choose picture...")
            self.draw()

    def add(self):
        self.panels.append(dict(asset="", bg="#1f3a5f", heading="New panel", color="#ffffff",
                                text="", btn="", link="", align="left", overlay="#000000",
                                overlay_op=0))
        self.fill(len(self.panels) - 1)

    def dup(self):
        p = self.cur()
        if p is not None:
            self.panels.insert(self.list.currentRow() + 1, dict(p))
            self.fill(self.list.currentRow() + 1)

    def remove(self):
        i = self.list.currentRow()
        if len(self.panels) > 1 and i >= 0:
            del self.panels[i]
            self.fill(i)

    def move(self, step):
        i = self.list.currentRow()
        j = i + step
        if 0 <= i < len(self.panels) and 0 <= j < len(self.panels):
            self.panels[i], self.panels[j] = self.panels[j], self.panels[i]
            self.fill(j)

    def apply(self):
        self.item["panels"] = self.panels
        self.item.update(self.opts)
