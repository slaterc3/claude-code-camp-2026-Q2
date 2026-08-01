"""
MUD tools — generic command + discovery, now with PERCEPTION COMPRESSION.

look / move return compact room facts (name | exits | entities) instead of the
full prose, cutting per-room context cost by ~50-90%. look_detail returns the
full raw description when the agent explicitly needs it.
"""

from __future__ import annotations

from registry import ToolRegistry
from mud_client import MudClient
from perception import compress_room


def register_mud_tools(registry: ToolRegistry, mud: MudClient) -> None:

    @registry.tool(
        "command",
        "Send any raw command to the MUD (e.g. 'drink from fountain', 'eat bread', "
        "'rent', 'buy sword'). MUD grammar is picky — some actions need a "
        "preposition ('drink from fountain'). If a command fails, try variations.",
    )
    def command(text: str):
        return mud.send(text)

    @registry.tool(
        "help",
        "Look up a command/topic in the MUD help. Tries variations (e.g. 'drink' -> 'drinking').",
    )
    def help(topic: str):
        t = topic.strip()
        resp = mud.send(f"help {t}")
        if "no help on that word" in resp.lower():
            variations = []
            if not t.endswith("ing"):
                base = t[:-1] if t.endswith("e") else t
                variations.append(base + "ing")
            if t.endswith("ing"):
                variations.append(t[:-3])
            variations.append(t + "s")
            for v in variations:
                alt = mud.send(f"help {v}")
                if "no help on that word" not in alt.lower():
                    return f"(no help for '{t}', showing '{v}')\n{alt}"
            return f"No help for '{t}' or variations. Try the command directly."
        return resp

    @registry.tool("list_commands", "List all valid commands available in the game.")
    def list_commands():
        return mud.send("commands")

    # ---- perception: COMPRESSED by default ----

    @registry.tool(
        "look",
        "Look at the current room. Returns compact facts: name, exits, and any "
        "creatures/items present. Use look_detail if you need the full description.",
    )
    def look():
        return compress_room(mud.send("look"))

    @registry.tool(
        "look_detail",
        "Look at the current room and get the FULL descriptive text. Use this only "
        "when you need details the compact view omits (clues, sign text, etc.).",
    )
    def look_detail():
        return mud.send("look")

    @registry.tool("exits", "List the obvious exits from the current room and where they lead.")
    def exits():
        return mud.send("exits")

    @registry.tool(
        "move",
        "Move in a direction: north, south, east, west, up, or down. Returns "
        "compact facts about the room you arrive in.",
    )
    def move(direction: str):
        d = direction.strip().lower()
        short = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
        d = short.get(d, d)
        if d not in {"north", "south", "east", "west", "up", "down"}:
            return f"Invalid direction: {direction!r}. Use north/south/east/west/up/down."
        return compress_room(mud.send(d))

    @registry.tool("consider", "Assess how tough a creature is BEFORE fighting it.")
    def consider(target: str):
        return mud.send(f"consider {target}")