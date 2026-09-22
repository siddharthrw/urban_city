"""
Phase 7/11: LLM wrapper -- local Ollama or NVIDIA NIM (hosted, OpenAI-compatible).

Provider is selected via LLM_PROVIDER env var ("ollama" default, or "nim").
Reads a local .env file for secrets (NVIDIA_API_KEY) so it never needs to be
typed into a terminal or committed to source.

NIM notes: the free-tier key only has access to a subset of models, and many
"obvious" model names (Llama 3.x, Mistral-7B, etc.) have been retired. Testing
found `openai/gpt-oss-20b` to be the reliable choice -- but it's a reasoning
model with hidden chain-of-thought tokens, so it needs a large max_tokens
budget or it truncates mid-thought and returns empty content.
"""
import json
import os
from pathlib import Path

import requests

# --- .env loading (no external dependency) ---
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

PROVIDER = os.environ.get("LLM_PROVIDER", "ollama").lower()

# --- Ollama (local) ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

# --- NVIDIA NIM (hosted) ---
NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NIM_MODEL = os.environ.get("NVIDIA_MODEL", "openai/gpt-oss-20b")
NIM_MAX_TOKENS = int(os.environ.get("NVIDIA_MAX_TOKENS", "1500"))

DEFAULT_MODEL = NIM_MODEL if PROVIDER == "nim" else OLLAMA_MODEL


def _chat_ollama(messages: list, model: str, json_mode: bool) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    if json_mode:
        payload["format"] = "json"

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Could not reach Ollama at {OLLAMA_URL}: {e}") from e

    return resp.json()["message"]["content"]


def _chat_nim(messages: list, model: str, json_mode: bool) -> str:
    if not NIM_API_KEY:
        raise RuntimeError("LLM_PROVIDER=nim but NVIDIA_API_KEY is not set (check .env)")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": NIM_MAX_TOKENS,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(
            NIM_URL,
            headers={"Authorization": f"Bearer {NIM_API_KEY}"},
            json=payload,
            timeout=90,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Could not reach NVIDIA NIM: {e}") from e

    data = resp.json()
    choice = data["choices"][0]
    content = choice["message"]["content"]
    if content is None:
        # Reasoning model burned the whole max_tokens budget on hidden
        # chain-of-thought before producing an answer.
        raise RuntimeError(
            f"NIM model '{model}' returned no content (finish_reason="
            f"{choice.get('finish_reason')}) -- likely ran out of max_tokens "
            f"during reasoning. Try raising NVIDIA_MAX_TOKENS."
        )
    return content


def chat(prompt: str, system: str = "", model: str = None, json_mode: bool = False) -> str:
    model = model or DEFAULT_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if PROVIDER == "nim":
        return _chat_nim(messages, model, json_mode)
    return _chat_ollama(messages, model, json_mode)


def chat_json(prompt: str, system: str = "", model: str = None, retries: int = 2) -> dict:
    last_err = None
    for attempt in range(retries + 1):
        try:
            raw = chat(prompt, system=system, model=model, json_mode=True)
            return json.loads(raw)
        except (json.JSONDecodeError, RuntimeError) as e:
            last_err = e
            continue
    raise RuntimeError(f"Model did not return valid JSON after {retries + 1} attempts: {last_err}")


if __name__ == "__main__":
    print(f"Provider: {PROVIDER}, model: {DEFAULT_MODEL}")
    print(chat("Say OK if you can hear me."))
