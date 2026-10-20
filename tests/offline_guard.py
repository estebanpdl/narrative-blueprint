"""Fail closed on provider construction, credential loading and network use."""

import builtins
import io
import os
from pathlib import Path
import socket

import dotenv
import dotenv.main
import openai
from google import genai
import pymongo


def forbidden(*args, **kwargs):
    raise AssertionError("Offline guard: provider, credential or network access")


def install_guard(patch):
    """Install before test collection so imported aliases are guarded too."""
    for module, names in (
        (dotenv, ("load_dotenv", "dotenv_values", "find_dotenv")),
        (dotenv.main, ("load_dotenv", "dotenv_values", "find_dotenv")),
        (openai, ("OpenAI", "AsyncOpenAI", "AzureOpenAI", "AsyncAzureOpenAI")),
        (genai, ("Client",)),
        (pymongo, ("MongoClient",)),
        (socket, ("create_connection", "getaddrinfo")),
        (socket.socket, ("connect", "connect_ex", "sendto", "sendmsg")),
    ):
        for name in names:
            if hasattr(module, name):
                patch.setattr(module, name, forbidden)

    for module in (builtins, io, os):
        original = module.open

        def guarded_open(file, *args, _original=original, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                name = Path(os.fsdecode(file)).name.lower()
                if name == ".env" or name.startswith(".env."):
                    forbidden()
            return _original(file, *args, **kwargs)

        patch.setattr(module, "open", guarded_open)

    # Tests must not inherit real provider credentials, including child tests.
    for key in tuple(os.environ):
        if key.upper().startswith(("OPENAI_", "GEMINI_", "GOOGLE_API_")):
            patch.delenv(key, raising=False)
