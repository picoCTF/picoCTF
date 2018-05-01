"""
Functional tests regarding user management.
"""

import time

import api
import pytest
from api.common import InternalException, safe_fail, WebException
from common import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


class TestFunctionalUserManagement(object):
    """
    Basic tests for user management
    """

    def setup_class(self):
        start_xvfb()
        self.driver = webdriver.Firefox()
        self.test_user = register_test_user(self.driver)

    def teardown_class(self):
        deactivate_test_user(self.driver, self.test_user)
        stop_xvfb()

    def find_id(self, ID):
        return find_id_with_timeout(self.driver, ID)

    def test_change_password(self):
        """
        Tests updating the test_user's password.
        Assumes logged in
        """

        self.driver.get(BASE_URI+"account")

        current_password = self.find_id("current-password")
        new_password = self.find_id("new-password")
        new_password_confirmation = self.find_id("new-password-confirmation")

        current_password.send_keys(self.test_user["password"])
        self.test_user["password"] += str(random.randint(0, 100000000))
        new_password.send_keys(self.test_user["password"])
        new_password_confirmation.send_keys(self.test_user["password"])

        new_password_confirmation.submit()

    def test_login(self):
        """
        Tests login functionality by using invalid credentials and the correct credentials in self.test_user.
        Leaves cookies set for future tests.
        """

        def login_with(username_text, password_text):
            self.driver.delete_all_cookies()
            self.driver.get(BASE_URI)

            # grab the fields
            username = self.find_id("username")
            password = self.find_id("password")

            # set the fields
            username.send_keys(username_text)
            password.send_keys(password_text)

            # submit the form
            username.submit()

            # wait for processing
            time.sleep(2)

        # try to login with invalid credentials
        login_with(self.test_user["username"], "badpassword")
        assert all([cookie['name'] != "flask" for cookie in self.driver.get_cookies()]), "Logged in with invalid credentials."

        # try to login with correct credentials
        login_with(self.test_user["username"], self.test_user["password"])
        assert any([cookie['name'] == "flask" for cookie in self.driver.get_cookies()]), "Could not login user."
