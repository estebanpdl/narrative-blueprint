"""Tripwire tests use synthetic targets and never disable the guard."""

import builtins
import io
import os
from pathlib import Path
import socket

import dotenv
import dotenv.main
from google import genai
import openai
import pymongo
import pytest


@pytest.mark.parametrize("call", [
    lambda: dotenv.load_dotenv("unused"),
    lambda: dotenv.dotenv_values("unused"),
    lambda: dotenv.find_dotenv(),
    lambda: dotenv.main.load_dotenv("unused"),
    lambda: openai.OpenAI(api_key="synthetic"),
    lambda: openai.AsyncOpenAI(api_key="synthetic"),
    lambda: genai.Client(api_key="synthetic"),
    lambda: pymongo.MongoClient("mongodb://127.0.0.1"),
    lambda: socket.create_connection(("127.0.0.1", 1)),
    lambda: socket.getaddrinfo("localhost", 1),
])
def test_external_access_is_blocked(call):
    with pytest.raises(AssertionError, match="Offline guard"):
        call()


@pytest.mark.parametrize("opener", [builtins.open, io.open, Path.open, os.open])
def test_env_file_open_is_blocked(tmp_path, opener):
    # No real credential path is used, even if the guard regresses.
    path = tmp_path / ".env"
    with pytest.raises(AssertionError, match="Offline guard"):
        if opener is os.open:
            opener(path, os.O_RDONLY)
        else:
            opener(path)


def test_socket_connect_is_blocked():
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="Offline guard"):
            connection.connect(("127.0.0.1", 1))
