"""Validation schemas for API requests."""
import werkzeug.datastructures
from flask_restplus import inputs
import api.reqparse as reqparse


def object_type(value):
    """To make the openAPI object type show up in the docs."""
    return value
object_type.__schema__ = {'type': 'object'} # noqa


def length_restricted(min_length, max_length, base_type):
    """Type to restrict string length."""
    def validate(s):
        if len(s) < min_length:
            raise ValueError(
                "Must be at least %i characters long" % min_length)
        if len(s) > max_length:
            raise ValueError(
                "Must be at most %i characters long" % max_length)
        return s
    return validate


# Achievement request schema
achievement_req = reqparse.RequestParser()
achievement_req.add_argument(
    'name', required=True, type=str, location='json',
    help='Name of the achievement.',
    error='Achievement name is required')
achievement_req.add_argument(
    'score', required=True, type=inputs.natural, location='json',
    help='Point value of the achievement (positive integer).',
    error='The achievement\'s score must be a positive integer')
achievement_req.add_argument(
    'description', required=True, type=str, location='json',
    help='Description of the achievement.',
    error='Achievement description is required')
achievement_req.add_argument(
    'processor', required=True, type=str, location='json',
    help='Path to the achievement processor.',
    error='Achievement processor path is required')
achievement_req.add_argument(
    'hidden', required=True, type=inputs.boolean, location='json',
    help='Hide this achievement?',
    error='Specify whether this achievement should be hidden (true/false)')
achievement_req.add_argument(
    'image', required=True, type=str, location='json',
    help='Path to achievement image.',
    error='Achievement image path is required')
achievement_req.add_argument(
    'smallimage', required=True, type=str, location='json',
    help='Path to achievement thumbnail.',
    error='Achievement thumbnail path is required')
achievement_req.add_argument(
    'disabled', required=True, type=inputs.boolean, location='json',
    help='Disable this achievement?',
    error='Specify whether this achievement should be disabled (true/false)')
achievement_req.add_argument(
    'multiple', required=True, type=inputs.boolean, location='json',
    help='Allow earning multiple instances of this achievement?',
    error='Specify whether this achievement can be earned multiple times ' +
          '(true/false)')
achievement_patch_req = achievement_req.copy()
for arg in achievement_patch_req.args:
    arg.required = False

# Shell server output schema
# (This is too complex for reqparse to really handle, so we'll trust it.
#  If we move to another validation engine e.g. marshmallow, we can revisit.)
shell_server_out = reqparse.RequestParser()
shell_server_out.add_argument(
    'sid', required=True, type=str, location='args',
    help='Shell server ID.',
    error='Shell server ID is required')
shell_server_out.add_argument(
    'problems', required=False, type=list, location='json',
    error='Problems array is invalid')
shell_server_out.add_argument(
    'bundles', required=False, type=list, location='json',
    error='Bundles array is invalid')

# Problem PATCH request schema
# ("disabled" is the only mutable field as the others are managed by the
#  shell manager.)
problem_patch_req = reqparse.RequestParser()
problem_patch_req.add_argument(
    'disabled', required=True, type=inputs.boolean, location='json',
    help='Whether the problem is disabled.',
    error='Specify whether the problem is disabled'
)

# Shell server list request schema
shell_server_list_req = reqparse.RequestParser()
shell_server_list_req.add_argument(
    'assigned_only', required=False, type=inputs.boolean, default=True,
    location='args',
    help='Whether to include only shell servers assigned to the' +
         ' current user. Must be admin to disable.',
    error='Specify a boolean value for assigned_only'
)

# Shell server request schema
shell_server_req = reqparse.RequestParser()
shell_server_req.add_argument(
    'name', required=True, type=str, location='json',
    help='Shell server display name.',
    error='Shell server display name is required')
shell_server_req.add_argument(
    'host', required=True, type=str, location='json',
    help='Shell server hostname.',
    error='Shell server hostname is required')
shell_server_req.add_argument(
    'port', required=True, type=inputs.int_range(1, 65535), location='json',
    help='Shell server port.',
    error='Shell server port is required (1-65535)')
shell_server_req.add_argument(
    'username', required=True, type=str, location='json',
    help='Username.',
    error='Shell server username is required')
shell_server_req.add_argument(
    'password', required=True, type=str, location='json',
    help='Password.',
    error='Shell server password is required')
shell_server_req.add_argument(
    'protocol', required=True, type=str, choices=['HTTP', 'HTTPS'],
    location='json',
    help='Protocol used to serve web resources.',
    error='Shell server protocol is required (HTTP/HTTPS)'
)
shell_server_req.add_argument(
    'server_number', required=False, type=inputs.positive, location='json',
    help='Server number (will be automatically assigned if not provided).',
    error='Shell server number must be a positive integer')
shell_server_patch_req = shell_server_req.copy()
for arg in shell_server_patch_req.args:
    arg.required = False

# Shell server reassignment schema
shell_server_reassignment_req = reqparse.RequestParser()
shell_server_reassignment_req.add_argument(
    'include_assigned', required=False, type=inputs.boolean, location='json',
    help="Whether to update the assignments of teams that already have " +
         "an assigned shell server.",
    error='Specify a boolean value for include_assigned'
)

# Exception request schema
exception_req = reqparse.RequestParser()
exception_req.add_argument(
    'result_limit', required=False, type=inputs.positive, default=50,
    location='args', help='Maximum number of exceptions to return',
    error='result_limit must be a positive integer'
)

# Settings update schema
# @TODO: this is very basic - config.py:change_settings() does the brunt of
# the validation work for now because of RequestParser's limitations
# regarding nested fields. Revisit this when upgrading to a
# better validation library.
settings_patch_req = reqparse.RequestParser()
settings_patch_req.add_argument(
    'enable_feedback', required=False, type=inputs.boolean, location='json',
    error='enable_feedback must be a boolean'
)
settings_patch_req.add_argument(
    'start_time', required=False, type=inputs.datetime_from_iso8601,
    location='json',
    error='start_time must be an ISO 8601 timestamp'
)
settings_patch_req.add_argument(
    'end_time', required=False, type=inputs.datetime_from_iso8601,
    location='json',
    error='end_time must be an ISO 8601 timestamp'
)
settings_patch_req.add_argument(
    'competition_name', required=False, type=str, location='json',
    error='competition_name must be a string'
)
settings_patch_req.add_argument(
    'competition_url', required=False, type=str, location='json',
    error='competition_url must be a string'
)
settings_patch_req.add_argument(
    'email_filter', required=False, type=list, location='json'
)
settings_patch_req.add_argument(
    'max_team_size', required=False, type=inputs.natural, location='json',
    error='max_team_size must be a positive integer'
)
settings_patch_req.add_argument(
    'achievements', required=False, type=object_type, location='json'
)
settings_patch_req.add_argument(
    'username_blacklist', required=False, type=list, location='json'
)
settings_patch_req.add_argument(
    'email', required=False, type=object_type, location='json'
)
settings_patch_req.add_argument(
    'captcha', required=False, type=object_type, location='json'
)
settings_patch_req.add_argument(
    'logging', required=False, type=object_type, location='json'
)
settings_patch_req.add_argument(
    'shell_servers', required=False, type=object_type, location='json'
)
settings_patch_req.add_argument(
    'eligibility', required=False, type=object_type, location='json'
)

# Bundle PATCH request schema
# ("dependencies_enabled" is the only mutable field as the others are managed
#  by the shell manager.)
bundle_patch_req = reqparse.RequestParser()
bundle_patch_req.add_argument(
    'dependencies_enabled', required=True, type=inputs.boolean,
    location='json',
    help="Whether to consider this bundle's dependencies when determining " +
         "unlocked problems.",
    error='Specify a boolean value for dependencies_enabled'
)

# Optional parameters for problems request
problems_req = reqparse.RequestParser()
problems_req.add_argument(
    'unlocked_only', required=False, location='args', default=True,
    help='Whether to display only problems unlocked for your team or ' +
         'all matching problems. Must be teacher/admin to disable, unless ' +
         'count_only=True. ' +
         'If disabled as a teacher account, will only return name, ' +
         'category, and score for each problem.',
    type=inputs.boolean,
    error='Specify a boolean value for unlocked_only'
)
problems_req.add_argument(
    'solved_only', required=False, location='args', default=False,
    help='Restrict results to problems solved by your team.',
    type=inputs.boolean,
    error='Specify a boolean value for solved_only'
)
problems_req.add_argument(
    'count_only', required=False, location='args', default=False,
    help='Whether to return only the count of matching problems.',
    type=inputs.boolean,
    error='Specify a boolean value for count_only'
)
problems_req.add_argument(
    'category', required=False, location='args', default=None,
    help='Restrict results to a specific category.', type=str,
    error='Category to filter on must be a string'
)
problems_req.add_argument(
    'include_disabled', required=False, location='args', default=False,
    help='Whether to include disabled problems.', type=inputs.boolean,
    error='Specify a boolean value for include_disabled'
)

# Submission request
submission_req = reqparse.RequestParser()
submission_req.add_argument(
    'pid', required=True, type=str, location='json',
    help='ID of the attempted problem',
    error='Problem ID is required'
)
submission_req.add_argument(
    'key', required=True, type=str, location='json',
    help='Flag for the problem',
    error='Flag is required'
)
submission_req.add_argument(
    'method', required=True, type=str, location='json',
    help='Submission method, e.g. "game"',
    error='Submission method is required'
)

# Feedback list request
feedback_list_req = reqparse.RequestParser()
feedback_list_req.add_argument(
    'pid', required=False, type=str, location='args',
    help='Filter feedback by this problem ID only',
    error='pid field must be a string'
)
feedback_list_req.add_argument(
    'uid', required=False, type=str, location='args',
    help='Filter feedback by this user ID only',
    error='uid field must be a string'
)
feedback_list_req.add_argument(
    'tid', required=False, type=str, location='args',
    help='Filter feedback by this team ID only',
    error='tid field must be a string'
)

# Feedback submission request
feedback_submission_req = reqparse.RequestParser()
feedback_submission_req.add_argument(
    'pid', required=True, type=str, help='Reviewed problem ID',
    location='json',
    error='Problem ID is required'
)
# @TODO validate this at request time - for now see problem_feedback.py
feedback_submission_req.add_argument(
    'feedback', required=True, type=object_type, help='Problem feedback',
    location='json',
    error='Feedback object required'
)

# New user request
user_req = reqparse.RequestParser()
user_req.add_argument(
    'email', required=True, type=inputs.regex(r".+@.+\..{2,}"),
    location='json', help='Email address',
    error='Email address is not valid'
)
user_req.add_argument(
    'firstname', required=False, type=length_restricted(1, 50, str),
    location='json', help='Given name', default='',
    error='First name is not valid (50 characters max)'
)
user_req.add_argument(
    'lastname', required=False, type=length_restricted(1, 50, str),
    location='json', help='Family name', default='',
    error='Last name is not valid (50 characters max)'
)
user_req.add_argument(
    'username', required=True, type=length_restricted(3, 20, str),
    location='json', help='Username',
    error='Username is not valid (must be 3-20 characters)'
)
user_req.add_argument(
    'password', required=True, type=length_restricted(3, 20, str),
    location='json', help='Password',
    error='Password is not valid (must be 3-20 characters)'
)
user_req.add_argument(
    'affiliation', required=True, type=length_restricted(3, 50, str),
    location='json', help='e.g. school or organization',
    error='School or organization name is not valid (must be 3-50 characters)'
)
user_req.add_argument(
    'usertype', required=True, type=str,
    choices=['student', 'college', 'teacher', 'other'],
    location='json', help='User type',
    error='Invalid user type'
)
user_req.add_argument(
    'country', required=True, type=length_restricted(2, 2, str),
    location='json', help='2-letter country code',
    error='Country is invalid (must be 2-letter country code)'
)
# @TODO validate nested fields
user_req.add_argument(
    'demo', required=True, type=object_type,
    location='json', help='Demographic information (parentemail, age)',
    error='Demographics fields are required'
)
user_req.add_argument(
    'gid', required=False, type=str, location='json',
    help='Group ID (optional, to automatically enroll in group)',
    error='gid field must be a string'
)
user_req.add_argument(
    'rid', required=False, type=str, location='json',
    help='Registration ID (optional, to automatically enroll in group)',
    error='rid field must be a string'
)
user_req.add_argument(
    'g-recaptcha-response', required=False, location='json',
    help='reCAPTCHA response, required if reCAPTCHA enabled in settings'
)

# Login request
login_req = reqparse.RequestParser()
login_req.add_argument(
    'username', required=True, type=str, help='Username', location='json',
    error='Username is required'
)
login_req.add_argument(
    'password', required=True, type=str, help='Password', location='json',
    error='Password is required'
)

# User extdata update request
user_extdata_req = reqparse.RequestParser()
user_extdata_req.add_argument(
    'extdata', required=True, type=object_type, location='json',
    help='Arbitrary object to set as extdata',
    error='extdata must be a valid JSON object'
)

# Disable account request
disable_account_req = reqparse.RequestParser()
disable_account_req.add_argument(
    'password', required=True, type=str, location='json',
    help='Current password required for confirmation',
    error='Password is required'
)

# Update password request
update_password_req = reqparse.RequestParser()
update_password_req.add_argument(
    'current_password', required=True, type=str, location='json',
    help='Current password',
    error='Current password is required'
)
update_password_req.add_argument(
    'new_password', required=True, type=length_restricted(3, 20, str),
    location='json', help='New password',
    error='New password is required'
)
update_password_req.add_argument(
    'new_password_confirmation', required=True,
    type=length_restricted(3, 20, str), location='json',
    help='Must match new_password',
    error='New password entries must match'
)

# Reset password confirmation request
reset_password_confirmation_req = reqparse.RequestParser()
reset_password_confirmation_req.add_argument(
    'reset_token', required=True, type=str, location='json',
    help='Password reset token',
    error='Password reset token is required'
)
reset_password_confirmation_req.add_argument(
    'new_password', required=True, type=length_restricted(3, 20, str),
    location='json', help='New password',
    error='New password is required'
)
reset_password_confirmation_req.add_argument(
    'new_password_confirmation', required=True,
    type=length_restricted(3, 20, str), location='json',
    help='Must match new_password',
    error='New password entries must match'
)

# Reset password request
reset_password_req = reqparse.RequestParser()
reset_password_req.add_argument(
    'username', required=True, type=str, location='json',
    help='Send a password reset email to this user.',
    error='Username is required'
)

# Email verification request
email_verification_req = reqparse.RequestParser()
email_verification_req.add_argument(
    'token', required=True, type=str, location='args',
    help='Password reset token',
    error='Password reset token is required'
)
email_verification_req.add_argument(
    'uid', required=True, type=str, location='args',
    help='User ID',
    error='User ID is required'
)

# Team password update request
update_team_password_req = reqparse.RequestParser()
update_team_password_req.add_argument(
    'new_password', required=True, type=length_restricted(3, 20, str),
    location='json', help='New password',
    error='New password is required'
)
update_team_password_req.add_argument(
    'new_password_confirmation', required=True,
    type=length_restricted(3, 20, str), location='json',
    help='Must match new_password',
    error='New password fields must match'
)

# Score progression request
score_progression_req = reqparse.RequestParser()
score_progression_req.add_argument(
    'category', required=False, type=str, location='args',
    help='Restrict score progression to this problem category',
    error='Category field must be a string'
)

# Team change request
team_change_req = reqparse.RequestParser()
team_change_req.add_argument(
    'team_name', required=True, type=str, location='json',
    help='Name of the team to join.',
    error='Must specify the name of the team to join'
)
team_change_req.add_argument(
    'team_password', required=True, type=str, location='json',
    help='Password of the team to join.',
    error='Team password is required'
)

# Team request
team_req = reqparse.RequestParser()
team_req.add_argument(
    'team_name', required=True, type=length_restricted(3, 100, str),
    location='json', help='Name of the new team'
    error='A name for the new team is required'
)
team_req.add_argument(
    'team_password', required=True, type=length_restricted(3, 20, str),
    location='json', help='Password for the new team',
    error='A password for the new team is required'
)

# Scoreboard page request
scoreboard_page_req = reqparse.RequestParser()
scoreboard_page_req.add_argument(
    'board', required=False, choices=['groups', 'global', 'student'],
    type=str, location='args', help='Choose which scoreboard to return',
    error='board must be one of: "groups", "global", "student"'
)
scoreboard_page_req.add_argument(
    'page', required=False, default=1, type=inputs.positive, location='args',
    help='Scoreboard page to return',
    error='page must be a positive integer'
)

# Top teams score progression request
top_teams_score_progression_req = reqparse.RequestParser()
top_teams_score_progression_req.add_argument(
    'limit', required=False, default=5, type=inputs.positive,
    location='args', help='Number of top teams to retrieve',
    error="limit must be a positive integer"
)
top_teams_score_progression_req.add_argument(
    'include_ineligible', required=False, default=False, type=inputs.boolean,
    location='args', help='Whether to include teams that are ineligible ' +
                          'for the current competition',
    error='include_ineligible must be a boolean value'
)
top_teams_score_progression_req.add_argument(
    'gid', required=False, type=str, default=None, location='args',
    help='If specified, restrict to top teams from this group',
    error='gid must be a string'
)

# Group request
group_req = reqparse.RequestParser()
group_req.add_argument(
    'name', required=True, type=length_restricted(3, 100, str),
    location='json', help='Name for the new group.',
    error='Group name is required'
)

# Group patch request
# @TODO because of RequestParser's limitations with nested fields,
# voluptous handles actually checking the settings fields within group.py.
group_patch_req = reqparse.RequestParser()
group_patch_req.add_argument(
    'settings', required=False, type=object_type, location='json',
    help='Updated settings object.'
)

# Group team removal request
group_remove_team_req = reqparse.RequestParser()
group_remove_team_req.add_argument(
    'team_id', required=True, location='json', type=str,
    help='ID of the team to remove.',
    error='Team ID is required'
)

# Group invite request
group_invite_req = reqparse.RequestParser()
group_invite_req.add_argument(
    'email', required=True, type=inputs.email(), location='json',
    help='Email address to invite to the group.',
    error='Must be a valid email address'
)
group_invite_req.add_argument(
    'as_teacher', required=True, type=inputs.boolean, location='json',
    default=False, help='Invite this user to be a teacher in the group, ' +
                        'rather than a regular member.',
    error='as_teacher must be a boolean value'
)

# Join group request
join_group_req = reqparse.RequestParser()
join_group_req.add_argument(
    'group_name', required=True, type=length_restricted(3, 100, str),
    location='json', help='Name of the group to join.',
    error='Group name is required'
)
join_group_req.add_argument(
    'group_owner', required=True, type=length_restricted(3, 40, str),
    location='json', help='Name of the teacher who owns the group.',
    error='Group owner is required'
)

# Minigame submission request
minigame_submission_req = reqparse.RequestParser()
minigame_submission_req.add_argument(
    'minigame_id', required=True, type=str, location='json',
    help='ID of the completed minigame',
    error='Minigame ID is required'
)
minigame_submission_req.add_argument(
    'verification_key', required=True, type=str, location='json',
    help='Verification key for the minigame',
    error='Minigame verification key is required'
)

# Batch registration schema
batch_registration_req = reqparse.RequestParser()
batch_registration_req.add_argument(
    'csv', type=werkzeug.datastructures.FileStorage,
    location='files', required=True,
    help='Modified copy of the provided batch import CSV',
    error='A valid CSV file is required'
)

# User search schema
user_search_req = reqparse.RequestParser()
user_search_req.add_argument(
    'field', required=True, type=str,
    choices=['email', 'parentemail'],
    location='json', help='The field to be searched',
    error='Field to search must be one of: "email", "parentemail"'
)
user_search_req.add_argument(
    'query', required=True, location='json', type=str,
    help="Body of the query", error="Query field is empty!"
)
