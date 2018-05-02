""" Module for token functionality. """

import api
from api.common import InternalException


def get_token_path(token_name):
    """
    Formats the token name into a token path.

    Returns:
      The token path
    """

    return "tokens.{}".format(token_name)


def set_token(key, token_name, token_value=None):
    """
    Sets a token for the user.

    Args:
        key: the unique identifier object
        token_name: the name of the token to set
        token_value: optionally specify the value of the token
    Returns:
        The token value
    """

    db = api.common.get_conn()

    # Should never realistically collide.
    if token_value is None:
        token_value = api.common.hash(str(key) + api.common.token())

    db.tokens.update(
        key, {'$set': {
            get_token_path(token_name): token_value
        }}, upsert=True)

    return token_value


def delete_token(key, token_name):
    """
    Removes the password reset token for the user in mongo

    Args:
        key: the unique identifier object
        token_name: the name of the token
    """

    db = api.common.get_conn()

    db.tokens.update(key, {'$unset': {get_token_path(token_name): ''}})


def find_key(query, multi=False):
    """
    Find a key based on a particular query.

    Args:
        query: the mongo query
        multi: defaults to False, return at most one result
    """

    db = api.common.get_conn()

    find_func = db.tokens.find_one
    if multi:
        find_func = db.tokens.find

    return find_func(query)


def find_key_by_token(token_name, token_value):
    """
    Searches the database for a user with a token_name token_value pair.

    Args:
        token_name: the name of the token
        token_value: the value of the token
    """

    db = api.common.get_conn()

    key = db.tokens.find_one({
        get_token_path(token_name): token_value
    }, {
        "_id": 0,
        "tokens": 0
    })

    if key is None:
        raise InternalException("Could not find {}.".format(token_name))

    return key
