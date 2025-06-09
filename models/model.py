# -*- coding: utf-8 -*-

'''
Defines LanguageModel base class

'''

# import modules
import os
import time
import json
import random
import threading

# abstract base class
from abc import ABC, abstractmethod

# tqdm bar
from tqdm import tqdm

# LanguageModel abstract base class
class LanguageModel(ABC):
    '''
    Abstract base class for language models.

    This class defines the structure and common functionality for language model implementations,
    including rate limiting and logging.

    Class Variables:
        - AVERAGE_TOKEN_USAGE: Average token usage for responses.
        - MAX_CONCURRENT_REQUESTS: Maximum number of concurrent requests allowed.
        - DEFAULT_JITTER: Default jitter value for rate limiting.
        - TEMPERATURE: Output parameter for controlling randomness in responses.

    Public Methods:
        - get_log_file: Abstract method to get the log file path.
        - _log_write: Write a message to the log file.
        - _update_tqdm_postfix: Update the tqdm progress bar postfix safely.
        - _update_tqdm_description: Update the tqdm progress bar description safely.
        - _get_average_completion_tokens: Get the average number of tokens used in responses.
        - _enforce_rate_limits: Enforce rate limits for API requests.
        - _signal_handler: Handle termination signals.
        - _estimate_tokens: Abstract method to estimate tokens in a prompt.
        - run_parallel_prompt_tasks: Abstract method to process multiple messages.
    '''

    # average token usage
    AVERAGE_TOKEN_USAGE = 1000

    # maximum number of concurrent requests
    MAX_CONCURRENT_REQUESTS = 10

    # jitter min value
    DEFAULT_JITTER = 0.15

    # output parameters
    TEMPERATURE = 0.5

    def __init__(self, provider: str, model_name: str):
        '''
        Initialize the LanguageModel abstract base class.

        :param provider: The provider of the model.
        :type provider: str

        :param model_name: The name of the model.
        :type model_name: str
        :raises KeyError: If the model limits cannot be found for the specified provider and model name.
        '''
        # get model limits
        model_limits_config = self.get_model_limits()
        self.model_limits = model_limits_config[provider][model_name]
        self.max_requests_per_min = self.model_limits['rpm']
        self.max_tokens_per_min = self.model_limits['tpm']

        # API limits
        self.request_interval = 60.0 / self.max_requests_per_min

        # shared threading locks
        self.rate_limit_lock = threading.Lock()
        self.token_lock = threading.Lock()
        self.tqdm_lock = threading.Lock()

        # shared controls for rate limiting
        self.request_timestamps = []
        self.token_usage_log = []

        # threading semaphore
        self.semaphore = threading.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        # shared threading event
        self.stop_flag = threading.Event()

    def get_model_limits(self) -> dict:
        '''
        Retrieve the model limits from the configuration file.

        :return: A dictionary containing model limits for different providers and models.
        :rtype: dict
        :raises FileNotFoundError: If the model limits configuration file does not exist.
        :raises json.JSONDecodeError: If the configuration file is not a valid JSON.
        '''
        path = './config/model_limits.json'
        with open(path, 'r', encoding='utf-8') as f:
            model_limits = json.load(f)
        
        return model_limits
    
    @abstractmethod
    def get_log_file(self) -> str:
        '''
        Abstract method to get the log file path.

        :return: The path to the log file.
        :rtype: str
        '''
        pass

    def _log_write(self, message: str) -> None:
        '''
        Write a message to the log file.

        :param message: The message to be written to the log file.
        :type message: str
        :raises IOError: If there is an error writing to the log file.
        :return: None
        '''
        # get log file
        log_file = self.get_log_file()

        # create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # write to log file
        with open(log_file, 'a') as f:
            f.write(message + '\n')
    
    def _update_tqdm_postfix(self, pbar: tqdm, data: dict) -> None:
        '''
        Update the tqdm progress bar postfix (metrics) safely.

        :param pbar: The tqdm progress bar instance.
        :type pbar: tqdm

        :param data: A dictionary of metric names and values.
        :type data: dict
        :return: None
        '''
        if pbar is not None:
            with self.tqdm_lock:
                pbar.set_postfix(data)
    
    def _update_tqdm_description(self, pbar: tqdm, message: str) -> None:
        '''
        Update the tqdm progress bar description safely.

        :param pbar: The tqdm progress bar instance.
        :type pbar: tqdm

        :param message: The message to be displayed in the progress bar.
        :type message: str
        :return: None
        '''
        if pbar is not None:
            with self.tqdm_lock:
                pbar.set_description(f'{self.model_name} - {message}')
    
    def _get_average_completion_tokens(self) -> int:
        '''
        Get the average number of tokens used in responses.

        :return: The average number of tokens used in responses.
        :rtype: int
        '''
        if not self.token_usage_log:
            return self.AVERAGE_TOKEN_USAGE
        
        completion_tokens = [c for _, _, c in self.token_usage_log]
        return int(sum(completion_tokens) / len(completion_tokens))
    
    def _enforce_rate_limits(self, estimated_tokens: int,
                             pbar: tqdm = None) -> None:
        '''
        Enforce rate limits for API requests.

        This method ensures that the number of requests and tokens used per minute does not exceed
        the specified limits.

        :param estimated_tokens: The estimated tokens in the prompt.
        :type estimated_tokens: int

        :param pbar: The tqdm progress bar instance (optional).
        :type pbar: tqdm, optional
        :return: None
        '''
        # wait for rate limit slot
        while True:
            wait_time = 0
            with self.rate_limit_lock, self.token_lock:
                now = time.time()

                # timestamps and tokens used
                self.request_timestamps[:] = [
                    t for t in self.request_timestamps if now - t < 60.0
                ]
                self.token_usage_log[:] = [
                    (t, p, c) for t, p, c in self.token_usage_log if now - t < 60.0
                ]

                if len(self.request_timestamps) >= self.max_requests_per_min:
                    if self.request_timestamps:
                        oldest_request_time = self.request_timestamps[0]
                        request_wait = 60.0 - (now - oldest_request_time)
                    else:
                        request_wait = 1.0
                    wait_time = max(wait_time, request_wait)
                
                tokens_used = sum(p + c for _, p, c in self.token_usage_log)

                # update progress bar
                self._update_tqdm_postfix(pbar, {'Tokens used/60s': tokens_used})

                # response buffer
                response_buffer = self._get_average_completion_tokens()

                # aggregate tokens -> tokens already used + (estimated tokens in next prompt) + (avg tokens in responses)
                agg_tokens = tokens_used + estimated_tokens + response_buffer
                if agg_tokens > self.max_tokens_per_min:
                    if self.token_usage_log:
                        oldest_token_time = self.token_usage_log[0][0]
                        token_wait = 60.0 - (now - oldest_token_time)
                    else:
                        token_wait = 1.0
                    wait_time = max(wait_time, token_wait)
                
                if wait_time == 0:
                    # no enforced wait time
                    now = time.time()
                    self.request_timestamps.append(now)

                    # add jitter to avoid thread pileup
                    jitter = self.DEFAULT_JITTER + random.uniform(0, 0.05)
                    self.stop_flag.wait(jitter)
                    break

            # wait_time != 0 - enforced rate-limit sleep - when over RPM/TPM
            jittered_wait = wait_time + random.uniform(0.05, 0.25)
            self._update_tqdm_description(
                pbar,
                f'[WAITING] Sleeping {jittered_wait:.2f}s (RPM/TPM limit)'
            )

            self.stop_flag.wait(jittered_wait)
    
    def _signal_handler(self, sig, frame) -> None:
        '''
        Signal handler for termination signals (e.g., Ctrl+C).

        :param sig: The signal number.
        :type sig: int

        :param frame: The current stack frame.
        :type frame: frame
        :return: None
        '''
        self.stop_flag.set()

    @abstractmethod
    def _estimate_tokens(self, prompt: str) -> int:
        '''
        Estimate the number of tokens in the prompt.

        :param prompt: The prompt to be estimated.
        :type prompt: str
        :return: The estimated number of tokens.
        :rtype: int
        '''
        pass

    @abstractmethod
    def run_parallel_prompt_tasks(self, messages: list) -> None:
        '''
        Process multiple messages in a single call.

        :param messages: List of messages to be processed.
        :type messages: list
        :return: None
        '''
        pass
