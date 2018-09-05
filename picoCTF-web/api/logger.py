"""
Manage loggers for the api.
"""

import logging
import logging.handlers
import time
from datetime import datetime
from sys import stdout

import api
from bson import json_util
from flask import logging as flask_logging
from flask import has_request_context, request

critical_error_timeout = 600
log = logging.getLogger(__name__)


class StatsHandler(logging.StreamHandler):
    """
    Logs statistical information into the mongodb.
    """

    time_format = "%H:%M:%S %Y-%m-%d"

    action_parsers = {
        "api.user.create_user_request":
            lambda params, result=None: {
                "username": params["username"]
            },
        "api.achievement.process_achievement":
            lambda aid, data, result=None: {
                "aid": aid,
                "success": result[0]
            },
        "api.autogen.grade_problem_instance":
            lambda pid, tid, key, result=None: {
                "pid": pid,
                "key": key,
                "correct": result["correct"]
            },
        "api.group.create_group":
            lambda uid, group_name, result=None: {
                "name": group_name,
                "owner": uid
            },
        "api.group.join_group":
            lambda gid, tid, teacher=False, result=None: {
                "gid": gid,
                "tid": tid
            },
        "api.group.leave_group":
            lambda gid, tid, result=None: {
                "gid": gid,
                "tid": tid
            },
        "api.group.delete_group":
            lambda gid, result=None: {
                "gid": gid
            },
        "api.problem.submit_key":
            lambda tid, pid, key, method, uid=None, ip=None, result=None: {
                "pid": pid,
                "key": key,
                "method": method,
                "success": result["correct"]
            },
        "api.problem_feedback.add_problem_feedback":
            lambda pid, uid, feedback, result=None: {
                "pid": pid,
                "feedback": feedback
            },
        "api.user.update_password_request":
            lambda params, uid=None, check_current=False, result=None: {},
        "api.email.request_password_reset":
            lambda username, result=None: {},
        "api.team.create_team":
            lambda params, result=None: params,
        "api.app.hint":
            lambda pid, source, result=None: {"pid": pid, "source": source}
    }

    def __init__(self):

        logging.StreamHandler.__init__(self)

    def emit(self, record):
        """
        Store record into the db.
        """

        information = get_request_information()

        result = record.msg

        if type(result) == dict:

            information.update({
                "event": result["name"],
                "time": datetime.now()
            })

            information["pass"] = True
            information["action"] = {}

            if "exception" in result:

                information["action"]["exception"] = result["exception"]
                information["pass"] = False

            elif result["name"] in self.action_parsers:
                action_parser = self.action_parsers[result["name"]]

                result["kwargs"]["result"] = result["result"]
                action_result = action_parser(*result["args"],
                                              **result["kwargs"])

                information["action"].update(action_result)

            api.common.get_conn().statistics.insert(information)


class ExceptionHandler(logging.StreamHandler):
    """
    Logs exceptions into mongodb.
    """

    def __init__(self):

        logging.StreamHandler.__init__(self)

    def emit(self, record):
        """
        Store record into the db.
        """

        information = get_request_information()

        information.update({
            "event": "exception",
            "time": datetime.now(),
            "trace": record.msg,
            "visible": True
        })

        api.common.get_conn().exceptions.insert(information)


class SevereHandler(logging.handlers.SMTPHandler):

    messages = {}

    def __init__(self):
        settings = api.config.get_settings()
        logging.handlers.SMTPHandler.__init__(
            self,
            mailhost=settings["email"]["smtp_url"],
            fromaddr=settings["email"]["from_addr"],
            toaddrs=settings["logging"]["admin_emails"],
            subject="Critical Error in {}".format(settings["competition_name"]),
            credentials=(settings["email"]["email_username"],
                         settings["email"]["email_password"]),
            secure=())

    def emit(self, record):
        """
        Don't excessively emit the same message.
        """

        last_time = self.messages.get(record.msg, None)
        if last_time is None or time.time(
        ) - last_time > api.config.get_settings()["critical_error_timeout"]:
            super(SevereHandler, self).emit(record)
            self.messages[record.msg] = time.time()


def set_level(name, level):
    """
    Get and set log level of a given logger.

    Args:
        name: name of logger
        level: level to set
    """

    logger = use(name)
    if logger:
        logger.setLevel(level)


def use(name):
    """
    Alias for logging.getLogger(name)

    Args:
        name: The name of the logger.
    Returns:
        The logging object.
    """

    return logging.getLogger(name)


def get_request_information():
    """
    Returns a dictionary of contextual information about the user at the time of logging.

    Returns:
        The dictionary.
    """

    information = {}

    if has_request_context():
        information["request"] = {
            "api_endpoint_method": request.method,
            "api_endpoint": request.path,
            "ip": request.remote_addr,
            "platform": request.user_agent.platform,
            "browser": request.user_agent.browser,
            "browser_version": request.user_agent.version,
            "user_agent": request.user_agent.string
        }

        if api.auth.is_logged_in():

            user = api.user.get_user()
            team = api.user.get_team()
            groups = api.team.get_groups()

            information["user"] = {
                "username": user["username"],
                "email": user["email"],
                "team_name": team["team_name"],
                "groups": [group["name"] for group in groups]
            }

    return information


def setup_logs(args):
    """
    Initialize the api loggers.

    Args:
        args: dict containing the configuration options.
    """

    flask_logging.create_logger = lambda app: use(app.logger_name)

    if not args.get("debug", True):
        set_level("werkzeug", logging.ERROR)

    level = [logging.WARNING, logging.INFO, logging.DEBUG][min(
        args.get("verbose", 1), 2)]

    internal_error_log = ExceptionHandler()
    internal_error_log.setLevel(logging.ERROR)

    log.root.setLevel(level)
    log.root.addHandler(internal_error_log)

    if api.config.get_settings()["email"]["enable_email"]:
        severe_error_log = SevereHandler()
        severe_error_log.setLevel(logging.CRITICAL)
        log.root.addHandler(severe_error_log)

    stats_log = StatsHandler()
    stats_log.setLevel(logging.INFO)

    log.root.addHandler(stats_log)
