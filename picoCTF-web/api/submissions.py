"""Module for handling flag submissions."""

from datetime import datetime

import api
from api import cache, check, log_action, PicoException, validate
from api.cache import memoize
from voluptuous import Length, Required, Schema

submission_schema = Schema(
    {
        Required("tid"): check(
            ("This does not look like a valid tid.", [str, Length(max=100)])
        ),
        Required("pid"): check(
            ("This does not look like a valid pid.", [str, Length(max=100)])
        ),
        Required("key"): check(
            ("This does not look like a valid key.", [str, Length(max=100)])
        ),
    }
)

DEBUG_KEY = None


def grade_problem(pid, key, tid=None):
    """
    Grade the problem with its associated flag.

    Args:
        tid: tid if provided
        pid: problem's pid
        key: user's submission

    Returns:
        (bool, bool): whether the submission is correct and suspicious
                      (suspicious: valid for another problem instance)

    """
    if tid is None:
        tid = api.user.get_user()["tid"]

    problem = api.problem.get_problem(pid)
    assigned_instance = api.problem.get_instance_data(pid, tid)

    suspicious = False
    correct = assigned_instance["flag"] in key
    if not correct and DEBUG_KEY is not None:
        correct = DEBUG_KEY in key
    if not correct:
        other_instance_flags = [
            instance["flag"]
            for instance in problem["instances"]
            if instance["iid"] != assigned_instance["iid"]
        ]
        suspicious = any([flag in key for flag in other_instance_flags])

    return (correct, suspicious)


@log_action
def submit_key(tid, pid, key, method, uid, ip=None):
    """
    User problem submission.

    Args:
        tid: user's team id
        pid: problem's pid
        key: answer text
        method: submission method (e.g. 'game')
        uid: user's uid
        ip: user's ip
    Returns:
        tuple: (correct, previously_solved_by_user,
                previously_solved_by_team)
    """
    db = api.db.get_conn()
    validate(submission_schema, {"tid": tid, "pid": pid, "key": key})

    if pid not in api.problem.get_unlocked_pids(tid):
        raise PicoException(
            "You can't submit flags to problems you haven't unlocked.", 422
        )

    previously_solved_by_user = (
        db.submissions.find_one(filter={"pid": pid, "uid": uid, "correct": True})
        is not None
    )

    previously_solved_by_team = (
        db.submissions.find_one(filter={"pid": pid, "tid": tid, "correct": True})
        is not None
    )

    correct, suspicious = grade_problem(pid, key, tid)

    if not previously_solved_by_user:
        count_solves = api.stats.get_problem_solves(pid)
        bonus = 10 - count_solves
        db.submissions.insert(
            {
                "uid": uid,
                "tid": tid,
                "timestamp": datetime.utcnow(),
                "pid": pid,
                "ip": ip,
                "key": key,
                "method": method,
                "category": api.problem.get_problem(pid, {"category": 1})["category"],
                "correct": correct,
                "suspicious": suspicious,
                "bonus": bonus,
            }
        )

    if correct and not previously_solved_by_team:
        # Immediately invalidate some caches
        cache.invalidate(api.stats.get_score, tid)
        cache.invalidate(api.stats.get_score, uid)
        cache.invalidate(api.problem.get_unlocked_pids, tid)
        cache.invalidate(
            api.problem.get_solved_problems, tid=tid, uid=uid, category=None
        )
        cache.invalidate(
            api.problem.get_solved_problems, tid=tid, uid=None, category=None
        )
        cache.invalidate(api.problem.get_solved_problems, tid=tid, uid=uid)
        cache.invalidate(api.problem.get_solved_problems, tid=tid)
        cache.invalidate(api.problem.get_solved_problems, uid=uid)
        cache.invalidate(api.stats.get_score_progression, tid=tid, category=None)
        cache.invalidate(api.stats.get_score_progression, tid=tid)

    # if the solve is correct there is no need to maintain the container
    if correct:
        instance = api.problem.get_instance_data(pid, tid)
        if "docker_challenge" in instance and instance["docker_challenge"]:
            containers = api.docker.submission_to_cid(tid, pid)
            for c in containers:
                cid = c["cid"]
                api.docker.delete(cid)

    if suspicious:
        cache.invalidate(api.submissions.get_suspicious_submissions, tid)

    return (correct, previously_solved_by_user, previously_solved_by_team)


def get_submissions(
    pid=None, uid=None, tid=None, category=None, correctness=None, suspicious=None,
):
    """
    Get the submissions from a team or user.

    Optional filters of pid or category.

    Args:
        uid: the user id
        tid: the team id

        category: category filter.
        pid: problem filter.
        correctness: correct filter
        suspicious: suspicious filter
    Returns:
        A list of submissions from the given entity.
    """
    db = api.db.get_conn()

    match = {}

    if uid is not None:
        match.update({"uid": uid})
    elif tid is not None:
        match.update({"tid": tid})

    if pid is not None:
        match.update({"pid": pid})

    if category is not None:
        match.update({"category": category})

    if correctness is not None:
        match.update({"correct": correctness})

    if suspicious is not None:
        match.update({"suspicious": suspicious})

    return list(db.submissions.find(match, {"_id": 0}))


@memoize
def get_suspicious_submissions(tid):
    """Get the suspicious submissions for a given team."""
    submissions = get_submissions(tid=tid, suspicious=True)
    for submission in submissions:
        submission["problem_name"] = api.problem.get_problem(submission["pid"])["name"]
    return submissions


def clear_all_submissions():
    """Remove all submissions from the database."""
    if DEBUG_KEY is not None:
        db = api.db.get_conn()
        db.submissions.remove()
        api.cache.clear()
    else:
        raise PicoException("Debug mode must be enabled", 500)
