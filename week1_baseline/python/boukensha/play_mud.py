"""
play_mud — your baseline agent playing the REAL tbaMUD.

Ties together:
  - MudClient (persistent socket session, logged in as dummy)
  - MUD tools (look, move, exits, consider, kill, ...)
  - your Agent loop, backend, logger, context

Give it a goal on the command line or edit TASK below.
"""

from __future__ import annotations

import sys

from config import Config
from structs import Context
from registry import ToolRegistry
from backends import build_backend
from agent import Agent, LoopError
from logger import Logger
from models import Models
from mud_client import MudClient
from mud_tools import register_mud_tools


SYSTEM_PROMPT = """You are playing tbaMUD, a text-based multiplayer dungeon (a CircleMUD variant).
You control a character named Dummy, a level 1 warrior, currently in Midgaard.

Use the available tools to perceive and act in the world:
- `look` to read the current room, `exits` to see where you can go.
- `move` to travel (north/south/east/west/up/down).
- `consider <target>` BEFORE fighting anything — never attack something that
  would beat you. `kill` to fight, `flee` if it goes badly.
- `get`, `inventory`, `examine`, `score` for items and status.

Play like a careful new player. Move ONE room at a time and read the result
before deciding your next move. When you have completed the user's goal, stop
and report what you did and what you observed.
"""


def main():
    task = " ".join(sys.argv[1:]) or "Look around, check your score, and describe where you are and what exits are available."

    cfg = Config()
    mud = MudClient()
    print("logging into the MUD as dummy...")
    mud.login("dummy", "helloworld")
    print("logged in.\n")

    registry = ToolRegistry()
    register_mud_tools(registry, mud)

    logger = Logger(cfg.sessions_dir)
    backend = build_backend(cfg)
    model = cfg.get("model", "claude-haiku-4-5")
    context = Context(
        system_prompt=SYSTEM_PROMPT,
        context_window=Models.context_window(model),
    )

    agent = Agent(
        backend=backend,
        registry=registry,
        context=context,
        max_iterations=15,
        on_event=logger.on_event,
    )

    print(f">>> GOAL: {task}\n")
    try:
        reply = agent.run_turn(task)
        print("\n=== AGENT REPORT ===")
        print(reply)
    except LoopError as e:
        print(f"\n[loop error] {e}")
    finally:
        mud.close()
        print("\n(disconnected)")


if __name__ == "__main__":
    main()