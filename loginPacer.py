import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from loginCheck import loginCheck

REPORT_READY_ID = "case_number_text_area_0"
LOGIN_USERNAME_ID = "loginForm:loginName"
LOGIN_PASSWORD_ID = "loginForm:password"
LOGIN_BUTTON_ID = "loginForm:fbtnLogin"
CLIENT_CODE_ID = "loginForm:clientCode"


def open_pacer_url(driver, court_code, url, username, password, client_code, case_number="", timeout=30):
    """
    Open one PACER addDocURL, log in when needed, and confirm the page opened.

    Stage 1 only: this function does not download, scrape, or collect documents.
    Credentials are supplied by the GUI fields, not by a config file.
    Returns True when the selected URL reaches the expected PACER/report page.
    """
    case_display = case_number or "(blank CaseNumber)"
    logging.info("Opening %s | CaseNumber: %s | URL: %s", court_code, case_display, url)

    if not username or not password:
        logging.error("PACER username/password were not provided.")
        return False

    driver.get(url)

    wait = WebDriverWait(driver, timeout)

    try:
        wait.until(
            lambda d: (
                len(d.find_elements(By.ID, LOGIN_USERNAME_ID)) > 0
                or len(d.find_elements(By.ID, REPORT_READY_ID)) > 0
            )
        )

        if driver.find_elements(By.ID, REPORT_READY_ID):
            logging.info("%s | CaseNumber: %s opened successfully; already logged in.", court_code, case_display)
            return True

        logging.info("Logging in to PACER for %s | CaseNumber: %s", court_code, case_display)
        username_box = wait.until(EC.presence_of_element_located((By.ID, LOGIN_USERNAME_ID)))
        password_box = wait.until(EC.presence_of_element_located((By.ID, LOGIN_PASSWORD_ID)))
        login_button = wait.until(EC.element_to_be_clickable((By.ID, LOGIN_BUTTON_ID)))

        username_box.clear()
        username_box.send_keys(username)
        password_box.clear()
        password_box.send_keys(password)

        # Some PACER screens include a client-code field and some do not.
        # Fill it when present, but do not fail the open test when absent.
        client_code_boxes = driver.find_elements(By.ID, CLIENT_CODE_ID)
        if client_code_boxes:
            client_code_boxes[0].clear()
            client_code_boxes[0].send_keys(client_code or "")

        login_button.click()

        if not loginCheck(driver, timeout=timeout):
            logging.error("PACER login failed for %s | CaseNumber: %s. Check the credentials typed in the GUI.", court_code, case_display)
            return False

        wait.until(EC.presence_of_element_located((By.ID, REPORT_READY_ID)))
        logging.info("%s | CaseNumber: %s opened successfully after PACER login.", court_code, case_display)
        return True

    except TimeoutException:
        logging.error("Timed out while opening %s | CaseNumber: %s.", court_code, case_display)
        logging.info("PACER page title: %s", driver.title)
        logging.info("PACER current URL: %s", driver.current_url)
        return False
    except Exception as exc:
        logging.error("PACER open/login error for %s | CaseNumber: %s: %s", court_code, case_display, exc)
        logging.info("PACER page title: %s", driver.title)
        logging.info("PACER current URL: %s", driver.current_url)
        return False
