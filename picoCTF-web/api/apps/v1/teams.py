"""Team related endpoints."""
import string

from flask import jsonify
from flask_restplus import Namespace, Resource

import api
from api import PicoException, require_admin, require_login

from .schemas import team_req

ns = Namespace('teams', description='Team management')


@ns.route('')
class TeamList(Resource):
    """The set of all teams."""

    @require_login
    @ns.response(201, 'Success')
    @ns.response(400, 'Error parsing request')
    @ns.response(401, 'Not logged in')
    @ns.response(403, 'Unauthorized to create team')
    @ns.response(409, 'User or team with this name already exists')
    @ns.response(422, 'User has already created a team')
    @ns.expect(team_req)
    def post(self):
        """Create and automatically join new team."""
        req = team_req.parse_args(strict=True)
        curr_user = api.user.get_user()
        if curr_user['teacher']:
            raise PicoException(
                'Teachers may not create teams', 403
            )
        if not all([
                c in string.digits + string.ascii_lowercase + " ()+-,#'*&!?"
                for c in req['team_name'].lower()]):
            raise PicoException(
                "Team names cannot contain special characters other than"+
                "()+-,#'*&!?", status_code=400
            )

        new_tid = api.team.create_and_join_new_team(
            req['team_name'],
            req['team_password'],
            curr_user
        )
        res = jsonify({
            'success': True,
            'tid': new_tid
        })
        res.status_code = 201
        return res


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.response(403, 'Permission denied')
@ns.response(404, 'Team not found')
@ns.route('/<string:team_id>/recalculate_eligibility')
class RecalculateEligibilityResponse(Resource):
    """Force recalculation of a team's eligibility status."""

    @require_admin
    def get(self, team_id):
        """
        Force recalculation of a team's eligibility status.

        Once a team has been found to be ineligible once, they are permanently
        flagged as such. This admin-only endpoint can potentially reverse this,
        if the competition's eligiblity conditions have been updated or the
        member(s) previously causing ineligiblity have been deleted.
        """
        team = api.team.get_team(team_id)
        if not team:
            raise PicoException('Team not found', 404)
        eligibility = api.team.is_eligible(team_id)
        api.team.mark_eligiblity(team_id, eligibility)
        return jsonify({
            'success': True,
            'eligible': eligibility
        })
