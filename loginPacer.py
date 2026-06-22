import logging
import re
from dataclasses import dataclass
from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from documentDownloader import download_order_documents_from_current_page
from loginCheck import loginCheck

REPORT_READY_ID = "case_number_text_area_0"
LOGIN_USERNAME_ID = "loginForm:loginName"
LOGIN_PASSWORD_ID = "loginForm:password"
LOGIN_BUTTON_ID = "loginForm:fbtnLogin"
CLIENT_CODE_ID = "loginForm:clientCode"

ATTACHED_DOCS_PATTERN = re.compile(
    r"\b(\d+)\s+documents?\s+are\s+attached\s+to\s+this\s+filing\b",
    re.IGNORECASE,
)
DOWNLOAD_CONFIRMATION_TEXT = "download confirmation"


@dataclass(frozen=True)
class PacerOpenResult:
    opened: bool
    downloaded: int = 0
    state: str = "unknown"
    message: str = ""


def _page_text(driver):
    try:
        return driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        return driver.page_source or ""


def detect_pacer_page_state(driver):
    """
    Detect the PACER page state.

    Returns:
      - login_required
      - attached_documents
      - download_confirmation
      - report_ready
      - loaded_unknown
    """
    if driver.find_elements(By.ID, LOGIN_USERNAME_ID):
        return "login_required"

    text = _page_text(driver)
    source = driver.page_source or ""
    combined = f"{text}\n{source}"
    combined_lower = combined.lower()

    if ATTACHED_DOCS_PATTERN.search(combined):
        return "attached_documents"

    if DOWNLOAD_CONFIRMATION_TEXT in combined_lower:
        return "download_confirmation"

    if driver.find_elements(By.ID, REPORT_READY_ID):
        return "report_ready"

    return "loaded_unknown"


def describe_pacer_page_state(driver):
    text = _page_text(driver)
    source = driver.page_source or ""
    combined = f"{text}\n{source}"

    match = ATTACHED_DOCS_PATTERN.search(combined)
    if match:
        count = match.group(1)
        return f"Detected attached-document notice: {count} document(s) are attached to this filing."

    if DOWNLOAD_CONFIRMATION_TEXT in combined.lower():
        return "Detected Download Confirmation page."

    if driver.find_elements(By.ID, REPORT_READY_ID):
        return "Detected PACER report/search page."

    return "Page loaded, but the expected markers were not detected."


def _wait_for_page_state(driver, timeout):
    wait = WebDriverWait(driver, timeout)
    return wait.until(
        lambda d: detect_pacer_page_state(d)
        if detect_pacer_page_state(d) in {
            "login_required",
            "attached_documents",
            "download_confirmation",
            "report_ready",
        }
        else False
    )


def _fill_client_code_if_present(driver, client_code):
    client_code_boxes = driver.find_elements(By.ID, CLIENT_CODE_ID)
    if client_code_boxes:
        client_code_boxes[0].clear()
        client_code_boxes[0].send_keys(client_code or "")
        logging.info("Client code field found and filled.")
    else:
        logging.info("Client code field was not present on this PACER login page.")


def open_pacer_url(
    driver,
    court_code,
    url,
    username,
    password,
    client_code,
    case_number="",
    output_root=None,
    timeout=30,
):
    """
    Open one PACER addDocURL, log in only when the login form is present,
    then download only attached documents whose Description contains Order/Orders.
    """
    case_display = case_number or "(blank CaseNumber)"
    logging.info("Opening %s | CaseNumber: %s | URL: %s", court_code, case_display, url)

    if not username or not password:
        logging.error("PACER username/password were not provided.")
        return PacerOpenResult(False, 0, "missing_credentials", "Missing PACER username/password.")

    driver.get(url)
    wait = WebDriverWait(driver, timeout)

    try:
        state = _wait_for_page_state(driver, timeout)

        if state == "login_required":
            logging.info(
                "Login form detected for %s | CaseNumber: %s. Logging in for this browser session.",
                court_code,
                case_display,
            )

            username_box = wait.until(EC.presence_of_element_located((By.ID, LOGIN_USERNAME_ID)))
            password_box = wait.until(EC.presence_of_element_located((By.ID, LOGIN_PASSWORD_ID)))
            login_button = wait.until(EC.element_to_be_clickable((By.ID, LOGIN_BUTTON_ID)))

            username_box.clear()
            username_box.send_keys(username)
            password_box.clear()
            password_box.send_keys(password)
            _fill_client_code_if_present(driver, client_code)

            login_button.click()

            if not loginCheck(driver, timeout=timeout):
                message = "PACER login/page check failed. Check the credentials typed in the GUI."
                logging.error("%s | %s | CaseNumber: %s", message, court_code, case_display)
                return PacerOpenResult(False, 0, "login_failed", message)
        else:
            logging.info(
                "No PACER login form detected for %s | CaseNumber: %s. Skipping login.",
                court_code,
                case_display,
            )

        state = _wait_for_page_state(driver, timeout)
        message = describe_pacer_page_state(driver)
        logging.info("%s | CaseNumber: %s | %s", court_code, case_display, message)

        if state not in {"attached_documents", "download_confirmation", "report_ready"}:
            logging.error("%s | CaseNumber: %s opened, but no expected success marker was detected.", court_code, case_display)
            return PacerOpenResult(False, 0, state, message)

        downloaded = 0
        if state in {"attached_documents", "download_confirmation"}:
            downloads_dir = Path(output_root or Path.cwd() / "downloads")
            downloaded = download_order_documents_from_current_page(
                driver=driver,
                output_root=downloads_dir,
                location_id=court_code,
                case_number=case_number,
                timeout=timeout,
            )
            logging.info(
                "%s | CaseNumber: %s | Downloaded %s Order PDF(s). Proceeding to next workbook row.",
                court_code,
                case_display,
                downloaded,
            )
        else:
            logging.info(
                "%s | CaseNumber: %s reached report/search page. No attached-document table was available to download from.",
                court_code,
                case_display,
            )

        return PacerOpenResult(True, downloaded, state, message)

    except TimeoutException:
        message = f"Timed out while opening {court_code} | CaseNumber: {case_display}."
        logging.error(message)
        logging.info("PACER page title: %s", driver.title)
        logging.info("PACER current URL: %s", driver.current_url)
        logging.info("Current page check: %s", describe_pacer_page_state(driver))
        return PacerOpenResult(False, 0, "timeout", message)
    except Exception as exc:
        message = f"PACER open/download error for {court_code} | CaseNumber: {case_display}: {exc}"
        logging.error(message)
        logging.info("PACER page title: %s", driver.title)
        logging.info("PACER current URL: %s", driver.current_url)
        return PacerOpenResult(False, 0, "error", message)
