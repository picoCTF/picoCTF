"""
Low level deployment operations.
"""

from os import makedirs, path
from random import randint, Random
from signal import SIGKILL
from time import time

from spur import LocalShell


class TimeoutError(Exception):
    """
    Exception dealing with executed commands that timeout.
    """
    pass


def execute(cmd, timeout=60, **kwargs):
    """
    Executes the given shell command

    Args:
        cmd: List of command arguments
        timeout: maximum alloted time for the command
        **kwargs: passes to LocalShell.spawn
    Returns:
        An execution result.
    Raises:
        NoSuchCommandError, RunProcessError, FileNotFoundError
    """

    shell = LocalShell()

    # It is unlikely that someone actually intends to supply
    # a string based on how spur works.
    if type(cmd) == str:
        cmd = ["bash", "-c"] + [cmd]

    process = shell.spawn(cmd, store_pid=True, **kwargs)
    start_time = time()

    while process.is_running():
        delta_time = time() - start_time
        if delta_time > timeout:
            process.send_signal(SIGKILL)
            raise TimeoutError(cmd, timeout)

    return process.wait_for_result()


def create_user(username):
    """
    Creates a user account with the given username

    Args:
        username: the username to create

    """

    execute(["useradd", "-s", "/bin/bash", username])
