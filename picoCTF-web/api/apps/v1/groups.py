"""Group (a.k.a Classroom) management."""
import base64
import csv
import io
import string

import api
from api import (block_before_competition, check_csrf, PicoException,
                 rate_limit, require_login, require_teacher)
from bs4 import UnicodeDammit
from flask import jsonify
from flask_restplus import Namespace, Resource
from marshmallow import (fields, post_load, pre_load, RAISE, Schema, validate,
                         validates_schema, ValidationError)

from .schemas import (batch_registration_req, group_invite_req,
                      group_modify_team_req, group_patch_req, group_req,
                      score_progressions_req, scoreboard_page_req)

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
    @rate_limit(limit=20, duration=10)
    @ns.response(201, 'Classroom added')
    @ns.response(400, 'Error parsing request')
    @ns.response(401, 'Not logged in')
    @ns.response(403, 'You do not have permission to create a classroom ' +
                      'or CSRF token invalid')
    @ns.response(409, 'You already have a classroom with that name')
    @ns.response(429, 'Too many requests, slow down!')
    @ns.expect(group_req)
    def post(self):
        """Create a new group."""
        req = group_req.parse_args(strict=True)
        curr_user = api.user.get_user()

        # Don't create group if teacher already has one with same name
        if api.group.get_group(
                name=req['name'], owner_tid=curr_user['tid']) is not None:
            raise PicoException(
                'You already have a classroom with that name', 409)
        if not all([
                c in string.digits + string.ascii_lowercase + " ()-,#'&"
                for c in req['name'].lower()]):
            raise PicoException(
                "Classroom names cannot contain special characters other " +
                "than ()-,#'&", status_code=400
            )

        # Make sure this teacher hasn't already created the max no. of groups
        db = api.db.get_conn()
        created_group_count = db.groups.count_documents(
            {'owner': curr_user['tid']})
        settings = api.config.get_settings()
        if (created_group_count >= settings['group_limit']
                and not curr_user.get('admin', False)):
            raise PicoException(
                'You have created the maximum number of classrooms. ' +
                'Please contact an administrator for assistance.',
                status_code=403
            )

        gid = api.group.create_group(curr_user['tid'], req['name'])
        res = jsonify({
            'success': True,
            'gid': gid
        })
        res.status_code = 201
        return res


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied')
@ns.response(404, 'Classroom not found')
@ns.route('/<string:group_id>')
class Group(Resource):
    """Get a specific group."""

    def get(self, group_id):
        """Get a specific group."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)

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

    @ns.response(400, 'Error parsing request')
    @ns.response(403, 'CSRF token incorrect')
    @ns.response(422, 'Cannot make a previously hidden classroom public')
    @ns.expect(group_patch_req)
    def patch(self, group_id):
        """Modify a group's settings (other fields are not available)."""
        req = group_patch_req.parse_args(strict=True)

        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] not in ([group['owner']] + group['teachers'])
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to modify this classroom.', 403
            )

        api.group.change_group_settings(group_id, req['settings'])
        return jsonify({
            'success': True
        })

    @check_csrf
    def delete(self, group_id):
        """Delete a group. Must be the owner of the group."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] != group['owner']
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to delete this classroom.', 403
            )
        tids_in_group = set()
        tids_in_group.update(group['members'])
        tids_in_group.update(group['teachers'])
        tids_in_group.add(group['owner'])
        for tid in tids_in_group:
            api.cache.invalidate(api.team.get_groups, tid)
        api.group.delete_group(group_id)
        return jsonify({
            'success': True
        })


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied or CSRF token invalid')
@ns.response(404, 'Classroom not found')
@ns.response(422, 'Specified team is not a member of the classroom')
@ns.route('/<string:group_id>/elevate_team')
class ElevateTeamResponse(Resource):
    """Elevate a team the teacher role within a group."""

    @check_csrf
    @require_login
    @ns.expect(group_modify_team_req)
    def post(self, group_id):
        """
        Elevate a specified team within a group to the teacher role.

        Requires teacher role within the group.
        """
        req = group_modify_team_req.parse_args(strict=True)
        group = api.group.get_group(group_id)
        if not group:
            raise PicoException('Classroom not found', 404)
        group_teachers = [group['owner']] + group['teachers']
        eligible_for_elevation = group['members']
        curr_tid = api.user.get_user()['tid']

        # Ensure the current user has a teacher role within the group
        if curr_tid not in group_teachers:
            raise PicoException(
                'You must be a teacher in this classroom to remove a team.',
                status_code=403
            )

        # Ensure the specified tid is eligible for elevation
        if req['team_id'] not in eligible_for_elevation:
            raise PicoException(
                'Team is not eligible for elevation to teacher role',
                status_code=422
            )

        api.group.elevate_team(group_id, req['team_id'])
        return jsonify({
            'success': True
        })


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied or CSRF token invalid')
@ns.response(404, 'Classroom not found')
@ns.response(422, 'Specified team is not a member of the classroom')
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
            raise PicoException('Classroom not found', 404)
        eligible_for_removal = group['members'] + group['teachers']
        curr_tid = api.user.get_user()['tid']

        if curr_tid not in eligible_for_removal:
            raise PicoException(
                'Team is not eligible for removal from this classroom',
                status_code=422
            )
        api.group.leave_group(group_id, curr_tid)
        return jsonify({
            'success': True
        })

    @check_csrf
    @require_login
    @ns.expect(group_modify_team_req)
    def post(self, group_id):
        """
        Remove a specified team from a group.

        Requires teacher role within the group.
        """
        req = group_modify_team_req.parse_args(strict=True)
        group = api.group.get_group(group_id)
        if not group:
            raise PicoException('Classroom not found', 404)
        group_teachers = [group['owner']] + group['teachers']
        eligible_for_removal = group['members'] + group['teachers']
        curr_tid = api.user.get_user()['tid']

        # Ensure the user has a teacher role within the group
        if curr_tid not in group_teachers:
            raise PicoException(
                'You must be a teacher in this classroom to remove a team.',
                status_code=403
            )

        # Ensure the specified tid is a member of the group
        if req['team_id'] not in eligible_for_removal:
            raise PicoException(
                'Team is not eligible for removal from this classroom',
                status_code=422
            )

        api.group.leave_group(group_id, req['team_id'])
        return jsonify({
            'success': True
        })


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied')
@ns.response(404, 'Classroom not found')
@ns.route('/<string:group_id>/flag_sharing')
class FlagSharingInfo(Resource):
    """Get flag sharing statistics for a specific group."""

    def get(self, group_id):
        """Get flag sharing statistics for a specific group."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] not in (group['teachers'] + [group['owner']])
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to view these statistics.', 403
            )

        return jsonify(
            api.stats.check_shared_group_submissions(group['gid']))


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied')
@ns.response(404, 'Classroom not found')
@ns.route('/<string:group_id>/invite')
class InviteResponse(Resource):
    """Send an email invite to join this team."""

    @rate_limit(limit=1, duration=30)
    @ns.response(429, 'Too many requests, slow down!')
    @ns.expect(group_invite_req)
    def post(self, group_id):
        """Send an email invite to join this team."""
        req = group_invite_req.parse_args(strict=True)
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] not in (group['teachers'] + [group['owner']])
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to invite members to ' +
                'this classroom.', status_code=403
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

    @rate_limit(limit=1, duration=30)
    @ns.response(200, 'Success')
    @ns.response(400, 'Error parsing CSV')
    @ns.response(401, 'Not logged in')
    @ns.response(403, 'Permission denied')
    @ns.response(404, 'Classroom not found')
    @ns.response(429, 'Too many requests, slow down!')
    @ns.expect(batch_registration_req)
    def post(self, group_id):
        """Automatically registers several student accounts based on a CSV."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)

        curr_user = api.user.get_user()
        if (curr_user['tid'] not in (group['teachers'] + [group['owner']])
                and not curr_user['admin']):
            raise PicoException(
                'You do not have permission to batch-register students into ' +
                'this classroom.', status_code=403
            )

        # Load in student demographics from CSV
        req = batch_registration_req.parse_args(strict=True)
        students = []
        unicoded_csv = UnicodeDammit(req['csv'].read())
        csv_reader = csv.DictReader(
            unicoded_csv.unicode_markup.split('\n'))
        try:
            for row in csv_reader:
                students.append(row)
        except csv.Error as e:
            raise PicoException(
                f"Error reading CSV at line {csv_reader.line_num}: {e}",
                status_code=400)

        # Check whether registering these students would exceed maximum
        # batch registrations per teacher account
        config = api.config.get_settings()
        teacher_metadata = api.token.find_key({
            'uid': api.user.get_user()['uid']
        })
        if not teacher_metadata:
            existing_batch_count = 0
        else:
            existing_batch_count = teacher_metadata.get(
                "tokens", {}).get('batch_registered_students', 0)
        potential_batch_count = existing_batch_count + len(students)
        if (potential_batch_count > config['max_batch_registrations']):
            raise PicoException(
                "You have exceeded the maximum number of batch-registered " +
                "student accounts. Please contact an administrator.", 403
            )

        # Validate demographics
        def validate_current_year(s):
            try:
                n = int(s)
                if not (1 <= n <= 12):
                    raise ValueError
            except ValueError:
                raise ValidationError(
                    f'Grade must be between 1 and 12 (provided {s})')

        class BatchRegistrationUserSchema(Schema):
            # Convert empty strings to Nones when doing validation,
            # but back before storing in database.
            @pre_load
            def empty_to_none(self, in_data, **kwargs):
                for k, v in in_data.items():
                    if v == "":
                        in_data[k] = None
                return in_data

            @post_load
            def none_to_empty(self, in_data, **kwargs):
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
                    ['male', 'female', 'nb/gf', 'nl/no'],
                    ['Male', 'Female', 'Non-Binary/Gender-Fluid',
                     'Not listed/Prefer not to answer'],
                    error="If specified, must be one of {labels}. Please use "
                          "the corresponding code from: {choices}."
                )
            )
            parent_email = fields.Email(
                data_key='Parent Email (if under 18)', required=True,
                allow_none=True
            )
            @validates_schema
            def validate_parent_email(self, data,  **kwargs):
                if (data['age'] == '13-17' and
                        data['parent_email'] is None):
                    raise ValidationError(
                        'Parent email must be specified for students under 18')

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

        output = []
        for i in range(len(students)):
            output.append({
                'Grade (1-12)': students[i]['current_year'],
                'Age (13-17 or 18+)': students[i]['age'],
                'Gender': students[i]['gender'],
                'Parent Email (if under 18)': students[i]['parent_email'],
                'Username': created_accounts[i]['username'],
                'Password': created_accounts[i]['password']
            })

        buffer = io.StringIO()
        csv_writer = csv.DictWriter(buffer, [
            'Grade (1-12)',
            'Age (13-17 or 18+)',
            'Gender',
            'Parent Email (if under 18)',
            'Username',
            'Password'
        ])
        csv_writer.writeheader()
        csv_writer.writerows(output)
        output_csv_bytes = buffer.getvalue().encode('utf-8')

        return jsonify({
            'success': True,
            'accounts': created_accounts,
            'as_csv': base64.b64encode(output_csv_bytes).decode('utf-8')
        })


@ns.route('/<string:group_id>/scoreboard')
class ScoreboardPage(Resource):
    """
    Get a scoreboard page for a group.

    If a page is not specified, will attempt to return the page containing the
    current team, falling back to the first page if neccessary.
    """

    @block_before_competition
    @ns.response(200, 'Success')
    @ns.response(403, 'Permission denied')
    @ns.response(404, 'Classroom not found')
    @ns.response(422, 'Competition has not started')
    @ns.expect(scoreboard_page_req)
    def get(self, group_id):
        """Retrieve a scoreboard page for a group."""
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)
        group_members = [group['owner']] + group['members'] + group['teachers']

        curr_user = api.user.get_user()
        if (not curr_user or (curr_user['tid'] not in group_members
                              and not curr_user['admin'])):
            raise PicoException("You do not have permission to " +
                                "view this classroom's scoreboard.", 403)

        req = scoreboard_page_req.parse_args(strict=True)
        if req['search'] is not None:
            page = api.stats.get_filtered_scoreboard_page(
                {'group_id': group_id},
                req['search'], req['page'] or 1
            )
        else:
            page = api.stats.get_scoreboard_page(
                {'group_id': group_id}, req['page'])
        return jsonify({
            'scoreboard': page[0],
            'current_page': page[1],
            'total_pages': page[2]
        })


@ns.route('/<string:group_id>/score_progressions')
class ScoreProgressionsResult(Resource):
    """Get a list of score progressions for the top n teams in a group."""

    @block_before_competition
    @ns.response(200, 'Success')
    @ns.response(403, 'Permission denied')
    @ns.response(404, 'Classroom not found')
    @ns.response(422, 'Competition has not started')
    @ns.expect(score_progressions_req)
    def get(self, group_id):
        """Get a list of teams' score progressions."""
        req = score_progressions_req.parse_args(strict=True)
        group = api.group.get_group(gid=group_id)
        if not group:
            raise PicoException('Classroom not found', 404)
        group_members = [group['owner']] + group['members'] + group['teachers']

        if (not api.user.is_logged_in() or (
                api.user.get_user()['tid'] not in group_members
                and not api.user.get_user()['admin'])):
            raise PicoException("You do not have permission to view this " +
                                "classroom's score progressions.", 403)
        if req['limit'] and (
                not api.user.is_logged_in()
                or not api.user.get_user()['admin']):
            raise PicoException('Must be admin to specify limit', 403)
        return jsonify(
            api.stats.get_top_teams_score_progressions(
                limit=(req['limit'] or 5), group_id=group_id
            ))
