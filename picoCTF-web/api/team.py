"""
API functions relating to team management.
"""

import api
from api.annotations import log_action
from api.common import (check, InternalException, safe_fail,
                        SevereInternalException, validate, WebException)
from voluptuous import Length, Required, Schema

new_team_schema = Schema(
    {
        Required("team_name"):
        check(
            ("The team name must be between 3 and 40 characters.",
             [str, Length(min=3, max=40)]),
            ("This team name conflicts with an existing user name.",
             [lambda name: safe_fail(api.user.get_user, name=name) is None]),
            ("A team with that name already exists.",
             [lambda name: safe_fail(api.team.get_team, name=name) is None]),
        ),
        Required("team_password"):
        check(("Passwords must be between 3 and 20 characters.",
               [str, Length(min=3, max=20)]))
    },
    extra=True)

join_team_schema = Schema(
    {
        Required("team_name"):
        check(
            ("The team name must be between 3 and 40 characters.",
               [str, Length(min=3, max=40)]),
            ("This team name conflicts with an existing user name.",
             [lambda name: safe_fail(api.user.get_user, name=name) is None]),
        ),
        Required("team_password"):
        check(("Passwords must be between 3 and 20 characters.",
               [str, Length(min=3, max=20)]))
    },
    extra=True)

update_team_schema = Schema(
    {
        Required("new-password"):
        check(("Passwords must be between 3 and 20 characters.",
               [str, Length(min=3, max=20)]))
    },
    extra=True)


def get_team(tid=None, name=None):
    """
    Retrieve a team based on a property (tid, name, etc.).

    Args:
        tid: team id
        name: team name
    Returns:
        Returns the corresponding team object or None if it could not be found
    """

    db = api.api.common.get_conn()

    match = {}
    if tid is not None:
        match.update({'tid': tid})
    elif name is not None:
        match.update({'team_name': name})
    elif api.auth.is_logged_in():
        match.update({"tid": api.user.get_user()["tid"]})
    else:
        raise InternalException("Must supply tid or team name to get_team")

    team = db.teams.find_one(match, {"_id": 0})

    if team is None:
        raise InternalException("Team does not exist.")

    return team


def get_groups(tid=None, uid=None):
    """
    Get the group membership for a team.

    Args:
        tid: The team id
        uid: The user id
    Returns:
        List of group objects the team is a member of.
    """

    db = api.common.get_conn()

    groups = []

    group_projection = {'name': 1, 'gid': 1, 'owner': 1, 'members': 1, '_id': 0}

    admin = False

    if uid is not None:
        user = api.user.get_user(uid=uid)
        # Given potential scale of *all* classrooms, DISABLED
        # admin = api.user.is_admin(uid=user["uid"])
        tid = user["tid"]
    else:
        tid = api.team.get_team(tid=tid)["tid"]

    # (DISABLED) Admins should be able to view all groups.
    group_query = {
        "$or": [{
            'owner': tid
        }, {
            "teachers": tid
        }, {
            "members": tid
        }]
    } if not admin else {}
    associated_groups = db.groups.find(group_query, group_projection)

    for group in list(associated_groups):
        owner = api.team.get_team(tid=group['owner'])['team_name']
        groups.append({
            'name':
            group['name'],
            'gid':
            group['gid'],
            'members':
            group['members'],
            'owner':
            owner,
            'score':
            api.stats.get_group_average_score(gid=group['gid'])
        })

    return groups


def create_new_team_request(params, uid=None):
    """
    Fulfills new team requests for users who have already registered.

    Args:
        team_name: The desired name for the team. Must be unique across users and teams.
        team_password: The team's password.
    Returns:
        True if successful, exception thrown otherwise.
    """

    user = api.user.get_user(uid=uid)
    if user["teacher"]:
        raise InternalException("Teachers may not create teams!")

    validate(new_team_schema, params)

    current_team = api.team.get_team(tid=user["tid"])

    if current_team["team_name"] != user["username"]:
        raise InternalException(
            "You can only create one new team per user account!")

    desired_tid = create_team({
        "team_name": params["team_name"],
        "password": api.common.hash_password(params["team_password"]),
        "affiliation": current_team["affiliation"],
        "eligible": user["eligible"],
        "creator": user["uid"],
        "country": user["country"],
    })

    return join_team(params["team_name"], params["team_password"], user["uid"])


def create_team(params):
    """
    Directly inserts team into the database. Assumes all fields have been validated.

    Args:
        team_name: Name of the team
        school: Name of the school
        password: Team's hashed password
        eligible: the teams eligibility, inherited from creator
        country: primary country of team
        creator: uid of creating user
    Returns:
        The newly created team id.
    """

    db = api.common.get_conn()

    params['tid'] = api.common.token()
    params['size'] = 0
    params['instances'] = {}

    settings = api.config.get_settings()
    if settings["shell_servers"]["enable_sharding"]:
        params['server_number'] = api.shell_servers.get_assigned_server_number(
            new_team=True)

    db.teams.insert(params)

    return params['tid']


def get_team_members(tid=None, name=None, show_disabled=True):
    """
    Retrieves the members on a team.

    Args:
        tid: the team id to query
        name: the team name to query
    Returns:
        A list of the team's members.
    """

    db = api.common.get_conn()

    tid = get_team(name=name, tid=tid)["tid"]

    users = list(
        db.users.find({
            "tid": tid
        }, {
            "_id": 0,
            "uid": 1,
            "username": 1,
            "disabled": 1,
            "email": 1,
            "teacher": 1,
            "country": 1,
            "usertype": 1,
            "eligible": 1,
        }))
    return [
        user for user in users
        if show_disabled or not user.get("disabled", False)
    ]


def get_team_uids(tid=None, name=None, show_disabled=True):
    """
    Gets the list of uids that belong to a team

    Args:
        tid: the team id
        name: the team name
    Returns:
        A list of uids
    """

    return [
        user['uid'] for user in get_team_members(
            tid=tid, name=name, show_disabled=show_disabled)
    ]


def get_team_information(tid=None, gid=None):
    """
    Retrieves the information of a team.

    Args:
        tid: the team id
    Returns:
        A dict of team information.
            team_name
            members
    """

    team_info = get_team(tid=tid)

    if tid is None:
        tid = team_info["tid"]

    if gid is not None:
        group = api.group.get_group(gid=gid)
        roles = api.group.get_roles_in_group(group["gid"], tid=tid)

    team_info["score"] = api.stats.get_score(tid=tid)
    team_info["members"] = [{
        "username": member["username"],
        "email": member["email"],
        "uid": member["uid"],
        "affiliation": member.get("affiliation", "None"),
        "country": member["country"],
        "usertype": member["usertype"],
    } for member in get_team_members(tid=tid, show_disabled=False)]
    team_info["competition_active"] = api.utilities.check_competition_active()
    team_info["progression"] = api.stats.get_score_progression(tid=tid)
    team_info["flagged_submissions"] = [
        sub for sub in api.stats.check_invalid_instance_submissions()
        if sub['tid'] == tid
    ]
    team_info["max_team_size"] = api.config.get_settings()["max_team_size"]

    if api.config.get_settings()["achievements"]["enable_achievements"]:
        team_info["achievements"] = api.achievement.get_earned_achievements(
            tid=tid)

    team_info["solved_problems"] = []
    for solved_problem in api.problem.get_solved_problems(tid=tid):
        solved_problem.pop("instances", None)
        solved_problem.pop("pkg_dependencies", None)
        team_info["solved_problems"].append(solved_problem)

    return team_info


def get_all_teams(ineligible=False, eligible=True, country=None, show_ineligible=False):
    """
    Retrieves all teams.

    Returns:
        A list of all of the teams.
    """

    if show_ineligible:
        match = {}
    else:
        conditions = []
        if ineligible:
            conditions.append({"eligible": False})
        elif eligible:
            conditions.append({"eligible": True})
        match = {"$or": conditions}

    if country is not None:
        match.update({"country": country})

    # Ignore empty teams (remnants of single player self-team ids)
    match.update({"size": {"$gt": 0}})

    db = api.common.get_conn()
    return list(db.teams.find(match, {"_id": 0}))


def join_team_request(params):
    """
    Validate and process a join_team request.

    Args:
        team_name
        team_password
    """

    user = api.user.get_user()
    if user["teacher"]:
        raise InternalException("Teachers may not join teams!")

    validate(join_team_schema, params)

    return join_team(params["team_name"], params["team_password"])


def join_team(team_name, password, uid=None):
    """
    Allow a user who is on an individual team to join a proper team. You can not use this to freely switch between teams.

    Args:
        team_name: The name of the team to join.
        password: The team's password.
        uid: The user's id.
    """

    user = api.user.get_user(uid=uid)
    current_team = api.user.get_team(uid=user["uid"])

    desired_team = api.team.get_team(name=team_name)

    if current_team["team_name"] != user["username"]:
        raise InternalException(
            "You can not switch teams once you have joined one.")

    db = api.common.get_conn()
    max_team_size = api.config.get_settings()["max_team_size"]

    if api.auth.confirm_password(password, desired_team["password"]
                                ) and desired_team["size"] < max_team_size:
        user_team_update = db.users.find_and_modify(
            query={
                "uid": user["uid"],
                "tid": current_team["tid"]
            },
            update={"$set": {
                "tid": desired_team["tid"]
            }},
            new=True)

        if not user_team_update:
            raise InternalException("There was an issue switching your team!")

        desired_team_size_update = db.teams.find_and_modify(
            query={
                "tid": desired_team["tid"],
                "size": {
                    "$lt": max_team_size
                }
            },
            update={"$inc": {
                "size": 1
            }},
            new=True)

        current_team_size_update = db.teams.find_and_modify(
            query={
                "tid": current_team["tid"],
                "size": {
                    "$gt": 0
                }
            },
            update={"$inc": {
                "size": -1
            }},
            new=True)

        # Team country is no longer consistent amongst members. Flag as mixed and ineligible
        if user["country"] != desired_team["country"]:
            db.teams.update({"tid": desired_team["tid"]}, {"$set": {"country": "??",
                                                                    "eligible": False}})

        # Ineligible user has spoiled team eligibility
        if not user["eligible"] and desired_team["eligible"]:
            db.teams.update({"tid": desired_team["tid"]}, {"$set": {"eligible": False}})

        if not desired_team_size_update or not current_team_size_update:
            raise InternalException(
                "There was an issue switching your team! Please contact an administrator."
            )

        # Remove membership of empty self-team.
        previous_groups = get_groups(tid=current_team["tid"])
        for group in previous_groups:
            api.group.leave_group(gid=group["gid"], tid=current_team["tid"])
            # Rejoin with new tid if not already member, and classroom
            # email filter is not enabled.
            roles = api.group.get_roles_in_group(group["gid"], tid=desired_team["tid"])
            if not roles["teacher"] and not roles["member"]:
                group_settings = api.group.get_group_settings(gid=group["gid"])
                if not group_settings["email_filter"]:
                        api.group.join_group(gid=group["gid"], tid=desired_team["tid"])


        # Called from within get_solved_problems, clear first
        api.cache.invalidate_memoization(api.problem.get_unlocked_pids,
                                         {"args": [desired_team["tid"]]})

        # Clear solved
        api.cache.invalidate_memoization(api.problem.get_solved_problems,
                                         {"kwargs.tid": desired_team["tid"]},
                                         {"kwargs.uid": uid})

        # Make sure team score is reflected as well
        api.cache.invalidate_memoization(api.stats.get_score,
                                         {"kwargs.tid": desired_team["tid"]})

        # Update score progression
        api.cache.invalidate_memoization(api.stats.get_score_progression,
                                         {"kwargs.tid": desired_team["tid"]})

        return True
    else:
        raise InternalException(
            "That is not the correct password to join that team.")


@log_action
def update_password_request(params):
    """
    Update team password.
    Assumes args are keys in params.

    Args:
        params:
            new-password: the new password
            new-password-confirmation: confirmation of password
    """

    validate(update_team_schema, params)
    user = api.user.get_user()
    current_team = api.team.get_team(tid=user["tid"])
    if current_team["team_name"] == user["username"]:
        raise WebException("You have not created a team yet.")

    if params["new-password"] != params["new-password-confirmation"]:
        raise WebException("Your team passwords do not match.")

    if len(params["new-password"]) == 0:
        raise WebException("Your team password cannot be empty.")

    update_password(user["tid"], params["new-password"])


def update_password(tid, password):
    """
    Updates a team's password.

    Args:
        tid: teams's uid.
        password: the new user password.
    """

    db = api.common.get_conn()
    db.teams.update({
        'tid': tid
    }, {'$set': {
        'password': api.common.hash_password(password)
    }})


def is_teacher_team(tid):
    """
     Checks if team is a teacher's self-team
    """
    team = get_team(tid=tid)
    members = get_team_members(tid=tid)
    if team["size"] == 1 and members[0]["username"] == team["team_name"] and members[0]["teacher"]:
        return True
    else:
        return False
