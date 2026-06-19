import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def loginCheck(driver, timeout=30):
    """Return True when the PACER/report page is ready after login."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "case_number_text_area_0"))
        )
        logging.info("User successfully signed in")
        return True
    except TimeoutException:
        logging.error("PACER login check failed or report page did not load.")
        return False
