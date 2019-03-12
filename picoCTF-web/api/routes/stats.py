import api
import bson
import math
from api.annotations import (api_wrapper, block_after_competition,
                             block_before_competition, check_csrf, log_action,
                             require_admin, require_login, require_teacher)
from api.common import WebError, WebSuccess
from flask import (Blueprint, Flask, render_template, request,
                   send_from_directory, session)

blueprint = Blueprint("stats_api", __name__)
scoreboard_page_len = 50


@blueprint.route('/team/solved_problems', methods=['GET'])
@api_wrapper
@require_login
@block_before_competition(WebError("The competition has not begun yet!"))
def get_team_solved_problems_hook():
    tid = request.args.get("tid", None)
    stats = {
        "problems": api.stats.get_problems_by_category(),
        "members": api.stats.get_team_member_stats(tid)
    }

    return WebSuccess(data=stats)


@blueprint.route('/team/score_progression', methods=['GET'])
@api_wrapper
@require_login
@block_before_competition(WebError("The competition has not begun yet!"))
def get_team_score_progression():
    category = request.args.get("category", None)

    tid = api.user.get_team()["tid"]

    return WebSuccess(
        data=api.stats.get_score_progression(tid=tid, category=category))


@blueprint.route('/scoreboard', defaults={'board': None, 'page': 1}, methods=['GET'])
@blueprint.route('/scoreboard/<board>/<int:page>', methods=['GET'])
@api_wrapper
@block_before_competition(WebError("The competition has not begun yet!"))
def get_scoreboard_hook(board, page):
    def get_user_pos(scoreboard, tid):
        for pos, team in enumerate(scoreboard):
            if team["tid"] == tid:
                return pos
        return 1

    user = None
    if api.auth.is_logged_in():
        user = api.user.get_user()

    # Old board, limit 1-50
    if board is None:
        result = {'tid': 0, 'groups': []}
        global_board = api.stats.get_all_team_scores(eligible=True, country=None, show_ineligible=True)
        result['global'] = {
            'name': 'global',
            'pages': math.ceil(len(global_board) / scoreboard_page_len),
            'start_page': 1
        }
        if user is None:
            result['global']['scoreboard'] = global_board[:scoreboard_page_len]
        else:
            result['tid'] = user['tid']
            global_pos = get_user_pos(global_board, user["tid"])
            start_slice = math.floor(global_pos / 50) * 50
            result['global']['scoreboard'] = global_board[start_slice:start_slice + 50]
            result['global']['start_page'] = math.ceil((global_pos + 1) / 50)

            result['country'] = user["country"]
            student_board = api.stats.get_all_team_scores(eligible=True, country=None, show_ineligible=False)
            student_pos = get_user_pos(student_board, user["tid"])
            start_slice = math.floor(student_pos / 50) * 50
            result['student'] = {
                'name': 'student',
                'pages': math.ceil(len(student_board) / scoreboard_page_len),
                'scoreboard': student_board[start_slice:start_slice + 50],
                'start_page': math.ceil((student_pos + 1) / 50),
            }

            for group in api.team.get_groups(uid=user["uid"]):
                group_board = api.stats.get_group_scores(gid=group['gid'])
                group_pos = get_user_pos(group_board, user["tid"])
                start_slice = math.floor(group_pos / 50) * 50
                result['groups'].append({
                    'gid':
                    group['gid'],
                    'name':
                    group['name'],
                    'scoreboard':
                    group_board[start_slice:start_slice + 50],
                    'pages': math.ceil(len(group_board) / scoreboard_page_len),
                    'start_page': math.ceil((group_pos + 1) / 50),
                })

        return WebSuccess(data=result)
    else:
        if board in ["groups", "global", "student"]:
            # 1-index page
            start = scoreboard_page_len * (page - 1)
            end = start + scoreboard_page_len
            result = []
            if api.auth.is_logged_in():
                user = api.user.get_user()
            if board == "groups":
                for group in api.team.get_groups(uid=user.get("uid")):
                    result.append({
                        'gid':
                            group['gid'],
                        'name':
                            group['name'],
                        'scoreboard':
                            api.stats.get_group_scores(gid=group['gid'])[start:end]
                    })
            elif board == "global":
                result = api.stats.get_all_team_scores(eligible=True, country=None, show_ineligible=True)[start:end]
            elif board == "student":
                result = api.stats.get_all_team_scores(eligible=True, country=None, show_ineligible=False)[start:end]
            else:
                result = []
            return WebSuccess(data=result)
        else:
            return WebError("A valid board must be specified")


@blueprint.route('/top_teams/score_progression', methods=['GET'])
@api_wrapper
def get_top_teams_score_progressions_hook():
    eligible = request.args.get("eligible", "true")
    eligible = bson.json_util.loads(eligible)

    show_ineligible = request.args.get("show_ineligible", "false")
    show_ineligible = bson.json_util.loads(show_ineligible)

    country = None
    # if api.auth.is_logged_in():
    #    user = api.user.get_user()
    #    if user["country"] in ["US"] and not show_ineligible:
    #        country = user["country"]

    return WebSuccess(
        data=api.stats.get_top_teams_score_progressions(eligible=eligible, country=country, show_ineligible=show_ineligible))


@blueprint.route('/group/score_progression', methods=['GET'])
@api_wrapper
def get_group_top_teams_score_progressions_hook():
    gid = request.args.get("gid", None)
    return WebSuccess(
        data=api.stats.get_top_teams_score_progressions(gid=gid, show_ineligible=True))


@blueprint.route('/registration', methods=['GET'])
@api_wrapper
def get_registration_count_hook():
    return WebSuccess(data=api.stats.get_registration_count())
