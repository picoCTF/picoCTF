import json

import api
import pymongo
import spur
from api.common import (check, InternalException, safe_fail, validate,
                        WebException)
from voluptuous import Length, Required, Schema

server_schema = Schema(
    {
        Required("name"):
        check(
            ("Name must be a reasonable string.", [str,
                                                   Length(min=1, max=128)])),
        Required("host"):
        check(
            ("Host must be a reasonable string", [str,
                                                  Length(min=1, max=128)])),
        Required("port"):
        check(("You have to supply a valid integer for your port.", [int]),
              ("Your port number must be in the valid range 1-65535.",
               [lambda x: 1 <= int(x) and int(x) <= 65535])),
        Required("username"):
        check(("Username must be a reasonable string",
               [str, Length(min=1, max=128)])),
        Required("password"):
        check(("Username must be a reasonable string",
               [str, Length(min=1, max=128)])),
        Required("protocol"):
        check(("Protocol must be either HTTP or HTTPS",
               [lambda x: x in ['HTTP', 'HTTPS']])),
        "server_number":
        check(("Server number must be an integer.", [int]),
              ("Server number must be a positive integer.",
               [lambda x: 0 < int(x)])),
    },
    extra=True)


def get_server(sid=None, name=None):
    """
    Returns the server object corresponding to the sid provided

    Args:
        sid: the server id to lookup

    Returns:
        The server object
    """

    db = api.common.get_conn()

    if sid is None:
        if name is None:
            raise InternalException("You must specify either an sid or name")
        else:
            sid = api.common.hash(name)

    server = db.shell_servers.find_one({"sid": sid})
    if server is None:
        raise InternalException(
            "Server with sid '{}' does not exist".format(sid))

    return server


def get_server_number(sid):
    """
    Gets the server_number designation from sid
    """
    if sid is None:
        raise InternalException("You must specify a sid")

    server = get_server(sid=sid)
    if server is None:
        raise InternalException(
            "Server with sid '{}' does not exist".format(sid))

    return server.get("server_number")


def get_connection(sid):
    """
    Attempts to connect to the given server and returns a connection.
    """

    server = get_server(sid)

    try:
        shell = spur.SshShell(
            hostname=server["host"],
            username=server["username"],
            password=server["password"],
            port=server["port"],
            missing_host_key=spur.ssh.MissingHostKey.accept,
            connect_timeout=10)
        shell.run(["echo", "connected"])
    except spur.ssh.ConnectionError as e:
        raise WebException(
            "Cannot connect to {}@{}:{} with the specified password".format(
                server["username"], server["host"], server["port"]))

    return shell


def ensure_setup(shell):
    """
    Runs sanity checks on the shell connection to ensure that
    shell_manager is set up correctly.

    Leaves connection open.
    """

    result = shell.run(
        ["sudo", "/picoCTF-env/bin/shell_manager", "status"], allow_error=True)
    if result.return_code == 1 and "command not found" in result.stderr_output.decode(
            "utf-8"):
        raise WebException("shell_manager not installed on server.")


def add_server(params):
    """
    Add a shell server to the pool of servers. First server is
    automatically assigned server_number 1 (yes, 1-based numbering)
    if not otherwise specified.

    Args:
        params: A dict containing:
            host
            port
            username
            password
            server_number
    Returns:
       The sid.
    """

    db = api.common.get_conn()

    validate(server_schema, params)

    if isinstance(params["port"], str):
        params["port"] = int(params["port"])
    if isinstance(params.get("server_number"), str):
        params["server_number"] = int(params["server_number"])

    if safe_fail(get_server, name=params["name"]) is not None:
        raise WebException("Shell server with this name already exists")

    params["sid"] = api.common.hash(params["name"])

    # Automatically set first added server as server_number 1
    if db.shell_servers.count() == 0:
        params["server_number"] = params.get("server_number", 1)

    db.shell_servers.insert(params)

    return params["sid"]


# Probably do not need/want the sid here anymore.
def update_server(sid, params):
    """
    Update a shell server from the pool of servers.

    Args:
        sid: The sid of the server to update
        params: A dict containing:
            port
            username
            password
            server_number
    """

    db = api.common.get_conn()

    validate(server_schema, params)

    server = safe_fail(get_server, sid=sid)
    if server is None:
        raise WebException(
            "Shell server with sid '{}' does not exist.".format(sid))

    params["name"] = server["name"]

    validate(server_schema, params)

    if isinstance(params["port"], str):
        params["port"] = int(params["port"])
    if isinstance(params.get("server_number"), str):
        params["server_number"] = int(params["server_number"])

    db.shell_servers.update({"sid": server["sid"]}, {"$set": params})


def remove_server(sid):
    """
    Remove a shell server from the pool of servers.

    Args:
        sid: the sid of the server to be removed
    """

    db = api.common.get_conn()

    if db.shell_servers.find_one({"sid": sid}) is None:
        raise WebException(
            "Shell server with sid '{}' does not exist.".format(sid))

    db.shell_servers.remove({"sid": sid})


def get_servers(get_all=False):
    """
    Returns the list of added shell servers, or the assigned shell server
    shard if sharding is enabled. Defaults to server 1 if not assigned
    """

    db = api.common.get_conn()

    settings = api.config.get_settings()
    match = {}
    if not get_all and settings["shell_servers"]["enable_sharding"]:
        team = api.team.get_team()
        match = {"server_number": team.get("server_number", 1)}

    servers = list(db.shell_servers.find(match, {"_id": 0}))

    if len(servers) == 0 and settings["shell_servers"]["enable_sharding"]:
        raise InternalException(
            "Your assigned shell server is currently down. Please contact an admin."
        )

    return servers


def get_problem_status_from_server(sid):
    """
    Connects to the server and checks the status of the problems running there.
    Runs `sudo shell_manager status --json` and parses its output.

    Closes connection after running command.

    Args:
        sid: The sid of the server to check

    Returns:
        A tuple containing:
            - True if all problems are online and false otherwise
            - The output data of shell_manager status --json
    """

    shell = get_connection(sid)
    ensure_setup(shell)

    with shell:
        output = shell.run(
            ["sudo", "/picoCTF-env/bin/shell_manager", "status",
             "--json"]).output.decode("utf-8")
    data = json.loads(output)

    all_online = True

    for problem in data["problems"]:
        for instance in problem["instances"]:
            # if the service is not working
            if not instance["service"]:
                all_online = False

            # if the connection is not working and it is a remote challenge
            if not instance["connection"] and instance["port"] is not None:
                all_online = False

    return (all_online, data)


def load_problems_from_server(sid):
    """
    Connects to the server and loads the problems from its deployment state.
    Runs `sudo shell_manager publish` and captures its output.

    Closes connection after running command.

    Args:
        sid: The sid of the server to load problems from.

    Returns:
        The number of problems loaded
    """

    shell = get_connection(sid)

    with shell:
        result = shell.run(["sudo", "/picoCTF-env/bin/shell_manager", "publish"])
    data = json.loads(result.output.decode("utf-8"))

    # Pass along the server
    data["sid"] = sid

    api.problem.load_published(data)

    has_instances = lambda p: len(p["instances"]) > 0
    return len(list(filter(has_instances, data["problems"])))


def get_assigned_server_number(new_team=True, tid=None):
    """
    Assigns a server number based on current teams count and
    configured stepping

    Returns:
         (int) server_number
    """
    settings = api.config.get_settings()["shell_servers"]
    db = api.common.get_conn()

    if new_team:
        team_count = db.teams.count()
    else:
        if not tid:
            raise InternalException("tid must be specified.")
        oid = db.teams.find_one({"tid": tid}, {"_id": 1})
        if not oid:
            raise InternalException("Invalid tid.")
        team_count = db.teams.count({"_id": {"$lt": oid["_id"]}})

    assigned_number = 1

    steps = settings["steps"]

    if steps:
        if team_count < steps[-1]:
            for i, step in enumerate(steps):
                if team_count < step:
                    assigned_number = i + 1
                    break
        else:
            assigned_number = 1 + len(steps) + (
                team_count - steps[-1]) // settings["default_stepping"]

    else:
        assigned_number = team_count // settings["default_stepping"] + 1

    if settings["limit_added_range"]:
        max_number = list(
            db.shell_servers.find({}, {
                "server_number": 1
            }).sort("server_number", -1).limit(1))[0]["server_number"]
        return min(max_number, assigned_number)
    else:
        return assigned_number


def reassign_teams(include_assigned=False):
    db = api.common.get_conn()

    if include_assigned:
        teams = api.team.get_all_teams(show_ineligible=True)
    else:
        teams = list(
            db.teams.find({
                "server_number": {
                    "$exists": False
                }
            }, {
                "_id": 0,
                "tid": 1
            }))

    for team in teams:
        old_server_number = team.get("server_number")
        server_number = get_assigned_server_number(
            new_team=False, tid=team["tid"])
        if old_server_number != server_number:
            db.teams.update({
                'tid': team["tid"]
            }, {'$set': {
                'server_number': server_number,
                'instances': {}
            }})
            # Re-assign instances
            safe_fail(api.problem.get_visible_problems, team["tid"])

    return len(teams)
