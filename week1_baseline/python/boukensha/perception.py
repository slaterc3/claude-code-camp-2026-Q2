"""
Perception — compress raw MUD room text into structured facts.

Strips descriptive prose and prompt lines, keeping room name, exits, and any
entities (NPCs/items) present. Full prose stays available via a detail tool.
"""

from __future__ import annotations

import re

# The MUD prompt line: "36H 100M 57V (news) (motd) >"
_PROMPT = re.compile(r"^\s*\d+H\s+\d+M\s+\d+V.*>\s*$", re.M)
# The exits line: "[ Exits: n e s w ]"
_EXITS = re.compile(r"\[\s*Exits:\s*([^\]]*)\]", re.I)

# An entity/item line: after the exits line, a line describing something present.
# We keep the WHOLE line (minus trailing period) as the entity — it carries
# tactical flavor (sleeping/standing/glowing) we don't want to lose.
# We just need to recognise which lines ARE entities vs stray text.
_ENTITY_SIGNALS = re.compile(
    r"\b(is here|lying here|standing here|is standing|is lying|is walking|"
    r"walking around|is sitting|is resting|is sleeping|is flying|"
    r"guarding|ready to|waiting to|behind the counter|corpse of)\b",
    re.I,
)


def compress_room(raw: str) -> str:
    """Turn a raw room response into a compact one-line summary of facts."""
    text = _PROMPT.sub("", raw)            # drop prompt lines
    lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        return raw.strip()

    # 1) Room name = first line.
    name = lines[0].strip()

    # 2) Exits from the [ Exits: ... ] line.
    exits = ""
    m = _EXITS.search(raw)
    if m:
        dirs = [d.strip("()") for d in m.group(1).split()]
        exits = ",".join(d for d in dirs if d)

    # 3) Entities = lines AFTER the exits line that carry an "is here"-type signal.
    #    Keep the full line (trimmed) — don't try to extract a sub-group.
    entities = []
    seen_exits = False
    for ln in lines:
        s = ln.strip()
        if _EXITS.search(s):
            seen_exits = True
            continue
        if not seen_exits:
            continue                       # still in the description block
        if _ENTITY_SIGNALS.search(s):
            entities.append(s.rstrip("."))

    parts = [name]
    if exits:
        parts.append(f"exits: {exits}")
    if entities:
        parts.append("here: " + "; ".join(entities))
    return " | ".join(parts)


if __name__ == "__main__":
    samples = [
        """Main Street
   You are on the main street crossing through town.  To the north is the
general store, and the main street continues east.
[ Exits: n e s w ]
36H 100M 58V (news) (motd) > """,
        """The Pet Shop
   The Pet Shop is a small crowded store, full of cages and animals.
[ Exits: n ]
There is a Pet Shop Boy standing here cuddling something furry in his hands.
36H 100M 57V (news) (motd) > """,
        """Ye Olde Water Shoppe
   You are standing in the center of a small wooden shop.
[ Exits: n ]
An oozing green gelatinous blob is here, sucking in bits of debris.
Wally the Watermaster is standing behind the counter.
36H 100M 58V (news) (motd) > """,
        """The Beginning Of The Passage
   You find yourself entering a long corridor.
[ Exits: e s ]
The corpse of the newbie monster is lying here.
A handful of gold coins is lying here.
A shiny newbie dagger is lying here looking for a back to stab.
11H 100M 83V (news) (motd) > """,
        """The Post Office
   You are in the central post office for Midgaard.
There is a sign posted on the wall here.
[ Exits: s ]
A Peacekeeper is standing here, ready to jump in at the first sign of trouble.
The head postmaster is standing here, waiting to help you with your mail.
36H 100M 53V (news) (motd) > """,
        """The Entrance To The Clerics' Guild
   The entrance hall is a small modest room.
[ Exits: n e ]
An automatic teller machine has been installed in the wall here.
An odif yltsaeb is here, walking backwards.
A knight templar is guarding the entrance.
36H 100M 50V (news) (motd) > """,
    ]
    for s in samples:
        rw = len(s.split()); comp = compress_room(s); cw = len(comp.split())
        print(f"[{rw}->{cw} words]  {comp}")