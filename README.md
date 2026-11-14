# ThesisMaster_Chatbot

**NAI** is a Vietnamese-language chatbot that supports outpatient triage. It was built for the Master of Software Engineering thesis *"Applying Large Language Models to a Chatbot for Outpatient Triage"* (FPT University, 2026).

## Overview

NAI conducts a short intake dialogue in Vietnamese and routes each session to one of three outcomes:

- **Emergency**: an emergency rule was satisfied, and the chatbot shows which one.
- **Clinical examination**: the OPQRST history was collected and no emergency rule fired.
- **Handover to staff**: the dialogue could not proceed, for example after repeated off-topic messages.

The system is a research prototype. It does not diagnose, recommend treatment, or replace clinical judgment.

## Architecture

NAI separates language understanding from decision making:

1. **Extraction (LLM).** A locally hosted Qwen3 model (8B parameters), served through Ollama, is confined to information extraction. For each patient message it returns, under a strict JSON schema, the six OPQRST fields, a list of affirmed or denied symptoms, and an off-topic flag.
2. **Validation and matching.** Every model output is validated defensively. Symptoms are then mapped to a catalog of 100 canonical symptoms by a deterministic matcher that preserves Vietnamese diacritics.
3. **Decision (rules).** A database-driven rule engine with 406 emergency rules, each a conjunction of canonical symptoms, determines the outcome. The LLM never makes the final decision, so every decision can be traced to an explicit rule.

All inference runs on-premises, so no patient text leaves the local network.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Angular |
| Backend | Python, Flask |
| Database | PostgreSQL (13 tables: prompts, symptom catalog, emergency rules, sessions, messages, extraction results) |
| LLM | Qwen3-8B via Ollama |

The interface shows the dialogue together with the extracted OPQRST data, the matched symptoms, and the reasoning of the rule engine.

## Evaluation

The system was evaluated on 180 deterministically generated Vietnamese scenarios (625 dialogue turns), covering emergency, clinical-examination, and handover cases, with and without diacritics.

- Three-class accuracy: 83.3% (macro-F1 0.859)
- Emergency specificity: 98.0%; emergency sensitivity: 71.3%
- Symptom extraction F1: 0.876; off-topic detection F1: 0.970
- Valid JSON in all 625 model responses; mean model call time 2.89 s

The scenarios were derived from the knowledge base and labeled by the rules, so these figures measure conformance to the specification, not clinical performance. Accuracy was much lower for text without diacritics (55.6% versus 92.6%). Most missed emergencies came from unrecognized symptoms, not from the rule engine.

## Repository structure

- `backend/`: Flask API, rule engine, LLM integration, database access
- `frontend/`: Angular web interface

## Disclaimer

This project is an academic prototype for research and demonstration only. It has not been clinically validated and must not be used for real patient care. All evaluation dialogues are simulated scenarios, and none come from real patients.

## Author

Nguyen Trung Nhan. Supervisor: Dr. Le Thanh Hai.
