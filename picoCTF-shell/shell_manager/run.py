#!/usr/bin/env python3
"""
Shell Manager -- Tools for deploying and packaging problems.
"""

import json
import logging
from argparse import ArgumentParser

import coloredlogs
import shell_manager
from hacksport.deploy import deploy_problems, undeploy_problems
from hacksport.status import clean, publish, status
from shell_manager.bundle import bundle_problems
from shell_manager.config import (new_configuration_file, print_configuration,
                                  set_configuration_option)
from shell_manager.package import problem_builder
from shell_manager.problem_repo import update_repo
from shell_manager.util import (FatalException, get_hacksports_config,
                                place_default_config)

coloredlogs.DEFAULT_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"
coloredlogs.DEFAULT_DATE_FORMAT = "%H:%M:%S"

logger = logging.getLogger(__name__)


def main():
    parser = ArgumentParser(description="Shell Manager")
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="show debug information")
    parser.add_argument(
        "--colorize",
        default="auto",
        choices=["auto", "never"],
        help="support colored output")
    subparsers = parser.add_subparsers()

    problem_package_parser = subparsers.add_parser(
        "package", help="problem package management")
    problem_package_parser.add_argument(
        "-s",
        "--staging-dir",
        help="use an explicit directory for problem staging.")
    problem_package_parser.add_argument(
        "-o", "--out", help="folder to store problem package.")
    problem_package_parser.add_argument(
        "-i",
        "--ignore",
        dest="ignore",
        default=[],
        action="append",
        help="list of files to ignore adding to the deb")
    problem_package_parser.add_argument(
        "problem_paths", nargs="*", type=str, help="paths to problems.")
    problem_package_parser.set_defaults(func=problem_builder)

    publish_repo_parser = subparsers.add_parser(
        "publish_repo", help="publish packaged problems")
    publish_repo_parser.add_argument(
        "-r",
        "--repository",
        default="/usr/local/ctf-packages",
        help="Location of problem repository.")
    publish_repo_parser.add_argument("repo_type", choices=["local", "remote"])
    publish_repo_parser.add_argument(
        "package_paths",
        nargs="+",
        type=str,
        help="problem packages to publish.")
    publish_repo_parser.set_defaults(func=update_repo)

    bundle_parser = subparsers.add_parser(
        "bundle", help="create a bundle of problems")
    bundle_parser.add_argument(
        "bundle_path", type=str, help="the name of the bundle.")
    bundle_parser.add_argument(
        "-s",
        "--staging-dir",
        help="use an explicit directory for problem staging.")
    bundle_parser.add_argument(
        "-o", "--out", type=str, help="folder to store the bundle.")
    bundle_parser.set_defaults(func=bundle_problems)

    deploy_parser = subparsers.add_parser("deploy", help="problem deployment")
    deploy_parser.add_argument(
        "-n",
        "--num-instances",
        type=int,
        default=1,
        help="number of instances to generate (numbers 0 through n-1).")
    deploy_parser.add_argument(
        "-i",
        "--instances",
        action="append",
        type=int,
        help="particular instance(s) to generate.")
    deploy_parser.add_argument(
        "-d",
        "--dry",
        action="store_true",
        help="don't make persistent changes.")
    deploy_parser.add_argument(
        "-r",
        "--redeploy",
        action="store_true",
        help="redeploy instances that have already been deployed")
    deploy_parser.add_argument(
        "-s",
        "--secret",
        action="store",
        type=str,
        help="use a different deployment secret for this invocation.")
    deploy_parser.add_argument(
        "-D",
        "--deployment-directory",
        type=str,
        default=None,
        help="the directory to deploy to")
    deploy_parser.add_argument(
        "-b",
        "--bundle",
        action="store_true",
        help="specify a bundle of problems to deploy.")
    deploy_parser.add_argument(
        "problem_paths", nargs="*", type=str, help="paths to problems.")
    deploy_parser.set_defaults(func=deploy_problems)

    undeploy_parser = subparsers.add_parser(
        "undeploy",
        help=
        "problem undeployment. cannot guarantee full removal of problem files")
    undeploy_parser.add_argument(
        "-n",
        "--num-instances",
        type=int,
        default=1,
        help="number of instances to undeploy (numbers 0 through n-1).")
    undeploy_parser.add_argument(
        "-i",
        "--instances",
        action="append",
        type=int,
        help="particular instance(s) to generate.")
    undeploy_parser.add_argument(
        "-b",
        "--bundle",
        action="store_true",
        help="specify a bundle of problems to undeploy.")
    undeploy_parser.add_argument(
        "problem_paths", nargs="*", type=str, help="paths to problems.")
    undeploy_parser.set_defaults(func=undeploy_problems)

    clean_parser = subparsers.add_parser(
        "clean",
        help="Clean up the intermediate staging data stored during deployments")
    clean_parser.set_defaults(func=clean)

    status_parser = subparsers.add_parser(
        "status",
        help=
        "List the installed problems and bundles and any instances associated with them."
    )
    status_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Show information about all problem instanes.")
    status_parser.add_argument(
        "-p",
        "--problem",
        type=str,
        default=None,
        help="Display status information for a given problem.")
    status_parser.add_argument(
        "-b",
        "--bundle",
        type=str,
        default=None,
        help="Display status information for a given bundle.")
    status_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=None,
        help="Display status information in json format")
    status_parser.add_argument(
        "-e",
        "--errors-only",
        action="store_true",
        help="Only print problems with failing service status.")
    status_parser.set_defaults(func=status)

    publish_parser = subparsers.add_parser(
        "publish",
        help=
        "Generate the information needed by the web server for this deployment."
    )
    publish_parser.set_defaults(func=publish)

    config_parser = subparsers.add_parser(
        "config", help="View or modify configuration options")
    config_parser.add_argument(
        "-f",
        "--file",
        type=str,
        default=None,
        help=
        "Which configuration file to access. If none is provided, the system wide configuration file will be used."
    )
    config_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help=
        "Whether to display the configuration options in JSON form or pretty printed. Defaults to False."
    )
    config_parser.set_defaults(func=print_configuration)
    config_subparsers = config_parser.add_subparsers()

    config_set_parser = config_subparsers.add_parser(
        "set", help="Set configuration options")
    config_set_parser.add_argument(
        "-f", "--field", type=str, required=True, help="which field to set")
    config_set_parser.add_argument(
        "-v", "--value", type=str, required=True, help="options's new value")
    config_set_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help="interpret the given value as JSON")
    config_set_parser.add_argument(
        "--allow-type-change",
        action="store_true",
        default=False,
        help="Allow the supplied field to change types if already specified")
    config_set_parser.set_defaults(func=set_configuration_option)

    config_new_parser = config_subparsers.add_parser(
        "new", help="Make a new configuration files with defaults")
    config_new_parser.add_argument(
        "files", nargs="+", help="Configuration files to make")
    config_new_parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="whether to overwrite files that already exist")
    config_new_parser.set_defaults(func=new_configuration_file)

    args = parser.parse_args()

    if args.colorize == "never":
        coloredlogs.DEFAULT_LEVEL_STYLES = {}
        coloredlogs.DEFAULT_FIELD_STYLES = {}

    coloredlogs.install()

    if args.debug:
        coloredlogs.set_level(logging.DEBUG)
    try:
        try:
            config = get_hacksports_config()
        except PermissionError:
            logger.error("You must run shell_manager with sudo.")
            raise FatalException
        except FileNotFoundError:
            place_default_config()
            logger.info(
                "There was no default configuration. One has been created for you. Please edit it accordingly using the 'shell_manager config' subcommand before deploying any instances."
            )
            raise FatalException

        # Call the default function
        if "func" in args:
            args.func(args, config)
        else:
            parser.print_help()
    except FatalException:
        exit(1)


if __name__ == "__main__":
    main()
