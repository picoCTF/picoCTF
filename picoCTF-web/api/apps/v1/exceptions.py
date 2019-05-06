"""Exception related endpoints."""

from flask import jsonify
from flask_restplus import Namespace, Resource

import api.logger
from api.common import PicoException

from .schemas import exception_req

ns = Namespace('exceptions', description='View and dismiss logged exceptions')


@ns.route('/')
class ExceptionsList(Resource):
    """Get the most recent exceptions, or dismiss all exceptions."""

    # @require_admin
    @ns.response(200, 'Success')
    @ns.response(400, 'Error parsing request')
    @ns.expect(exception_req)
    def get(self):
        """Get the most recent logged exceptions."""
        req = exception_req.parse_args(strict=False)
        if req['result_limit'] is None:
            return jsonify(api.logger.get_api_exceptions())
        else:
            return jsonify(api.logger.get_api_exceptions(
                result_limit=req['result_limit']))

    # @require_admin
    def delete(self):
        """Dismiss all exceptions. Retains the exceptions in the database."""
        count = api.logger.dismiss_api_exceptions()
        res = jsonify({
            'success': True,
            'dismissed_count': count
        })
        res.status_code = 200
        return res


@ns.response(200, 'Success')
@ns.response(404, 'Exception not found')
@ns.route('/<string:exception_id>')
class Exception(Resource):
    """Get or dismiss a specific exception."""

    # @require_admin
    def get(self, exception_id):
        """Retrieve a specific exception."""
        exception = api.logger.get_api_exception(exception_id)
        if not exception:
            raise PicoException('Exception not found', status_code=404)
        else:
            res = jsonify(exception)
            res.response_code = 200
            return res

    # @require_admin
    def delete(self, exception_id):
        """Dismiss a specific exception."""
        count = api.logger.dismiss_api_exceptions(exception_id)
        res = jsonify({
            'success': True,
            'dismissed_count': count
        })
        res.status_code = 200
        return res