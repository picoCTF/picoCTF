"""Team management module."""

from pymongo.collation import Collation, CollationStrength
from voluptuous import Length, Required, Schema

import api
from api import cache, check, log_action, PicoException
from api.cache import memoize
from api.stats import check_shared_submissions

PROBLEMSOLVED_FILTER = ['category', 'name', 'score', 'solve_time']

new_team_schema = Schema({
    Required("team_name"):
    check(
        ("The team name must be between 3 and 40 characters.",
         [str, Length(min=3, max=40)]),
        ("This team name conflicts with an existing user name.",
         [lambda name: api.user.get_user(name=name) is None]),
        ("A team with that name already exists.",
         [lambda name: api.team.get_team(name=name) is None]),
    ),
    Required("team_password"):
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
    db = api.db.get_conn()

    match = {}
    if tid is not None:
        match.update({'tid': tid})
    elif name is not None:
        match.update({'team_name': name})
    elif api.user.is_logged_in():
        match.update({"tid": api.user.get_user()["tid"]})
    else:
        return None

    return db.teams.find_one(match, {"_id": 0})


def update_team(tid, updates):
    """
    Update a team with new properties.

    Args:
        tid: the tid of the team to update
        updates: dict of updated properties

    Returns:
        tid of the updated team (unchanged), or
        None if the team was not found

    """
    db = api.db.get_conn()
    if len(updates) > 0:
        success = db.teams.find_one_and_update(
            {'tid': tid}, {'$set': updates})
        if not success:
            return None
    return tid


@memoize(timeout=5*24*60*60)
def get_groups(tid):
    """
    Get the group membership for a team.

    Args:
        tid: The team id
    Returns:
        List of group objects the team is a member of.
    """
    # Get all groups associated with the given team
    db = api.db.get_conn()
    associated_groups = list(db.groups.find(
        {"$or": [
            {'owner': tid},
            {"teachers": tid},
            {"members": tid}]},
        {
            'name': 1,
            'gid': 1,
            'owner': 1,
            'teachers': 1,
            'members': 1,
            '_id': 0
        }))

    for group in associated_groups:
        # Replace the owner tid with the team's name
        group['owner'] = api.team.get_team(tid=group['owner'])['team_name']

        # Add the group's average score - WHY???
        # group['score'] = api.stats.get_group_average_score(gid=group['gid'])

    return associated_groups


def create_and_join_new_team(team_name, team_password, user):
    """
    Fulfill new team requests for users who have already registered.

    Seperate from create_team() as we need to do additional logic:
    - Check that the new team name doesn't conflict with a team or user
    - Check that the user creating the team is on their initial
      1-person "username team"

    Args:
        team_name: The desired name for the team.
                   Must be unique across users and teams.
        team_password: The team's password.
        user: The user

    Returns:
        The tid of the new team

    Raises:
        PicoException if a team or user with name team_name already exists,
                      or if user has already created a team

    """
    # Ensure name does not conflict with existing user or team
    db = api.db.get_conn()
    if db.users.find_one({
        'username': team_name
    }, collation=Collation(locale="en", strength=CollationStrength.PRIMARY)):
        raise PicoException(
            'There is already a user with this name.', 409)
    if db.teams.find_one({
        'team_name': team_name
    }, collation=Collation(locale="en", strength=CollationStrength.PRIMARY)):
        raise PicoException(
            'There is already a team with this name.', 409)

    # Make sure the creating user has not already created a team
    current_team = api.team.get_team(tid=user['tid'])
    if current_team['team_name'] != user['username']:
        raise PicoException(
            "You can only create one new team per user account!", 422)

    # Create the team and join it
    new_tid = create_team({
        "team_name": team_name,
        "password": api.common.hash_password(team_password),
        "affiliation": current_team["affiliation"],
        "creator": user["uid"],
        "allow_ineligible_members": False
    })
    join_team(team_name, team_password, user)

    return new_tid


def create_team(params):
    """
    Directly insert team into the database.

    Assumes all fields have been validated.

    Args:
        params:
            team_name: Name of the team
            password: team's hashed password
            affiliation: team's affiliation
    Returns:
        The newly created team id.
    """
    db = api.db.get_conn()

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
    Retrieve the members on a team.

    Args:
        tid: the team id to query
        name: the team name to query
    Returns:
        A list of the team's members.
    """
    db = api.db.get_conn()

    tid = get_team(name=name, tid=tid)["tid"]

    users = list(
        db.users.find({"tid": tid}, {
            "_id": 0,
            "uid": 1,
            "username": 1,
            "firstname": 1,
            "lastname": 1,
            "disabled": 1,
            "email": 1,
            "teacher": 1,
            "country": 1,
            "usertype": 1,
        }))
    return [
        user for user in users
        if show_disabled or not user.get("disabled", False)
    ]


def get_team_uids(tid=None, name=None, show_disabled=True):
    """
    Get the list of uids that belong to a team.

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


def get_team_information(tid):
    """
    Retrieve the information of a team.

    Args:
        tid: the team id
    Returns:
        A dict of team information.
            team_name
            members
    """
    team_info = get_team(tid=tid)

    # Sanitize
    team_info.pop("password", None)
    team_info.pop("instances", None)

    # @TODO there is a LOT of stuff being added here - expensive. all needed?
    #       ideally combine/replace this w/ get_team()
    # Add additional information
    team_info["score"] = api.stats.get_score(tid=tid, time_weighted=False)
    team_info["members"] = [{
        "username": member["username"],
        "firstname": member["firstname"],
        "lastname": member["lastname"],
        "email": member["email"],
        "uid": member["uid"],
        "affiliation": member.get("affiliation", "None"),
        "country": member["country"],
        "usertype": member["usertype"],
    } for member in get_team_members(tid=tid, show_disabled=False)]
    team_info["progression"] = api.stats.get_score_progression(tid=tid)
    team_info["flagged_submissions"] = check_shared_submissions(tid=tid)
    team_info["max_team_size"] = api.config.get_settings()["max_team_size"]

    if api.config.get_settings()["achievements"]["enable_achievements"]:
        team_info["achievements"] = api.achievement.get_earned_achievements(
            tid)

    team_info["solved_problems"] = []
    for solved_problem in api.problem.get_solved_problems(tid=tid):
        filtered_problem = {k: v for k, v in solved_problem.items() if
                            k in PROBLEMSOLVED_FILTER}
        team_info["solved_problems"].append(filtered_problem)

    return team_info


def get_all_teams(scoreboard_id=None):
    """
    Retrieve all teams.

    Args:
        scoreboard_id: optional, find only teams eligible for this scoreboard

    Returns:
        A list of all matching teams.

    """
    # Ignore empty teams (remnants of single player self-team ids)
    db = api.db.get_conn()
    match = {"size": {"$gt": 0}}

    # If specified, restrict to teams eligible for a certain scoreboard
    if scoreboard_id:
        match['eligibilities'] = scoreboard_id

    return list(db.teams.find(match, {"_id": 0}))


def join_team(team_name, password, user):
    """
    Switch a user from their individual team to a proper team.

    You can not use this to freely switch between teams.

    Args:
        team_name: The name of the team to join
        password: The new team's password
        user: The user
    Returns:
        ID of the new team
    """
    current_team = api.user.get_team(uid=user["uid"])
    desired_team = api.team.get_team(name=team_name)
    desired_team_info = api.team.get_team_information(desired_team['tid'])

    if current_team["team_name"] != user["username"]:
        raise PicoException(
            "You can not switch teams once you have joined one.", 403)

    # Make sure the password is correct and there is room on the team
    max_team_size = api.config.get_settings()["max_team_size"]
    if desired_team['size'] >= max_team_size:
        raise PicoException(
            'That team is already at maximum capacity.', 403)
    if not api.user.confirm_password(password, desired_team["password"]):
        raise PicoException(
            'That is not the correct password to join that team.', 403)

    # Update the team's eligibilities
    if desired_team_info['size'] == 0:
        updated_eligible_scoreboards = [
            scoreboard for scoreboard in api.scoreboards.get_all_scoreboards()
            if api.scoreboards.is_eligible(user, scoreboard)
        ]
    else:
        currently_eligible_scoreboards = [
            api.scoreboards.get_scoreboard(sid)
            for sid in desired_team_info['eligibilities']
        ]
        updated_eligible_scoreboards = [
            scoreboard for scoreboard in currently_eligible_scoreboards
            if api.scoreboards.is_eligible(user, scoreboard)
        ]
        lost_eligibilities = [
            scoreboard for scoreboard in currently_eligible_scoreboards
            if scoreboard not in updated_eligible_scoreboards
        ]
        if (len(lost_eligibilities) > 0 and
                not desired_team_info.get('allow_ineligible_members', False)):
            raise PicoException(
                'You cannot join this team as doing so would make it ' +
                'ineligible for the {} scoreboard.'.format(
                    lost_eligibilities[0]["name"]
                ), 403
            )

    # Join the new team
    db = api.db.get_conn()
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
        raise PicoException("There was an issue switching your team!")

    # Update the eligiblities of the new team
    db.teams.find_one_and_update(
        {"tid": desired_team["tid"]},
        {"$set": {
            "eligibilities": [s['sid'] for s in updated_eligible_scoreboards]
        }}
    )

    # Update the sizes of the old and new teams
    db.teams.find_one_and_update(
        {"tid": desired_team["tid"]},
        {"$inc": {
            "size": 1
        }})

    db.teams.find_one_and_update(
        {"tid": current_team["tid"]},
        {"$inc": {
            "size": -1
        }})

    # Remove old team from any groups and attempt to add new team
    previous_groups = get_groups(current_team['tid'])
    for group in previous_groups:
        api.group.leave_group(gid=group["gid"], tid=current_team["tid"])
        # Rejoin with new tid if not already member, and classroom
        # email filter is not enabled.
        if (desired_team['tid'] not in group['members'] and
                desired_team['tid'] not in group['teachers']):
            group_settings = api.group.get_group_settings(gid=group["gid"])
            if not group_settings["email_filter"]:
                api.group.join_group(
                    gid=group["gid"], tid=desired_team["tid"])

    # Immediately invalidate some caches
    cache.invalidate(api.stats.get_score, desired_team['tid'])
    cache.invalidate(api.stats.get_score, user['uid'])
    cache.invalidate(api.problem.get_unlocked_pids, desired_team['tid'])
    cache.invalidate(
        api.problem.get_solved_problems,
        tid=desired_team['tid'],
        uid=user['uid'],
        category=None)
    cache.invalidate(
        api.problem.get_solved_problems,
        tid=desired_team['tid'],
        uid=None,
        category=None
    )
    cache.invalidate(
        api.problem.get_solved_problems,
        tid=desired_team['tid'],
        uid=user['uid'])
    cache.invalidate(api.problem.get_solved_problems, tid=desired_team['tid'])
    cache.invalidate(api.problem.get_solved_problems, uid=user['uid'])
    cache.invalidate(
        api.stats.get_score_progression, tid=desired_team['tid'], category=None)
    cache.invalidate(api.stats.get_score_progression, tid=desired_team['tid'])

    return desired_team['tid']


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
    user = api.user.get_user()
    current_team = api.team.get_team(tid=user["tid"])
    if current_team["team_name"] == user["username"]:
        raise PicoException("You have not created a team yet.", 422)

    if params["new-password"] != params["new-password-confirmation"]:
        raise PicoException("Your team passwords do not match.", 422)

    db = api.db.get_conn()
    db.teams.update(
        {'tid': user['tid']},
        {'$set': {
            'password': api.common.hash_password(
                params["new-password"])
        }})


def is_teacher_team(tid):
    """Check if team is a teacher's self-team."""
    team = get_team(tid=tid)
    members = get_team_members(tid=tid)
    if (team["size"] == 1 and members[0]["username"] == team["team_name"] and
            members[0]["teacher"]):
        return True
    else:
        return False
