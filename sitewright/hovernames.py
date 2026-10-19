"""Button names that appear when you point at a picture button.

The name is drawn by Sitewright inside its own window (not as a separate desktop
pop-up), so it shows on every desktop and window manager."""
from PyQt5.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PyQt5.QtWidgets import QLabel, QToolButton

STYLE = ("QLabel{background:#ffffe0;color:#101820;border:1px solid #6b7480;"
         "padding:3px 8px;font-size:13px}")


class HoverNames(QObject):
    def __init__(self, parent=None, delay=300):
        super().__init__(parent)
        self.delay = delay
        self.labels = {}                  # one label per window the buttons live in
        self.pending = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._show)
        self.current = None

    def watch(self, widget):
        widget.installEventFilter(self)

    @staticmethod
    def text_for(w):
        t = w.toolTip()
        if not t and isinstance(w, QToolButton) and w.defaultAction() is not None:
            t = w.defaultAction().toolTip()
        return t

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.ToolTip:
            return True                     # the built-in pop-up is replaced by ours
        if t == QEvent.Enter:
            self.pending = obj
            self.timer.start(self.delay)
        elif t in (QEvent.Leave, QEvent.MouseButtonPress, QEvent.Wheel, QEvent.Hide,
                   QEvent.WindowDeactivate):
            self.hide()
        return False

    def _label_for(self, widget):
        win = widget.window()
        lab = self.labels.get(id(win))
        if lab is None or lab.parent() is not win:
            lab = QLabel(win)
            lab.setStyleSheet(STYLE)
            lab.setAttribute(Qt.WA_TransparentForMouseEvents)
            lab.hide()
            self.labels[id(win)] = lab
        return lab

    def _show(self):
        w = self.pending
        if w is None or not w.isVisible() or not w.underMouse():
            return
        text = self.text_for(w)
        if not text:
            return
        lab = self._label_for(w)
        lab.setText(text)
        lab.adjustSize()
        win = w.window()
        p = w.mapTo(win, QPoint(0, w.height() + 4))
        x = min(max(p.x(), 2), max(win.width() - lab.width() - 2, 2))
        y = p.y()
        if y + lab.height() > win.height():          # no room below: put it above
            y = w.mapTo(win, QPoint(0, 0)).y() - lab.height() - 4
        lab.move(x, max(y, 0))
        lab.raise_()
        lab.show()
        self.current = lab

    def hide(self):
        self.timer.stop()
        self.pending = None
        for lab in self.labels.values():
            lab.hide()
        self.current = None
