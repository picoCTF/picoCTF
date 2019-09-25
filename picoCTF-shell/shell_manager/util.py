"""
Common utilities for the shell manager.
"""

import json
import logging
import os
import re
import shutil
import string
from os import chmod, listdir, sep, unlink
from os.path import isdir, isfile, join
from shutil import copy2, copytree
from hashlib import md5

from voluptuous import (All, ALLOW_EXTRA, Length, MultipleInvalid, Range,
                        Required, Schema)

logger = logging.getLogger(__name__)

# Directories used to store server state.

# Most resources (installed problems and bundles, config, etc.) are stored
# within the SHARED_ROOT directory, which can be located on a network
# filesystem and mounted onto several shell servers to sync state.

# Deployed problem instances, however, are separate to each server
# (although the same problem instance will share its flag/port across servers).
SHARED_ROOT = '/opt/hacksports/shared/'
LOCAL_ROOT = '/opt/hacksports/local/'

PROBLEM_ROOT = join(SHARED_ROOT, "sources")
EXTRA_ROOT = join(SHARED_ROOT, "extra")
STAGING_ROOT = join(SHARED_ROOT, "staging")
BUNDLE_ROOT = join(SHARED_ROOT, "bundles")
DEB_ROOT = join(SHARED_ROOT, "debs")

DEPLOYED_ROOT = join(LOCAL_ROOT, "deployed")


class ConfigDict(dict):
    # Neat trick to allow configuration fields to be accessed as attributes
    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, value):
        self[attr] = value


default_shared_config = ConfigDict({
    # secret used for deterministic deployment
    "deploy_secret":
    "qwertyuiop",

    # the default username for files to be owned by
    "default_user":
    "hacksports",

    # the root of the web server running to serve static files
    # make sure this is consistent with what config/shell.nginx
    # specifies.
    "web_root":
    "/usr/share/nginx/html/",

    # the root of the problem directories for the instances
    "problem_directory_root":
    "/problems/",

    # "obfuscate" problem directory names
    "obfuscate_problem_directories":
    False,

    # list of port ranges that should not be assigned to any instances
    # this bans the first ports 0-1024 and 4242 for wetty
    "banned_ports": [{
        "start": 0,
        "end": 1024
    }, {
        "start": 4242,
        "end": 4242
    }]
})

default_local_config = ConfigDict({
    # the externally accessible address of this server
    "hostname":
    "127.0.0.1",

    # the url of the web server
    "web_server":
    "http://127.0.0.1",
})

problem_schema = Schema({
    Required("author"): All(str, Length(min=1, max=32)),
    Required("score"): All(int, Range(min=0)),
    Required("name"): All(str, Length(min=1, max=32)),
    Required("description"): str,
    Required("category"): All(str, Length(min=1, max=32)),
    Required("hints"): list,
    Required("organization"): All(str, Length(min=1, max=32)),
    Required("event"): All(str, Length(min=1, max=32)),
    "unique_name": str,
    "static_flag": bool,
    "walkthrough": All(str, Length(min=1, max=512)),
    "version": All(str, Length(min=1, max=8)),
    "tags": list,
    "pkg_description": All(str, Length(min=1, max=256)),
    "pkg_name": All(str, Length(min=1, max=32)),
    "pkg_dependencies": list,
    "pip_requirements": list,
    "pip_python_version": All(str, Length(min=1, max=3)),
    "env": All(str, Length(min=1, max=256)),
}, extra=ALLOW_EXTRA)

bundle_schema = Schema({
    Required("author"): All(str, Length(min=1, max=32)),
    Required("name"): All(str, Length(min=1, max=32)),
    Required("description"): str,
    "dependencies": dict
})

shared_config_schema = Schema(
    {
        Required("deploy_secret"): str,
        Required("default_user"): str,
        Required("web_root"): str,
        Required("problem_directory_root"): str,
        Required("obfuscate_problem_directories"): bool,
        Required("banned_ports"): list
    },
    extra=False)

local_config_schema = Schema(
    {
        Required("hostname"): str,
        Required("web_server"): str,
        Required("rate_limit_bypass_key"): str,
    },
    extra=False)

port_range_schema = Schema({
    Required("start"):
    All(int, Range(min=0, max=65535)),
    Required("end"):
    All(int, Range(min=0, max=65535))
})


class FatalException(Exception):
    pass


def get_attributes(obj):
    """
    Returns all attributes of an object, excluding those that start with
    an underscore.

    Args:
        obj: the object

    Returns:
        A dictionary of attributes
    """

    return {
        key: getattr(obj, key) if not key.startswith("_") else None
        for key in dir(obj)
    }


def sanitize_name(name):
    """
    Sanitizes the given name such that it conforms to unix policy.

    Args:
        name: the name to sanitize.

    Returns:
        The sanitized form of name.
    """

    if len(name) == 0:
        raise Exception("Can not sanitize an empty field.")

    sanitized_name = re.sub(r"[^a-z0-9\+-]", "-", name.lower())

    if sanitized_name[0] in string.digits:
        sanitized_name = "p" + sanitized_name

    return sanitized_name


# I will never understand why the shutil functions act the way they do...


def full_copy(source, destination, ignore=None):
    if ignore is None:
        ignore = []
    for f in listdir(source):
        if f in ignore:
            continue
        source_item = join(source, f)
        destination_item = join(destination, f)

        if isdir(source_item):
            if not isdir(destination_item):
                copytree(source_item, destination_item)
        else:
            copy2(source_item, destination_item)


def move(source, destination, clobber=True):
    if sep in source:
        file_name = source.split(sep)[-1]
    else:
        file_name = source

    new_path = join(destination, file_name)
    if clobber and isfile(new_path):
        unlink(new_path)

    shutil.move(source, destination)


def get_problem_root(problem_name, absolute=False):
    """
    Installation location for a given problem.

    Args:
        problem_name: the problem name.
        absolute: should return an absolute path.

    Returns:
        The tentative installation location.
    """

    problem_root = join(PROBLEM_ROOT, sanitize_name(problem_name))

    assert problem_root.startswith(sep)
    if absolute:
        return problem_root

    return problem_root[len(sep):]

def get_problem_root_hashed(problem, absolute=False):
    """
    Installation location for a given problem.

    Args:
        problem: the problem object.
        absolute: should return an absolute path.

    Returns:
        The tentative installation location.
    """

    problem_root = join(PROBLEM_ROOT, "{}-{}".format(sanitize_name(problem["name"]), get_pid_hash(problem, True)))

    assert problem_root.startswith(sep)
    if absolute:
        return problem_root

    return problem_root[len(sep):]


def get_problem(problem_path):
    """
    Returns a problem spec from a given problem directory.

    Args:
        problem_path: path to the root of the problem directory.

    Returns:
        A problem object.
    """

    json_path = join(problem_path, "problem.json")
    try:
        problem = json.loads(open(json_path, "r").read())
    except json.decoder.JSONDecodeError as e:
        logger.critical(f"Error reading JSON file {json_path}")
        logger.critical(e)
        raise FatalException
    problem['unique_name'] = "{}-{}".format(sanitize_name(problem["name"]), get_pid_hash(problem, True))
    try:
        problem_schema(problem)
    except MultipleInvalid as e:
        logger.critical("Error validating problem object at '%s'!", json_path)
        logger.critical(e)
        raise FatalException

    return problem


def get_bundle_root(bundle_name, absolute=False):
    """
    Installation location for a given bundle.

    Args:
        bundle_name: the bundle name.
        absolute: should return an absolute path.

    Returns:
        The tentative installation location.
    """

    bundle_root = join(BUNDLE_ROOT, sanitize_name(bundle_name), "bundle.json")

    assert bundle_root.startswith(sep)
    if absolute:
        return bundle_root

    return bundle_root[len(sep):]


def get_bundle(bundle_path):
    """
    Returns a bundle spec from a bundle JSON file.

    Args:
        bundle_path: path to the bundle JSON file.

    Returns:
        A bundle object.
    """

    bundle = json.loads(open(bundle_path, "r").read())

    try:
        bundle_schema(bundle)
    except MultipleInvalid as e:
        logger.critical("Error validating bundle object at '%s'!", bundle_path)
        logger.critical(e)
        raise FatalException

    return bundle


def verify_shared_config(shared_config_object):
    """
    Verifies the given shared configuration dict against
    the shared_config_schema and the port_range_schema.

    Args:
        shared_config_object: The configuration options in a dict

    Raises:
         FatalException: if failed.
    """

    try:
        shared_config_schema(shared_config_object)
    except MultipleInvalid as e:
        logger.critical("Error validating shared config file!")
        logger.critical(e)
        raise FatalException

    for port_range in shared_config_object["banned_ports"]:
        try:
            port_range_schema(port_range)
            assert port_range["start"] <= port_range["end"]
        except MultipleInvalid as e:
            logger.critical(
                "Error validating port range in shared config file!")
            logger.critical(e)
            raise FatalException
        except AssertionError:
            logger.critical("Invalid port range: (%d -> %d)",
                            port_range["start"], port_range["end"])
            raise FatalException


def verify_local_config(local_config_object):
    """
    Verifies the given local configuration dict against
    the local_config_schema.

    Args:
        local_config_object: The configuration options in a dict

    Raises:
         FatalException: if failed.
    """

    try:
        local_config_schema(local_config_object)
    except MultipleInvalid as e:
        logger.critical("Error validating local config file!")
        logger.critical(e)
        raise FatalException


def write_configuration_file(path, config_dict):
    """
    Writes the options in config_dict to the specified path as JSON.

    Args:
        path: the path of the output JSON file
        config_dict: the configuration dictionary
    """

    with open(path, "w") as f:
        json_data = json.dumps(
            config_dict, sort_keys=True, indent=4, separators=(',', ': '))
        f.write(json_data)


def get_shared_config():
    """
    Returns the shared configuration options from the file in SHARED_ROOT.
    """
    shared_config_location = join(SHARED_ROOT, "shared_config.json")
    try:
        with open(shared_config_location) as f:
            config_object = json.loads(f.read())
        verify_shared_config(config_object)
        config = ConfigDict()
        for key, value in config_object.items():
            config[key] = value
        return config
    except PermissionError:
        logger.error("You must run shell_manager with sudo.")
        raise FatalException
    except FileNotFoundError:
        write_configuration_file(shared_config_location, default_shared_config)
        chmod(shared_config_location, 0o640)
        logger.info(
            "There was no default configuration. One has been created for you. Please edit it accordingly using the 'shell_manager config' subcommand before deploying any instances."
        )
        raise FatalException


def get_local_config():
    """
    Returns the local configuration options from the file in LOCAL_ROOT.
    """
    local_config_location = join(LOCAL_ROOT, "local_config.json")
    try:
        with open(local_config_location) as f:
            config_object = json.loads(f.read())
        verify_local_config(config_object)
        config = ConfigDict()
        for key, value in config_object.items():
            config[key] = value
        return config
    except PermissionError:
        logger.error("You must run shell_manager with sudo.")
        raise FatalException
    except FileNotFoundError:
        write_configuration_file(local_config_location, default_local_config)
        chmod(local_config_location, 0o640)
        logger.info(
            "There was no default configuration. One has been created for you. Please edit it accordingly using the 'shell_manager config' subcommand before deploying any instances."
        )
        raise FatalException


def set_shared_config(config_dict):
    """
    Validates and writes the options in config_dict to the shared config file.

    Args:
        config_dict: the configuration dictionary
    """
    verify_shared_config(config_dict)
    write_configuration_file(
        join(SHARED_ROOT, "shared_config.json"), config_dict)


def set_local_config(config_dict):
    """
    Validates and writes the options in config_dict to the local config file.

    Args:
        config_dict: the configuration dictionary
    """
    verify_local_config(config_dict)
    write_configuration_file(
        join(LOCAL_ROOT, "local_config.json"), config_dict)


def get_pid_hash(problem, short=False):
    """
    Returns a hash of a given problem.

    Args:
        problem: a valid problem object.
        short: shorten the return value (first 7 characters)

    Returns:
        Hex digest of the MD5 hash
    """

    try:
        problem_schema(problem)
    except MultipleInvalid as e:
        logger.critical("Error validating problem object!")
        logger.critical(e)
        raise FatalException

    input = "{}-{}-{}-{}".format(problem["name"], problem["author"], problem["organization"], problem["event"])
    output = md5(input.encode("utf-8")).hexdigest()

    if short:
        return output[:7]

    return output


def acquire_lock():
    """Acquire the problem installation/deployment lock."""
    lock_file = join(SHARED_ROOT, "deploy.lock")
    if isfile(lock_file):
        logger.error(
            "Another problem installation or deployment appears in progress. If you believe this to be an error, "
            "run 'shell_manager clean'")
        raise FatalException

    with open(lock_file, "w") as f:
        f.write("1")
    logger.debug(f"Obtained lock file ({str(lock_file)})")


def release_lock():
    """Release the problem installation/deployment lock."""
    lock_file = join(SHARED_ROOT, "deploy.lock")
    if isfile(lock_file):
        os.remove(lock_file)
        logger.debug(f"Released lock file ({str(lock_file)})")
