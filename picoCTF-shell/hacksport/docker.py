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
    problem_name = None         # XXX: should be able to derive
    ports = {}

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
        img = self._build_docker_image(build_args, timeout)
        if img is None:
            raise Exception('Unable to build docker image')

        self.image_digest = img.id

        try:
            exposed_ports = img.attrs["Config"]["ExposedPorts"].keys()
        except KeyError:
            raise Exception("Dockerfile must expose at least 1 port")

        # Ensure all ports are represented and convert to ints, e.g. "5555/tcp"
        image_ports = [int(p.split("/")[0]) for p in exposed_ports]
        for p in image_ports:
            if p not in self.ports:
                self.ports[p] = Plain("challenge")

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

        return img


# Utility classes to handle templating of ports. Will get formated twice in the
# following order host, then port (this is why the extra {} in the fmt string)
class HTTP():
    def __init__(self, desc, path="", link_text=""):
        self.desc = desc
        self.path = path
        self.link_text = link_text

    def dict(self):
        url = "http://{host}:{{port}}" + self.path
        if self.link_text == "":
            link = "<a href='{}'>{}</a>".format(url, url)
        else:
            link = "<a href='{}'>{}</a>".format(url, self.link_text)
        return {"fmt": link, "desc": self.desc}

class Netcat():
    def __init__(self, desc):
        self.desc = desc

    def dict(self):
        return {"fmt": "nc {host} {{port}}", "desc": self.desc}

class Plain():
    def __init__(self, desc):
        self.desc = desc

    def dict(self):
        return {"fmt": "{host}:{{port}}", "desc": self.desc}

class Custom():
    def __init__(self, fmt, desc):
        self.desc = desc

    def dict(self):
        return {"fmt": self.fmt, "desc": self.desc}
