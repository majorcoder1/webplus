"""Publishing: upload an exported site over FTP, with a progress window like
WebPlus's "File Operation" dialog."""
import ftplib
import os
import tempfile
import time

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                             QProgressBar, QPushButton, QSpinBox, QVBoxLayout)


class Target:
    def __init__(self, host="", port=21, user="", password="", directory="/",
                 tls=True):
        self.host, self.port, self.user = host, port, user
        self.password, self.directory, self.tls = password, directory, tls


def list_files(outdir):
    out = []
    for root, _dirs, names in os.walk(outdir):
        for n in sorted(names):
            ap = os.path.join(root, n)
            out.append((os.path.relpath(ap, outdir).replace(os.sep, "/"), ap,
                        os.path.getsize(ap)))
    out.sort(key=lambda t: (t[0].count("/"), t[0]))
    return out


def file_hashes(outdir):
    import hashlib
    out = {}
    for rel, ap, _size in list_files(outdir):
        with open(ap, "rb") as f:
            out[rel] = hashlib.sha1(f.read()).hexdigest()
    return out


def upload(target, outdir, progress, cancelled, ftp_factory=None, log=lambda s: None,
           only=None):
    """Send every file in outdir. progress(i, n, name, file_done, file_size,
    total_done, total_size). Returns True when everything was sent."""
    files = [f for f in list_files(outdir) if only is None or f[0] in only]
    total = sum(s for _r, _a, s in files) or 1
    if ftp_factory is None:
        ftp_factory = ftplib.FTP_TLS if target.tls else ftplib.FTP
    ftp = ftp_factory()
    log("Connecting to %s ..." % target.host)
    ftp.connect(target.host, target.port, timeout=30)
    ftp.login(target.user, target.password)
    if target.tls and hasattr(ftp, "prot_p"):
        ftp.prot_p()
    ftp.set_pasv(True)
    made = set()

    def goto(path):
        ftp.cwd("/")
        for part in [p for p in path.split("/") if p]:
            try:
                ftp.cwd(part)
            except ftplib.error_perm:
                ftp.mkd(part)
                ftp.cwd(part)

    base = target.directory or "/"
    done = 0
    try:
        for i, (rel, ap, size) in enumerate(files, 1):
            if cancelled():
                log("Cancelled.")
                return False
            sub = os.path.dirname(rel)
            goto((base.rstrip("/") + "/" + sub) if sub else base)
            sent = [0]

            def chunk(block, i=i, rel=rel, size=size):
                sent[0] += len(block)
                progress(i, len(files), rel, sent[0], size, done + sent[0], total)
            progress(i, len(files), rel, 0, size, done, total)
            for attempt in (1, 2, 3):           # a flaky connection should not lose a file
                sent[0] = 0
                try:
                    with open(ap, "rb") as f:
                        ftp.storbinary("STOR " + os.path.basename(rel), f, 8192, chunk)
                    try:
                        remote = ftp.size(os.path.basename(rel))
                    except Exception:  # noqa: BLE001 - not every server offers SIZE
                        remote = None
                    if remote is not None and remote != size:
                        raise OSError("size on server is %s, expected %s" % (remote, size))
                    break
                except (OSError, ftplib.Error) as e:
                    log("%s: attempt %d failed (%s)" % (rel, attempt, e))
                    if attempt == 3:
                        raise
            done += size
            made.add(sub)
            log("Sent %s" % rel)
        progress(len(files), len(files), "", 0, 0, total, total)
        return True
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001 - the connection may already be gone
            pass


class UploadWorker(QThread):
    progress = pyqtSignal(int, int, str, int, int, int, int)
    log = pyqtSignal(str)
    finished_with = pyqtSignal(bool, str)

    def __init__(self, target, outdir, ftp_factory=None, only=None):
        super().__init__()
        self.target, self.outdir, self.factory = target, outdir, ftp_factory
        self.only = only
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            ok = upload(self.target, self.outdir, self.progress.emit,
                        lambda: self._cancel, self.factory, self.log.emit, self.only)
            self.finished_with.emit(ok, "" if ok else "Cancelled")
        except Exception as e:  # noqa: BLE001 - report any network problem
            self.finished_with.emit(False, str(e))


class SettingsDialog(QDialog):
    def __init__(self, parent, target):
        super().__init__(parent)
        self.setWindowTitle("Publish to the web (FTP)")
        f = QFormLayout(self)
        self.host = QLineEdit(target.host)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(target.port)
        self.user = QLineEdit(target.user)
        self.password = QLineEdit(target.password)
        self.password.setEchoMode(QLineEdit.Password)
        self.directory = QLineEdit(target.directory)
        self.tls = QCheckBox("Use a secure connection (FTPS)")
        self.tls.setChecked(target.tls)
        f.addRow("Server", self.host)
        f.addRow("Port", self.port)
        f.addRow("User name", self.user)
        f.addRow("Password", self.password)
        f.addRow("Remote directory", self.directory)
        f.addRow(self.tls)
        f.addRow(QLabel("The password is used for this upload only and is never saved."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def target(self):
        return Target(self.host.text().strip(), self.port.value(), self.user.text().strip(),
                      self.password.text(), self.directory.text().strip() or "/",
                      self.tls.isChecked())


class FileOperationDialog(QDialog):
    """Progress window: server, directory, file x of y, bars, time left, Cancel."""

    def __init__(self, parent, target, outdir, ftp_factory=None, only=None):
        super().__init__(parent)
        self.setWindowTitle("File Operation")
        self.setMinimumWidth(460)
        self.started = time.time()
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Server: %s" % target.host))
        v.addWidget(QLabel("Remote directory: %s" % target.directory))
        self.file_label = QLabel("Connecting...")
        v.addWidget(self.file_label)
        self.name_label = QLabel("")
        v.addWidget(self.name_label)
        self.size_label = QLabel("")
        self.size_label.setAlignment(Qt.AlignRight)
        v.addWidget(self.size_label)
        self.file_bar = QProgressBar()
        v.addWidget(self.file_bar)
        v.addWidget(QLabel("Overall progress:"))
        row = QHBoxLayout()
        self.speed = QLabel("")
        self.left = QLabel("")
        row.addWidget(self.speed)
        row.addStretch(1)
        row.addWidget(self.left)
        v.addLayout(row)
        self.total_bar = QProgressBar()
        v.addWidget(self.total_bar)
        self.status = QPlainTextEdit()
        self.status.setReadOnly(True)
        self.status.setFixedHeight(90)
        self.status.hide()
        v.addWidget(self.status)
        row = QHBoxLayout()
        self.show_btn = QPushButton("Show Status")
        self.show_btn.clicked.connect(self.toggle_status)
        self.cancel_btn = QPushButton("Cancel")
        row.addWidget(self.show_btn)
        row.addStretch(1)
        row.addWidget(self.cancel_btn)
        v.addLayout(row)
        self.result_ok = False
        self.message = ""
        self.worker = UploadWorker(target, outdir, ftp_factory, only)
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.status.appendPlainText)
        self.worker.finished_with.connect(self.on_done)
        self.cancel_btn.clicked.connect(self.cancel)

    def start(self):
        self.worker.start()

    def toggle_status(self):
        self.status.setVisible(not self.status.isVisible())
        self.adjustSize()

    def cancel(self):
        if self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
        else:
            self.reject()

    def on_progress(self, i, n, name, fd, fs, td, ts):
        self.file_label.setText("File %d of %d" % (i, n))
        self.name_label.setText(name)
        self.size_label.setText("%.1f of %.1f Kb" % (fd / 1024, fs / 1024))
        self.file_bar.setRange(0, max(fs, 1))
        self.file_bar.setValue(fd)
        self.total_bar.setRange(0, max(ts, 1))
        self.total_bar.setValue(td)
        el = max(time.time() - self.started, 0.1)
        rate = td / el
        self.speed.setText("%.1f KB/Sec" % (rate / 1024))
        if rate > 0 and td < ts:
            left = int((ts - td) / rate)
            self.left.setText("Time remaining: %d Min, %d Sec" % (left // 60, left % 60))

    def on_done(self, ok, msg):
        self.result_ok, self.message = ok, msg
        self.cancel_btn.setEnabled(True)
        if ok:
            self.accept()
        else:
            self.file_label.setText("Stopped: " + (msg or "error"))
            self.cancel_btn.setText("Close")


def export_temp(doc, export_fn):
    d = tempfile.mkdtemp(prefix="sitewright-pub-")
    export_fn(doc, d)
    return d
