from datetime import UTC, datetime
from uuid import UUID, uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
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
from libs.generate_text.services.generate_text_graph_service import GenerateTextGraphService
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextRunStatusType, HumanDecisionType


class GenerateTextService:
    """Starts and resumes generate-text runs. Owns the graph's lifecycle: it mints
    the thread identity, builds the graph a run needs, runs it, reads the snapshot,
    and maps it to a Result."""

    def __init__(
        self,
        graph_service: GenerateTextGraphService,
        run_service: GenerateTextRunService,
        step_service: GenerateTextStepService,
        checkpointer: BaseCheckpointSaver,
    ) -> None:
        self._graph_service = graph_service
        self._run_service = run_service
        self._step_service = step_service
        self._checkpointer = checkpointer

    async def generate_text[OptionsT: BaseModel](
        self, generate_text_input: GenerateTextInput[OptionsT], auth_user: AuthUser
    ) -> GenerateTextRunResult:
        text_type = generate_text_input.text_type
        graph_name = self._graph_service.current_graph_name(text_type)
        graph_version = self._graph_service.current_graph_version(text_type)
        options_dict = generate_text_input.options.model_dump(mode="json")

        thread_id = str(uuid4())
        create_generate_text_run_input = CreateGenerateTextRunInput(
            text_type=text_type,
            graph_name=graph_name,
            graph_version=graph_version,
            thread_id=thread_id,
            prompt_text=generate_text_input.prompt_text,
            persona_info=generate_text_input.persona_info,
            additional_context=generate_text_input.additional_context,
            options=options_dict,
        )
        create_run_result = await self._run_service.create_run(
            create_generate_text_run_input, auth_user
        )

        generate_text_graph = self._graph_service.build_graph(
            text_type, graph_version, options_dict, self._checkpointer
        )
        initial_state = GenerateTextState(
            auth_user_id=auth_user.id,
            auth_user_identity=auth_user.identity,
            generate_text_run_id=create_run_result.id,
            generate_text_run_identity=create_run_result.identity,
            graph_version=graph_version,
            text_type=text_type.value,
            prompt_text=generate_text_input.prompt_text,
            persona_info=generate_text_input.persona_info,
            additional_context=generate_text_input.additional_context,
        )

        await self._run_service.start_run(create_run_result.id)

        graph_run_config = {"configurable": {"thread_id": thread_id}}
        await generate_text_graph.ainvoke(initial_state, graph_run_config)

        state_snapshot = await generate_text_graph.aget_state(graph_run_config)
        return await self._finish(create_run_result.id, create_run_result.identity, state_snapshot)

    async def find_generate_text_run(
        self, run_identity: UUID, auth_user: AuthUser
    ) -> GenerateTextRunResult:
        find_run_result = await self._run_service.find_run_by_identity(run_identity)
        if find_run_result.created_by_id != auth_user.id:
            raise NotFoundException(f"Generate text run {run_identity} not found")

        latest_output = await self._step_service.find_latest_output(find_run_result.id)
        return self._build_run_result(find_run_result, latest_output)

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

        current_graph_version = self._graph_service.current_graph_version(find_run_result.text_type)
        if find_run_result.graph_version != current_graph_version:
            # The checkpoint is shaped by a topology that no longer exists.
            raise GenerateTextRunVersionMismatchException(
                f"Generate text run {run_identity} was built on graph version "
                f"{find_run_result.graph_version}, not the current {current_graph_version}"
            )

        generate_text_graph = self._graph_service.build_graph(
            find_run_result.text_type,
            find_run_result.graph_version,
            find_run_result.options,
            self._checkpointer,
        )
        graph_run_config = {"configurable": {"thread_id": find_run_result.thread_id}}
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

        resume_payload = {
            "is_approved": resume_generate_text_input.is_approved,
            "feedback_text": resume_generate_text_input.feedback_text,
        }
        await generate_text_graph.ainvoke(Command(resume=resume_payload), graph_run_config)

        new_state_snapshot = await generate_text_graph.aget_state(graph_run_config)
        return await self._finish(find_run_result.id, run_identity, new_state_snapshot)

    async def _finish(
        self, run_id: int, run_identity: UUID, state_snapshot: StateSnapshot
    ) -> GenerateTextRunResult:
        generate_text_state = GenerateTextState.model_validate(state_snapshot.values)
        if state_snapshot.next:
            await self._run_service.record_awaiting_review(run_id)
        else:
            await self._run_service.complete_run(run_id)

        find_run_result = await self._run_service.find_run_by_identity(run_identity)
        return self._build_run_result(find_run_result, generate_text_state.latest_output())

    @staticmethod
    def _build_run_result(
        find_run_result: FindGenerateTextRunByIdentityResult, content: str
    ) -> GenerateTextRunResult:
        return GenerateTextRunResult(
            run_identity=find_run_result.identity,
            text_type=find_run_result.text_type,
            status=find_run_result.status,
            current_step=find_run_result.current_step,
            graph_name=find_run_result.graph_name,
            graph_version=find_run_result.graph_version,
            content=content,
            character_count=len(content),
            llm_call_count=find_run_result.llm_call_count,
            input_tokens=find_run_result.input_tokens,
            output_tokens=find_run_result.output_tokens,
            cost_usd=find_run_result.cost_usd,
            started_at=find_run_result.started_at,
            finished_at=find_run_result.finished_at,
        )
