"""HTML pages: a page whose whole content is HTML you wrote (or pasted). It is published as its
own file, listed in the menu like any page, and has its own properties (name, file name,
description, menu, search engines)."""
import html
import os
import re

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout)

STARTER = ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
           "<title>%s</title>\n</head>\n<body>\n<h1>%s</h1>\n<p>Write your own HTML here.</p>\n</body>\n</html>\n")


def new_html_page(name="HTML page"):
    from .model import new_page
    return new_page(name, type="html", html=STARTER % (html.escape(name), html.escape(name)),
                    filename="")


def safe_filename(name):
    """A plain file name that ends in .html or .htm, or '' if nothing usable was typed."""
    base = os.path.basename((name or "").strip().replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.")
    if not base:
        return ""
    return base if base.lower().endswith((".html", ".htm")) else base + ".html"


def page_text(page):
    """The file's content: the HTML as written, with the page's description and search-engine
    choice added to its <head> unless it already says so."""
    raw = page.get("html", "")
    low = raw.lower()
    if "<html" not in low:
        raw = ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<title>%s</title>\n"
               "</head>\n<body>\n%s\n</body>\n</html>\n" % (html.escape(page.get("title") or page["name"]), raw))
        low = raw.lower()
    extra = []
    if page.get("description") and 'name="description"' not in low and "name='description'" not in low:
        extra.append('<meta name="description" content="%s">' % html.escape(page["description"], quote=True))
    if "noindex" in (page.get("robots") or "") and 'name="robots"' not in low:
        extra.append('<meta name="robots" content="noindex">')
    if extra:
        m = re.search(r"<head[^>]*>", raw, re.IGNORECASE)
        if m:
            raw = raw[:m.end()] + "\n" + "\n".join(extra) + raw[m.end():]
        else:
            m = re.search(r"<html[^>]*>", raw, re.IGNORECASE)
            raw = raw[:m.end()] + "\n<head>\n" + "\n".join(extra) + "\n</head>" + raw[m.end():]
    return raw


class HtmlPageDialog(QDialog):
    """HTML Page Properties."""

    def __init__(self, win, page, creating=False):
        super().__init__(win)
        self.page = page
        self.setWindowTitle("New HTML page" if creating else "HTML Page Properties")
        self.resize(640, 560)
        v = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(page["name"])
        self.fname = QLineEdit(page.get("filename", ""))
        self.fname.setPlaceholderText("Leave empty and a name is made from the page name")
        self.desc = QLineEdit(page.get("description", ""))
        self.nav = QCheckBox("Show this page in the menu")
        self.nav.setChecked(page.get("nav", True))
        self.index = QCheckBox("Let search engines list this page")
        self.index.setChecked("noindex" not in (page.get("robots") or ""))
        form.addRow("Page name", self.name)
        form.addRow("File name", self.fname)
        form.addRow("Description", self.desc)
        form.addRow(self.nav)
        form.addRow(self.index)
        v.addLayout(form)
        v.addWidget(QLabel("HTML for the page:"))
        self.code = QPlainTextEdit(page.get("html", ""))
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.TypeWriter)
        self.code.setFont(mono)
        self.code.setLineWrapMode(QPlainTextEdit.NoWrap)
        v.addWidget(self.code, 1)
        row = QHBoxLayout()
        load = QPushButton("Load from a file...")
        load.clicked.connect(self.load)
        row.addWidget(load)
        row.addStretch(1)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load an HTML file", "", "Web pages (*.html *.htm);;All files (*)")
        if path:
            with open(path, encoding="utf-8", errors="replace") as f:
                self.code.setPlainText(f.read())
            if self.name.text() in ("", "HTML page"):
                self.name.setText(os.path.splitext(os.path.basename(path))[0])

    def apply(self):
        p = self.page
        p["name"] = self.name.text().strip() or p["name"]
        p["title"] = p["name"]
        p["filename"] = safe_filename(self.fname.text())
        p["description"] = self.desc.text().strip()
        p["nav"] = self.nav.isChecked()
        p["robots"] = "" if self.index.isChecked() else "noindex"
        p["html"] = self.code.toPlainText()
