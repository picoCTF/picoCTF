"""Minigame submission endpoint."""
import hashlib

from flask import jsonify
from flask_restplus import Namespace, Resource

import api
from api import (block_before_competition, check_csrf, PicoException,
                 require_login)

from .schemas import minigame_submission_req

ns = Namespace('minigames', description='Minigame submission endpoint')


@ns.route('')
class MinigameList(Resource):
    """Get the list of available minigames."""

    @ns.response(200, 'Success')
    @ns.response(401, 'Not logged in')
    @block_before_competition
    @require_login
    def get(self):
        """Get the list of available minigames."""
        settings = api.config.get_settings()
        minigame_config = settings.get("minigame", {}).get("token_values", {})
        return jsonify(
            [dict(zip(('mid', 'value'), minigame))
             for minigame in minigame_config.items()])


@ns.route('/<string:minigame_id>')
class Minigame(Resource):
    """Get a specific minigame."""

    @ns.response(200, 'Success')
    @ns.response(401, 'Not logged in')
    @ns.response(404, 'Minigame not found')
    @block_before_competition
    @require_login
    def get(self, minigame_id):
        """Get a specific minigame."""
        settings = api.config.get_settings()
        minigame_config = settings.get("minigame", {}).get("token_values", {})
        if minigame_id not in minigame_config:
            raise PicoException(
                "Minigame not found", 404
            )
        return jsonify({
            'mid': minigame_id,
            'value': minigame_config[minigame_id]
        })


@ns.route('/submit')
class MinigameSubmissionResponse(Resource):
    """Submit a verification key for a minigame."""

    @check_csrf
    @block_before_competition
    @require_login
    @ns.response(200, 'Success')
    @ns.response(400, 'Error parsing request')
    @ns.response(401, 'Not logged in')
    @ns.response(403, 'CSRF token invalid')
    @ns.response(404, 'Minigame not found')
    @ns.response(422, 'Invalid verification key or competition ' +
                      'has not started')
    @ns.expect(minigame_submission_req)
    def post(self):
        """Submit a verification key for a minigame."""
        req = minigame_submission_req.parse_args(strict=True)
        curr_user = api.user.get_user()

        settings = api.config.get_settings()
        minigame_config = settings.get("minigame", {}).get("token_values", {})

        if req['minigame_id'] not in minigame_config:
            raise PicoException('Minigame not found', 404)

        hashstring = req['minigame_id'] + curr_user['username'] + \
            settings['minigame']['secret']

        if hashlib.md5(hashstring.encode('utf-8')).hexdigest() != \
                req['verification_key']:
            raise PicoException('Invalid verification key', 422)

        previously_solved = True
        tokens_earned = 0
        if req['minigame_id'] not in curr_user['completed_minigames']:
            previously_solved = False
            tokens_earned = minigame_config[req['minigame_id']]
            db = api.db.get_conn()
            db.users.update_one({
                'uid': curr_user["uid"],
                'completed_minigames': {
                    '$ne': req['minigame_id']
                }
            }, {
                '$push': {
                    'completed_minigames': req['minigame_id']
                },
                '$inc': {
                    'tokens': tokens_earned
                }
            })

        return jsonify({
            'success': True,
            'previously_solved': previously_solved,
            'tokens_earned': tokens_earned,
            'new_token_count': api.user.get_user()['tokens']
        })
