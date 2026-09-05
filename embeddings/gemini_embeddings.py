# -*- coding: utf-8 -*-

# import modules
import os
import time

# progress bar
from tqdm import tqdm

# dotenv for environment variables
from dotenv import load_dotenv

# import base class
from .base import VectorModel
from databases.database import Database

# Gemini related modules
from google import genai
from google.genai import types

# Embedding Model class
class GeminiEmbeddingModel(VectorModel):
    '''
    GeminiEmbeddingModel class
    '''
    # Gemini model limits
    MODEL_LIMITS = {
        'gemini-embedding-001': {
            'rpm': 3000,
            'tpm': 1000000
        }
    }

    # max tokens per request
    MAX_TOKENS_PER_REQUEST = 2000

    # max number of documents to process in one batch
    DOCS_PER_BATCH = 100

    def __init__(self, model_name: str,
                 task_type: str = 'SEMANTIC_SIMILARITY'):
        super().__init__()

        # load environment variables
        env_file_path = './config/.env'
        load_dotenv(env_file_path)

        # read API key
        api_key = os.getenv('GEMINI_API_KEY')

        # initialize Gemini client
        self.client = genai.Client(api_key=api_key)

        # Gemini model
        self.model_name = model_name
        self.task_type = task_type

        # get model limits
        self.max_requests_per_min = self.MODEL_LIMITS[self.model_name]['rpm']
        self.max_tokens_per_min = self.MODEL_LIMITS[self.model_name]['tpm']

    def estimate_tokens(self, text: str) -> int:
        '''
        Estimate the number of tokens in data.

        :param text: The text to be estimated.
        :type text: str

        :return: The estimated number of tokens.
        :rtype: int
        '''
        return len(text) // 4

    def _safe_embed_request(self,
                            uuids: list = None,
                            batch_data: list[str] = None,
                            request_id: int = None,
                            retry_max: int = 3) -> None:
        '''
        Safe embedding request.

        :param uuids: The uuids of the documents to be embedded.
        :type uuids: list

        :param batch_data: The batch of text to be embedded.
        :type batch_data: list[str]

        :param request_id: The request ID.
        :type request_id: int

        :param retry_max: The maximum number of retries.
        :type retry_max: int
        '''
        retry_count = 0
        while retry_count < retry_max:
            try:
                response = self.client.models.embed_content(
                    model=f'models/{self.model_name}',
                    contents=batch_data,
                    config=types.EmbedContentConfig(
                        task_type=self.task_type
                    )
                )

                # build data object
                data = [
                    {
                        'uuid': uuids[i],
                        'text': batch_data[i],
                        'embedding': response.embeddings[i].values,
                        'model_name': self.model_name,
                        'provider': 'Google',
                        'task_type': self.task_type
                    }
                    for i in range(len(uuids))
                ]

                self._store_embeddings(data)

                return
            except Exception as e:
                self._log_write(f'Failed to compute embeddings for request {request_id}')
                self._log_write(str(e))
                self._log_write('')

                # retry
                retry_count += 1
                wait_time = 60
                time.sleep(wait_time)

        # exceeded max retries
        if retry_count >= retry_max:
            self._log_write(f'Failed to compute embeddings for request {request_id}. Cancelled!')
            return

    def _process_batch(self,
                       uuids: list = None,
                       batch_data: list[str] = None,
                       rpm_start_time=None,
                       tpm_start_time=None,
                       request_count=0,
                       pbar=None,
                       start_request_id=1,
                       global_token_count: int = 0) -> tuple[float, float, int, int, int]:
        '''
        Process a batch of documents.

        :param uuids: The uuids of the documents to be embedded.
        :type uuids: list

        :param batch_data: The batch of documents to be processed.
        :type batch_data: list[str]

        :param rpm_start_time: The start time of the RPM.
        :type rpm_start_time: float

        :param tpm_start_time: The start time of the TPM.
        :type tpm_start_time: float

        :param request_count: The number of requests.
        :type request_count: int

        :param pbar: The progress bar.
        :type pbar: tqdm

        :param start_request_id: The starting request ID.
        :type start_request_id: int

        :param global_token_count: The global token count.
        :type global_token_count: int

        :return: Tuple of (rpm_start_time, tpm_start_time,
            request_count, next_request_id, global_token_count)
        :rtype: tuple[float, float, int, int, int]
        '''
        current_batch = []
        current_uuids = []

        # token count
        token_count = 0

        # request ID
        request_id = start_request_id

        # process batch data
        for idx, text in enumerate(batch_data):
            text_tokens = self.estimate_tokens(text)

            # flush when current request payload is full
            if token_count + text_tokens > self.MAX_TOKENS_PER_REQUEST:
                # compute embeddings
                self._safe_embed_request(
                    uuids=current_uuids,
                    batch_data=current_batch,
                    request_id=request_id
                )

                # update progress bar
                pbar.update(len(current_batch))

                # increment request count
                request_count += 1
                request_id += 1
                current_batch = []
                current_uuids = []
                token_count = 0

                # check RPM limits
                elapsed_rpm = time.time() - rpm_start_time
                if request_count >= self.max_requests_per_min:
                    if elapsed_rpm < 60:
                        pbar.set_description(f'RPM limit pause: {int(60 - elapsed_rpm)}s')
                        time.sleep(60 - elapsed_rpm)
                        pbar.set_description('Computing embeddings')
                    rpm_start_time = time.time()
                    request_count = 0

                # check TPM limits (windowed by global_token_count)
                elapsed_tpm = time.time() - tpm_start_time
                if global_token_count >= self.max_tokens_per_min:
                    if elapsed_tpm < 60:
                        pbar.set_description(f'TPM limit pause: {int(60 - elapsed_tpm)}s')
                        time.sleep(60 - elapsed_tpm)
                        pbar.set_description('Computing embeddings')
                    tpm_start_time = time.time()
                    global_token_count = 0
                elif elapsed_tpm >= 60:
                    # reset window if minute has passed
                    tpm_start_time = time.time()
                    global_token_count = 0

            # add text and uuid to batch
            current_batch.append(text)
            current_uuids.append(uuids[idx])
            token_count += text_tokens
            global_token_count += text_tokens

            # tokens and requests being processed
            pbar.set_postfix(
                {
                    'requests': request_count,
                    'tokens/batch': token_count,
                    'tokens/total': global_token_count
                }
            )

        # compute embeddings for current batch
        if current_batch:
            self._safe_embed_request(
                uuids=current_uuids,
                batch_data=current_batch,
                request_id=request_id
            )

            # update progress bar
            pbar.update(len(current_batch))

            # increment request count
            request_count += 1
            request_id += 1

        return rpm_start_time, tpm_start_time, \
            request_count, request_id, global_token_count

    def compute_embeddings(self,
                           uuids: list = None,
                           data: list[str] = None,
                           storage: Database = None) -> None:
        '''
        Compute the embeddings for the data.

        :param uuids: The uuids of the documents to be embedded.
        :type uuids: list

        :param data: The data to be computed.
        :type data: list[str]

        :param storage: Storage backend for embedding documents.
        :type storage: Database
        '''
        if not isinstance(storage, Database):
            raise TypeError('storage must be an instance of Database')
        self.storage = storage

        # initialize rate limiting trackers
        rpm_start_time = time.time()
        tpm_start_time = time.time()
        request_count = 0
        next_request_id = 1
        global_token_count = 0

        # create single progress bar for all batches
        with tqdm(total=len(data), desc="Computing embeddings", unit="text") as pbar:
            # process data in batches
            for batch_start in range(0, len(data), self.DOCS_PER_BATCH):
                batch_end = min(batch_start + self.DOCS_PER_BATCH, len(data))
                batch_data = data[batch_start:batch_end]

                # uuids
                batch_uuids = uuids[batch_start:batch_end]

                # process batch
                result = self._process_batch(
                    uuids=batch_uuids,
                    batch_data=batch_data,
                    rpm_start_time=rpm_start_time,
                    tpm_start_time=tpm_start_time,
                    request_count=request_count,
                    pbar=pbar,
                    start_request_id=next_request_id,
                    global_token_count=global_token_count
                )

                rpm_start_time, tpm_start_time, \
                    request_count, next_request_id, global_token_count = result

        return
