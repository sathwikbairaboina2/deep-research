# ADR-0003: Call the Ollama native `/api/chat` with a JSON-schema `format`, behind a tiny `LLM` protocol

- Status: accepted (2026-10-04)

## Context
Prototype (2026-10-04): `POST /api/chat` with `format=<JSON schema>`, `think: false` and `temperature: 0` on `qwen3.8:27b` returned schema-valid JSON, and all 4 proposed quotes were found in the SQLite WAL page. The call took 138.8 s for 957 prompt and 352 completion tokens while other sessions shared the GPU. Live runs are slow, so the eval must stay small.

## Decision
- `deep_research.llm.OllamaLLM` uses `httpx` against `/api/chat`, non-streaming, with `format` set to the Pydantic model's JSON schema, `think: false`, and `options = {temperature: 0, num_ctx: 16384, num_predict: <per call>}`. Timeout is 900 s.
- Token usage comes from `prompt_eval_count` and `eval_count`.
- `call_structured()` validates with Pydantic and retries once with the validation error appended. A second failure raises `LLMOutputError`.
- Tests use `ScriptedLLM`. It answers by `purpose` (`plan`, `queries`, `extract`, `write`) with a function of the request, so parallel branches stay deterministic.

## What I gave up
- `langchain-ollama` / `ChatOllama`, and provider portability through LangChain chat models. This removes one dependency layer and gives full control of `format` and `think`. A second provider means writing another small class.
- Streaming tokens to the terminal.
