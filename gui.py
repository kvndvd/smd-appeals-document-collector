import logging
import os
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, QSettings, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from courtWorkbook import iter_selected_rows, read_court_urls
from loginPacer import open_pacer_url
from sessionDriver import session

APP_NAME = "Counsel Collector"
ORG_NAME = "LexisNexis"


class QtLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


class PacerWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(int, int)
    failed = pyqtSignal(str)

    def __init__(self, xlsm_path, selected_courts, username, password, client_code, headless):
        super().__init__()
        self.xlsm_path = xlsm_path
        self.selected_courts = selected_courts
        self.username = username
        self.password = password
        self.client_code = client_code
        self.headless = headless

    def run(self):
        handler = QtLogHandler(self.log)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        root = logging.getLogger()
        root.addHandler(handler)
        root.setLevel(logging.INFO)

        driver = None
        total = 0
        success = 0
        try:
            grouped_rows = read_court_urls(self.xlsm_path)
            if not grouped_rows:
                self.failed.emit("No supported court codes with addDocURL values were found in the workbook.")
                return

            logging.info("Client code: %s", self.client_code or "(blank)")
            logging.info("Selected court(s): %s", ", ".join(self.selected_courts))
            driver = session(headless=self.headless)

            for item in iter_selected_rows(grouped_rows, self.selected_courts):
                total += 1
                self.log.emit(
                    f"DEBUG: Opening row {item.row_number} | "
                    f"CaseNumber: {item.case_number or '(blank)'} | "
                    f"Court: {item.court_code}"
                )
                opened = open_pacer_url(
                    driver=driver,
                    court_code=item.court_code,
                    url=item.add_doc_url,
                    username=self.username,
                    password=self.password,
                    client_code=self.client_code,
                    case_number=item.case_number,
                )
                if opened:
                    success += 1
                    self.log.emit(
                        f"DEBUG: Successfully opened row {item.row_number} | "
                        f"CaseNumber: {item.case_number or '(blank)'} | "
                        f"Court: {item.court_code}. Proceeding to the next cell URL."
                    )
                else:
                    self.log.emit(
                        f"DEBUG: Failed to open row {item.row_number} | "
                        f"CaseNumber: {item.case_number or '(blank)'} | "
                        f"Court: {item.court_code}. Proceeding to the next cell URL."
                    )

            if self.headless and driver is not None:
                driver.quit()
                driver = None
            elif driver is not None:
                self.log.emit("Chrome is left open so you can verify the loaded PACER pages.")

            self.finished.emit(success, total)
        except Exception as exc:
            self.failed.emit(str(exc))
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
        finally:
            root.removeHandler(handler)


class CounselCollectorWindow(QMainWindow):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.grouped_rows = {}
        self.worker_thread = None
        self.worker = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(760, 560)
        self._build_ui()
        self._apply_theme()
        self._load_saved_credentials()
        self.log_signal.connect(self._append_log)

    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        root_layout.addWidget(title)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 18)
        card_layout.setHorizontalSpacing(14)
        card_layout.setVerticalSpacing(10)

        self.lexis_id = QLineEdit()
        self.lexis_id.setPlaceholderText("PACER / Lexis ID")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)

        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(self._toggle_password)
        self.save_credentials = QCheckBox("Save credentials")
        self.headless = QCheckBox("Headless Mode")
        self.headless.setChecked(True)

        self.client_code = QLineEdit()
        self.client_code.setPlaceholderText("Client code")

        self.xlsm_path = QLineEdit()
        self.xlsm_path.setPlaceholderText("Select .xlsm workbook")
        self.xlsm_path.setReadOnly(True)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self._browse_xlsm)

        self.court_list = QListWidget()
        self.court_list.setMinimumHeight(100)
        self.court_list.setObjectName("courtList")

        self.select_all = QCheckBox("Select all available courts")
        self.select_all.toggled.connect(self._toggle_all_courts)

        self.view_folder = QPushButton("View Folder")
        self.view_folder.clicked.connect(self._view_folder)
        self.collect = QPushButton("Open PACER")
        self.collect.setObjectName("collectButton")
        self.collect.clicked.connect(self._start)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Status will appear here...")
        self.log_box.setMinimumHeight(120)

        card_layout.addWidget(QLabel("LEXIS / PACER ID"), 0, 0)
        card_layout.addWidget(QLabel("PASSWORD"), 0, 1)
        card_layout.addWidget(self.lexis_id, 1, 0)
        card_layout.addWidget(self.password, 1, 1)
        card_layout.addWidget(self.show_password, 2, 0)
        card_layout.addWidget(self.save_credentials, 2, 1)

        card_layout.addWidget(QLabel("CLIENT CODE"), 3, 0)
        card_layout.addWidget(QLabel("XLSM FILE"), 3, 1)
        card_layout.addWidget(self.client_code, 4, 0)
        file_row = QHBoxLayout()
        file_row.addWidget(self.xlsm_path)
        file_row.addWidget(self.browse_button)
        card_layout.addLayout(file_row, 4, 1)

        card_layout.addWidget(QLabel("AVAILABLE CIRCUIT COURTS"), 5, 0, 1, 2)
        card_layout.addWidget(self.court_list, 6, 0, 1, 2)
        card_layout.addWidget(self.select_all, 7, 0)
        card_layout.addWidget(self.headless, 7, 1)

        card_layout.addWidget(self.view_folder, 8, 0)
        card_layout.addWidget(self.collect, 8, 1)
        card_layout.addWidget(self.log_box, 9, 0, 1, 2)

        root_layout.addWidget(card)
        self.setCentralWidget(root)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #111827;
                color: #e5f3ff;
                font-family: Segoe UI, Arial;
                font-size: 12px;
            }
            QLabel {
                color: #aee6ff;
                font-weight: 700;
            }
            QFrame#card {
                background-color: #0f1724;
                border: 1px solid #1f3756;
                border-radius: 14px;
            }
            QLineEdit, QTextEdit, QListWidget {
                background-color: #0b1220;
                border: 1px solid #263d60;
                border-radius: 9px;
                color: #ffffff;
                padding: 9px;
                selection-background-color: #2dd4ff;
            }
            QListWidget#courtList::item {
                padding: 6px;
            }
            QCheckBox {
                color: #e5f3ff;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #38577d;
                background-color: #0b1220;
            }
            QCheckBox::indicator:checked {
                background-color: #38dfff;
                border: 1px solid #38dfff;
            }
            QPushButton {
                background-color: #111c2e;
                border: 1px solid #2a4264;
                border-radius: 9px;
                color: #ffffff;
                padding: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: #38dfff;
            }
            QPushButton#collectButton {
                color: #06111f;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #30d5e8, stop:0.55 #5867ff, stop:1 #b8eeff);
            }
            QPushButton:disabled {
                background-color: #1a2535;
                color: #607087;
            }
        """)

    def _load_saved_credentials(self):
        saved_user = self.settings.value("username", "")
        saved_password = self.settings.value("password", "")
        saved_client_code = self.settings.value("client_code", "")
        if saved_user:
            self.lexis_id.setText(saved_user)
        if saved_password:
            self.password.setText(saved_password)
        if saved_client_code:
            self.client_code.setText(saved_client_code)
        if saved_user or saved_password or saved_client_code:
            self.save_credentials.setChecked(True)

    def _save_credentials_if_requested(self):
        if self.save_credentials.isChecked():
            self.settings.setValue("username", self.lexis_id.text().strip())
            self.settings.setValue("password", self.password.text())
            self.settings.setValue("client_code", self.client_code.text().strip())
        else:
            self.settings.remove("username")
            self.settings.remove("password")
            self.settings.remove("client_code")

    def _toggle_password(self, checked):
        self.password.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def _browse_xlsm(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select XLSM Workbook", "", "Excel Macro Workbook (*.xlsm)")
        if not path:
            return
        self.xlsm_path.setText(path)
        self._load_courts(path)

    def _load_courts(self, path):
        self.court_list.clear()
        self.select_all.setChecked(False)
        try:
            self.grouped_rows = read_court_urls(path)
        except Exception as exc:
            QMessageBox.critical(self, "Workbook Error", str(exc))
            return

        if not self.grouped_rows:
            QMessageBox.warning(self, "No Courts Found", "No supported court codes with addDocURL values were found.")
            return

        for court_code, rows in self.grouped_rows.items():
            item = QListWidgetItem(f"{court_code} - {len(rows)} URL(s)")
            item.setData(Qt.UserRole, court_code)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.court_list.addItem(item)
        self.select_all.setChecked(True)
        self._append_log(f"Loaded courts from workbook: {', '.join(self.grouped_rows.keys())}")

    def _toggle_all_courts(self, checked):
        state = Qt.Checked if checked else Qt.Unchecked
        for index in range(self.court_list.count()):
            self.court_list.item(index).setCheckState(state)

    def _selected_courts(self):
        selected = []
        for index in range(self.court_list.count()):
            item = self.court_list.item(index)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected

    def _view_folder(self):
        folder = Path(self.xlsm_path.text()).parent if self.xlsm_path.text() else Path.cwd()
        if sys.platform.startswith("win"):
            os.startfile(str(folder))
        elif sys.platform == "darwin":
            os.system(f'open "{folder}"')
        else:
            os.system(f'xdg-open "{folder}"')

    def _validate(self):
        if not self.lexis_id.text().strip():
            return "Enter the PACER / Lexis ID."
        if not self.password.text():
            return "Enter the PACER password."
        if not self.xlsm_path.text().strip():
            return "Select an .xlsm workbook."
        if not self._selected_courts():
            return "Select at least one available court."
        return None

    def _start(self):
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Missing Information", error)
            return

        self._save_credentials_if_requested()
        self.collect.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.log_box.clear()
        self._append_log("Starting stage 1 PACER open test. No downloads will be performed.")
        self._append_log("Reading CaseNumber, LocationID, and addDocURL row by row.")

        self.worker_thread = QThread()
        self.worker = PacerWorker(
            xlsm_path=self.xlsm_path.text().strip(),
            selected_courts=self._selected_courts(),
            username=self.lexis_id.text().strip(),
            password=self.password.text(),
            client_code=self.client_code.text().strip(),
            headless=self.headless.isChecked(),
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append_log)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._enable_buttons)
        self.worker_thread.start()

    def _append_log(self, text):
        self.log_box.append(text)

    def _failed(self, message):
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "PACER Open Failed", message)

    def _finished(self, success, total):
        self._append_log(f"Stage 1 complete: {success}/{total} URL(s) opened successfully.")
        QMessageBox.information(self, "Stage 1 Complete", f"{success}/{total} URL(s) opened successfully.")

    def _enable_buttons(self):
        self.collect.setEnabled(True)
        self.browse_button.setEnabled(True)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    app = QApplication(sys.argv)
    window = CounselCollectorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
