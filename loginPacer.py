import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from loginCheck import loginCheck
from loadCreds import load_credentials


def login_pacer(url_code, driver):
    url_wrt = f"https://ecf.{url_code}.uscourts.gov/cgi-bin/WrtOpRpt.pl"
    logging.info(f"Opening {url_wrt}")

    driver.execute_script(f"window.open('{url_wrt}', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])

    try:
        username, password = load_credentials()
    except Exception as e:
        logging.error(f"Could not load PACER credentials: {e}")
        return False

    wait = WebDriverWait(driver, 20)

    try:
        # Already logged in case
        if driver.find_elements(By.ID, "case_number_text_area_0"):
            logging.info("Already logged in, proceeding with search.")
            return True

        # Wait for either login form or report page
        wait.until(
            lambda d: (
                len(d.find_elements(By.ID, "loginForm:loginName")) > 0
                or len(d.find_elements(By.ID, "case_number_text_area_0")) > 0
            )
        )

        # Report page ready
        if driver.find_elements(By.ID, "case_number_text_area_0"):
            logging.info("Already logged in, proceeding with search.")
            return True

        # Login page
        if driver.find_elements(By.ID, "loginForm:loginName"):
            logging.info("Logging in to PACER")

            username_box = wait.until(
                EC.presence_of_element_located((By.ID, "loginForm:loginName"))
            )
            password_box = wait.until(
                EC.presence_of_element_located((By.ID, "loginForm:password"))
            )
            login_button = wait.until(
                EC.element_to_be_clickable((By.ID, "loginForm:fbtnLogin"))
            )

            username_box.clear()
            username_box.send_keys(username)

            password_box.clear()
            password_box.send_keys(password)

            login_button.click()

            login_event = loginCheck(driver)
            if not login_event:
                logging.error("PACER login failed. Check username/password in pacer.config.")
                return False

            # Wait until search page is really ready
            wait.until(
                EC.presence_of_element_located((By.ID, "case_number_text_area_0"))
            )

            logging.info("User successfully signed in")
            return True

        logging.error("PACER login page or report page could not be identified.")
        return False

    except TimeoutException:
        logging.error("Timed out while loading the PACER login/report page.")
        logging.info(f"PACER page title: {driver.title}")
        logging.info(f"PACER current URL: {driver.current_url}")
        return False

    except Exception as e:
        logging.error(f"PACER login error: {e}")
        logging.info(f"PACER page title: {driver.title}")
        logging.info(f"PACER current URL: {driver.current_url}")
        return False