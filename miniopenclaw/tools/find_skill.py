"""find-skill + MCP workflow tool."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import urllib.parse
import urllib.request
import webbrowser
from typing import Any

from miniopenclaw.skills import SkillLoader
from miniopenclaw.tools.base import ToolError

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


class FindSkillTool:
    """Discover/install/invoke skills via external find-skill command templates."""

    name = "find_skill"
    description = "Find and invoke skill via MCP workflow (search -> install -> invoke)."
    json_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "task": {"type": "string", "minLength": 1, "maxLength": 4000},
            "skill_id": {"type": "string", "minLength": 1, "maxLength": 120},
            "open_login": {"type": "boolean"},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        enabled: bool,
        search_template: str,
        install_template: str,
        invoke_template: str,
        login_template: str,
        auto_open_login: bool,
        skill_paths: list[str],
        workspace_root: str,
    ) -> None:
        self._enabled = enabled
        self._search_template = search_template
        self._install_template = install_template
        self._invoke_template = invoke_template
        self._login_template = login_template
        self._auto_open_login = auto_open_login
        self._skill_paths = skill_paths
        self._workspace_root = workspace_root

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if not self._enabled:
            raise ToolError(
                "find_skill is disabled",
                details="Set MINICLAW_FIND_SKILL_ENABLED=true and restart miniopenclaw.",
            )

        query = str(args["query"]).strip()
        task = str(args.get("task") or query).strip()
        skill_id = str(args.get("skill_id") or "").strip()
        timeout = int(args.get("timeout_seconds", 40))
        open_login = bool(args.get("open_login", True))

        if not self._external_available():
            online = self._run_online_install(query=query, skill_id=skill_id, timeout_seconds=timeout)
            if online is not None:
                return online
            return self._run_local(query=query, task=task, skill_id=skill_id)

        trace: list[str] = []
        search_output = self._run(self._render_template(self._search_template, query, task, skill_id), timeout)
        trace.append(f"search_cmd={search_output['command']}")
        if search_output["returncode"] != 0:
            raise ToolError("find-skill search failed", details=search_output["stderr"] or search_output["stdout"])

        resolved = skill_id or self._pick_skill_id(search_output["stdout"])
        if not resolved:
            raise ToolError("No skill found by find-skill", details=search_output["stdout"][:500])

        if self._install_template.strip():
            install_out = self._run(
                self._render_template(self._install_template, query, task, resolved),
                timeout,
            )
            trace.append(f"install_cmd={install_out['command']}")
            if install_out["returncode"] != 0:
                raise ToolError("find-skill install failed", details=install_out["stderr"] or install_out["stdout"])

        invoke_out = self._run(
            self._render_template(self._invoke_template, query, task, resolved),
            timeout,
        )
        trace.append(f"invoke_cmd={invoke_out['command']}")

        login_url = self._extract_login_url(invoke_out["stdout"] + "\n" + invoke_out["stderr"])
        if (
            not login_url
            and invoke_out["returncode"] != 0
            and self._login_template.strip()
            and self._looks_like_login_issue(invoke_out["stdout"] + "\n" + invoke_out["stderr"])
        ):
            login_out = self._run(
                self._render_template(self._login_template, query, task, resolved),
                timeout,
            )
            trace.append(f"login_cmd={login_out['command']}")
            login_url = self._extract_login_url(login_out["stdout"] + "\n" + login_out["stderr"])

        opened = False
        if login_url and open_login and self._auto_open_login:
            try:
                opened = bool(webbrowser.open(login_url))
            except Exception:
                opened = False

        summary = [
            f"find_skill resolved skill_id={resolved}",
            f"invoke_exit_code={invoke_out['returncode']}",
        ]
        if login_url:
            summary.append(f"login_url={login_url}")
            summary.append(f"browser_opened={opened}")
        if invoke_out["stdout"].strip():
            summary.append(f"stdout:\n{invoke_out['stdout'][:2800]}")
        if invoke_out["stderr"].strip():
            summary.append(f"stderr:\n{invoke_out['stderr'][:1200]}")
        summary.append("trace:\n" + "\n".join(trace))

        return {
            "skill_id": resolved,
            "invoke_exit_code": invoke_out["returncode"],
            "login_url": login_url,
            "browser_opened": opened,
            "summary": "\n".join(summary),
        }

    def _run_local(self, query: str, task: str, skill_id: str) -> dict[str, Any]:
        loader = SkillLoader(search_paths=self._skill_paths)
        selected = []
        trace = {"mode": "local", "external": "missing_find-skill"}
        if skill_id:
            found = loader.get_skill(skill_id)
            if found:
                selected = [found]
        if not selected:
            selected, resolve_trace = loader.resolve_for_text(f"{query}\n{task}")
            trace["resolve"] = resolve_trace
        if not selected:
            raise ToolError(
                "No matching local skill found",
                details=(
                    "find-skill command is not installed, and local SKILL.md match also failed. "
                    "Use /skills to check loaded skills."
                ),
            )

        chosen = selected[0]
        hints = loader.render_system_hints([chosen], max_chars_each=800)
        summary = (
            f"find_skill fallback mode=local\n"
            f"matched_skill={chosen.name}\n"
            f"path={chosen.path}\n"
            f"suggested_trigger=${chosen.name}\n"
            "external find-skill not found; returning local skill guidance only.\n"
            f"trace={trace}\n"
            f"skill_hints:\n{hints}"
        )
        return {
            "skill_id": chosen.name,
            "invoke_exit_code": 0,
            "login_url": None,
            "browser_opened": False,
            "summary": summary,
        }

    def _run_online_install(self, query: str, skill_id: str, timeout_seconds: int) -> dict[str, Any] | None:
        """Fallback mode: search GitHub and install SKILL.md into local ./skills."""
        candidates = self._github_search(query=query, timeout_seconds=timeout_seconds)
        if skill_id:
            candidates = [x for x in candidates if x.get("name", "").lower() == skill_id.lower()] or candidates

        for repo in candidates:
            installed = self._try_install_repo_skill(repo=repo, timeout_seconds=timeout_seconds)
            if installed is None:
                continue
            return {
                "skill_id": installed["skill_name"],
                "invoke_exit_code": 0,
                "login_url": None,
                "browser_opened": False,
                "summary": (
                    "find_skill fallback mode=online\n"
                    f"installed_skill={installed['skill_name']}\n"
                    f"installed_path={installed['path']}\n"
                    f"source_repo={repo.get('html_url')}\n"
                    "next_step:\n"
                    f"${installed['skill_name']} {query}"
                ),
            }
        return None

    def _github_search(self, query: str, timeout_seconds: int) -> list[dict[str, str]]:
        q = f"{query} skill agent in:name,description,readme"
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": q, "sort": "stars", "order": "desc", "per_page": 8}
        )
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        items = payload.get("items", [])
        out: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            owner = (item.get("owner") or {}).get("login", "")
            name = item.get("name", "")
            if not owner or not name:
                continue
            out.append(
                {
                    "owner": str(owner),
                    "name": str(name),
                    "default_branch": str(item.get("default_branch") or "main"),
                    "html_url": str(item.get("html_url") or ""),
                }
            )
        return out

    def _try_install_repo_skill(self, repo: dict[str, str], timeout_seconds: int) -> dict[str, str] | None:
        owner = repo.get("owner", "")
        name = repo.get("name", "")
        branch = repo.get("default_branch", "main")
        if not owner or not name:
            return None

        candidates = [
            f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/SKILL.md",
            f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/skills/SKILL.md",
            f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/.codex/SKILL.md",
        ]
        content = ""
        source_url = ""
        for raw in candidates:
            req = urllib.request.Request(raw, headers={"Accept": "text/plain"})
            try:
                with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                    text = resp.read().decode("utf-8", errors="ignore")
                if text.strip():
                    content = text
                    source_url = raw
                    break
            except Exception:
                continue
        if not content:
            return None

        safe_repo = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "remote-skill"
        skill_name = f"{safe_repo}-remote"
        target_dir = Path(self._workspace_root).expanduser().resolve() / "skills" / skill_name
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(content, encoding="utf-8")
        (target_dir / "SOURCE_URL.txt").write_text(source_url + "\n", encoding="utf-8")
        return {"skill_name": skill_name, "path": str(target_dir / "SKILL.md")}

    def _run(self, command: str, timeout_seconds: int) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self._workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError("find-skill command timed out", details=str(exc)) from exc
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }

    def _external_available(self) -> bool:
        # Try exact command from template first; fallback to find-skill.
        first = ""
        try:
            parts = shlex.split(self._search_template.strip())
            if parts:
                first = parts[0]
        except ValueError:
            first = ""
        if first and shutil.which(first):
            return True
        return shutil.which("find-skill") is not None

    @staticmethod
    def _render_template(template: str, query: str, task: str, skill_id: str) -> str:
        rendered = template
        rendered = rendered.replace("{query}", query)
        rendered = rendered.replace("{task}", task)
        rendered = rendered.replace("{skill_id}", skill_id)
        return rendered

    @staticmethod
    def _pick_skill_id(stdout: str) -> str:
        text = stdout.strip()
        if not text:
            return ""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            candidates = payload.get("skills") or payload.get("results") or payload.get("items") or []
            if isinstance(candidates, list):
                return FindSkillTool._extract_skill_id(candidates)
            for key in ("skill_id", "id", "name"):
                val = payload.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        if isinstance(payload, list):
            return FindSkillTool._extract_skill_id(payload)

        # Fallback: first token-like id in plain text.
        for line in text.splitlines():
            m = re.search(r"\b([A-Za-z0-9._-]{3,80})\b", line)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _extract_skill_id(items: list[Any]) -> str:
        for item in items:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                for key in ("skill_id", "id", "name", "slug"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        return ""

    @staticmethod
    def _looks_like_login_issue(text: str) -> bool:
        lower = text.lower()
        markers = ("login", "sign in", "authenticate", "unauthorized", "扫码", "二维码")
        return any(x in lower for x in markers)

    @staticmethod
    def _extract_login_url(text: str) -> str | None:
        urls = _URL_RE.findall(text)
        if not urls:
            return None
        for url in urls:
            lower = url.lower()
            if any(k in lower for k in ("login", "auth", "oauth", "qr", "signin")):
                return url
        return urls[0]
