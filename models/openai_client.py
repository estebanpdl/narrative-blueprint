# -*- coding: utf-8 -*-

# import modules
import json
import time
import signal
import random
import openai
import tiktoken
import traceback

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

# OpenAIGPT class
class OpenAIGPT(LanguageModel):
    '''
    OpenAIGPT class for interacting with OpenAI's API.

    This class provides methods to generate responses using the specified
    OpenAI model, manage token usage, and return structured results.

    Public Methods:
    - get_log_file: Returns the path to the log file.
    - _estimate_tokens: Estimates the number of tokens in a given prompt.
    - _process_response: Processes the API response and returns a document.
    - _call_with_backoff: Calls the OpenAI API with a backoff strategy.
    - run_parallel_prompt_tasks: Executes multiple prompt tasks in parallel.

    Instance Variables:
    - client: OpenAI client instance.
    - model_name: Name of the OpenAI model.
    - encoding: Token encoding for the model.
    - log_file: Path to the log file.
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
                          response: openai.ChatCompletion) -> dict:
        '''
        Process the API response and return a result document.

        :param uuid: The UUID of the narrative that has been processed.
        :type uuid: str

        :param response: The response from the OpenAI API.
        :type response: openai.ChatCompletion

        :return: Parsed response document with uuid.
        :rtype: dict
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

        return response_content

    def _call_with_backoff(self,
                           request_id: int,
                           uuid: str,
                           message: list[dict],
                           pbar: tqdm = None,
                           on_result: callable = None,
                           max_retries: int = 5) -> dict:
        '''
        Call the OpenAI API with a backoff strategy for handling rate limits.

        :param request_id: The request ID for tracking.
        :type request_id: int

        :param uuid: The UUID of the narrative being processed.
        :type uuid: str

        :param message: The message prompt to be processed.
        :type message: list[dict]

        :param pbar: Tqdm progress bar for tracking progress.
        :type pbar: tqdm

        :param max_retries: Maximum number of retries for the request (default 5).
        :type max_retries: int

        :return: Parsed result document, or None on failure.
        :rtype: dict or None
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
                        estimated_tokens=estimated_tokens,
                        pbar=pbar
                    )

                    # make request
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=message,
                        temperature=self.TEMPERATURE,
                        response_format={'type': 'json_object'}
                    )

                    result = self._process_response(
                        uuid=uuid,
                        response=response,
                    )

                    if on_result is not None:
                        on_result(result)

                    return result

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

                    return None

        # exceeded max retries
        if retry_count > max_retries:
            self._update_tqdm_description(
                pbar,
                f'[FAILED] prompt #{request_id} exceeded retries'
            )

            # write to log file
            self._log_write(f"[FAILED] prompt #{uuid} exceeded retries - {e_rate_limit}")
            return None

    def run_parallel_prompt_tasks(self,
                                  uuids: list,
                                  messages: list,
                                  on_result: callable = None) -> list:
        '''
        Run multiple prompt tasks in parallel with thread pooling and
        rate-limiting.

        :param uuids: List of UUIDs to process.
        :type uuids: list

        :param messages: List of message prompts to process.
        :type messages: list

        :param on_result: Optional callback invoked with each result document
            as soon as it is ready.
        :type on_result: callable, optional

        :return: List of result documents.
        :rtype: list
        '''
        signal.signal(signal.SIGINT, self._signal_handler)

        results = []
        results_lock = __import__('threading').Lock()

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
                        pbar,
                        on_result
                    ): i
                    for i, (uuid, message) in enumerate(zip(uuids, messages))
                }
                while futures:
                    done, _ = wait(futures.keys(), timeout=0.2)
                    for future in done:
                        futures.pop(future)
                        try:
                            result = future.result()
                            if result is not None:
                                with results_lock:
                                    results.append(result)
                        except Exception as e:
                            pass
                        pbar.update(1)

        return results
