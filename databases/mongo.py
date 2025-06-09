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
    def __init__(self):
        '''
        Initializes the MongoDBManager instance.
        '''
        connection_string = 'mongodb://localhost:27017/'
        self.client = MongoClient(connection_string)

    def test_access_to_db_and_collection(self,
                                         db_name: str,
                                         collection_name: str) -> bool:
        '''
        Tests access to the specified database and collection.

        :param db_name: The name of the MongoDB database.
        :type db_name: str

        :param collection_name: The name of the MongoDB collection.
        :type collection_name: str

        :return: True if access is successful, False otherwise
        :rtype: bool
        '''
        db = self.client[db_name]

        # list all collections
        collections = db.list_collection_names()
        if collection_name in collections:
            return True
        else:
            return False

    def get_collection(self, db_name: str, collection_name: str) -> Collection:
        '''
        Retrieves a collection from the MongoDB database.

        :param db_name: The name of the MongoDB database.
        :type db_name: str

        :param collection_name: The name of the MongoDB collection.
        :type collection_name: str

        :return: The collection object.
        :rtype: pymongo.collection.Collection
        '''
        db = self.client[db_name]

        # access to db collection
        collection = db[collection_name]
        return collection
    
    def get_collected_uuids(self,
                            db_name: str,
                            collection_name: str) -> list:
        '''
        Retrieves all UUIDs from the MongoDB collection.

        :param db_name: The name of the MongoDB database.
        :type db_name: str

        :param collection_name: The name of the MongoDB collection.
        :type collection_name: str

        :return: A list of UUIDs.
        :rtype: list
        '''
        db = self.client[db_name]
        collection = db[collection_name]
        uuids = [
            doc['uuid'] for doc in collection.find(
                {}, {'uuid': 1, '_id': 0}
            )
        ]
        
        return uuids

    def insert_many(self,
                    data: list,
                    db_name: str,
                    collection_name: str) -> None:
        '''
        Inserts a list of data into the MongoDB collection.

        :param data: The data to be inserted.
        :type data: list

        :param db_name: The name of the MongoDB database.
        :type db_name: str

        :param collection_name: The name of the MongoDB collection.
        :type collection_name: str
        '''
        db = self.client[db_name]
        collection = db[collection_name]
        collection.insert_many(data)
    
    def get_documents(self,
                      db_name: str,
                      collection_name: str) -> list:
        '''
        Retrieves all documents from the MongoDB collection.

        :param db_name: The name of the MongoDB database.
        :type db_name: str

        :param collection_name: The name of the MongoDB collection.
        :type collection_name: str

        :return: A list of documents.
        :rtype: list
        '''
        db = self.client[db_name]
        collection = db[collection_name]
        return [doc for doc in collection.find({})]
    
    def upload_test_case(self,
                         test_case: dict,
                         db_name: str,
                         collection_name: str) -> None:
        '''
        Uploads a test case to the MongoDB collection.

        :param test_case: The test case to be uploaded.
        :type test_case: dict

        :param db_name: The name of the MongoDB database.
        :type db_name: str

        :param collection_name: The name of the MongoDB collection.
        :type collection_name: str
        '''
        db = self.client[db_name]
        collection = db[collection_name]
        collection.insert_one(test_case)
