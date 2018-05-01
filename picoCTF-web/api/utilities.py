""" Module for utilities such as emailing, password reset, etc """

from datetime import datetime

import api


def check_competition_active():
    """
    Is the competition currently running
    """

    settings = api.config.get_settings()

    return settings["start_time"].timestamp() < datetime.utcnow().timestamp() < settings["end_time"].timestamp()
