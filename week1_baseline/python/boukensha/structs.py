"""
Step 1 — The Struct Skeleton

Plain data containers. No logic beyond trivial construction/serialization.
These are the vocabulary every other component speaks.

  Tool     — a callable capability the agent can invoke
  Message  — one turn in the conversation (provider-agnostic)
  Context  — conversation state + token accounting

NOTE: Context does NOT own tools. The Tool Registry (step 2) owns them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    """A capability the agent can call.

    `input_schema` is JSON Schema, sent to the provider so the model knows
    how to call it. `handler` is the local callable the registry dispatches to.
    """
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
    })
    handler: Callable[..., Any] | None = None

    def to_schema(self) -> dict[str, Any]:
        """The shape a provider expects in its `tools` array."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class Message:
    """One message in the conversation.

    `role` is "user" | "assistant" | "system".
    `content` is either a plain string or a list of content blocks
    (text / tool_use / tool_result / reasoning) — matching the normalized
    shape the prompt builder produces from any backend.
    """
    role: str
    content: str | list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def user(cls, content: str | list[dict[str, Any]]) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str | list[dict[str, Any]]) -> "Message":
        return cls(role="assistant", content=content)

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)


@dataclass
class Context:
    """Conversation state and token accounting.

    context_window : the model's max INPUT capacity (static, from the model table)
    current_tokens : actual usage reported by the most recent API response
                     (NOT a cumulative running sum — that was the bug called out
                      in step 12)
    """
    messages: list[Message] = field(default_factory=list)
    system_prompt: str | None = None
    context_window: int = 200_000
    current_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # ---- message handling ----

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def to_api_messages(self) -> list[dict[str, Any]]:
        """Messages in the wire format (system is sent separately for Anthropic)."""
        return [m.to_dict() for m in self.messages if m.role != "system"]

    def clear(self) -> None:
        """Wipe history. Tools live in the registry, so nothing else to reset."""
        self.messages.clear()
        self.current_tokens = 0

    # ---- token accounting ----

    @property
    def usage_ratio(self) -> float:
        if not self.context_window:
            return 0.0
        return self.current_tokens / self.context_window

    def usage_label(self) -> str:
        """Colour band for the status line: grey <70%, yellow 70-84%, red 85%+."""
        pct = self.usage_ratio
        if pct >= 0.85:
            return "red"
        if pct >= 0.70:
            return "yellow"
        return "grey"

    def compact_messages(self, keep_min: int = 2, drop_ratio: float = 0.40) -> int:
        """Drop the oldest ~40% of messages, always keeping at least `keep_min`.

        Returns how many were dropped.
        """
        total = len(self.messages)
        if total <= keep_min:
            return 0
        drop_count = int(total * drop_ratio)
        drop_count = min(drop_count, total - keep_min)
        if drop_count <= 0:
            return 0
        del self.messages[:drop_count]
        return drop_count

    def __repr__(self) -> str:
        return (
            f"<Context messages={len(self.messages)} "
            f"tokens={self.current_tokens}/{self.context_window} "
            f"({self.usage_ratio:.0%})>"
        )


if __name__ == "__main__":
    # Smoke test
    t = Tool(
        name="mud_look",
        description="Look at the current room",
        input_schema={"type": "object", "properties": {}},
        handler=lambda: "You are in a bakery.",
    )
    print("tool schema:", t.to_schema())

    ctx = Context(context_window=200_000)
    ctx.add(Message.user("find the bakery"))
    ctx.add(Message.assistant("Looking around..."))
    ctx.current_tokens = 150_000
    print(ctx, "->", ctx.usage_label())

    for i in range(10):
        ctx.add(Message.user(f"msg {i}"))
    print("before compact:", len(ctx.messages))
    dropped = ctx.compact_messages()
    print(f"dropped {dropped}, after compact:", len(ctx.messages))