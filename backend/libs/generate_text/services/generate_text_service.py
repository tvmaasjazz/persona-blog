from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot
from pydantic import BaseModel

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.generate_text.exceptions import (
    GenerateTextRunNotPausedException,
    GenerateTextRunVersionMismatchException,
)
from libs.generate_text.inputs import (
    CreateGenerateTextRunInput,
    GenerateTextInput,
    ResumeGenerateTextInput,
)
from libs.generate_text.results import FindGenerateTextRunByIdentityResult, GenerateTextRunResult
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextRunStatusType, HumanDecisionType
from libs.personas.results import FindUserPersonaResult

if TYPE_CHECKING:
    # Imported for the annotation only: the builders this registry holds import the node
    # and instrumentation services, so importing it at runtime closes a cycle through
    # services/__init__.py. The registry itself arrives through __init__.
    from libs.generate_text.graphs.generate_text_graph_builder_registry import (
        GenerateTextGraphBuilderRegistry,
    )


class GenerateTextService:
    """Starts and resumes generate-text runs. Owns the graph's lifecycle: it asks the
    registry for the run's builder, runs the graph on the run's own identity as the
    LangGraph thread id, reads the snapshot, and maps it to a Result."""

    def __init__(
        self,
        graph_builder_registry: GenerateTextGraphBuilderRegistry,
        run_service: GenerateTextRunService,
        step_service: GenerateTextStepService,
        checkpointer: BaseCheckpointSaver,
    ) -> None:
        self._graph_builder_registry = graph_builder_registry
        self._run_service = run_service
        self._step_service = step_service
        self._checkpointer = checkpointer

    async def generate_text[OptionsT: BaseModel](
        self,
        generate_text_input: GenerateTextInput[OptionsT],
        find_user_persona_result: FindUserPersonaResult,
        auth_user: AuthUser,
    ) -> GenerateTextRunResult:
        text_type = generate_text_input.text_type
        graph_builder = self._graph_builder_registry.get_by_text_type(text_type)
        options_dict = generate_text_input.options.model_dump(mode="json")

        create_generate_text_run_input = CreateGenerateTextRunInput(
            text_type=text_type,
            graph_name=graph_builder.graph_name,
            graph_version=graph_builder.graph_version,
            prompt_text=generate_text_input.prompt_text,
            persona_id=find_user_persona_result.id,
            tone=generate_text_input.tone,
            target_audience=generate_text_input.target_audience,
            additional_context=generate_text_input.additional_context,
            options=options_dict,
        )
        # Built before the row exists, so bad options fail with nothing left behind.
        generate_text_graph = graph_builder.build_graph(options_dict, self._checkpointer)
        create_run_result = await self._run_service.create_run(
            create_generate_text_run_input, auth_user
        )
        initial_state = GenerateTextState(
            auth_user_id=auth_user.id,
            auth_user_identity=auth_user.identity,
            generate_text_run_id=create_run_result.id,
            generate_text_run_identity=create_run_result.identity,
            graph_version=graph_builder.graph_version,
            text_type=text_type.value,
            prompt_text=generate_text_input.prompt_text,
            persona_name=find_user_persona_result.name,
            persona_bio=find_user_persona_result.bio,
            persona_background=find_user_persona_result.background,
            persona_writing_style=find_user_persona_result.writing_style,
            persona_sample_writing=find_user_persona_result.sample_writing,
            tone=generate_text_input.tone,
            target_audience=generate_text_input.target_audience,
            additional_context=generate_text_input.additional_context,
        )

        await self._run_service.start_run(create_run_result.id)

        # The run's identity is its LangGraph thread id, so no separate thread_id needs
        # to be minted or stored.
        graph_run_config = {"configurable": {"thread_id": str(create_run_result.identity)}}
        await self._invoke_graph(
            generate_text_graph, initial_state, graph_run_config, create_run_result.id
        )

        state_snapshot = await generate_text_graph.aget_state(graph_run_config)
        return await self._finish(create_run_result.id, create_run_result.identity, state_snapshot)

    async def find_generate_text_run(
        self, run_identity: UUID, auth_user: AuthUser
    ) -> GenerateTextRunResult:
        find_run_result = await self._run_service.find_run_by_identity(run_identity)
        if find_run_result.created_by_id != auth_user.id:
            raise NotFoundException(f"Generate text run {run_identity} not found")

        return await self._build_run_result_from_steps(find_run_result)

    async def resume_generate_text(
        self,
        run_identity: UUID,
        resume_generate_text_input: ResumeGenerateTextInput,
        auth_user: AuthUser,
    ) -> GenerateTextRunResult:
        find_run_result = await self._run_service.find_run_by_identity(run_identity)
        if find_run_result.created_by_id != auth_user.id:
            raise NotFoundException(f"Generate text run {run_identity} not found")

        if find_run_result.status != GenerateTextRunStatusType.AWAITING_REVIEW:
            raise GenerateTextRunNotPausedException(
                f"Generate text run {run_identity} is not awaiting review"
            )

        graph_builder = self._graph_builder_registry.get_by_text_type(find_run_result.text_type)
        if find_run_result.graph_version != graph_builder.graph_version:
            # The checkpoint is shaped by a topology that no longer exists.
            raise GenerateTextRunVersionMismatchException(
                f"Generate text run {run_identity} was built on graph version "
                f"{find_run_result.graph_version}, not the current {graph_builder.graph_version}"
            )

        generate_text_graph = graph_builder.build_graph(find_run_result.options, self._checkpointer)
        graph_run_config = {"configurable": {"thread_id": str(run_identity)}}
        state_snapshot = await generate_text_graph.aget_state(graph_run_config)
        generate_text_state = GenerateTextState.model_validate(state_snapshot.values)

        if generate_text_state.current_step_id is not None:
            human_decision = (
                HumanDecisionType.APPROVED
                if resume_generate_text_input.is_approved
                else HumanDecisionType.REJECTED
            )
            await self._step_service.record_decision(
                generate_text_state.current_step_id,
                human_decision,
                resume_generate_text_input.feedback_text,
                auth_user,
                datetime.now(UTC),
            )

        resume_payload = resume_generate_text_input.model_dump()
        await self._invoke_graph(
            generate_text_graph,
            Command(resume=resume_payload),
            graph_run_config,
            find_run_result.id,
        )

        new_state_snapshot = await generate_text_graph.aget_state(graph_run_config)
        return await self._finish(find_run_result.id, run_identity, new_state_snapshot)

    async def _invoke_graph(
        self,
        generate_text_graph: CompiledStateGraph,
        graph_input: object,
        graph_run_config: dict[str, object],
        run_id: int,
    ) -> None:
        """A node's failure is already recorded by the instrumentation wrapper, which then
        re-raises. Anything else that breaks — the checkpointer, the graph itself — has no
        step to own it, so the run is failed here rather than left RUNNING forever."""
        try:
            await generate_text_graph.ainvoke(graph_input, graph_run_config)
        except Exception as graph_exception:
            await self._run_service.fail_run(
                run_id, type(graph_exception).__name__, str(graph_exception)
            )
            raise

    async def _finish(
        self, run_id: int, run_identity: UUID, state_snapshot: StateSnapshot
    ) -> GenerateTextRunResult:
        if state_snapshot.next:
            await self._run_service.record_awaiting_review(run_id)
        else:
            await self._run_service.complete_run(run_id)

        find_run_result = await self._run_service.find_run_by_identity(run_identity)
        # The wrapper has already written the steps this run produced, so they answer both
        # where it sits and what it wrote — the same source the GET route reads.
        return await self._build_run_result_from_steps(find_run_result)

    async def _build_run_result_from_steps(
        self, find_run_result: FindGenerateTextRunByIdentityResult
    ) -> GenerateTextRunResult:
        """Where the run sits and what it has produced both come from its newest step."""
        try:
            find_latest_step_result = await self._step_service.find_latest_step(find_run_result.id)
        except NotFoundException:
            # A run whose first node hasn't finished has no step to report yet.
            return self._build_run_result(find_run_result, last_step=None, content="")

        return self._build_run_result(
            find_run_result,
            last_step=find_latest_step_result.step_name,
            content=find_latest_step_result.content,
        )

    @staticmethod
    def _build_run_result(
        find_run_result: FindGenerateTextRunByIdentityResult, last_step: str | None, content: str
    ) -> GenerateTextRunResult:
        return GenerateTextRunResult(
            run_identity=find_run_result.identity,
            text_type=find_run_result.text_type,
            status=find_run_result.status,
            last_step=last_step,
            graph_name=find_run_result.graph_name,
            graph_version=find_run_result.graph_version,
            persona_identity=find_run_result.persona_identity,
            prompt_text=find_run_result.prompt_text,
            tone=find_run_result.tone,
            target_audience=find_run_result.target_audience,
            additional_context=find_run_result.additional_context,
            options=find_run_result.options,
            content=content,
            character_count=len(content),
            llm_call_count=find_run_result.llm_call_count,
            input_tokens=find_run_result.input_tokens,
            output_tokens=find_run_result.output_tokens,
            cost_usd=find_run_result.cost_usd,
            started_at=find_run_result.started_at,
            finished_at=find_run_result.finished_at,
        )
