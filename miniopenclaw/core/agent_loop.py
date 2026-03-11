"""Agent loop contract and provider-backed implementation."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Protocol

from miniopenclaw.core.events import AgentResponse, AgentStatus, MessageEvent
from miniopenclaw.memory import MemoryStore
from miniopenclaw.providers.base import BaseProvider, ChatMessage
from miniopenclaw.providers.errors import ProviderError
from miniopenclaw.skills import SkillLoader
from miniopenclaw.tools import ToolExecutor


class AgentLoop(Protocol):
    """Contract for any core agent loop implementation."""

    def run(self, event: MessageEvent, context: list[MessageEvent]) -> AgentResponse:
        """Execute one turn and return a normalized response."""


class ProviderAgentLoop:
    """Run turns by delegating to provider and optional tool task loop."""

    _TOOL_BLOCK_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
    _TOOL_CODE_BLOCK_PATTERN = re.compile(r"<tool_code>\s*(.*?)\s*</tool_code>", re.DOTALL)
    _PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "system_core.txt"

    def __init__(
        self,
        provider: BaseProvider,
        model: str,
        tool_executor: ToolExecutor,
        memory_store: MemoryStore | None = None,
        skill_loader: SkillLoader | None = None,
        max_steps: int = 8,
        stream: bool = False,
    ) -> None:
        self._provider = provider
        self._model = model
        self._stream = stream
        self._tool_executor = tool_executor
        self._memory_store = memory_store
        self._skill_loader = skill_loader
        self._max_steps = max_steps

    def run(self, event: MessageEvent, context: list[MessageEvent]) -> AgentResponse:
        try:
            if event.content.strip().startswith("/task"):
                return self._run_task_loop(event)
            return self._run_with_auto_tools(event=event, context=context)
        except KeyboardInterrupt:
            return AgentResponse(text="Task interrupted by user.", status=AgentStatus.ERROR)
        except ProviderError as exc:
            return AgentResponse(
                text=f"Error [{exc.kind.value}]: {exc.user_message}",
                status=AgentStatus.ERROR,
                metadata={"error_kind": exc.kind.value, "error_details": exc.details},
            )

    def _run_with_auto_tools(self, event: MessageEvent, context: list[MessageEvent]) -> AgentResponse:
        skill_hints = ""
        skill_trace: dict = {"selected": []}
        if self._skill_loader is not None:
            selected_skills, skill_trace = self._skill_loader.resolve_for_text(event.content)
            skill_hints = self._skill_loader.render_system_hints(selected_skills)

        memory_hints = ""
        memory_trace: dict = {"retrieved_count": 0}
        if self._memory_store is not None:
            session_key = MemoryStore.session_key(event)
            items, trace = self._memory_store.retrieve(session_key=session_key, query=event.content)
            memory_trace = trace
            memory_hints = self._memory_store.render_context(items)

        messages = self._build_messages(
            context=context,
            event=event,
            skill_hints=skill_hints,
            memory_hints=memory_hints,
        )
        all_tool_calls = []

        for _step in range(1, self._max_steps + 1):
            if self._stream:
                model_output = "".join(self._provider.stream_generate(messages=messages, model=self._model))
            else:
                model_output = self._provider.generate(messages=messages, model=self._model)

            parsed_calls = self._parse_tool_calls(model_output)
            if not parsed_calls:
                cleaned = self._strip_tool_blocks(model_output).strip()
                if not cleaned:
                    cleaned = "(No response text returned.)"
                fallback = None
                if not all_tool_calls:
                    fallback = self._fallback_write_if_needed(event.content, cleaned)
                    if fallback:
                        all_tool_calls.append(fallback)
                        if fallback.error:
                            cleaned = f"{cleaned}\n\n[Auto-write failed] {fallback.error}"
                        else:
                            cleaned = f"{cleaned}\n\n已自动写入本地文件。"
                return AgentResponse(
                    text=cleaned,
                    tool_calls=all_tool_calls,
                    metadata={"skills": skill_trace, "memory": memory_trace},
                )

            tool_result_lines: list[str] = []
            for item in parsed_calls:
                normalized_name, normalized_args = self._normalize_tool_call(item["name"], item.get("arguments", {}))
                tool_call = self._tool_executor.execute(normalized_name, normalized_args)
                all_tool_calls.append(tool_call)

                if tool_call.error:
                    tool_result_lines.append(
                        f"tool={item['name']} mapped_tool={normalized_name} status=error\n{tool_call.error}"
                    )
                else:
                    tool_result_lines.append(
                        f"tool={item['name']} mapped_tool={normalized_name} status=ok\n{tool_call.result}"
                    )

            messages.append({"role": "assistant", "content": model_output})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Tool results are ready. Use them to answer the user in final plain text.\n"
                        + "\n\n".join(tool_result_lines)
                    ),
                }
            )

        return AgentResponse(
            text=(
                "Reached max tool-calling steps before producing a final response. "
                "Try simplifying the task or increase MINICLAW_MAX_AGENT_STEPS."
            ),
            status=AgentStatus.ERROR,
            tool_calls=all_tool_calls,
            metadata={"error_kind": "max_steps", "skills": skill_trace, "memory": memory_trace},
        )

    def _run_task_loop(self, event: MessageEvent) -> AgentResponse:
        """Run a deterministic plan->act->observe loop from /task JSON plan."""
        raw = event.content.strip()[len("/task") :].strip()
        if not raw:
            return AgentResponse(
                text=(
                    "Usage: /task {\"steps\":[{\"tool\":\"read_file\",\"args\":{\"path\":\"README.md\"}}]}"
                ),
                status=AgentStatus.ERROR,
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return AgentResponse(text=f"Invalid /task JSON: {exc}", status=AgentStatus.ERROR)

        steps = payload.get("steps", [])
        stop_on_error = bool(payload.get("stop_on_error", False))
        if not isinstance(steps, list) or not steps:
            return AgentResponse(text="/task requires a non-empty steps list", status=AgentStatus.ERROR)

        observations: list[str] = []
        tool_calls = []

        # plan -> act -> observe
        for idx, step in enumerate(steps[: self._max_steps], start=1):
            if not isinstance(step, dict):
                observations.append(f"step {idx}: invalid step format")
                continue

            tool_name = str(step.get("tool", "")).strip()
            args = step.get("args", {})
            if not tool_name or not isinstance(args, dict):
                observations.append(f"step {idx}: missing tool or invalid args")
                continue

            call = self._tool_executor.execute(tool_name, args)
            tool_calls.append(call)

            if call.error:
                observations.append(f"step {idx} [error] {tool_name}: {call.error}")
                if stop_on_error:
                    break
                continue

            observations.append(f"step {idx} [ok] {tool_name}: {call.result}")

        if len(steps) > self._max_steps:
            observations.append(f"max_steps reached: executed {self._max_steps}/{len(steps)} steps")

        status = AgentStatus.COMPLETED
        if any(call.error for call in tool_calls):
            status = AgentStatus.ERROR if stop_on_error else AgentStatus.COMPLETED

        return AgentResponse(
            text="\n".join(observations) if observations else "No steps executed.",
            status=status,
            tool_calls=tool_calls,
            metadata={"max_steps": self._max_steps, "stop_on_error": stop_on_error},
        )

    def _parse_tool_calls(self, text: str) -> list[dict]:
        calls: list[dict] = []
        for raw_json in self._TOOL_BLOCK_PATTERN.findall(text):
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
            name = payload.get("name")
            args = payload.get("arguments", {})
            if isinstance(name, str) and isinstance(args, dict):
                calls.append({"name": name, "arguments": args})
        if calls:
            return calls
        # Fallback for models that emit pseudo code:
        # <tool_code>print(web_search(query="..."))</tool_code>
        return self._parse_tool_code_calls(text)

    def _parse_tool_code_calls(self, text: str) -> list[dict]:
        calls: list[dict] = []
        for code in self._TOOL_CODE_BLOCK_PATTERN.findall(text):
            # 1) Support raw JSON payload inside <tool_code>...</tool_code>
            raw = code.strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                name = payload.get("name")
                args = payload.get("arguments", {})
                if isinstance(name, str) and isinstance(args, dict):
                    calls.append({"name": name, "arguments": args})
                    continue

            # 2) Fallback: parse pseudo Python calls in tool_code blocks.
            try:
                tree = ast.parse(code)
            except SyntaxError:
                continue

            seen: set[tuple[str, str]] = set()
            for stmt in tree.body:
                node = getattr(stmt, "value", None)
                if isinstance(node, ast.Call):
                    extracted = self._extract_call(node)
                    if extracted:
                        key = (extracted["name"], json.dumps(extracted.get("arguments", {}), ensure_ascii=False, sort_keys=True))
                        if key not in seen:
                            seen.add(key)
                            calls.append(extracted)
        return calls

    def _extract_call(self, node: ast.Call) -> dict | None:
        """Extract tool calls from AST nodes, including wrapped print(...) calls."""

        def _func_name(expr: ast.AST) -> str | None:
            if isinstance(expr, ast.Name):
                return expr.id
            if isinstance(expr, ast.Attribute):
                return expr.attr
            return None

        name = _func_name(node.func)
        if name == "print" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Call):
                return self._extract_call(first)
            return None

        if not name:
            return None

        known = {
            "readFile",
            "read_file",
            "fsRead",
            "writeFile",
            "write_file",
            "fsWrite",
            "appendFile",
            "append_file",
            "fsAppend",
            "shell",
            "web_search",
            "webSearch",
            "find_skill",
            "findSkill",
        }
        if name not in known:
            return None

        args: dict = {}
        for kw in node.keywords:
            if not kw.arg:
                continue
            try:
                args[kw.arg] = ast.literal_eval(kw.value)
            except Exception:
                pass
        return {"name": name, "arguments": args}
        return calls

    @staticmethod
    def _strip_tool_blocks(text: str) -> str:
        text = ProviderAgentLoop._TOOL_BLOCK_PATTERN.sub("", text)
        text = ProviderAgentLoop._TOOL_CODE_BLOCK_PATTERN.sub("", text)
        return text

    @staticmethod
    def _normalize_tool_call(tool_name: str, arguments: dict) -> tuple[str, dict]:
        name = tool_name.strip()
        args = dict(arguments)

        alias_map = {
            "readFile": "read_file",
            "fsRead": "read_file",
            "read_file": "read_file",
            "fsWrite": "write_file",
            "writeFile": "write_file",
            "write_file": "write_file",
            "fsAppend": "append_file",
            "appendFile": "append_file",
            "append_file": "append_file",
            "shell": "shell",
            "web_search": "web_search",
            "webSearch": "web_search",
            "find_skill": "find_skill",
            "findSkill": "find_skill",
        }
        normalized_name = alias_map.get(name, name)

        if "filePath" in args and "path" not in args:
            args["path"] = args.pop("filePath")
        if "cmd" in args and "command" not in args:
            args["command"] = args.pop("cmd")
        if "queryText" in args and "query" not in args:
            args["query"] = args.pop("queryText")
        if "skillId" in args and "skill_id" not in args:
            args["skill_id"] = args.pop("skillId")
        if "openLogin" in args and "open_login" not in args:
            args["open_login"] = args.pop("openLogin")
        if normalized_name == "write_file" and "confirm" not in args:
            # Model-triggered writes default to confirmed to avoid stalled overwrite loops.
            args["confirm"] = True

        return normalized_name, args

    def _fallback_write_if_needed(self, user_text: str, model_text: str):
        """If user asks to save/write but model didn't call write tool, auto-write once."""
        if not self._requires_write_by_intent(user_text):
            return None
        if not model_text.strip():
            return None

        path = self._infer_output_path(user_text)
        return self._tool_executor.execute("write_file", {"path": path, "content": model_text, "confirm": True})

    @staticmethod
    def _requires_write_by_intent(text: str) -> bool:
        lower = text.lower()
        keywords = (
            "写入",
            "保存",
            "落盘",
            "生成文档",
            "写个文档",
            "write to file",
            "save to file",
            "save locally",
        )
        return any(k in lower for k in keywords)

    @staticmethod
    def _infer_output_path(text: str) -> str:
        # Prefer explicit markdown path from user input.
        m = re.search(r"([\\w/\\-\\u4e00-\\u9fff]+\\.md)", text)
        if m:
            return m.group(1)

        # Build a deterministic markdown filename under docs/.
        core = re.sub(r"[^0-9A-Za-z\\u4e00-\\u9fff]+", "_", text).strip("_")
        if not core:
            core = "总结文档"
        core = core[:24]
        return f"docs/{core}.md"

    @staticmethod
    def _build_messages(
        context: list[MessageEvent],
        event: MessageEvent,
        skill_hints: str = "",
        memory_hints: str = "",
    ) -> list[ChatMessage]:
        system_prompt = ProviderAgentLoop._load_system_prompt()
        messages: list[ChatMessage] = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        if skill_hints:
            messages.append({"role": "system", "content": skill_hints})
        if memory_hints:
            messages.append({"role": "system", "content": memory_hints})
        for item in context:
            role = item.metadata.get("role", "user")
            if role not in {"system", "user", "assistant"}:
                role = "user"
            messages.append({"role": role, "content": item.content})

        messages.append(
            {
                "role": "system",
                "content": f"Preferred response language: {ProviderAgentLoop._detect_language(event.content)}.",
            }
        )
        messages.append({"role": "user", "content": event.content})
        return messages

    @staticmethod
    def _detect_language(text: str) -> str:
        """Rough language hint based on Unicode ranges in latest user input."""
        if re.search(r"[\u4e00-\u9fff]", text):
            return "Chinese"
        if re.search(r"[\u3040-\u30ff]", text):
            return "Japanese"
        if re.search(r"[\uac00-\ud7af]", text):
            return "Korean"
        return "English"

    @staticmethod
    def _load_system_prompt() -> str:
        fallback = (
            "Respond in the same language as the user's latest message by default. "
            "Use only declared tools and return strict <tool_call> JSON when calling tools."
        )
        try:
            text = ProviderAgentLoop._PROMPT_FILE.read_text(encoding="utf-8").strip()
            return text or fallback
        except Exception:
            return fallback
