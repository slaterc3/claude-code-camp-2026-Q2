# Exploring Agent Architectures
### July 17, 2026 - C. Guy Slater

## Architecture #1 - Coding Harness with Markdown Memory

**Setup:** 

Claude Code serves as the coding-harness. An instruction file, `CLAUDE.md`, and two markdown files, `data/player.md` and `data/world.md`, that serve as memory.

Test goal: *"Find the bakery and list what is on the menu."* 
Connection to tbaMUD occurs on
`localhost:4000` as `dummy`. Model choice deliberately started small (Haiku 4.5) to test and then escalated to Sonnet model. Ideally, we can find a good balance between a small (inexpensive) model and one that can complete goals/tasks with efficiency.

**Food for thought** - It may be better to start with the larger, more capable model first to create a kind of benchmark before testing with smaller model. But for the purposes of this activity, it was helpful to see the limitations of the Haiku model before continuing with Sonnet.


### Observations

- **The agent created temporary connection scripts.** Rather than using a persistent
  session, it kept writing Python socket scripts (and some `echo | nc`
  bash). It re-generated this connection logic on
  nearly every attempt instead of reusing a stable interface.

- **Struggles with the MUD login flow.** The login sequence process is fixed,
  but the agent treated it as something to reason about each time. It either sent the password as a character name, or tried to confirm creating a *new* character before finally learning it had to select '1' to proceed.

- **It read unrelated repo files.** The agent inspected files like `CHALLENGES.md`
  that had nothing to do with actually playing MUD. This led to wasted time and tokens.

- **Model capability/size *did* affect task completion.**
  Haiku 4.5 handled mechanical steps (login, movement) but couldn't complete the task. More importantly, it **did not** write to the `world.md` or `player.md` files. 
  
  Switching to Sonnet completed the bakery
  task and produced useful `world.md` contributions, such as room description and route info. For example, here was the output from the preliminary task to *find the baker and list out the menu items*:
``` 
## The Bakery

You are standing inside the small bakery. A sweet scent of danish and fine
bread fills the room. The bread and Danish are arranged in fine order on the
shelves, and seem to be of the finest quality. A small sign is on the counter.
- Exits: s (Main Street west)
- NPC: The baker (shopkeeper)
- Path from starting Main Street: w (Market Square) -> w (Main Street west) -> n (Main Street west, again - two "west" moves needed) -> n (Bakery)
  Actual working route confirmed: from Main Street (start) -> w -> w -> n -> n -> Bakery
- Menu (via `list` command):
  | # | Item            | Cost |
  |---|-----------------|------|
  | 1 | A danish pastry | 7    |
  | 2 | A bread         | 14   |
  | 3 | A waybread      | 72   |
```
#### Additional (in-game) observations with Sonnet model

gave the Sonnet some instructions to find practice yard, practice kick, and then look for ways to make money-
- successfully found practice area and practiced kick
- found blob and attempted to fight, but i told it not to
- added instruction to use 'consider' command before fighting enemies
- noticed navigation was basically blind, considering all directions at once without recording movements
- Agent discovered town is peaceful/guarded; identified unarmed combat as a failure mode; hit the gold-vs-gear bootstrap problem.
    
**The Haiku agent had difficulty understanding its login mistakes.** 

It could not easily tell *why* a login failed and just kept reattempting (and failing)

### Cost Findings

A full session cost **$1.86**, and **>99.9% was Sonnet**. Haiku's portion was
only **$0.0006**. The dominant token consumption was *~3.5M cache-read
tokens* vs. only *~29.5k output tokens* of actual reasoning. 

Conclusion: 
most of the cost is coming from the context size of each loop, not from reasoning alone. Prompt caching is helpful, but optimization is needed.

### Technical Conclusion

A coding harness by itself is not the ideal solution for solving tasks/goals in MUD.

- **The fixed login flow (including connecting to MUD) should be handled by reusable code**. If the model is generating this every time it is very inefficient (and error prone). A deterministic solution is therefore recommended.

- **The MUD Manager** will be responsible for managing long-lived telnet sessions, handling the multi-step re-login, and exposing generic MUD command primitives (according to the README.md)
