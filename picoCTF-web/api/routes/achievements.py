import api
from api.annotations import (api_wrapper, block_after_competition,
                             block_before_competition, log_action,
                             require_login)
from api.common import WebError, WebSuccess
from flask import Blueprint

blueprint = Blueprint("achievements_api", __name__)


@blueprint.route('', methods=['GET'])
@require_login
@api_wrapper
def get_achievements_hook():
    tid = api.user.get_team()["tid"]
    achievements = api.achievement.get_earned_achievements_display(tid=tid)

    for achievement in achievements:
        achievement[
            "timestamp"] = None  # JB : Hack to temporarily fix achievements timestamp problem

    return WebSuccess(data=achievements)
