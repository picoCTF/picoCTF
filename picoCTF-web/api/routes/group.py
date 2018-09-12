import json

import api
from api.annotations import (api_wrapper, block_after_competition,
                             block_before_competition, check_csrf, log_action,
                             require_admin, require_login, require_teacher)
from api.common import (check, safe_fail, validate, WebError, WebException,
                        WebSuccess)
from flask import (Blueprint, Flask, render_template, request,
                   send_from_directory, session)
from voluptuous import Length, Required, Schema

register_group_schema = Schema({
    Required("group-name"):
    check(("Class name must be between 3 and 50 characters.",
           [str, Length(min=3, max=100)]),)
},
                               extra=True)

join_group_schema = Schema({
    Required("group-name"):
    check(("Class name must be between 3 and 50 characters.",
           [str, Length(min=3, max=100)]),),
    Required("group-owner"):
    check(("The team name must be between 3 and 40 characters.",
           [str, Length(min=3, max=40)]),)
},
                           extra=True)

leave_group_schema = Schema({
    Required("group-name"):
    check(("Class name must be between 3 and 50 characters.",
           [str, Length(min=3, max=100)]),),
    Required("group-owner"):
    check(("The team name must be between 3 and 40 characters.",
           [str, Length(min=3, max=40)]),)
},
                            extra=True)

delete_group_schema = Schema({
    Required("group-name"):
    check(("Class name must be between 3 and 50 characters.",
           [str, Length(min=3, max=100)]),)
},
                             extra=True)

blueprint = Blueprint("group_api", __name__)


@blueprint.route('', methods=['GET'])
@api_wrapper
@require_login
def get_group_hook():
    name = request.form.get("group-name")
    owner = request.form.get("group-owner")
    gid = request.form.get("gid")

    owner_tid = None
    if not gid or len(gid) == 0:
        owner_tid = api.team.get_team(name=owner)["tid"]

    group = api.group.get_group(gid=gid, name=name, owner_tid=owner_tid)

    user = api.user.get_user()
    roles = api.group.get_roles_in_group(gid=group["gid"], uid=user["uid"])

    if not roles["member"] and not roles["teacher"]:
        return WebError("You are not a member of this group.")

    return WebSuccess(data=group)


@blueprint.route('/settings', methods=['GET'])
@api_wrapper
def get_group_settings_hook():
    gid = request.args.get("gid")
    group = api.group.get_group(gid=gid)

    prepared_data = {
        "name": group["name"],
        "settings": api.group.get_group_settings(gid=group["gid"])
    }

    return WebSuccess(data=prepared_data)


@blueprint.route('/settings', methods=['POST'])
@api_wrapper
@require_teacher
def change_group_settings_hook():
    gid = request.form.get("gid")
    settings = json.loads(request.form.get("settings"))

    user = api.user.get_user()
    group = api.group.get_group(gid=gid)

    roles = api.group.get_roles_in_group(gid=group["gid"], uid=user["uid"])

    if roles["teacher"]:
        api.group.change_group_settings(group["gid"], settings)
        return WebSuccess(message="Group settings changed successfully.")
    else:
        return WebError(
            message="You do not have sufficient privilege to do that.")


@blueprint.route('/invite', methods=['POST'])
@api_wrapper
@require_teacher
def invite_email_to_group_hook():
    gid = request.form.get("gid")
    email = request.form.get("email")
    role = request.form.get("role")

    user = api.user.get_user()

    if gid is None or email is None or len(email) == 0:
        return WebError(
            message="You must specify a gid and email address to invite.")

    if role not in ["member", "teacher"]:
        return WebError(message="A user's role is either a member or teacher.")

    group = api.group.get_group(gid=gid)
    roles = api.group.get_roles_in_group(group["gid"], uid=user["uid"])

    if roles["teacher"]:
        api.email.send_email_invite(
            group["gid"], email, teacher=(role == "teacher"))
        return WebSuccess(message="Email invitation has been sent.")
    else:
        return WebError(
            message="You do not have sufficient privilege to do that.")


@blueprint.route('/list')
@api_wrapper
@require_login
def get_group_list_hook():
    user = api.user.get_user()
    return WebSuccess(data=api.team.get_groups(uid=user["uid"]))


@blueprint.route('/teacher_information', methods=['GET'])
@api_wrapper
@require_teacher
def get_teacher_information_hook(gid=None):
    gid = request.args.get("gid")

    user = api.user.get_user()
    roles = api.group.get_roles_in_group(gid, uid=user["uid"])

    if not roles["teacher"]:
        return WebError("You are not a teacher for this group.")

    return WebSuccess(data=api.group.get_teacher_information(gid=gid))


@blueprint.route('/member_information', methods=['GET'])
@api_wrapper
@require_teacher
def get_member_information_hook(gid=None):
    gid = request.args.get("gid")

    user = api.user.get_user()
    roles = api.group.get_roles_in_group(gid, uid=user["uid"])

    if not roles["teacher"]:
        return WebError("You are not a teacher for this group.")

    return WebSuccess(data=api.group.get_member_information(gid=gid))


@blueprint.route('/score', methods=['GET'])
@api_wrapper
@require_teacher
def get_group_score_hook():
    name = request.args.get("group-name")

    user = api.user.get_user()
    roles = api.group.get_roles_in_group(gid, uid=user["uid"])

    if not roles["teacher"]:
        return WebError("You are not a teacher for this group.")

    score = api.stats.get_group_scores(name=name)
    if score is None:
        return WebError("There was an error retrieving the group's score.")

    return WebSuccess(data={'score': score})


@blueprint.route('/create', methods=['POST'])
@api_wrapper
@check_csrf
@require_admin
def create_group_hook():
    """
    Creates a new group. Validates forms.
    All required arguments are assumed to be keys in params.
    """

    params = api.common.flat_multi(request.form)
    validate(register_group_schema, params)

    # Current user is the prospective owner.
    team = api.user.get_team()

    if safe_fail(
            api.group.get_group, name=params["group-name"],
            owner_tid=team["tid"]) is not None:
        raise WebException("A group with that name already exists!")

    gid = api.group.create_group(team["tid"], params["group-name"])
    return WebSuccess("Successfully created group.", data=gid)


@blueprint.route('/join', methods=['POST'])
@api_wrapper
@check_csrf
@require_login
def join_group_hook():
    """
    Tries to place a team into a group. Validates forms.
    All required arguments are assumed to be keys in params.
    """

    params = api.common.flat_multi(request.form)
    validate(join_group_schema, params)

    owner_team = api.team.get_team(name=params["group-owner"])

    if safe_fail(
            api.group.get_group,
            name=params["group-name"],
            owner_tid=owner_team["tid"]) is None:
        raise WebException("No class exists with that name!")

    group = api.group.get_group(
        name=params["group-name"], owner_tid=owner_team["tid"])

    group_settings = api.group.get_group_settings(gid=group["gid"])

    team = api.team.get_team()
    for member_uid in api.team.get_team_uids(tid=team["tid"]):
        member = api.user.get_user(uid=member_uid)
        if not api.user.verify_email_in_whitelist(
                member["email"], group_settings["email_filter"]):
            raise WebException(
                "{}'s email does not belong to the whitelist for that group. Your team may not join this group at this time."
                .format(member["username"]))

    roles = api.group.get_roles_in_group(group["gid"], tid=team["tid"])
    if roles["teacher"] or roles["member"]:
        raise WebException("Your team is already a member of that class!")

    api.group.join_group(group["gid"], team["tid"])

    return WebSuccess("Successfully joined group")


@blueprint.route('/leave', methods=['POST'])
@api_wrapper
@check_csrf
@require_login
def leave_group_hook():
    """
    Tries to remove a team from a group. Validates forms.
    All required arguments are assumed to be keys in params.
    """

    params = api.common.flat_multi(request.form)

    validate(leave_group_schema, params)
    owner_team = api.team.get_team(name=params["group-owner"])

    group = api.group.get_group(
        name=params["group-name"], owner_tid=owner_team["tid"])

    team = api.user.get_team()
    roles = api.group.get_roles_in_group(group["gid"], tid=team["tid"])

    if not roles["member"] and not roles["teacher"]:
        raise WebException("Your team is not a member of that class!")

    api.group.leave_group(group["gid"], team["tid"])

    return WebSuccess("Successfully left group.")


@blueprint.route('/delete', methods=['POST'])
@api_wrapper
@check_csrf
@require_teacher
def delete_group_hook():
    """
    Tries to delete a group. Validates forms.
    All required arguments are assumed to be keys in params.
    """

    params = api.common.flat_multi(request.form)

    validate(delete_group_schema, params)

    if params.get("group-owner"):
        owner_team = api.team.get_team(name=params["group-owner"])
    else:
        owner_team = api.team.get_team()

    group = api.group.get_group(
        name=params["group-name"], owner_tid=owner_team["tid"])

    user = api.user.get_user()
    roles = api.group.get_roles_in_group(group["gid"], uid=user["uid"])

    if roles["owner"]:
        api.group.delete_group(group["gid"])
    else:
        raise WebException("Only the owner of a group can delete it!")

    return WebSuccess("Successfully deleted group")


@blueprint.route('/flag_sharing', methods=['GET'])
@api_wrapper
@require_teacher
def get_flag_shares():
    gid = request.args.get("gid", None)

    if gid is None:
        return WebError(
            "You must specify a gid when looking at flag sharing statistics.")

    user = api.user.get_user()
    roles = api.group.get_roles_in_group(gid, uid=user["uid"])
    if not roles["teacher"]:
        return WebError(
            "You must be a teacher of a group to see its flag sharing statistics."
        )

    return WebSuccess(
        data=api.stats.check_invalid_instance_submissions(gid=gid))


@blueprint.route('/teacher/leave', methods=['POST'])
@api_wrapper
@check_csrf
@require_teacher
def force_leave_group_hook():
    gid = request.form.get("gid")
    tid = request.form.get("tid")

    if gid is None or tid is None:
        return WebError("You must specify a gid and tid.")

    user = api.user.get_user()
    roles = api.group.get_roles_in_group(gid, uid=user["uid"])
    if not roles["teacher"]:
        return WebError("You must be a teacher of a group to remove a team.")

    api.group.leave_group(gid, tid)

    return WebSuccess("Team has successfully left the group.")


@blueprint.route('/teacher/role_switch', methods=['POST'])
@api_wrapper
@require_teacher
def switch_user_role_group_hook():
    gid = request.form.get("gid")
    tid = request.form.get("tid")
    role = request.form.get("role")

    user = api.user.get_user()

    if gid is None or tid is None:
        return WebError(
            message="You must specify a gid and tid to perform a role switch.")

    if role not in ["member", "teacher"]:
        return WebError(message="A user's role is either a member or teacher.")

    group = api.group.get_group(gid=gid)

    roles = api.group.get_roles_in_group(group["gid"], uid=user["uid"])
    if not roles["teacher"]:
        return WebError(
            message="You do not have sufficient privilege to do that.")

    affected_team = api.team.get_team(tid=tid)
    affected_team_roles = api.group.get_roles_in_group(
        group["gid"], tid=affected_team["tid"])
    if affected_team_roles["owner"]:
        return WebError(
            message="You can not change the role of the owner of the group.")

    api.group.switch_role(group["gid"], affected_team["tid"], role)
    return WebSuccess(message="User's role has been successfully changed.")
