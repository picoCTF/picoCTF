
import string

import api
from api.annotations import (api_wrapper, block_after_competition,
                             block_before_competition, check_csrf,
                             require_login)
from api.common import WebError, WebSuccess
from flask import (Blueprint, request)

blueprint = Blueprint("docker_api", __name__)


@blueprint.route('/create', methods=['POST'])
@api_wrapper
@check_csrf
@require_login
@block_before_competition(WebError("The competition has not begun yet!"))
@block_after_competition(WebError("The competition is over!"))
def create_container_hook():

    # Containers are mapped to teams
    user_account = api.user.get_user()
    tid = user_account['tid']
    digest = request.form.get('digest', '')

    # fail fast on invalid requests
    if any(char not in string.hexdigits + "sha:" for char in digest):
        return WebError("Invalid image digest")

    # Get a list of live running containers
    existing = api.docker.list_containers(tid)
    print(existing)

    # Create the container
    result = api.docker.create(tid, digest)

    if result['success']:
        # XXX: Actually parse result into a better response
        return WebSuccess(result['message'], result)
    else:
        return WebError(result['message'])
