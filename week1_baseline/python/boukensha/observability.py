"""
Observability — OpenTelemetry/Logfire instrumentation for the agent.

Wraps the agent's work in spans so you get a trace tree in the Logfire dashboard:

    run_turn (task)
      └─ iteration 1
      │    ├─ api_call   (tokens, cost, latency, model)
      │    └─ tool: look (input, output, latency)
      └─ iteration 2
           └─ ...

Design: it plugs into the Agent's existing on_event hook, so instrumentation is
additive — your loop, logger, everything else keeps working unchanged.

Reads LOGFIRE_TOKEN from ~/.boukensha/.env via Config. If logfire isn't
installed or no token is present, it degrades gracefully to a no-op.
"""

from __future__ import annotations

from contextlib import contextmanager

try:
    import logfire
    _HAS_LOGFIRE = True
except ImportError:
    _HAS_LOGFIRE = False


class Observability:
    """Turns the agent's event stream into OTel spans via Logfire."""

    def __init__(self, config, service_name: str = "boukensha", console: bool = False):
        self.enabled = False
        self._span_stack = []      # nested spans (task -> iteration -> ...)
        self._iteration_span = None

        token = config.secret("LOGFIRE_TOKEN") if config else None
        if _HAS_LOGFIRE and token:
            logfire.configure(
                token=token,
                service_name=service_name,
                console=logfire.ConsoleOptions() if console else False,
            )
            self.enabled = True

    # ---- the top-level task span ----

    @contextmanager
    def task(self, goal: str):
        """Wrap a whole run_turn in a span. Use: `with obs.task(goal): ...`"""
        if not self.enabled:
            yield
            return
        with logfire.span("task", goal=goal) as span:
            self._task_span = span
            yield span

    # ---- the on_event hook the Agent calls ----

    def on_event(self, name: str, data: dict) -> None:
        if not self.enabled:
            return

        if name == "iteration":
            # Close any previous iteration span, open a new one.
            self._close_iteration()
            self._iteration_span = logfire.span("iteration", n=data.get("n"))
            self._iteration_span.__enter__()

        elif name == "response":
            usage = data.get("usage", {})
            logfire.info(
                "api_response",
                stop_reason=data.get("stop_reason"),
                model=data.get("model"),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cost=data.get("cost", 0.0),
            )

        elif name == "tool_call":
            logfire.info("tool_call", tool=data.get("name"), input=data.get("input"))

        elif name == "tool_result":
            out = str(data.get("output", ""))
            if len(out) > 500:
                out = out[:500] + "…"
            logfire.info(
                "tool_result",
                tool=data.get("name"),
                error=data.get("error", False),
                output=out,
            )

        elif name == "compaction":
            logfire.info("compaction", dropped=data.get("dropped"),
                         remaining=data.get("remaining"))

    def _close_iteration(self):
        if self._iteration_span is not None:
            self._iteration_span.__exit__(None, None, None)
            self._iteration_span = None

    def close(self):
        self._close_iteration()


if __name__ == "__main__":
    from config import Config
    cfg = Config()
    obs = Observability(cfg, console=True)
    print("logfire installed:", _HAS_LOGFIRE)
    print("observability enabled:", obs.enabled)
    if obs.enabled:
        with obs.task("smoke test"):
            obs.on_event("iteration", {"n": 1})
            obs.on_event("response", {
                "stop_reason": "end_turn", "model": "claude-haiku-4-5",
                "usage": {"input_tokens": 100, "output_tokens": 20}, "cost": 0.0005,
            })
            obs.on_event("tool_call", {"name": "look", "input": {}})
            obs.on_event("tool_result", {"name": "look", "output": "The Bakery", "error": False})
            obs.close()
        print("sent a test trace to Logfire — check your dashboard.")
    else:
        print("no LOGFIRE_TOKEN found or logfire not installed.")