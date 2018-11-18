
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

    # Create the container
    result = api.docker.create(tid, digest)

    if result['success']:
        return WebSuccess(result['message'])
    else:
        return WebError(result['message'])

@blueprint.route('/stop', methods=['POST'])
@api_wrapper
@check_csrf
@require_login
@block_before_competition(WebError("The competition has not begun yet!"))
@block_after_competition(WebError("The competition is over!"))
def stop_container_hook():

    container_id = request.form.get('cid', '')
    print("stopping: ", container_id)

    # fail fast on invalid requests
    if any(char not in string.hexdigits for char in container_id):
        return WebError("Invalid container ID")

    # Delete the container
    result = api.docker.delete(container_id)

    if result:
        return WebSuccess("Challenge stopped")
    else:
        return WebError("Error stopping challenge")

@blueprint.route('/reset', methods=['POST'])
@api_wrapper
@check_csrf
@require_login
@block_before_competition(WebError("The competition has not begun yet!"))
@block_after_competition(WebError("The competition is over!"))
def reset_container_hook():

    # Containers are mapped to teams
    user_account = api.user.get_user()
    tid = user_account['tid']

    # get form values
    digest = request.form.get('digest', '')
    container_id = request.form.get('cid', '')
    print("cid: ", container_id)

    # fail fast on invalid requests
    if any(char not in string.hexdigits for char in container_id):
        return WebError("Invalid container ID")
    if any(char not in string.hexdigits + "sha:" for char in digest):
        return WebError("Invalid image digest")

    # Delete the container
    del_result = api.docker.delete(container_id)

    # Create the container
    create_result = api.docker.create(tid, digest)

    if del_result and create_result["success"]:
        return WebSuccess("Challenge reset.\nBe sure to use the new port.")
    else:
        return WebError("Error resetting challenge")
