""" Module for email related functionality. """

from datetime import datetime

import api
from api.common import (check, InternalException, safe_fail, validate,
                        WebException)
from flask_mail import Message
from voluptuous import Length, Required, Schema

mail = None

password_reset_request_schema = Schema({
    Required('username'):
    check(("Usernames must be between 3 and 20 characters.",
           [str, Length(min=3, max=20)]),)
})

password_reset_schema = Schema({
    Required("token"):
    check(("This does not look like a valid token.", [str, Length(max=100)])),
    Required('password'):
    check(("Passwords must be between 3 and 20 characters.",
           [str, Length(min=3, max=20)]))
})


def reset_password(token_value, password, confirm_password):
    """
    Perform the password update operation.

    Gets a token and new password from a submitted form, if the token is found in a team object in the database
    the new password is hashed and set, the token is then removed and an appropriate response is returned.

    Args:
        token_value: the password reset token
        password: the password to set
        confirm_password: the same password again
    """

    validate(password_reset_schema, {
        "token": token_value,
        "password": password
    })
    uid = api.token.find_key_by_token("password_reset", token_value)["uid"]
    api.user.update_password_request(
        {
            "new-password": password,
            "new-password-confirmation": confirm_password
        },
        uid=uid)

    api.token.delete_token({"uid": uid}, "password_reset")


def request_password_reset(username):
    """
    Emails a user a link to reset their password.

    Checks that a username was submitted to the function and grabs the relevant team info from the db.
    Generates a secure token and inserts it into the team's document as 'password_reset_token'.
    A link is emailed to the registered email address with the random token in the url.  The user can go to this
    link to submit a new password, if the token submitted with the new password matches the db token the password
    is hashed and updated in the db.

    Args:
        username: the username of the account
    """
    validate(password_reset_request_schema, {"username": username})
    user = safe_fail(api.user.get_user, name=username)
    if user is None:
        raise WebException("No registration found for '{}'.".format(username))

    token_value = api.token.set_token({"uid": user['uid']}, "password_reset")

    settings = api.config.get_settings()

    body = """We recently received a request to reset the password for the following {0} account:\n\n\t{2}\n\nOur records show that this is the email address used to register the above account.  If you did not request to reset the password for the above account then you need not take any further steps.  If you did request the password reset please follow the link below to set your new password. \n\n {1}/reset#{3} \n\n Best of luck! \n The {0} Team""".format(
        settings["competition_name"], settings["competition_url"], username,
        token_value)

    subject = "{} Password Reset".format(settings["competition_name"])

    message = Message(body=body, recipients=[user['email']], subject=subject)
    mail.send(message)


def send_user_verification_email(username):
    """
    Emails the user a link to verify his account. If email_verification is
    enabled in the config then the user won't be able to login until this step is completed.
    """

    settings = api.config.get_settings()
    db = api.common.get_conn()

    user = api.user.get_user(name=username)

    key_query = {
        "$and": [{
            "uid": user["uid"]
        }, {
            "email_verification_count": {
                "$exists": True
            }
        }]
    }
    previous_key = api.token.find_key(key_query)

    if previous_key is None:
        token_value = api.token.set_token({
            "uid": user["uid"],
            "email_verification_count": 1
        }, "email_verification")
    else:
        if previous_key["email_verification_count"] < settings["email"]["max_verification_emails"]:
            token_value = previous_key["tokens"]["email_verification"]
            db.tokens.find_and_modify(key_query,
                                      {"$inc": {
                                          "email_verification_count": 1
                                      }})
        else:
            raise InternalException(
                "User has been sent the maximum number of verification emails.")

    # Is there a better way to do this without dragging url_for + app_context into it?
    verification_link = "{}/api/user/verify?uid={}&token={}".\
        format(settings["competition_url"], user["uid"], token_value)

    body = """
Welcome to {0}!

You will need to visit the verification link below to finalize your account's creation. If you believe this to be a mistake, and you haven't recently created an account for {0} then you can safely ignore this email.

Verification link: {1}

Good luck and have fun!
The {0} Team.
    """.format(settings["competition_name"], verification_link)

    subject = "{} Account Verification".format(settings["competition_name"])

    verification_message = Message(body=body, recipients=[user['email']], subject=subject)

    bulk = [verification_message]

    if settings["parent_verification_email"] and previous_key is None and user['demo']['age'] == "13-17":
        body = """
        Welcome to {0}!  Thank you for authorizing the participation of your child age 13-17 in {0} and providing your email address as part of the account registration process for your child.  As a reminder, the Terms of Service, Privacy Statement and Competition Rules for {0}.
    
        If you received this email in error because you did not authorize your child’s registration for {0}, you are not the child’s parent or legal guardian, or your child is under age 13, please email us immediately at {2}
        """.format(settings["competition_name"])

        subject = "{} Parent Account Verification".format(settings["competition_name"])
        recipients = [user['demo']['parentemail']]
        parent_email = Message(body=body, recipients=recipients, subject=subject)

        bulk.append(parent_email)

    with mail.connect() as conn:
        for msg in bulk:
            conn.send(msg)


def send_email_invite(gid, email, teacher=False):
    """
    Sends an email registration link that will automatically join into a group. This link will bypass the email filter.
    """

    settings = api.config.get_settings()
    group = api.group.get_group(gid=gid)

    token_value = api.token.set_token({
        "gid": group["gid"],
        "email": email,
        "teacher": teacher
    }, "registration_token")

    registration_link = "{}/#g={}&r={}".\
        format(settings["competition_url"], group["gid"], token_value)

    body = """
You have been invited by the staff of the {1} organization to compete in {0}.
You will need to follow the registration link below to finish the account creation process.

If you believe this to be a mistake you can safely ignore this email.

Registration link: {2}

Good luck!
  The {0} Team.
    """.format(settings["competition_name"], group["name"], registration_link)

    subject = "{} Registration".format(settings["competition_name"])

    message = Message(body=body, recipients=[email], subject=subject)
    mail.send(message)
