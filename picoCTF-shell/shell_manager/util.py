"""
Common utilities for the shell manager.
"""

import json
import logging
import re
import shutil
import string
from os import chmod, listdir, sep, unlink
from os.path import isdir, isfile, join
from shutil import copy2, copytree

from voluptuous import All, Length, MultipleInvalid, Range, Required, Schema

logger = logging.getLogger(__name__)

# the root of the hacksports local store
HACKSPORTS_ROOT = "/opt/hacksports/"
PROBLEM_ROOT = join(HACKSPORTS_ROOT, "sources")
EXTRA_ROOT = join(HACKSPORTS_ROOT, "extra")
STAGING_ROOT = join(HACKSPORTS_ROOT, "staging")
DEPLOYED_ROOT = join(HACKSPORTS_ROOT, "deployed")
BUNDLE_ROOT = join(HACKSPORTS_ROOT, "bundles")


class ConfigDict(dict):
    # Neat trick to allow configuration fields to be accessed as attributes
    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, value):
        self[attr] = value


default_config = ConfigDict({
    # secret used for deterministic deployment
    "deploy_secret":
    "qwertyuiop",

    # the externally accessable address of this server
    "hostname":
    "127.0.0.1",

    # the url of the web server
    "web_server":
    "http://127.0.0.1",

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
    # this bans the first ports 0-999 and 4242 for shellinaboxd
    "banned_ports": [{
        "start": 0,
        "end": 1000
    }, {
        "start": 4242,
        "end": 4242
    }]
})

problem_schema = Schema({
    Required("author"): All(str, Length(min=1, max=32)),
    Required("score"): All(int, Range(min=0)),
    Required("name"): All(str, Length(min=1, max=32)),
    Required("description"): str,
    Required("category"): All(str, Length(min=1, max=32)),
    Required("hints"): list,
    "version": All(str, Length(min=1, max=8)),
    "tags": list,
    "organization": All(str, Length(min=1, max=32)),
    "pkg_description": All(str, Length(min=1, max=256)),
    "pkg_name": All(str, Length(min=1, max=32)),
    "pkg_dependencies": list,
    "pip_requirements": list
})

bundle_schema = Schema({
    Required("author"): All(str, Length(min=1, max=32)),
    Required("problems"): list,
    Required("name"): All(str, Length(min=1, max=32)),
    Required("description"): str,
    Required("categories"): list,
    "version": All(str, Length(min=1, max=8)),
    "tags": list,
    "organization": All(str, Length(min=1, max=32)),
    "dependencies": dict,
    "pkg_dependencies": list
})

config_schema = Schema(
    {
        Required("deploy_secret"): str,
        Required("hostname"): str,
        Required("web_server"): str,
        Required("default_user"): str,
        Required("web_root"): str,
        Required("problem_directory_root"): str,
        Required("obfuscate_problem_directories"): bool,
        Required("banned_ports"): list
    },
    extra=True)

port_range_schema = Schema({
    Required("start"):
    All(int, Range(min=0, max=66635)),
    Required("end"):
    All(int, Range(min=0, max=66635))
})


class FatalException(Exception):
    pass


def get_attributes(obj):
    """
    Returns all attributes of an object, excluding those that start with
    an underscore

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
    Sanitize a given name such that it conforms to unix policy.

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


#I will never understand why the shutil functions act
#the way they do...


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


def get_problem(problem_path):
    """
    Retrieve a problem spec from a given problem directory.

    Args:
        problem_path: path to the root of the problem directory.

    Returns:
        A problem object.
    """

    json_path = join(problem_path, "problem.json")
    problem = json.loads(open(json_path, "r").read())

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

    bundle_root = join(BUNDLE_ROOT, sanitize_name(bundle_name))

    assert bundle_root.startswith(sep)
    if absolute:
        return bundle_root

    return bundle_root[len(sep):]


def get_bundle(bundle_path):
    """
    Retrieve a bundle spec from a given bundle directory.

    Args:
        bundle_path: path to the root of the bundle directory.

    Returns:
        A bundle object.
    """

    json_path = join(bundle_path, "bundle.json")

    bundle = json.loads(open(json_path, "r").read())

    try:
        bundle_schema(bundle)
    except MultipleInvalid as e:
        logger.critical("Error validating bundle object at '%s'!", json_path)
        logger.critical(e)
        raise FatalException

    return bundle


def verify_config(config_object):
    """
    Verifies the given configuration dict against the config_schema and the port_range_schema
    Raise FatalException if failed.

    Args:
        config_object: The configuration options in a dict
    """

    try:
        config_schema(config_object)
    except MultipleInvalid as e:
        logger.critical("Error validating config file at '%s'!", path)
        logger.critical(e)
        raise FatalException

    for port_range in config_object["banned_ports"]:
        try:
            port_range_schema(port_range)
            assert port_range["start"] <= port_range["end"]
        except MultipleInvalid as e:
            logger.critical(
                "Error validating port range in config file at '%s'!", path)
            logger.critical(e)
            raise FatalException
        except AssertionError as e:
            logger.critical("Invalid port range: (%d -> %d)",
                            port_range["start"], port_range["end"])
            raise FatalException


def get_config(path):
    """
    Retrieve a configuration object from the given path

    Args:
        path: the full path to the json file

    Returns:
        A python object containing the fields within
    """

    with open(path) as f:
        config_object = json.loads(f.read())

    verify_config(config_object)

    config = ConfigDict()
    for key, value in config_object.items():
        config[key] = value

    return config


def get_hacksports_config():
    """
    Returns the global configuration options from the file in HACKSPORTS_ROOT
    """

    return get_config(join(HACKSPORTS_ROOT, "config.json"))


def write_configuration_file(path, config_dict):
    """
    Write the options in config_dict to the specified path as JSON

    Args:
        path: the path of the output JSON file
        config_dict: the configuration dictionary
    """

    verify_config(config_dict)

    with open(path, "w") as f:
        json_data = json.dumps(
            config_dict, sort_keys=True, indent=4, separators=(',', ': '))
        f.write(json_data)


def write_global_configuration(config_dict):
    """
    Write the options in config_dict to the global config file

    Args:
        config_dict: the configuration dictionary
    """

    write_configuration_file(join(HACKSPORTS_ROOT, "config.json"), config_dict)


def place_default_config(destination=join(HACKSPORTS_ROOT, "config.json")):
    """
    Places a default configuration file in the destination

    Args:
        destination: Where to place the default configuration. Defaults to HACKSPORTS_ROOT/config.json
    """

    write_configuration_file(destination, default_config)
    chmod(destination, 0o640)
