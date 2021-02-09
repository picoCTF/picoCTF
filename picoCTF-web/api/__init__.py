"""Configures the Flask app."""

import inspect
import logging
import traceback

from flask import Flask, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix

# these have to come first to avoid circular import issues
from api.common import check, PicoException, validate  # noqa
from api.config import block_after_competition, block_before_competition  # noqa
from api.logger import log_action  # noqa
from api.user import (
    check_csrf,
    rate_limit,
    require_admin,  # noqa
    require_login,
    require_teacher,
    require_bot,
)

import api.achievement
import api.bundles
import api.cache
import api.common
import api.config
import api.db
import api.email
import api.group
import api.logger
import api.problem
import api.problem_feedback
import api.scoreboards
import api.shell_servers
import api.stats
import api.submissions
import api.team
import api.token
import api.user
from api.apps.v1 import blueprint as v1_blueprint

log = logging.getLogger(__name__)


def get_origin_logger(exception):
    """Get the logger for the module where an exception was raised."""
    try:
        origin = inspect.getmodule(inspect.trace()[-1]).__name__
        origin_logger = logging.getLogger(origin)
        return origin_logger
    except Exception as e:
        log.error(
            "Failed to get origin logger for exception: "
            + str(e)
            + " - returning fallback logger"
        )
        return logging.getLogger("origin_fallback")


def create_app(config=None):
    """
    Configure and create the Flask app via factory function.

    Args:
        config (optional): dict of app.config settings to override
    """
    if config is None:
        config = {}
    app = Flask(__name__, static_url_path="/")
    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Load default Flask settings
    app.config.from_pyfile("default_settings.py")
    # Override defaults with settings file passed in environment variable
    app.config.from_envvar("APP_SETTINGS_FILE", silent=True)
    # If any config settings specified, set them
    for k, v in config.items():
        app.config[k] = v

    # Add any new runtime settings to DB
    with app.app_context():
        api.config.merge_new_settings()

    # Register blueprints
    app.register_blueprint(v1_blueprint, url_prefix="/api/v1")

    # Report all validation errors (RequestParser-specific setting)
    app.config["BUNDLE_ERRORS"] = True

    # Register error handlers
    @app.errorhandler(PicoException)
    def handle_pico_exception(e):
        """Handle exceptions."""
        response = jsonify(e.to_dict())
        response.status_code = e.status_code
        return response

    @app.errorhandler(404)
    def page_not_found(e):
        response = jsonify({"message": "API endpoint not found"})
        response.status_code = 404
        return response

    if not app.debug:

        @app.errorhandler(Exception)
        def handle_generic_exception(e):
            # @TODO log picoexceptions also?
            get_origin_logger(e).error(traceback.format_exc())
            response = jsonify(
                {
                    "message": "An internal error occurred. "
                    + "Please contact an administrator."
                }
            )
            response.status_code = 500
            return response

    # Configure logging
    with app.app_context():
        api.logger.setup_logs({"verbose": 2})

    # Register a post-request function
    @app.after_request
    def after_request(response):
        response.headers.add(
            "Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, *")
        response.headers.add("Cache-Control", "no-cache")
        response.headers.add("Cache-Control", "no-store")
        with app.app_context():
            if app.debug:
                response.headers.add("Access-Control-Allow-Origin", "*")
        if api.user.is_logged_in():
            # Flask 1.0+ bug loads config SESSION_COOKIE_DOMAIN
            # correctly as None but later converts it to bool false.
            domain = app.config["SESSION_COOKIE_DOMAIN"]
            if not domain:
                domain = None

            # Set the CSRF token cookie
            if "token" not in session:
                csrf_token = api.common.token()
                session["token"] = csrf_token
            response.set_cookie("token", session["token"], domain=domain)

        return response

    return app
