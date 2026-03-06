# -*- coding: utf-8 -*-

'''
Defines VectorModel base class

'''

# import modules
import os

# import abstract base class
from abc import ABC, abstractmethod

# VectorModel abstract base class
class VectorModel(ABC):
    '''
    VectorModel abstract base class
    '''
    def __init__(self):
        '''
        Initialize VectorModel abstract base class
        '''
        self.log_file = './logs/vector_model_log.txt'

    def _log_write(self, message: str) -> None:
        '''
        Write a message to the log file.
        '''
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(message + '\n')

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        '''
        Estimate the number of tokens in data.
        '''
        pass

    @abstractmethod
    def _insert_into_mongodb(self, data: list[dict]) -> None:
        '''
        Insert data into MongoDB.
        '''
        pass

    @abstractmethod
    def _safe_embed_request(self, uuids: list,
                            batch_data: list[str],
                            request_id: int,
                            retry_max: int = 3) -> None:
        '''
        Safe embedding request.
        '''
        pass

    @abstractmethod
    def compute_embeddings(self,
                           uuids: list,
                           data: list[str],
                           mongo_db_name: str,
                           mongo_collection_name: str) -> None:
        '''
        Compute embeddings for a list of strings.
        '''
        pass
