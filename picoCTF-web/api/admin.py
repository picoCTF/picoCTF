"""
API functions relating to admin users.
"""

import api
import pymongo
from api.annotations import log_action
from api.common import (check, InternalException, safe_fail, validate,
                        WebException)


def give_admin_role(name=None, uid=None):
    """
    Give a particular user admin privileges.
    There is no option to give a particular user admin privileges by default.

    Args:
        name: the user's name
        uid: the user's id
    """

    db = api.common.get_conn()

    user = api.user.get_user(name=name, uid=uid)
    db.users.update({
        "uid": user["uid"]
    }, {"$set": {
        "admin": True,
        "teacher": True
    }})


def give_teacher_role(name=None, uid=None):
    """
    Give a particular user teacher privileges if they weren't created with them.

    Args:
        name: the user's name
        uid: the user's id
    """

    db = api.common.get_conn()

    user = api.user.get_user(name=name, uid=uid)
    db.users.update({"uid": user["uid"]}, {"$set": {"teacher": True}})


def set_problem_availability(pid, disabled):
    """
    Updates a problem's availability.

    Args:
        pid: the problem's pid
        disabled: whether or not the problem should be disabled.
    Returns:
        The updated problem object.
    """

    problem = api.problem.get_problem(pid=pid)
    if len(problem["instances"]) > 0:
        result = api.problem.update_problem(pid, {"disabled": disabled})
        api.cache.clear_all()
    else:
        raise WebException(
            "You cannnot change the availability of \"{}\".".format(
                problem["name"]))
    return result


def get_api_exceptions(result_limit=50, sort_direction=pymongo.DESCENDING):
    """
    Retrieve api exceptions.

    Args:
        result_limit: the maximum number of exceptions to return.
        sort_direction: pymongo.ASCENDING or pymongo.DESCENDING
    """

    db = api.common.get_conn()

    results = db.exceptions.find({
        "visible": True
    }).sort([("time", sort_direction)]).limit(result_limit)
    return list(results)


def dismiss_api_exceptions(trace):
    """
    Remove exceptions from the management tab.

    Args:
        trace: the exception trace
    """

    db = api.common.get_conn()
    db.exceptions.remove({"trace": trace})
