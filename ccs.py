APP_STYLESHEET = """
QWidget#root {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #191C24, stop: 1 #14161C
    );
    color: white;
    font-family: "Poppins";
    font-size: 10px;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
}

QFrame#headerCard {
    background: transparent;
}

QFrame#mainCard {
    background: #14161C;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
}
QLabel#title {
    font-size: 25px;
    font-weight: 1000;
    font-family: "Poppins";
    color: #f3f3f3;
}

QLabel#subtitle {
    font-size: 11px;
    color: #999999;
}

QLabel#sectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: rgba(255,255,255,0.84);
}

QLabel#statusText {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255,255,255,0.92);
}

QLabel#dot {
    background: #32d98a;
    border-radius: 10px;
    min-width: 20px;
    min-height: 20px;
    max-width: 20px;
    max-height: 20px;
}

QPushButton#pushButton {
    border: none;
    padding: 10px 16px;
    font-weight: 700;
    font-size: 15;
    background: #006986;
    color: white;
    border-radius: 12px;
}

QPushButton#cancelButton {
    border: none;
    padding: 10px 16px;
    font-weight: 700;
    font-size: 15;
    background: #8c0009;
    color: white;
    border-radius: 12px;
}

QPushButton#cancelButton:hover {
    background: #ad000c;
}

QPushButton#pushButton:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #ad59ff, stop: 1 #ff4960
    );
}

QPushButton#pushButton:disabled {
    background: #45454a;
    color: rgba(255,255,255,0.35);
}

QPushButton#macMinBtn,
QPushButton#macCloseBtn
{
    border-radius: 10px;
    font-size: 11px;
    font-weight: 900;
    padding: 0px;
    color: rgba(0, 0, 0, 0.72);
}

QPushButton#macMinBtn {
    background: #f5c542;
}

QPushButton#macMinBtn:hover {
    background: #ffd45c;
}

QPushButton#macCloseBtn
{
    background: #ff5f57;
}

QPushButton#macCloseBtn:hover{
    background: #ff7b74;
}

QFrame#statusFrame,
QFrame#logShell {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
}

QFrame#statusFrame {
    border-radius: 15px;
    min-height: 40px;
}

QFrame#logShell {
    border-radius: 18px;
}

QLineEdit,
QPlainTextEdit#logViewer {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    color: rgba(255,255,255,0.92);
    selection-background-color: rgba(155, 61, 255, 0.35);
}

QLineEdit {
    padding: 10px 12px;
}

QPlainTextEdit#logViewer {
    padding: 8px;
}

QLineEdit:focus,
QPlainTextEdit#logViewer:focus {
    border: 1px solid rgba(0, 132, 168, 0.75);
}

QCheckBox#checkBox
{
    color: #f3f3f3;
    font-size: 13px;
    font-weight: 600;
    spacing: 10px;
    
}

QCheckBox#checkBox:disable
{
    color: rgba(255,255,255,0.35);
    font-size: 13px;
    font-weight: 600;
    spacing: 10px;
    
}

QCheckBox#checkBox::indicator
{
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 1px solid rgba(255,255,255,0.35);
    background: rgba(255,255,255,0.06);
}

QCheckBox#checkBox::indicator:checked
{
    background: #32d98a;
    border: 1px solid #32d98a;
}

QCheckBox#checkBox::indicator:disabled
{
    background: #45454a;
    border: 1px solid #45454a;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 2px;
}

QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.18);
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,0.28);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    border: none;
}

QDialog {
    background: transparent;
}

QFrame#messageCard {
    background: #131314;
    color: white;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
}

QLabel#messageTitle {
    color: #f3f3f3;
    font-size: 14px;
    font-weight: 700;
    font-family: "Poppins";
}

QLabel#messageText {
    color: rgba(255,255,255,0.88);
    font-size: 13px;
    font-family: "Poppins";
}

QLabel#messageIconInfo {
    background: #32d98a;
    border-radius: 9px;
}

QLabel#messageIconWarning {
    background: #f5c542;
    border-radius: 9px;
}

QLabel#messageIconCritical {
    background: #ff5f57;
    border-radius: 9px;
}

QPushButton#messageOkBtn {
    border: none;
    border-radius: 12px;
    color: white;
    background: #006986;
    padding: 8px 14px;
    min-width: 80px;
    font-weight: 700;
}

QPushButton#messageOkBtn:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #ad59ff, stop: 1 #ff4960
    );
}


QPushButton#messageCancelBtn {
    border: none;
    padding: 8px 14px;
    min-width: 80px;
    font-weight: 700;
    background: #45454a;
    color: white;
    border-radius: 12px;
}

QPushButton#messageCancelBtn:hover {
    background: #5a5a60;
}

QPushButton#msgCloseBtn {
    border: none;
    border-radius: 10px;
    background: #ff5f57;
    color: rgba(0, 0, 0, 0.72);
    font-size: 10px;
    font-weight: 900;
    padding: 0px;
}

QPushButton#msgCloseBtn:hover {
    background: #ff7b74;
}
QToolTip {
    background-color: #2b2b2b;
    color: white;
    border: 1px solid #555;
    padding: 6px;
    border-radius: 4px;
    font-size: 10pt;
}

/* App-specific additions for this collector UI */
QMainWindow {
    background: #232323;
}

QListWidget#courtList {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    color: rgba(255,255,255,0.92);
    padding: 8px;
}

QListWidget#courtList::item:selected {
    background: rgba(155, 61, 255, 0.35);
}
"""