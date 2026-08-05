"""
Step 5 — The Agent Loop

Boukensha::Agent — the core agentic loop.

  call the API
    -> check stop_reason
    -> if tool_use: dispatch each tool call into the registry,
       append the results to the context
    -> repeat
  until stop_reason == "end_turn"  OR  max_iterations is hit.

The Agent never knows which provider it's talking to — the backend already
normalized the response to {stop_reason, content, usage}.
"""

from __future__ import annotations

from structs import Context, Message
from registry import ToolRegistry, ToolError
from backends import Backend, ApiError


class LoopError(Exception):
    """Raised when the loop hits a limit or an unrecoverable state."""


class Agent:
    def __init__(
        self,
        backend: Backend,
        registry: ToolRegistry,
        context: Context,
        max_iterations: int = 10,
        max_turn_tokens: int | None = None,
        compaction_threshold: float = 0.85,
        summarizer=None,
        on_event=None,
        wrapup_margin: int = 2,  
    ):
        self.backend = backend
        self.registry = registry
        self.context = context
        self.max_iterations = max_iterations
        self.max_turn_tokens = max_turn_tokens
        self.compaction_threshold = compaction_threshold
        self.summarizer = summarizer
        # on_event(name, data) — optional hook so the logger/TUI can observe.
        self.on_event = on_event or (lambda name, data: None)
        self.wrapup_margin = wrapup_margin

    def run_turn(self, user_input: str) -> str:
        """Run one user turn to completion (through any number of tool calls)."""
        self.context.add(Message.user(user_input))

        turn_tokens = 0

        for iteration in range(1, self.max_iterations + 1):
            self.on_event("iteration", {"n": iteration})

            # Bound context growth: summarize old history if it's gotten large.
            # Checked each iteration so it fires as context grows during the turn.
            if self.summarizer and self.summarizer.should_summarize(self.context):
                self.summarizer.summarize(self.context)
            else:
                self._maybe_compact()

            remaining = self.max_iterations - iteration
            if 0 < remaining <= self.wrapup_margin:
                self.context.add(Message.user(
                    f"[SYSTEM] You have {remaining} iteration(s) left before you "
                    f"must stop. Finish your current objective if you can, then "
                    f"report your status and stop. Your progress and equipment are "
                    f"saved automatically when the session ends."
                ))

            # 1. Call the API.
            try:
                result = self.backend.call(
                    self.context,
                    self.registry.to_schemas(),
                )
            except ApiError as e:
                raise LoopError(f"API call failed on iteration {iteration}: {e}") from e

            # Token accounting.
            usage = result["usage"]
            self.context.current_tokens = (
                usage["input_tokens"] + usage["output_tokens"]
            )
            turn_tokens += usage["input_tokens"] + usage["output_tokens"]
            self.on_event("response", {
                "stop_reason": result["stop_reason"],
                "usage": usage,
                "model": result.get("model"),
                "cost": self.backend.estimate_cost(usage),
            })

            # 2. Record the assistant's message.
            self.context.add(Message.assistant(result["content"]))

            # 3. Branch on stop_reason.
            stop = result["stop_reason"]

            if stop == "tool_use":
                tool_results = self._dispatch_tools(result["content"])
                self.context.add(Message.user(tool_results))
            elif stop in ("end_turn", "stop_sequence", "max_tokens"):
                return self._extract_text(result["content"])
            else:
                raise LoopError(f"unexpected stop_reason: {stop!r}")

            if self.max_turn_tokens and turn_tokens >= self.max_turn_tokens:
                raise LoopError(
                    f"turn exceeded max_turn_tokens ({turn_tokens} >= {self.max_turn_tokens})"
                )

        raise LoopError(f"hit max_iterations ({self.max_iterations}) without end_turn")

    # ---- internals ----

    def _maybe_compact(self) -> None:
        """Drop the oldest messages if usage has crossed the threshold."""
        if self.context.usage_ratio < self.compaction_threshold:
            return
        dropped = self.context.compact_messages()
        if dropped:
            self.on_event("compaction", {
                "dropped": dropped,
                "remaining": len(self.context.messages),
            })

    def _dispatch_tools(self, content: list[dict]) -> list[dict]:
        """Run every tool_use block the model emitted, return tool_result blocks."""
        results = []
        for block in content:
            if block.get("type") != "tool_use":
                continue
            name = block["name"]
            args = block.get("input", {})
            self.on_event("tool_call", {"name": name, "input": args})

            try:
                output = self.registry.dispatch(name, args)
                is_error = False
            except ToolError as e:
                # Don't crash — hand the error back so the model can adapt.
                output = f"Error: {e}"
                is_error = True

            self.on_event("tool_result", {"name": name, "output": output, "error": is_error})
            results.append({
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": str(output),
                "is_error": is_error,
            })
        return results

    @staticmethod
    def _extract_text(content: list[dict]) -> str:
        """Pull the text blocks out of a normalized content list."""
        parts = [b["text"] for b in content if b.get("type") == "text"]
        return "\n".join(parts).strip()


if __name__ == "__main__":
    # End-to-end test against the live API with a couple of fake tools.
    from config import Config

    cfg = Config()
    from backends import build_backend

    backend = build_backend(cfg)
    registry = ToolRegistry()

    # A tiny fake "MUD" so the agent has something to call.
    _room = {"name": "The Bakery", "exits": ["s"], "items": ["a fresh danish"]}

    @registry.tool("look", "Look at the current room and see exits and items")
    def look():
        return f"{_room['name']}. Exits: {', '.join(_room['exits'])}. You see: {', '.join(_room['items'])}."

    @registry.tool("take", "Take an item from the room")
    def take(item: str):
        if item in _room["items"]:
            _room["items"].remove(item)
            return f"You take {item}."
        return f"There is no {item} here."

    ctx = Context(
        system_prompt=(
            "You are playing a text adventure. Use the available tools to "
            "explore and act. When you have completed the user's request, "
            "stop and report what you did."
        ),
        context_window=200_000,
    )

    def log(name, data):
        print(f"  [{name}] {data}")

    agent = Agent(backend, registry, ctx, max_iterations=6, on_event=log)

    print(">>> user: look around, then take the danish")
    reply = agent.run_turn("Look around, then take the danish.")
    print("\n=== FINAL REPLY ===")
    print(reply)