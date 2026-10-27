# Flask blueprint with two Ollama test endpoints; never writes to the database.
import requests
from flask import Blueprint, jsonify, request

from app.config import OLLAMA_MODEL
from app.ollama_client import (
    OllamaHttpError,
    OllamaTimeoutError,
    OllamaUnreachableError,
    ask_ollama,
    get_installed_models,
)

ollama_bp = Blueprint("ollama", __name__)

TEST_SYSTEM_TEXT = "Reply with one short sentence in Vietnamese."


@ollama_bp.get("/ollama/health")
def ollama_health():
    # Report whether Ollama is reachable and whether the model is installed.
    try:
        names = get_installed_models()
    except requests.RequestException:
        return jsonify(reachable=False, detail="Cannot connect to Ollama"), 503
    return jsonify(
        reachable=True,
        model=OLLAMA_MODEL,
        model_available=OLLAMA_MODEL in names,
        installed_models=names,
    )


@ollama_bp.post("/ollama/test")
def ollama_test():
    # Send the posted text to the model and return its reply.
    body = request.get_json(silent=True) or {}
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify(detail="text is required"), 400
    try:
        result = ask_ollama(TEST_SYSTEM_TEXT, text.strip())
    except OllamaUnreachableError as error:
        return jsonify(detail=str(error)), 503
    except OllamaTimeoutError as error:
        return jsonify(detail=str(error)), 504
    except OllamaHttpError as error:
        return jsonify(detail=str(error)), 502
    return jsonify(reply=result["text"], model=result["model"], elapsed_ms=result["elapsed_ms"])
