"""Group manangement."""
import csv
import string

from flask import jsonify
from flask_restplus import Namespace, Resource
from marshmallow import (fields, post_load, pre_load, RAISE, Schema, validate,
                         ValidationError)

import api
from api import check_csrf, PicoException, require_login, require_teacher

from .schemas import (batch_registration_req, group_invite_req,
                      group_patch_req, group_remove_team_req, group_req)

ns = Namespace('groups', description='Group management')


@ns.route('')
class GroupList(Resource):
    """Get the list of your groups, or create a new group."""

    @require_login
    @ns.response(200, 'Success')
    @ns.response(401, 'Not logged in')
    def get(self):
        """Get the groups of which you are a member."""
        curr_tid = api.user.get_user()['tid']
        return jsonify(api.team.get_groups(curr_tid))

    @check_csrf
    @require_teacher
    @ns.response(201, 'Group added')
    @ns.response(400, 'Error parsing request')
    @ns.response(401, 'Not logged in')
    @ns.response(403, 'You do not have permission to create a group ' +
                      'or CSRF token invalid')
    @ns.response(409, 'You already have a group with that name')
    @ns.expect(group_req)
    def post(self):
        """Create a new group."""
        req = group_req.parse_args(strict=True)
        curr_tid = api.user.get_user()['tid']

        # Don't create group if teacher already has one with same name
        if api.group.get_group(
                name=req['name'], owner_tid=curr_tid) is not None:
            raise PicoException(
                'You already have a classroom with that name', 409)
        if not all([
                c in string.digits + string.ascii_lowercase + " ()-,#'&"
                for c in req['name'].lower()]):
            raise PicoException(
                "Classroom names cannot contain special characters other than"+
                "()-,#'&", status_code=400
            )

        gid = api.group.create_group(curr_tid, req['name'])
        res = jsonify({
            'success': True,
            'gid': gid
        })
        res.status_code = 201
        return res


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied')
@ns.response(404, 'Group not found')
@ns.route('/<string:group_id>')
class Group(Resource):
    """Get a specific group."""

    def get(self, group_id):
        """Get a specific group."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Group not found', 404)

        group_members = [group['owner']] + group['members'] + group['teachers']
        group_teachers = [group['owner']] + group['teachers']
        if not api.user.is_logged_in():
            # Return group name and settings even if not a member.
            # Used for group invite links.
            return jsonify({
                'name': group['name'],
                'settings': group['settings']
            })
        curr_user = api.user.get_user()
        if curr_user['tid'] not in group_members and not curr_user['admin']:
            return jsonify({
                'name': group['name'],
                'settings': group['settings']
            })

        # Replace the team ids with full team objects if teacher, else remove
        if curr_user['tid'] in group_teachers:
            full_teachers = []
            for tid in group['teachers']:
                full_teachers.append(api.team.get_team_information(tid))
            group['teachers'] = full_teachers
            full_members = []
            for tid in group['members']:
                full_members.append(api.team.get_team_information(tid))
            group['members'] = full_members
        else:
            group.pop('teachers')
            group.pop('members')

        return jsonify(group)

    @require_teacher
    @ns.response(400, 'Error parsing request')
    @ns.response(403, 'CSRF token incorrect')
    @ns.response(422, 'Cannot make a previously hidden group public')
    @ns.expect(group_patch_req)
    def patch(self, group_id):
        """Modify a group's settings (other fields are not available)."""
        req = group_patch_req.parse_args(strict=True)

        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Group not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] not in ([group['owner']] + group['teachers'])
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to modify this group.', 403
            )

        api.group.change_group_settings(group_id, req['settings'])
        return jsonify({
            'success': True
        })

    @check_csrf
    @require_teacher
    def delete(self, group_id):
        """Delete a group. Must be the owner of the group."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Group not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] != group['owner']
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to delete this group.', 403
            )

        api.group.delete_group(group_id)
        return jsonify({
            'success': True
        })


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied or CSRF token invalid')
@ns.response(404, 'Group not found')
@ns.response(422, 'Specified team is not a member of the group')
@ns.route('/<string:group_id>/remove_team')
class RemoveTeamResponse(Resource):
    """
    Remove a team from a group.

    If the specified team is not your own, requires teacher role within
    the group.
    """

    @check_csrf
    @require_login
    def get(self, group_id):
        """Remove your own team from this group."""
        group = api.group.get_group(group_id)
        if not group:
            raise PicoException('Group not found', 404)
        eligible_for_removal = group['members'] + group['teachers']
        curr_tid = api.user.get_user()['tid']

        if curr_tid not in eligible_for_removal:
            raise PicoException(
                'Specified team is not eligible for removal from this group',
                status_code=422
            )
        api.group.leave_group(group_id, curr_tid)
        return jsonify({
            'success': True
        })

    @check_csrf
    @require_login
    @ns.expect(group_remove_team_req)
    def post(self, group_id):
        """
        Remove a specified team from a group.

        Requires teacher role within the group.
        """
        req = group_remove_team_req.parse_args(strict=True)
        group = api.group.get_group(group_id)
        if not group:
            raise PicoException('Group not found', 404)
        group_teachers = [group['owner']] + group['teachers']
        eligible_for_removal = group['members'] + group['teachers']
        curr_tid = api.user.get_user()['tid']

        # Ensure the user has a teacher role within the group
        if curr_tid not in group_teachers:
            raise PicoException(
                'You must be a teacher in this group to remove a team.',
                status_code=403
            )

        # Ensure the specified tid is a member of the group
        if req['team_id'] not in eligible_for_removal:
            raise PicoException(
                'Specified team is not eligible for removal from this group',
                status_code=422
            )

        api.group.leave_group(group_id, req['team_id'])
        return jsonify({
            'success': True
        })


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied')
@ns.response(404, 'Group not found')
@ns.route('/<string:group_id>/flag_sharing')
class FlagSharingInfo(Resource):
    """Get flag sharing statistics for a specific group."""

    @require_teacher
    def get(self, group_id):
        """Get flag sharing statistics for a specific group."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Group not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] not in (group['teachers'] + [group['owner']])
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to view these statistics.', 403
            )

        return jsonify(
            api.stats.check_invalid_instance_submissions(group['gid']))


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied')
@ns.response(404, 'Group not found')
@ns.route('/<string:group_id>/invite')
class InviteResponse(Resource):
    """Send an email invite to join this team."""

    @require_teacher
    @ns.expect(group_invite_req)
    def post(self, group_id):
        """Send an email invite to join this team."""
        req = group_invite_req.parse_args(strict=True)
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Group not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] not in (group['teachers'] + [group['owner']])
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to invite members to this group.',
                status_code=403
            )

        api.email.send_email_invite(group_id, req['email'],
                                    req['as_teacher'])
        return jsonify({
            'success': True
            })


@ns.route('/<string:group_id>/batch_registration')
class BatchRegistrationResponse(Resource):
    """
    Register multiple student accounts and assign them to this group.

    Demographics for the registered accounts are provided via CSV upload.
    """

    @require_teacher
    @ns.response(200, 'Success')
    @ns.response(401, 'Not logged in')
    @ns.response(403, 'Permission denied')
    @ns.response(404, 'Group not found')
    @ns.expect(batch_registration_req)
    def post(self, group_id):
        """Automatically registers several student accounts based on a CSV."""
        # Load in student demographics from CSV
        req = batch_registration_req.parse_args(strict=True)
        students = []
        csv_reader = csv.DictReader(
            req['csv'].read().decode('utf-8').split('\n'))
        try:
            for row in csv_reader:
                students.append(row)
        except csv.Error as e:
            raise PicoException(
                f"Error reading CSV at line {csv_reader.line_num}: {e}",
                status_code=400)

        # Validate demographics
        def validate_current_year(s):
            n = int(s)
            if not (1 <= n <= 12):
                raise ValidationError(
                    f'Grade must be between 1 and 12 (provided {s})')

        class BatchRegistrationUserSchema(Schema):
            # Convert empty strings to Nones when doing validation,
            # but back before storing in database.
            @pre_load
            def empty_to_none(self, in_data):
                for k, v in in_data.items():
                    if v == "":
                        in_data[k] = None
                return in_data

            @post_load
            def none_to_empty(self, in_data):
                for k, v in in_data.items():
                    if v is None:
                        in_data[k] = ''
                return in_data
            current_year = fields.Str(
                data_key='Grade (1-12)',
                required=True,
                validate=validate_current_year)
            age = fields.Str(
                data_key='Age (13-17 or 18+)', required=True,
                validate=validate.OneOf(choices=['13-17', '18+']))
            gender = fields.Str(
                data_key="Gender", required=False, allow_none=True,
                validate=validate.OneOf(
                    ['man', 'woman', 'transgenderman', 'transgenderwoman',
                     'gfnc'],
                    ['Man', 'Woman', 'Transgender Man', 'Transgender Woman',
                     'Gender Fluid/Non-Conforming'],
                    error="If specified, must be one of {labels}. Please use "
                          "the corresponding code from: {choices}."
                )
            )

        try:
            students = BatchRegistrationUserSchema().load(
                students, many=True, unknown=RAISE)
        except ValidationError as err:
            raise PicoException(err.messages, status_code=400)

        # Batch-register accounts
        curr_teacher = api.user.get_user()
        created_accounts = api.group.batch_register(
            students, curr_teacher, group_id)

        if len(created_accounts) != len(students):
            raise PicoException(
                "An error occurred while adding student accounts. " +
                f"The first {len(created_accounts)} were created. " +
                "Please contact an administrator."
            )
        return jsonify({
            'success': True,
            'accounts': created_accounts
        })
