"""
Challenge template to deploy instances in on-demand containers
"""

import os
from spur import RunProcessError

from hacksport.problem import Challenge
from hacksport.operations import execute

class DockerChallenge(Challenge):
    """Challenge based on a docker container.

    Class variables that must be defined:
    * problem_name - name that will show up in Docker UI for this problem
    """
    def initialize_docker(self, build_args):
        self.image_name = '{}/challenges:{}'.format(self.docker_registry, self.problem_name)
        if not self._build_docker_image(build_args):
            raise Exception('Unable to set up docker image')
        self.image_digest = self._push_docker_image()
        if self.image_digest is None:
            raise Exception('Unable to set up docker image')

    def _build_docker_image(self, build_args, timeout=600):
        """
        Run a local docker build
        Args:
            image_name: what to save the docker image as
            build_args: dict of build arguments to pass to `docker build`
            timeout: how long to allow for the build

        Returns: boolean success
        """
        command_line = ['sudo', 'docker', 'build', '-t', self.image_name,
                        '--label', 'problem={}'.format(self.problem_name)]

        for arg, val in build_args.items():
            command_line.append('--build-arg')
            command_line.append('{}={}'.format(arg, val))

        command_line.append('.')

        try:
            dev_null = open(os.devnull, 'wb')
            execute(command_line, timeout=timeout, stdout=dev_null, stderr=dev_null)
        except TimeoutError:
            print("Timeout triggered while waiting to build docker {}".format(self.image_name))
            return False
        except RunProcessError as e:
            print("Issue building docker: {}".format(e.stderr_output.decode()))
            return False
        return True

    def _push_docker_image(self, timeout=600):
        """
        Push image to docker registry

        Returns: str of image's sha256 digest if push succeeds, else None
        """
        try:
            execute(['docker', 'login', '-u', self.docker_registry_user, '-p',
                     self.docker_registry_pass, self.docker_registry], timeout=timeout)
            result = execute(['docker', 'push', self.image_name], timeout=timeout)
            execute(['docker', 'logout', self.docker_registry], timeout=timeout)
        except TimeoutError:
            print("Timeout triggered while pushing docker image {}".format(self.image_name))
            return None
        except RunProcessError as e:
            print("Error pushing docker image: {}".format(e.stderr_output.decode()))
            return None

        for line in result.output.splitlines():
            words = line.split()
            if len(words) >= 3 and words[1] == b'digest:' and words[2].startswith(b'sha256:'):
                return words[2][len(b'sha256:'):].decode()

        print("Unexpected output format from docker push: {}".format(result.output.decode()))
        return None
