"""
Step 6 — The Logger

Records a session's events to ~/.boukensha/sessions/<session_id>.jsonl and
optionally prints coloured output to the console.

Every event is one JSON line (JSONL) so it's append-only, streamable, and easy
for log_viz to read. Each event carries provider / model / cost / token counts
where relevant, for detailed reporting.

Design:
  - Logger.event(name, data) writes one JSONL line.
  - Logger.subscribe(fn) lets other components (a TUI, later) receive every
    event live, in addition to it hitting disk.
  - Logger.on_event is the callable you hand to Agent(on_event=...).
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# ANSI colours for the console. Kept tiny and stdlib-only.
_COLORS = {
    "grey": "\033[90m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "reset": "\033[0m",
}

# Which colour to print each event name in.
_EVENT_COLOR = {
    "iteration": "cyan",
    "response": "green",
    "tool_call": "yellow",
    "tool_result": "grey",
    "compaction": "red",
    "reasoning": "grey",
    "error": "red",
}


class Logger:
    def __init__(
        self,
        sessions_dir: str | Path,
        session_id: str | None = None,
        console: bool = True,
    ):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or self._new_session_id()
        self.path = self.sessions_dir / f"{self.session_id}.jsonl"
        self.console = console
        self._subscribers: list[Callable[[str, dict], None]] = []

    # ---- the hook you give to Agent(on_event=...) ----

    @property
    def on_event(self) -> Callable[[str, dict], None]:
        return self.event

    # ---- core ----

    def event(self, name: str, data: dict[str, Any]) -> None:
        """Record one event: write to disk, print to console, fan out to subscribers."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event": name,
            **data,
        }
        # 1. Persist as one JSONL line.
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")

        # 2. Console (coloured).
        if self.console:
            self._print(name, data)

        # 3. Fan out live (for a TUI, progress line, etc.).
        for fn in self._subscribers:
            fn(name, data)

    def subscribe(self, fn: Callable[[str, dict], None]) -> None:
        """Register a live listener that gets every event as it happens."""
        self._subscribers.append(fn)

    # ---- console formatting ----

    def _print(self, name: str, data: dict[str, Any]) -> None:
        color = _COLORS.get(_EVENT_COLOR.get(name, "grey"), "")
        reset = _COLORS["reset"]

        if name == "iteration":
            line = f"iteration {data.get('n')}"
        elif name == "response":
            usage = data.get("usage", {})
            cost = data.get("cost", 0.0)
            line = (
                f"response  stop={data.get('stop_reason')} "
                f"in={usage.get('input_tokens', 0)} "
                f"out={usage.get('output_tokens', 0)} "
                f"${cost:.6f}"
            )
        elif name == "tool_call":
            line = f"  → {data.get('name')}({data.get('input', {})})"
        elif name == "tool_result":
            out = str(data.get("output", ""))
            # if len(out) > 80:
            #     out = out[:77] + "..."

            mark = "✗" if data.get("error") else "✓"
            line = f"  {mark} {out}"
        elif name == "compaction":
            line = f"compacted: dropped {data.get('dropped')} messages"
        else:
            line = f"{name} {data}"

        print(f"{color}{line}{reset}")

    # ---- internals ----

    @staticmethod
    def _new_session_id() -> str:
        stamp = time.strftime("%Y%m%dT%H%M%S")
        short = uuid.uuid4().hex[:6]
        return f"{stamp}-{short}"

    def __repr__(self) -> str:
        return f"<Logger session={self.session_id} path={self.path}>"


if __name__ == "__main__":
    # Standalone smoke test: fire a few events and read the file back.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        log = Logger(tmp)
        print("session:", log.session_id)
        print("file:", log.path)
        print()

        log.event("iteration", {"n": 1})
        log.event("response", {
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 638, "output_tokens": 53},
            "model": "claude-haiku-4-5",
            "cost": 0.000903,
        })
        log.event("tool_call", {"name": "look", "input": {}})
        log.event("tool_result", {"name": "look", "output": "The Bakery. Exits: s.", "error": False})

        print("\n--- file contents ---")
        print(log.path.read_text())