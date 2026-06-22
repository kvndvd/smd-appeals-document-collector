import logging
import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

REPORT_READY_ID = "case_number_text_area_0"
LOGIN_USERNAME_ID = "loginForm:loginName"
ATTACHED_DOCS_PATTERN = re.compile(
    r"\b(\d+)\s+documents?\s+are\s+attached\s+to\s+this\s+filing\b",
    re.IGNORECASE,
)
DOWNLOAD_CONFIRMATION_TEXT = "download confirmation"


def _page_has_success_marker(driver):
    if driver.find_elements(By.ID, REPORT_READY_ID):
        return True

    text = ""
    try:
        text = driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        pass

    source = driver.page_source or ""
    combined = f"{text}\n{source}"

    if ATTACHED_DOCS_PATTERN.search(combined):
        return True

    if DOWNLOAD_CONFIRMATION_TEXT in combined.lower():
        return True

    # If the login form is still visible after submitting credentials, login did not complete yet.
    if driver.find_elements(By.ID, LOGIN_USERNAME_ID):
        return False

    return False


def loginCheck(driver, timeout=30):
    """Return True when PACER reaches a known post-login/loaded page for Stage 1."""
    try:
        WebDriverWait(driver, timeout).until(lambda d: _page_has_success_marker(d))
        logging.info("PACER page reached a known post-login state.")
        return True
    except TimeoutException:
        logging.error("PACER login check failed or expected page marker did not load.")
        return False
