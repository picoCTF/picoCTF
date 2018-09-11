""" Module for getting competition statistics"""

import datetime
import statistics
from collections import defaultdict
from hashlib import sha1

import api
import pymongo
from api.common import InternalException

_get_problem_names = lambda problems: [problem['name'] for problem in problems]
top_teams = 5


@api.cache.memoize()
def get_score(tid=None, uid=None):
    """
    Get the score for a user or team.

    Args:
        tid: The team id
        uid: The user id
    Returns:
        The users's or team's score
    """
    score = sum([
        problem['score']
        for problem in api.problem.get_solved_problems(tid=tid, uid=uid)
    ])
    return score


def get_team_review_count(tid=None, uid=None):
    if uid is not None:
        return len(api.problem_feedback.get_reviewed_pids(uid=uid))
    elif tid is not None:
        count = 0
        for member in api.team.get_team_members(tid=tid):
            count += len(
                api.problem_feedback.get_reviewed_pids(uid=member['uid']))
        return count


def get_group_scores(gid=None, name=None):
    """
    Get the group scores.

    Args:
        gid: The group id
        name: The group name
    Returns:
        A dictionary containing name, tid, and score
    """

    members = [
        api.team.get_team(tid=tid)
        for tid in api.group.get_group(gid=gid, name=name)['members']
    ]

    result = []
    for team in members:
        if team["size"] > 0:
            result.append({
                "name": team['team_name'],
                "tid": team['tid'],
                "affiliation": team["affiliation"],
                "eligible": team["eligible"],
                "score": get_score(tid=team['tid'])
            })

    return sorted(result, key=lambda entry: entry['score'], reverse=True)


def get_group_average_score(gid=None, name=None):
    """
    Get the average score of teams in a group.

    Args:
        gid: The group id
        name: The group name
    Returns:
        The total score of the group
    """

    group_scores = get_group_scores(gid=gid, name=name)
    total_score = sum([entry['score'] for entry in group_scores])
    return int(total_score / len(group_scores)) if len(group_scores) > 0 else 0


# Stored by the cache_stats daemon
@api.cache.memoize()
def get_all_team_scores(eligible=None):
    """
    Gets the score for every team in the database.

    Args:
        eligible: required boolean field

    Returns:
        A list of dictionaries with name and score
    """

    if eligible is None:
        raise InternalException("Eligible must be set to either true or false")

    if eligible:
        teams = api.team.get_all_teams(eligible=True, ineligible=False)
    else:
        teams = api.team.get_all_teams(eligible=False, ineligible=True)

    db = api.api.common.get_conn()

    result = []
    for team in teams:
        # Get the full version of the group.
        groups = [
            api.group.get_group(group["gid"])
            for group in api.team.get_groups(tid=team["tid"])
        ]

        # Determine if the user is exclusively a member of hidden groups.
        # If they are, they won't be processed.
        if len(groups) == 0 or any(
            [not (group["settings"]["hidden"]) for group in groups]):
            team_query = db.submissions.find({
                'tid': team['tid'],
                'eligible': eligible,
                'correct': True
            })
            if team_query.count() > 0:
                lastsubmit = team_query.sort(
                    'timestamp', direction=pymongo.DESCENDING)[0]['timestamp']
            else:
                lastsubmit = datetime.datetime.now()
            score = get_score(tid=team['tid'])
            if score > 0:
                result.append({
                    "name": team['team_name'],
                    "tid": team['tid'],
                    "score": score,
                    "affiliation": team["affiliation"],
                    "eligible": team["eligible"],
                    "lastsubmit": lastsubmit
                })
    time_ordered = sorted(result, key=lambda entry: entry['lastsubmit'])
    time_ordered_time_removed = [{
        'name': x['name'],
        'eligible': x['eligible'],
        'tid': x['tid'],
        'score': x['score'],
        'affiliation': x['affiliation']
    } for x in time_ordered]
    return sorted(
        time_ordered_time_removed,
        key=lambda entry: entry['score'],
        reverse=True)


def get_all_user_scores():
    """
    Gets the score for every user in the database.

    Returns:
        A list of dictionaries with name and score
    """

    users = api.user.get_all_users()

    result = []
    for user in users:
        result.append({
            "name": user['username'],
            "score": get_score(uid=user['uid'])
        })

    return sorted(result, key=lambda entry: entry['score'], reverse=True)


@api.cache.memoize(timeout=120, fast=True)
def get_problems_by_category():
    """
    Gets the list of all problems divided into categories

    Returns:
        A dictionary of category:[problem list]
    """

    result = {
        cat: _get_problem_names(api.problem.get_all_problems(category=cat))
        for cat in api.problem.get_all_categories()
    }

    return result


@api.cache.memoize(timeout=120, fast=True)
def get_pids_by_category():
    result = {
        cat: [x['pid'] for x in api.problem.get_all_problems(category=cat)
             ] for cat in api.problem.get_all_categories()
    }
    return result


@api.cache.memoize(timeout=120, fast=True)
def get_pid_categories():
    pid_map = {}
    for cat in api.problem.get_all_categories():
        for p in api.problem.get_all_problems(category=cat):
            pid_map[p['pid']] = cat
    return pid_map


def get_team_member_stats(tid):
    """
    Gets the solved problems for each member of a given team.

    Args:
        tid: the team id

    Returns:
        A dict of username:[problem list]
    """

    members = api.team.get_team_members(tid=tid)

    return {
        member['username']: _get_problem_names(
            api.problem.get_solved_problems(uid=member['uid']))
        for member in members
    }


def get_problem_submission_stats(pid=None, name=None):
    """
    Retrieves the number of valid and invalid submissions for a given problem.

    Args:
        pid: the pid of the problem
        name: the name of the problem
    Returns:
        Dict of {valid: #, invalid: #}
    """

    problem = api.problem.get_problem(pid=pid, name=name)

    return {
        "valid":
        len(api.problem.get_submissions(pid=problem["pid"], correctness=True)),
        "invalid":
        len(api.problem.get_submissions(pid=problem["pid"], correctness=False)),
    }


@api.cache.memoize()
def get_score_progression(tid=None, uid=None, category=None):
    """
    Finds the score and time after each correct submission of a team or user.
    NOTE: this is slower than get_score. Do not use this for getting current score.

    Args:
        tid: the tid of the user
        uid: the uid of the user
        category: category filter
    Returns:
        A list of dictionaries containing score and time
    """

    solved = api.problem.get_solved_problems(
        tid=tid, uid=uid, category=category)

    result = []
    score = 0

    problems_counted = set()

    for problem in sorted(solved, key=lambda prob: prob["solve_time"]):
        if problem['pid'] not in problems_counted:
            score += problem["score"]
            problems_counted.add(problem['pid'])
        result.append({
            "score": score,
            "time": int(problem["solve_time"].timestamp())
        })

    return result


def get_top_teams(gid=None, eligible=None):
    """
    Finds the top teams

    Args:
        gid: if specified, return the top teams from this group only
        eligible: required boolean field

    Returns:
        The top teams and their scores
    """

    if gid is None:
        if eligible is None:
            raise InternalException(
                "Eligible must be set to either true or false")
        all_teams = api.stats.get_all_team_scores(eligible=eligible)
    else:
        all_teams = api.stats.get_group_scores(gid=gid)
    return all_teams if len(all_teams) < top_teams else all_teams[:top_teams]


# Stored by the cache_stats daemon
@api.cache.memoize()
def get_problem_solves(name=None, pid=None):
    """
    Returns the number of solves for a particular problem.
    Must supply either pid or name.

    Args:
        name: name of the problem
        pid: pid of the problem
    """

    if not name and not pid:
        raise InternalException(
            "You must supply either a pid or name of the problem.")

    db = api.common.get_conn()

    problem = api.problem.get_problem(name=name, pid=pid)

    return db.submissions.find({'pid': problem["pid"], 'correct': True}).count()


@api.cache.memoize()
def get_top_teams_score_progressions(gid=None, eligible=True):
    """
    Gets the score_progressions for the top teams

    Args:
        gid: If specified, compute the progressions for the top teams from this group only

    Returns:
        The top teams and their score progressions.
        A dict of {name: name, score_progression: score_progression}
    """

    return [{
        "name": team["name"],
        "affiliation": team["affiliation"],
        "score_progression": get_score_progression(tid=team["tid"]),
    } for team in get_top_teams(gid=gid, eligible=eligible)]


# Custom statistics not necessarily to be served publicly


def bar():
    print("------------------")


def get_stats():
    bar()
    print("Average Eligible, Scoring Team Score: {0:.3f} +/- {1:.3f}".format(
        *get_average_eligible_score()))
    print("Median Eligible, Scoring Team Score: {0:.3f}".format(
        get_median_eligible_score()))
    bar()
    print(
        "Average Number of Problems Solved per Team (eligible, scoring): {0:.3f} +/- {1:.3f}".
        format(*get_average_problems_solved()))
    print(
        "Median Number of Problems Solved per Team (eligible, scoring): {:.3f}".
        format(get_median_problems_solved()))
    bar()
    user_breakdown = get_team_member_solve_stats()
    print(
        "Average Number of Problems Solved per User (eligible, user scoring): {0:.3f} +/- {1:.3f}".
        format(*get_average_problems_solved_per_user(
            user_breakdown=user_breakdown)))
    print(
        "Median Number of Problems Solved per User (eligible, user scoring): {:.3f}".
        format(
            get_median_problems_solved_per_user(user_breakdown=user_breakdown)))
    bar()
    print("Team participation averages:")
    correct_percent, any_percent = get_team_participation_percentage(
        user_breakdown=user_breakdown)
    for size in sorted(correct_percent.keys()):
        print(
            "\tTeam size: {0}\t{1:.3f} submitted a correct answer\t{2:.3f} submitted some answer".
            format(size, correct_percent[size], any_percent[size]))

    bar()
    print("User background breakdown:")
    for background, count in sorted(
            get_user_backgrounds().items(), key=lambda x: x[1], reverse=True):
        print("{0:30} {1}".format(background, count))
    bar()
    print("User country breakdown:")
    for country, count in sorted(
            get_user_countries().items(), key=lambda x: x[1],
            reverse=True)[0:15]:
        print("%s: %s" % (country, count))
    print("...")
    bar()
    print("Event ID breakdown:")
    for eventid, count in sorted(
            get_user_game_progress().items(), key=lambda x: x[0]):
        print("{0:60} {1}".format(eventid, count))
    bar()
    print("Average Achievement Number:")
    print("Average Number of Achievements per Team (all teams): %s +/- %s" %
          get_average_achievement_number())
    print("Achievement breakdown:")
    for achievement, count in sorted(
            get_achievement_frequency().items(), key=lambda x: x[1],
            reverse=True):
        print("{0:30} {1}".format(achievement, count))
    bar()
    print("Average # per category per eligible team")
    for cat, count in get_category_solves().items():
        print("{0:30} {1:.3f}".format(cat, count))
    bar()
    print("Number of days worked by teams")
    for number, count in get_days_active_breakdown(
            user_breakdown=user_breakdown).items():
        print("%s Days: %s Teams" % (number, count))
    bar()
    print("REVIEWS:")
    bar()
    review_data = get_review_stats()
    print("Problems by Reviewed Educational Value (10+ Reviews)")
    for problem in sorted(review_data, key=lambda x: x['education']):
        if problem['votes'] > 10:
            print(
                "{name:30} {education:.3f} ({votes} reviews)".format(**problem))
    bar()
    print("Problems by Reviewed Enjoyment (10+ Reviews)")
    for problem in sorted(review_data, key=lambda x: x['enjoyment']):
        if problem['votes'] > 10:
            print(
                "{name:30} {enjoyment:.3f} ({votes} reviews)".format(**problem))
    bar()
    print("Problems by Reviewed Difficulty (10+ Reviews)")
    for problem in sorted(review_data, key=lambda x: x['difficulty']):
        if problem['votes'] > 10:
            print("{name:30} {difficulty:.3f} ({votes} reviews)".format(
                **problem))
    bar()


def get_average_eligible_score():
    return (statistics.mean([x['score'] for x in get_all_team_scores()]),
            statistics.stdev([x['score'] for x in get_all_team_scores()]))


def get_median_eligible_score():
    return statistics.median([x['score'] for x in get_all_team_scores()])


def get_average_problems_solved(eligible=True, scoring=True):
    teams = api.team.get_all_teams(show_ineligible=(not eligible))
    values = [
        len(api.problem.get_solved_pids(tid=t['tid']))
        for t in teams
        if not scoring or len(api.problem.get_solved_pids(tid=t['tid'])) > 0
    ]
    return statistics.mean(values), statistics.stdev(values)


def get_median_problems_solved(eligible=True, scoring=True):
    teams = api.team.get_all_teams(show_ineligible=(not eligible))
    return statistics.median([
        len(api.problem.get_solved_pids(tid=t['tid']))
        for t in teams
        if not scoring or len(api.problem.get_solved_pids(tid=t['tid'])) > 0
    ])


def get_average_problems_solved_per_user(eligible=True,
                                         scoring=True,
                                         user_breakdown=None):
    if user_breakdown is None:
        user_breakdown = get_team_member_solve_stats(eligible)
    solves = []
    for tid, breakdown in user_breakdown.items():
        for uid, ubreakdown in breakdown.items():
            if ubreakdown is None:
                solved = 0
            else:
                if 'correct' in ubreakdown:
                    solved = ubreakdown['correct']
                else:
                    solved = 0
            if solved > 0 or not scoring:
                solves += [solved]
    return (statistics.mean(solves), statistics.stdev(solves))


def get_median_problems_solved_per_user(eligible=True,
                                        scoring=True,
                                        user_breakdown=None):
    if user_breakdown is None:
        user_breakdown = get_team_member_solve_stats(eligible)
    solves = []
    for tid, breakdown in user_breakdown.items():
        for uid, ubreakdown in breakdown.items():
            if ubreakdown is None:
                solved = 0
            else:
                if 'correct' in ubreakdown:
                    solved = ubreakdown['correct']
                else:
                    solved = 0
            if solved > 0 or not scoring:
                solves += [solved]
    return statistics.median(solves)


def get_user_backgrounds():
    db = api.api.common.get_conn()
    all_users = db.users.find()
    backgrounds = defaultdict(int)
    for user in all_users:
        if 'background' in user:
            backgrounds[user['background']] += 1
        else:
            print("No background for user %s" % user)
    return backgrounds


def get_user_countries():
    db = api.api.common.get_conn()
    all_users = db.users.find()
    countries = defaultdict(int)
    for user in all_users:
        countries[user['country']] += 1
    return countries


def get_team_size_distribution(eligible=True):
    teams = api.team.get_all_teams(show_ineligible=(not eligible))
    size_dist = defaultdict(int)
    for t in teams:
        members = api.team.get_team_members(tid=t['tid'], show_disabled=False)
        if len(members) > api.team.max_team_users:
            print("WARNING: Team %s has too many members" % t['team_name'])
        size_dist[len(members)] += 1
    return size_dist


def get_team_member_solve_stats(eligible=True):
    db = api.api.common.get_conn()
    teams = api.team.get_all_teams(show_ineligible=(not eligible))
    user_breakdowns = {}
    for t in teams:
        uid_map = defaultdict(lambda: defaultdict(int))
        members = api.team.get_team_members(tid=t['tid'], show_disabled=False)
        subs = db.submissions.find({'tid': t['tid']})
        for sub in subs:
            uid = sub['uid']
            uid_map[uid]['submits'] += 1
            if uid_map[uid]['times'] == 0:
                uid_map[uid]['times'] = list()
            uid_map[uid]['times'].append(sub['timestamp'])
            if sub['correct']:
                uid_map[uid]['correct'] += 1
                uid_map[uid][sub['category']] += 1
            else:
                uid_map[uid]['incorrect'] += 1
        user_breakdowns[t['tid']] = uid_map
        for member in members:
            if member['uid'] not in uid_map:
                uid_map[uid] = None
    return user_breakdowns


def get_team_participation_percentage(eligible=True, user_breakdown=None):
    if user_breakdown is None:
        user_breakdown = get_team_member_solve_stats(eligible)
    team_size_any = defaultdict(list)
    team_size_correct = defaultdict(list)
    for tid, breakdown in user_breakdown.items():
        count_any = 0
        count_correct = 0
        for uid, work in breakdown.items():
            if work is not None:
                count_any += 1
                if work['correct'] > 0:
                    count_correct += 1
        team_size_any[len(breakdown.keys())].append(count_any)
        team_size_correct[len(breakdown.keys())].append(count_correct)
    return {x: statistics.mean(y) for x, y in team_size_any.items()}, \
           {x: statistics.mean(y) for x, y in team_size_correct.items()}


def get_achievement_frequency():
    earned_achievements = api.achievement.get_earned_achievement_instances()
    frequency = defaultdict(int)
    for achievement in earned_achievements:
        frequency[achievement['name']] += 1
    return frequency


def get_average_achievement_number():
    earned_achievements = api.achievement.get_earned_achievement_instances()
    frequency = defaultdict(int)
    for achievement in earned_achievements:
        frequency[achievement['uid']] += 1
    extra = len(api.team.get_all_teams(show_ineligible=False)) - len(
        frequency.keys())
    values = [0] * extra
    for val in frequency.values():
        values.append(val)
    return statistics.mean(values), statistics.stdev(values)


def get_category_solves(eligible=True):
    teams = api.team.get_all_teams(show_ineligible=(not eligible))
    category_breakdown = defaultdict(int)
    for team in teams:
        problems = api.problem.get_solved_problems(tid=team['tid'])
        for problem in problems:
            category_breakdown[problem['category']] += 1
    team_count = len(api.team.get_all_teams(show_ineligible=False))
    return {x: y / team_count for x, y in category_breakdown.items()}


def get_days_active_breakdown(eligible=True, user_breakdown=None):
    if user_breakdown is None:
        user_breakdown = get_team_member_solve_stats(eligible)
    day_breakdown = defaultdict(int)
    for tid, breakdown in user_breakdown.items():
        days_active = set()
        for uid, work in breakdown.items():
            if work is None:
                continue
            for time in work['times']:
                days_active.add(time.date())
        day_breakdown[len(days_active)] += 1
    return day_breakdown


@api.cache.memoize(timeout=300)
def check_invalid_instance_submissions(gid=None):
    db = api.api.common.get_conn()
    badteams = set()
    shared_key_submissions = []

    group = None
    if gid is not None:
        group = api.group.get_group(gid=gid)

    for problem in api.problem.get_all_problems(show_disabled=True):
        valid_keys = [instance['flag'] for instance in problem['instances']]
        incorrect_submissions = db.submissions.find({
            'pid': problem['pid'],
            'correct': False
        }, {"_id": 0})
        for submission in incorrect_submissions:
            if submission['key'] in valid_keys:
                # make sure that the key is still invalid
                if not api.problem.grade_problem(
                        submission['pid'], submission['key'],
                        tid=submission['tid'])['correct']:
                    if group is None or submission['tid'] in group['members']:
                        submission['username'] = api.user.get_user(
                            uid=submission['uid'])['username']
                        submission["problem_name"] = problem["name"]
                        shared_key_submissions.append(submission)

    return shared_key_submissions


def get_review_stats():
    results = []
    problems = api.problem.get_all_problems()
    for p in problems:
        timespent = 0
        enjoyment = 0
        difficulty = 0
        edval = 0
        counter = 0
        for item in api.problem_feedback.get_problem_feedback(pid=p['pid']):
            counter += 1
            metrics = item['feedback']['metrics']
            edval += metrics['educational-value']
            difficulty += metrics['difficulty']
            enjoyment += metrics['enjoyment']
            timespent += item['feedback']['timeSpent']
        if counter > 0:
            results.append({
                'name': p['name'],
                'education': edval / counter,
                'difficulty': difficulty / counter,
                'enjoyment': enjoyment / counter,
                'time': timespent / counter,
                'votes': counter
            })
    return results


def print_review_comments():
    problems = api.problem.get_all_problems()
    for p in problems:
        comments = []
        for item in api.problem_feedback.get_problem_feedback(pid=p['pid']):
            comment = item['feedback']['comment']
            if len(comment.strip()) > 0:
                comments.append(comment.strip())
        if len(comments) > 0:
            print("")
            print("")
            print(p['name'])
            print("----------")
            for comment in comments:
                print("'%s'" % comment)
