"""Handles database interaction."""

import logging

from flask import current_app

import pymongo
from pymongo.collation import Collation, CollationStrength
from pymongo.errors import PyMongoError

from api import PicoException

log = logging.getLogger(__name__)

__connection = None
__client = None


def get_conn():
    """
    Get a database connection, reusing one if it exists.

    Raises:
        PicoException if a successful connection cannot be established

    """
    global __client, __connection
    if not __connection:
        conf = current_app.config
        if conf["MONGO_USER"] and conf["MONGO_PW"]:
            uri = "mongodb://{}:{}@{}:{}/{}?authMechanism=SCRAM-SHA-1".format(
                conf["MONGO_USER"], conf["MONGO_PW"], conf["MONGO_ADDR"],
                conf["MONGO_PORT"], conf["MONGO_DB_NAME"])
            if conf["MONGO_REPLICA_SETTINGS"]:
                uri = "{}&{}".format(uri, conf["MONGO_REPLICA_SETTINGS"])
            if conf["MONGO_TLS_SETTINGS"]:
                uri = "{}&{}".format(uri, conf["MONGO_TLS_SETTINGS"])
        else:
            uri = "mongodb://{}:{}/{}".format(
                conf["MONGO_ADDR"], conf["MONGO_PORT"], conf["MONGO_DB_NAME"])
        try:
            __client = pymongo.MongoClient(uri)
            __connection = __client[conf["MONGO_DB_NAME"]]
        except PyMongoError as error:
            raise PicoException(
                'Internal server error. Please contact a system adminstrator.',
                data={'original_error': error})

        log.debug("Ensuring mongo is indexed.")

        __connection.exceptions.create_index([('time', pymongo.DESCENDING)])

        __connection.users.create_index("uid", unique=True, name="unique uid")
        __connection.users.create_index(
            "username", unique=True, name="unique usernames")
        __connection.users.create_index(
            "username", unique=True, collation=Collation(
                locale="en", strength=CollationStrength.PRIMARY
            ), name="unique normalized usernames")
        __connection.users.create_index("tid")
        __connection.users.create_index("email")
        __connection.users.create_index("demo.parentemail")

        __connection.groups.create_index("gid", unique=True, name="unique gid")
        __connection.groups.create_index("owner", name="owner")
        __connection.groups.create_index("teachers", name="teachers")
        __connection.groups.create_index("members", name="members")
        __connection.groups.create_index(
            [('owner', 1), ('time', 1)], name="name and owner")

        __connection.problems.create_index(
            "pid", unique=True, name="unique pid")
        __connection.problems.create_index("disabled")
        __connection.problems.create_index(
            [('score', pymongo.ASCENDING), ('name', pymongo.ASCENDING)])

        __connection.scoreboards.create_index(
            "sid", unique=True, name="unique scoreboard sid")

        __connection.settings.create_index("settings_id", unique=True)

        __connection.shell_servers.create_index(
            "sid", unique=True, name="unique shell sid")

        __connection.submissions.create_index(
            [("pid", 1), ("uid", 1), ("correct", 1)])
        __connection.submissions.create_index(
            [("pid", 1), ("tid", 1), ("correct", 1)])
        __connection.submissions.create_index([("uid", 1), ("correct", 1)])
        __connection.submissions.create_index([("tid", 1), ("correct", 1)])
        __connection.submissions.create_index([("pid", 1), ("correct", 1)])
        __connection.submissions.create_index("uid")
        __connection.submissions.create_index("tid")

        __connection.teams.create_index(
            "team_name", unique=True, name="unique team_names")
        __connection.teams.create_index(
            "team_name", unique=True, collation=Collation(
                locale="en", strength=CollationStrength.PRIMARY
            ), name="unique normalized team names")
        __connection.teams.create_index("tid", unique=True, name="unique tid")
        __connection.teams.create_index(
            "eligibilities",
            name="non-empty eligiblity",
            partialFilterExpression={
                "size": {
                    "$gt": 0
                }
            })
        __connection.teams.create_index(
            "size",
            name="non-empty size",
            partialFilterExpression={
                "size": {
                    "$gt": 0
                }
            })

        __connection.tokens.create_index("uid")
        __connection.tokens.create_index("gid")
        __connection.tokens.create_index("tokens.registration_token")
        __connection.tokens.create_index("tokens.email_verification")
        __connection.tokens.create_index("tokens.password_reset")

        __connection.shared_submissions.create_index("tid")

    return __connection
