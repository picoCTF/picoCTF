"""
Legacy API shim to support 2019 game.

Provides legacy behavior for:

/user/login
/user/logout
/user/status
/user/minigame @TODO: merge in gamedev branch
/user/extdata
/problems
/problems/submit
/problems/unlock_walkthrough @TODO: merge in gamedev branch
/problems/walkthrough?pid=<pid> @TODO: merge in gamedev branch
/team/score
"""
from bson import json_util
from flask import Blueprint, request

import api.auth
import api.config
import api.db
import api.problem
import api.stats
import api.submissions
import api.user
from api.annotations import (block_after_competition, block_before_competition,
                             check_csrf, require_login)
from api.common import flat_multi, PicoException

blueprint = Blueprint('v0_api', __name__)


def WebSuccess(message=None, data=None):
    return json_util.dumps({
            'status': 1,
            'message': message,
            'data': data
        })


def WebError(message=None, data=None):
    return json_util.dumps({
            'status': 0,
            'message': message,
            'data': data
        })


@blueprint.route('/user/login', methods=['POST'])
def login_hook():
    username = request.form.get('username')
    password = request.form.get('password')
    try:
        api.auth.login(username, password)
    except PicoException as e:
        if e.status_code == 401:
            return WebError(
                message='Incorrect password'
            )
    return WebSuccess(
        message="Successfully logged in as " + username,
        data={
            'teacher': api.user.is_teacher(),
            'admin': api.user.is_admin()
        }), 200


@blueprint.route('/user/logout', methods=['GET'])
def logout_hook():
    if api.auth.is_logged_in():
        api.auth.logout()
        return WebSuccess("Successfully logged out."), 200
    else:
        return WebError("You do not appear to be logged in."), 400


@blueprint.route('/user/status', methods=['GET'])
def status_hook():
    settings = api.config.get_settings()
    status = {
        "logged_in":
        api.auth.is_logged_in(),
        "admin":
        api.auth.is_logged_in() and api.user.is_admin(),
        "teacher":
        api.auth.is_logged_in() and api.user.is_teacher(),
        "enable_feedback":
        settings["enable_feedback"],
        "enable_captcha":
        settings["captcha"]["enable_captcha"],
        "reCAPTCHA_public_key":
        settings["captcha"]["reCAPTCHA_public_key"],
        "competition_active":
        api.config.check_competition_active(),
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

    return WebSuccess(data=status), 200


@blueprint.route('/user/extdata', methods=['GET'])
@require_login
def get_extdata_hook():
    """
    Return user extdata, or empty JSON object if unset.
    """
    user = api.user.get_user(uid=None)
    return WebSuccess(data=user['extdata']), 200


@blueprint.route('/user/extdata', methods=['PUT'])
@check_csrf
@require_login
def update_extdata_hook():
    """
    Sets user extdata via HTTP form. Takes in any key-value pairs.
    """
    api.user.update_extdata(flat_multi(request.form))
    return WebSuccess("Your Extdata has been successfully updated."), 200


@blueprint.route('/problems', methods=['GET'])
@require_login
@block_before_competition()
def get_visible_problems_hook():
    tid = api.user.get_user()['tid']
    all_problems = api.problem.get_all_problems(show_disabled=False)
    unlocked_pids = api.problem.get_unlocked_pids(tid)
    solved_pids = api.problem.get_solved_pids(tid=tid)

    visible_problems = []
    for problem in all_problems:
        if problem["pid"] in unlocked_pids:
            problem = api.problem.filter_problem_instances(problem, tid)
            problem.pop('flag', None)
            problem.pop('tags', None)
            problem.pop('files', None)
            problem['solved'] = problem["pid"] in solved_pids
            problem['unlocked'] = True
            visible_problems.append(problem)
    for problem in visible_problems:
        problem['solves'] = api.stats.get_problem_solves(problem['pid'])
    return WebSuccess(
        data=api.problem.sanitize_problem_data(visible_problems)), 200


@blueprint.route('/problems/submit', methods=['POST'])
@check_csrf
@require_login
@block_before_competition()
@block_after_competition()
def submit_key_hook():
    user_account = api.user.get_user()
    tid = user_account['tid']
    uid = user_account['uid']
    pid = request.form.get('pid', '')
    key = request.form.get('key', '')
    method = request.form.get('method', '')
    ip = request.remote_addr

    (correct, previously_solved_by_user,
     previously_solved_by_team) = api.submissions.submit_key(
            tid, pid, key, method, uid, ip)

    if correct and not previously_solved_by_team:
        return WebSuccess("That is correct!"), 200
    elif not correct and not previously_solved_by_team:
        return WebError("That is incorrect!"), 200
    elif correct and previously_solved_by_user:
        return WebSuccess(
            'Flag correct: however, you have already solved ' +
            'this problem.'
        ), 200
    elif correct and previously_solved_by_team:
        return WebSuccess(
            'Flag correct: however, your team has already received points ' +
            'for this flag.'
        ), 200
    elif not correct and previously_solved_by_user:
        return WebError(
            'Flag incorrect: please note that you have ' +
            'already solved this problem.'
        ), 200
    elif not correct and previously_solved_by_team:
        return WebError(
            'Flag incorrect: please note that someone on your team has ' +
            'already solved this problem.'
        ), 200


@blueprint.route('/team/score', methods=['GET'])
@require_login
def get_team_score_hook():
    score = api.stats.get_score(tid=api.user.get_user()['tid'])
    if score is not None:
        return WebSuccess(data={'score': score})
    return WebError("There was an error retrieving your score."), 500