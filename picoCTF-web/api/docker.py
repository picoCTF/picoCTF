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


def ensure_consistency(tid):
    """
    Ensure consistency of a team's containers with ground truth from docker
    daemon. This catches scenarios where a container died, or was killed by
    timeout.

    Args:
        tid: The team id to lookup containers for
    """

    tracked_cids = {c['cid']: c for c in list_containers_db(tid)}
    actual = list_containers_daemon(tid)

    # ensure we are tracking all actual containers
    for container in actual:
        try:
            tracked_cids.pop(container.id)
            # XXX: add check for expiration
        except KeyError:
            # container exists but is not in database so delete
            print("untracked: ", container.id)
            delete(container.id)

    # remove any tracked containers that no longer exist
    for container_id in tracked_cids:
        print("tracked but non existent:", container_id)
        delete(container_id)

    return actual

def create(tid, image_name):
    """
    Start a new container from the specified image.

    Args:
        tid: The team id to lookup containers for
        image_name: the sha256 digest for the image to launch
    Returns:
        A dictionary containing the container_id and port mappings for the newly
        running container. success is False on any errors.
    """

    # Query information about the requested image to ensure it exists and get
    # problem and port mapping information
    db = api.common.get_conn()
    image_info = db.images.find_one({"digests": image_name})
    if image_info is None:
        return {"success": False, "message": "Invalid image"}
    pid = image_info["pid"]

    # Update database with ground truth
    existing_containers = ensure_consistency(tid)

    # Check if team has exceeded the number of allowed containers
    settings = api.config.get_settings()
    if "containers_per_team" in settings:
        num_allowed = settings["containers_per_user"]
        if num_allowed >= len(existing_containers):
            msg = "Container limit Reached. Stop another challenge to start this challenge"
            return {"success": False, "message": msg}

    # check if a container already exists for this challenge
    if db.containers.find_one({"tid": tid, "pid": pid}) is not None:
        msg = "Challenge already running. Use reset to get a fresh version"
        return {"success": False, "message": msg}

    client, api_client = get_clients()
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
        return {"success": False, "message": "Error creating container"}

    container_id = container.id

    ports = api_client.inspect_container(container_id)['NetworkSettings']['Ports']
    print("ports: ", ports)

    # store container information in database
    data = {"cid": container_id,
            "ports": ports,
            "tid": tid,
            "pid": pid}

    db.containers.insert(data)

    # XXX: Get metadata about the running container into the container itself
    return {
        "success": True,
        "message": "Challenge started",
        "container_id": container_id,
        "ports": ports
    }

def delete(cid):
    """
    Kills and removes a running container. Also updates the database.

    Args:
        cid: container id to stop and remove from database
    """

    client, _ = get_clients()

    try:
        # kill and remove container on docker daemon
        container = client.containers.get(cid)
        container.remove(force=True)
    except docker.errors.NotFound as e:
        print("container not found: ", cid)
    except docker.errors.APIError as e:
        print("docker error: " + e.explanation)
        return False

    # also remove from database
    db = api.common.get_conn()
    db.containers.delete_many({"cid": cid})
    return True


def list_containers_daemon(tid):
    """
    List the currently running containers for a team. Checks ground truth by
    querying the docker daemon.

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


# XXX: streamline just necessary information (don't return raw cursor)
def list_containers_db(tid):
    """
    List the currently running containers for a team. Checks metadata stored in
    the database. There is the potential that this information is stale however
    consistency is updated on any container related requests for the given team.
    This function is appropriate for non-container related functions.

    Args:
        tid: The team id to lookup containers for
    Returns:
        mongo cursor (iterator) over the tracked containers
    """

    db = api.common.get_conn()
    return db.containers.find({"tid": tid})
