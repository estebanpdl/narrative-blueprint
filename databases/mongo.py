# -*- coding: utf-8 -*-

# import base class
from .database import Database

# MongoDB dependencies
from pymongo import MongoClient
from pymongo.collection import Collection

# MongoDBManager class
class MongoDBManager(Database):
    '''
    MongoDBManager class to manage MongoDB connections and operations.
    '''
    def __init__(self, db_name: str, collection_name: str):
        '''
        Initializes the MongoDBManager instance.

        :param db_name: The name of the MongoDB database.
        :type db_name: str

        :param collection_name: The name of the MongoDB collection.
        :type collection_name: str
        '''
        connection_string = 'mongodb://localhost:27017/'
        self.client = MongoClient(connection_string)
        self.db_name = db_name
        self.collection_name = collection_name

        # access to db collection
        db = self.client[self.db_name]
        self.collection = db[self.collection_name]

    def test_access(self) -> bool:
        '''
        Tests access to the specified database and collection.

        :return: True if access is successful, False otherwise
        :rtype: bool
        '''
        db = self.client[self.db_name]

        # list all collections
        collections = db.list_collection_names()
        if self.collection_name in collections:
            return True
        else:
            return False

    def get_collected_uuids(self) -> list:
        '''
        Retrieves all UUIDs from the MongoDB collection.

        :return: A list of UUIDs.
        :rtype: list
        '''
        uuids = [
            doc['uuid'] for doc in self.collection.find(
                {}, {'uuid': 1, '_id': 0}
            )
        ]

        return uuids

    def insert_one(self, document: dict) -> None:
        '''
        Inserts a single document into the MongoDB collection.

        :param document: The document to be inserted.
        :type document: dict
        '''
        self.collection.insert_one(document)

    def get_collection(self) -> Collection:
        '''
        Retrieves the collection object.

        :return: The collection object.
        :rtype: pymongo.collection.Collection
        '''
        return self.collection

    def insert_many(self, data: list) -> None:
        '''
        Inserts a list of data into the MongoDB collection.

        :param data: The data to be inserted.
        :type data: list
        '''
        self.collection.insert_many(data)

    def get_documents(self) -> list:
        '''
        Retrieves all documents from the MongoDB collection.

        :return: A list of documents.
        :rtype: list
        '''
        return [doc for doc in self.collection.find({})]
