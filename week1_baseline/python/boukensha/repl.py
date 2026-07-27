"""
Step 8 — The REPL Loop

An interactive session that stays alive across turns. Reads user input, runs the
agent, prints the reply, loops back. A single Context is shared across all turns,
so the agent sees the full conversation history and remembers what it has seen
and done.

Built-in commands:
  /help            show commands
  /clear           wipe history (keep tools)
  /quiet /loud     toggle the per-event console logging
  /exit /quit      leave

    boukensha.repl(system="You play a MUD", tools_setup=fn)
"""

from __future__ import annotations

from typing import Callable

from config import Config
from structs import Context
from registry import ToolRegistry
from backends import build_backend
from agent import Agent, LoopError
from logger import Logger
from models import Models

VERSION = "0.1.0"


class Repl:
    """Interactive session. One shared Context, one Agent, many turns."""

    def __init__(
        self,
        *,
        config: Config | None = None,
        system: str | None = None,
        max_iterations: int = 10,
        max_turn_tokens: int | None = None,
    ):
        self.config = config or Config()
        self.registry = ToolRegistry()
        self.logger = Logger(self.config.sessions_dir)
        self.system = system

        model = self.config.get("model", "claude-haiku-4-5")
        self.context = Context(
            system_prompt=system,
            context_window=self.config.get(
                "context_window", Models.context_window(model)
            ),
        )
        self.backend = build_backend(self.config)
        self.agent = Agent(
            backend=self.backend,
            registry=self.registry,
            context=self.context,
            max_iterations=max_iterations,
            max_turn_tokens=max_turn_tokens,
            on_event=self.logger.on_event,
        )

    # ---- tool registration (call before .start()) ----

    def tool(self, name, description="", input_schema=None):
        return self.registry.tool(name, description, input_schema)

    # ---- the loop ----

    def start(self) -> None:
        self._banner()
        while True:
            try:
                line = input("\n\033[36myou>\033[0m ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye.")
                return

            if not line:
                continue

            # Slash commands are handled locally, never sent to the model.
            if line.startswith("/"):
                if self._handle_command(line):
                    return          # command asked us to exit
                continue

            # Otherwise it's a turn for the agent.
            try:
                reply = self.agent.run_turn(line)
                print(f"\n\033[32magent>\033[0m {reply}")
            except LoopError as e:
                print(f"\n\033[31m[loop error]\033[0m {e}")

    # ---- commands ----

    def _handle_command(self, line: str) -> bool:
        """Return True if the REPL should exit."""
        cmd = line.split()[0].lower()

        if cmd in ("/exit", "/quit"):
            print("bye.")
            return True
        elif cmd == "/help":
            self._help()
        elif cmd == "/clear":
            self.context.clear()
            print("[history cleared, tools kept]")
        elif cmd == "/compact":
            dropped = self.context.compact_messages()
            print(f"[compacted: dropped {dropped} messages]")
        elif cmd == "/quiet":
            self.logger.console = False
            print("[event logging off]")
        elif cmd == "/loud":
            self.logger.console = True
            print("[event logging on]")
        else:
            print(f"[unknown command: {cmd}] — try /help")
        return False

    # ---- display ----

    def _banner(self) -> None:
        model = self.config.get("model", "?")
        print(f"boukensha v{VERSION} · {model} · {len(self.registry)} tools")
        print("type a message, or /help for commands.")

    def _help(self) -> None:
        print(
            "commands:\n"
            "  /help          this message\n"
            "  /clear         wipe conversation history (keep tools)\n"
            "  /compact       drop oldest ~40% of messages now\n"
            "  /quiet /loud   toggle per-event logging\n"
            "  /exit /quit    leave"
        )


def repl(*, tools_setup: Callable[[Repl], None] | None = None, **kwargs) -> Repl:
    """Build a REPL, optionally register tools via a setup callback, and start it.

        def setup(r):
            @r.tool("look", "look around")
            def look(): ...
        boukensha.repl(system="You play a MUD", tools_setup=setup)
    """
    r = Repl(**kwargs)
    if tools_setup:
        tools_setup(r)
    r.start()
    return r


if __name__ == "__main__":
    # Interactive bakery demo. Try:
    #   you> look around
    #   you> take the danish
    #   you> what did I just do?      (it remembers — shared context)
    #   /exit
    _room = {"name": "The Bakery", "exits": ["s"], "items": ["danish", "a loaf of bread"]}

    def setup(r: Repl):
        @r.tool("look", "Look at the current room")
        def look():
            return (
                f"{_room['name']}. Exits: {', '.join(_room['exits'])}. "
                f"You see: {', '.join(_room['items'])}."
            )

        @r.tool("take", "Take an item from the room")
        def take(item: str):
            if item in _room["items"]:
                _room["items"].remove(item)
                return f"You take {item}."
            return f"There is no {item} here."

    repl(
        system="You are playing a text adventure. Use tools to explore and act. "
               "Be concise.",
        max_iterations=6,
        tools_setup=setup,
    )