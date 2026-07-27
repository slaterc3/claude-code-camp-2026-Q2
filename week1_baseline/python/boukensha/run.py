"""
Step 7 — The Run DSL

Everything up to now is separate classes you have to construct and wire together
by hand. That's a mess to use. This gives a single `run()` entry point plus a
small DSL so callers get an SDK-like surface:

    import boukensha

    with boukensha.run("Look around and take the danish") as b:
        @b.tool("look", "Look at the room")
        def look():
            return "The Bakery. Exits: s. You see: danish."

        @b.tool("take", "Take an item")
        def take(item: str):
            return f"You take {item}."

    print(b.reply)

Or the one-shot form:

    reply = boukensha.run("say hello")   # no tools, just talks

`RunDSL` is what `self` becomes inside the block. It exposes `tool()` so you can
register ad-hoc tools inline, keeping the main signature clean.
"""

from __future__ import annotations

from typing import Any, Callable

from config import Config
from structs import Context
from registry import ToolRegistry
from backends import build_backend
from agent import Agent
from logger import Logger
from models import Models


class RunDSL:
    """The object `self` becomes inside a `boukensha.run(...) as b` block.

    Collects inline tool registrations, then runs the agent on block exit.
    """

    def __init__(
        self,
        task: str,
        *,
        config: Config | None = None,
        system: str | None = None,
        max_iterations: int = 10,
        max_turn_tokens: int | None = None,
        console: bool = True,
    ):
        self.task = task
        self.config = config or Config()
        self.registry = ToolRegistry()
        self.logger = Logger(self.config.sessions_dir, console=console)
        self.system = system
        self.max_iterations = max_iterations
        self.max_turn_tokens = max_turn_tokens
        self.reply: str | None = None

    # ---- inline tool registration (the DSL surface) ----

    def tool(
        self,
        name: str,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> Callable:
        """Register an ad-hoc tool inline. Same decorator as the registry's."""
        return self.registry.tool(name, description, input_schema)

    # ---- execution ----

    def execute(self) -> str:
        """Build the agent from collected pieces and run the task."""
        backend = build_backend(self.config)

        # Context window comes from the model's capability table.
        model = self.config.get("model", "claude-haiku-4-5")
        context = Context(
            system_prompt=self.system,
            context_window=self.config.get(
                "context_window", Models.context_window(model)
            ),
        )

        agent = Agent(
            backend=backend,
            registry=self.registry,
            context=context,
            max_iterations=self.max_iterations,
            max_turn_tokens=self.max_turn_tokens,
            on_event=self.logger.on_event,
        )
        self.agent = agent
        self.context = context
        self.reply = agent.run_turn(self.task)
        return self.reply

    # ---- context-manager protocol (so `with run(...) as b:` works) ----

    def __enter__(self) -> "RunDSL":
        # Hand the DSL object to the block so tools can be registered.
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # If the block raised, don't swallow it — let it propagate.
        if exc_type is not None:
            return False
        # Block finished registering tools → now run.
        self.execute()
        return False


def run(task: str, **kwargs) -> RunDSL:
    """The single entry point.

    Two usage modes:

      # 1. With inline tools (context-manager form):
      with boukensha.run("do the thing") as b:
          @b.tool("look", "look around")
          def look(): ...
      print(b.reply)

      # 2. No tools (immediate form) — call .execute() yourself,
      #    or just use the `with` form which auto-executes on exit.
    """
    return RunDSL(task, **kwargs)


if __name__ == "__main__":
    # Demo: the full bakery task in DSL form. Compare this to the old
    # agent.py __main__ block — same behavior, a fraction of the wiring.
    _room = {"name": "The Bakery", "exits": ["s"], "items": ["danish"]}

    with run(
        "Look around, then take the danish.",
        system="You are playing a text adventure. Use tools to explore and act, "
               "then report what you did.",
        max_iterations=6,
    ) as b:

        @b.tool("look", "Look at the current room")
        def look():
            return (
                f"{_room['name']}. Exits: {', '.join(_room['exits'])}. "
                f"You see: {', '.join(_room['items'])}."
            )

        @b.tool("take", "Take an item from the room")
        def take(item: str):
            if item in _room["items"]:
                _room["items"].remove(item)
                return f"You take {item}."
            return f"There is no {item} here."

    print("\n=== FINAL REPLY ===")
    print(b.reply)