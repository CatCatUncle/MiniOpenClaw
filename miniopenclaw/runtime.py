"""Runtime builder for router/tool/provider wiring."""

from __future__ import annotations

from miniopenclaw.config.schema import Config
from miniopenclaw.core.agent_loop import ProviderAgentLoop
from miniopenclaw.core.router import AgentRouter
from miniopenclaw.providers.factory import create_provider
from miniopenclaw.session.manager import SessionManager
from miniopenclaw.tools import ToolExecutor, build_default_registry


def build_runtime(
    config: Config,
    session_store: str,
    max_turns: int,
    max_context_chars: int,
) -> tuple[AgentRouter, SessionManager, ToolExecutor]:
    """Build runtime components used by CLI and gateway channels."""
    provider_instance = create_provider(config)
    tool_executor = ToolExecutor(build_default_registry(config))
    agent_loop = ProviderAgentLoop(
        provider=provider_instance,
        model=config.model,
        tool_executor=tool_executor,
        max_steps=config.max_agent_steps,
        stream=config.stream,
    )

    manager = SessionManager(
        storage_path=session_store,
        max_turns=max_turns,
        max_context_chars=max_context_chars,
    )
    router = AgentRouter(agent_loop=agent_loop, session_manager=manager)
    return router, manager, tool_executor
