# Week 1 - Baseline
### July 25, 2026 - C. Guy Slater

### Technical Goal(s)
- create a functional and self-sufficient *agent framework* w/o relying on 3rd-party SDKs
- ownership/understanding of the framework so that it can potentially be used (have value) beyond the Claude Code Camp 
- create the following interrelated components:
    - **config** - loads settings, secrets, and paths from `~/.boukensha/` directory 
    - **structs** - framework elements (`Tool`, `Message`, `Context`)
    - **tool registry** - registers/dispatches tool calls to the right handler
    - **prompt builder + API client** - builds the request the backend expects and formats responses (`{stop_reason, content}`)
    - **agent loop** - calls the API and checks `stop_reason`. Also dispatches tool calls, appends results, and repeats until `end_turn` or a limit is hit
    - **logger** - records session events, incl. tokens, costs, tool calls. Utilizes **<u>JSONL</u>**
    - **run DSL** - a single `run()` - connects all the pieces together
    - **REPL** - loop shares the context so the agent remembers across turns; includes session commands: `/clear`, `/compact`, `/exit`
    - **context management** - tracks token usage against the model's window and drops oldest messages (compaction). 

### Technical Uncertainty

- can I build a working agentic loop without 3rd-party framework/SDK?
- is coding-harness strictly necessary? In other words, is the loop simple enough to not require this?
- how much of the cost is repeatedly resending the context vs. the actual reasoning?
- can a cheap model like Haiku be enough to drive the loop accurately/reliably?

### Technical Hypotheses

##### **Note: These are presented as *null* hypotheses, not necessarily my expectation 

- A 3rd-party framework/SDK is required for the loop to obtain the necessary accuracy reliability
- Haiku is not a strong enough model for a functional loop (that can reliably and efficiently complete goal(s))
- Writing the agent framework Python (vs following the Ruby code) will result in technical debt or unforeseen problems

### Technical Observations

- the loop works end-to-end: agent reasoned, called tools, adapted, and stopped with end_turn
- tool errors fed back as tool_results
- multi-turn memory via shared Context confirmed and token count carried across turns (~812 on turn 2 vs ~50 if it hadn't)
- costs: multi-tool interactions ran ~$0.003 on Haiku; reasonable token accumulation on successive runs
- a Python success: urllib handled TLS transparently
- circuit breakers (max_iterations, max_turn_tokens) and auto-compaction (85% threshold, drop oldest ~40%) worked correctly
- JSONL logging captures tokens/cost/model info on each event
- tools live in the Registry, not Context

### Technical Conclusions

- 3rd party framework not required - loop is simple enough (150 lines of code)
- REST is workable and allows for increased transparency
- costs are more from recycled context than reasoning (logger makes this observation possible)
- a perception layer using regex/NLP extraction might reduce the clutter of verbose context
- Python is a viable means for creating the loop (so far...)

### Key Takeaways

- creating from scratch led to understanding *and* ownership
- costs are mostly from context verbosity, not reasoning. This is a workable challenge
