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
