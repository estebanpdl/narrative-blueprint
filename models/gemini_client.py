# -*- coding: utf-8 -*-

# import modules
import os
import json
import time
import signal
import random
import traceback

# dotenv for environment variables
from dotenv import load_dotenv

# multithreading
from concurrent.futures import ThreadPoolExecutor, wait

# tqdm bar
from tqdm import tqdm

# import base class
from .model import LanguageModel

# Google AI SDK
from google import genai
from google.genai import types
from google.genai.errors import ClientError

# MongoDB connection
from databases import MongoDBManager

# Gemini class
class GeminiModels(LanguageModel):
    '''
    GeminiModels class for interacting with Google's Gemini API.

    This class provides methods to generate responses using the specified
    Gemini model, manage token usage, and log responses to a MongoDB database.

    Public Methods:
    - get_log_file: Returns the path to the log file.
    - _estimate_tokens: Estimates the number of tokens in a given prompt.
    - _process_response: Processes the API response and logs it to MongoDB.
    - _call_with_backoff: Calls the Gemini API with a backoff strategy.
    - run_parallel_prompt_tasks: Executes multiple prompt tasks in parallel.

    Instance Variables:
    - client: Gemini client instance.
    - model_name: Name of the Gemini model.
    - log_file: Path to the log file.
    - mongodb_manager: MongoDB connection manager.
    '''
    def __init__(self, model_name: str):
        '''
        '''
        super().__init__(provider='google', model_name=model_name)

        # load environment variables
        env_file_path = './config/.env'
        load_dotenv(env_file_path)

        # Gemini client
        self.client = genai.Client(
            api_key=os.getenv('GEMINI_API_KEY')
        )

        # Gemini model
        self.model_name = model_name

        # log file
        self.log_file = './logs/gemini_client.log'

        # MongoDB connection
        self.mongodb_manager = MongoDBManager()

    def get_log_file(self) -> str:
        '''
        Get the log file path.

        :return: The path to the log file.
        :rtype: str
        '''
        return self.log_file
    
    def _estimate_tokens(self, system_prompt: str, user_prompt: str) -> int:
        '''
        '''
        res = self.client.models.count_tokens(
            model=self.model_name,
            contents=[
                system_prompt,
                user_prompt
            ]
        )

        return res.total_tokens

    def _process_response(self,
                          uuid: str,
                          response: types.GenerateContentResponse,
                          mongo_db_name: str,
                          mongo_collection_name: str) -> None:
        '''
        Process the API response and log it to MongoDB.

        :param uuid: The UUID of the narrative being processed.
        :type uuid: str

        :param response: The response from the Gemini API.
        :type response: types.GenerateContentResponse

        :param mongo_db_name: Name of the MongoDB database.
        :type mongo_db_name: str

        :param mongo_collection_name: Name of the MongoDB collection.
        :type mongo_collection_name: str

        :raises Exception: If there is an error during processing or logging.
        :return: None
        '''
        # get tokens used
        prompt_tokens_used = response.usage_metadata.prompt_token_count
        completion_tokens_used = response.usage_metadata.candidates_token_count

        # update token usage log
        self.token_usage_log.append(
            (
                time.time(),
                prompt_tokens_used,
                completion_tokens_used
            )
        )

        # get response
        response_content = response.text

        # parse response
        response_content = json.loads(response_content)

        # add uuid to response
        response_content['uuid'] = uuid

        # get collection
        collection = self.mongodb_manager.get_collection(
            db_name=mongo_db_name,
            collection_name=mongo_collection_name   
        )

        # upload response to database
        collection.insert_one(
            response_content
        )
    
    def _call_with_backoff(self,
                           request_id: int,
                           uuid: str,
                           message: list[dict],
                           mongo_db_name: str,
                           mongo_collection_name: str,
                           pbar: tqdm,
                           max_retries: int = 5) -> None:
        '''
        Call the Gemini API with a backoff strategy for handling rate limits.

        :param request_id: The request ID for tracking.
        :type request_id: int

        :param uuid: The UUID of the narrative being processed.
        :type uuid: str

        :param message: The message prompt to be processed.
        :type message: list[dict]

        :param mongo_db_name: Name of the MongoDB database.
        :type mongo_db_name: str

        :param mongo_collection_name: Name of the MongoDB collection.
        :type mongo_collection_name: str

        :param pbar: Tqdm progress bar for tracking progress.
        :type pbar: tqdm

        :param max_retries: Maximum number of retries for the request (default 5).
        :type max_retries: int

        :raises RateLimitError: If the request exceeds the rate limit.
        :raises Exception: For other unexpected errors.
        :return: None
        '''
        retry_count = 0
        while not self.stop_flag.is_set() and retry_count <= max_retries:
            with self.semaphore:
                try:
                    # get prompts
                    system_prompt = message[0]['content']
                    user_prompt = message[1]['content']

                    # estimate tokens
                    estimated_tokens = self._estimate_tokens(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt
                    )

                    # update progress bar
                    self._update_tqdm_description(
                        pbar,
                        f'[RUNNING] prompt #{request_id} in thread'
                    )

                    # enforce rate limits
                    self._enforce_rate_limits(
                        estimated_tokens=estimated_tokens,
                        pbar=pbar
                    )

                    # make request
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=self.TEMPERATURE,
                            response_mime_type='application/json'
                        )
                    )

                    # process response
                    self._process_response(
                        uuid=uuid,
                        response=response,
                        mongo_db_name=mongo_db_name,
                        mongo_collection_name=mongo_collection_name
                    )

                    return
                
                except ClientError as e_client_error:
                    if e_client_error.code == 429:
                        # update progress bar
                        self._update_tqdm_description(
                            pbar,
                            f'[RETRY {retry_count}] prompt #{request_id} sleeping'
                        )

                        # log limits
                        self._log_write(
                            f'Rate limit exceeded for prompt #{request_id} - {e_client_error}'
                        )
                        
                        # increment retry count and calculate sleep time
                        retry_count += 1
                        random_jitter = random.uniform(0, self.DEFAULT_JITTER)
                        sleep_time = (2 ** retry_count) + random_jitter
                        self.stop_flag.wait(sleep_time)
                    else:
                        raise e_client_error
                
                except Exception as e:
                    # handle unexpected errors
                    self._update_tqdm_description(
                        pbar,
                        f'[ERROR] prompt #{request_id} error'
                    )

                    # capture full traceback
                    tb_str = traceback.format_exc()
                    
                    # write to log file
                    e_name = e.__class__.__name__
                    self._log_write(
                        f'[ERROR] prompt #{uuid} error: {e_name} - {e}\nTraceback:\n{tb_str}'
                    )

                    return
        
        # exceeded max retries
        if retry_count > max_retries:
            self._update_tqdm_description(
                pbar,
                f'[FAILED] prompt #{request_id} exceeded retries'
            )
            
            # write to log file
            self._log_write(f"[FAILED] prompt #{uuid} exceeded retries - {e_rate_limit}")
            return

    def run_parallel_prompt_tasks(self,
                                  uuids: list,
                                  messages: list,
                                  mongo_db_name: str,
                                  mongo_collection_name: str) -> None:
        '''
        Run multiple prompt tasks in parallel with thread pooling and
        rate-limiting.

        :param uuids: List of UUIDs to process.
        :type uuids: list

        :param messages: List of message prompts to process.
        :type messages: list

        :param mongo_db_name: Name of the MongoDB database.
        :type mongo_db_name: str

        :param mongo_collection_name: Name of the MongoDB collection.
        :type mongo_collection_name: str

        :raises Exception: If there is an error during execution.
        :return: None
        '''
        signal.signal(signal.SIGINT, self._signal_handler)

        # total tasks
        total_tasks = len(messages)
        with tqdm(total=total_tasks, desc="Processing requests") as pbar:
            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = {
                    executor.submit(
                        self._call_with_backoff,
                        i,
                        uuid,
                        message,
                        mongo_db_name,
                        mongo_collection_name,
                        pbar
                    ): i
                    for i, (uuid, message) in enumerate(zip(uuids, messages))
                }
                while futures:
                    done, _ = wait(futures.keys(), timeout=0.2)
                    for future in done:
                        futures.pop(future)
                        try:
                            future.result()
                        except Exception as e:
                            pass
                        pbar.update(1)
