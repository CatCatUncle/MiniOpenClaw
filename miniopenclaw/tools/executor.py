"""Tool executor: validate -> run -> summarize."""

from __future__ import annotations

from typing import Any

from miniopenclaw.core.events import ToolCall
from miniopenclaw.tools.base import ToolError
from miniopenclaw.tools.registry import ToolRegistry


class ToolExecutor:
    """Executes registered tools with lightweight schema validation."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, name: str, args: dict[str, Any]) -> ToolCall:
        tool = self._registry.get(name)
        if tool is None:
            return ToolCall(name=name, args=args, error=f"Unknown tool: {name}")

        try:
            self._validate(args=args, schema=tool.json_schema)
            result = tool.execute(args)
            summary = self._summarize(result)
            return ToolCall(name=name, args=args, result=summary)
        except ToolError as exc:
            return ToolCall(name=name, args=args, error=str(exc))
        except Exception as exc:
            return ToolCall(name=name, args=args, error=f"Unexpected tool error: {exc}")

    @staticmethod
    def _validate(args: dict[str, Any], schema: dict[str, Any]) -> None:
        required = schema.get("required", [])
        for key in required:
            if key not in args:
                raise ToolError(f"Missing required argument: {key}")

        props = schema.get("properties", {})
        allow_extra = not schema.get("additionalProperties", True)
        if allow_extra:
            for key in args:
                if key not in props:
                    raise ToolError(f"Unexpected argument: {key}")

        for key, value in args.items():
            rules = props.get(key, {})
            typ = rules.get("type")
            if typ == "string" and not isinstance(value, str):
                raise ToolError(f"Argument '{key}' must be a string")
            if typ == "integer" and not isinstance(value, int):
                raise ToolError(f"Argument '{key}' must be an integer")
            if typ == "boolean" and not isinstance(value, bool):
                raise ToolError(f"Argument '{key}' must be a boolean")

            if isinstance(value, str):
                min_len = rules.get("minLength")
                max_len = rules.get("maxLength")
                if min_len is not None and len(value) < min_len:
                    raise ToolError(f"Argument '{key}' must have length >= {min_len}")
                if max_len is not None and len(value) > max_len:
                    raise ToolError(f"Argument '{key}' must have length <= {max_len}")
                enum = rules.get("enum")
                if enum and value not in enum:
                    raise ToolError(f"Argument '{key}' must be one of: {', '.join(enum)}")

            if isinstance(value, int):
                minimum = rules.get("minimum")
                maximum = rules.get("maximum")
                if minimum is not None and value < minimum:
                    raise ToolError(f"Argument '{key}' must be >= {minimum}")
                if maximum is not None and value > maximum:
                    raise ToolError(f"Argument '{key}' must be <= {maximum}")

    @staticmethod
    def _summarize(result: dict[str, Any]) -> str:
        if "summary" in result and isinstance(result["summary"], str):
            return result["summary"]
        return str(result)
