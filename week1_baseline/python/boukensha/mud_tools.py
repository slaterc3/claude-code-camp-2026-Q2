"""
MUD tools — a generic command interface plus discovery, so the agent isn't
limited to a hardcoded verb list. It can send any MUD command and look up how
commands work from the game's own help system.
"""

from __future__ import annotations

from registry import ToolRegistry
from mud_client import MudClient


def register_mud_tools(registry: ToolRegistry, mud: MudClient) -> None:

    # ---- the generic escape hatch: send anything ----

    @registry.tool(
        "command",
        "Send any raw command to the MUD and get the game's response. Use this "
        "for any action not covered by a specific tool (e.g. 'drink from fountain', "
        "'eat bread', 'rest', 'wear armor', 'buy sword'). MUD grammar is picky — "
        "some actions need a preposition ('drink from fountain', 'get sword from bag'). "
        "If a command fails, try variations before giving up.",
    )
    def command(text: str):
        return mud.send(text)

    # ---- discovery ----

    @registry.tool(
        "help",
        "Look up a command or topic in the MUD's help system. Automatically tries "
        "variations (e.g. 'drink' -> 'drinking') if the exact topic isn't found.",
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

    @registry.tool(
        "list_commands",
        "List all valid commands available in the game.",
    )
    def list_commands():
        return mud.send("commands")

    # ---- convenience wrappers for high-frequency actions ----

    @registry.tool("look", "Look at the current room: description, exits, items, creatures.")
    def look():
        return mud.send("look")

    @registry.tool("exits", "List the obvious exits from the current room and where they lead.")
    def exits():
        return mud.send("exits")

    @registry.tool("move", "Move in a direction: north, south, east, west, up, or down.")
    def move(direction: str):
        d = direction.strip().lower()
        short = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
        d = short.get(d, d)
        if d not in {"north", "south", "east", "west", "up", "down"}:
            return f"Invalid direction: {direction!r}. Use north/south/east/west/up/down."
        return mud.send(d)

    @registry.tool("consider", "Assess how tough a creature is BEFORE fighting it.")
    def consider(target: str):
        return mud.send(f"consider {target}")


if __name__ == "__main__":
    mud = MudClient()
    print("logging in...")
    mud.login("dummy", "helloworld")
    reg = ToolRegistry()
    register_mud_tools(reg, mud)
    print("registered:", reg.names())

    print("\n--- command: south ---")
    print(reg.dispatch("command", {"text": "south"}))
    print("\n--- command: drink from fountain ---")
    print(reg.dispatch("command", {"text": "drink from fountain"}))

    mud.close()
    print("\n(closed)")