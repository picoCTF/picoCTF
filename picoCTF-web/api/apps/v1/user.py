"""Endpoints related to authorization and the current user."""
from flask import jsonify, redirect
from flask_restplus import Namespace, Resource

import api
from api import check_csrf, PicoException, rate_limit, require_login, require_bot

from .schemas import (
    disable_account_req,
    email_verification_req,
    login_req,
    reset_password_confirmation_req,
    reset_password_req,
    update_password_req,
    user_extdata_req,
    user_htb_req,
)

ns = Namespace(
    "user", description="Authentication and information about " + "current user"
)

USERDATA_FILTER = [
    "admin",
    "extdata",
    "completed_minigames",
    "logged_in",
    "teacher",
    "tid",
    "tokens",
    "uid",
    "unlocked_walkthroughs",
    "username",
    "verified",
]


@ns.route("")
class User(Resource):
    """Get the current user or update their extdata."""

    @ns.response(200, "Success")
    def get(self):
        """Get information about the current user."""
        res = {"logged_in": False}
        if api.user.is_logged_in():
            res["logged_in"] = True
            res["score"] = api.stats.get_score(
                tid=api.user.get_user()["tid"], time_weighted=False
            )
            userdata = {
                k: v for k, v in api.user.get_user().items() if k in USERDATA_FILTER
            }
            res.update(userdata)
        return jsonify(res)

    @check_csrf
    @require_login
    @ns.response(200, "Success")
    @ns.response(401, "Not logged in")
    @ns.response(403, "CSRF token invalid")
    @ns.expect(user_extdata_req)
    def patch(self):
        """Update the current user's extdata (other fields not supported)."""
        req = user_extdata_req.parse_args(strict=True)
        api.user.update_extdata(req["extdata"])
        return jsonify({"success": True})


@ns.route("/login")
class LoginResponse(Resource):
    """Log in."""

    @rate_limit(limit=20, duration=15, by_ip=True, allow_bypass=True)
    @ns.response(200, "Success")
    @ns.response(400, "Error parsing request")
    @ns.response(401, "Incorrect username or password")
    @ns.response(403, "Account deleted or not yet verified")
    @ns.response(429, "Too many requests, slow down!")
    @ns.expect(login_req)
    def post(self):
        """Log in."""
        req = login_req.parse_args(strict=False)
        api.user.login(req["username"], req["password"])
        return jsonify({"success": True, "username": req["username"]})


@ns.route("/logout")
class LogoutResponse(Resource):
    """Log out."""

    @require_login
    @ns.response(200, "Success")
    @ns.response(401, "Not logged in")
    def get(self):
        """Log out."""
        api.user.logout()
        return jsonify({"success": True})


@ns.route("/authorize/<string:requested_role>")
class AuthorizationResponse(Resource):
    """
    Determine whether the current user has certain roles.

    Used to handle authorization in nginx.
    """

    @ns.response(200, "User is authorized for the given role")
    @ns.response(401, "User is not authorized for the given role")
    def get(self, requested_role):
        """Get the authorization status for the current user."""
        # Determine authorizations
        authorizations = {
            "anonymous": True,
            "user": False,
            "teacher": False,
            "admin": False,
        }
        if requested_role not in authorizations:
            raise PicoException("Invalid role", 401)

        user = None
        if api.user.is_logged_in():
            authorizations["user"] = True
            user = api.user.get_user()

        if user:
            for role in ["teacher", "admin"]:
                authorizations[role] = user[role]

        if authorizations[requested_role] is True:
            status_code = 200
        else:
            status_code = 401

        res = jsonify(authorizations)
        res.status_code = status_code
        return res


@ns.route("/disable_account")
class DisableAccountResponse(Resource):
    """Disable your user account. Requires password confirmation."""

    @check_csrf
    @require_login
    @ns.response(200, "Success")
    @ns.response(401, "Not logged in")
    @ns.response(403, "CSRF token invalid")
    @ns.response(422, "Provided password is not correct")
    @ns.expect(disable_account_req)
    def post(self):
        """
        Disable your user account. Requires password confirmation.

        Note that this is an irreversable action.
        """
        user = api.user.get_user(include_pw_hash=True)
        req = disable_account_req.parse_args(strict=True)

        if not api.user.confirm_password(req["password"], user["password_hash"]):
            raise PicoException("The provided password is not correct.", 422)
        api.user.disable_account(user["uid"], "Deleted at user's request.")
        api.user.logout()
        return jsonify({"success": True})


@ns.route("/update_password")
class UpdatePasswordResponse(Resource):
    """Update your account password."""

    @check_csrf
    @require_login
    @ns.response(200, "Success")
    @ns.response(400, "Error parsing request")
    @ns.response(401, "Not logged in")
    @ns.response(403, "CSRF token invalid")
    @ns.response(422, "Provided password does not match")
    @ns.expect(update_password_req)
    def post(self):
        """Update your account password."""
        req = update_password_req.parse_args(strict=True)
        # @TODO refactor update_password_request()
        api.user.update_password_request(
            {
                "current-password": req["current_password"],
                "new-password": req["new_password"],
                "new-password-confirmation": req["new_password_confirmation"],
            },
            check_current=True,
        )
        return jsonify({"success": True})


@ns.route("/reset_password")
class ResetPasswordResponse(Resource):
    """Reset a user's password. Requires a password reset token."""

    @rate_limit(limit=2, duration=15, by_ip=True)
    @ns.response(200, "Success")
    @ns.response(400, "Error parsing request")
    @ns.response(422, "Invalid token")
    @ns.response(429, "Too many requests, slow down!")
    @ns.expect(reset_password_confirmation_req)
    def post(self):
        """Reset a user's password. Requires a password reset token."""
        req = reset_password_confirmation_req.parse_args(strict=True)
        api.user.reset_password(
            req["reset_token"], req["new_password"], req["new_password_confirmation"]
        )
        return jsonify({"success": True})


@ns.route("/reset_password/request")
class ResetPasswordRequestResponse(Resource):
    """Request a password reset. Does not require authentication."""

    @rate_limit(limit=2, duration=30, by_ip=True)
    @ns.response(200, "Success")
    @ns.response(400, "Error parsing request")
    @ns.response(404, "Username not found")
    @ns.response(429, "Too many requests, slow down!")
    @ns.expect(reset_password_req)
    def post(self):
        """Request a password reset. Does not require authentication."""
        req = reset_password_req.parse_args(strict=True)
        api.email.request_password_reset(req["username"])
        return jsonify({"success": True})


@ns.route("/verify")
class UserVerificationResponse(Resource):
    """Verify a user's email address."""

    @ns.expect(email_verification_req)
    def get(self):
        """Verify a user's email address."""
        req = email_verification_req.parse_args(strict=True)
        success = api.user.verify_user(req["uid"], req["token"])
        settings = api.config.get_settings()
        if success:
            return redirect(settings["competition_url"] + "/#status=verified")
        else:
            return redirect(settings["competition_url"] + "/#status=verification_error")


@ns.route("/export")
class UserDataExport(Resource):
    """Export all data of the logged in user."""

    @require_login
    def get(self):
        """Export all data of the logged in user."""
        user_data = api.user.get_user()
        submissions = api.submissions.get_submissions(uid=user_data["uid"])
        feedbacks = api.problem_feedback.get_problem_feedback(uid=user_data["uid"])
        return jsonify(
            {"user": user_data, "submissions": submissions, "feedback": feedbacks}
        )


@ns.route("/set_htb_id")
class SetHTBProfile(Resource):
    """Add Hack the Box Profile ID to User data."""

    @check_csrf
    @require_bot
    @ns.response(200, "Success")
    @ns.response(401, "Not logged in")
    @ns.response(403, "CSRF token invalid")
    @ns.response(404, "Username not found")
    @ns.expect(user_htb_req)
    def post(self):
        req = user_htb_req.parse_args(strict=True)
        res = api.user.add_htb_id(req["user_name"], req["htb_id"])
        return jsonify(res)

@ns.route("/get_htb_id/<string:user_name>")
class SetHTBProfile(Resource):
    """Add Hack the Box Profile ID to User data."""

    @check_csrf
    @require_bot
    @ns.response(200, "Success")
    @ns.response(401, "Not logged in")
    @ns.response(403, "CSRF token invalid")
    @ns.response(404, "Username not found")
    def get(self, user_name):
        if user_name == None:
            raise PicoException("Missing user_name", 400)

        res = api.user.get_htb_id(user_name)
        return jsonify(res)
