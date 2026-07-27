"""
Step 2 — The Tool Registry

Owns the table of available tools and dispatches a model's tool call to the
right handler. This is where tools live — NOT in Context.

Usage:

    registry = ToolRegistry()

    @registry.tool("mud_look", "Look at the current room")
    def mud_look():
        return "You are in a bakery."

    registry.dispatch("mud_look", {})        # -> "You are in a bakery."
    registry.to_schemas()                    # -> [ {...}, ... ] for the API payload
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

from structs import Tool


class ToolError(Exception):
    """Raised when a tool is missing or fails during dispatch."""


class ToolRegistry:
    """A data table of tools plus dispatch."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    # ---- registration ----

    def register(self, tool: Tool) -> Tool:
        """Register a fully-built Tool. Collisions raise rather than clobber."""
        if tool.name in self._tools:
            raise ToolError(f"tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool
        return tool

    def tool(
        self,
        name: str,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> Callable:
        """Decorator form: register a function as a tool.

        If no input_schema is given, one is inferred from the function signature.
        """
        def decorator(fn: Callable) -> Callable:
            schema = input_schema or self._infer_schema(fn)
            self.register(Tool(
                name=name,
                description=description or (fn.__doc__ or "").strip(),
                input_schema=schema,
                handler=fn,
            ))
            return fn
        return decorator

    def register_many(self, tools: list[Tool], prefix: str | None = None) -> None:
        """Bulk-register (used by the MCP layer in step 10).

        `prefix` namespaces tool names client-side so two servers can't collide.
        """
        for t in tools:
            if prefix:
                t = Tool(
                    name=f"{prefix}{t.name}",
                    description=t.description,
                    input_schema=t.input_schema,
                    handler=t.handler,
                )
            self.register(t)

    # ---- lookup ----

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"unknown tool {name!r}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return list(self._tools)

    def to_schemas(self) -> list[dict[str, Any]]:
        """All tool schemas, for the provider's `tools` array."""
        return [t.to_schema() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    # ---- dispatch ----

    def dispatch(self, name: str, args: dict[str, Any] | None = None) -> Any:
        """Call a registered tool with the model-supplied arguments."""
        tool = self.get(name)
        if tool.handler is None:
            raise ToolError(f"tool {name!r} has no handler")
        args = args or {}
        try:
            return tool.handler(**args)
        except TypeError as e:
            raise ToolError(f"bad arguments for {name!r}: {e}") from e
        except Exception as e:
            # Tool failures shouldn't kill the loop — the agent should see the
            # error as a tool_result and decide what to do.
            raise ToolError(f"tool {name!r} failed: {e}") from e

    # ---- internals ----

    @staticmethod
    def _infer_schema(fn: Callable) -> dict[str, Any]:
        """Build a minimal JSON Schema from the function signature."""
        sig = inspect.signature(fn)
        props: dict[str, Any] = {}
        required: list[str] = []
        type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}

        for pname, param in sig.parameters.items():
            ptype = type_map.get(param.annotation, "string")
            props[pname] = {"type": ptype}
            if param.default is inspect.Parameter.empty:
                required.append(pname)

        schema: dict[str, Any] = {"type": "object", "properties": props}
        if required:
            schema["required"] = required
        return schema

    def __repr__(self) -> str:
        return f"<ToolRegistry {len(self._tools)} tools: {', '.join(self._tools)}>"


if __name__ == "__main__":
    reg = ToolRegistry()

    @reg.tool("mud_look", "Look at the current room")
    def mud_look():
        return "The Bakery. Exits: s"

    @reg.tool("mud_move", "Move in a direction")
    def mud_move(direction: str):
        return f"You walk {direction}."

    print(reg)
    print("schemas:", reg.to_schemas())
    print("dispatch look:", reg.dispatch("mud_look"))
    print("dispatch move:", reg.dispatch("mud_move", {"direction": "north"}))

    # error paths
    for bad in [lambda: reg.dispatch("nope"), lambda: reg.dispatch("mud_move", {"wrong": 1})]:
        try:
            bad()
        except ToolError as e:
            print("caught:", e)
