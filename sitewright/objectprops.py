"""Extra settings for any object: CSS properties, HTML attributes and Actions (what happens when
someone clicks it or moves the mouse over it). The rules about what is allowed and how each is
written onto the page are plain functions; the dialogs are at the bottom."""
import html
import json
import os
import re

from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QTableWidget, QVBoxLayout)

from .pagetools import describe

NAMES_FILE = os.path.join(os.path.dirname(__file__), "library", "css_properties.json")
STATES = ["normal", "hover", "focus", "active"]
BLOCKED_ATTRS = {"style", "class", "id"}            # these have their own settings
EVENTS = [("click", "Clicked"), ("hover", "Mouse moves over it"), ("leave", "Mouse moves off it")]
DOS = [("show", "Show an object"), ("hide", "Hide an object"), ("toggle", "Show or hide an object"),
       ("alert", "Show a message"), ("goto", "Go to a page or address"), ("js", "Run my own JavaScript")]


def names():
    try:
        with open(NAMES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return dict(css=[], html=[], events=[])


# -- rules ---------------------------------------------------------------------------
def css_problem(prop, value):
    """None if this property and value are fine to write, otherwise a few words on what is wrong."""
    prop, value = (prop or "").strip(), (value or "").strip()
    if not prop or not value:
        return "Fill in both the property and its value"
    if not re.match(r"^(--)?[a-z][a-z0-9-]*$", prop):
        return '"%s" is not a CSS property name (letters and hyphens only)' % prop
    if len(value) > 300 or re.search(r"[;{}<>\\]", value):
        return 'The value of %s has a character that is not allowed (; { } < > \\)' % prop
    low = value.lower().replace(" ", "")
    if "javascript:" in low or "expression(" in low or "@import" in low or "behavior:" in low:
        return "The value of %s is not allowed" % prop
    return None


def attr_problem(name, value):
    name = (name or "").strip().lower()
    if not name:
        return "Give the attribute a name"
    if not re.match(r"^[a-z_:][a-z0-9_:.-]*$", name):
        return '"%s" is not an attribute name' % name
    if name in BLOCKED_ATTRS:
        return "%s is set elsewhere (use the CSS properties, the HTML id and the CSS class boxes)" % name
    return None


def clean_css(rows):
    out = []
    for r in rows or []:
        prop, value = r.get("prop", "").strip().lower(), r.get("value", "").strip()
        if css_problem(prop, value) is None:
            out.append(dict(state=r.get("state") if r.get("state") in STATES else "normal", prop=prop, value=value))
    return out


def clean_attrs(rows):
    out = []
    for r in rows or []:
        name = r.get("name", "").strip().lower()
        if attr_problem(name, r.get("value", "")) is None:
            out.append(dict(name=name, value=r.get("value", "")))
    return out


def dom_id(d):
    """The id an object has on the published page."""
    ident = d.get("ident") or d.get("anchor")
    return re.sub(r"[^A-Za-z0-9_-]", "-", ident) if ident else "o-" + re.sub(r"[^A-Za-z0-9_-]", "", d["id"])


def targets(items):
    """Ids of objects that some action points at."""
    return {a.get("target") for it in items for a in it.get("actions") or [] if a.get("target")}


# -- writing them onto the page -------------------------------------------------------
def append_style(out, extra):
    """Add CSS to the end of the first element's style attribute, so it wins."""
    m = re.match(r'(<\w+[^>]*?\sstyle=")([^"]*)(")', out)
    if not m or not extra:
        return out
    return out[:m.start(2)] + m.group(2).rstrip(";") + ";" + extra.replace('"', "&quot;") + out[m.end(2):]


def add_attrs(out, text):
    return re.sub(r"^<(\w+)", lambda m: "<%s %s" % (m.group(1), text), out, 1) if text else out


def action_js(d, items_by_id, resolve):
    """JavaScript for one object's actions, or ''."""
    acts = d.get("actions") or []
    if not acts:
        return ""
    el = dom_id(d)
    parts = []
    for ev in ("click", "hover", "leave"):
        body = []
        for a in acts:
            if a.get("on") != ev:
                continue
            do, val = a.get("do"), a.get("value", "")
            tgt = items_by_id.get(a.get("target"))
            tid = json.dumps(dom_id(tgt)) if tgt else None
            if do in ("show", "hide", "toggle") and tid:
                t = "document.getElementById(%s)" % tid
                if do == "show":
                    body.append("var t=%s;if(t)t.style.display='';" % t)
                elif do == "hide":
                    body.append("var t=%s;if(t)t.style.display='none';" % t)
                else:
                    body.append("var t=%s;if(t)t.style.display=(getComputedStyle(t).display==='none')?'':'none';" % t)
            elif do == "alert":
                body.append("alert(%s);" % json.dumps(val))
            elif do == "goto" and val:
                body.append("location.href=%s;" % json.dumps(resolve(val)))
            elif do == "js" and val.strip():
                body.append("try{%s}catch(err){}" % val.replace("</", "<\\/"))
        if body:
            name = {"click": "click", "hover": "mouseenter", "leave": "mouseleave"}[ev]
            parts.append("e.addEventListener(%s,function(ev){%s});" % (json.dumps(name), "".join(body)))
    if not parts:
        return ""
    js = "(function(){var e=document.getElementById(%s);if(!e)return;%s})();" % (json.dumps(el), "".join(parts))
    return js.replace("</", "<\\/")          # nothing typed by the user can end the <script> early


def markup(out, d, page_css, page_js, items_by_id, resolve):
    """Apply an object's CSS properties, attributes and actions to its finished HTML."""
    if not out.startswith("<"):
        return out
    rows = clean_css(d.get("cssp"))
    normal = ";".join("%s:%s" % (r["prop"], r["value"]) for r in rows if r["state"] == "normal")
    if normal:
        out = append_style(out, normal)
    states = {}
    for r in rows:
        if r["state"] != "normal":
            states.setdefault(r["state"], []).append("%s:%s!important" % (r["prop"], r["value"]))
    if states:
        cls = "cp-" + re.sub(r"[^A-Za-z0-9_-]", "", d["id"])
        out = re.sub(r'class="([^"]*)"', lambda m: 'class="%s %s"' % (m.group(1), cls), out, 1)
        for st, decls in states.items():
            page_css.append(".%s:%s{%s}" % (cls, st, ";".join(decls)))
    attrs = " ".join('%s="%s"' % (r["name"], html.escape(r["value"], quote=True)) for r in clean_attrs(d.get("attrs")))
    out = add_attrs(out, attrs)
    js = action_js(d, items_by_id, resolve)
    if js:
        page_js.append(js)
        if not re.match(r'<\w+[^>]*\sid="', out):
            out = add_attrs(out, 'id="%s"' % dom_id(d))
    elif d["id"] in getattr(markup, "targets", ()) and not re.match(r'<\w+[^>]*\sid="', out):
        out = add_attrs(out, 'id="%s"' % dom_id(d))
    return out


# ============================== dialogs ================================================
class RowsDialog(QDialog):
    """A little table you add rows to. Subclasses say what the columns are."""
    TITLE = ""
    HELP = ""
    COLUMNS = []

    def __init__(self, win, rows):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(self.TITLE)
        self.resize(640, 380)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(self.HELP))
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        v.addWidget(self.table, 1)
        row = QHBoxLayout()
        add = QPushButton("Add")
        add.clicked.connect(lambda: self.add_row({}))
        rem = QPushButton("Remove")
        rem.clicked.connect(self.remove_row)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.try_accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        for r in rows or []:
            self.add_row(r)

    def remove_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    @staticmethod
    def combo(items, current=None, editable=False):
        box = QComboBox()
        box.setEditable(editable)
        for it in items:
            if isinstance(it, tuple):
                box.addItem(it[1], it[0])
            else:
                box.addItem(it)
        if current is not None:
            i = box.findData(current) if items and isinstance(items[0], tuple) else box.findText(current)
            if i >= 0:
                box.setCurrentIndex(i)
            elif editable:
                box.setEditText(current)
        return box

    def try_accept(self):
        problem = self.problem()
        if problem:
            QMessageBox.information(self, self.TITLE, problem)
            return
        self.accept()

    def problem(self):
        return None


class CssDialog(RowsDialog):
    TITLE = "CSS properties"
    HELP = ("Extra styling for this object, written straight onto the page. 'normal' always applies; "
            "'hover' only while the mouse is over it.")
    COLUMNS = ["When", "Property", "Value"]

    def add_row(self, r):
        n = self.table.rowCount()
        self.table.insertRow(n)
        self.table.setCellWidget(n, 0, self.combo(STATES, r.get("state", "normal")))
        self.table.setCellWidget(n, 1, self.combo([""] + names()["css"], r.get("prop", ""), True))
        self.table.setCellWidget(n, 2, QLineEdit(r.get("value", "")))

    def rows(self):
        return [dict(state=self.table.cellWidget(i, 0).currentText(),
                     prop=self.table.cellWidget(i, 1).currentText().strip(),
                     value=self.table.cellWidget(i, 2).text().strip()) for i in range(self.table.rowCount())]

    def problem(self):
        for r in self.rows():
            p = css_problem(r["prop"], r["value"])
            if p:
                return p
        return None


class AttrsDialog(RowsDialog):
    TITLE = "HTML attributes"
    HELP = "Extra attributes written on this object's tag, for example title, role, tabindex or data-... ."
    COLUMNS = ["Attribute", "Value"]

    def add_row(self, r):
        n = self.table.rowCount()
        self.table.insertRow(n)
        nm = names()
        self.table.setCellWidget(n, 0, self.combo([""] + nm["html"] + nm["events"], r.get("name", ""), True))
        self.table.setCellWidget(n, 1, QLineEdit(r.get("value", "")))

    def rows(self):
        return [dict(name=self.table.cellWidget(i, 0).currentText().strip(),
                     value=self.table.cellWidget(i, 1).text()) for i in range(self.table.rowCount())]

    def problem(self):
        for r in self.rows():
            p = attr_problem(r["name"], r["value"])
            if p:
                return p
        return None


class ActionsDialog(RowsDialog):
    TITLE = "Actions"
    HELP = ("What happens when someone clicks this object or moves the mouse over it. "
            "Pick the object to show or hide from the list, or type a message, address or JavaScript.")
    COLUMNS = ["When", "Do this", "To this object", "Message, address or code"]

    def __init__(self, win, rows, me):
        self.me = me
        self.others = [d for d in win.target_list() if d["id"] != me["id"]]
        super().__init__(win, rows)
        self.resize(760, 380)

    def add_row(self, r):
        n = self.table.rowCount()
        self.table.insertRow(n)
        self.table.setCellWidget(n, 0, self.combo(EVENTS, r.get("on", "click")))
        self.table.setCellWidget(n, 1, self.combo(DOS, r.get("do", "toggle")))
        self.table.setCellWidget(n, 2, self.combo([("", "(none)")] + [(d["id"], describe(d)) for d in self.others],
                                                  r.get("target", "")))
        self.table.setCellWidget(n, 3, QLineEdit(r.get("value", "")))

    def rows(self):
        return [dict(on=self.table.cellWidget(i, 0).currentData(), do=self.table.cellWidget(i, 1).currentData(),
                     target=self.table.cellWidget(i, 2).currentData() or "",
                     value=self.table.cellWidget(i, 3).text()) for i in range(self.table.rowCount())]

    def problem(self):
        for r in self.rows():
            if r["do"] in ("show", "hide", "toggle") and not r["target"]:
                return "Choose which object to show or hide."
            if r["do"] in ("alert", "goto", "js") and not r["value"].strip():
                return "Type the message, address or code for each action."
        return None


def edit_rows(win, key, dialog_cls, clean, label, *extra):
    objs = win.selected()
    if not objs:
        win.statusBar().showMessage("Select an object first", 4000)
        return False
    d = objs[0].d
    dlg = dialog_cls(win, d.get(key) or [], *extra) if not extra else dialog_cls(win, d.get(key) or [], d)
    if dlg.exec_() != QDialog.Accepted:
        return False
    rows = clean(dlg.rows())
    if rows:
        d[key] = rows
    else:
        d.pop(key, None)
    win.commit_if_changed(label)
    return True


def clean_actions(rows):
    out = []
    for r in rows or []:
        if r.get("on") in dict(EVENTS) and r.get("do") in dict(DOS):
            out.append(dict(on=r["on"], do=r["do"], target=r.get("target", ""), value=r.get("value", "")))
    return out
