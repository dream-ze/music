# Multi-provider LLM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UI-selectable DeepSeek, OpenAI, Qwen, Gemini, Anthropic, and Ollama text providers with persistent Windows credential storage and visible fallback status.

**Architecture:** A provider registry and one router remain behind `src.llm.complete()`. A focused credential module resolves temporary input, Windows Credential Manager, then environment variables; planner and lyrics append status events that the pipeline returns to Gradio.

**Tech Stack:** Python 3.12, requests, Anthropic SDK, keyring/Windows Credential Manager, Gradio, pytest.

---

## File Structure

- Create `src/credentials.py`: save/read/delete provider secrets and resolve priority.
- Create `tests/test_credentials.py`: credential behavior without touching real credentials.
- Modify `config.py`: immutable provider registry and defaults.
- Modify `src/llm.py`: provider routing and normalized safe errors.
- Modify `src/planner.py`, `src/lyrics.py`, `src/pipeline.py`: pass LLM settings and collect status events.
- Modify `app.py`: provider/model/key controls and credential actions.
- Modify related tests and dependency files.

### Task 1: Provider registry and credentials

**Files:** `config.py`, `src/credentials.py`, `tests/test_config.py`, `tests/test_credentials.py`, `requirements.txt`, `requirements-dev.txt`

- [ ] Write failing tests asserting all six providers, their default models, key environment names, temporary/saved/environment priority, save/delete, and non-Windows failure.
- [ ] Run `python -m pytest tests/test_config.py tests/test_credentials.py -q`; expect failures for missing registry/module.
- [ ] Implement `LLM_PROVIDERS`, `get_provider()`, and credential functions `get_saved_key`, `save_key`, `delete_key`, `resolve_key`, `has_key`. Inject the keyring backend in tests so real Windows credentials are untouched.
- [ ] Add `keyring` to runtime and development requirements.
- [ ] Re-run the focused tests; expect all passing.

### Task 2: Provider router

**Files:** `src/llm.py`, `tests/test_llm.py`

- [ ] Write failing tests for OpenAI-compatible request bodies/Base URLs, Gemini request shape, Anthropic routing, Ollama without Key, missing-Key errors, empty responses, and secret redaction.
- [ ] Run `python -m pytest tests/test_llm.py -q`; expect provider arguments to be unsupported.
- [ ] Implement `complete(prompt, system="", *, provider="anthropic", model=None, api_key=None, timeout=60)` and focused private adapters. Use `requests` for compatible APIs, Gemini, and Ollama; retain the Anthropic SDK. Normalize failures to `LLMError` without response bodies or secrets.
- [ ] Re-run router tests; expect all passing.

### Task 3: Pipeline propagation and fallback status

**Files:** `src/planner.py`, `src/lyrics.py`, `src/pipeline.py`, `tests/test_planner.py`, `tests/test_lyrics.py`, `tests/test_pipeline.py`

- [ ] Write failing tests showing one provider/model/Key configuration reaches both text stages and that missing/failing providers still reach song generation while returning fallback events.
- [ ] Run focused tests; expect unexpected keyword or missing status failures.
- [ ] Add optional `llm_options` and `status_events` parameters to planner and lyrics. On success append stage success; on exception append safe fallback status. Extend `make_song` with LLM options and return `llm_status`.
- [ ] Re-run focused tests; expect all passing.

### Task 4: Gradio controls and credential actions

**Files:** `app.py`, `tests/test_app.py`

- [ ] Write failing callback tests for provider selection, default model lookup, password-field behavior, save/delete status, and generation status output.
- [ ] Run `python -m pytest tests/test_app.py -q`; expect missing callbacks/parameters.
- [ ] Add provider dropdown, model textbox, password textbox, save/delete buttons, saved-key indicator, and LLM status output inside Advanced Settings. Resolve a blank UI Key through credentials before calling the pipeline; never return a stored Key to the browser.
- [ ] Re-run UI tests; expect all passing.

### Task 5: Verification and documentation

**Files:** `README.md` (create if absent), all tests.

- [ ] Document supported providers, environment variables, Windows saved credentials, Ollama URL, and fallback behavior.
- [ ] Run `python -m pytest -q`; expect zero failures.
- [ ] Run `python -m compileall app.py config.py src`; expect exit code 0.
- [ ] Start `python app.py`, request `http://127.0.0.1:7860`, and expect HTTP 200.
- [ ] Inspect `git diff --check` and `git status --short`; ensure only intended files changed and no Key appears in the diff.
