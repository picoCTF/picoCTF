""" Module for interacting with the problems """

import imp
from copy import copy, deepcopy
from datetime import datetime
from os.path import isfile, join
from random import randint

import api
import pymongo
from api.annotations import log_action
from api.common import (check, InternalException, safe_fail,
                        SevereInternalException, validate, WebException)
from bson import json_util
from voluptuous import Length, Range, Required, Schema

submission_schema = Schema({
    Required("tid"):
    check(("This does not look like a valid tid.", [str, Length(max=100)])),
    Required("pid"):
    check(("This does not look like a valid pid.", [str, Length(max=100)])),
    Required("key"):
    check(("This does not look like a valid key.", [str, Length(max=100)]))
})

problem_schema = Schema({
    Required("name"):
    check(("The problem's display name must be a string.", [str])),
    Required("sanitized_name"):
    check(("The problems's sanitized name must be a string.", [str])),
    Required("score"):
    check(("Score must be a positive integer.", [int, Range(min=0)])),
    Required("author"):
    check(("Author must be a string.", [str])),
    Required("category"):
    check(("Category must be a string.", [str])),
    Required("instances"):
    check(("The instances must be a list.", [list])),
    Required("hints"):
    check(("Hints must be a list.", [list])),
    "description":
    check(("The problem description must be a string.", [str])),
    "version":
    check(("A version must be a string.", [str])),
    "tags":
    check(("Tags must be described as a list.", [list])),
    "organization":
    check(("Organization must be string.", [str])),
    "pkg_architecture":
    check(("Package architecture must be string.", [str])),
    "pkg_description":
    check(("Package description must be string.", [str])),
    "pkg_name":
    check(("Package name must be string.", [str])),
    "pkg_dependencies":
    check(("Package dependencies must be list.", [list])),
    "pip_requirements":
    check(("pip requirements must be list.", [list])),
    "pip_python_version":
    check(("Pip python version must be a string.", [str])),
    "pid":
    check(("You should not specify a pid for a problem.", [lambda _: False])),
    "_id":
    check(("Your problems should not already have _ids.", [lambda id: False]))
})

instance_schema = Schema(
    {
        Required("description"):
        check(("The description must be a string.", [str])),
        Required("flag"):
        check(("The flag must be a string.", [str])),
        "port":
        check(("The port must be an int", [int])),
        "server":
        check(("The server must be a string.", [str]))
    },
    extra=True)

bundle_schema = Schema({
    Required("name"):
    check(("The bundle name must be a string.", [str])),
    Required("author"):
    check(("The bundle author must be a string.", [str])),
    Required("categories"):
    check(("The bundle categories must be a list.", [list])),
    Required("problems"):
    check(("The bundle problems must be a list.", [list])),
    Required("description"):
    check(("The bundle description must be a string.", [str])),
    "organization":
    check(("The bundle organization must be a string.", [str])),
    "dependencies":
    check(("The bundle dependencies must be a dict.", [dict])),
    "dependencies_enabled":
    check(("The dependencies enabled state must be a bool.",
           [lambda x: type(x) == bool])),
    "pkg_dependencies":
    check(("The package dependencies must be a list.",
           [lambda x: type(x) == list]))
})

SANITATION_KEYS = [
    "deployment_directory",
    "flag",
    "flag_sha1",
    "iid",
    "instance_number",
    "pip_python_version",
    "pip_requirements",
    "pkg_dependencies",
    "service",
    "should_symlink",
    "sid",
    "user",
]

DEBUG_KEY = None


def get_all_categories(show_disabled=False):
    """
    Gets the set of distinct problem categories.

    Args:
        show_disabled: Whether to include categories that are only on disabled problems
    Returns:
        The set of distinct problem categories.
    """

    db = api.common.get_conn()

    match = {}
    if not show_disabled:
        match.update({"disabled": False})

    return db.problems.find(match).distinct("category")


def set_instance_ids(problem, sid):
    """
    Generate the instance ids for a set of problems.
    """

    for instance in problem["instances"]:
        instance["iid"] = api.common.hash(
            str(instance["instance_number"]) + sid + problem["pid"])
        instance["sid"] = sid


def insert_problem(problem, sid=None):
    """
    Inserts a problem into the database. Does sane validation.

    Args:
        Problem dict.
        score: points awarded for completing the problem.
        category: problem's category
        author: author of the problem
        description: description of the problem.

        Optional:
        version: version of the problem
        tags: list of problem tags.
        hints: hints for completing the problem.
        organization: Organization that author is associated with
    Returns:
        The newly created problem id.
    """

    if sid is None:
        raise InternalException("Must provide an sid to insert problem.")

    db = api.common.get_conn()
    validate(problem_schema, problem)

    # initially disable problems
    problem["disabled"] = True
    problem["pid"] = api.common.hash("{}-{}".format(problem["name"],
                                                    problem["author"]))

    for instance in problem["instances"]:
        validate(instance_schema, instance)

    set_instance_ids(problem, sid)

    if safe_fail(get_problem, pid=problem["pid"]) is not None:
        # problem is already inserted, so update instead
        old_problem = copy(get_problem(pid=problem["pid"]))

        # leave all instances from different shell server
        instances = list(
            filter(lambda i: i["sid"] != sid, old_problem["instances"]))

        # add instances from this shell server
        instances.extend(problem["instances"])
        problem["instances"] = instances

        # disable problems with zero instances
        problem["disabled"] = old_problem["disabled"] or len(
            problem["instances"]) == 0

        # run the update
        update_problem(problem["pid"], problem)
        return

    if safe_fail(get_problem, name=problem["name"]) is not None:
        raise WebException(
            "Problem with identical name \"{}\" already exists.".format(
                problem["name"]))

    db.problems.insert(problem)
    api.cache.fast_cache.clear()

    return problem["pid"]


def remove_problem(pid):
    """
    Removes a problem from the given database.

    Args:
        pid: the pid of the problem to remove.
    Returns:
        The removed problem object.
    """

    db = api.common.get_conn()
    problem = get_problem(pid=pid)

    db.problems.remove({"pid": pid})
    api.cache.fast_cache.clear()

    return problem


def update_problem(pid, updated_problem):
    """
    Updates a problem with new properties.

    Args:
        pid: the pid of the problem to update.
        updated_problem: an updated problem object.
    Returns:
        The updated problem object.
    """

    db = api.common.get_conn()

    problem = get_problem(pid=pid).copy()

    problem.update(updated_problem)

    # pass validation by removing/readding pid
    # TODO: add in-database problem schema
    """
    problem.pop("pid", None)
    validate(problem_schema, problem)
    problem["pid"] = pid
    """

    db.problems.update({"pid": pid}, problem)
    api.cache.fast_cache.clear()

    return problem


def search_problems(*conditions):
    """
    Aggregates all problems that contain all of the given properties from the list specified.

    Args:
        conditions: multiple mongo queries to search.
    Returns:
        The list of matching problems.
    """

    db = api.common.get_conn()

    return list(db.problems.find({"$or": list(conditions)}, {"_id": 0}))


def assign_instance_to_team(pid, tid=None, reassign=False):
    """
    Assigns an instance of problem pid to team tid. Updates it in the database.

    Args:
        pid: the problem id
        tid: the team id
        reassign: whether or not we should assign over an old assignment

    Returns:
        The iid that was assigned
    """

    team = api.team.get_team(tid=tid)
    problem = get_problem(pid=pid)

    if pid in team["instances"] and not reassign:
        raise InternalException(
            "Team with tid {} already has an instance of pid {}.".format(
                tid, pid))

    if len(problem["instances"]) == 0:
        raise InternalException(
            "Problem {} has no instances to assign.".format(pid))

    instance_number = randint(0, len(problem["instances"]) - 1)
    iid = problem["instances"][instance_number]["iid"]

    team["instances"][pid] = iid

    db = api.common.get_conn()
    db.teams.update({"tid": tid}, {"$set": team})

    return instance_number


def get_instance_data(pid, tid):
    """
    Returns the instance dictionary for the specified pid, tid pair

    Args:
        pid: the problem id
        tid: the team id

    Returns:
        The instance dictionary
    """

    instance_map = api.team.get_team(tid=tid)["instances"]
    problem = get_problem(pid=pid)

    if pid not in instance_map:
        iid = assign_instance_to_team(pid, tid)
    else:
        iid = instance_map[pid]

    for instance in problem["instances"]:
        if instance["iid"] == iid:
            return instance

    # Cannot find assigned instance. Reassign instance and recurse.
    assign_instance_to_team(pid, tid, reassign=True)
    return get_instance_data(pid, tid)


def get_problem_instance(pid, tid):
    """
    Returns the problem instance dictionary that can be displayed to the user.

    Args:
        pid: the problem id
        tid: the team id

    Returns:
        The problem instance
    """

    problem = deepcopy(get_problem(pid=pid, tid=tid))
    instance = get_instance_data(pid, tid)

    problem['solves'] = api.stats.get_problem_solves(pid=pid)

    problem.pop("instances")
    problem.update(instance)
    return problem


def grade_problem(pid, key, tid=None):
    """
    Grades the problem with its associated flag.

    Args:
        tid: tid if provided
        pid: problem's pid
        key: user's submission
    Returns:
        A dict.
        correct: boolean
        points: number of points the problem is worth.
        message: message indicating the correctness of the key.
    """

    if tid is None:
        tid = api.user.get_user()["tid"]

    problem = get_problem(pid=pid)
    instance = get_instance_data(pid, tid)

    correct_key = instance['flag'] if DEBUG_KEY is None else DEBUG_KEY

    correct = correct_key in key

    return {
        "correct": correct,
        "points": problem["score"],
        "message": "That is correct!" if correct else "That is incorrect!"
    }


@log_action
def submit_key(tid, pid, key, uid=None, ip=None):
    """
    User problem submission. Problem submission is inserted into the database.

    Args:
        tid: user's team id
        pid: problem's pid
        key: answer text
        uid: user's uid
    Returns:
        A dict.
        correct: boolean
        points: number of points the problem is worth.
        message: message indicating the correctness of the key.
    """

    db = api.common.get_conn()
    validate(submission_schema, {"tid": tid, "pid": pid, "key": key})

    if pid not in get_unlocked_pids(tid):
        raise InternalException(
            "You can't submit flags to problems you haven't unlocked.")

    if pid in get_solved_pids(tid=tid):
        exp = WebException("You have already solved this problem.")
        exp.data = {'code': 'solved'}
        raise exp

    user = api.user.get_user(uid=uid)
    if user is None:
        raise InternalException("User submitting flag does not exist.")

    uid = user["uid"]

    result = grade_problem(pid, key, tid)

    problem = get_problem(pid=pid)

    eligibility = api.team.get_team(tid=tid)['eligible']

    submission = {
        'uid': uid,
        'tid': tid,
        'timestamp': datetime.utcnow(),
        'pid': pid,
        'ip': ip,
        'key': key,
        'eligible': eligibility,
        'category': problem['category'],
        'correct': result['correct']
    }

    if (key, pid) in [(submission["key"], submission["pid"])
                      for submission in get_submissions(tid=tid)]:
        exp = WebException(
            "You or one of your teammates has already tried this solution.")
        exp.data = {'code': 'repeat'}
        raise exp

    db.submissions.insert(submission)

    if submission["correct"]:
        api.cache.invalidate_memoization(
            api.stats.get_score, {"kwargs.tid": tid}, {"kwargs.uid": uid})
        api.cache.invalidate_memoization(get_unlocked_pids, {"args": tid})
        api.cache.invalidate_memoization(
            get_solved_problems, {"kwargs.tid": tid}, {"kwargs.uid": uid})

        api.cache.invalidate_memoization(api.stats.get_score_progression,
                                         {"kwargs.tid": tid},
                                         {"kwargs.uid": uid})

        api.achievement.process_achievements("submit", {
            "uid": uid,
            "tid": tid,
            "pid": pid
        })

    return result


def count_submissions(pid=None,
                      uid=None,
                      tid=None,
                      category=None,
                      correctness=None,
                      eligibility=None):
    db = api.common.get_conn()
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

    if eligibility is not None:
        match.update({"eligible": eligibility})

    return db.submissions.find(match, {"_id": 0}).count()


def get_submissions(pid=None,
                    uid=None,
                    tid=None,
                    category=None,
                    correctness=None,
                    eligibility=None):
    """
    Gets the submissions from a team or user.
    Optional filters of pid or category.

    Args:
        uid: the user id
        tid: the team id

        category: category filter.
        pid: problem filter.
        correctness: correct filter
    Returns:
        A list of submissions from the given entity.
    """

    db = api.common.get_conn()

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

    if eligibility is not None:
        match.update({"eligible": eligibility})

    return list(db.submissions.find(match, {"_id": 0}))


def clear_all_submissions():
    """
    Removes all submissions from the database.
    """

    if DEBUG_KEY is not None:
        db = api.common.get_conn()
        db.submissions.remove()
        api.cache.clear_all()
    else:
        raise InternalException("DEBUG Mode must be enabled")


def clear_submissions(uid=None, tid=None, pid=None):
    """
    Clear submissions for a given team, user, or problems.

    Args:
        uid: the user's uid to clear from.
        tid: the team's tid to clear from.
        pid: the pid to clear from.
    """

    db = api.common.get_conn()

    match = {}

    if pid is not None:
        match.update({"pid", pid})
    elif uid is not None:
        match.update({"uid": uid})
    elif tid is not None:
        match.update({"tid": tid})
    else:
        raise InternalException("You must supply either a tid, uid, or pid")

    return db.submissions.remove(match)


def invalidate_submissions(pid=None, uid=None, tid=None):
    """
    Invalidates the submissions for a given problem. Can be filtered by uid or tid.
    Passing no arguments will invalidate all submissions.

    Args:
        pid: the pid of the problem.
        uid: the user's uid that will his submissions invalidated.
        tid: the team's tid that will have their submissions invalidated.
    """

    db = api.common.get_conn()

    match = {}

    if pid is not None:
        match.update({"pid": pid})

    if uid is not None:
        match.update({"uid": uid})
    elif tid is not None:
        match.update({"tid": tid})

    db.submissions.update(match, {"correct": False})


def reevaluate_submissions_for_problem(pid):
    """
    In the case of the problem being updated, this will reevaluate submissions for a problem.

    Args:
        pid: the pid of the problem to be reevaluated.
    """

    db = api.common.get_conn()

    get_problem(pid=pid)

    keys = {}
    for submission in get_submissions(pid=pid):
        key = submission["key"]
        if key not in keys:
            result = grade_problem(pid, key, submission["tid"])
            if result["correct"] != submission["correct"]:
                keys[key] = result["correct"]
            else:
                keys[key] = None

    for key, change in keys.items():
        if change is not None:
            db.submissions.update(
                {
                    "key": key
                }, {"$set": {
                    "correct": change
                }}, multi=True)


def reevaluate_all_submissions():
    """
    In the case of the problem being updated, this will reevaluate all submissions.
    """

    api.cache.clear_all()
    for problem in get_all_problems(show_disabled=True):
        reevaluate_submissions_for_problem(problem["pid"])


@api.cache.memoize(timeout=60, fast=True)
def get_problem(pid=None, name=None, tid=None, show_disabled=True):
    """
    Gets a single problem.

    Args:
        pid: The problem id
        name: The name of the problem
        show_disabled: Boolean indicating whether or not to show disabled problems. Defaults to True
    Returns:
        The problem dictionary from the database
    """

    db = api.common.get_conn()

    match = {}

    if pid is not None:
        match.update({'pid': pid})
    elif name is not None:
        match.update({'name': name})
    else:
        raise InternalException("Must supply pid or display name")

    if tid is not None and pid not in get_unlocked_pids(tid):
        raise InternalException("You cannot get this problem")

    if not show_disabled:
        match.update({"disabled": False})

    db = api.common.get_conn()
    problem = db.problems.find_one(match, {"_id": 0})

    if problem is None:
        raise SevereInternalException("Could not find problem! You gave " +
                                      str(match))

    return problem


def get_all_problems(category=None, show_disabled=False):
    """
    Gets all of the problems in the database.

    Args:
        category: Optional parameter to restrict which problems are returned
        show_disabled: Boolean indicating whether or not to show disabled problems.
    Returns:
        List of problems from the database
    """

    db = api.common.get_conn()

    match = {}
    if category is not None:
        match.update({'category': category})

    if not show_disabled:
        match.update({'disabled': False})

    return list(
        db.problems.find(match, {
            "_id": 0
        }).sort([('score', pymongo.ASCENDING), ('name', pymongo.ASCENDING)]))


@api.cache.memoize()
def get_solved_problems(tid=None, uid=None, category=None, show_disabled=False):
    """
    Gets the solved problems for a given team or user.

    Args:
        tid: The team id
        category: Optional parameter to restrict which problems are returned
    Returns:
        List of solved problem dictionaries
    """

    if uid is not None and tid is None:
        team = api.user.get_team(uid=uid)
    else:
        team = api.team.get_team(tid=tid)

    members = api.team.get_team_uids(tid=team["tid"])

    submissions = get_submissions(
        tid=tid, uid=uid, category=category, correctness=True)

    for uid in members:
        submissions += get_submissions(
            uid=uid, category=category, correctness=True)

    pids = []
    result = []

    # Team submissions will take precedence because they appear first in the submissions list.
    for submission in submissions:
        if submission["pid"] not in pids:
            pids.append(submission["pid"])
            problem = unlocked_filter(get_problem(pid=submission["pid"]), True)
            problem["solve_time"] = submission["timestamp"]
            if not problem["disabled"] or show_disabled:
                result.append(problem)

    return result


def get_solved_pids(*args, **kwargs):
    """
    Gets the solved pids for a given team or user.

    Args:
        tid: The team id
        category: Optional parameter to restrict which problems are returned
    Returns:
        List of solved problem ids
    """

    return [problem["pid"] for problem in get_solved_problems(*args, **kwargs)]


def is_problem_unlocked(problem, solved):
    """
    Checks if the specified problem is unlocked.
    A problem is unlocked if either:
        1. It has no dependencies in any of the bundles
        2. Its threshold is reached in all bundles that specify a dependency for it

    Args:
        problem: the problem object to check
        solved: the list of solved problem objects
    """

    unlocked = True

    for bundle in get_all_bundles():
        if problem["sanitized_name"] in bundle["problems"]:
            if "dependencies" in bundle and bundle["dependencies_enabled"]:
                if problem["sanitized_name"] in bundle["dependencies"]:
                    dependency = bundle["dependencies"][problem[
                        "sanitized_name"]]
                    weightsum = sum(
                        dependency['weightmap'].get(p['sanitized_name'], 0)
                        for p in solved)
                    if weightsum < dependency['threshold']:
                        unlocked = False

    return unlocked


@api.cache.memoize()
def get_unlocked_pids(tid, category=None):
    """
    Gets the unlocked pids for a given team.

    Args:
        tid: The team id
        category: Optional parameter to restrict which problems are returned
    Returns:
        List of unlocked problem ids
    """
    # Note: Do NOT limit solved problems to category for proper weight count
    solved = get_solved_problems(tid=tid, category=None)
    team = api.team.get_team(tid=tid)

    unlocked = []
    for problem in get_all_problems(category=category):
        if is_problem_unlocked(problem, solved):
            unlocked.append(problem["pid"])

    for pid in unlocked:
        if pid not in team["instances"]:
            assign_instance_to_team(pid, tid)

    return unlocked


def filter_problem(problem, remove_list, set_dict):
    """
    Filters the problem by removing all keys in the remove_list
    and setting all keys in the set_dict.
    """

    problem = copy(problem)

    for key in remove_list:
        if key in problem:
            problem.pop(key)

    problem.update(set_dict)

    return problem


def unlocked_filter(problem, solved):
    """
    Returns a filtered version of the problem for when it is in an unlocked state

    Args:
        problem: the problem object
        solved: boolean indicating if this problem is also solved

    Returns:
        A filtered problem object
    """

    return filter_problem(problem, ["flag", "tags", "files"], {
        "solved": solved,
        "unlocked": True
    })


def locked_filter(problem):
    """
    Returns a filtered version of the problem for when it is in a locked state

    Args:
        problem: the problem object

    Returns:
        A filtered problem object
    """

    return filter_problem(problem,
                          ["description", "instances", "hints", "tags"], {
                              "solved": False,
                              "unlocked": False
                          })


def count_all_problems(category=None):
    """
    Returns all (enabled) category names and the number of (enabled) problems
    in each, both visible and non-visible.

    Args:
        category: Optional parameter to restrict to only one category
    Returns:
        A dict.
        category: category name
        count: number of problems in that category
    """
    if category is None:
        categories = get_all_categories(show_disabled=False)
    else:
        categories = [category]
    result = {}

    for cat in categories:
        result[cat] = len(get_all_problems(cat))

    return result


def get_visible_problems(tid, category=None):
    """
    Returns all of the problems where the unlocked problems have full information and the
    locked problems show only name, category, and score.

    Args:
        tid: The team id
        category: Optional parameter to restrict which problems are returned
    Returns:
        List of visible problem dictionaries
    """

    all_problems = get_all_problems(category=category, show_disabled=False)
    unlocked_pids = get_unlocked_pids(tid, category=category)
    solved_pids = get_solved_pids(tid=tid)

    result = []

    result = []
    # locked = []

    for problem in all_problems:
        if problem["pid"] in unlocked_pids:
            result.append(
                unlocked_filter(
                    get_problem_instance(problem["pid"], tid),
                    problem["pid"] in solved_pids))

        # Disable locked problem display.
        # else:
        # locked.append(locked_filter(problem))

    # place locked problems at the end of the list
    # result.extend(locked)

    return result


def get_unlocked_problems(tid, category=None):
    """
    Gets the unlocked problems for a given team.

    Args:
        tid: The team id
        category: Optional parameter to restrict which problems are returned
    Returns:
        List of unlocked problem dictionaries
    """

    return [
        problem for problem in get_visible_problems(tid, category=category)
        if problem['unlocked']
    ]


def insert_bundle(bundle):
    """
    Inserts the bundle into the database after
    validating it with the bundle_schema
    """

    db = api.common.get_conn()
    validate(bundle_schema, bundle)

    bid = api.common.hash("{}-{}".format(bundle["name"], bundle["author"]))

    if safe_fail(get_bundle, bid) is not None:
        # bundle already exists, update it instead
        update_bundle(bid, bundle)
        return

    bundle["bid"] = bid
    bundle["dependencies_enabled"] = False

    db.bundles.insert(bundle)


def load_published(data):
    """
    Load in the problems from the shell_manager publish blob.

    Args:
        data: The output of "shell_manager publish"
    """

    if "problems" not in data:
        raise WebException("Please provide a problems list in your json.")

    for problem in data["problems"]:
        insert_problem(problem, sid=data["sid"])

    if "bundles" in data:
        db = api.common.get_conn()
        for bundle in data["bundles"]:
            insert_bundle(bundle)

    api.cache.clear_all()


def get_bundle(bid):
    """
    Returns the bundle object corresponding to the given bid
    """

    db = api.common.get_conn()

    bundle = db.bundles.find_one({"bid": bid})

    if bundle is None:
        raise WebException("Bundle with bid {} does not exist".format(bid))

    return bundle


def update_bundle(bid, updates):
    """
    Updates the bundle object in the database with the given updates.
    """

    db = api.common.get_conn()

    bundle = db.bundles.find_one({"bid": bid}, {"_id": 0})
    if bundle is None:
        raise WebException("Bundle with bid {} does not exist".format(bid))

    # pop the bid temporarily to check with schema
    bid = bundle.pop("bid")
    bundle.update(updates)
    validate(bundle_schema, bundle)
    bundle["bid"] = bid

    db.bundles.update({"bid": bid}, {"$set": bundle})


def get_all_bundles():
    """
    Returns all bundles from the database
    """

    db = api.common.get_conn()

    return list(db.bundles.find({}, {"_id": 0}))


def set_bundle_dependencies_enabled(bid, enabled):
    """
    Sets the dependencies_enabled field in the object in the database.
    This will affect the unlocked problems.

    Args:
        bid: the bundle id to update
        enabled:
    """

    update_bundle(bid, {"dependencies_enabled": enabled})
    api.cache.clear_all()


def sanitize_problem_data(data):
    """
    Removes problem data as specified in SANITATION_KEYS, to eliminate leakage
    of unnecessary platform information to players.

    Args:
        data: dict or list of problems
    """

    def pop_keys(problem_dict):
        for key in SANITATION_KEYS:
            problem_dict.pop(key, None)

    if isinstance(data, list):
        for problem in data:
            pop_keys(problem)
    elif isinstance(data, dict):
        pop_keys(data)
    return data
