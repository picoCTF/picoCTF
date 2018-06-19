""" Module for handling problem feedback """

from datetime import datetime

import api
import pymongo
from api.annotations import log_action
from api.common import (check, InternalException, safe_fail,
                        SevereInternalException, validate, WebException)
from voluptuous import Length, Required, Schema

feedback_schema = Schema({
    Required("liked"):
    check(("liked must be a boolean", [lambda x: type(x) == bool])),
    "comment":
    check(("The comment must be no more than 500 characters",
           [str, Length(max=500)])),
    "timeSpent":
    check(("Time spend must be a number", [int])),
    "source":
    check(("The source must be no more than 500 characters",
           [str, Length(max=10)]))
})


def get_problem_feedback(pid=None, tid=None, uid=None):
    """
    Retrieve feedback for a given problem, team, or user

    Args:
        pid: the problem id
        tid: the team id
        uid: the user id
    Returns:
        A list of problem feedback entries.
    """

    db = api.common.get_conn()
    match = {}

    if pid is not None:
        match.update({"pid": pid})
    if tid is not None:
        match.update({"tid": tid})
    if uid is not None:
        match.update({"uid": uid})

    return list(db.problem_feedback.find(match, {"_id": 0}))


def get_reviewed_pids(uid=None):
    """
    Gets the list of pids reviewed by the user

    Args:
        uid: the user id
    Returns:
        A list of pids
    """

    db = api.common.get_conn()

    if uid is None:
        uid = api.user.get_user()['uid']

    return [entry["pid"] for entry in get_problem_feedback(uid=uid)]


@log_action
def add_problem_feedback(pid, uid, feedback):
    """
    Add user problem feedback to the database.

    Args:
        pid: the problem id
        uid: the user id
        feedback: the problem feedback.
    """

    db = api.common.get_conn()

    # Make sure the problem actually exists.
    api.problem.get_problem(pid=pid)
    team = api.user.get_team(uid=uid)
    solved = pid in api.problem.get_solved_pids(tid=team["tid"])

    validate(feedback_schema, feedback)

    # update feedback if already present
    if get_problem_feedback(pid=pid, uid=uid) != []:
        db.problem_feedback.update({
            "pid": pid,
            "uid": uid
        }, {"$set": {
            "timestamp": datetime.utcnow(),
            "feedback": feedback
        }})
    else:
        db.problem_feedback.insert({
            "pid": pid,
            "uid": uid,
            "tid": team["tid"],
            "solved": solved,
            "timestamp": datetime.utcnow(),
            "feedback": feedback
        })

        api.achievement.process_achievements("review", {
            "uid": uid,
            "tid": team['tid'],
            "pid": pid
        })
