"""
Problem deployment.
"""

PROBLEM_FILES_DIR = "problem_files"
STATIC_FILE_ROOT = "static"
XINETD_SERVICE_PATH = "/etc/xinetd.d/"

# will be set to the configuration module during deployment
deploy_config = None

port_map = {}
inv_port_map = {}
current_problem = None
current_instance = None


def get_deploy_context():
    """
    Returns the deployment context, a dictionary containing the current
    config, port_map, problem, instance
    """

    global deploy_config, port_map, inv_port_map, current_problem, current_instance

    return {
        "config": deploy_config,
        "port_map": port_map,
        "inv_port_map": inv_port_map,
        "problem": current_problem,
        "instance": current_instance
    }


port_random = None


def give_port():
    """
    Returns a random port and registers it.
    """

    global port_random

    context = get_deploy_context()

    # default behavior
    if context["config"] is None:
        return randint(1000, 65000)

    if "banned_ports_parsed" not in context["config"]:
        banned_ports_result = []
        for port_range in context["config"].banned_ports:
            banned_ports_result.extend(
                list(range(port_range["start"], port_range["end"] + 1)))

        context["config"]["banned_ports_parsed"] = banned_ports_result

    # during real deployment, let's register a port
    if port_random is None:
        port_random = Random(context["config"].deploy_secret)

    # if this instance already has a port, reuse it
    if (context["problem"], context["instance"]) in inv_port_map:
        return inv_port_map[(context["problem"], context["instance"])]

    if len(context["port_map"].items()) + len(
            context["config"].banned_ports_parsed) == 65536:
        raise Exception(
            "All usable ports are taken. Cannot deploy any more instances.")

    while True:
        port = port_random.randint(0, 65535)
        if port not in context["config"].banned_ports_parsed:
            owner, instance = context["port_map"].get(port, (None, None))
            if owner is None or (owner == context["problem"] and
                                 instance == context["instance"]):
                context["port_map"][port] = (context["problem"],
                                             context["instance"])
                return port


import functools
import json
import logging
import os
import shutil
import traceback
from abc import ABCMeta
from copy import copy, deepcopy
from grp import getgrnam
from hashlib import md5, sha1
from imp import load_source
# These are below because of a cirucular import issue with problem.py and give_port
# [TODO] cleanup
from os.path import commonprefix, isdir, isfile, join
from pwd import getpwnam
from random import randint, Random
from time import sleep

from hacksport.operations import create_user, execute
from hacksport.problem import (Compiled, Directory, ExecutableFile, File,
                               FlaskApp, PHPApp, WebService, PreTemplatedFile,
                               ProtectedFile, Remote, Service)
from hacksport.status import get_all_problem_instances, get_all_problems
from jinja2 import Environment, FileSystemLoader, Template
from shell_manager.bundle import get_bundle, get_bundle_root
from shell_manager.util import (DEPLOYED_ROOT, FatalException, get_attributes,
                                get_problem, get_problem_root, HACKSPORTS_ROOT,
                                sanitize_name, STAGING_ROOT)
from spur import RunProcessError

logger = logging.getLogger(__name__)


def challenge_meta(attributes):
    """
    Returns a metaclass that will introduce the given attributes into the class
    namespace.

    Args:
        attributes: The dictionary of attributes

    Returns:
        The metaclass described above
    """

    class ChallengeMeta(ABCMeta):

        def __new__(cls, name, bases, attr):
            attrs = dict(attr)
            attrs.update(attributes)
            return super().__new__(cls, name, bases, attrs)

    return ChallengeMeta


def update_problem_class(Class, problem_object, seed, user, instance_directory):
    """
    Changes the metaclass of the given class to introduce necessary fields before
    object instantiation.

    Args:
        Class: The problem class to be updated
        problem_name: The problem name
        seed: The seed for the Random object
        user: The linux username for this challenge instance
        instance_directory: The deployment directory for this instance

    Returns:
        The updated class described above
    """

    random = Random(seed)
    attributes = deepcopy(problem_object)

    # pass configuration options in as class fields
    attributes.update(dict(deploy_config))

    attributes.update({
        "random": random,
        "user": user,
        "directory": instance_directory,
        "server": deploy_config.hostname
    })

    return challenge_meta(attributes)(Class.__name__, Class.__bases__,
                                      Class.__dict__)


def get_username(problem_name, instance_number):
    """
    Determine the username for a given problem instance.
    """

    return "{}_{}".format(sanitize_name(problem_name), instance_number)


def create_service_files(problem, instance_number, path):
    """
    Creates xinetd service files for the given problem.
    Creates a service file for a problem

    Args:
        problem: the instantiated problem object
        instance_number: the instance number
        path: the location to drop the service file
    Returns:
        A tuple containing (service_file_path, socket_file_path).
        socket_file_path will be None if the problem is not a service.
    """

    # See https://github.com/puppetlabs/puppetlabs-xinetd/blob/master/templates/service.erb
    # and https://linux.die.net/man/5/xinetd.conf
    xinetd_template = """
service %s
{
    type = UNLISTED
    port = %d
    disable = no
    socket_type = stream
    protocol = tcp
    wait = %s
    user = %s
    group = %s
    log_type = FILE /var/log/xinetd-hacksport-%s.log
    log_on_success = HOST EXIT DURATION
    log_on_failure = HOST
    cps = 50 3
    rlimit_cpu = %s
    per_source = 100
    server = %s
}
"""

    is_service = isinstance(problem, Service)
    is_web = isinstance(problem, WebService)
    if not is_service and not is_web:
        return (None, None)

    problem_service_info = problem.service()
    service_content = xinetd_template % (
        problem.user, problem.port, "no"
        if problem_service_info["Type"] == "oneshot" else "yes", problem.user,
        problem.user, problem.user, "100"
        if problem_service_info["Type"] == "oneshot" else "UNLIMITED",
        problem_service_info['ExecStart'])

    service_file_path = join(path, "{}".format(problem.user))

    with open(service_file_path, "w") as f:
        f.write(service_content)

    return (service_file_path, None)


def create_instance_user(problem_name, instance_number):
    """
    Generates a random username based on the problem name. The username returned is guaranteed to
    not exist.

    Args:
        problem_name: The name of the problem
        instance_number: The unique number for this instance
    Returns:
        The created username
    """

    converted_name = sanitize_name(problem_name)
    username = get_username(converted_name, instance_number)

    try:
        #Check if the user already exists.
        user = getpwnam(username)
        new = False
    except KeyError:
        create_user(username)
        new = True

    return username, new


def generate_instance_deployment_directory(username):
    """
    Generates the instance deployment directory for the given username
    """

    directory = username
    if deploy_config.obfuscate_problem_directories:
        directory = md5(
            (username + deploy_config.deploy_secret).encode()).hexdigest()

    root_dir = deploy_config.problem_directory_root

    if not isdir(root_dir):
        os.makedirs(root_dir)
        # make the root not world readable
        os.chmod(root_dir, 0o751)

    path = join(root_dir, directory)
    if not isdir(path):
        os.makedirs(path)

    return path


def generate_seed(*args):
    """
    Generates a seed using the list of string arguments
    """

    return md5("".join(args).encode("utf-8")).hexdigest()


def generate_staging_directory(root=STAGING_ROOT,
                               problem_name=None,
                               instance_number=None):
    """
    Creates a random, empty staging directory

    Args:
        root: The parent directory for the new directory. Defaults to join(HACKSPORTS_ROOT, "staging")

        Optional prefixes to help identify the staging directory: problem_name, instance_number

    Returns:
        The path of the generated directory
    """

    if not os.path.isdir(root):
        os.makedirs(root)

    # ensure that the staging files are not world-readable
    os.chmod(root, 0o750)

    def get_new_path():
        prefix = ""
        if problem_name != None:
            prefix += problem_name + "_"
        if instance_number != None:
            prefix += str(instance_number) + "_"

        path = join(root, prefix + str(randint(0, 1e16)))
        if os.path.isdir(path):
            return get_new_path()
        return path

    path = get_new_path()
    os.makedirs(path)
    return path


def template_string(template, **kwargs):
    """
    Templates the given string with the keyword arguments

    Args:
        template: The template string
        **kwards: Variables to use in templating
    """

    temp = Template(template)
    return temp.render(**kwargs)


def template_file(in_file_path, out_file_path, **kwargs):
    """
    Templates the given file with the keyword arguments.

    Args:
        in_file_path: The path to the template
        out_file_path: The path to output the templated file
        **kwargs: Variables to use in templating
    """

    env = Environment(
        loader=FileSystemLoader(os.path.dirname(in_file_path)),
        keep_trailing_newline=True)
    template = env.get_template(os.path.basename(in_file_path))
    output = template.render(**kwargs)

    with open(out_file_path, "w") as f:
        f.write(output)


def template_staging_directory(staging_directory, problem):
    """
    Templates every file in the staging directory recursively other than
    problem.json and challenge.py.

    Args:
        staging_directory: The path of the staging directory
        problem: The problem object
    """

    # prepend the staging directory to all
    dont_template = copy(problem.dont_template) + [
        "problem.json", "challenge.py", "templates", "__pre_templated"
    ]

    dont_template_files = list(filter(isfile, dont_template))
    dont_template_directories = list(filter(isdir, dont_template))
    dont_template_directories = [
        join(staging_directory, directory)
        for directory in dont_template_directories
    ]

    for root, dirnames, filenames in os.walk(staging_directory):
        if any(
                os.path.commonprefix([root, path]) == path
                for path in dont_template_directories):
            logger.debug(
                "....Not templating anything in the directory '{}'".format(
                    root))
            continue
        for filename in filenames:
            if filename in dont_template_files:
                logger.debug(
                    "....Not templating the file '{}'".format(filename))
                continue
            fullpath = join(root, filename)
            try:
                template_file(fullpath, fullpath, **get_attributes(problem))
            except UnicodeDecodeError as e:
                # tried templating binary file
                pass


def deploy_files(staging_directory, instance_directory, file_list, username,
                 problem_class):
    """
    Copies the list of files from the staging directory to the instance directory.
    Will properly set permissions and setgid files based on their type.
    """

    # get uid and gid for default and problem user
    user = getpwnam(username)
    default = getpwnam(deploy_config.default_user)

    for f in file_list:
        # copy the file over, making the directories as needed
        output_path = join(instance_directory, f.path)
        if not os.path.isdir(os.path.dirname(output_path)):
            os.makedirs(os.path.dirname(output_path))

        if not isinstance(f, Directory):
            if isinstance(f, PreTemplatedFile):
                file_source = join(staging_directory, "__pre_templated", f.path)
            else:
                file_source = join(staging_directory, f.path)

            shutil.copy2(file_source, output_path)

        # set the ownership based on the type of file
        if isinstance(f, ProtectedFile) or isinstance(f, ExecutableFile):
            os.chown(output_path, default.pw_uid, user.pw_gid)
        else:
            uid = default.pw_uid if f.user is None else getpwnam(f.user).pw_uid
            gid = default.pw_gid if f.group is None else getgrnam(
                f.group).gr_gid
            os.chown(output_path, uid, gid)

        # set the permissions appropriately
        os.chmod(output_path, f.permissions)

    if issubclass(problem_class, Service):
        os.chown(instance_directory, default.pw_uid, user.pw_gid)
        os.chmod(instance_directory, 0o750)


def install_user_service(service_file, socket_file):
    """
    Installs the service file and socket file into the xinetd
    service directory, sets the service to start on boot, and
    starts the service now.

    Args:
        service_file: The path to the systemd service file to install
        socket_file: The path to the systemd socket file to install
    """

    if service_file is None:
        return
    service_name = os.path.basename(service_file)

    logger.debug("...Installing user service '%s'.", service_name)

    # copy service file
    service_path = os.path.join(XINETD_SERVICE_PATH, service_name)
    shutil.copy2(service_file, service_path)

    execute(["service", "xinetd", "restart"], timeout=60)


def generate_instance(problem_object,
                      problem_directory,
                      instance_number,
                      staging_directory,
                      deployment_directory=None):
    """
    Runs the setup functions of Problem in the correct order

    Args:
        problem_object: The contents of the problem.json
        problem_directory: The directory to the problem
        instance_number: The instance number to be generated
        staging_directory: The temporary directory to store files in
        deployment_directory: The directory that will be deployed to. Defaults to a deterministic, unique
                              directory generated for each problem,instance pair using the configuration options
                              PROBLEM_DIRECTORY_ROOT and OBFUSCATE_PROBLEM_DIRECTORIES

    Returns:
        A dict containing (problem, staging_directory, deployment_directory, files,
                           web_accessible_files, service_file, socket_file)
    """

    logger.debug("Generating instance %d of problem '%s'.", instance_number,
                 problem_object["name"])
    logger.debug("...Using staging directory %s", staging_directory)

    username, new = create_instance_user(problem_object['name'],
                                         instance_number)
    if new:
        logger.debug("...Created problem user '%s'.", username)
    else:
        logger.debug("...Using existing problem user '%s'.", username)

    if deployment_directory is None:
        deployment_directory = generate_instance_deployment_directory(username)
    logger.debug("...Using deployment directory '%s'.", deployment_directory)

    seed = generate_seed(problem_object['name'], deploy_config.deploy_secret,
                         str(instance_number))
    logger.debug("...Generated random seed '%s' for deployment.", seed)

    copy_path = join(staging_directory, PROBLEM_FILES_DIR)
    shutil.copytree(problem_directory, copy_path)

    pretemplated_directory = join(copy_path, "__pre_templated")

    if isdir(pretemplated_directory):
        shutil.rmtree(pretemplated_directory)

    # store cwd to restore later
    cwd = os.getcwd()
    os.chdir(copy_path)

    challenge = load_source("challenge", join(copy_path, "challenge.py"))

    Problem = update_problem_class(challenge.Problem, problem_object, seed,
                                   username, deployment_directory)

    # run methods in proper order
    problem = Problem()

    # reseed and generate flag
    problem.flag = problem.generate_flag(Random(seed))
    problem.flag_sha1 = sha1(problem.flag.encode("utf-8")).hexdigest()
    logger.debug("...Instance %d flag is '%s'.", instance_number, problem.flag)

    logger.debug("...Running problem initialize.")
    problem.initialize()

    shutil.copytree(copy_path, pretemplated_directory)

    web_accessible_files = []

    def url_for(web_accessible_files,
                source_name,
                display=None,
                raw=False,
                pre_templated=False):
        if pre_templated:
            source_path = join(copy_path, "__pre_templated", source_name)
        else:
            source_path = join(copy_path, source_name)

        problem_hash = problem_object["name"] + deploy_config.deploy_secret + str(
            instance_number)
        problem_hash = md5(problem_hash.encode("utf-8")).hexdigest()

        destination_path = join(STATIC_FILE_ROOT, problem_hash, source_name)

        link_template = "<a href='{}'>{}</a>"

        web_accessible_files.append((source_path,
                                     join(deploy_config.web_root,
                                          destination_path)))
        uri_prefix = "//"
        uri = join(uri_prefix, deploy_config.hostname, destination_path)

        if not raw:
            return link_template.format(
                uri, source_name if display is None else display)

        return uri

    problem.url_for = functools.partial(url_for, web_accessible_files)

    logger.debug("...Templating the staging directory")
    template_staging_directory(copy_path, problem)

    if isinstance(problem, Compiled):
        problem.compiler_setup()
    if isinstance(problem, Remote):
        problem.remote_setup()
    if isinstance(problem, FlaskApp):
        problem.flask_setup()
    if isinstance(problem, PHPApp):
        problem.php_setup()
    if isinstance(problem, Service):
        problem.service_setup()

    logger.debug("...Running problem setup.")
    problem.setup()

    os.chdir(cwd)

    all_files = copy(problem.files)

    if isinstance(problem, Compiled):
        all_files.extend(problem.compiled_files)
    if isinstance(problem, Service):
        all_files.extend(problem.service_files)

    if not all([isinstance(f, File) for f in all_files]):
        logger.error("All files must be created using the File class!")
        raise FatalException

    for f in all_files:
        if not isinstance(f, Directory) and not os.path.isfile(
                join(copy_path, f.path)):
            logger.error("File '%s' does not exist on the file system!", f)

    service_file, socket_file = create_service_files(problem, instance_number,
                                                     staging_directory)
    logger.debug("...Created service files '%s','%s'.", service_file,
                 socket_file)

    # template the description
    problem.description = template_string(problem.description,
                                          **get_attributes(problem))
    logger.debug("...Instance description: %s", problem.description)

    return {
        "problem": problem,
        "staging_directory": staging_directory,
        "deployment_directory": deployment_directory,
        "files": all_files,
        "web_accessible_files": web_accessible_files,
        "service_file": service_file,
        "socket_file": socket_file
    }


def deploy_problem(problem_directory,
                   instances=None,
                   test=False,
                   deployment_directory=None,
                   debug=False):
    """
    Deploys the problem specified in problem_directory.

    Args:
        problem_directory: The directory storing the problem
        instances: The list of instances to deploy. Defaults to [0]
        test: Whether the instances are test instances or not. Defaults to False.
        deployment_directory: If not None, the challenge will be deployed here instead of their home directory
    """

    if instances is None:
        instances = [0]
    global current_problem, current_instance

    problem_object = get_problem(problem_directory)

    current_problem = problem_object["name"]

    instance_list = []

    logger.debug("Beginning to deploy problem '%s'.", problem_object["name"])

    for instance_number in instances:
        current_instance = instance_number
        staging_directory = generate_staging_directory(
            problem_name=problem_object["name"],
            instance_number=instance_number)
        if test and deployment_directory is None:
            deployment_directory = join(staging_directory, "deployed")

        instance = generate_instance(
            problem_object,
            problem_directory,
            instance_number,
            staging_directory,
            deployment_directory=deployment_directory)
        instance_list.append((instance_number, instance))

    deployment_json_dir = join(DEPLOYED_ROOT,
                               sanitize_name(problem_object["name"]))
    if not os.path.isdir(deployment_json_dir):
        os.makedirs(deployment_json_dir)

    # ensure that the deployed files are not world-readable
    os.chmod(DEPLOYED_ROOT, 0o750)

    # all instances generated without issue. let's do something with them
    for instance_number, instance in instance_list:
        problem_path = join(instance["staging_directory"], PROBLEM_FILES_DIR)
        problem = instance["problem"]
        deployment_directory = instance["deployment_directory"]

        logger.debug("...Copying problem files %s to deployment directory %s.",
                     instance["files"], deployment_directory)
        deploy_files(problem_path, deployment_directory, instance["files"],
                     problem.user, problem.__class__)

        if test:
            logger.info("Test instance %d information:", instance_number)
            logger.info("...Description: %s", problem.description)
            logger.info("...Deployment Directory: %s", deployment_directory)

            logger.debug("Cleaning up test instance side-effects.")
            logger.debug("...Killing user processes.")
            #This doesn't look great.
            try:
                execute("killall -u {}".format(problem.user))
                sleep(0.1)
            except RunProcessError as e:
                pass

            logger.debug("...Removing test user '%s'.", problem.user)
            execute(["userdel", problem.user])

            deployment_json_dir = instance["staging_directory"]
        else:
            # copy files to the web root
            logger.debug("...Copying web accessible files: %s",
                         instance["web_accessible_files"])
            for source, destination in instance["web_accessible_files"]:
                if not os.path.isdir(os.path.dirname(destination)):
                    os.makedirs(os.path.dirname(destination))
                shutil.copy2(source, destination)

            install_user_service(instance["service_file"],
                                 instance["socket_file"])

            # keep the staging directory if run with debug flag
            # this can still be cleaned up by running "shell_manager clean"
            if not debug:
                shutil.rmtree(instance["staging_directory"])

        unique = problem_object["name"] + problem_object["author"] + str(
            instance_number) + deploy_config.deploy_secret

        deployment_info = {
            "user":
            problem.user,
            "deployment_directory":
            deployment_directory,
            "service":
            None if instance["service_file"] is None else
            os.path.basename(instance["service_file"]),
            "socket":
            None if instance["socket_file"] is None else os.path.basename(
                instance["socket_file"]),
            "server":
            problem.server,
            "description":
            problem.description,
            "flag":
            problem.flag,
            "flag_sha1":
            problem.flag_sha1,
            "instance_number":
            instance_number,
            "should_symlink":
            not isinstance(problem, Service) and len(instance["files"]) > 0,
            "files": [f.to_dict() for f in instance["files"]]
        }

        if isinstance(problem, Service):
            deployment_info["port"] = problem.port
            logger.debug("...Port %d has been allocated.", problem.port)

        instance_info_path = os.path.join(deployment_json_dir,
                                          "{}.json".format(instance_number))
        with open(instance_info_path, "w") as f:
            f.write(
                json.dumps(deployment_info, indent=4, separators=(", ", ": ")))

        logger.debug(
            "The instance deployment information can be found at '%s'.",
            instance_info_path)

    logger.info("Problem instances %s were successfully deployed for '%s'.",
                instances, problem_object["name"])


def deploy_problems(args, config):
    """ Main entrypoint for problem deployment """

    global deploy_config, port_map, inv_port_map
    deploy_config = config

    try:
        user = getpwnam(deploy_config.default_user)
    except KeyError as e:
        logger.info("default_user '%s' does not exist. Creating the user now.",
                    deploy_config.default_user)
        create_user(deploy_config.default_user)

    if args.deployment_directory is not None and (len(args.problem_paths) > 1 or
                                                  args.num_instances > 1):
        logger.error(
            "Cannot specify deployment directory if deploying multiple problems or instances."
        )
        raise FatalException

    if args.secret:
        deploy_config.deploy_secret = args.secret
        logger.warn("Overriding deploy_secret with user supplied secret '%s'.",
                    args.secret)

    problem_names = args.problem_paths

    if args.bundle:
        bundle_problems = []
        for bundle_path in args.problem_paths:
            if os.path.isfile(bundle_path):
                bundle = get_bundle(bundle_path)
                bundle_problems.extend(bundle["problems"])
            else:
                bundle_sources_path = get_bundle_root(
                    bundle_path, absolute=True)
                if os.path.isdir(bundle_sources_path):
                    bundle = get_bundle(bundle_sources_path)
                    bundle_problems.extend(bundle["problems"])
                else:
                    logger.error("Could not find bundle at '%s'.", bundle_path)
                    raise FatalException
        problem_names = bundle_problems

    # before deploying problems, load in port_map and already_deployed instances
    already_deployed = {}
    for path, problem in get_all_problems().items():
        already_deployed[path] = []
        for instance in get_all_problem_instances(path):
            already_deployed[path].append(instance["instance_number"])
            if "port" in instance:
                port_map[instance["port"]] = (problem["name"],
                                              instance["instance_number"])
                inv_port_map[(problem["name"],
                              instance["instance_number"])] = instance["port"]

    lock_file = join(HACKSPORTS_ROOT, "deploy.lock")
    if os.path.isfile(lock_file):
        logger.error(
            "Cannot deploy while other deployment in progress. If you believe this is an error, "
            "run 'shell_manager clean'")
        raise FatalException

    logger.debug("Obtaining deployment lock file %s", lock_file)
    with open(lock_file, "w") as f:
        f.write("1")

    if args.instances:
        instance_list = args.instances
    else:
        instance_list = list(range(0, args.num_instances))

    try:
        for problem_name in problem_names:
            if args.redeploy:
                todo_instance_list = instance_list
            else:
                # remove already deployed instances
                todo_instance_list = list(
                    set(instance_list) -
                    set(already_deployed.get(problem_name, [])))

            if args.dry and isdir(problem_name):
                deploy_problem(
                    problem_name,
                    instances=todo_instance_list,
                    test=args.dry,
                    deployment_directory=args.deployment_directory,
                    debug=args.debug)
            elif isdir(join(get_problem_root(problem_name, absolute=True))):
                deploy_problem(
                    join(get_problem_root(problem_name, absolute=True)),
                    instances=todo_instance_list,
                    test=args.dry,
                    deployment_directory=args.deployment_directory,
                    debug=args.debug)
            else:
                logger.error("Problem '%s' doesn't appear to be installed.",
                             problem_name)
                raise FatalException
    finally:
        logger.debug("Releasing lock file %s", lock_file)
        if not args.dry:
            os.remove(lock_file)


def remove_instances(path, instance_list):
    """ Remove all files under deployment directory and metdata for a given list of instances """

    problem_instances = get_all_problem_instances(path)
    deployment_json_dir = join(DEPLOYED_ROOT, path)

    for instance in problem_instances:
        instance_number = instance["instance_number"]
        if instance["instance_number"] in instance_list:
            logger.debug("Removing instance {} of '{}'.".format(
                instance_number, path))

            directory = instance["deployment_directory"]
            user = instance["user"]
            service = instance["service"]
            socket = instance["socket"]
            deployment_json_path = join(deployment_json_dir,
                                        "{}.json".format(instance_number))

            logger.debug("...Removing xinetd service '%s'.", service)
            os.remove(join(XINETD_SERVICE_PATH, service))
            execute(["service", "xinetd", "restart"], timeout=60)

            logger.debug("...Removing deployment directory '%s'.", directory)
            shutil.rmtree(directory)
            os.remove(deployment_json_path)

            logger.debug("...Removing problem user '%s'.", user)
            execute(["userdel", user])


def undeploy_problems(args, config):
    """ Main entrypoint for problem undeployment """

    problem_names = args.problem_paths

    if args.bundle:
        bundle_problems = []
        for bundle_path in args.problem_paths:
            if isfile(bundle_path):
                bundle = get_bundle(bundle_path)
                bundle_problems.extend(bundle["problems"])
            else:
                bundle_sources_path = get_bundle_root(
                    bundle_path, absolute=True)
                if isdir(bundle_sources_path):
                    bundle = get_bundle(bundle_sources_path)
                    bundle_problems.extend(bundle["problems"])
                else:
                    logger.error("Could not find bundle at '%s'.", bundle_path)
                    raise FatalException
        problem_names = bundle_problems

    # before deploying problems, load in already_deployed instances
    already_deployed = {}
    for path, problem in get_all_problems().items():
        already_deployed[problem["name"]] = []
        for instance in get_all_problem_instances(path):
            already_deployed[problem["name"]].append(
                instance["instance_number"])

    lock_file = join(HACKSPORTS_ROOT, "deploy.lock")
    if os.path.isfile(lock_file):
        logger.error(
            "Cannot undeploy while other deployment in progress. If you believe this is an error, "
            "run 'shell_manager clean'")
        raise FatalException

    logger.debug("Obtaining deployment lock file %s", lock_file)
    with open(lock_file, "w") as f:
        f.write("1")

    if args.instances:
        instance_list = args.instances
    else:
        instance_list = list(range(0, args.num_instances))

    try:
        for problem_name in problem_names:
            problem_root = get_problem_root(problem_name, absolute=True)
            if isdir(problem_root):
                problem = get_problem(problem_root)
                instances = list(
                    filter(lambda x: x in already_deployed[problem["name"]],
                           instance_list))
                if len(instances) == 0:
                    logger.warn(
                        "No deployed instances %s were found for problem '%s'.",
                        instance_list, problem["name"])
                else:
                    logger.debug("Undeploying problem '%s'.", problem["name"])
                    remove_instances(problem_name, instance_list)
                    logger.info(
                        "Problem instances %s were successfully removed from '%s'.",
                        instances, problem["name"])
            else:
                logger.error("Problem '%s' doesn't appear to be installed.",
                             problem_name)
                raise FatalException
    finally:
        logger.debug("Releasing lock file %s", lock_file)
        os.remove(lock_file)
