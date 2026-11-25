"""Main window: tabs for Inspect, Clean (batch), Compare, and Watch."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QFileDialog, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QTabWidget,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget, QComboBox, QCheckBox, QProgressBar,
                               QHBoxLayout, QSplitter, QTextEdit, QLineEdit,
                               QFormLayout, QGroupBox, QScrollArea)

from ..core import service
from ..core.model import FileReport
from ..licensing import License, PRO_PRICE_EUR, FEATURE_TIERS

_ACTION_COLORS = {"strip": "#f28b82", "set": "#a8dab5", "keep": "#5f6368",
                  "flag": "#fdd663", "review": "#8ab4f8"}


def _color_for(action: str) -> str:
    return _ACTION_COLORS.get(action, "#ffffff")


class MainWindow(QMainWindow):
    def __init__(self, license_: License = None):
        super().__init__()
        self.license = license_ or License()
        self.setWindowTitle("Metadata Studio")
        self.resize(1100, 720)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.inspect_tab = InspectTab(self.license)
        self.clean_tab = CleanTab(self.license)
        self.compare_tab = CompareTab(self.license)
        self.watch_tab = WatchTab(self.license)

        self.tabs.addTab(self.inspect_tab, "Inspect")
        self.tabs.addTab(self.clean_tab, "Clean (batch)")
        self.tabs.addTab(self.compare_tab, "Compare")
        self.tabs.addTab(self.watch_tab, "Watch")

        self._status = self.statusBar()
        self._update_tier_badge()

    def _update_tier_badge(self):
        tier = "Pro" if self.license.is_pro() else "Free"
        self._status.showMessage(f"Tier: {tier}  |  Upgrade to Pro at vanguardarts.vip")


def _tree_from_report(tree: QTreeWidget, rep: FileReport):
    tree.clear()
    for f in rep.findings:
        item = QTreeWidgetItem([f.key, f.value, f.action, f.kind if f.kind else "-"])
        for col in range(4):
            if f.action in ("strip", "flag", "set"):
                item.setForeground(col, _qcolor(_color_for(f.action)))
            item.setToolTip(2, f"kind={f.kind} severity={f.severity}")
        tree.addTopLevelItem(item)


def _qcolor(hexs):
    from PySide6.QtGui import QColor
    return QColor(hexs)


def _make_tree():
    tree = QTreeWidget()
    tree.setHeaderLabels(["Key", "Value", "Action", "Kind"])
    tree.setColumnWidth(0, 240)
    tree.setColumnWidth(1, 420)
    tree.setColumnWidth(2, 90)
    tree.setAlternatingRowColors(True)
    return tree


class InspectTab(QWidget):
    def __init__(self, license_):
        super().__init__()
        self.license = license_
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("File or folder…")
        self.add_btn = QPushButton("Add files/folder…")
        self.add_btn.clicked.connect(self._pick)
        self.scan_btn = QPushButton("Inspect")
        self.scan_btn.clicked.connect(self._scan)
        bar.addWidget(self.path_edit, 1)
        bar.addWidget(self.add_btn)
        bar.addWidget(self.scan_btn)
        lay.addLayout(bar)

        self.tree = _make_tree()
        lay.addWidget(self.tree, 1)

    def _pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files")
        if paths:
            self.path_edit.setText(paths[0])
        elif (p := QFileDialog.getExistingDirectory(self, "Select folder")):
            self.path_edit.setText(p)

    def _scan(self):
        path = self.path_edit.text().strip()
        if not path:
            return
        self.tree.clear()
        from pathlib import Path
        files = service._iter_files([path], recurse=True)
        for f in files:
            rep = service.inspect(f)
            root = QTreeWidgetItem([rep.path, rep.format, "", rep.category])
            self.tree.addTopLevelItem(root)
            for fd in rep.findings:
                child = QTreeWidgetItem([fd.key, fd.value, fd.action, fd.kind or "-"])
                root.addChild(child)
            root.setExpanded(True)


class CleanTab(QWidget):
    def __init__(self, license_):
        super().__init__()
        self.license = license_
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Folder to clean (recursive)…")
        self.pick_btn = QPushButton("Browse…")
        self.pick_btn.clicked.connect(self._pick)
        bar.addWidget(self.path_edit, 1)
        bar.addWidget(self.pick_btn)
        lay.addLayout(bar)

        opts = QHBoxLayout()
        opts.addWidget(QLabel("Image level:"))
        self.level = QComboBox()
        self.level.addItems(["0 — metadata strip (lossless)", "1 — clean re-encode",
                             "2 — resample + noise", "3 — micro-crop + jitter"])
        opts.addWidget(self.level)
        self.dry_btn = QCheckBox("Dry run (no writes)")
        self.dry_btn.setChecked(True)
        opts.addWidget(self.dry_btn)
        self.apply_btn = QPushButton("Clean")
        self.apply_btn.clicked.connect(self._clean)
        opts.addWidget(self.apply_btn)
        lay.addLayout(opts)

        self.progress = QProgressBar()
        lay.addWidget(self.progress)
        self.tree = _make_tree()
        lay.addWidget(self.tree, 1)

    def _pick(self):
        p = QFileDialog.getExistingDirectory(self, "Select folder")
        if p:
            self.path_edit.setText(p)

    def _clean(self):
        path = self.path_edit.text().strip()
        if not path:
            return
        if self.level.currentIndex() in (2, 3) and not self.license.is_pro():
            QMessageBox.information(self, "Pro feature",
                                    "Transform ladder levels 2–3 are Pro features "
                                    f"(€{PRO_PRICE_EUR}). Free tier supports 0–1.")
            return
        from ..gui.workers import Worker
        self.worker = Worker(service.sanitize, service._iter_files([path], recurse=True),
                             level=self.level.currentIndex(),
                             dry_run=self.dry_btn.isChecked())
        self.worker.progressed.connect(self._progress)
        self.worker.finished.connect(self._done)
        self.worker.start()

    def _progress(self, done, total, res):
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _done(self, results):
        self.tree.clear()
        for rep in results:
            root = QTreeWidgetItem([rep.path, rep.format, "OK" if not rep.error else "ERR",
                                    rep.category])
            self.tree.addTopLevelItem(root)
            for fd in rep.findings:
                child = QTreeWidgetItem([fd.key, fd.value, fd.action, fd.kind or "-"])
                root.addChild(child)
            root.setExpanded(True)


class CompareTab(QWidget):
    """Side-by-side before/after for a single file."""

    def __init__(self, license_):
        super().__init__()
        self.license = license_
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Single file…")
        self.pick_btn = QPushButton("Browse…")
        self.pick_btn.clicked.connect(self._pick)
        self.diff_btn = QPushButton("Compare")
        self.diff_btn.clicked.connect(self._run)
        bar.addWidget(self.path_edit, 1)
        bar.addWidget(self.pick_btn)
        bar.addWidget(self.diff_btn)
        lay.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        self.before = _make_tree()
        self.before.setHeaderLabels(["Key", "Value", "Action"])
        self.after = _make_tree()
        self.after.setHeaderLabels(["Key", "Value", "Action"])
        split.addWidget(self.before)
        split.addWidget(self.after)
        lay.addWidget(split, 1)

    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select file")
        if p:
            self.path_edit.setText(p)

    def _run(self):
        path = self.path_edit.text().strip()
        if not path:
            return
        before = service.inspect(path)
        # produce a sanitized comparison without touching disk (dry-run)
        after = service.sanitize(path, dry_run=True)
        self.before.clear()
        self.after.clear()
        for f in before.findings:
            self.before.addTopLevelItem(QTreeWidgetItem([f.key, f.value, f.action]))
        for f in after.findings:
            self.after.addTopLevelItem(QTreeWidgetItem([f.key, f.value, f.action]))


class WatchTab(QWidget):
    """Folder monitoring: re-scan on changes and flag new findings."""

    def __init__(self, license_):
        super().__init__()
        self.license = license_
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Folder to watch…")
        self.pick_btn = QPushButton("Browse…")
        self.pick_btn.clicked.connect(self._pick)
        self.start_btn = QPushButton("Start watching")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        bar.addWidget(self.path_edit, 1)
        bar.addWidget(self.pick_btn)
        bar.addWidget(self.start_btn)
        bar.addWidget(self.stop_btn)
        lay.addLayout(bar)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)

        import PySide6
        self._watch_available = hasattr(PySide6, "QtCore")
        self.timer = None

    def _pick(self):
        p = QFileDialog.getExistingDirectory(self, "Select folder")
        if p:
            self.path_edit.setText(p)

    def _start(self):
        if not self.license.is_pro():
            QMessageBox.information(self, "Pro feature",
                                    f"Folder monitoring is a Pro feature (€{PRO_PRICE_EUR}).")
            return
        path = self.path_edit.text().strip()
        if not path:
            return
        # polling-based watch (no external dependency)
        from PySide6.QtCore import QTimer
        import hashlib
        import os
        from pathlib import Path

        def snapshot():
            sigs = []
            for p in Path(path).rglob("*"):
                if p.is_file():
                    st = p.stat()
                    sigs.append((str(p), st.st_mtime, st.st_size))
            return hashlib.sha256(repr(sigs).encode()).hexdigest()

        self.log.append(f"Watching {path}…")
        self._base = snapshot()

        def poll():
            cur = snapshot()
            if cur != self._base:
                self._base = cur
                self.log.append(f"[change detected] re-scanning…")
                for f in service._iter_files([path], recurse=True):
                    rep = service.inspect(f)
                    hits = [fd for fd in rep.findings if fd.action in ("strip", "flag")]
                    if hits:
                        self.log.append(f"  {rep.path}: {len(hits)} finding(s)")
                        for fd in hits[:5]:
                            self.log.append(f"    - {fd.key}: {fd.value}")

        self.timer = QTimer(self)
        self.timer.timeout.connect(poll)
        self.timer.start(2000)
        self.stop_btn.setEnabled(True)
        self.start_btn.setEnabled(False)

    def _stop(self):
        if self.timer:
            self.timer.stop()
            self.log.append("Stopped watching.")
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)


def main():
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
