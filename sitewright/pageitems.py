"""Things you can put on a page that need a little set-up: empty picture frames, rollovers,
animated GIFs and sounds. Each helper takes the main window and makes the object."""
import os

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QMovie, QPixmap
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout)

PICTURES = "Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg)"
SOUNDS = "Sounds (*.mp3 *.ogg *.wav *.m4a *.oga *.opus);;All files (*)"


def _place(win, d):
    """Put a new object on the current page and select it."""
    win.target_list().append(d)
    win.reload({d["id"]})


# -- empty picture frame ------------------------------------------------------
def insert_empty_frame(win, rect=None):
    from .model import new_item
    r = rect or QRectF(80, 80, 240, 160)
    d = new_item("image", round(r.x()), round(r.y()), w=max(round(r.width()), 40),
                 h=max(round(r.height()), 30), asset="")
    _place(win, d)
    win.commit_if_changed("Insert picture frame")
    return d


def fill_frame(win, item, path=None):
    """Choose the picture for a frame (an empty one, or to replace what it holds)."""
    if path is None:
        path, _ = QFileDialog.getOpenFileName(win, "Choose a picture", "", PICTURES)
    if not path:
        return False
    item["asset"] = win.doc.add_asset(path)
    win.reload({item["id"]})
    win.commit_if_changed("Fill picture frame")
    return True


# -- rollover ------------------------------------------------------------------
class RolloverDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.setWindowTitle("Rollover")
        self.paths = {"normal": "", "over": ""}
        v = QVBoxLayout(self)
        v.addWidget(QLabel("A rollover changes its picture when the mouse is over it."))
        form = QFormLayout()
        self.labels = {}
        for key, text in (("normal", "Picture as it looks normally"), ("over", "Picture under the mouse")):
            row = QHBoxLayout()
            lab = QLabel("(none chosen)")
            btn = QPushButton("Choose...")
            btn.clicked.connect(lambda _=False, k=key: self.choose(k))
            row.addWidget(lab, 1)
            row.addWidget(btn)
            form.addRow(text, row)
            self.labels[key] = lab
        self.effect = QComboBox()
        self.effect.addItem("Swap at once", "swap")
        self.effect.addItem("Fade across", "fade")
        form.addRow("How it changes", self.effect)
        self.link = QLineEdit()
        self.link.setPlaceholderText("Optional: a web address to go to when clicked")
        form.addRow("Link", self.link)
        v.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def choose(self, key):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a picture", "", PICTURES)
        if path:
            self.paths[key] = path
            self.labels[key].setText(os.path.basename(path))

    def accept(self):
        if not (self.paths["normal"] and self.paths["over"]):
            QMessageBox.information(self, "Rollover", "Choose both pictures.")
            return
        super().accept()


def make_rollover(win, normal, over, effect="swap", link=""):
    """An image object with a second picture that shows under the mouse."""
    from .model import new_item
    a, b = win.doc.add_asset(normal), win.doc.add_asset(over)
    pm = QPixmap()
    pm.loadFromData(win.doc.asset_bytes(a))
    w, h = (min(pm.width(), 400), 0) if not pm.isNull() else (240, 0)
    h = round(pm.height() * w / pm.width()) if not pm.isNull() and pm.width() else 160
    d = new_item("image", 80, 80, w=w, h=h, asset=a, hover_asset=b, hover_effect=effect, link=link)
    _place(win, d)
    win.commit_if_changed("Insert rollover")
    return d


def insert_rollover(win):
    dlg = RolloverDialog(win)
    if dlg.exec_() == QDialog.Accepted and dlg.paths.get("normal") and dlg.paths.get("over"):
        return make_rollover(win, dlg.paths["normal"], dlg.paths["over"], dlg.effect.currentData(),
                             dlg.link.text().strip())


# -- animated GIF ----------------------------------------------------------------
def make_gif(win, path):
    from .model import new_item
    aid = win.doc.add_asset(path)
    mv = QMovie(path)
    mv.jumpToFrame(0)
    sz = mv.currentPixmap().size()
    w = min(sz.width(), 480) if sz.width() else 240
    h = round(sz.height() * w / sz.width()) if sz.width() else 160
    d = new_item("image", 80, 80, w=w, h=h, asset=aid, fit="fill")
    _place(win, d)
    win.commit_if_changed("Insert animated GIF")
    return d


def insert_gif(win):
    path, _ = QFileDialog.getOpenFileName(win, "Choose an animated GIF", "", "GIF pictures (*.gif)")
    if path:
        return make_gif(win, path)


def is_gif(doc, aid):
    a = doc.assets.get(aid)
    return bool(a) and a["name"].lower().endswith(".gif")


# -- sound ------------------------------------------------------------------------
def make_sound(win, path):
    from .model import new_item
    aid = win.doc.add_asset(path)
    d = new_item("audio", 80, 80, asset=aid)
    _place(win, d)
    win.commit_if_changed("Insert sound")
    return d


def insert_sound(win):
    path, _ = QFileDialog.getOpenFileName(win, "Choose a sound", "", SOUNDS)
    if path:
        return make_sound(win, path)


def sound_html(page, anames):
    """The hidden player for a page's background sound (empty if the page has none)."""
    snd = page.get("sound") or {}
    if snd.get("asset") not in anames:
        return ""
    loop = " loop" if snd.get("loop", True) else ""
    return ('<audio id="pgsnd" src="images/%s"%s preload="auto" style="display:none"></audio>\n'
            '<script>(function(){var a=document.getElementById("pgsnd"),p=a.play();'
            'if(p&&p.catch){p.catch(function(){var go=function(){a.play();["click","keydown","touchstart"]'
            '.forEach(function(e){document.removeEventListener(e,go)})};["click","keydown","touchstart"]'
            '.forEach(function(e){document.addEventListener(e,go)})})}})();</script>\n'
            % (anames[snd["asset"]], loop))


# -- pop-up rollover ------------------------------------------------------------------
class PopupDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.setWindowTitle("Pop-up rollover")
        self.paths = {"base": "", "pop": ""}
        v = QVBoxLayout(self)
        v.addWidget(QLabel("A picture that shows another picture or some words when the mouse is over it."))
        form = QFormLayout()
        self.labels = {}
        for key, text in (("base", "The picture people see"), ("pop", "Picture that pops up (optional)")):
            row = QHBoxLayout()
            lab = QLabel("(none chosen)")
            btn = QPushButton("Choose...")
            btn.clicked.connect(lambda _=False, k=key: self.choose(k))
            row.addWidget(lab, 1)
            row.addWidget(btn)
            form.addRow(text, row)
            self.labels[key] = lab
        from PyQt5.QtWidgets import QPlainTextEdit
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Or the words that pop up")
        self.text.setFixedHeight(70)
        form.addRow("Words", self.text)
        self.side = QComboBox()
        for label, value in (("To the right", "right"), ("To the left", "left"), ("Above", "above"), ("Below", "below")):
            self.side.addItem(label, value)
        form.addRow("Pops up", self.side)
        v.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def choose(self, key):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a picture", "", PICTURES)
        if path:
            self.paths[key] = path
            self.labels[key].setText(os.path.basename(path))

    def accept(self):
        if not self.paths["base"]:
            QMessageBox.information(self, "Pop-up rollover", "Choose the picture people will see.")
            return
        if not self.paths["pop"] and not self.text.toPlainText().strip():
            QMessageBox.information(self, "Pop-up rollover", "Choose a picture or type the words that pop up.")
            return
        super().accept()


def make_popup(win, base, pop="", text="", side="right"):
    from .model import new_item
    a = win.doc.add_asset(base)
    pa = win.doc.add_asset(pop) if pop else ""
    pm = QPixmap()
    pm.loadFromData(win.doc.asset_bytes(a))
    w = min(pm.width(), 300) if not pm.isNull() else 220
    h = round(pm.height() * w / pm.width()) if not pm.isNull() and pm.width() else 150
    d = new_item("popup", 80, 80, w=w, h=h, asset=a, pop_asset=pa, pop_text=text, side=side)
    _place(win, d)
    win.commit_if_changed("Insert pop-up rollover")
    return d


def insert_popup(win):
    dlg = PopupDialog(win)
    if dlg.exec_() == QDialog.Accepted and dlg.paths.get("base"):
        return make_popup(win, dlg.paths["base"], dlg.paths["pop"], dlg.text.toPlainText().strip(),
                          dlg.side.currentData())
