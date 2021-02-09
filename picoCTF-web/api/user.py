"""User management and registration module."""

import json
import re
import urllib.parse
import urllib.request
from functools import wraps

import bcrypt
import flask
from flask import current_app, request, session
from pymongo.collation import Collation, CollationStrength

import api
from api import cache, log_action, PicoException


def is_blacklisted_username(username):
    """
    Whether the username is blacklisted.

    Args:
        username: the username to check
    """
    settings = api.config.get_settings()
    return username in settings.get(
        "username_blacklist", api.config.default_settings["username_blacklist"]
    )


def verify_email_in_whitelist(email, whitelist=None):
    """
    Verify that the email address passes the global whitelist if one exists.

    Args:
        email: The email address to verify
    """
    if whitelist is None:
        settings = api.config.get_settings()
        whitelist = settings["email_filter"]

    # Nothing to check against!
    if len(whitelist) == 0:
        return True

    for email_domain in whitelist:
        if re.match(r"^[^@]+@{}$".format(email_domain), email) is not None:
            return True

    return False


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


def get_user(name=None, uid=None, include_pw_hash=False):
    """
    Retrieve a user based on a property, or the current user, if logged in.

    Kwargs:
        name: the user's username
        uid: the user's uid
        include_pw_hash: include password hash in the dict
    Returns:
        Returns the corresponding user object or None if it could not be found
    """
    db = api.db.get_conn()

    projection = {"_id": 0}
    if not include_pw_hash:
        projection["password_hash"] = 0

    if uid is not None:
        return db.users.find_one({"uid": uid}, projection)
    elif name is not None:
        return db.users.find_one(
            {"username": name},
            projection,
            collation=Collation(locale="en", strength=CollationStrength.PRIMARY),
        )
    elif api.user.is_logged_in():
        return db.users.find_one({"uid": session["uid"]}, projection)
    else:
        raise PicoException("Could not retrieve user - not logged in", 401)


def get_users(email=None, parentemail=None, username=None, include_pw_hash=False):
    """
    Retrieve all users matching the given property.

    Kwargs:
        email: the user's email address
        parentemail: the user's parent email address
        include_pw_hash: include password hash in the dict
    Returns:
        Returns the corresponding user objects or None if it could not be found
    """
    db = api.db.get_conn()

    match = {}
    projection = {"_id": 0}
    if not include_pw_hash:
        projection["password_hash"] = 0

    if email is not None:
        match.update({"email": re.compile(email, re.IGNORECASE)})
    elif parentemail is not None:
        match.update({"demo.parentemail": re.compile(parentemail, re.IGNORECASE)})
    elif username is not None:
        match.update({"username": re.compile(username, re.IGNORECASE)})
    else:
        raise PicoException("Could not retrieve user - no argument provided", 400)

    return list(db.users.find(match, projection).limit(50))


def get_all_users():
    """
    Find all users in the database.

    Returns:
        Returns all user dicts.

    """
    db = api.db.get_conn()
    return list(db.users.find({}, {"_id": 0, "password_hash": 0}))


def _validate_captcha(data):
    """
    Validate a captcha with google's reCAPTCHA.

    Args:
        data: the posted form data
    """
    settings = api.config.get_settings()["captcha"]

    post_data = urllib.parse.urlencode(
        {
            "secret": settings["reCAPTCHA_private_key"],
            "response": data["g-recaptcha-response"],
            "remoteip": flask.request.remote_addr,
        }
    ).encode("utf-8")

    request = urllib.request.Request(settings["captcha_url"], post_data, method="POST")
    response = urllib.request.urlopen(request).read().decode("utf-8")
    parsed_response = json.loads(response)
    return parsed_response["success"] is True


@log_action(dont_log=["params.password"])
def add_user(params, batch_registration=False):
    """
    Register a new user and creates a team for them automatically.

    Assume arguments to be specified in a dict.

    Args:
        params:
            username: user's username
            password: user's password
            firstname: user's first name
            lastname: user's first name
            email: user's email
            country: 2-digit country code
            affiliation: user's affiliation
            usertype: "student", "teacher" or other
            demo: arbitrary dict of demographic data
            gid (optional): group registration
            rid (optional): registration id
        batch_registration: Allows bypass of recaptcha in class batch regs
    """
    # Make sure the username is unique
    db = api.db.get_conn()
    if is_blacklisted_username(params["username"]) or db.users.find_one(
        {"username": params["username"]},
        collation=Collation(locale="en", strength=CollationStrength.PRIMARY),
    ):
        raise PicoException("There is already a user with this username.", 409)
    if db.teams.find_one(
        {"team_name": params["username"]},
        collation=Collation(locale="en", strength=CollationStrength.PRIMARY),
    ):
        raise PicoException("There is already a team with this username.", 409)

    # If gid is specified, force affiliation to that team's name
    email_whitelist = None
    if params.get("gid", None):
        group = api.group.get_group(gid=params["gid"])
        group_settings = api.group.get_group_settings(gid=group["gid"])
        params["affiliation"] = group["name"]
        email_whitelist = group_settings["email_filter"]

    # If rid is specified and gid and email match,
    # get teacher status from registration token.
    # Additionally, invited users are automatically validated.
    user_is_teacher = params["usertype"] == "teacher"
    user_was_invited = False
    join_group_as_teacher = False
    if params.get("rid", None):
        key = api.token.find_key_by_token("registration_token", params["rid"])
        if params.get("gid") != key["gid"]:
            raise PicoException(
                "Registration token group and supplied gid do not match."
            )
        if params["email"] != key["email"]:
            raise PicoException(
                "Registration token email does not match the supplied one."
            )
        join_group_as_teacher = key["teacher"]
        user_was_invited = True
        api.token.delete_token(key, "registration_token")

    # If not invited, validate the user's email against the whitelist
    else:
        if not verify_email_in_whitelist(params["email"], email_whitelist):
            raise PicoException(
                "Your email does not belong to the whitelist. "
                + "Please see the registration form for details."
            )

    # If CAPTCHAs are enabled, validate the submission if not batch registration
    if (
        api.config.get_settings()["captcha"]["enable_captcha"]
        and not batch_registration
        and not _validate_captcha(params)
    ):
        raise PicoException("Incorrect captcha!")

    # Create a team for the new user and set its count to 1
    tid = api.team.create_team(
        {
            "team_name": params["username"],
            "password": api.common.hash_password("-"),
            "affiliation": params["affiliation"],
        }
    )
    db.teams.update_one({"tid": tid}, {"$set": {"size": 1}})

    # The first registered user automatically becomes an admin
    user_is_admin = False
    if db.users.count() == 0:
        user_is_admin = True
        user_is_teacher = True

    # Insert the new user in the DB
    uid = api.common.token()
    settings = api.config.get_settings()
    user = {
        "uid": uid,
        "firstname": params["firstname"],
        "lastname": params["lastname"],
        "username": params["username"],
        "email": params["email"],
        "password_hash": api.common.hash_password(params["password"]),
        "tid": tid,
        "usertype": params["usertype"],
        "country": params["country"],
        "demo": params["demo"],
        "teacher": user_is_teacher,
        "admin": user_is_admin,
        "challenge": False,
        "disabled": False,
        "verified": (not settings["email"]["email_verification"] or user_was_invited),
        "extdata": {},
        "completed_minigames": [],
        "unlocked_walkthroughs": [],
        "tokens": 0,
    }
    db.users.insert_one(user)

    # Determine the user team's initial eligibilities
    initial_eligibilities = [
        scoreboard["sid"]
        for scoreboard in api.scoreboards.get_all_scoreboards()
        if api.scoreboards.is_eligible(user, scoreboard)
    ]
    db.teams.find_one_and_update(
        {"tid": tid}, {"$set": {"eligibilities": initial_eligibilities}}
    )

    # If gid was specified, add the newly created team to the group
    if params.get("gid", None):
        api.group.join_group(params["gid"], tid, teacher=join_group_as_teacher)

    # If email verification is enabled and user wasn't invited, send
    # validation email
    if settings["email"]["email_verification"] and not user_was_invited:
        api.email.send_user_verification_email(params["username"])

    return uid


def is_teacher(uid=None):
    """
    Determine if a user is a teacher.

    Args:
        uid: user's uid
    Returns:
        True if the user is a teacher, False otherwise
    """
    user = get_user(uid=uid)
    return user.get("teacher", False)


def verify_user(uid, token_value):
    """
    Verify the current user's account.

    Link should have been sent to the user's email.

    Args:
        token_value: the verification token value
    Returns:
        True if successful verification based on the (uid, token_value)
        False if token is not valid for the current user
    Raises:
        PicoException if user is not logged in
    """
    db = api.db.get_conn()

    token_user = api.token.find_key_by_token("email_verification", token_value)
    if token_user is None:
        return False
    current_user = api.user.get_user(uid=uid)

    if token_user["uid"] == current_user["uid"]:
        db.users.find_one_and_update(
            {"uid": current_user["uid"]}, {"$set": {"verified": True}}
        )
        api.token.delete_token({"uid": current_user["uid"]}, "email_verification")
        return True
    else:
        return False


@log_action(dont_log=["params.current-password",
                      "params.new-password",
                      "params.new-password-confirmation"])
def update_password_request(params, uid=None, check_current=False):
    """
    Update account password.

    Assumes args are keys in params.

    Args:
        uid: uid to reset
        check_current: whether to ensure that current-password is correct
        params (dict):
            current-password: the users current password
            new-password: the new password
            new-password-confirmation: confirmation of password
    """
    user = get_user(uid=uid, include_pw_hash=True)

    if check_current and not api.user.confirm_password(
        params["current-password"], user["password_hash"]
    ):
        raise PicoException("Your current password is incorrect.", 422)

    if params["new-password"] != params["new-password-confirmation"]:
        raise PicoException("Your passwords do not match.", 422)

    db = api.db.get_conn()
    db.users.update(
        {"uid": user["uid"]},
        {"$set": {"password_hash": api.common.hash_password(params["new-password"])}},
    )


@log_action
def disable_account(uid, disable_reason=None):
    """
    Note: The original disable account has now been updated to perform delete account instead.

    Disables a user account.

    Disabled user accounts can't login or consume space on a team.

    Args:
        uid: ID of the user to disable
        disable_reason (optional): Reason to inform user about in email
    """
    if disable_reason is None:
        disable_reason = "Not specified"

    db = api.db.get_conn()
    user = api.user.get_user(uid=uid)
    api.email.send_deletion_notification(
        user["username"], user["email"], disable_reason
    )

    db.users.find_one_and_update(
        {"uid": uid, "disabled": False},
        {
            "$set": {
                "disabled": True,
                "firstname": "",
                "lastname": "",
                "email": "",
                "country": "",
                "demo": {},
                "disable_reason": disable_reason,
            }
        },
    )

    # Drop them from their team
    former_tid = api.user.get_team(uid=uid)["tid"]
    db.teams.find_one_and_update(
        {"tid": former_tid, "size": {"$gt": 0}}, {"$inc": {"size": -1}}
    )

    # Drop empty team from groups
    former_team = db.teams.find_one({"tid": former_tid})
    if former_team["size"] == 0:
        groups = api.team.get_groups(tid=former_tid)
        for group in groups:
            api.group.leave_group(gid=group["gid"], tid=former_tid)

    # Clean up cache
    cache.invalidate(api.team.get_groups, former_tid)
    cache.invalidate(api.stats.get_score, former_tid)
    cache.invalidate(api.stats.get_score, uid)
    cache.invalidate(api.problem.get_unlocked_pids, former_tid)
    cache.invalidate(
        api.problem.get_solved_problems, tid=former_tid, uid=uid, category=None
    )
    cache.invalidate(
        api.problem.get_solved_problems, tid=former_tid, uid=None, category=None
    )
    cache.invalidate(api.problem.get_solved_problems, tid=former_tid, uid=uid)
    cache.invalidate(api.problem.get_solved_problems, tid=former_tid)
    cache.invalidate(api.problem.get_solved_problems, uid=uid)
    cache.invalidate(api.stats.get_score_progression, tid=former_tid, category=None)
    cache.invalidate(api.stats.get_score_progression, tid=former_tid)


def update_extdata(params):
    """
    Update user extdata.

    Assumes args are keys in params.

    Args:
        params:
            (any)
    """
    user = get_user(uid=None)
    db = api.db.get_conn()
    db.users.update_one({"uid": user["uid"]}, {"$set": {"extdata": params}})

def reset_password(token_value, password, confirm_password):
    """
    Perform the password update operation.

    Gets a token and new password from a submitted form, if the token is found
    in a team object in the database the new password is hashed and set,
    the token is then removed and an appropriate response is returned.

    Args:
        token_value: the password reset token
        password: the password to set
        confirm_password: the same password again

    Raises:
        PicoException if invalid password reset token is given
    """
    user = api.token.find_key_by_token("password_reset", token_value)
    if user is None:
        raise PicoException("Invalid password reset token", 422)
    api.user.update_password_request(
        {"new-password": password, "new-password-confirmation": confirm_password},
        uid=user["uid"],
    )

    api.token.delete_token({"uid": user["uid"]}, "password_reset")


def confirm_password(attempt, password_hash):
    """
    Verify the password attempt.

    Args:
        attempt: the password attempt
        password_hash: the real password hash
    """
    return bcrypt.hashpw(attempt.encode("utf-8"), password_hash) == password_hash


@log_action(dont_log=["password"])
def login(username, password):
    """Authenticate a user."""
    user = get_user(name=username, include_pw_hash=True)
    if user is None:
        raise PicoException("Incorrect username.", 401)

    if user["disabled"]:
        raise PicoException("This account has been deleted.", 403)

    if not user["verified"]:
        api.email.send_user_verification_email(username)
        raise PicoException(
            "This account has not been verified yet. An additional email has been sent to {}.".format(
                user["email"]
            ),
            403,
        )

    if confirm_password(password, user["password_hash"]):
        session["uid"] = user["uid"]
        session.permanent = True
    else:
        raise PicoException("Incorrect password", 401)


@log_action
def logout():
    """Clear the session."""
    session.clear()


def is_logged_in():
    """
    Check if the user is currently logged in.

    Returns:
        True if the user is logged in, false otherwise.

    """
    logged_in = "uid" in session
    if logged_in:
        user = api.user.get_user(uid=session["uid"])
        if not user or (user.get("disabled", False) is True):
            logout()
            return False
    return logged_in


def require_login(f):
    """Wrap routing functions that require a user to be logged in."""

    @wraps(f)
    def wrapper(*args, **kwds):
        if not api.user.is_logged_in():
            raise PicoException("You must be logged in", 401)
        return f(*args, **kwds)

    return wrapper


def require_teacher(f):
    """Wrap routing functions that require a user to be a teacher."""

    @require_login
    @wraps(f)
    def wrapper(*args, **kwds):
        if not api.user.get_user().get("teacher", False):
            raise PicoException(
                "You do not have permission to access this resource", 403
            )
        return f(*args, **kwds)

    return wrapper


def require_admin(f):
    """Wrap routing functions that require a user to be an admin."""

    @require_login
    @wraps(f)
    def wrapper(*args, **kwds):
        if not api.user.get_user().get("admin", False):
            raise PicoException(
                "You do not have permission to access this resource", 403
            )
        return f(*args, **kwds)

    return wrapper

def require_bot(f):
    """
    Wrap routing functions that require a user to be a challenge.

    This allows challenges to use the API to query user data

    Setting a user as a Challenge Bot is currently done manually

    TODO:
    Provide admin user ability to add a user as a Challenge Bot
    """

    @require_login
    @wraps(f)
    def wrapper(*args, **kwds):
        if not api.user.get_user().get("challenge", False):
            raise PicoException(
                "You do not have permission to access this resource", 403
            )
        return f(*args, **kwds)

    return wrapper

def check_csrf(f):
    """Wrap routing functions that require a CSRF token."""

    @wraps(f)
    @require_login
    def wrapper(*args, **kwds):
        if "token" not in session:
            raise PicoException(
                "Internal server error",
                data={"debug": "CSRF token not found in session"},
            )
        submitted_token = request.headers.get("X-CSRF-Token", None)
        if submitted_token is None:
            raise PicoException("CSRF token not included in request", 403)
        if session["token"] != submitted_token:
            raise PicoException("CSRF token is not correct", 403)
        return f(*args, **kwds)

    return wrapper


def rate_limit(limit=5, duration=60, by_ip=False, allow_bypass=False):
    """
    Limits requests per user or ip to specified limit threshold
    with lingering duration/expiry (as opposed to rolling interval).
    Note that non-user IP limits should be more generous given shared IPs
    likely in school networks.

    Does not use Walrus rate_limit to avoid having to instantiate new instance
    per rate-limit target.
    :param limit: number of requests allowed before limit is enforced
    :param duration: expiration of last request before limit is reset
    :param by_ip: force keying by ip. Note that requests out of user context
                  default to ip-based key
    :param allow_bypass: allow inclusion of bypass secret in HTTP header
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            settings = api.config.get_settings()
            if not settings.get("enable_rate_limiting", True):
                return f(*args, **kwargs)
            app_config = current_app.config
            if allow_bypass or app_config.get("TESTING", False):
                bypass_header = request.headers.get("Limit-Bypass")
                if bypass_header == app_config["RATE_LIMIT_BYPASS_KEY"]:
                    return f(*args, **kwargs)

            key_id = request.remote_addr

            if is_logged_in():
                current_user = get_user()
                # Bypass admin
                if current_user.get("admin", False):
                    return f(*args, **kwargs)
                if not by_ip:
                    key_id = current_user["uid"]

            _db = cache.get_conn()
            key = "rate_limit:{}:{}".format(request.path, key_id)
            # Avoid race conditions of setting (get-value + 1)
            _db.incr(key)
            _db.expire(key, duration)
            count = int(_db.get(key))
            if count is not None and count <= limit:
                return f(*args, **kwargs)
            else:
                limit_msg = (
                    "Too many requests, slow down! "
                    "Limit: {}, {}s duration".format(limit, duration)
                )
                raise PicoException(limit_msg, 429)

        return wrapper

    return decorator


def can_leave_team(uid):
    """Determine whether a user is eligible to leave their current team."""
    current_user = get_user(uid=uid)
    current_team = api.team.get_team(current_user["tid"])
    if current_team["team_name"] == current_user["username"]:
        return False
    if current_team["creator"] == uid and current_team["size"] != 1:
        return False
    if len(api.submissions.get_submissions(uid=uid)) > 0:
        return False
    return True

@log_action
def add_htb_id(user_name, htb_id):
    """
    Note: This could be done with def update_extdata, however
    update_extdata looks up the logged in user. This request
    is being performed by a challenge at the request of a user,
    so the user lookup there would fail.

    Associate a users Hack the Box ID with their User data.

    Args:
        user_name: the user who's profile is updated
        htb_id: the HTB id for the user
    """
    user = get_user(name=user_name)

    if not user:
        raise PicoException("Could not find user", 400)

    if "htb_id" in user:
        raise PicoException("HTB ID already set", 409)

    users = get_all_users()
    for u in users:
        if "htb_id" in u:
            if htb_id == u["htb_id"]:
                raise PicoException("Another User has this HTB ID already", 409)

    db = api.db.get_conn()
    db.users.update_one({"uid": user["uid"]}, {"$set": {"htb_id": htb_id}})

    return {"success": True}

def get_htb_id(user_name):
    """
    Get a user's HTB ID

    Args:
        user_name: the user to find
    """
    user = get_user(name=user_name)

    if not user:
        raise PicoException("Could not find user", 400)

    if "htb_id" not in user:
        raise PicoException("Missing HTB ID", 409)

    return {"success": True, "htb_id": user["htb_id"]}
