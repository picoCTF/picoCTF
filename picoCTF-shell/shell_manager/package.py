"""
Packaging operations for the shell manager.
"""

import gzip
import json
import logging
import os
import re
from copy import deepcopy
from os import chmod, getcwd, listdir, makedirs
from os.path import dirname, isdir, isfile, join
from shutil import copy, rmtree

import spur
from shell_manager.util import (FatalException, full_copy, get_problem,
                                get_problem_root, move, sanitize_name)

logger = logging.getLogger(__name__)

DEB_DEFAULTS = {
    "Section": "ctf",
    "Priority": "standard",
}


def problem_to_control(problem, debian_path):
    """
    Convert problem.json to a deb control file.

    Args:
        problem: deserialized problem.json (dict)
        debian_path: path to the DEBIAN directory
    """

    # a-z, digits 0-9, plus + and minus - signs, and periods
    package_name = problem.get("pkg_name", problem["name"])
    sanitized_name = sanitize_name(package_name)
    control = deepcopy(DEB_DEFAULTS)
    control.update(
        **{
            "Package": sanitized_name,
            "Version": problem.get("version", "1.0-0"),
            "Architecture": problem.get("architecture", "all"),
            "Maintainer": problem["author"],
            "Description": problem.get("pkg_description", problem[
                "description"])
        })

    if "pkg_dependencies" in problem:
        control["Depends"] = ", ".join(problem.get("pkg_dependencies", []))

    contents = ""
    for option, value in sorted(control.items()):
        contents += "{}: {}\n".format(option, value)

    control_file = open(join(debian_path, "control"), "w")
    control_file.write(contents)
    control_file.close()

    logger.debug("Control file contents:\n%s", contents)


def postinst_dependencies(problem, problem_path, debian_path, install_path):
    """
    Handles the generation of the postinst script for additional dependencies.

    Args:
        problem: the problem object.
        problem_path: the problem directory.
        debian_path: the deb's DEBIAN directory.
    """

    postinst_template = ["#!/bin/bash"]

    requirements_path = join(problem_path, "requirements.txt")
    dependencies_path = join(problem_path, "install_dependencies")

    staging_requirements_path = join(install_path, "requirements.txt")

    deployed_requirements_path = join(
        get_problem_root(problem["name"], absolute=True), "__files",
        "requirements.txt")
    deployed_setup_path = join(
        get_problem_root(problem["name"], absolute=True), "__files",
        "install_dependencies")

    listed_requirements = problem.get("pip_requirements", [])

    pip_python_version = problem.get("pip_python_version")
    valid_pip_python_versions = ["2", "3", "3.6"]
    if pip_python_version not in valid_pip_python_versions:
        pip_python_version = "3"

    # Write or copy the requirements to the staging directory.
    if len(listed_requirements) > 0:
        if isfile(requirements_path):
            logger.error(
                "Problem '%s' has both a pip_requirements field and requirements.txt.",
                problem["name"])
            raise FatalException

        with open(staging_requirements_path, "w") as f:
            f.writelines("\n".join(listed_requirements))

    elif isfile(requirements_path):
        copy(requirements_path, staging_requirements_path)

    if logger.getEffectiveLevel() <= logging.DEBUG and isfile(
            staging_requirements_path):
        with open(staging_requirements_path, "r") as f:
            logger.debug("python requirements:\n%s", f.read())

    if isfile(staging_requirements_path):
        postinst_template.append("python{ver} -m pip install -r {path}".format(
            ver=pip_python_version, path=deployed_requirements_path))

    if isfile(dependencies_path):
        copy(dependencies_path, join(install_path, "install_dependencies"))

        # Ensure it is executable
        chmod(join(install_path, "install_dependencies"), 0o500)

        postinst_template.append("bash -c '{}'".format(deployed_setup_path))

    chmod(debian_path, 0o775)

    postinst_path = join(debian_path, "postinst")
    with open(postinst_path, "w") as f:
        chmod(postinst_path, 0o775)
        contents = "\n".join(postinst_template)
        f.write(contents)

        # post_template always has a she-bang.
        if len(postinst_template) > 1:
            logger.debug("post install:\n%s", contents)


def find_problems(problem_path):
    """
    Find all problems that exist under the given root.
    We consider any directory with a problem.json to be an intended problem directory.

    Args:
        problem_path: the problem directory
    Returns:
        A list of problem paths returned from get_problem.
    """

    problem_paths = []

    for root, _, files in os.walk(problem_path):
        if "problem.json" in files and "__staging" not in root:
            problem_paths.append(root)

    return problem_paths


def problem_builder(args, config):
    """
    Main entrypoint for package building operations.
    """

    # Grab a problem_path
    problem_base_path = args.problem_paths.pop()

    problem_paths = find_problems(problem_base_path)

    if len(problem_paths) == 0:
        logging.critical("No problems found under '%s'!", problem_base_path)
        raise FatalException

    for problem_path in problem_paths:
        problem = get_problem(problem_path)

        logger.debug("Starting to package: '%s'.", problem["name"])

        paths = {}
        if args.staging_dir is None:
            paths["staging"] = join(problem_path, "__staging")
        else:
            paths["staging"] = join(args.staging_dir, "__staging")

        paths["debian"] = join(paths["staging"], "DEBIAN")
        paths["data"] = join(paths["staging"],
                             get_problem_root(problem["name"]))
        paths["install_data"] = join(paths["data"], "__files")

        # Make all of the directories, order does not matter with makedirs
        [
            makedirs(staging_path)
            for _, staging_path in paths.items()
            if not isdir(staging_path)
        ]

        args.ignore.append("__staging")

        full_copy(problem_path, paths["data"], ignore=args.ignore)

        # note that this chmod does not work correct if on a vagrant shared folder,
        # so we need to package the problems elsewhere
        chmod(paths["data"], 0o750)

        problem_to_control(problem, paths["debian"])

        postinst_dependencies(problem, problem_path, paths["debian"],
                              paths["install_data"])

        deb_directory = args.out if args.out is not None else getcwd()

        def format_deb_file_name(problem):
            """
            Prepare the file name of the deb package according to deb policy.

            Args:
                problem: the problem object

            Returns:
            An acceptable file name for the problem.
            """

            raw_package_name = "{}-{}-{}.deb".format(
                sanitize_name(problem.get("organization", "ctf")),
                sanitize_name(problem.get("pkg_name", problem["name"])),
                sanitize_name(problem.get("version", "1.0-0")))

            return raw_package_name

        deb_path = join(deb_directory, format_deb_file_name(problem))

        shell = spur.LocalShell()
        result = shell.run(
            ["fakeroot", "dpkg-deb", "--build", paths["staging"], deb_path])

        if result.return_code != 0:
            logger.error("Error building problem deb for '%s'.",
                         problem["name"])
            logger.error(result.output)
        else:
            logger.info("Problem '%s' packaged successfully.", problem["name"])

        logger.debug("Clearning up '%s' staging directory '%s'.",
                     problem["name"], paths["staging"])

        rmtree(paths["staging"])

    if len(args.problem_paths) >= 1:
        return problem_builder(args, config)
