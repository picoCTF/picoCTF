import time

import docker

import api
from api.common import SevereInternalException

log = api.logger.use(__name__)

# global docker clients
__client = None
# low-level Docker API Client: https://docker-py.readthedocs.io/en/stable/api.html?#
__api_client = None


def get_clients():
    """
    Get a high level and a low level docker client connection,

    Ensures that only one global docker client exists per thread. If the client
    does not exist a new one is created and returned.
    """

    global __client, __api_client
    if not __client or not __api_client:
        try:
            conf = api.app.app.config

            # use an explicit remote docker daemon per the configuration
            opts = ["DOCKER_HOST", "DOCKER_CA", "DOCKER_CLIENT", "DOCKER_KEY"]
            if all([o in conf for o in opts]):
                host, ca, client, key = [conf[o] for o in opts]

                log.debug("Connecting to docker daemon with config")
                tls_config = docker.tls.TLSConfig(ca_cert=ca, client_cert=(client, key))
                __api_client = docker.APIClient(base_url=host, tls=tls_config)
                __client = docker.DockerClient(base_url=host, tls=tls_config)

            # Docker options not set in configuration so attempt to use unix socket
            else:
                log.debug("Connecting to docker daemon on local unix socket")
                __api_client = docker.APIClient(base_url="unix:///var/run/docker.sock")
                __client = docker.DockerClient(base_url="unix:///var/run/docker.sock")

            # ensure a responsive connection
            __client.ping()
        except docker.errors.APIError as e:
            raise SevereInternalException("Could not connect to docker daemon:" + e)

    return __client, __api_client


def create(tid, image_name):
    """
    Start a new container from the specified image.

    Args:
        tid: The team id to lookup containers for
        image_name: the sha256 digest for the image to launch
    Returns:
        A dictionary containing the container_id and port mappings for the newly
        running container. sucess is False on any errors.
    """

    client, api_client = get_clients()
    # XXX: manage total number of containers per user
    # XXX: prevent duplicate containers per challenge
    # XXX: manage container longevity and deletion
    labels = {"owner": str(tid), "delete_at": str(int(time.time()) + 20 * 60)}
    try:
        container = client.containers.run(
            image=image_name,
            labels=labels,
            detach=True,
            remove=True,
            publish_all_ports=True)
    except docker.errors.APIError as e:
        print("error: " + e.explanation)
        return {"sucess": False, "message": "Error creating container"}

    container_id = container.id

    ports = api_client.inspect_container(container_id)['NetworkSettings']['Ports']
    print("ports: ", ports)

    # XXX: Get metadata about the running container into the container itself
    return {
        "success": True,
        "message": "Challenge started",
        "container_id": container_id,
        "ports": ports
    }


def list_containers(tid):
    """
    List the currently running containers for a team

    Args:
        tid: The team id to lookup containers for
    Returns:
        list of Container objects, or None on error
    """
    try:
        client, _ = get_clients()
        filters = {"label": "owner={}".format(tid)}
        existing = client.containers.list(filters=filters)
    except docker.errors.APIError as e:
        print("error: " + e.explanation)
        return None
    return existing
