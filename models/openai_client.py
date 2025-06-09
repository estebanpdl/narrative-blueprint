# -*- coding: utf-8 -*-

# import modules
import ast
import json
import time
import signal
import random
import openai
import tiktoken
import traceback

# typing
from typing import Callable

# dotenv for environment variables
from dotenv import load_dotenv

# multithreading
from concurrent.futures import ThreadPoolExecutor, wait

# tqdm bar
from tqdm import tqdm

# import base class
from .model import LanguageModel

# OpenAI related modules
from openai import OpenAI, RateLimitError

# MongoDB connection
from databases import MongoDBManager

# OpenAIGPT class
class OpenAIGPT(LanguageModel):
    '''
    OpenAIGPT class for interacting with OpenAI's API.

    This class provides methods to generate responses using the specified OpenAI model,
    manage token usage, and log responses to a MongoDB database.

    Public Methods:
        - get_log_file: Returns the path to the log file.
        - _estimate_tokens: Estimates the number of tokens in a given prompt.
        - _process_response: Processes the API response and logs it to MongoDB.
        - _call_with_backoff: Calls the OpenAI API with a backoff strategy for rate limits.
        - run_parallel_prompt_tasks: Executes multiple prompt tasks in parallel.

    Instance Variables:
        - client: OpenAI client instance.
        - model_name: Name of the OpenAI model.
        - encoding: Token encoding for the model.
        - log_file: Path to the log file.
        - audit_response: Instance for auditing responses.
        - mongodb_manager: MongoDB connection manager.
    '''
    def __init__(self, model_name: str):
        '''
        Initialize the OpenAIGPT class.

        :param model_name: The name of the OpenAI model to be used.
        :type model_name: str
        :raises KeyError: If the model name is not recognized for token encoding.
        '''
        super().__init__(provider='openai', model_name=model_name)

        # load environment variables
        env_file_path = './config/.env'
        load_dotenv(env_file_path)

        # OpenAI client
        self.client = OpenAI()

        # OpenAI model
        self.model_name = model_name

        # OpenAI model token encoding
        try:
            self.encoding = tiktoken.encoding_for_model(self.model_name)
        except Exception as KeyError:
            self.encoding = tiktoken.get_encoding('o200k_base')

        # log file
        self.log_file = './logs/openai_client.log'

        # MongoDB connection
        self.mongodb_manager = MongoDBManager()
    
    def get_log_file(self) -> str:
        '''
        Get the log file path.

        :return: The path to the log file.
        :rtype: str
        '''
        return self.log_file

    def _estimate_tokens(self, prompt: str) -> int:
        '''
        Estimate the number of tokens in a prompt.

        :param prompt: The prompt to be estimated.
        :type prompt: str
        
        :return: The estimated number of tokens.
        :rtype: int
        '''
        # estimate tokens
        return len(self.encoding.encode(prompt))
    
    def _process_response(self,
                          uuid: str,
                          system_prompt: str,
                          user_prompt: str,
                          response: openai.ChatCompletion,
                          mongo_db_name: str = None,
                          mongo_collection_name: str = None) -> None:
        '''
        Process the API response and log it to MongoDB.

        :param uuid: The UUID of the narrative that has been processed.
        :type uuid: str

        :param system_prompt: The system prompt used to generate the response.
        :type system_prompt: str

        :param user_prompt: The user prompt used to generate the response.
        :type user_prompt: str

        :param response: The response from the OpenAI API.
        :type response: openai.ChatCompletion

        :param mongo_db_name: Name of the MongoDB database (optional).
        :type mongo_db_name: str, optional

        :param mongo_collection_name: Name of the MongoDB collection (optional).
        :type mongo_collection_name: str, optional

        :param task: The task to be processed (optional).
        :type task: str, optional

        :param judge_fn: A function that evaluates the model output (optional).
        :type judge_fn: Callable, optional

        :raises Exception: If there is an error during processing or logging.
        :return: None
        '''
        # get tokens used
        prompt_tokens_used = response.usage.prompt_tokens
        completion_tokens_used = response.usage.completion_tokens

        # update token usage log
        self.token_usage_log.append(
            (
                time.time(),
                prompt_tokens_used,
                completion_tokens_used
            )
        )

        # get response
        response_content = response.choices[0].message.content

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
                           mongo_db_name: str = None,
                           mongo_collection_name: str = None,
                           response_format: dict = None,
                           pbar: tqdm = None,
                           max_retries: int = 5) -> None:
        '''
        Call the OpenAI API with a backoff strategy for handling rate limits.

        :param request_id: The request ID for tracking.
        :type request_id: int

        :param uuid: The UUID of the narrative being processed.
        :type uuid: str

        :param message: The message prompt to be processed.
        :type message: list[dict]

        :param mongo_db_name: Name of the MongoDB database (optional).
        :type mongo_db_name: str, optional

        :param mongo_collection_name: Name of the MongoDB collection (optional).
        :type mongo_collection_name: str, optional

        :param response_format: The expected response format (optional).
        :type response_format: dict, optional

        :param pbar: The tqdm progress bar for tracking progress (optional).
        :type pbar: tqdm, optional

        :param max_retries: The maximum number of retries for the request (default is 5).
        :type max_retries: int, optional

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
                    prompt = f'{system_prompt}\n{user_prompt}'
                    estimated_tokens = self._estimate_tokens(prompt)

                    # update progress bar
                    self._update_tqdm_description(
                        pbar,
                        f'[RUNNING] prompt #{request_id} in thread'
                    )
                    
                    # enforce rate limits
                    self._enforce_rate_limits(
                        estimated_tokens,
                        pbar
                    )

                    # make request
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=message,
                        temperature=self.TEMPERATURE,
                        response_format=response_format
                    )

                    self._process_response(
                        uuid,
                        system_prompt,
                        user_prompt,
                        response,
                        mongo_db_name,
                        mongo_collection_name,
                    )

                    return
                    
                except RateLimitError as e_rate_limit:
                    # update progress bar
                    self._update_tqdm_description(
                        pbar,
                        f'[RETRY {retry_count}] prompt #{request_id} sleeping'
                    )
                    
                    # increment retry count and calculate sleep time
                    retry_count += 1
                    random_jitter = random.uniform(0, self.DEFAULT_JITTER)
                    sleep_time = (2 ** retry_count) + random_jitter
                    self.stop_flag.wait(sleep_time)
                
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
                                  uuids: list = None,
                                  messages: list = None,
                                  mongo_db_name: str = None,
                                  mongo_collection_name: str = None,
                                  response_format: dict = None) -> None:
        '''
        Run multiple prompt tasks in parallel with thread pooling and rate-limiting.

        :param uuids: List of UUIDs to process.
        :type uuids: list

        :param messages: List of message prompts to process.
        :type messages: list

        :param mongo_db_name: Name of the MongoDB database (optional).
        :type mongo_db_name: str, optional

        :param mongo_collection_name: Name of the MongoDB collection (optional).
        :type mongo_collection_name: str, optional

        :param response_format: The expected response format (optional).
        :type response_format: dict, optional

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
                        response_format,
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
