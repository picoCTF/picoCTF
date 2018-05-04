""" Module dealing with authentication to the api """

import api
import bcrypt
from api.annotations import log_action
from api.common import InternalException, safe_fail, validate, WebException
from api.user import check
from flask import session
from voluptuous import Length, Required, Schema

log = api.logger.use(__name__)

debug_disable_general_login = False

user_login_schema = Schema({
    Required('username'):
    check(("Usernames must be between 3 and 50 characters.",
           [str, Length(min=3, max=50)]),),
    Required('password'):
    check(("Passwords must be between 3 and 50 characters.",
           [str, Length(min=3, max=50)]))
})


def confirm_password(attempt, password_hash):
    """
    Verifies the password attempt

    Args:
        attempt: the password attempt
        password_hash: the real password pash
    """
    return bcrypt.hashpw(attempt.encode('utf-8'),
                         password_hash) == password_hash


@log_action
def login(username, password):
    """
    Authenticates a user.
    """

    # Read in submitted username and password
    validate(user_login_schema, {"username": username, "password": password})

    user = safe_fail(api.user.get_user, name=username)
    if user is None:
        raise WebException("Incorrect username.")

    if user.get("disabled", False):
        raise WebException("This account has been disabled.")

    if not user["verified"]:
        raise WebException("This account has not been verified yet.")

    if confirm_password(password, user['password_hash']):
        if not user["verified"]:
            try:
                api.email.send_user_verification_email(username)
                raise WebException(
                    "This account is not verified. An additional email has been sent to {}.".
                    format(user["email"]))
            except InternalException as e:
                raise WebException(
                    "You have hit the maximum number of verification emails. Please contact support."
                )

        if debug_disable_general_login:
            if session.get('debugaccount', False):
                raise WebException(
                    "Correct credentials! But the game has not started yet...")
        if user['uid'] is not None:
            session['uid'] = user['uid']
            session.permanent = True
        else:
            raise WebException("Login Error")
    else:
        raise WebException("Incorrect password")


@log_action
def logout():
    """
    Clears the session
    """

    session.clear()


def is_logged_in():
    """
    Check if the user is currently logged in.

    Returns:
        True if the user is logged in, false otherwise.
    """

    logged_in = "uid" in session
    if logged_in and not safe_fail(api.user.get_user, uid=session["uid"]):
        logout()
        return False
    return logged_in


def get_uid():
    """
    Gets the user id from the session if it is logged in.

    Returns:
        The user id of the logged in user.
    """

    if is_logged_in():
        return session['uid']
    else:
        return None
