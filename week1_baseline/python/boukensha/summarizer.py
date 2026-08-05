"""
Summarizer — bounds context growth on long tasks.

Perception compression flattened the per-room cost, but on long tasks context
still grows without bound because history never leaves the window (a 100-iter
grind reached ~16k tokens). This collapses OLD history into one compact state
note via a single model call, keeping the RECENT messages verbatim.

    before:  [m1][m2]...[m64][m65][m66]   (~16k tokens)
    after:   [STATE SUMMARY of m1-63][m64][m65][m66]   (~2k tokens)

Result: instead of a rising ramp, the token curve becomes a sawtooth — it grows,
gets summarized back down, grows again. Bounded.

This is a FUNCTION (one model call), not an agent — no loop, no tools.
"""

from __future__ import annotations

from structs import Context, Message


SUMMARY_PROMPT = """You are compacting an AI agent's memory of a MUD (text adventure) session.
Summarize the conversation so far into a compact STATE NOTE the agent can use to
continue its task. Preserve only what's needed to keep going:

- Current location and the route/key rooms discovered
- Character state: level, exp, gold, HP, notable equipment held/worn
- Progress toward the current goal (what's done, what remains)
- Useful discoveries: commands that worked, locations of interest, dangers/mobs

Drop: room prose, redundant exploration, blow-by-blow combat, dead ends.
Write terse factual state, not narrative. Under 150 words. Start with "STATE:".
"""


class Summarizer:
    def __init__(
        self,
        backend,
        keep_recent: int = 4,
        trigger_ratio: float = 0.5,
        on_event=None,
    ):
        self.backend = backend
        self.keep_recent = keep_recent
        self.trigger_ratio = trigger_ratio
        self.on_event = on_event or (lambda name, data: None)

    def should_summarize(self, context: Context) -> bool:
        """Summarize once usage crosses the ratio and there's enough old history."""
        if context.usage_ratio < self.trigger_ratio:
            return False
        return len(context.messages) > self.keep_recent + 2

    def summarize(self, context: Context) -> None:
        """Collapse old messages into a single state-summary message, in place."""
        # Split: everything except the most recent `keep_recent` gets summarized.
        split = len(context.messages) - self.keep_recent
        old = context.messages[:split]
        recent = context.messages[split:]

        # Don't split a tool_use from its matching tool_result: if the first
        # "recent" message is a tool_result (user role with tool_result blocks),
        # pull one more message back into `old` so the pairing stays intact.
        recent = self._fix_tool_boundary(old, recent)

        # Build a transcript of the old messages for the summarizer to read.
        transcript = self._render(old)

        # One model call to produce the summary.
        summary_text = self._call_summarizer(transcript)

        # Replace old messages with the single summary; keep recent verbatim.
        summary_msg = Message.user(f"[MEMORY] {summary_text}")
        context.messages = [summary_msg] + recent

        # Usage will be recomputed from the next real API response; reset the
        # stale figure so we don't immediately re-trigger.
        context.current_tokens = 0

        self.on_event("summarization", {
            "summarized": len(old),
            "kept": len(recent),
            "summary_chars": len(summary_text),
        })

    # ---- internals ----

    def _fix_tool_boundary(self, old, recent):
        """Ensure `recent` doesn't start mid tool_use/tool_result pair."""
        if not recent:
            return recent
        first = recent[0]
        # A tool_result message is a user message whose content is a list with
        # tool_result blocks. If recent starts with one, its matching tool_use
        # is in `old` — move the boundary so we don't orphan it.
        content = first.content
        if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        ):
            if old:
                recent = [old[-1]] + recent
                del old[-1]
        return recent

    @staticmethod
    def _render(messages) -> str:
        lines = []
        for m in messages:
            role = m.role
            content = m.content
            if isinstance(content, str):
                lines.append(f"{role}: {content}")
            else:
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    t = b.get("type")
                    if t == "text":
                        lines.append(f"{role}: {b.get('text','')}")
                    elif t == "tool_use":
                        lines.append(f"{role}: [called {b.get('name')} {b.get('input')}]")
                    elif t == "tool_result":
                        lines.append(f"{role}: [result: {str(b.get('content',''))[:300]}]")
        return "\n".join(lines)

    def _call_summarizer(self, transcript: str) -> str:
        """One model call. Reuses the same backend but with a fresh, tiny context."""
        ctx = Context(system_prompt=SUMMARY_PROMPT)
        ctx.add(Message.user(
            "Here is the session so far. Produce the STATE note.\n\n" + transcript
        ))
        result = self.backend.call(ctx, tools=[])
        parts = [b["text"] for b in result["content"] if b.get("type") == "text"]
        return "\n".join(parts).strip()


if __name__ == "__main__":
    # Offline test with a fake backend — verifies split/boundary/replacement
    # logic without a live API call.
    from structs import Context, Message

    class FakeBackend:
        def call(self, context, tools):
            return {"stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "STATE: level 2, in newbie zone, 2890 exp, geared with sword+shield, grinding toward level 3."}],
                    "usage": {"input_tokens": 500, "output_tokens": 40}}
        def estimate_cost(self, u): return 0.0

    ctx = Context(context_window=1000)
    for i in range(20):
        ctx.add(Message.user(f"explored room {i}"))
        ctx.add(Message.assistant(f"moved to room {i}"))
    ctx.current_tokens = 600   # 60% -> over trigger

    s = Summarizer(FakeBackend(), keep_recent=4, trigger_ratio=0.5,
                   on_event=lambda n, d: print(f"[{n}] {d}"))
    print("before:", len(ctx.messages), "messages")
    print("should_summarize:", s.should_summarize(ctx))
    s.summarize(ctx)
    print("after:", len(ctx.messages), "messages")
    print("first message:", ctx.messages[0].content[:80])
    print("kept recent:", [m.content for m in ctx.messages[1:]])