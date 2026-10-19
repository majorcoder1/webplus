"""Ways to get your work out as something other than a website: a PDF, a picture, a single-file widget."""
import base64
import copy
import mimetypes
import os
import re
import tempfile

from PyQt5.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt5.QtGui import QColor, QImage, QPageSize, QPainter, QPdfWriter
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                             QMessageBox, QApplication)


class Printing:
    """While this is active the scene draws no grid, guides or selection, so what is drawn is the design."""
    def __init__(self, win):
        self.win = win

    def __enter__(self):
        self.win.scene.printing = True
        self.old_sel = [o.d["id"] for o in self.win.selected()]
        guard = getattr(self.win, "_sel_guard", False)
        self.win._sel_guard = True
        self.win.scene.clearSelection()
        self.win._sel_guard = guard
        return self

    def __exit__(self, *a):
        self.win.scene.printing = False
        self.win.reload(set(self.old_sel))


class Merged:
    """For the moment a page is written out, repeating areas are filled with every record
    (the same way the published site does it) and the page is as tall as that needs."""

    def __init__(self, win, index):
        self.win, self.page = win, win.doc.pages[index]

    def __enter__(self):
        from . import databasemerge
        self.keep = (self.page["items"], self.page["h"])
        items, page2 = databasemerge.expand(self.win.doc, self.page, self.page["items"])
        self.page["items"], self.page["h"] = items, page2["h"]
        return self

    def __exit__(self, *a):
        self.page["items"], self.page["h"] = self.keep


def render_page(win, index, scale=1.0, transparent=False):
    with Merged(win, index):
        return _render_page(win, index, scale, transparent)


def _render_page(win, index, scale, transparent):
    win.page_index = index
    win.reload()
    page = win.cur_page()
    w, h = int(win.doc.width), int(page["h"])
    img = QImage(int(w * scale), int(h * scale), QImage.Format_ARGB32)
    img.fill(Qt.transparent if transparent else QColor(page.get("bg", "#ffffff")))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    win.scene.render(p, QRectF(0, 0, img.width(), img.height()), QRectF(0, 0, w, h))
    p.end()
    return img


def link_target(link, page_to_pdf):
    """('page', n) or ('uri', address) for a link that can click in a PDF, else None."""
    if not link:
        return None
    if link.startswith(("page:", "anchor:")):
        pid = link.split(":", 1)[1].partition("#")[0]
        return ("page", page_to_pdf[pid]) if pid in page_to_pdf else None
    if link.lower().startswith(("http://", "https://", "mailto:", "tel:")):
        return ("uri", link)
    return None


def collect_links(win, page_to_pdf):
    """Link boxes for the page now in the scene, in PDF points from the page's top left."""
    from PyQt5.QtGui import QImage, QPainter
    from . import styles
    from .canvas import ItemObj
    from .model import nav_entries
    out = []

    def box(o, r):
        if o.d.get("rot") or o.d.get("fx") or o.d.get("fy"):
            r = o.xform().mapRect(r)
        r = r.translated(o.pos())
        return (r.left() * 0.75, r.top() * 0.75, r.right() * 0.75, r.bottom() * 0.75)

    for o in win.scene.items():
        if not isinstance(o, ItemObj) or o.d.get("hidden"):
            continue
        d = o.d
        if d["kind"] == "navbar":
            hits = []
            img = QImage(1, 1, QImage.Format_ARGB32)
            q = QPainter(img)
            cur = win.cur_page()
            styles.paint_nav(q, o.rect(), d, nav_entries(win.doc), "page:" + cur["id"], hits)
            q.end()
            for r, tgt in hits:
                t = link_target(tgt, page_to_pdf)
                if t:
                    out.append(box(o, r) + t)
        else:
            t = link_target(d.get("link", ""), page_to_pdf)
            if t:
                out.append(box(o, o.rect()) + t)
    return out


def pdf_pages(win):
    return [i for i, pg in enumerate(win.doc.pages) if pg.get("type", "page") == "page"]


def write_pdf(win, path, indexes=None):
    """One PDF page per website page, each as big as the design (96 pixels to the inch)."""
    indexes = indexes if indexes is not None else pdf_pages(win)
    start = win.page_index
    w = int(win.doc.width)
    pdf = QPdfWriter(path)
    pdf.setResolution(96)
    pdf.setTitle(win.doc.site_title)
    pdf.setCreator("WebPlus")
    pdf.setPageMargins(QMarginsF(0, 0, 0, 0))
    all_links = []
    page_to_pdf = {win.doc.pages[i]["id"]: n for n, i in enumerate(indexes)}
    with Printing(win):
        p = None
        for i in indexes:
            with Merged(win, i):
                win.page_index = i
                win.reload()
                page = win.cur_page()
                h = int(page["h"])
                pdf.setPageSize(QPageSize(QSizeF(w * 0.75, h * 0.75), QPageSize.Point))
                if p is None:
                    p = QPainter(pdf)
                    p.setRenderHint(QPainter.Antialiasing)
                    p.setRenderHint(QPainter.SmoothPixmapTransform)
                else:
                    pdf.newPage()
                p.fillRect(QRectF(0, 0, w, h), QColor(page.get("bg", "#ffffff")))
                win.scene.render(p, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
                all_links.append(collect_links(win, page_to_pdf))
        if p is not None:
            p.end()
        win.page_index = start
    from . import pdflinks
    pdflinks.add_links(path, all_links)
    return len(indexes)


def publish_pdf(win):
    default = os.path.splitext(win.doc.path)[0] + ".pdf" if win.doc.path else "website.pdf"
    path, _ = QFileDialog.getSaveFileName(win, "Publish as PDF", default, "PDF files (*.pdf)")
    if not path:
        return
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    n = write_pdf(win, path)
    win.statusBar().showMessage("Saved %d page(s) to %s" % (n, path), 8000)


# -- picture ---------------------------------------------------------------------------------------
def selection_rect(win):
    objs = win.selected()
    if not objs:
        return None
    r = objs[0].sceneBoundingRect()
    for o in objs[1:]:
        r = r.united(o.sceneBoundingRect())
    return r


def export_picture(win):
    dlg = QDialog(win)
    dlg.setWindowTitle("Export as picture")
    lay = QFormLayout(dlg)
    what = QComboBox()
    has_sel = bool(win.selected())
    if has_sel:
        what.addItem("The selected objects", "sel")
    what.addItem("This whole page", "page")
    size = QComboBox()
    for label, k in (("Normal size", 1), ("Double size (sharper)", 2), ("Half size", 0.5)):
        size.addItem(label, k)
    fmt = QComboBox()
    for label, k in (("PNG (keeps see-through areas)", "png"), ("JPEG (smaller file)", "jpg")):
        fmt.addItem(label, k)
    trans = QCheckBox("Leave the background see-through")
    trans.setChecked(has_sel)
    lay.addRow("Save", what)
    lay.addRow("Size", size)
    lay.addRow("Kind", fmt)
    lay.addRow(trans)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addRow(bb)
    if dlg.exec_() != QDialog.Accepted:
        return
    kind, k, ext = what.currentData(), size.currentData(), fmt.currentData()
    path, _ = QFileDialog.getSaveFileName(win, "Export as picture", "picture." + ext,
                                          "PNG (*.png);;JPEG (*.jpg)" if ext == "png" else "JPEG (*.jpg);;PNG (*.png)")
    if not path:
        return
    img = picture_image(win, kind == "sel", k, trans.isChecked() and path.lower().endswith(".png"))
    if img is None or not img.save(path, quality=92):
        QMessageBox.warning(win, "WebPlus", "The picture could not be saved.")
        return
    win.statusBar().showMessage("Saved %dx%d picture to %s" % (img.width(), img.height(), path), 8000)


def picture_image(win, selection, scale, transparent):
    page_index = win.page_index
    if not selection:
        with Printing(win):
            return render_page(win, page_index, scale, transparent)
    from . import imagefx
    objs = win.selected()
    ids = {o.d["id"] for o in objs}
    box = QRectF()
    for o in objs:
        box = box.united(o.sceneBoundingRect())
    from .canvas import HANDLE
    box.adjust(HANDLE + 2, HANDLE + 2, -(HANDLE + 2), -(HANDLE + 2))     # undo the handle margin
    pad = max((imagefx.pad_for(o.d.get("effects")) for o in objs), default=0)
    box.adjust(-pad, -pad, pad, pad)
    img = QImage(max(int(box.width() * scale), 1), max(int(box.height() * scale), 1), QImage.Format_ARGB32)
    page = win.cur_page()
    img.fill(Qt.transparent if transparent else QColor(page.get("bg", "#ffffff")))
    with Printing(win):
        for it in win.scene.items():
            if hasattr(it, "d") and it.d["id"] not in ids and it.editable:
                it.setVisible(False)
            elif hasattr(it, "d") and not it.editable:
                it.setVisible(False)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        win.scene.render(p, QRectF(0, 0, img.width(), img.height()), box)
        p.end()
    return img


# -- widget ----------------------------------------------------------------------------------------------
def widget_document(win, objs):
    """A little one-page site holding copies of the objects, moved to the top left corner."""
    box = None
    for o in objs:
        d = o.d
        r = QRectF(d["x"], d["y"], d["w"], d["h"])
        box = r if box is None else box.united(r)
    doc2 = copy.deepcopy(win.doc)
    items = copy.deepcopy([o.d for o in objs])
    for d in items:
        d["x"] -= box.x()
        d["y"] -= box.y()
        d.pop("group", None)
        if d.get("link", "").startswith("page:"):
            d["link"] = ""
    page = doc2.pages[0]
    page.update(items=items, h=int(box.height()), master=False, type="page", bg="rgba(0,0,0,0)")
    doc2.pages = [page]
    doc2.master, doc2.masters = [], []
    doc2.width = int(box.width())
    doc2.seo = dict(doc2.seo, site_url="")
    return doc2, int(box.width()), int(box.height())


def inline_site(folder):
    """Turn the exported index.html + style.css + images/ into one self-contained HTML text."""
    def data_uri(rel):
        full = os.path.join(folder, rel)
        if not os.path.isfile(full):
            return None
        mime = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode())

    def swap_images(text):
        return re.sub(r"images/[A-Za-z0-9._%~+-]+", lambda m: data_uri(m.group(0)) or m.group(0), text)

    with open(os.path.join(folder, "index.html"), encoding="utf-8") as f:
        text = f.read()
    with open(os.path.join(folder, "style.css"), encoding="utf-8") as f:
        css = f.read()
    text = text.replace('<link rel="stylesheet" href="style.css">', "<style>%s</style>" % swap_images(css), 1)
    text = swap_images(text)
    text = re.sub(r'<link rel="(?:icon|canonical|alternate)[^>]*>', "", text)
    return text


def export_widget(win):
    objs = win.selected()
    if not objs:
        win.statusBar().showMessage("Select the objects that make up the widget first", 5000)
        return
    path, _ = QFileDialog.getSaveFileName(win, "Export as widget", "widget.html", "Web page (*.html)")
    if not path:
        return
    from . import export
    doc2, w, h = widget_document(win, objs)
    tmp = tempfile.mkdtemp(prefix="widget-")
    export.export_site(doc2, tmp, optimise=False, preview=True)
    text = inline_site(tmp)
    text = text.replace("<body", '<body style="margin:0;background:transparent"', 1) if "<body" in text else text
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    name = os.path.basename(path)
    snippet = '<iframe src="%s" width="%d" height="%d" style="border:0" loading="lazy" title="Widget"></iframe>' % (
        name, w, h)
    with open(os.path.splitext(path)[0] + "-embed.txt", "w") as f:
        f.write(snippet + "\n")
    QApplication.clipboard().setText(snippet)
    win.statusBar().showMessage("Widget saved. The embed code is on the clipboard.", 8000)
    return path
