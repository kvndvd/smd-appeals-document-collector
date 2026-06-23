import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, QSettings, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QFileDialog,
    QDialog,
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
    QGraphicsDropShadowEffect,
    QVBoxLayout,
    QWidget,
)

from courtWorkbook import iter_selected_rows, read_court_urls
from loginPacer import open_pacer_url
from sessionDriver import session
from ccs import APP_STYLESHEET

APP_NAME = "Appeals Document Collector"
v= 1
VERSION = f"v{v}"
SUBAPP_NAME = f"SMD Appeals Document Collector {VERSION}"


class QtLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


class PacerWorker(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str, str, int, int, int, int)
    output_folder_ready = pyqtSignal(str)
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
        self.cancel_requested = False

    def request_cancel(self):
        """Ask the worker to stop after the current PACER row finishes."""
        self.cancel_requested = True

    def _make_run_paths(self):
        run_stamp = datetime.now().strftime("%Y-%m-%d-%I%M%S%p")
        workbook_path = Path(self.xlsm_path).expanduser().resolve()
        output_root = workbook_path.parent / f"Bot_Appeals_Collection_{run_stamp}"
        log_path = output_root / f"appeals-collection-{run_stamp}.log"
        return output_root, log_path

    def run(self):
        root_logger = logging.getLogger()
        file_handler = None
        driver = None
        total = 0
        success = 0
        downloaded_total = 0

        try:
            self.status.emit("Preparing output folder...", "-", 0, 0, 0, 0)
            output_root, log_path = self._make_run_paths()
            output_root.mkdir(parents=True, exist_ok=True)
            self.output_folder_ready.emit(str(output_root))

            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            root_logger.addHandler(file_handler)
            root_logger.setLevel(logging.INFO)

            logging.info("Starting PACER Order PDF collection.")
            logging.info("Workbook: %s", self.xlsm_path)
            logging.info("Output folder: %s", output_root)
            logging.info("Log file: %s", log_path)
            logging.info("Client code: %s", self.client_code or "(blank)")
            logging.info("Selected court(s): %s", ", ".join(self.selected_courts))
            logging.info("Headless mode: %s", self.headless)

            self.status.emit("Preparing workbook...", "Reading workbook...", 0, 0, 0, 0)
            grouped_rows = read_court_urls(self.xlsm_path)
            if not grouped_rows:
                message = "No supported court codes with addDocURL values were found in the workbook."
                logging.error(message)
                self.failed.emit(message)
                return

            selected_items = list(iter_selected_rows(grouped_rows, self.selected_courts))
            total = len(selected_items)
            if total == 0:
                message = "No workbook rows matched the selected courts."
                logging.error(message)
                self.failed.emit(message)
                return

            court_counts = ", ".join(
                f"{court_code}: {len(grouped_rows.get(court_code, []))}"
                for court_code in self.selected_courts
                if grouped_rows.get(court_code)
            )
            logging.info("Usable selected rows: %s. %s", total, court_counts)
            self.status.emit("Workbook ready", court_counts or "Selected courts ready", 0, total, 0, total)

            self.status.emit("Starting browser session...", "-", 0, total, 0, total)
            driver = session(headless=self.headless, download_dir=output_root)

            for index, item in enumerate(selected_items, start=1):
                if self.cancel_requested:
                    logging.info("Cancellation requested. Stopping before row %s of %s.", index, len(selected_items))
                    self.status.emit("Cancelled", "-", index - 1, len(selected_items), success, len(selected_items))
                    break

                total = index
                case_display = item.case_number or "(blank)"
                self.status.emit(f"Starting download | {case_display}", item.court_code, index, len(selected_items), index - 1, len(selected_items))
                logging.info(
                    "Opening workbook row %s of %s | Excel row %s | CaseNumber: %s | Court: %s | URL: %s",
                    index,
                    len(selected_items),
                    item.row_number,
                    case_display,
                    item.court_code,
                    item.add_doc_url,
                )

                result = open_pacer_url(
                    driver=driver,
                    court_code=item.court_code,
                    url=item.add_doc_url,
                    username=self.username,
                    password=self.password,
                    client_code=self.client_code,
                    case_number=item.case_number,
                    output_root=output_root,
                )

                if result.opened:
                    success += 1
                    downloaded_total += result.downloaded
                    logging.info(
                        "Processed row successfully | Excel row %s | CaseNumber: %s | Court: %s | Order PDFs downloaded: %s",
                        item.row_number,
                        case_display,
                        item.court_code,
                        result.downloaded,
                    )
                    self.status.emit(f"Downloaded | {case_display}", item.court_code, index, len(selected_items), index, len(selected_items))
                else:
                    logging.error(
                        "Failed row | Excel row %s | CaseNumber: %s | Court: %s | Reason: %s",
                        item.row_number,
                        case_display,
                        item.court_code,
                        result.message,
                    )
                    self.status.emit(f"Skipped | {case_display}", item.court_code, index, len(selected_items), index, len(selected_items))

            if self.headless and driver is not None:
                self.status.emit("Closing browser session...", "-", len(selected_items), len(selected_items), len(selected_items), len(selected_items))
                driver.quit()
                driver = None
            elif driver is not None:
                self.status.emit("Browser left open for review", "-", len(selected_items), len(selected_items), len(selected_items), len(selected_items))

            logging.info("Downloaded Order PDF total: %s", downloaded_total)
            if self.cancel_requested:
                logging.info("Run cancelled by user: %s/%s row(s) opened successfully.", success, len(selected_items))
                self.status.emit("Cancelled", "User requested stop", total, len(selected_items), success, len(selected_items))
            else:
                logging.info("Run complete: %s/%s row(s) opened successfully.", success, len(selected_items))
                self.status.emit("Complete", "All selected courts", len(selected_items), len(selected_items), len(selected_items), len(selected_items))
            self.finished.emit(success, len(selected_items))

        except Exception as exc:
            logging.exception("PACER collection worker failed: %s", exc)
            self.failed.emit(str(exc))
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
        finally:
            if file_handler is not None:
                root_logger.removeHandler(file_handler)
                file_handler.close()



class FramelessMessageBox(QDialog):
    """Small custom modal dialog with true rounded corners, drag support, and optional buttons."""

    def __init__(self, parent, title, message, icon=QMessageBox.Information, buttons=("OK",)):
        super().__init__(parent)
        self._drag_pos = None
        self.result_value = None
        self.buttons = tuple(buttons or ("OK",))
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Dialog
            | Qt.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(360, 185)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(0)

        self.card = QFrame(self)
        self.card.setObjectName("messageCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 16, 18, 14)
        card_layout.setSpacing(12)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 170))
        self.card.setGraphicsEffect(shadow)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.icon_dot = QLabel()
        self.icon_dot.setObjectName(self._icon_object_name(icon))
        self.icon_dot.setFixedSize(18, 18)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("messageTitle")
        self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.close_btn = QPushButton("X")
        self.close_btn.setObjectName("msgCloseBtn")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(lambda: self._finish(None, accept=False))

        header_row.addWidget(self.icon_dot)
        header_row.addWidget(self.title_label, 1)
        header_row.addWidget(self.close_btn)

        self.message_label = QLabel(message)
        self.message_label.setObjectName("messageText")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        button_row = QHBoxLayout()
        button_row.addStretch()
        for button_text in self.buttons:
            button = QPushButton(str(button_text))
            if str(button_text).strip().lower() in ("ok", "yes"):
                button.setObjectName("messageOkBtn")
            else:
                button.setObjectName("messageCancelBtn")
            button.setMinimumSize(92, 34)
            button.clicked.connect(lambda checked=False, value=str(button_text): self._finish(value))
            button_row.addWidget(button)

        card_layout.addLayout(header_row)
        card_layout.addWidget(self.message_label, 1)
        card_layout.addLayout(button_row)
        root_layout.addWidget(self.card)

    def _finish(self, value, accept=True):
        self.result_value = value
        if accept:
            self.accept()
        else:
            self.reject()

    def exec_and_get_result(self):
        self.exec_()
        return self.result_value

    def _icon_object_name(self, icon):
        if icon == QMessageBox.Critical:
            return "messageIconCritical"
        if icon == QMessageBox.Warning:
            return "messageIconWarning"
        return "messageIconInfo"

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent() is not None:
            parent_center = self.parent().frameGeometry().center()
            self.move(parent_center.x() - self.width() // 2, parent_center.y() - self.height() // 2)
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

class CounselCollectorWindow(QMainWindow):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_NAME)
        self.grouped_rows = {}
        self._drag_pos = None
        self.worker_thread = None
        self.worker = None
        self.current_output_folder = None
        self._is_running = False
        self._cancel_requested = False
        self._close_after_cancel = False
        self._force_close = False

        self.setWindowTitle(APP_NAME)
        self.setFixedSize(600, 420)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._build_ui()
        self._apply_theme()
        self._load_saved_credentials()
        self._log_history = []
        self._status_state = {
            "status": "Ready",
            "court": "-",
            "processing_current": 0,
            "processing_total": 0,
            "completed_current": 0,
            "completed_total": 0,
        }
        self.log_signal.connect(self._append_log)

    def _make_section_label(self, text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        # =====================================================
        # CARD 1: Header card
        # =====================================================

        header_card = QFrame()
        header_card.setObjectName("headerCard")

        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(8)

        left_spacer = QWidget()
        left_spacer.setFixedWidth(52)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)

        title = QLabel(APP_NAME)
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(SUBAPP_NAME)
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        self.window_btn_row = QHBoxLayout()
        self.window_btn_row.setSpacing(8)

        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("macMinBtn")
        self.min_btn.setToolTip("Minimize")
        self.min_btn.setFixedSize(20, 20)
        self.min_btn.clicked.connect(self.showMinimized)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("macCloseBtn")
        self.close_btn.setToolTip("Close")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)

        self.window_btn_row.addWidget(self.min_btn)
        self.window_btn_row.addWidget(self.close_btn)

        right_buttons = QWidget()
        right_buttons.setFixedWidth(60)
        right_buttons.setLayout(self.window_btn_row)

        header_layout.addWidget(left_spacer)
        header_layout.addLayout(title_col, 1)
        header_layout.addWidget(right_buttons)

        # =====================================================
        # CARD 2: Main app card
        # =====================================================

        main_card = QFrame()
        main_card.setObjectName("mainCard")

        main_layout = QGridLayout(main_card)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setHorizontalSpacing(10)
        main_layout.setVerticalSpacing(8)

        # -----------------------------
        # Input fields
        # -----------------------------

        self.lexis_id = QLineEdit()
        self.lexis_id.setPlaceholderText("Username")
        self.lexis_id.setToolTip("Enter PACER Username")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setToolTip("Enter PACER Password")
        self.password.setEchoMode(QLineEdit.Password)

        self.show_password = QCheckBox()
        self.show_password.setObjectName("checkBox")
        self.show_password.setToolTip("Show password")
        self.show_password.toggled.connect(self._toggle_password)

        self.save_credentials = QCheckBox("Remember me")
        self.save_credentials.setObjectName("checkBox")
        self.save_credentials.setToolTip("Save Credentials")

        self.headless = QCheckBox("Headless Mode")
        self.headless.setObjectName("checkBox")
        self.headless.setToolTip("Toggle ON: Headless mode on (Hide Browser) \nToggle OFF: Headless mode off (Show Browser)")
        self.headless.setChecked(True)

        self.client_code = QLineEdit()
        self.client_code.setPlaceholderText("Client code")
        self.client_code.setToolTip("eg. Base_SMD_<legalID>")

        self.xlsm_path = QLineEdit()
        self.xlsm_path.setPlaceholderText("Browse Appeals Template")
        self.xlsm_path.setToolTip("eg. SMD Appeals Template.xlsm")
        self.xlsm_path.setReadOnly(True)

        self.browse_button = QPushButton("Browse")
        self.browse_button.setToolTip("Select SMD Appeals Template")
        self.browse_button.setObjectName("pushButton")
        self.browse_button.setMinimumHeight(38)
        self.browse_button.clicked.connect(self._browse_xlsm)

        self.court_list = QListWidget()
        self.court_list.setMinimumHeight(38)
        self.court_list.setObjectName("courtList")

        self.select_all = QCheckBox("Select all")
        self.select_all.setToolTip("Select All Court ")
        self.select_all.setObjectName("checkBox")
        self.select_all.toggled.connect(self._toggle_all_courts)

        self.view_folder = QPushButton("View Folder")
        self.view_folder.setObjectName("pushButton")
        self.view_folder.setToolTip("Open output folder")
        self.view_folder.setMinimumHeight(38)
        self.view_folder.clicked.connect(self._view_folder)

        self.collect = QPushButton("Start Download")
        self.collect.setObjectName("pushButton")
        self.collect.setToolTip("Start download appeals")
        self.collect.setMinimumHeight(38)
        self.collect.clicked.connect(self._collect_clicked)

        self.status_frame = QFrame()
        self.status_frame.setObjectName("statusFrame")
        self.status_frame.setFixedWidth(300)
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(12, 6, 12, 6)
        status_layout.setSpacing(10)

        self.status_dot = QLabel()
        self.status_dot.setObjectName("dot")
        self.status_text = QLabel("Ready")
        self.status_text.setObjectName("statusText")
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()

        # -----------------------------
        # Form layout
        # -----------------------------

        cred_frame = QVBoxLayout()
        cred_frame.setSpacing(8)
        cred_frame.addWidget(self._make_section_label("PACER ID"))
        cred_frame.addWidget(self.lexis_id)
        pass_row = QHBoxLayout()
        pass_row.setSpacing(8)
        pass_row.addWidget(self.password)
        pass_row.addWidget(self.show_password)
        cred_frame.addLayout(pass_row)
        cred_frame.addWidget(self.client_code)
        cred_frame.addWidget(self.save_credentials)
        folder_start_row = QHBoxLayout()
        folder_start_row.setSpacing(8)
        folder_start_row.addWidget(self.view_folder)
        folder_start_row.addWidget(self.collect)
        cred_frame.addLayout(folder_start_row)
        cred_frame.addWidget(self.status_frame)

        main_layout.addLayout(cred_frame,0,0)

        file_frame = QVBoxLayout()
        file_frame.setSpacing(5)
        file_frame.addWidget(self._make_section_label("SELECT APPEALS TEMPLATE"))
        browse_row = QHBoxLayout()
        browse_row.setSpacing(8)
        browse_row.addWidget(self.xlsm_path)
        browse_row.addWidget(self.browse_button)
        file_frame.addLayout(browse_row)
        file_frame.addWidget(self._make_section_label("AVAILABLE CIRCUIT COURTS"))
        file_frame.addWidget(self.court_list)
        collec_row = QHBoxLayout()
        collec_row.setSpacing(8)
        collec_row.addWidget(self.select_all)
        collec_row.addWidget(self.headless)
        file_frame.addLayout(collec_row)

        main_layout.addLayout(file_frame,0,1)

        root_layout.addWidget(header_card)
        root_layout.addWidget(main_card)
        self.setCentralWidget(root)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    def _apply_theme(self):
        self.setStyleSheet(APP_STYLESHEET)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

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
        path, _ = QFileDialog.getOpenFileName(self, "Select the SMD Appeals Template", "", "Excel Files (*.xlsx *.xlsm);;All Files (*.*)")
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
            self.show_frameless_message(
                "Error",
                "Workbook Error",
                QMessageBox.Critical,
            )
            self._append_log(f"WORKBOOK ERROR: {exc}")
            return

        if not self.grouped_rows:

            self.show_frameless_message(
                "No Courts Found",
                "No supported court codes with addDocURL values were found."
            )
            return

        for court_code, rows in self.grouped_rows.items():
            item = QListWidgetItem(f"{court_code} - {len(rows)} URL(s)")
            item.setData(Qt.UserRole, court_code)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.court_list.addItem(item)
        self.select_all.setChecked(True)
        total_rows = sum(len(rows) for rows in self.grouped_rows.values())
        counts = ", ".join(f"{court_code}: {len(rows)}" for court_code, rows in self.grouped_rows.items())
        self._update_status("Workbook loaded", counts, 0, total_rows, 0, total_rows)

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
        if self.current_output_folder and Path(self.current_output_folder).exists():
            folder = Path(self.current_output_folder)
        else:
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

    def _collect_clicked(self):
        if self._is_running:
            self._cancel_download()
        else:
            self._start()

    def _set_collect_button_mode(self, running, cancelling=False):
        if running:
            self.collect.setText("Cancelling..." if cancelling else "Cancel")
            self.collect.setObjectName("cancelButton")
            self.collect.setEnabled(not cancelling)
        else:
            self.collect.setText("Start Download")
            self.collect.setObjectName("pushButton")
            self.collect.setEnabled(True)

        self.collect.style().unpolish(self.collect)
        self.collect.style().polish(self.collect)
        self.collect.update()

    def _set_inputs_enabled(self, enabled):
        """Disable setup controls while a run is active. View Folder stays enabled."""
        controls = [
            self.lexis_id,
            self.password,
            self.show_password,
            self.save_credentials,
            self.headless,
            self.client_code,
            self.xlsm_path,
            self.browse_button,
            self.court_list,
            self.select_all,
        ]
        for control in controls:
            control.setEnabled(enabled)

        self.view_folder.setEnabled(True)

    def _set_running_ui(self, running):
        self._is_running = running
        self._cancel_requested = False if running else self._cancel_requested
        self._set_inputs_enabled(not running)
        self._set_collect_button_mode(running, cancelling=False)

    def _request_cancel_after_confirmation(self, close_after_cancel=False):
        """Ask the user before cancelling. Returns True only when cancellation was confirmed."""
        if not self._is_running or self._cancel_requested:
            return False

        message = "Still processing.\nAre you sure you want to cancel?"
        if close_after_cancel:
            message = "Still processing.\nAre you sure you want to cancel and close the app?"

        answer = self.show_frameless_message(
            "Cancel Process",
            message,
            QMessageBox.Warning,
            buttons=("Yes", "No"),
        )

        if answer != "Yes":
            return False

        self._cancel_requested = True
        self._close_after_cancel = bool(close_after_cancel)

        if self.worker is not None:
            self.worker.request_cancel()

        self._set_collect_button_mode(True, cancelling=True)

        status_text = "Closing after current row" if close_after_cancel else "Stopping after current row"
        self._update_status(
            "Cancel requested",
            status_text,
            self._status_state.get("processing_current", 0),
            self._status_state.get("processing_total", 0),
            self._status_state.get("completed_current", 0),
            self._status_state.get("completed_total", 0),
        )
        return True

    def _cancel_download(self):
        self._request_cancel_after_confirmation(close_after_cancel=False)

    def _start(self):
        error = self._validate()
        if error:
            self.show_frameless_message(
                "Data Missing",
                "Missing Information",
                QMessageBox.Warning,
            )
            return

        self._save_credentials_if_requested()
        self._set_running_ui(True)
        self._log_history.clear()
        self._update_status("Preparing output folder...", "-", 0, 0, 0, 0)

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
        self.worker.status.connect(self._update_status)
        self.worker.output_folder_ready.connect(self._set_current_output_folder)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._enable_buttons)
        self.worker_thread.start()

    def _set_current_output_folder(self, folder):
        self.current_output_folder = folder

    def _format_status_tooltip(self):
        return (
            f"Status: {self._status_state['status']}\n"
            f"Circuit Court: {self._status_state['court']}\n"
            f"Processing: {self._status_state['processing_current']}/{self._status_state['processing_total']}\n"
            f"Completed: {self._status_state['completed_current']}/{self._status_state['completed_total']}"
        )

    def _refresh_status_label(self):
        if hasattr(self, "status_text"):
            self.status_text.setText(self._status_state["status"])
            self.status_text.setToolTip(self._format_status_tooltip())
            if hasattr(self, "status_frame"):
                self.status_frame.setToolTip(self._format_status_tooltip())

    def _update_status(self, status, court, processing_current, processing_total, completed_current, completed_total):
        self._status_state.update({
            "status": str(status),
            "court": str(court or "-"),
            "processing_current": int(processing_current or 0),
            "processing_total": int(processing_total or 0),
            "completed_current": int(completed_current or 0),
            "completed_total": int(completed_total or 0),
        })
        self._refresh_status_label()

    def _append_log(self, text):
        """Compatibility hook for non-worker messages.

        The GUI now keeps the status label short. Detailed technical logs are
        written to the run log file in the output folder by the worker.
        """
        message = str(text)
        if not hasattr(self, "_log_history"):
            self._log_history = []
        self._log_history.append(message)
        self._status_state["status"] = message[:80]
        self._refresh_status_label()

    def show_frameless_message(self, title: str, message: str, icon=QMessageBox.Information, buttons=("OK",)):
        dialog = FramelessMessageBox(self, title, message, icon, buttons)
        dialog.setStyleSheet(APP_STYLESHEET)
        return dialog.exec_and_get_result()

    def closeEvent(self, event):
        """Confirm before closing while a collection is running."""
        if self._force_close:
            event.accept()
            return

        if self._is_running:
            if self._cancel_requested:
                self.show_frameless_message(
                    "Please Wait",
                    "Cancellation is already requested. The app will close after the current row finishes.",
                    QMessageBox.Information,
                )
            else:
                self._request_cancel_after_confirmation(close_after_cancel=True)
            event.ignore()
            return

        event.accept()

    def _failed(self, message):
        self._append_log(f"ERROR: {message}")
        self.show_frameless_message(
            "PACER Collection Failed",
            "PACER Collection Failed",
            QMessageBox.Critical,
        )

    def _finished(self, success, total):
        if self._cancel_requested:
            self._update_status("Cancelled", "User requested stop",
                                self._status_state.get("processing_current", 0),
                                self._status_state.get("processing_total", total),
                                self._status_state.get("completed_current", success),
                                self._status_state.get("completed_total", total))
            self.show_frameless_message(
            "Collection Cancelled",
            f"Collection cancelled. {success}/{total} row(s) processed successfully.\n\nFull log saved in the output folder."
            )

        else:
            self._append_log(f"Collection complete: {success}/{total} row(s) processed successfully.")
            self.show_frameless_message(
                "Collection Complete",
                f"{success}/{total} row(s) processed successfully.\n\nFull log saved in the output folder."
            )

    # 006986
    def _enable_buttons(self):
        self._is_running = False
        self._set_inputs_enabled(True)
        self._set_collect_button_mode(False)
        close_after_cancel = self._close_after_cancel
        self._cancel_requested = False
        self._close_after_cancel = False

        if close_after_cancel:
            self._force_close = True
            self.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    app = QApplication(sys.argv)
    window = CounselCollectorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
