"""
Setup for the API
"""

import api

log = api.logger.use(__name__)


def index_mongo():
    """
    Ensure the mongo collections are indexed.
    """

    db = api.common.get_conn()

    log.debug("Ensuring mongo is indexed.")

    db.users.ensure_index("uid", unique=True, name="unique uid")
    db.users.ensure_index("username", unique=True, name="unique username")

    db.groups.ensure_index("gid", unique=True, name="unique gid")
    db.problems.ensure_index("pid", unique=True, name="unique pid")

    db.submissions.ensure_index("tid", name="submission tids")
    db.ssh.ensure_index("tid", unique=True, name="unique ssh tid")
    db.teams.ensure_index("team_name", unique=True, name="unique team names")

    db.shell_servers.ensure_index("name", unique=True, name="unique shell name")
    db.shell_servers.ensure_index("sid", unique=True, name="unique shell sid")

    db.cache.ensure_index("expireAt", expireAfterSeconds=0)
    db.cache.ensure_index("kwargs", name="kwargs")
    db.cache.ensure_index("args", name="args")

    db.shell_servers.ensure_index(
        "sid", unique=True, name="unique shell server id")
