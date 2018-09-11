""" The common module contains general-purpose functions potentially used by multiple modules in the system."""
import uuid
from hashlib import md5

import api
import bcrypt
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, InvalidName
from voluptuous import Invalid, MultipleInvalid
from werkzeug.contrib.cache import SimpleCache

cache = SimpleCache()

__connection = None
__client = None


def get_conn():
    """
    Get a database connection

    Ensures that only one global database connection exists per thread.
    If the connection does not exist a new one is created and returned.
    """

    global __client, __connection
    if not __connection:
        try:
            # Allow more complex mongodb connections
            conf = api.app.app.config
            if conf["MONGO_USER"] and conf["MONGO_PW"]:
                uri = "mongodb://{}:{}@{}:{}/{}?authMechanism=SCRAM-SHA-1".format(
                    conf["MONGO_USER"], conf["MONGO_PW"], conf["MONGO_ADDR"],
                    conf["MONGO_PORT"], conf["MONGO_DB_NAME"])
            else:
                uri = "mongodb://{}:{}/{}".format(conf["MONGO_ADDR"],
                                                  conf["MONGO_PORT"],
                                                  conf["MONGO_DB_NAME"])

            __client = MongoClient(uri)
            __connection = __client[conf["MONGO_DB_NAME"]]
        except ConnectionFailure:
            raise SevereInternalException(
                "Could not connect to mongo database {} at {}:{}".format(
                    mongo_db_name, mongo_addr, mongo_port))
        except InvalidName as error:
            raise SevereInternalException("Database {} is invalid! - {}".format(
                mongo_db_name, error))

    return __connection


def token():
    """
    Generate a token, should be random but does not have to be secure necessarily. Speed is a priority.

    Returns:
        The randomly generated token
    """

    return str(uuid.uuid4().hex)


def hash(string):
    """
    Hashes a string

    Args:
        string: string to be hashed.
    Returns:
        The hex digest of the string.
    """

    return md5(string.encode("utf-8")).hexdigest()


class APIException(Exception):
    """
    Exception thrown by the API.
    """
    data = {}


def WebSuccess(message=None, data=None):
    """
    Successful web request wrapper.
    """

    return {"status": 1, "message": message, "data": data}


def WebError(message=None, data=None):
    """
    Unsuccessful web request wrapper.
    """

    return {"status": 0, "message": message, "data": data}


class WebException(APIException):
    """
    Errors that are thrown that need to be displayed to the end user.
    """

    pass


class InternalException(APIException):
    """
    Exceptions thrown by the API constituting mild errors.
    """

    pass


class SevereInternalException(InternalException):
    """
    Exceptions thrown by the API constituting critical errors.
    """

    pass


def flat_multi(multidict):
    """
    Flattens any single element lists in a multidict.

    Args:
        multidict: multidict to be flattened.
    Returns:
        Partially flattened database.
    """

    flat = {}
    for key, values in multidict.items():
        flat[key] = values[0] if type(values) == list and len(values) == 1 \
                    else values
    return flat


def check(*callback_tuples):
    """
    Voluptuous wrapper function to raise our APIException

    Args:
        callback_tuples: a callback_tuple should contain (status, msg, callbacks)
    Returns:
        Returns a function callback for the Schema
    """

    def v(value):
        """
        Tries to validate the value with the given callbacks.

        Args:
            value: the item to validate
        Raises:
            APIException with the given error code and msg.
        Returns:
            The value if the validation callbacks are satisfied.
        """

        for msg, callbacks in callback_tuples:
            for callback in callbacks:
                try:
                    result = callback(value)
                    if not result and type(result) == bool:
                        raise Invalid()
                except Exception:
                    raise WebException(msg)
        return value

    return v


def validate(schema, data):
    """
    A wrapper around the call to voluptuous schema to raise the proper exception.

    Args:
        schema: The voluptuous Schema object
        data: The validation data for the schema object

    Raises:
        APIException with status 0 and the voluptuous error message
    """

    try:
        schema(data)
    except MultipleInvalid as error:
        raise APIException(0, None, error.msg)


def safe_fail(f, *args, **kwargs):
    """
    Safely calls a function that can raise an APIException.

    Args:
        f: function to call
        *args: positional arguments
        **kwargs: keyword arguments
    Returns:
        The function result or None if an exception was raised.
    """

    try:
        return f(*args, **kwargs)
    except APIException:
        return None


def hash_password(password):
    """
    Hash plaintext password.

    Args:
        password: plaintext password
    Returns:
        Secure hash of password.
    """

    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(8))
