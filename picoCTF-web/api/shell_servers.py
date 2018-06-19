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
               [lambda x: x in ['HTTP', 'HTTPS']]))
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


def get_connection(sid):
    """
    Attempts to connect to the given server and
    returns a connection.
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
    """

    result = shell.run(["sudo", "shell_manager", "status"], allow_error=True)
    if result.return_code == 1 and "command not found" in result.stderr_output.decode(
            "utf-8"):
        raise WebException("shell_manager not installed on server.")


def add_server(params):
    """
    Add a shell server to the pool of servers.

    Args:
        params: A dict containing:
            host
            port
            username
            password
    Returns:
       The sid.
    """

    db = api.common.get_conn()

    validate(server_schema, params)

    if isinstance(params["port"], str):
        params["port"] = int(params["port"])

    if safe_fail(get_server, name=params["name"]) is not None:
        raise WebException("Shell server with this name already exists")

    params["sid"] = api.common.hash(params["name"])
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


def get_servers():
    """
    Returns the list of added shell servers.
    """

    db = api.common.get_conn()
    return list(db.shell_servers.find({}, {"_id": 0}))


def get_problem_status_from_server(sid):
    """
    Connects to the server and checks the status of the problems running there.
    Runs `sudo shell_manager status --json` and parses its output.

    Args:
        sid: The sid of the server to check

    Returns:
        A tuple containing:
            - True if all problems are online and false otherwise
            - The output data of shell_manager status --json
    """

    shell = get_connection(sid)
    ensure_setup(shell)

    output = shell.run(["sudo", "shell_manager", "status",
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

    Args:
        sid: The sid of the server to load problems from.

    Returns:
        The number of problems loaded
    """

    shell = get_connection(sid)

    result = shell.run(["sudo", "shell_manager", "publish"])
    data = json.loads(result.output.decode("utf-8"))

    # Pass along the server
    data["sid"] = sid

    api.problem.load_published(data)

    has_instances = lambda p: len(p["instances"]) > 0
    return len(list(filter(has_instances, data["problems"])))
