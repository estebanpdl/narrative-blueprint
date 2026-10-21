# -*- coding: utf-8 -*-

'''
Defines VectorModel base class

'''

# import modules
import os

from narrative_blueprint.databases.database import Database

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
        self.storage = None

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

    def _store_embeddings(self, data: list[dict]) -> None:
        '''
        Store computed embedding documents.
        '''
        if self.storage is None:
            raise RuntimeError('Embedding storage has not been configured')
        self.storage.insert_many(data)

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
                           storage: Database) -> None:
        '''
        Compute embeddings for a list of strings.
        '''
        pass
