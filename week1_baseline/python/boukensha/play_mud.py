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
from summarizer import Summarizer

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

Movement costs movement points (V). If you see 'too exhausted', rest or sleep and WAIT several turns (rest multiple times without standing) until your movement points recover before trying to move again.

DANGER — DEATH TRAPS:
Some rooms are instant-death traps. If a room description mentions an "Abyss",
falling, "descending", "Good-bye cruel world", or shows "[ Exits: None! ]", DO NOT
proceed and do not move further in. If you somehow enter one, you are likely stuck.
Never move in a direction if the destination sounds lethal.

OPPORTUNISTIC LOOTING (do this during ANY task, without being told):
As you move through rooms, grab useful items you come across if you have space:
- ALWAYS pick up gold/coins ('get coins' or 'get all coins') — they stack and are always useful.
- Pick up weapons and armor that are upgrades, ESPECIALLY items with a "glowing aura"
  (these are magical/valuable). Wield better weapons ('wield <item>') and wear better
  armor ('wear <item>').
- Skip junk, duplicates you already have, and stop if you see "you can't carry that many
  items" (inventory is full).
- Grab-and-go: don't let looting derail your main objective, but don't walk past free value.
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

    summarizer = Summarizer(backend, keep_recent=4, trigger_ratio=0.02, on_event=fan_out)

    agent = Agent(
        backend=backend,
        registry=registry,
        context=context,
        summarizer=summarizer,
        max_iterations=100,
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