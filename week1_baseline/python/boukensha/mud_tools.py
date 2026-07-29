"""
MUD tools — wraps a live MudClient as tools the agent can call.

register_mud_tools(registry, mud) adds the core MUD actions to your existing
ToolRegistry, each one calling through to the persistent MUD session.
"""

from __future__ import annotations

from registry import ToolRegistry
from mud_client import MudClient


def register_mud_tools(registry: ToolRegistry, mud: MudClient) -> None:
    """Register the core MUD action tools against a live, logged-in MudClient."""

    @registry.tool("look", "Look at the current room to see its description, exits, items, and creatures.")
    def look():
        return mud.send("look")

    @registry.tool("exits", "List the obvious exits from the current room and where they lead.")
    def exits():
        return mud.send("exits")

    @registry.tool("move", "Move in a compass direction. One of: north, south, east, west, up, down.")
    def move(direction: str):
        d = direction.strip().lower()
        # accept short forms too
        short = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
        d = short.get(d, d)
        if d not in {"north", "south", "east", "west", "up", "down"}:
            return f"Invalid direction: {direction!r}. Use north/south/east/west/up/down."
        return mud.send(d)

    @registry.tool("score", "Check your character's stats: level, HP, mana, movement, gold, experience.")
    def score():
        return mud.send("score")

    @registry.tool("inventory", "See what you are carrying.")
    def inventory():
        return mud.send("inventory")

    @registry.tool("consider", "Assess how tough a target creature is before fighting it.")
    def consider(target: str):
        return mud.send(f"consider {target}")

    @registry.tool("examine", "Examine an object or creature closely.")
    def examine(target: str):
        return mud.send(f"examine {target}")

    @registry.tool("get", "Pick up an item. Use 'get all corpse' to loot a corpse.")
    def get(item: str):
        return mud.send(f"get {item}")

    @registry.tool("kill", "Attack a creature to start combat.")
    def kill(target: str):
        return mud.send(f"kill {target}")

    @registry.tool("flee", "Attempt to flee from combat in a random direction.")
    def flee():
        return mud.send("flee")

    @registry.tool("say", "Say something out loud in the current room.")
    def say(message: str):
        return mud.send(f"say {message}")


if __name__ == "__main__":
    # Quick check: log in, register tools, dispatch a couple directly.
    mud = MudClient()
    print("logging in...")
    mud.login("dummy", "helloworld")

    reg = ToolRegistry()
    register_mud_tools(reg, mud)
    print("registered tools:", reg.names())

    print("\n--- look ---")
    print(reg.dispatch("look"))
    print("\n--- exits ---")
    print(reg.dispatch("exits"))

    mud.close()
    print("\n(closed)")