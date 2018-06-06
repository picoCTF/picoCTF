"""
API functions relating to user management and registration.
"""

import json
import re
import string
import urllib.parse
import urllib.request

import api
import bcrypt
import flask
from api.annotations import log_action
from api.common import (check, InternalException, safe_fail, validate,
                        WebException)
from voluptuous import Length, Required, Schema

_check_email_format = lambda email: re.match(r".+@.+\..{2,}", email) is not None


def _check_username(username):
    return all(
        [c in string.digits + string.ascii_lowercase for c in username.lower()])


def verify_email_in_whitelist(email, whitelist=None):
    """
    Verify that the email address passes the global whitelist if one exists.

    Args:
        email: The email address to verify
    """

    if whitelist is None:
        settings = api.config.get_settings()
        whitelist = settings["email_filter"]

    #Nothing to check against!
    if len(whitelist) == 0:
        return True

    for email_domain in whitelist:
        if re.match(r".*?@{}$".format(email_domain), email) is not None:
            return True

    return False


user_schema = Schema(
    {
        Required('email'):
        check(
            ("Email must be between 5 and 50 characters.",
             [str, Length(min=5, max=50)]),
            ("Your email does not look like an email address.",
             [_check_email_format]),
        ),
        Required('firstname'):
        check(("First Name must be between 1 and 50 characters.",
               [str, Length(min=1, max=50)])),
        Required('lastname'):
        check(("Last Name must be between 1 and 50 characters.",
               [str, Length(min=1, max=50)])),
        Required('country'):
        check(("Please select a country", [str, Length(min=2, max=2)])),
        Required('username'):
        check(("Usernames must be between 3 and 20 characters.",
               [str, Length(min=3, max=20)]),
              ("Usernames must be alphanumeric.", [_check_username]),
              ("This username already exists.",
               [lambda name: safe_fail(get_user, name=name) is None]),
              ("This username conflicts with an existing team.",
               [lambda name: safe_fail(api.team.get_team, name=name) is None])),
        Required('password'):
        check(("Passwords must be between 3 and 20 characters.",
               [str, Length(min=3, max=20)])),
        Required('affiliation'):
        check(("You must specify an affiliation.", [str,
                                                    Length(min=3, max=50)])),
        Required('eligibility'):
        check(("You must specify whether or not your account is eligibile.",
               [str, lambda status: status in ["eligible", "ineligible"]])),
    },
    extra=True)

new_team_schema = Schema(
    {
        Required('team-name-new'):
        check(("The team name must be between 3 and 40 characters.",
               [str, Length(min=3, max=40)]),
              ("A team with that name already exists.",
               [lambda name: safe_fail(api.team.get_team, name=name) is None])),
        Required('team-password-new'):
        check(("Team passphrase must be between 3 and 20 characters.",
               [str, Length(min=3, max=20)])),
    },
    extra=True)

existing_team_schema = Schema({
    Required('team-name-existing'): check(
        ("Existing team names must be between 3 and 50 characters.", [str, Length(min=3, max=50)]),
        ("There is no existing team named that.", [
            lambda name: api.team.get_team(name=name) != None]),
        ("There are too many members on that team for you to join.", [
            lambda name: len(api.team.get_team_uids(name=name, show_disabled=False)) < api.config.get_settings()["max_team_size"]
        ])
    ),
    Required('team-password-existing'):
        check(("Team passwords must be between 3 and 50 characters.", [str, Length(min=3, max=50)]))
}, extra=True)


def hash_password(password):
    """
    Hash plaintext password.

    Args:
        password: plaintext password
    Returns:
        Secure hash of password.
    """

    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(8))


def get_team(uid=None):
    """
    Retrieve the the corresponding team to the user's uid.

    Args:
        uid: user's userid
    Returns:
        The user's team.
    """

    user = get_user(uid=uid)
    return api.team.get_team(tid=user["tid"])


def get_user(name=None, uid=None):
    """
    Retrieve a user based on a property. If the user is logged in,
    it will return that user object.

    Args:
        name: the user's username
        uid: the user's uid
    Returns:
        Returns the corresponding user object or None if it could not be found
    """

    db = api.common.get_conn()

    match = {}

    if uid is not None:
        match.update({'uid': uid})
    elif name is not None:
        match.update({'username': name})
    elif api.auth.is_logged_in():
        match.update({'uid': api.auth.get_uid()})
    else:
        raise InternalException("Uid or name must be specified for get_user")

    user = db.users.find_one(match)

    if user is None:
        raise InternalException("User does not exist")

    return user


def create_user(username,
                firstname,
                lastname,
                email,
                password_hash,
                tid,
                teacher=False,
                country="US",
                admin=False,
                verified=False):
    """
    This inserts a user directly into the database. It assumes all data is valid.

    Args:
        username: user's username
        firstname: user's first name
        lastname: user's last name
        email: user's email
        password_hash: a hash of the user's password
        tid: the team id to join
        teacher: whether this account is a teacher
    Returns:
        Returns the uid of the newly created user
    """

    db = api.common.get_conn()
    settings = api.config.get_settings()
    uid = api.common.token()

    if safe_fail(get_user, name=username) is not None:
        raise InternalException("User already exists!")

    max_team_size = api.config.get_settings()["max_team_size"]

    updated_team = db.teams.find_and_modify(
        query={
            "tid": tid,
            "size": {
                "$lt": max_team_size
            }
        },
        update={"$inc": {
            "size": 1
        }},
        new=True)

    if not updated_team:
        raise InternalException("There are too many users on this team!")

    #All teachers are admins.
    if admin or db.users.count() == 0:
        admin = True
        teacher = True

    user = {
        'uid': uid,
        'firstname': firstname,
        'lastname': lastname,
        'username': username,
        'email': email,
        'password_hash': password_hash,
        'tid': tid,
        'teacher': teacher,
        'admin': admin,
        'disabled': False,
        'country': country,
        'verified': not settings["email"]["email_verification"] or verified,
        'extdata': {},
    }

    db.users.insert(user)

    if settings["email"]["email_verification"] and not user["verified"]:
        api.email.send_user_verification_email(username)

    return uid


def get_all_users(show_teachers=False):
    """
    Finds all the users in the database

    Args:
        show_teachers: whether or not to include teachers in the response
    Returns:
        Returns the uid, username, and email of all users.
    """

    db = api.common.get_conn()

    match = {}
    projection = {"uid": 1, "username": 1, "email": 1, "tid": 1}

    if not show_teachers:
        match.update({"teacher": False})
        projection.update({"teacher": 1})

    return list(db.users.find(match, projection))


def _validate_captcha(data):
    """
    Validates a captcha with google's reCAPTCHA.

    Args:
        data: the posted form data
    """

    settings = api.config.get_settings()["captcha"]

    post_data = urllib.parse.urlencode({
        "secret":
        api.config.reCAPTCHA_private_key,
        "response":
        data["g-recaptcha-response"],
        "remoteip":
        flask.request.remote_addr
    }).encode("utf-8")

    request = urllib.request.Request(
        api.config.captcha_url, post_data, method='POST')
    response = urllib.request.urlopen(request).read().decode("utf-8")
    parsed_response = json.loads(response)
    return parsed_response['success'] == True


@log_action
def create_simple_user_request(params):
    """
    Registers a new user and creates a team for them automatically. Validates all fields.
    Assume arguments to be specified in a dict.

    Args:
        username: user's username
        password: user's password
        firstname: user's first name
        lastname: user's first name
        email: user's email
        eligibile: "eligibile" or "ineligibile"
        affiliation: user's affiliation
        gid: group registration
        rid: registration id
    """

    params["country"] = "US"
    validate(user_schema, params)

    whitelist = None

    if params.get("gid", None):
        group = api.group.get_group(gid=params["gid"])
        group_settings = api.group.get_group_settings(gid=group["gid"])

        #Force affiliation
        params["affiliation"] = group["name"]

        whitelist = group_settings["email_filter"]

    user_is_teacher = False
    user_was_invited = False

    if params.get("rid", None):
        key = api.token.find_key_by_token("registration_token", params["rid"])

        if params.get("gid") != key["gid"]:
            raise WebException(
                "Registration token group and supplied gid do not match.")

        if params["email"] != key["email"]:
            raise WebException(
                "Registration token email does not match the supplied one.")

        user_is_teacher = key["teacher"]
        user_was_invited = True

        api.token.delete_token(key, "registration_token")
    else:
        if not verify_email_in_whitelist(params["email"], whitelist):
            raise WebException(
                "Your email does not belong to the whitelist. Please see the registration form for details."
            )

    if api.config.get_settings(
    )["captcha"]["enable_captcha"] and not _validate_captcha(params):
        raise WebException("Incorrect captcha!")

    team_params = {
        "team_name": params["username"],
        "password": api.common.token(),
        "eligible": params["eligibility"] == "eligible",
        "affiliation": params["affiliation"]
    }

    tid = api.team.create_team(team_params)

    if tid is None:
        raise InternalException("Failed to create new team")

    team = api.team.get_team(tid=tid)

    # Create new user
    uid = create_user(
        params["username"],
        params["firstname"],
        params["lastname"],
        params["email"],
        hash_password(params["password"]),
        team["tid"],
        country=params["country"],
        teacher=user_is_teacher,
        verified=user_was_invited)

    if uid is None:
        raise InternalException("There was an error during registration.")

    # Join group after everything else has succeeded
    if params.get("gid", None):
        api.group.join_group(
            params["gid"], team["tid"], teacher=user_is_teacher)

    return uid


def is_teacher(uid=None):
    """
    Determines if a user is a teacher.

    Args:
        uid: user's uid
    Returns:
        True if the user is a teacher, False otherwise
    """

    user = get_user(uid=uid)
    return user.get('teacher', False)


def is_admin(uid=None):
    """
    Determines if a user is an admin.

    Args:
        uid: user's uid
    Returns:
        True if the user is an admin, False otherwise
    """

    user = get_user(uid=uid)
    return user.get('admin', False)


def verify_user(uid, token_value):
    """
    Verify an unverified user account. Link should have been sent to the user's email.

    Args:
        uid: the user id
        token_value: the verification token value
    Returns:
        True if successful verification based on the (uid, token_value)
    """

    db = api.common.get_conn()

    if uid is None:
        raise InternalException("You must specify a uid.")

    token_user = api.token.find_key_by_token("email_verification", token_value)

    if token_user["uid"] == uid:
        db.users.find_and_modify({"uid": uid}, {"$set": {"verified": True}})
        api.token.delete_token({"uid": uid}, "email_verification")
        return True
    else:
        raise InternalException("This is not a valid token for your user.")


@log_action
def update_password_request(params, uid=None, check_current=False):
    """
    Update account password.
    Assumes args are keys in params.

    Args:
        uid: uid to reset
        check_current: whether to ensure that current-password is correct
        params:
            current-password: the users current password
            new-password: the new password
            new-password-confirmation: confirmation of password
    """

    user = get_user(uid=uid)

    if check_current and not api.auth.confirm_password(
            params["current-password"], user['password_hash']):
        raise WebException("Your current password is incorrect.")

    if params["new-password"] != params["new-password-confirmation"]:
        raise WebException("Your passwords do not match.")

    if len(params["new-password"]) == 0:
        raise WebException("Your password cannot be empty.")

    update_password(user['uid'], params["new-password"])


def update_password(uid, password):
    """
    Updates an account's password.

    Args:
        uid: user's uid.
        password: the new user password.
    """

    db = api.common.get_conn()
    db.users.update({
        'uid': uid
    }, {'$set': {
        'password_hash': hash_password(password)
    }})


def disable_account(uid):
    """
    Disables a user account. They will no longer be able to login and do not count
    towards a team's maximum size limit.

    Args:
        uid: user's uid
    """

    db = api.common.get_conn()
    result = db.users.update({
        "uid": uid,
        "disabled": False
    }, {"$set": {
        "disabled": True
    }})

    tid = api.user.get_team(uid=uid)["tid"]

    # Making certain that we have actually made a change.
    # result["n"] refers to how many documents have been updated.
    if result["n"] == 1:
        db.teams.find_and_modify(
            query={
                "tid": tid,
                "size": {
                    "$gt": 0
                }
            },
            update={"$inc": {
                "size": -1
            }},
            new=True)


@log_action
def disable_account_request(params, uid=None, check_current=False):
    """
    Disable user account so they can't login or consume space on a team.
    Assumes args are keys in params.

    Args:
        uid: uid to reset
        check_current: whether to ensure that current-password is correct
        params:
            current-password: the users current password
    """

    user = get_user(uid=uid)

    if check_current and not api.auth.confirm_password(
            params["current-password"], user['password_hash']):
        raise WebException("Your current password is incorrect.")
    disable_account(user['uid'])

    api.auth.logout()


def update_extdata(params):
    """
    Update user extdata.
    Assumes args are keys in params.

    Args:
        params:
            (any)
    """
    user = get_user(uid=None)
    db = api.common.get_conn()
    params.pop('token', None)
    db.users.update_one({'uid': user['uid']}, {'$set': {'extdata': params}})
