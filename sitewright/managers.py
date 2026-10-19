"""The Site Manager: lists of everything in the site that you can check and fix in one place -
pages, hyperlinks, fonts, files (pictures) and text. The data functions at the top are plain
Python (easy to test); the dialog classes below put them on screen."""
import base64
import os
import re
from collections import namedtuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                             QFontComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from . import findreplace
from .model import KIND_NAMES, asset_refs

LinkRef = namedtuple("LinkRef", "page_index page_name item holder key label")


# -- helpers ---------------------------------------------------------------
def real_pages(doc):
    return [(i, p) for i, p in enumerate(doc.pages) if p.get("type", "page") == "page"]


def item_lists(doc):
    """[(page_index or -1, name, items)] for every page and every master page."""
    out = [(i, p["name"], p["items"]) for i, p in real_pages(doc)]
    for mid, name, items in doc.all_masters():
        out.append((-1, name, items))
    return out


def kind_name(item):
    return KIND_NAMES.get(item.get("kind", ""), item.get("kind", "").title())


# -- hyperlinks --------------------------------------------------------------
def links(doc):
    """Every link in the site as LinkRef rows. holder[key] holds the link text."""
    out = []
    for pi, name, items in item_lists(doc):
        for it in items:
            if it.get("link"):
                out.append(LinkRef(pi, name, it, it, "link", kind_name(it)))
            for n, panel in enumerate(it.get("panels") or []):
                if panel.get("link"):
                    out.append(LinkRef(pi, name, it, panel, "link", "Slider panel %d" % (n + 1)))
    for i, p in enumerate(doc.pages):
        if p.get("type") == "link" and p.get("url"):
            out.append(LinkRef(i, "(menu)", p, p, "url", "Offsite link: " + p["name"]))
    return out


def describe(link, doc):
    """Plain words for where a link goes."""
    names = {p["id"]: p["name"] for p in doc.pages}
    if link.startswith("page:"):
        return 'Page "%s"' % names[link[5:]] if link[5:] in names else "(a page that was deleted)"
    if link.startswith("anchor:"):
        pid, _, anchor = link[7:].partition("#")
        return 'Anchor "%s" on page "%s"' % (anchor, names.get(pid, "(deleted page)"))
    if link.startswith("toggle:"):
        return 'Show/hide "%s"' % link[7:]
    if link.startswith("mailto:"):
        return "Email " + link[7:]
    return link


def all_anchors(doc, page_id=None):
    out = set()
    for pi, _n, items in item_lists(doc):
        pid = doc.pages[pi]["id"] if pi >= 0 else None
        for it in items:
            for key in ("anchor", "ident"):
                if it.get(key) and (page_id is None or pid in (page_id, None)):
                    out.add(it[key])
    return out


def status(link, doc):
    """'ok', 'web' (an address on the web, not checked yet) or the words of a problem."""
    ids = {p["id"] for p in doc.pages}
    if link.startswith("page:"):
        return "ok" if link[5:] in ids else "The page was deleted"
    if link.startswith("anchor:"):
        pid, _, anchor = link[7:].partition("#")
        if pid not in ids:
            return "The page was deleted"
        return "ok" if anchor in all_anchors(doc, pid) else "The anchor is gone"
    if link.startswith("toggle:"):
        return "ok" if link[7:] in all_anchors(doc) else "Nothing has that id"
    if link.startswith("mailto:"):
        return "ok" if re.match(r"^mailto:[^@\s]+@[^@\s]+\.[^@\s]+", link) else "Not an email address"
    if re.match(r"^https?://", link, re.I):
        return "web" if re.match(r"^https?://[^/\s]+\.[^/\s]+", link, re.I) else "Not a full web address"
    if link.startswith("tel:") or link.startswith("#"):
        return "ok"
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", link):
        return "ok"
    return "not checked"


def check_web(url, opener=None, timeout=8):
    """Ask the web server about an address. 'ok' or a few words on what went wrong."""
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 (link check)"})
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
            code = getattr(r, "status", 200)
        return "ok" if code < 400 else "The site answered %d" % code
    except urllib.error.HTTPError as e:
        return "ok" if e.code in (401, 403, 405, 429) else "The site answered %d" % e.code
    except Exception as e:                     # no network, bad name, timeout
        return "Could not reach it (%s)" % (getattr(e, "reason", None) or type(e).__name__)


def set_link(ref, new):
    ref.holder[ref.key] = new


def replace_in_links(doc, old, new):
    """Swap one piece of text for another inside every link (for example a new web address)."""
    n = 0
    for ref in links(doc):
        cur = ref.holder.get(ref.key, "")
        if old and old in cur:
            ref.holder[ref.key] = cur.replace(old, new)
            n += 1
    return n


# -- fonts -------------------------------------------------------------------
WEB_SAFE = {"arial", "helvetica", "times new roman", "times", "georgia", "verdana", "courier new",
            "courier", "trebuchet ms", "tahoma", "palatino", "palatino linotype", "impact",
            "comic sans ms", "lucida sans unicode", "lucida console", "garamond", "bookman",
            "sans serif", "serif", "monospace", "sans-serif", "cursive", "fantasy", "system-ui"}


def font_usage(doc):
    """{family: (objects using it, set of page names)}"""
    out = {}
    for _pi, name, items in item_lists(doc):
        for it in items:
            f = it.get("font")
            if f:
                n, pages = out.get(f, (0, set()))
                pages.add(name)
                out[f] = (n + 1, pages)
    return out


def installed(family):
    return family in QFontDatabase().families()


def substitute_font(doc, old, new):
    n = 0
    for _pi, _name, items in item_lists(doc):
        for it in items:
            if it.get("font") == old:
                it["font"] = new
                n += 1
    return n


# -- files (pictures) --------------------------------------------------------
def file_usage(doc):
    """{asset id: set of page names} for every picture used anywhere."""
    out = {}
    for _pi, name, items in item_lists(doc):
        for it in items:
            for a in asset_refs(it):
                out.setdefault(a, set()).add(name)
    seo = doc.seo or {}
    for key in ("og_image", "favicon"):
        if seo.get(key):
            out.setdefault(seo[key], set()).add("(site settings)")
    for p in doc.pages:
        if p.get("og_image"):
            out.setdefault(p["og_image"], set()).add(p["name"])
        if (p.get("sound") or {}).get("asset"):
            out.setdefault(p["sound"]["asset"], set()).add(p["name"] + " (sound)")
    if (doc.feed or {}).get("image"):
        out.setdefault(doc.feed["image"], set()).add("(podcast feed)")
    return out


def asset_kb(doc, aid):
    return len(doc.assets[aid]["data"]) * 0.75 / 1024


def delete_unused(doc):
    used = file_usage(doc)
    gone = [a for a in doc.assets if a not in used]
    for a in gone:
        del doc.assets[a]
    return len(gone)


def save_asset(doc, aid, path):
    with open(path, "wb") as f:
        f.write(base64.b64decode(doc.assets[aid]["data"]))


def replace_asset(doc, aid, path):
    """Put a different file in the same place: everything that used the old picture shows the new one."""
    with open(path, "rb") as f:
        data = f.read()
    doc.assets[aid] = dict(name=os.path.basename(path), data=base64.b64encode(data).decode())


# -- text ----------------------------------------------------------------------
def text_rows(doc):
    """[(Field, words)] for every piece of text, with the page it is on."""
    out = []
    for f in findreplace.fields(doc, None):
        out.append((f, str(f.cont[f.key])))
    return out


def word_count(text):
    return len(re.findall(r"\w[\w'-]*", text))


# -- getting to things -----------------------------------------------------------
def go_to(win, page_index, item, cell=None):
    """Show the page and select the object."""
    if page_index >= 0 and page_index != win.page_index:
        i = win.page_combo.findData(win.doc.pages[page_index]["id"])
        if i >= 0:
            win.page_combo.setCurrentIndex(i)
            win.page_combo_picked(i)
        else:
            win.page_index = page_index
            win.reload()
    for o in win.scene.items():
        if getattr(o, "editable", False) and o.d.get("id") == item.get("id"):
            for s in win.scene.selectedItems():
                s.setSelected(False)
            o.setSelected(True)
            if cell is not None and item.get("kind") == "table":
                item["sel"] = [cell[0], cell[1], cell[0], cell[1]]
                o.update()
            win.view.ensureVisible(o)
            return True
    return False


# ============================== screens ======================================
class Tab(QWidget):
    """Base for the tabs: a tree, a row of buttons, and a refresh()."""
    headers = []

    def __init__(self, win, dlg):
        super().__init__()
        self.win, self.dlg = win, dlg
        v = QVBoxLayout(self)
        self.top = QHBoxLayout()
        v.addLayout(self.top)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(self.headers)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        v.addWidget(self.tree, 1)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        v.addWidget(self.note)
        self.buttons = QHBoxLayout()
        v.addLayout(self.buttons)
        self.entries = []

    def button(self, label, fn):
        b = QPushButton(label)
        b.clicked.connect(lambda _=False: fn())
        self.buttons.addWidget(b)
        return b

    def fill(self, rows, data):
        self.tree.clear()
        self.entries = data
        for r in rows:
            self.tree.addTopLevelItem(QTreeWidgetItem([str(c) for c in r]))
        for i in range(len(self.headers)):
            self.tree.resizeColumnToContents(i)

    def chosen(self):
        idx = [self.tree.indexOfTopLevelItem(i) for i in self.tree.selectedItems()]
        return [self.entries[i] for i in sorted(idx) if 0 <= i < len(self.entries)]

    def changed(self, label):
        self.win.reload({o.d["id"] for o in self.win.selected()})
        self.win.commit_if_changed(label)
        self.dlg.refresh_all()


class PagesTab(Tab):
    headers = ["Page", "File", "Objects", "In menu", "Master page"]

    def __init__(self, win, dlg):
        super().__init__(win, dlg)
        self.button("Go to page", self.go)
        self.button("Page settings...", self.settings)
        self.tree.itemDoubleClicked.connect(lambda *_: self.go())

    def refresh(self):
        from . import export
        from .model import ordered_pages
        files = export.page_files(self.win.doc)
        names = {mid: n for mid, n, _i in self.win.doc.all_masters()}
        rows, data = [], []
        for p, _d in ordered_pages(self.win.doc.pages):
            if p.get("type") == "link":
                rows.append((p["name"], p.get("url", ""), "-", "yes" if p.get("nav", True) else "no", "-"))
            else:
                m = p.get("master", True)
                mn = "none" if m is False else names.get("" if m is True else m, "(missing)")
                rows.append((p["name"], files.get(p["id"], ""), len(p["items"]),
                             "yes" if p.get("nav", True) else "no", mn))
            data.append(p)
        self.fill(rows, data)

    def go(self):
        for p in self.chosen():
            i = self.win.doc.pages.index(p)
            if p.get("type", "page") == "page":
                go_to(self.win, i, {"id": None})
            return

    def settings(self):
        for p in self.chosen():
            self.win.page_index = self.win.doc.pages.index(p)
            self.win.page_settings_for(p)
            self.dlg.refresh_all()
            return


class LinksTab(Tab):
    """The Hyperlink Manager: every link, where it goes, and whether it still works."""
    headers = ["On page", "Object", "Goes to", "Status"]

    def __init__(self, win, dlg):
        super().__init__(win, dlg)
        self.problems = QCheckBox("Show only the ones with a problem")
        self.problems.toggled.connect(self.refresh)
        self.top.addWidget(self.problems)
        self.top.addStretch(1)
        self.web = {}
        self.button("Modify...", self.modify)
        self.button("Replace text in all links...", self.replace_all)
        self.button("Remove link", self.remove)
        self.button("Go to object", self.go)
        self.button("Check web addresses", self.check_all)
        self.tree.itemDoubleClicked.connect(lambda *_: self.go())

    def state(self, ref):
        link = ref.holder.get(ref.key, "")
        s = status(link, self.win.doc)
        if s == "web":
            s = self.web.get(link, "not checked yet")
        return s

    def refresh(self, *_):
        rows, data = [], []
        bad = bad_n = 0
        for ref in links(self.win.doc):
            s = self.state(ref)
            is_bad = s not in ("ok", "not checked", "not checked yet")
            bad += is_bad
            if self.problems.isChecked() and not is_bad:
                continue
            rows.append((ref.page_name, ref.label, describe(ref.holder.get(ref.key, ""), self.win.doc), s))
            data.append(ref)
        self.fill(rows, data)
        for i, ref in enumerate(self.entries):
            if self.state(ref) not in ("ok", "not checked", "not checked yet"):
                it = self.tree.topLevelItem(i)
                for c in range(4):
                    it.setForeground(c, Qt.red)
        self.note.setText("%d link(s), %d with a problem." % (len(links(self.win.doc)), bad))

    def modify(self):
        refs = self.chosen()
        if not refs:
            return
        doc = self.win.doc
        dlg = QDialog(self)
        dlg.setWindowTitle("Modify link")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Send the link to:"))
        box = QComboBox()
        box.addItem("(a web address or email, typed below)", "")
        for i, p in real_pages(doc):
            box.addItem('Page "%s"' % p["name"], "page:" + p["id"])
        v.addWidget(box)
        edit = QLineEdit(refs[0].holder.get(refs[0].key, "") if not refs[0].holder.get(refs[0].key, "").startswith(("page:", "anchor:", "toggle:")) else "")
        edit.setPlaceholderText("https://example.com   or   mailto:you@example.com")
        v.addWidget(edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec_() != QDialog.Accepted:
            return
        new = box.currentData() or edit.text().strip()
        if not new:
            return
        if "@" in new and "://" not in new and not new.startswith(("mailto:", "page:")):
            new = "mailto:" + new
        for ref in refs:
            set_link(ref, new)
        self.changed("Modify links")

    def replace_all(self):
        old, ok = QInputDialog.getText(self, "Replace text in links", "Find this text in the links:")
        if not ok or not old:
            return
        new, ok = QInputDialog.getText(self, "Replace text in links", "Replace it with:")
        if not ok:
            return
        n = replace_in_links(self.win.doc, old, new)
        self.note.setText("Changed %d link(s)." % n)
        self.changed("Replace in links")

    def remove(self):
        refs = self.chosen()
        if not refs:
            return
        for ref in refs:
            if ref.key == "link":
                ref.holder["link"] = ""
        self.changed("Remove links")

    def go(self):
        for ref in self.chosen():
            if ref.page_index >= 0 and ref.item.get("kind") != "link" and ref.item.get("id"):
                go_to(self.win, ref.page_index, ref.item)
            return

    def check_all(self, opener=None):
        from PyQt5.QtWidgets import QApplication
        urls = sorted({r.holder.get(r.key, "") for r in links(self.win.doc)
                       if status(r.holder.get(r.key, ""), self.win.doc) == "web"})
        for n, u in enumerate(urls):
            self.note.setText("Checking %d of %d: %s" % (n + 1, len(urls), u[:60]))
            QApplication.processEvents()
            self.web[u] = check_web(u, opener)
        self.refresh()


class FontsTab(Tab):
    headers = ["Font", "Used by", "On this computer", "Safe on the web", "Pages"]

    def __init__(self, win, dlg):
        super().__init__(win, dlg)
        self.button("Use a different font...", self.substitute)
        self.button("Go to first use", self.go)

    def refresh(self):
        use = font_usage(self.win.doc)
        rows, data = [], []
        for f, (n, pages) in sorted(use.items(), key=lambda kv: -kv[1][0]):
            rows.append((f, "%d object(s)" % n, "yes" if installed(f) else "NO - substituted",
                         "yes" if f.lower() in WEB_SAFE else "no (browsers may swap it)",
                         ", ".join(sorted(pages))))
            data.append(f)
        self.fill(rows, data)
        self.note.setText("%d font(s) in use. A font that is not safe on the web is shown with a "
                          "stand-in in visitors' browsers if they do not have it." % len(data))

    def substitute(self):
        fonts = self.chosen()
        if not fonts:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Use a different font")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Replace %s everywhere with:" % ", ".join(fonts)))
        box = QFontComboBox()
        v.addWidget(box)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec_() != QDialog.Accepted:
            return
        n = sum(substitute_font(self.win.doc, f, box.currentFont().family()) for f in fonts)
        self.note.setText("Changed %d object(s)." % n)
        self.changed("Change fonts")

    def go(self):
        for f in self.chosen():
            for pi, _name, items in item_lists(self.win.doc):
                for it in items:
                    if it.get("font") == f and pi >= 0:
                        go_to(self.win, pi, it)
                        return


class FilesTab(Tab):
    headers = ["Picture", "Size", "Used on"]

    def __init__(self, win, dlg):
        super().__init__(win, dlg)
        self.button("Save a copy...", self.save)
        self.button("Replace with another file...", self.replace)
        self.button("Delete the ones not used", self.clean)

    def refresh(self):
        doc = self.win.doc
        used = file_usage(doc)
        rows, data = [], []
        for aid, a in doc.assets.items():
            rows.append((a["name"], "%.0f KB" % asset_kb(doc, aid),
                         ", ".join(sorted(used.get(aid, []))) or "not used"))
            data.append(aid)
        self.fill(rows, data)
        total = sum(asset_kb(doc, a) for a in doc.assets)
        self.note.setText("%d file(s), %.1f MB in all. Pictures that are not used on any page are "
                          "left out of the saved site anyway." % (len(doc.assets), total / 1024))

    def save(self):
        for aid in self.chosen():
            name = self.win.doc.assets[aid]["name"]
            path, _ = QFileDialog.getSaveFileName(self, "Save a copy", name)
            if path:
                save_asset(self.win.doc, aid, path)
            return

    def replace(self):
        for aid in self.chosen():
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose the new file", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg)")
            if path:
                replace_asset(self.win.doc, aid, path)
                if hasattr(self.win, "_pixcache"):
                    self.win._pixcache.pop(aid, None)
                self.changed("Replace file")
            return

    def clean(self):
        n = delete_unused(self.win.doc)
        self.note.setText("Deleted %d unused file(s)." % n)
        self.win.side_refresh()
        self.dlg.refresh_all()


class TextTab(Tab):
    """The Text Manager: every piece of text in the site; double-click one to change it."""
    headers = ["On page", "Object", "Words", "Text"]

    def __init__(self, win, dlg):
        super().__init__(win, dlg)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Show only text that contains...")
        self.find.textChanged.connect(self.refresh)
        self.top.addWidget(self.find)
        self.tree.itemDoubleClicked.connect(self.edit)
        self.button("Change this text...", self.edit)
        self.button("Go to object", self.go)

    def refresh(self, *_):
        q = self.find.text().lower()
        rows, data = [], []
        total = 0
        for f, text in text_rows(self.win.doc):
            total += word_count(text)
            if q and q not in text.lower():
                continue
            label = kind_name(f.item) + (" (cell)" if f.item["kind"] == "table" else "")
            rows.append((f.page_name, label, word_count(text), text.replace("\n", " ")[:140]))
            data.append(f)
        self.fill(rows, data)
        self.note.setText("%d piece(s) of text shown, %d word(s) in the whole site." % (len(data), total))

    def edit(self, *_):
        for f in self.chosen():
            cur = str(f.cont[f.key])
            dlg = QDialog(self)
            dlg.setWindowTitle("Change text")
            dlg.resize(460, 300)
            v = QVBoxLayout(dlg)
            from PyQt5.QtWidgets import QPlainTextEdit
            box = QPlainTextEdit(cur)
            v.addWidget(box)
            bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            bb.accepted.connect(dlg.accept)
            bb.rejected.connect(dlg.reject)
            v.addWidget(bb)
            if dlg.exec_() == QDialog.Accepted and box.toPlainText() != cur:
                f.cont[f.key] = box.toPlainText()
                from . import textlayout
                if f.item.get("kind") == "text":
                    textlayout.fit_height(f.item)
                self.changed("Change text")
            return

    def go(self):
        for f in self.chosen():
            cell = None
            if f.item["kind"] == "table":
                row = [i for i, r in enumerate(f.item["cells"]) if r is f.cont]
                cell = (row[0], f.key) if row else None
            go_to(self.win, f.page_index, f.item, cell)
            return


class SiteManagerDialog(QDialog):
    TABS = ("pages", "links", "fonts", "files", "text")

    def __init__(self, win, start="pages"):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Site Manager")
        self.resize(760, 480)
        self.setModal(False)
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)
        self.parts = {}
        for key, title, cls in (("pages", "Pages", PagesTab), ("links", "Hyperlinks", LinksTab),
                                ("fonts", "Fonts", FontsTab), ("files", "Files", FilesTab),
                                ("text", "Text", TextTab)):
            part = cls(win, self)
            self.parts[key] = part
            self.tabs.addTab(part, title)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.close)
        bb.button(QDialogButtonBox.Close).clicked.connect(self.close)
        v.addWidget(bb)
        self.refresh_all()
        self.tabs.setCurrentIndex(self.TABS.index(start) if start in self.TABS else 0)

    def refresh_all(self):
        for part in self.parts.values():
            part.refresh()


# ============================ master pages ===================================
def add_master(doc, name, items=None):
    """A new master page (empty, or starting from a copy of some objects). Returns its id."""
    import copy
    from .model import new_id
    mid = new_id()
    new = copy.deepcopy(items) if items else []
    for it in new:
        it["id"] = new_id()
    doc.masters.append(dict(id=mid, name=name, items=new))
    return mid


def duplicate_master(doc, mid, name=None):
    for m_id, m_name, items in doc.all_masters():
        if m_id == (mid or ""):
            return add_master(doc, name or (m_name + " copy"), items)
    return None


def rename_master(doc, mid, name):
    for m in doc.masters:
        if m["id"] == mid and name.strip():
            m["name"] = name.strip()
            return True
    return False


def delete_master(doc, mid):
    """Remove an extra master page; the pages that used it go back to the main master page."""
    n = 0
    for p in doc.pages:
        if p.get("master") == mid:
            p["master"] = True
            n += 1
    before = len(doc.masters)
    doc.masters = [m for m in doc.masters if m["id"] != mid]
    return n if len(doc.masters) < before else -1


def assign_master(doc, mid, page_ids):
    for p in doc.pages:
        if p["id"] in page_ids and p.get("type", "page") == "page":
            p["master"] = mid if mid else True


def master_users(doc, mid):
    return [p["name"] for p in doc.pages
            if p.get("type", "page") == "page" and
            ((p.get("master", True) is True and not mid) or p.get("master") == mid)]


class MasterManagerDialog(QDialog):
    """The Master Page Manager: more than one master page, and which pages use which."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Master Page Manager")
        self.resize(560, 360)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("A master page holds things that show on many pages, such as a logo or "
                           "a menu. Each page uses one master page, or none."))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Master page", "Objects", "Used by"])
        self.tree.setRootIsDecorated(False)
        v.addWidget(self.tree, 1)
        self.note = QLabel("")
        v.addWidget(self.note)
        row = QHBoxLayout()
        for label, fn in (("Add new...", self.add), ("Duplicate", self.dup), ("Rename...", self.rename),
                          ("Delete", self.delete), ("Use on pages...", self.use),
                          ("Edit this master page", self.edit), ("Close", self.close)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, f=fn: f())
            row.addWidget(b)
        v.addLayout(row)
        self.ids = []
        self.refresh()

    def refresh(self):
        doc = self.win.doc
        self.tree.clear()
        self.ids = []
        for mid, name, items in doc.all_masters():
            users = master_users(doc, mid)
            self.tree.addTopLevelItem(QTreeWidgetItem(
                [name, str(len(items)), ", ".join(users) if users else "no pages"]))
            self.ids.append(mid)
        self.tree.setCurrentItem(self.tree.topLevelItem(0))
        for i in range(3):
            self.tree.resizeColumnToContents(i)

    def current(self):
        i = self.tree.indexOfTopLevelItem(self.tree.currentItem())
        return self.ids[i] if 0 <= i < len(self.ids) else ""

    def done(self, label):
        self.win.reload({o.d["id"] for o in self.win.selected()})
        self.win.commit_if_changed(label)
        self.refresh()

    def add(self):
        name, ok = QInputDialog.getText(self, "New master page", "Name:", text="Master page %d" % (len(self.win.doc.masters) + 2))
        if ok and name.strip():
            add_master(self.win.doc, name.strip())
            self.done("Add master page")

    def dup(self):
        duplicate_master(self.win.doc, self.current())
        self.done("Copy master page")

    def rename(self):
        mid = self.current()
        if not mid:
            self.note.setText("The main master page keeps its name.")
            return
        cur = next(m["name"] for m in self.win.doc.masters if m["id"] == mid)
        name, ok = QInputDialog.getText(self, "Rename", "Name:", text=cur)
        if ok and rename_master(self.win.doc, mid, name):
            self.done("Rename master page")

    def delete(self):
        mid = self.current()
        if not mid:
            self.note.setText("The main master page cannot be deleted.")
            return
        if QMessageBox.question(self, "Delete", "Delete this master page? Pages that use it will "
                                "use the main master page instead.") == QMessageBox.Yes:
            if self.win.master_mode and self.win.master_edit == mid:
                self.win.master_btn.setChecked(False)
            delete_master(self.win.doc, mid)
            self.done("Delete master page")

    def use(self):
        mid = self.current()
        doc = self.win.doc
        dlg = QDialog(self)
        dlg.setWindowTitle("Use this master page on...")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Tick the pages that should use it:"))
        from PyQt5.QtWidgets import QListWidget, QListWidgetItem
        lst = QListWidget()
        mine = set(master_users(doc, mid))
        for _i, p in real_pages(doc):
            it = QListWidgetItem(p["name"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if p["name"] in mine else Qt.Unchecked)
            it.setData(Qt.UserRole, p["id"])
            lst.addItem(it)
        v.addWidget(lst)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec_() == QDialog.Accepted:
            ids = {lst.item(i).data(Qt.UserRole) for i in range(lst.count())
                   if lst.item(i).checkState() == Qt.Checked}
            assign_master(doc, mid, ids)
            self.done("Use master page")

    def edit(self):
        self.win.edit_master(self.current())
        self.close()
