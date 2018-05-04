"""
Utilities for dealing with configuration commands
"""

import json
import logging
import os

from shell_manager.util import (FatalException, get_config,
                                place_default_config, write_configuration_file,
                                write_global_configuration)

logger = logging.getLogger(__name__)


def port_range_to_str(port_range):
    if port_range["start"] == port_range["end"]:
        return str(port_range["start"])
    return "%d-%d" % (port_range["start"], port_range["end"])


def banned_ports_to_str(banned_ports):
    return "[" + ", ".join(map(port_range_to_str, banned_ports)) + "]"


def print_configuration(args, global_config):
    """
    Entry point for config subcommand
    """

    if args.file == None:
        config = global_config
    else:
        try:
            config = get_config(args.file)
        except FileNotFoundError:
            logger.fatal("Could not find configuration file '%s'", args.file)
            raise FatalException

    if args.json:
        print("Configuration options (in JSON):")
    else:
        print("Configuration options (pretty printed):")

    for option, value in config.items():
        if args.json:
            value_string = json.dumps(value)
        else:
            if option == "banned_ports":
                value_string = banned_ports_to_str(value)
            else:
                value_string = repr(value)

        print("  %s = %s" % (option.ljust(50), value_string))


def set_configuration_option(args, global_config):
    """
    Entry point for config set subcommand
    """

    if args.file == None:
        config = global_config
    else:
        try:
            config = get_config(args.file)
        except FileNotFoundError:
            logger.fatal("Could not find configuration file '%s'", args.file)
            raise FatalException

    field = args.field
    value = args.value
    if args.json:
        try:
            value = json.loads(args.value)
        except Exception as e:
            logger.fatal("Couldn't parse value as JSON")
            raise FatalException

    if field in config and type(
            config[field]) != type(value) and not args.allow_type_change:
        logger.fatal("Tried to change type of '%s' from '%s' to '%s'", field,
                     type(config[field]), type(value))
        logger.fatal("Try adding --json and supplying the value as json.")
        logger.fatal(
            "If changing the type is desired, add the --allow-type-change option"
        )
        raise FatalException

    config[field] = value

    if args.file:
        write_configuration_file(args.file, config)
    else:
        write_global_configuration(config)

    logger.info("Set {} = {}".format(field, value))


def new_configuration_file(args, global_config):
    """
    Entry point for config new subcommand
    """

    for path in args.files:
        if not args.overwrite and os.path.exists(path):
            logger.warning(
                "'%s' already exists. Not placing new configuration.", path)
            continue

        place_default_config(path)
        logger.info("Default configuration file '%s' was created", path)
