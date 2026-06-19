import logging
from selenium.webdriver.common.by import By
import time

def loginCheck(driver):
    #Rechecking login if user is signed in or credentials were not correct
    limitCounter = 5
    loopCounter = 0

    while loopCounter < limitCounter:
        time.sleep(10)
        #User is already signed in
        if driver.find_element(By.ID, 'case_number_text_area_0').is_displayed() == True:
            logging.info("User successfully signed in")
            loginEvent = True
            break
        else:
            if driver.find_element(By.ID, 'case_number_text_area_0').is_displayed() == False:
                logging.info("User ID or password is invalid. Try again")
                loginEvent = False
                break

    return loginEvent