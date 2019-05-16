"""
Common set of functionality for API testing.
Fixtures defined within this file are available to all
other testing modules.
"""

import api.common
import api.config
import pytest
from pymongo import MongoClient

TEST_MONGO_ADDR = '127.0.0.1'
TEST_MONGO_PORT = 27017
TEST_MONGO_DB_NAME = 'ctf-test'


def setup_db():
    """ Creates a mongodb instance and shuts it down after testing has concluded. """

    client = MongoClient(TEST_MONGO_ADDR, TEST_MONGO_PORT)[TEST_MONGO_DB_NAME]

    if len(client.collection_names()) != 0:
        client.connection.drop_database(TEST_MONGO_DB_NAME)

    # Set debug client for mongo
    if api.common.external_client is None:
        api.common.external_client = client

    return client


def teardown_db():
    """ Drops the db and shuts down the mongodb instance. """
    client = MongoClient(TEST_MONGO_ADDR, TEST_MONGO_PORT)[TEST_MONGO_DB_NAME]
    client.connection.drop_database(TEST_MONGO_DB_NAME)
    client.connection.disconnect()
