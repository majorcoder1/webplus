"""Trigger every menu and right-click command on every kind of object and report any exception.
Run:  XDG_CONFIG_HOME=$(mktemp -d) QT_QPA_PLATFORM=offscreen python3 tools/sweep.py   (about 2 minutes)
It must be run with its own settings folder, because commands like Save workspace write settings."""
import faulthandler, os, sys, traceback
faulthandler.dump_traceback_later(420, exit=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PyQt5.QtWidgets import *
errs = []
sys.excepthook = lambda t, v, tb: errs.append("".join(traceback.format_exception(t, v, tb)))
app = QApplication([])
QDialog.exec_ = lambda self: QDialog.Accepted
QDialog.exec = QDialog.exec_
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
for n in ("information", "warning", "critical"):
    setattr(QMessageBox, n, staticmethod(lambda *a, **k: QMessageBox.Ok))
QInputDialog.getText = staticmethod(lambda *a, **k: (k.get("text") or "Test", True))
QInputDialog.getItem = staticmethod(lambda *a, **k: (a[3][0] if len(a) > 3 and a[3] else "", True))
QInputDialog.getInt = staticmethod(lambda *a, **k: (0, False))
for n in ("getOpenFileName", "getSaveFileName"):
    setattr(QFileDialog, n, staticmethod(lambda *a, **k: ("", "")))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
QMenu.exec_ = lambda self, *a, **k: None
from sitewright.window import MainWindow
from sitewright.model import new_item
from sitewright.canvas import ItemObj
w = MainWindow()
w._sel_guard = True


def ctx_acts(kind):
    m = QMenu(w)
    w.object_context_menu(m, kind) if kind else w.page_context_menu(m)
    out = []
    def walk(mm, path):
        for a in mm.actions():
            if a.menu(): walk(a.menu(), path + [a.text()])
            elif not a.isSeparator(): out.append((["ctx"] + path + [a.text()], a))
    walk(m, [])
    return out


def acts():
    out = []
    def walk(m, path):
        for a in m.actions():
            if a.menu(): walk(a.menu(), path + [a.text()])
            elif not a.isSeparator(): out.append((path + [a.text()], a))
    for a in w.menuBar().actions():
        if a.menu(): walk(a.menu(), [a.text()])
    return out


kinds = ["shape", "text", "image", "table", "rect", "button", "navbar", "gallery", "field", "hotspot", "repeater"]
skip = ("About", "Help articles", "Quit", "Exit", "New site", "Open", "Revert", "Startup", "Import", "Estimate",
        "Publish", "Quick", "Back up", "Preview", "View site online")
total = 0
for scenario in [None] + kinds:
    w.cur_page()["items"].clear()
    if scenario:
        w.cur_page()["items"].append(new_item(scenario, 50, 50))
    w.reload()
    if scenario:
        for o in w.scene.items():
            if isinstance(o, ItemObj) and o.editable:
                o.setSelected(True)
    for path, a in acts() + ctx_acts(scenario):
        label = "/".join(path).replace("&", "")
        if any(s in label for s in skip) or not a.isEnabled():
            continue
        before = len(errs)
        try:
            if a.isCheckable(): a.setChecked(not a.isChecked())
            a.trigger()
        except Exception:
            errs.append(label + "\n" + traceback.format_exc())
        total += 1
        if len(errs) > before:
            errs[-1] = "[%s | %s]\n" % (scenario, label) + errs[-1]
        app.processEvents()
        if a.isCheckable(): a.setChecked(not a.isChecked())
print("triggered", total, "errors", len(errs))
seen = set()
for e in errs:
    k = e.strip().splitlines()[-1]
    if k in seen: continue
    seen.add(k); print(e[-900:]); print("-----")
