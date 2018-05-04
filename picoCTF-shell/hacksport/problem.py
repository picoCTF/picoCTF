"""
Challenge deployment and problem types.
"""

import os
from abc import ABCMeta, abstractmethod, abstractproperty
from hashlib import md5
from os.path import join
from shutil import copy2

from hacksport.deploy import give_port
from hacksport.operations import execute
from shell_manager.util import EXTRA_ROOT

XINETD_SCRIPT = """#!/bin/bash
cd $(dirname $0)
exec timeout -sKILL 3m %s
"""
XINETD_WEB_SCRIPT = """#!/bin/bash
cd $(dirname $0)
%s
"""


class File(object):
    """
    Wraps files with default permissions
    """

    def __init__(self, path, permissions=0o664, user=None, group=None):
        self.path = path
        self.permissions = permissions
        self.user = user
        self.group = group

    def __repr__(self):
        return "{}({},{})".format(self.__class__.__name__, repr(self.path),
                                  oct(self.permissions))

    def to_dict(self):
        return {
            "path": self.path,
            "permissions": self.permissions,
            "user": self.user,
            "group": self.group
        }


class Directory(File):
    """
    Wrapper for specifying permissions for your subdirectories
    """


class PreTemplatedFile(File):
    """
    Wrapper for files that should be served pre-templated.
    """

    def __init__(self, path, permissions=0o664):
        super().__init__(path, permissions=permissions)


class ExecutableFile(File):
    """
    Wrapper for executable files that will make them setgid and owned
    by the problem's group.
    """

    def __init__(self, path, permissions=0o2755):
        super().__init__(path, permissions=permissions)


class ProtectedFile(File):
    """
    Wrapper for protected files, i.e. files that can only be read after
    escalating privileges. These will be owned by the problem's group.
    """

    def __init__(self, path, permissions=0o0440):
        super().__init__(path, permissions=permissions)


def files_from_directory(directory, recurse=True, permissions=0o664):
    """
    Returns a list of File objects for every file in a directory. Can recurse optionally.

    Args:
        directory: The directory to add files from
        recurse: Whether or not to recursively add files. Defaults to true
        permissions: The default permissions for the files. Defaults to 0o664.
    """

    result = []

    for root, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            result.append(File(join(root, filename), permissions))
        if not recurse:
            break

    return result


class Challenge(metaclass=ABCMeta):
    """
    The most hands off, low level approach to creating challenges.
    Requires manual setup and generation.
    """

    files = []
    dont_template = []

    def generate_flag(self, random):
        """
        Default generation of flags.

        Args:
            random: seeded random module.
        """

        token = str(random.randint(1, 1e12))
        hash_token = md5(token.encode("utf-8")).hexdigest()

        return hash_token

    def initialize(self):
        """
        Initial setup function that runs before any other.
        """

        pass

    @abstractmethod
    def setup(self):
        """
        Main setup method for the challenge.
        This is implemented by many of the more specific problem types.
        """

        pass

    def service(self):
        """
        No-op service file values.
        """

        return {"Type": "oneshot", "ExecStart": "/bin/bash -c 'echo started'"}


class Compiled(Challenge):
    """
    Sensible behavior for compiled challenges.
    """

    compiler = "gcc"
    compiler_flags = []
    compiler_sources = []

    makefile = None

    program_name = None

    compiled_files = []

    def setup(self):
        """ No-op implementation for Challenge. """
        pass

    def compiler_setup(self):
        """
        Setup function for compiled challenges
        """

        if self.program_name is None:
            raise Exception("Must specify program_name for compiled challenge.")

        if self.makefile is not None:
            execute(["make", "-f", self.makefile])
        elif len(self.compiler_sources) > 0:
            compile_cmd = [self.compiler
                          ] + self.compiler_flags + self.compiler_sources
            compile_cmd += ["-o", self.program_name]
            execute(compile_cmd)

        if not isinstance(self, Remote):
            # only add the setgid executable if Remote is not handling it
            self.compiled_files = [ExecutableFile(self.program_name)]


class Service(Challenge):
    """
    Base class for challenges that are remote services.
    """

    service_files = []

    def setup(self):
        """
        No-op implementation of setup
        """

        pass

    def service_setup(self):
        if self.start_cmd is None:
            raise Exception("Must specify start_cmd for services.")
        open("xinet_startup.sh", 'w').write(XINETD_SCRIPT % self.start_cmd)
        self.start_cmd = join(self.directory, "xinet_startup.sh")
        self.service_files.append(ExecutableFile("xinet_startup.sh"))

    @property
    def port(self):
        """
        Provides port on-demand with caching
        """
        if not hasattr(self, '_port'):
            self._port = give_port()
        return self._port

    def service(self):
        return {"Type": "simple", "ExecStart": self.start_cmd}


class Remote(Service):
    """
    Base behavior for remote challenges that use stdin/stdout.
    """

    remove_aslr = False

    def remote_setup(self):
        """
        Setup function for remote challenges
        """

        if self.program_name is None:
            raise Exception("Must specify program_name for remote challenge.")

        if self.remove_aslr:
            # do not setgid if being wrapped
            self.service_files = [File(self.program_name, permissions=0o755)]

            self.program_name = self.make_no_aslr_wrapper(
                join(self.directory, self.program_name),
                output="{}_no_aslr".format(self.program_name))
        else:
            self.service_files = [ExecutableFile(self.program_name)]

        self.start_cmd = join(self.directory, self.program_name)

    def make_no_aslr_wrapper(self, exec_path, output="no_aslr_wrapper"):
        """
        Compiles a setgid wrapper to remove aslr.
        Returns the name of the file generated
        """

        source_path = "no_aslr_wrapper.c"
        execute([
            "gcc", "-o", output, "-DBINARY_PATH=\"{}\"".format(exec_path),
            join(EXTRA_ROOT, source_path)
        ])
        self.files.append(ExecutableFile(output))

        return output

    def service(self):
        """
        Unlike the parent class, these are executables and should be restarted each time
        """
        return {"Type": "oneshot", "ExecStart": self.start_cmd}


class WebService(Service):

    def service_setup(self):
        if self.start_cmd is None:
            raise Exception("Must specify start_cmd for services.")
        open("xinet_startup.sh", 'w').write(XINETD_WEB_SCRIPT % self.start_cmd)
        self.start_cmd = join(self.directory, "xinet_startup.sh")
        self.service_files.append(ExecutableFile("xinet_startup.sh"))


class FlaskApp(WebService):
    """
    Class for python Flask web apps
    """

    python_version = "3"
    app = "server:app"
    num_workers = 1

    @property
    def flask_secret(self):
        """
        Provides flask_secret on-demand with caching
        """
        if not hasattr(self, '_flask_secret'):
            token = str(self.random.randint(1, 1e16))
            self._flask_secret = md5(token.encode("utf-8")).hexdigest()

        return self._flask_secret

    def flask_setup(self):
        """
        Setup for flask apps
        """

        self.app_file = "{}.py".format(self.app.split(":")[0])
        assert os.path.isfile(self.app_file), "module must exist"

        if self.python_version == "2":
            plugin_version = ""
        elif self.python_version == "3":
            plugin_version = "3"
        else:
            assert False, "Python version {} is invalid".format(python_version)

        self.service_files = [File(self.app_file)]
        self.start_cmd = "uwsgi --protocol=http --plugin python{} -p {} -w {} --logto /dev/null".format(
            plugin_version, self.num_workers, self.app)


class PHPApp(WebService):
    """
    Class for PHP web apps
    """

    php_root = ""
    num_workers = 1

    def php_setup(self):
        """
        Setup for php apps
        """

        web_root = join(self.directory, self.php_root)
        self.start_cmd = "uwsgi --protocol=http --plugin php -p {1} --force-cwd {0} --http-socket-modifier1 14 --php-index index.html --php-index index.php --check-static {0} --static-skip-ext php --logto /dev/null".format(
            web_root, self.num_workers)
