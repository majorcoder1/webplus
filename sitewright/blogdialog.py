"""Tools > Blog manager: write posts, set up comments and likes."""
import copy
import secrets

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                             QPlainTextEdit, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from . import blog


class BlogManager(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.work = copy.deepcopy(win.doc.blog)
        self.cur = None
        self.setWindowTitle("Blog manager")
        self.resize(980, 640)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        # -- posts
        pw = QWidget()
        row = QHBoxLayout(pw)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.pick)
        left.addWidget(self.list, 1)
        for label, fn in (("New post", self.new), ("Delete", self.delete), ("Move up", lambda: self.move(-1)),
                          ("Move down", lambda: self.move(1))):
            b = QPushButton(label)
            b.clicked.connect(fn)
            left.addWidget(b)
        row.addLayout(left, 1)
        right = QVBoxLayout()
        form = QFormLayout()
        self.title = QLineEdit()
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.author = QLineEdit()
        self.category = QComboBox()
        self.category.setEditable(True)
        self.tags = QLineEdit()
        self.published = QCheckBox("Published (untick to keep it as a draft)")
        form.addRow("Title", self.title)
        form.addRow("Date", self.date)
        form.addRow("Author", self.author)
        form.addRow("Category", self.category)
        form.addRow("Tags (commas)", self.tags)
        pic = QHBoxLayout()
        self.thumb = QLabel("No picture")
        self.thumb.setFixedSize(90, 60)
        self.thumb.setStyleSheet("border:1px solid #bbb;background:#eef")
        self.thumb.setAlignment(Qt.AlignCenter)
        pic.addWidget(self.thumb)
        b1, b2 = QPushButton("Choose picture..."), QPushButton("Remove")
        b1.clicked.connect(self.choose_picture)
        b2.clicked.connect(self.remove_picture)
        pic.addWidget(b1)
        pic.addWidget(b2)
        pic.addStretch()
        form.addRow("Picture", pic)
        self.excerpt = QPlainTextEdit()
        self.excerpt.setFixedHeight(54)
        self.excerpt.setPlaceholderText("A sentence or two for the list. Blank = the start of the post.")
        form.addRow("Short excerpt", self.excerpt)
        form.addRow("", self.published)
        right.addLayout(form)
        self.inner = QTabWidget()
        self.body = QPlainTextEdit()
        self.preview = QTextBrowser()
        self.inner.addTab(self.body, "Write")
        self.inner.addTab(self.preview, "Preview")
        self.inner.currentChanged.connect(self.show_preview)
        right.addWidget(self.inner, 1)
        right.addWidget(QLabel("Formatting: blank line = new paragraph. # Heading, ## Smaller heading, - list, "
                               "1. numbered list, > quote, **bold**, *italic*, [words](address), "
                               "![picture](asset:ID) is added with the Insert picture button."))
        ins = QPushButton("Insert picture into the post...")
        ins.clicked.connect(self.insert_picture)
        right.addWidget(ins)
        row.addLayout(right, 3)
        self.tabs.addTab(pw, "Posts")
        # -- settings
        sw = QWidget()
        sf = QFormLayout(sw)
        self.name = QLineEdit(self.work.get("title", "Blog"))
        self.comments = QCheckBox("Readers can leave comments")
        self.comments.setChecked(self.work.get("comments", True))
        self.moderate = QCheckBox("Comments wait for my approval before they appear (recommended)")
        self.moderate.setChecked(self.work.get("moderate", True))
        self.likes = QCheckBox("Readers can like posts")
        self.likes.setChecked(self.work.get("likes", True))
        self.key = QLineEdit(self.work.get("key", ""))
        self.key.setReadOnly(True)
        newkey = QPushButton("Make a new key")
        newkey.clicked.connect(lambda: self.key.setText(secrets.token_hex(10)))
        kr = QHBoxLayout()
        kr.addWidget(self.key)
        kr.addWidget(newkey)
        sf.addRow("Blog name", self.name)
        sf.addRow(self.comments)
        sf.addRow(self.moderate)
        sf.addRow(self.likes)
        sf.addRow("Your secret key", kr)
        note = QLabel("Comments and likes are kept on your own web host, so it must run PHP.\n"
                      "To approve or delete comments, open  yoursite.com/blog-admin.php?key=YOUR KEY  (keep it private).\n"
                      "You are emailed about new comments at the address in Tools > Form email address.")
        note.setWordWrap(True)
        sf.addRow(note)
        self.tabs.addTab(sw, "Comments and likes")
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.fill_list()
        if self.work["posts"]:
            self.list.setCurrentRow(0)
        else:
            self.enable(False)

    # -- list handling
    def fill_list(self, keep=None):
        self.list.blockSignals(True)
        self.list.clear()
        for p in self.work["posts"]:
            it = QListWidgetItem("%s%s\n%s" % ("" if p.get("published", True) else "[draft] ", p["title"], p.get("date", "")))
            it.setData(Qt.UserRole, p["id"])
            self.list.addItem(it)
        self.list.blockSignals(False)
        cats = sorted({p.get("category", "") for p in self.work["posts"] if p.get("category")}, key=str.lower)
        self.cats = cats
        if keep is not None:
            self.list.setCurrentRow(keep)

    def enable(self, on):
        for w in (self.title, self.date, self.author, self.category, self.tags, self.excerpt, self.body,
                  self.published):
            w.setEnabled(on)

    def save_current(self):
        if self.cur is None:
            return
        p = self.cur
        p["title"] = self.title.text().strip() or "Untitled"
        p["date"] = self.date.date().toString("yyyy-MM-dd")
        p["author"] = self.author.text().strip()
        p["category"] = self.category.currentText().strip()
        p["tags"] = self.tags.text().strip()
        p["excerpt"] = self.excerpt.toPlainText().strip()
        p["body"] = self.body.toPlainText()
        p["published"] = self.published.isChecked()

    def pick(self, row):
        self.save_current()
        if row < 0 or row >= len(self.work["posts"]):
            self.cur = None
            self.enable(False)
            return
        p = self.cur = self.work["posts"][row]
        self.enable(True)
        self.title.setText(p["title"])
        try:
            self.date.setDate(QDate.fromString(p.get("date", ""), "yyyy-MM-dd") if p.get("date") else QDate.currentDate())
        except Exception:
            self.date.setDate(QDate.currentDate())
        self.author.setText(p.get("author", ""))
        self.category.clear()
        self.category.addItems(self.cats)
        self.category.setCurrentText(p.get("category", ""))
        self.tags.setText(p.get("tags", ""))
        self.excerpt.setPlainText(p.get("excerpt", ""))
        self.body.setPlainText(p.get("body", ""))
        self.published.setChecked(p.get("published", True))
        self.show_thumb()
        self.inner.setCurrentIndex(0)

    def new(self):
        self.save_current()
        p = blog.new_post("New post")
        self.work["posts"].insert(0, p)
        self.fill_list(0)
        self.pick(0)
        self.title.setFocus()
        self.title.selectAll()

    def delete(self):
        row = self.list.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "WebPlus", "Delete the post \"%s\"?" % self.work["posts"][row]["title"]) != QMessageBox.Yes:
            return
        self.cur = None
        del self.work["posts"][row]
        self.fill_list()
        if self.work["posts"]:
            self.list.setCurrentRow(min(row, len(self.work["posts"]) - 1))
        else:
            self.enable(False)

    def move(self, step):
        row = self.list.currentRow()
        j = row + step
        if row < 0 or not 0 <= j < len(self.work["posts"]):
            return
        self.save_current()
        ps = self.work["posts"]
        ps[row], ps[j] = ps[j], ps[row]
        self.cur = None
        self.fill_list(j)
        self.pick(j)

    # -- pictures
    def add_picture(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a picture", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp)")
        return self.win.doc.add_asset(path) if path else None

    def choose_picture(self):
        if self.cur is None:
            return
        aid = self.add_picture()
        if aid:
            self.cur["asset"] = aid
            self.show_thumb()

    def remove_picture(self):
        if self.cur is not None:
            self.cur["asset"] = ""
            self.show_thumb()

    def insert_picture(self):
        aid = self.add_picture()
        if aid:
            self.body.insertPlainText("\n\n![picture](asset:%s)\n\n" % aid)

    def show_thumb(self):
        pm = self.win.pixmap(self.cur.get("asset")) if self.cur and self.cur.get("asset") else None
        if pm is not None and not pm.isNull():
            self.thumb.setPixmap(pm.scaled(88, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.thumb.setPixmap(QPixmap())
            self.thumb.setText("No picture")

    def show_preview(self, i):
        if i == 1:
            self.preview.setHtml("<h2>%s</h2>%s" % (self.title.text(), blog.render_body(self.body.toPlainText())))

    def accept(self):
        self.save_current()
        self.work.update(title=self.name.text().strip() or "Blog", comments=self.comments.isChecked(),
                         moderate=self.moderate.isChecked(), likes=self.likes.isChecked(), key=self.key.text())
        super().accept()


def blog_manager(win):
    dlg = BlogManager(win)
    if dlg.exec_() == QDialog.Accepted:
        win.doc.blog = dlg.work
        win.reload({o.d["id"] for o in win.selected()})
        win.commit_if_changed("Blog")
