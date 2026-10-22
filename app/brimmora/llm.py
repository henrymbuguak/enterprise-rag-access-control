"""Model serving client (Ollama). Records token usage for cost tracking."""
import httpx

from .config import settings
from .metrics import LLM_TOKENS


def chat(messages, purpose, json_mode=False, model=None):
    body = {"model": model or settings.llm_model, "messages": messages, "stream": False,
            "options": {"temperature": 0}}
    if json_mode:
        body["format"] = "json"
    r = httpx.post(f"{settings.ollama_url}/api/chat", json=body, timeout=300)
    r.raise_for_status()
    data = r.json()
    LLM_TOKENS.labels(purpose, "prompt").inc(data.get("prompt_eval_count", 0))
    LLM_TOKENS.labels(purpose, "completion").inc(data.get("eval_count", 0))
    return data["message"]["content"]
