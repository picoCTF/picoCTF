"""
Problem repository management for the shell manager.
"""

import gzip
import logging
from os import makedirs
from os.path import exists, isdir, join
from shutil import copy2

import spur
from shell_manager.util import FatalException

logger = logging.getLogger(__name__)


def update_repo(args, config):
    """
    Main entrypoint for repo update operations.
    """

    if args.repo_type == "local":
        local_update(args.repository, args.package_paths)
    else:
        remote_update(args.repository, args.package_paths)


def remote_update(repo_ui, deb_paths=[]):
    """
    Pushes packages to a remote deb repository.

    Args:
        repo_uri: location of the repository.
        deb_paths: list of problem deb paths to copy.
    """

    logger.error("Currently not implemented -- sorry!")
    raise FatalException


def local_update(repo_path, deb_paths=[]):
    """
    Updates a local deb repository by copying debs and running scanpackages.

    Args:
        repo_path: the path to the local repository.
        dep_paths: list of problem deb paths to copy.
    """

    if not exists(repo_path):
        logger.info("Creating repository at '%s'.", repo_path)
        makedirs(repo_path)
    elif not isdir(repo_path):
        logger.error("Repository '%s' is not a directory!", repo_path)
        raise FatalException

    [copy2(deb_path, repo_path) for deb_path in deb_paths]

    shell = spur.LocalShell()
    result = shell.run(["dpkg-scanpackages", ".", "/dev/null"], cwd=repo_path)

    packages_path = join(repo_path, "Packages.gz")
    with gzip.open(packages_path, "wb") as packages:
        packages.write(result.output)

    logger.info("Repository '%s' updated successfully. Copied %d packages.",
                repo_path, len(deb_paths))
