# -*- coding: utf-8 -*-

# import modules
import os
import json
import threading

# import base class
from .database import Database

# JSONFileManager class
class JSONFileManager(Database):
    '''
    JSONFileManager class to store results in a JSON file.
    '''
    def __init__(self, output_path: str):
        '''
        Initializes the JSONFileManager instance.

        :param output_path: Path to the output JSON file.
        :type output_path: str
        '''
        self.output_path = output_path
        self._lock = threading.Lock()
        self._results = []

        # load existing results if file exists
        if os.path.exists(self.output_path):
            with open(self.output_path, 'r', encoding='utf-8') as f:
                self._results = json.load(f)

    def insert_one(self, document: dict) -> None:
        '''
        Append a document to the in-memory list and write to file.

        :param document: The document to store.
        :type document: dict
        '''
        with self._lock:
            self._results.append(document)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(self._results, f, indent=2, ensure_ascii=False)

    def get_collected_uuids(self) -> list:
        '''
        Return UUIDs already present in the output file.

        :return: A list of UUIDs.
        :rtype: list
        '''
        return [doc['uuid'] for doc in self._results if 'uuid' in doc]

    def test_access(self) -> bool:
        '''
        Verify the output directory exists and is writable.

        :return: True if access is successful.
        :rtype: bool
        '''
        output_dir = os.path.dirname(self.output_path)
        if not output_dir:
            # relative path in current directory
            output_dir = '.'
        return os.path.isdir(output_dir) and os.access(output_dir, os.W_OK)
