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

from observability import Observability

SYSTEM_PROMPT = """You are playing tbaMUD, a text-based multiplayer dungeon (a CircleMUD variant).
You control a character named Dummy, a level 1 warrior, currently in Midgaard.

You have a generic `command` tool that sends ANY command to the game, plus
`help` and `list_commands` to discover what's possible. Use the specific tools
(look, exits, move, consider) for common actions.

IMPORTANT: If you don't know how to do something (e.g. drink, eat, wear, buy),
do NOT give up. Use `help <topic>` to learn the command, then use `command` to
do it. The game is self-documenting — look things up rather than assuming
something is impossible.

- `look` / `exits` to perceive; `move` one room at a time and read the result.
- `consider <target>` BEFORE fighting; never attack something that would win.
- When you complete the goal, stop and report what you did and observed.
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



    obs = Observability(cfg)

    def fan_out(name, data):
        logger.on_event(name, data)
        obs.on_event(name, data)    

    agent = Agent(
        backend=backend,
        registry=registry,
        context=context,
        max_iterations=15,
        on_event=fan_out,          # both logger AND observability get every event
    )

    # agent = Agent(
    #     backend=backend,
    #     registry=registry,
    #     context=context,
    #     max_iterations=50,
    #     on_event=logger.on_event,
    # )
    
    print(f">>> GOAL: {task}\n")
    with obs.task(task):           # top-level span for the whole task
        try:
            reply = agent.run_turn(task)
            print("\n=== AGENT REPORT ===")
            print(reply)
        except LoopError as e:
            print(f"\n[loop error] {e}")
        finally:
            obs.close()
            mud.close()
            print("\n(disconnected)")


if __name__ == "__main__":
    main()