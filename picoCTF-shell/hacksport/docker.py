"""
Challenge template to deploy instances in on-demand containers
"""

import logging

import docker

from hacksport.problem import Challenge

logger = logging.getLogger(__name__)

class DockerChallenge(Challenge):
    """Challenge based on a docker container.

    Class variables that must be defined:
    * problem_name - name that will show up in Docker UI for this problem
    """

    def __init__(self):
        """ Connnects to the docker daemon"""
        # use an explicit remote docker daemon per the configuration
        try:
            tls_config = docker.tls.TLSConfig(
                ca_cert=self.docker_ca_cert,
                client_cert=(self.docker_client_cert, self.docker_client_key))

            self.client = docker.DockerClient(base_url=self.docker_host, tls=tls_config)
            logger.debug("Connecting to docker daemon with config")

        # Docker options not set in configuration so use the environment to
        # configure (could be local or remote)
        except AttributeError:
            logger.debug("Connecting to docker daemon with env")
            self.client = docker.from_env()

        # throws an exception if the server returns an error: docker.errors.APIError
        self.client.ping()

    def initialize_docker(self, build_args, timeout=600):

        self.image_name = 'challenges:{}'.format(self.problem_name)

        logger.debug("Building docker image: {}".format(self.image_name))
        self.image_digest = self._build_docker_image(build_args, timeout)
        if self.image_digest is None:
            raise Exception('Unable to build docker image')
        logger.debug("Built image, digest: {}".format(self.image_digest))

    def _build_docker_image(self, build_args, timeout):
        """
        Run a docker build
        Args:
            build_args: dict of build arguments to pass to `docker build`
            timeout: how long to allow for the build

        Returns: boolean success
        """

        try:
            img, logs = self.client.images.build(
                path='.',
                tag=self.image_name,
                buildargs=build_args,
                labels={'problem': self.problem_name},
                timeout=timeout)
        except docker.errors.BuildError as e:
            logger.error("Docker Build Error: " + e.msg)
            logger.debug(e.build_log)
            return None
        except docker.errors.APIError as e:
            logger.error("Docker API Error: " + e.explanation)
            return None

        return img.id
