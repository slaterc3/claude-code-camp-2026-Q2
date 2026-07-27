"""
Step 3 — The Prompt Builder  +  Step 4 — The API Client

Step 3: build the exact request body each provider expects, and normalize
        their different responses back into one shape: {stop_reason, content}
Step 4: a low-level HTTP client that POSTs to the REST API. Stdlib only.

Adding a provider later = a new Backend subclass. The Agent never learns
which provider it is talking to.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from structs import Context


class ApiError(Exception):
    """Raised when the HTTP call fails or the provider returns an error."""


# --------------------------------------------------------------------------
# Step 4 — The API Client (low-level HTTP)
# --------------------------------------------------------------------------

class HttpClient:
    """Minimal JSON-over-HTTPS POST. No third-party libraries."""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("content-type", "application/json")
        for k, v in headers.items():
            req.add_header(k, v)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise ApiError(f"HTTP {e.code} from {url}: {detail}") from e
        except urllib.error.URLError as e:
            raise ApiError(f"network error calling {url}: {e.reason}") from e


# --------------------------------------------------------------------------
# Step 3 — The Prompt Builder (per-backend request + response normalization)
# --------------------------------------------------------------------------

class Backend:
    """Base class: build_request + parse_response are the contract."""

    name = "base"

    def __init__(self, api_key: str, model: str, max_tokens: int = 1024,
                 client: HttpClient | None = None):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.client = client or HttpClient()

    def build_request(self, context: Context, tools: list[dict[str, Any]]) -> dict:
        raise NotImplementedError

    def parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize to {stop_reason, content, usage, raw}."""
        raise NotImplementedError

    def call(self, context: Context, tools: list[dict[str, Any]]) -> dict[str, Any]:
        url, headers, payload = self.build_request(context, tools)
        raw = self.client.post_json(url, payload, headers)
        return self.parse_response(raw)

    def estimate_cost(self, usage: dict[str, int]) -> float:
        return 0.0


class AnthropicBackend(Backend):
    """Anthropic Messages API."""

    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"
    VERSION = "2023-06-01"

    # USD per million tokens (input, output)
    PRICING = {
        "claude-haiku-4-5":  (1.00, 5.00),
        "claude-sonnet-4-5": (3.00, 15.00),
        "claude-opus-4-1":   (15.00, 75.00),
    }

    def build_request(self, context: Context, tools: list[dict[str, Any]]):
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": context.to_api_messages(),
        }
        if context.system_prompt:
            payload["system"] = context.system_prompt
        if tools:
            payload["tools"] = tools

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.VERSION,
        }
        return self.URL, headers, payload

    def parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Anthropic returns content blocks: text, tool_use, thinking."""
        content: list[dict[str, Any]] = []
        for block in raw.get("content", []):
            btype = block.get("type")
            if btype == "text":
                content.append({"type": "text", "text": block["text"]})
            elif btype == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block["id"],
                    "name": block["name"],
                    "input": block.get("input", {}),
                })
            elif btype in ("thinking", "redacted_thinking"):
                # normalized reasoning block (step 12)
                content.append({
                    "type": "reasoning",
                    "text": block.get("thinking", ""),
                })

        usage = raw.get("usage", {}) or {}
        return {
            "stop_reason": raw.get("stop_reason"),
            "content": content,
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
            "model": raw.get("model", self.model),
            "raw": raw,
        }

    def estimate_cost(self, usage: dict[str, int]) -> float:
        in_rate, out_rate = self.PRICING.get(self.model, (0.0, 0.0))
        return (usage.get("input_tokens", 0) / 1_000_000) * in_rate + \
               (usage.get("output_tokens", 0) / 1_000_000) * out_rate


BACKENDS = {"anthropic": AnthropicBackend}


def build_backend(config, client: HttpClient | None = None) -> Backend:
    """Construct the backend named in settings.json."""
    name = config.get("backend", "anthropic")
    cls = BACKENDS.get(name)
    if cls is None:
        raise ApiError(f"unknown backend {name!r}; have {list(BACKENDS)}")
    key = config.secret("ANTHROPIC_API_KEY")
    if not key:
        raise ApiError("ANTHROPIC_API_KEY missing from ~/.boukensha/.env")
    return cls(
        api_key=key,
        model=config.get("model", "claude-haiku-4-5"),
        max_tokens=config.get("max_tokens", 1024),
        client=client,
    )


if __name__ == "__main__":
    from config import Config
    from structs import Message

    cfg = Config()
    backend = build_backend(cfg)
    print("backend:", backend.name, "| model:", backend.model)

    ctx = Context(system_prompt="You are terse. Answer in under 10 words.")
    ctx.add(Message.user("Say hello and nothing else."))

    result = backend.call(ctx, tools=[])
    print("stop_reason:", result["stop_reason"])
    for block in result["content"]:
        if block["type"] == "text":
            print("text:", block["text"])
    print("usage:", result["usage"])
    print(f"cost: ${backend.estimate_cost(result['usage']):.6f}")
