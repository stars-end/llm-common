"""IterativeOrchestrator for Dexter-style agentic workflows.

Full orchestrator with Understand → Plan → Execute → Reflect loop,
ported from Dexter's orchestrator.ts pattern.
"""

import logging
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from llm_common.agents.executor import AgenticExecutor, StreamEvent
from llm_common.agents.message_history import MessageHistory
from llm_common.agents.phases.reflect import ReflectPhase
from llm_common.agents.phases.understand import UnderstandPhase
from llm_common.agents.planner import TaskPlanner
from llm_common.agents.provenance import EvidenceEnvelope
from llm_common.agents.synthesizer import AnswerSynthesizer
from llm_common.agents.tool_context import ToolContextManager
from llm_common.agents.tools import ToolRegistry
from llm_common.core import LLMClient

logger = logging.getLogger(__name__)


class OrchestratorResult(BaseModel):
    """Result from IterativeOrchestrator run."""

    answer: str
    sources: list[dict[str, Any]]
    evidence_envelope: dict[str, Any]
    understanding: dict[str, Any]
    iterations: int
    query_id: str


class IterativeOrchestrator:
    """Full Dexter-style orchestrator with reflection loop.

    Flow:
    1. **Understand**: Extract intent and entities from the query
    2. **Loop** (max N iterations):
       a. **Plan**: Generate execution plan with tool calls
       b. **Execute**: Run tools in parallel
       c. **Reflect**: Evaluate completeness
    3. **Answer**: Synthesize final response with sources

    Example:
        >>> from llm_common.agents import IterativeOrchestrator, ToolRegistry
        >>>
        >>> registry = ToolRegistry()
        >>> registry.register(PortfolioTool())
        >>> registry.register(PriceTool())
        >>>
        >>> orchestrator = IterativeOrchestrator(
        ...     llm_client=client,
        ...     tool_registry=registry,
        ...     max_iterations=2,
        ... )
        >>>
        >>> result = await orchestrator.run("How is my portfolio doing?")
        >>> print(result.answer)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        work_dir: Path | str = "/tmp/iterative_agent",
        max_iterations: int = 2,
        model: str = "glm-4.5-air",
    ):
        """Initialize IterativeOrchestrator.

        Args:
            llm_client: LLM client for all phases
            tool_registry: Registry of available tools
            work_dir: Directory for context storage
            max_iterations: Maximum Plan→Execute→Reflect iterations (default: 2)
            model: Model for Understand/Reflect phases (default: glm-4.5-air)
        """
        self.llm = llm_client
        self.work_dir = Path(work_dir)
        self.max_iterations = max_iterations

        # Initialize sub-components
        self.understand = UnderstandPhase(llm_client, model=model)
        self.planner = TaskPlanner(llm_client)
        self.context_manager = ToolContextManager(self.work_dir)
        self.executor = AgenticExecutor(llm_client, tool_registry, self.context_manager)
        self.reflect = ReflectPhase(llm_client, model=model, max_iterations=max_iterations)
        self.synthesizer = AnswerSynthesizer(llm_client)

        # Store registry for tool descriptions
        self.registry = tool_registry

    async def run(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        conversation_history: MessageHistory | None = None,
    ) -> OrchestratorResult:
        """Run the full agentic flow.

        Args:
            query: User's question/request
            context: Optional context (e.g., page_context, user_id)
            conversation_history: Optional conversation history for multi-turn

        Returns:
            OrchestratorResult with answer, sources, and metadata
        """
        query_id = str(uuid.uuid4())[:12]
        logger.info(f"IterativeOrchestrator starting query_id={query_id}")

        # 1. UNDERSTAND
        conversation_context = None
        if conversation_history and conversation_history.has_messages():
            relevant = await conversation_history.select_relevant_messages(query)
            if relevant:
                conversation_context = conversation_history.format_for_planning(relevant)

        understanding = await self.understand.run(query, conversation_context)

        # 2. ITERATE: Plan → Execute → Reflect
        completed_plans = []
        all_results = []
        evidence_envelope = EvidenceEnvelope(source_tool="iterative_orchestrator")

        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")

            # Build guidance from previous reflection
            guidance = ""
            if completed_plans:
                last_reflection = getattr(completed_plans[-1], "_reflection", None)
                if last_reflection:
                    guidance = self.reflect.build_planning_guidance(last_reflection)

            # PLAN
            plan_context = {
                "understanding": understanding.model_dump(),
                "guidance": guidance,
                **(context or {}),
            }

            # Get tool descriptions for planner
            tool_descriptions = None
            if hasattr(self.registry, "list_tools"):
                tool_descriptions = self.registry.list_tools()
            elif hasattr(self.registry, "get_tool_descriptions"):
                tool_descriptions = self.registry.get_tool_descriptions()

            plan = await self.planner.plan(
                query=query,
                context=plan_context,
                available_tools=tool_descriptions,
            )

            # EXECUTE
            results = await self.executor.execute_plan(plan, query_id)
            all_results.extend(results)

            # Collect evidence from results
            for sub_res in results:
                if isinstance(sub_res.result, list):
                    for tool_exec in sub_res.result:
                        if isinstance(tool_exec, dict) and "output" in tool_exec:
                            output = tool_exec["output"]
                            if hasattr(output, "evidence") and output.evidence:
                                for ev in output.evidence:
                                    evidence_envelope.merge(ev)
                # Fallback for direct SubTaskResult.result if it's a ToolResult
                elif hasattr(sub_res.result, "evidence") and sub_res.result.evidence:
                    for ev in sub_res.result.evidence:
                        evidence_envelope.merge(ev)

            # Format completed work for reflection
            completed_work = self._format_completed_work(completed_plans, all_results)

            # REFLECT
            reflection = await self.reflect.run(
                query=query,
                understanding=understanding,
                completed_work=completed_work,
                iteration=iteration,
            )

            # Store reflection for next iteration's guidance
            plan._reflection = reflection  # type: ignore
            completed_plans.append(plan)

            if reflection.is_complete:
                logger.info(f"Reflection marked complete at iteration {iteration + 1}")
                break

        # 3. SYNTHESIZE
        collected_data = []
        for r in all_results:
            if getattr(r, "success", True) and hasattr(r, "result") and r.result:
                collected_data.append(
                    {
                        "data": r.result,
                        "tool_name": getattr(r, "tool", "unknown"),
                    }
                )

        # Get conversation context for synthesis
        answer_context = None
        if conversation_history and conversation_history.has_messages():
            relevant = await conversation_history.select_relevant_messages(query)
            if relevant:
                answer_context = conversation_history.format_for_answer(relevant)

        answer = await self.synthesizer.synthesize(
            query=query,
            collected_data=collected_data,
            conversation_context=answer_context,
        )

        logger.info(
            f"IterativeOrchestrator complete: {len(completed_plans)} iterations, "
            f"{len(all_results)} tool results"
        )

        return OrchestratorResult(
            answer=answer.content,
            sources=answer.sources if hasattr(answer, "sources") else [],
            evidence_envelope=evidence_envelope.model_dump(),
            understanding=understanding.model_dump(),
            iterations=len(completed_plans),
            query_id=query_id,
        )

    async def run_stream(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        conversation_history: MessageHistory | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Run the agentic flow with streaming events.

        Yields StreamEvent objects for real-time UI updates.

        Args:
            query: User's question/request
            context: Optional context
            conversation_history: Optional conversation history

        Yields:
            StreamEvent objects with type and data
        """
        query_id = str(uuid.uuid4())[:12]

        # 1. UNDERSTAND
        yield StreamEvent(type="thinking", data="Understanding your question...")

        conversation_context = None
        if conversation_history and conversation_history.has_messages():
            relevant = await conversation_history.select_relevant_messages(query)
            if relevant:
                conversation_context = conversation_history.format_for_planning(relevant)

        understanding = await self.understand.run(query, conversation_context)
        yield StreamEvent(
            type="understanding",
            data={"intent": understanding.intent, "entities": len(understanding.entities)},
        )

        # 2. ITERATE
        completed_plans = []
        all_results = []
        evidence_envelope = EvidenceEnvelope(source_tool="iterative_orchestrator")

        for iteration in range(self.max_iterations):
            yield StreamEvent(
                type="thinking",
                data=f"Planning iteration {iteration + 1}/{self.max_iterations}...",
            )

            guidance = ""
            if completed_plans:
                last_reflection = getattr(completed_plans[-1], "_reflection", None)
                if last_reflection:
                    guidance = self.reflect.build_planning_guidance(last_reflection)

            plan_context = {
                "understanding": understanding.model_dump(),
                "guidance": guidance,
                **(context or {}),
            }

            tool_descriptions = None
            if hasattr(self.registry, "list_tools"):
                tool_descriptions = self.registry.list_tools()

            plan = await self.planner.plan(
                query=query,
                context=plan_context,
                available_tools=tool_descriptions,
            )
            yield StreamEvent(type="plan", data=plan.model_dump())

            # Stream executor events
            async for event in self.executor.run_stream(plan, query_id):
                yield event
                if event.type == "tool_result" and event.data:
                    all_results.append(event.data)
                    # Extract evidence for the envelope
                    if isinstance(event.data, dict) and "output" in event.data:
                        output = event.data["output"]
                        if hasattr(output, "evidence") and output.evidence:
                            for ev in output.evidence:
                                evidence_envelope.merge(ev)

            completed_work = self._format_completed_work(completed_plans, all_results)

            yield StreamEvent(type="thinking", data="Evaluating results...")
            reflection = await self.reflect.run(
                query=query,
                understanding=understanding,
                completed_work=completed_work,
                iteration=iteration,
            )

            plan._reflection = reflection  # type: ignore
            completed_plans.append(plan)

            if reflection.is_complete:
                break

        # 3. SYNTHESIZE
        yield StreamEvent(type="thinking", data="Synthesizing answer...")

        collected_data = []
        for r in all_results:
            if isinstance(r, dict) and r.get("output"):
                collected_data.append(
                    {
                        "data": r["output"],
                        "tool_name": r.get("tool", "unknown"),
                    }
                )

        answer_context = None
        if conversation_history and conversation_history.has_messages():
            relevant = await conversation_history.select_relevant_messages(query)
            if relevant:
                answer_context = conversation_history.format_for_answer(relevant)

        answer = await self.synthesizer.synthesize(
            query=query,
            collected_data=collected_data,
            conversation_context=answer_context,
        )

        yield StreamEvent(type="answer", data=answer.content)
        yield StreamEvent(
            type="sources",
            data=answer.sources if hasattr(answer, "sources") else [],
        )
        yield StreamEvent(type="evidence", data=evidence_envelope.model_dump())

    def _format_completed_work(self, plans: list, results: list) -> str:
        """Format completed work for reflection.

        Args:
            plans: List of completed execution plans
            results: List of tool results

        Returns:
            Formatted string describing completed work
        """
        if not plans and not results:
            return "No work completed yet."

        parts = []
        result_idx = 0

        for i, plan in enumerate(plans):
            parts.append(f"--- Iteration {i + 1} ---")
            if hasattr(plan, "tasks"):
                for task in plan.tasks:
                    # Try to match results to tasks
                    if result_idx < len(results):
                        r = results[result_idx]
                        if isinstance(r, dict):
                            status = "✓" if not r.get("error") else "✗"
                            output = str(r.get("output", r.get("error", "No output")))[:200]
                        else:
                            status = "✓" if getattr(r, "success", True) else "✗"
                            output = str(getattr(r, "result", "No output"))[:200]
                        parts.append(f"{status} {task.description}: {output}")
                        result_idx += 1
                    else:
                        parts.append(f"? {task.description}: pending")

        # Any remaining results
        while result_idx < len(results):
            r = results[result_idx]
            if isinstance(r, dict):
                tool = r.get("tool", "unknown")
                output = str(r.get("output", r.get("error", "")))[:200]
                status = "✓" if not r.get("error") else "✗"
            else:
                tool = getattr(r, "tool", "unknown")
                output = str(getattr(r, "result", ""))[:200]
                status = "✓" if getattr(r, "success", True) else "✗"
            parts.append(f"{status} {tool}: {output}")
            result_idx += 1

        return "\n".join(parts) if parts else "No work completed yet."
