# -*- coding: utf-8 -*-

'''
Defines the abstract base class

'''

# import modules
from abc import ABC, abstractmethod

# Database abstract base class
class Database(ABC):
    '''
    Database abstract base class
    '''

    @abstractmethod
    def insert_one(self, document: dict) -> None:
        '''
        Store a single result document.

        :param document: The document to store.
        :type document: dict
        '''
        pass

    @abstractmethod
    def insert_many(self, data: list) -> None:
        '''
        Store multiple documents.

        :param data: The documents to store.
        :type data: list
        '''
        pass

    @abstractmethod
    def get_collected_uuids(self) -> list:
        '''
        Return list of already-processed UUIDs.

        :return: A list of UUIDs.
        :rtype: list
        '''
        pass

    @abstractmethod
    def get_documents(self) -> list:
        '''
        Retrieve all documents.

        :return: A list of documents.
        :rtype: list
        '''
        pass

    @abstractmethod
    def test_access(self) -> bool:
        '''
        Verify the backend is usable.

        :return: True if access is successful.
        :rtype: bool
        '''
        pass

    def finalize(self) -> None:
        '''Finalize pending writes for backends that require it.'''
        return
