"""
Common fields used in functional tests
"""

import os
import random
import time
from copy import copy
from subprocess import Popen

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URI = "http://127.0.0.1/"
TIMEOUT = 10

base_test_user = {
    "username": "testuser",
    "password": "testpassword",
    "first_name": "test",
    "last_name": "user",
    "email": "test@test.test",
}

xvfb_process = None

def start_xvfb():
    global xvfb_process
    # run an x virtual frame buffer so firefox can run headlessly
    xvfb_process = Popen(["Xvfb", ":40", "-ac"])
    os.environ["DISPLAY"] = ":40"

def stop_xvfb():
    global xvfb_process
    xvfb_process.kill()

def find_id_with_timeout(driver, ID, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, ID))
    )

def find_class_with_timeout(driver, CLASS, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, CLASS))
    )

def find_xpath_with_timeout(driver, XPATH, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, XPATH))
    )

def find_visible_id_with_timeout(driver, ID, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.ID, ID))
    )

def register_test_user(driver):
    """
    Registers a random test user based on the base_test_user.
    The driver will be logged into this user upon returning.
    Returns the user object created.
    """

    # make a new random username
    new_user = copy(base_test_user)
    new_user["username"] += str(random.randint(0, 100000000))

    driver.get(BASE_URI)

    # make the form a registration form
    set_register = find_id_with_timeout(driver, "set-register")
    set_register.click()

    # grab the fields
    username = find_id_with_timeout(driver, "username")
    password = find_id_with_timeout(driver, "password")
    first_name = find_id_with_timeout(driver, "first-name")
    last_name = find_id_with_timeout(driver, "last-name")
    email = find_id_with_timeout(driver, "email")

    # set the fields
    username.send_keys(new_user["username"])
    password.send_keys(new_user["password"])
    first_name.send_keys(new_user["first_name"])
    last_name.send_keys(new_user["last_name"])
    email.send_keys(new_user["email"])

    # submit the form
    username.submit()

    # wait for processing
    time.sleep(1)

    assert any([cookie['name'] == "flask" for cookie in driver.get_cookies()]), "Could not register user."

    return new_user

def deactivate_test_user(driver, test_user):
    """
    Deactivates the test_user account using the driver provided.
    """

    driver.get(BASE_URI+"account")

    current_password = find_id_with_timeout(driver, "current-password-disable")
    current_password.send_keys(test_user["password"])
    current_password.submit()

    # wait for modal
    confirm_disable = find_visible_id_with_timeout(driver, "modal-yes-button")

    confirm_disable.click()

    time.sleep(3)

    assert all([cookie['name'] != "flask" for cookie in driver.get_cookies()])
