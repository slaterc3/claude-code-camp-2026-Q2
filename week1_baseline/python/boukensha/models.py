"""
Step 12 (part 1) — The Models table

A static model -> capability lookup so Context can be sized correctly BEFORE a
backend is even constructed. Unknown models fall back to a conservative default
rather than assuming a huge window (which would let usage silently overflow).

context_window = the model's max INPUT capacity (tokens).
"""

from __future__ import annotations

# Conservative fallback for anything we don't recognize.
_DEFAULT_WINDOW = 32_000

# model name (prefix-matched) -> context window in tokens
_WINDOWS: dict[str, int] = {
    # Anthropic
    "claude-haiku-4-5":   200_000,
    "claude-sonnet-4-5":  200_000,
    "claude-opus-4":      200_000,
    "claude-3-5":         200_000,
    # OpenAI (for later, if you add the backend)
    "gpt-5":              400_000,
    "gpt-4o":             128_000,
    # Gemini
    "gemini-2":           1_000_000,
    # Local (Ollama) — usually small
    "llama":              8_000,
    "qwen":               32_000,
}


class Models:
    """Static capability table."""

    @staticmethod
    def context_window(model: str) -> int:
        """Best-effort context window for a model name.

        Prefix match so 'claude-haiku-4-5-20251001' resolves to the
        'claude-haiku-4-5' entry.
        """
        if not model:
            return _DEFAULT_WINDOW
        # exact hit first
        if model in _WINDOWS:
            return _WINDOWS[model]
        # then longest prefix match
        best = None
        for prefix, window in _WINDOWS.items():
            if model.startswith(prefix):
                if best is None or len(prefix) > len(best[0]):
                    best = (prefix, window)
        return best[1] if best else _DEFAULT_WINDOW


if __name__ == "__main__":
    for m in [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5",
        "gpt-5.1",
        "gemini-2.0-flash",
        "llama3.2",
        "some-unknown-model",
    ]:
        print(f"{m:35s} -> {Models.context_window(m):>10,}")
