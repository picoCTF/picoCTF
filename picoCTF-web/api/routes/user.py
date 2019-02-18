import json
import mimetypes
import os.path
from datetime import datetime

import api
from api.annotations import (api_wrapper, block_after_competition,
                             block_before_competition, check_csrf, log_action,
                             require_admin, require_login, require_teacher)
from api.common import safe_fail, WebError, WebSuccess
from flask import (abort, Blueprint, Flask, redirect, render_template, request,
                   send_from_directory, session)

blueprint = Blueprint("user_api", __name__)


@blueprint.route("/authorize/<role>")
def authorize_role(role=None):
    """
    This route is used to ensure sensitive static content is withheld from clients.
    """

    if role == "user" and safe_fail(api.user.get_user):
        return "Client is logged in.", 200
    elif role == "teacher" and safe_fail(api.user.is_teacher):
        return "Client is a teacher.", 200
    elif role == "admin" and safe_fail(api.user.is_admin):
        return "Client is an administrator.", 200
    elif role == "anonymous":
        return "Client is authorized.", 200
    else:
        return "Client is not authorized.", 401


@blueprint.route('/create_simple', methods=['POST'])
@api_wrapper
def create_simple_user_hook():
    settings = api.config.get_settings()

    new_uid = api.user.create_simple_user_request(
        api.common.parse_multi_form(request.form))

    # Only automatically login if we don't have to verify
    if api.user.get_user(uid=new_uid)["verified"]:
        session['uid'] = new_uid

    return WebSuccess("User '{}' registered successfully!".format(
        request.form["username"]))


@blueprint.route('/update_password', methods=['POST'])
@api_wrapper
@check_csrf
@require_login
def update_password_hook():
    api.user.update_password_request(
        api.common.flat_multi(request.form), check_current=True)
    return WebSuccess("Your password has been successfully updated!")


@blueprint.route('/disable_account', methods=['POST'])
@api_wrapper
@check_csrf
@require_login
def disable_account_hook():
    api.user.disable_account_request(
        api.common.flat_multi(request.form), check_current=True)
    return WebSuccess("Your have successfully disabled your account!")


@blueprint.route('/reset_password', methods=['POST'])
@api_wrapper
def reset_password_hook():
    username = request.form.get("username", None)

    api.email.request_password_reset(username)
    return WebSuccess(
        "A password reset link has been sent to the email address provided during registration."
    )


@blueprint.route('/confirm_password_reset', methods=['POST'])
@api_wrapper
def confirm_password_reset_hook():
    password = request.form.get("new-password")
    confirm = request.form.get("new-password-confirmation")
    token_value = request.form.get("reset-token")

    api.email.reset_password(token_value, password, confirm)
    return WebSuccess("Your password has been reset")


@blueprint.route('/verify', methods=['GET'])
# @api_wrapper
def verify_user_hook():
    uid = request.args.get("uid")
    token = request.args.get("token")

    # Needs to be more telling of success
    if api.common.safe_fail(api.user.verify_user, uid, token):
        if api.config.get_settings()["max_team_size"] > 1:
            return redirect("/#team-builder")
        else:
            return redirect("/#status=verified")
    else:
        return redirect("/")


@blueprint.route('/login', methods=['POST'])
@api_wrapper
def login_hook():
    username = request.form.get('username')
    password = request.form.get('password')
    api.auth.login(username, password)
    return WebSuccess(
        message="Successfully logged in as " + username,
        data={
            'teacher': api.user.is_teacher(),
            'admin': api.user.is_admin()
        })


@blueprint.route('/logout', methods=['GET'])
@api_wrapper
def logout_hook():
    if api.auth.is_logged_in():
        api.auth.logout()
        return WebSuccess("Successfully logged out.")
    else:
        return WebError("You do not appear to be logged in.")


@blueprint.route('/status', methods=['GET'])
@api_wrapper
def status_hook():
    settings = api.config.get_settings()
    status = {
        "logged_in":
        api.auth.is_logged_in(),
        "admin":
        api.auth.is_logged_in() and api.user.is_admin(),
        "teacher":
        api.auth.is_logged_in() and api.user.is_teacher(),
        "enable_teachers":
        settings["enable_teachers"],
        "enable_feedback":
        settings["enable_feedback"],
        "enable_captcha":
        settings["captcha"]["enable_captcha"],
        "reCAPTCHA_public_key":
        settings["captcha"]["reCAPTCHA_public_key"],
        "competition_active":
        api.utilities.check_competition_active(),
        "username":
        api.user.get_user()['username'] if api.auth.is_logged_in() else "",
        "tid":
        api.user.get_user()["tid"] if api.auth.is_logged_in() else "",
        "email_verification":
        settings["email"]["email_verification"]
    }

    if api.auth.is_logged_in():
        team = api.user.get_team()
        status["team_name"] = team["team_name"]
        status["score"] = api.stats.get_score(tid=team["tid"])

    return WebSuccess(data=status)


@blueprint.route('/shell_servers', methods=['GET'])
@api_wrapper
@require_login
def shell_servers_hook():
    servers = [{
        "host": server['host'],
        "protocol": server['protocol']
    } for server in api.shell_servers.get_servers()]
    return WebSuccess(data=servers)


@blueprint.route('/extdata', methods=['GET'])
@api_wrapper
@require_login
def get_extdata_hook():
    """
    Return user extdata, or empty JSON object if unset.
    """
    user = api.user.get_user(uid=None)
    return WebSuccess(data=user['extdata'])


@blueprint.route('/extdata', methods=['PUT'])
@api_wrapper
@check_csrf
@require_login
def update_extdata_hook():
    """
    Sets user extdata via HTTP form. Takes in any key-value pairs.
    """
    api.user.update_extdata(api.common.flat_multi(request.form))
    return WebSuccess("Your Extdata has been successfully updated.")
