# Sends chat and model-list requests to the local Ollama server.
import time

import requests

from app.config import OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_URL


class OllamaUnreachableError(Exception):
    """Ollama server cannot be reached."""


class OllamaTimeoutError(Exception):
    """Ollama did not answer within the timeout."""


class OllamaHttpError(Exception):
    """Ollama answered with an HTTP error."""

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def ask_ollama(system_text, user_text, json_schema=None):
    # Send a system and user message to the model and return its reply.
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
    }
    if json_schema is not None:
        payload["format"] = json_schema

    started = time.perf_counter()
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT_SECONDS
        )
    except requests.Timeout as error:
        raise OllamaTimeoutError(f"Ollama did not answer within {OLLAMA_TIMEOUT_SECONDS} seconds") from error
    except requests.ConnectionError as error:
        raise OllamaUnreachableError(f"Cannot connect to Ollama at {OLLAMA_URL}") from error
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if response.status_code != 200:
        raise OllamaHttpError(response.text, response.status_code)
    data = response.json()
    return {
        "text": data["message"]["content"],
        "model": data["model"],
        "elapsed_ms": elapsed_ms,
    }


def get_installed_models():
    # Return the names of models installed in Ollama.
    response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    response.raise_for_status()
    return [model["name"] for model in response.json().get("models", [])]
