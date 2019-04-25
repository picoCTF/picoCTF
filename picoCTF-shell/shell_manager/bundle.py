"""
Bundling operation for the shell manager. A special case of packaging.
"""

import copy as object_copy
import json
import logging
import os
from os import chmod, getcwd, makedirs
from os.path import dirname, isdir, join
from shutil import copyfile, rmtree

import spur
from shell_manager.package import DEB_DEFAULTS
from shell_manager.util import (BUNDLE_ROOT, FatalException, get_bundle,
                                get_bundle_root, get_problem, get_problem_root,
                                sanitize_name)

logger = logging.getLogger(__name__)


def bundle_to_control(bundle, debian_path):
    """
    Create a deb control file for a bundle.

    Args:
        bundle: the bundle object.
        debian_path: path to the DEBIAN directory
    """

    control = object_copy.deepcopy(DEB_DEFAULTS)
    control.update(
        **{
            "Package": sanitize_name(bundle["name"]),
            "Version": bundle.get("version", "1.0-0"),
            "Architecture": bundle.get("architecture", "all"),
            "Maintainer": bundle["author"],
            "Description": bundle["description"]
        })

    # Need to install problems and bundle dependencies.
    pkg_dependencies = bundle["problems"] + bundle.get("pkg_dependencies", [])
    control["Depends"] = ", ".join(pkg_dependencies)

    contents = ""
    for option, value in sorted(control.items()):
        contents += "{}: {}\n".format(option, value)

    control_file = open(join(debian_path, "control"), "w")
    control_file.write(contents)
    control_file.close()

    logger.debug("Control file contents:\n%s", contents)


def bundle_problems(args, config):
    """
    Main entrypoint for generating problem bundles.
    """

    bundle_path = args.bundle_path
    if os.path.isdir(args.bundle_path):
        bundle = get_bundle(args.bundle_path)
        bundle_path = join(args.bundle_path, "bundle.json")
    elif os.path.isfile(args.bundle_path):
        bundle = json.loads(open(args.bundle_path).read())
    else:
        logger.error("No bundle could be found at '%s'", args.bundle_path)
        raise FatalException

    logger.debug("Starting to bundle: '%s'.", bundle["name"])

    for problem_name in bundle["problems"]:
        installed_path = get_problem_root(problem_name, absolute=True)
        if not isdir(installed_path) or not get_problem(installed_path):
            logger.error("'%s' is not an installed problem.", problem_name)
            raise FatalException

    paths = {"working": getcwd() if args.out is None else args.out}

    if args.staging_dir:
        paths["staging"] = join(args.staging_dir, "__staging")
    else:
        paths["staging"] = join(paths["working"], "__staging")

    paths["debian"] = join(paths["staging"], "DEBIAN")
    paths["bundle_root"] = join(paths["staging"],
                                get_bundle_root(bundle["name"]))

    [
        makedirs(staging_path)
        for _, staging_path in paths.items()
        if not isdir(staging_path)
    ]

    # note that this chmod does not work correct if on a vagrant shared folder,
    # so we need to package the problems elsewhere
    chmod(dirname(paths["bundle_root"]), 0o750)

    bundle_to_control(bundle, paths["debian"])

    copied_bundle_path = join(paths["bundle_root"], "bundle.json")
    copyfile(bundle_path, copied_bundle_path)

    def format_deb_file_name(bundle):
        """
        Prepare the file name of the deb package according to deb policy.

        Args:
            bundle: the bundle object

        Returns:
           An acceptable file name for the bundle.
        """

        raw_package_name = "{}-{}-bundle-{}.deb".format(
            sanitize_name(bundle.get("organization", "ctf")),
            sanitize_name(bundle["name"]),
            sanitize_name(bundle.get("version", "1.0-0")))

        return raw_package_name

    deb_path = join(paths["working"], format_deb_file_name(bundle))

    shell = spur.LocalShell()
    result = shell.run(
        ["fakeroot", "dpkg-deb", "--build", paths["staging"], deb_path])

    if result.return_code != 0:
        logger.error("Error building bundle deb for '%s'.", bundle["name"])
        logger.error(result.output)
    else:
        logger.info("Bundle '%s' packaged successfully.", bundle["name"])

    logger.debug("Clearning up '%s' staging directory '%s'.", bundle["name"],
                 paths["staging"])

    rmtree(paths["staging"])
