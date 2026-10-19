"""Smaller commands: View Site Online, Form (tab order, action, lock), Frame Properties,
View Variables, Pop-up menu editor and Save Default Settings."""
import json
import os

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QApplication, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMessageBox,
                             QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                             QVBoxLayout)

DEFAULT_KEYS = ("width", "scheme", "styles", "user", "swatches", "form_email", "form_mode", "form_action",
                "clean_urls")


def defaults_path():
    if os.environ.get("WEBSITE_DEFAULTS"):                  # tests point this somewhere harmless
        return os.environ["WEBSITE_DEFAULTS"]
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "4ThePeopleMedia", "Website", "defaults.json")


def save_defaults(win):
    d = win.doc
    data = {k: getattr(d, k) for k in DEFAULT_KEYS}
    p = defaults_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(data, f)
    win.statusBar().showMessage("Saved. New sites will start with this site's width, colours, styles and details.", 8000)


def apply_defaults(doc):
    """Used for a brand-new site only; returns True when a saved set was found."""
    try:
        with open(defaults_path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    for k in DEFAULT_KEYS:
        if k in data:
            setattr(doc, k, data[k])
    return True


def view_online(win):
    url = (win.doc.seo.get("site_url") or "").strip()
    if not url:
        url, ok = QInputDialog.getText(win, "View site online", "Where is the site on the web?",
                                       text="https://")
        url = url.strip()
        if not ok or url in ("", "https://"):
            return
        win.doc.seo["site_url"] = url
        win.commit_if_changed("Site address")
    if "://" not in url:
        url = "https://" + url
    QDesktopServices.openUrl(QUrl(url))


def form_fields(win):
    return [d for d in win.cur_page()["items"] if d.get("kind") == "field"]


def tab_order(win):
    fields = form_fields(win)
    if len(fields) < 2:
        QMessageBox.information(win, "WebPlus", "This page needs at least two form fields.")
        return
    fields.sort(key=lambda d: (d.get("tab") or 999, d["y"], d["x"]))
    dlg = QDialog(win)
    dlg.setWindowTitle("Set tab order")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("The Tab key moves down this list. Choose one and move it."))
    lst = QListWidget()
    for d in fields:
        item = lst.addItem("%s: %s" % (d.get("ftype", "field"), d.get("label") or d.get("name") or ""))
    row = QHBoxLayout()
    for text, step in (("Move up", -1), ("Move down", 1)):
        b = QPushButton(text)

        def go(_=False, s=step):
            i = lst.currentRow()
            j = i + s
            if i < 0 or not 0 <= j < lst.count():
                return
            it = lst.takeItem(i)
            lst.insertItem(j, it)
            fields.insert(j, fields.pop(i))
            lst.setCurrentRow(j)
        b.clicked.connect(go)
        row.addWidget(b)
    lay.addWidget(lst)
    lay.addLayout(row)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    if dlg.exec_() == QDialog.Accepted:
        for n, d in enumerate(fields, 1):
            d["tab"] = n
        win.commit_if_changed("Set tab order")


def form_action(win):
    d = win.doc
    dlg = QDialog(win)
    dlg.setWindowTitle("Form action")
    lay = QFormLayout(dlg)
    mode = QComboBox()
    for k, t in (("php", "Send by email from my web host (PHP)"), ("mailto", "Open the visitor's email program"),
                 ("custom", "Send to a form service or script at this address")):
        mode.addItem(t, k)
    mode.setCurrentIndex(max(mode.findData(d.form_mode), 0))
    mail = QLineEdit(d.form_email)
    act = QLineEdit(d.form_action)
    act.setPlaceholderText("https://example.com/form-handler")
    lay.addRow("How to send", mode)
    lay.addRow("Email address", mail)
    lay.addRow("Service address", act)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addRow(bb)
    if dlg.exec_() == QDialog.Accepted:
        d.form_mode, d.form_email, d.form_action = mode.currentData(), mail.text().strip(), act.text().strip()
        win.commit_if_changed("Form action")


def lock_form(win, lock=True):
    fields = form_fields(win)
    if not fields:
        QMessageBox.information(win, "WebPlus", "There are no form fields on this page.")
        return
    gid = "form-" + fields[0]["id"]
    for d in fields:
        if lock:
            d["group"] = gid
        elif str(d.get("group", "")).startswith("form-"):
            d["group"] = ""
    win.reload()
    win.commit_if_changed("Lock form" if lock else "Unlock form")
    win.statusBar().showMessage("The form fields now move together" if lock else "The form fields are free again", 5000)


def frame_properties(win):
    objs = [o for o in win.selected() if o.d["kind"] == "image"]
    if not objs:
        win.statusBar().showMessage("Select a picture frame first", 4000)
        return
    d = objs[0].d
    dlg = QDialog(win)
    dlg.setWindowTitle("Frame properties")
    lay = QFormLayout(dlg)
    fit = QComboBox()
    for k, t in (("cover", "Fill the frame (crop the edges)"), ("contain", "Fit inside (show it all)"),
                 ("fill", "Stretch to the frame")):
        fit.addItem(t, k)
    fit.setCurrentIndex(max(fit.findData(d.get("fit", "cover")), 0))
    rad = QSpinBox()
    rad.setRange(0, 500)
    rad.setValue(int(d.get("radius", 0)))
    bw = QSpinBox()
    bw.setRange(0, 40)
    bw.setValue(int(d.get("bw", 0)))
    col = {"c": d.get("bcolor") or "#000000"}
    cb = QPushButton(col["c"])

    def pick():
        c = QColorDialog.getColor(Qt.black, dlg, "Border colour")
        if c.isValid():
            col["c"] = c.name()
            cb.setText(c.name())
    cb.clicked.connect(pick)
    alt = QLineEdit(d.get("alt", ""))
    lay.addRow("Picture size", fit)
    lay.addRow("Rounded corners", rad)
    lay.addRow("Border width", bw)
    lay.addRow("Border colour", cb)
    lay.addRow("Describe the picture", alt)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addRow(bb)
    if dlg.exec_() != QDialog.Accepted:
        return
    for o in objs:
        o.d.update(fit=fit.currentData(), radius=rad.value(), bw=bw.value(), bcolor=col["c"], alt=alt.text())
        o.update()
    win.scene.update()
    win.commit_if_changed("Frame properties")


def view_variables(win):
    from .export import token_values
    vals = token_values(win.doc, win.cur_page())
    dlg = QDialog(win)
    dlg.setWindowTitle("Variables")
    dlg.resize(520, 480)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Type a variable between percent signs in any text. Double-click one to copy it."))
    t = QTableWidget(len(vals), 2)
    t.setHorizontalHeaderLabels(["Variable", "Shows"])
    t.horizontalHeader().setStretchLastSection(True)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    for i, (k, v) in enumerate(sorted(vals.items())):
        t.setItem(i, 0, QTableWidgetItem("%" + k + "%"))
        t.setItem(i, 1, QTableWidgetItem(v))
    t.cellDoubleClicked.connect(lambda r, c: (QApplication.clipboard().setText(t.item(r, 0).text()),
                                              win.statusBar().showMessage("Copied " + t.item(r, 0).text(), 3000)))
    lay.addWidget(t)
    row = QHBoxLayout()
    b = QPushButton("Edit user details...")
    b.clicked.connect(lambda: (dlg.accept(), win.user_details()))
    row.addWidget(b)
    row.addStretch()
    c = QPushButton("Close")
    c.clicked.connect(dlg.accept)
    row.addWidget(c)
    lay.addLayout(row)
    dlg.exec_()


def popup_menu(win):
    objs = win.selected()
    if not objs:
        win.statusBar().showMessage("Select an object first", 4000)
        return
    d = objs[0].d
    dlg = QDialog(win)
    dlg.setWindowTitle("Pop-up menu")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("A menu that drops down when the mouse is over the object.\n"
                         "One entry per line: Label|address  (an address can be page:<id> or a web address)"))
    box = QPlainTextEdit(d.get("popup", ""))
    lay.addWidget(box)
    pages = QComboBox()
    pages.addItem("Add a link to a page...", "")
    for p in win.doc.pages:
        if p.get("type", "page") == "page":
            pages.addItem(p["name"], "%s|page:%s" % (p["name"], p["id"]))

    def add(_=0):
        v = pages.currentData()
        if v:
            box.appendPlainText(v)
            pages.setCurrentIndex(0)
    pages.currentIndexChanged.connect(add)
    lay.addWidget(pages)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    if dlg.exec_() == QDialog.Accepted:
        win.set_prop("popup", box.toPlainText().strip())
