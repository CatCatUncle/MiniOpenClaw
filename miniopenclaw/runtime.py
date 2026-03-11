"""Runtime builder for router/tool/provider wiring."""

from __future__ import annotations

from miniopenclaw.config.schema import Config
from miniopenclaw.core.agent_loop import ProviderAgentLoop
from miniopenclaw.core.router import AgentRouter
from miniopenclaw.memory import MemoryStore
from miniopenclaw.providers.factory import create_provider
from miniopenclaw.session.manager import SessionManager
from miniopenclaw.skills import SkillLoader
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
    memory_store = None
    if config.memory_enabled:
        memory_store = MemoryStore(
            storage_path=config.memory_path,
            max_items=config.memory_max_items,
            retrieve_k=config.memory_retrieve_k,
            summary_max_chars=config.memory_summary_max_chars,
        )

    skill_loader = None
    if config.skill_enabled:
        skill_loader = SkillLoader(
            search_paths=config.skill_paths,
            max_skills=config.skill_max_loaded,
            script_timeout_seconds=config.skill_script_timeout_seconds,
        )

    agent_loop = ProviderAgentLoop(
        provider=provider_instance,
        model=config.model,
        tool_executor=tool_executor,
        memory_store=memory_store,
        skill_loader=skill_loader,
        max_steps=config.max_agent_steps,
        stream=config.stream,
    )

    manager = SessionManager(
        storage_path=session_store,
        max_turns=max_turns,
        max_context_chars=max_context_chars,
    )
    router = AgentRouter(agent_loop=agent_loop, session_manager=manager, memory_store=memory_store)
    return router, manager, tool_executor
