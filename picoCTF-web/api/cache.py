"""
Caching Library
"""

import time
from functools import wraps

import api
from bson import datetime, json_util

log = api.logger.use(__name__)

no_cache = False
fast_cache = {}
_mongo_index = None


def clear_all():
    """
    Clears the cache.
    """

    db = api.common.get_conn()
    db.cache.remove()
    fast_cache.clear()


def get_mongo_key(f, *args, **kwargs):
    """
    Returns a mongo object key for the function.

    Args:
        f: the function
        args: positional arguments
        kwargs: keyword arguments
    Returns:
        The key.
    """

    min_kwargs = list(filter(lambda pair: pair[1] is not None, kwargs.items()))

    return {
        "function": "{}.{}".format(f.__module__, f.__name__),
        "args": args,
        "ordered_kwargs": sorted(min_kwargs),
        "kwargs": dict(min_kwargs)
    }


def get_key(f, *args, **kwargs):
    """
    Returns a unique key for a memoized function.

    Args:
        f: the function
        args: positional arguments
        kwargs: keyword arguments
    Returns:
        The key.
    """

    if len(args) > 0:
        kwargs["#args"] = ",".join(map(str, args))

    sorted_keys = sorted(kwargs)
    arg_key = "&".join(
        ["{}:{}".format(key, kwargs[key]) for key in sorted_keys])

    key = "{}.{}${}".format(f.__module__, f.__name__, arg_key).replace(" ", "~")

    return key


def get(key, fast=False):
    """
    Get a key from the cache.

    Args:
        key: cache key
        fast: whether or not to use the fast cache
    Returns:
        The result from the cache.
    """

    if fast:
        return fast_cache.get(key, None)

    db = api.common.get_conn()

    # We aren't interested in matching the unordered kwargs.
    partial_key = key.copy()
    partial_key.pop("kwargs", None)

    cached_result = db.cache.find_one(partial_key)

    if cached_result:
        return cached_result["value"]


def set(key, value, timeout=None, fast=False):
    """
    Set a key in the cache.

    Args:
        key: The cache key.
        timeout: Time the key is valid.
        fast: whether or not to use the fast cache
    """

    if fast:
        fast_cache[key] = {
            "result": value,
            "timeout": timeout,
            "set_time": time.time()
        }
        return

    db = api.common.get_conn()

    update = key.copy()
    update.update({"value": value})

    if timeout is not None:
        expireAt = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
        update.update({"expireAt": expireAt})

    db.cache.update(key, update, upsert=True)


def timed_out(info):
    """
    Determines if a fast_cache entry has been timed out
    """

    return int(time.time()) - info['set_time'] > info['timeout']


def memoize(timeout=None, fast=False):
    """
    Cache a function based on its arguments.

    Args:
        timout: Time the result stays valid in the cache.
    Returns:
        The functions result.
    """

    assert (not fast or (fast and timeout is not None)
           ), "You cannot set fast cache without a timeout!"

    def decorator(f):
        """
        Inner decorator
        """

        @wraps(f)
        def wrapper(*args, **kwargs):
            """
            Function cache
            """

            if not kwargs.get("cache", True):
                kwargs.pop("cache", None)
                return f(*args, **kwargs)

            key = get_key(f, *args, **kwargs) if fast else get_mongo_key(
                f, *args, **kwargs)
            cached_result = get(key, fast=fast)

            if cached_result is None or no_cache or (fast and
                                                     timed_out(cached_result)):
                function_result = f(*args, **kwargs)
                set(key, function_result, timeout=timeout, fast=fast)

                return function_result

            return cached_result['result'] if fast else cached_result

        return wrapper

    return decorator


def invalidate_memoization(f, *keys):
    """
    Invalidate a memoized function.

    Args:
        f: the function
        You must pass all arguments given to the function to accurately invalidate it.
    """

    db = api.common.get_conn()

    search = {"function": "{}.{}".format(f.__module__, f.__name__)}
    search.update({"$or": list(keys)})

    db.cache.remove(search)
