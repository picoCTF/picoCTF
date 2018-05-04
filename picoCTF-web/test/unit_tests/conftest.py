"""
Common set of functionality for API testing.
Fixtures defined within this file are available to all
other testing modules.
"""

import api.common
import api.config
import pytest
from pymongo import MongoClient


def setup_db():
    """ Creates a mongodb instance and shuts it down after testing has concluded. """

    client = MongoClient(
        api.config.testing_mongo_addr,
        api.config.testing_mongo_port)[api.config.testing_mongo_db_name]

    if len(client.collection_names()) != 0:
        client.connection.drop_database(api.config.testing_mongo_db_name)

    #Set debug client for mongo
    if api.common.external_client is None:
        api.common.external_client = client

    return client


def teardown_db():
    """ Drops the db and shuts down the mongodb instance. """
    client = MongoClient(
        api.config.testing_mongo_addr,
        api.config.testing_mongo_port)[api.config.testing_mongo_db_name]
    client.connection.drop_database(api.config.testing_mongo_db_name)
    client.connection.disconnect()
