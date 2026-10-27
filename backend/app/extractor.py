# Asks the local LLM for OPQRST fields and validates its answer.
import json
import re
import time
from dataclasses import dataclass, field

from app.config import OLLAMA_MODEL
from app.ollama_client import (
    OllamaHttpError,
    OllamaTimeoutError,
    OllamaUnreachableError,
    ask_ollama,
)

FIELD_KEYS = ("onset", "provocation_palliation", "quality", "region_radiation", "severity", "time_course")

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "off_topic": {"type": "boolean"},
        "onset": {"type": ["string", "null"]},
        "provocation_palliation": {"type": ["string", "null"]},
        "quality": {"type": ["string", "null"]},
        "region_radiation": {"type": ["string", "null"]},
        "severity": {"type": ["string", "null"]},
        "time_course": {"type": ["string", "null"]},
        "symptoms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"phrase": {"type": "string"}, "status": {"type": "boolean"}},
                "required": ["phrase", "status"],
            },
        },
    },
    "required": ["off_topic", *FIELD_KEYS, "symptoms"],
}


def empty_fields():
    # Return a field dict with every OPQRST value set to None.
    return {key: None for key in FIELD_KEYS}


@dataclass
class ExtractionResult:
    # One extraction run: validity, model text, timing and the parsed values.
    valid: bool
    raw_text: str
    model: str
    elapsed_ms: int
    error_text: str | None = None
    off_topic: bool | None = None
    fields: dict = field(default_factory=empty_fields)
    symptoms: list = field(default_factory=list)


def extract_fields(system_text, question_text, answer_text):
    # Ask the model about one patient answer and return a validated result.
    user_text = f"QUESTION: {question_text}\nANSWER: {answer_text}"
    started = time.perf_counter()
    try:
        reply = call_model(system_text, user_text)
    except OllamaTimeoutError:
        return failed_result("timeout", started)
    except OllamaUnreachableError:
        return failed_result("Ollama unreachable", started)
    except OllamaHttpError as error:
        return failed_result(f"Ollama HTTP error {error.status_code}", started)

    elapsed_ms = elapsed_since(started)
    model = reply.get("model") or OLLAMA_MODEL
    try:
        parsed = parse_model_text(reply["text"])
    except ValueError as error:
        return ExtractionResult(False, reply["text"], model, elapsed_ms, error_text=str(error))
    if parsed["off_topic"]:
        return ExtractionResult(True, reply["text"], model, elapsed_ms, off_topic=True)
    return ExtractionResult(
        True, reply["text"], model, elapsed_ms, off_topic=False, fields=parsed["fields"], symptoms=parsed["symptoms"]
    )


def call_model(system_text, user_text):
    # Ask with the JSON schema; if Ollama rejects the schema, retry in plain JSON mode.
    try:
        return ask_ollama(system_text, user_text, EXTRACT_SCHEMA)
    except OllamaHttpError as error:
        if error.status_code != 400:
            raise
    return ask_ollama(system_text, user_text, "json")


def parse_model_text(raw_text):
    # Remove think blocks and code fences, then check the JSON shape and value types.
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError("invalid JSON") from error
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    for key in ("off_topic", *FIELD_KEYS, "symptoms"):
        if key not in data:
            raise ValueError(f"missing key {key}")
    if not isinstance(data["off_topic"], bool):
        raise ValueError("off_topic is not a boolean")
    values = empty_fields()
    for key in FIELD_KEYS:
        value = data[key]
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{key} is not text or null")
        values[key] = value.strip() or None
    symptoms = parse_symptoms(data["symptoms"]) if not data["off_topic"] else []
    return {"off_topic": data["off_topic"], "fields": values, "symptoms": symptoms}


def parse_symptoms(items):
    # Check the symptom list shape, strip phrases and drop repeated phrases.
    if not isinstance(items, list):
        raise ValueError("symptoms is not a list")
    symptoms = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("symptom item is invalid")
        phrase = item.get("phrase")
        status = item.get("status")
        if not isinstance(phrase, str) or not phrase.strip() or not isinstance(status, bool):
            raise ValueError("symptom item is invalid")
        phrase = phrase.strip()
        if phrase.lower() in seen:
            continue
        seen.add(phrase.lower())
        symptoms.append({"phrase": phrase, "status": status})
    return symptoms


def failed_result(error_text, started):
    # Build an invalid result for a failed model call.
    return ExtractionResult(False, "", OLLAMA_MODEL, elapsed_since(started), error_text=error_text)


def elapsed_since(started):
    # Milliseconds elapsed since a time.perf_counter() value.
    return int((time.perf_counter() - started) * 1000)
