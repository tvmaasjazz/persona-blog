import asyncio
from contextlib import aclosing
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot
from pydantic import BaseModel

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.core.services import BackgroundJobService
from libs.generate_text.constants import (
    RUN_NEVER_STARTED_ERROR_CODE,
    RUN_NEVER_STARTED_ERROR_MESSAGE,
    RUN_PICKED_UP_TOO_OFTEN_ERROR_CODE,
    RUN_PICKED_UP_TOO_OFTEN_ERROR_MESSAGE,
)
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
from libs.generate_text.settings import GenerateTextSettings
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

logger = structlog.get_logger(__name__)


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
        background_job_service: BackgroundJobService,
        generate_text_settings: GenerateTextSettings,
    ) -> None:
        self._graph_builder_registry = graph_builder_registry
        self._run_service = run_service
        self._step_service = step_service
        self._checkpointer = checkpointer
        self._background_job_service = background_job_service
        self._generate_text_settings = generate_text_settings

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
            lease_owner=self._background_job_service.worker_id,
            lease_expires_at=self._build_lease_expires_at(),
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

        # Read before the task starts, so the caller is told PENDING whatever the task does.
        find_run_result = await self._run_service.find_run_by_identity(create_run_result.identity)

        # The run's identity is its LangGraph thread id, so no separate thread_id needs
        # to be minted or stored.
        graph_run_config = {"configurable": {"thread_id": str(create_run_result.identity)}}
        self._background_job_service.start(
            self._run_graph_in_background(
                generate_text_graph,
                initial_state,
                graph_run_config,
                create_run_result.id,
                should_start_run=True,
            )
        )
        return self._build_run_result(find_run_result, last_step=None, content="")

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

        graph_builder = self._graph_builder_registry.get_by_text_type(find_run_result.text_type)
        if find_run_result.graph_version != graph_builder.graph_version:
            # The checkpoint is shaped by a topology that no longer exists.
            raise GenerateTextRunVersionMismatchException(
                f"Generate text run {run_identity} was built on graph version "
                f"{find_run_result.graph_version}, not the current {graph_builder.graph_version}"
            )

        generate_text_graph = graph_builder.build_graph(find_run_result.options, self._checkpointer)
        graph_run_config = {"configurable": {"thread_id": str(run_identity)}}

        is_claimed = await self._run_service.claim_paused_run(
            find_run_result.id,
            self._background_job_service.worker_id,
            self._build_lease_expires_at(),
        )
        if not is_claimed:
            raise GenerateTextRunNotPausedException(
                f"Generate text run {run_identity} is not awaiting review"
            )

        try:
            await self._record_review_decision(
                find_run_result.id, resume_generate_text_input, auth_user
            )
        except Exception as record_decision_exception:
            # The run is already claimed as RUNNING, and no task exists yet to move it
            # on, so it's failed here rather than left RUNNING forever.
            await self._run_service.fail_run(
                find_run_result.id,
                type(record_decision_exception).__name__,
                str(record_decision_exception),
            )
            raise

        # Read before the task starts: once it runs it writes steps of its own, and the
        # response would depend on how far it had got.
        claimed_run_result = find_run_result.model_copy(
            update={"status": GenerateTextRunStatusType.RUNNING}
        )
        resume_run_result = await self._build_run_result_from_steps(claimed_run_result)

        resume_payload = resume_generate_text_input.model_dump()
        self._background_job_service.start(
            self._run_graph_in_background(
                generate_text_graph,
                Command(resume=resume_payload),
                graph_run_config,
                find_run_result.id,
                should_start_run=False,
            )
        )
        return resume_run_result

    async def _record_review_decision(
        self,
        run_id: int,
        resume_generate_text_input: ResumeGenerateTextInput,
        auth_user: AuthUser,
    ) -> None:
        """Records the decision on the step the run is paused on. That step is read from the
        step rows, not the checkpoint: a review node interrupts before its state update is
        saved, so the checkpoint never holds its step."""
        awaiting_review_step_id = await self._step_service.find_awaiting_review_step_id(run_id)
        if awaiting_review_step_id is None:
            return
        human_decision = (
            HumanDecisionType.APPROVED
            if resume_generate_text_input.is_approved
            else HumanDecisionType.REJECTED
        )
        await self._step_service.record_decision(
            awaiting_review_step_id,
            human_decision,
            resume_generate_text_input.feedback_text,
            auth_user,
            datetime.now(UTC),
        )

    async def pick_up_expired_run(self) -> bool:
        """Called by the sweeper. Claims one run whose lease has run out and resumes it from
        its checkpoint. Returns whether it claimed a run, so the caller can ask again."""
        if self._background_job_service.is_stopping:
            return False

        lease_expires_at = self._build_lease_expires_at()
        claim_expired_run_result = await self._run_service.claim_expired_run(
            self._background_job_service.worker_id, lease_expires_at
        )
        if claim_expired_run_result is None:
            return False

        run_id = claim_expired_run_result.id
        if claim_expired_run_result.status is GenerateTextRunStatusType.PENDING:
            # Its job never started, so no checkpoint exists to resume from.
            await self._run_service.fail_run(
                run_id, RUN_NEVER_STARTED_ERROR_CODE, RUN_NEVER_STARTED_ERROR_MESSAGE
            )
            return True

        if claim_expired_run_result.pickup_count > self._generate_text_settings.max_run_pickups:
            await self._run_service.fail_run(
                run_id, RUN_PICKED_UP_TOO_OFTEN_ERROR_CODE, RUN_PICKED_UP_TOO_OFTEN_ERROR_MESSAGE
            )
            return True

        graph_builder = self._graph_builder_registry.get_by_text_type(
            claim_expired_run_result.text_type
        )
        if claim_expired_run_result.graph_version != graph_builder.graph_version:
            await self._run_service.fail_run(
                run_id,
                GenerateTextRunVersionMismatchException.__name__,
                f"Generate text run {claim_expired_run_result.identity} was built on graph "
                f"version {claim_expired_run_result.graph_version}, "
                f"not the current {graph_builder.graph_version}",
            )
            return True

        try:
            generate_text_graph = graph_builder.build_graph(
                claim_expired_run_result.options, self._checkpointer
            )
        except Exception as build_graph_exception:
            await self._run_service.fail_run(
                run_id, type(build_graph_exception).__name__, str(build_graph_exception)
            )
            return True

        graph_run_config = {"configurable": {"thread_id": str(claim_expired_run_result.identity)}}
        self._background_job_service.start(
            self._run_graph_in_background(
                generate_text_graph,
                None,
                graph_run_config,
                run_id,
                should_start_run=False,
            )
        )
        return True

    def _build_lease_expires_at(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self._generate_text_settings.lease_seconds)

    async def _run_graph_in_background(
        self,
        generate_text_graph: CompiledStateGraph,
        graph_input: object,
        graph_run_config: dict[str, object],
        run_id: int,
        should_start_run: bool,
    ) -> None:
        """Runs as a background job, so nothing here may use the request's resources.
        A failure is recorded on the run and re-raised for BackgroundJobService to log. A
        cancellation (the drain deadline passed, or the lease was lost) releases the lease
        instead of failing the run, so another process can pick it up."""
        job_task = asyncio.current_task()
        heartbeat_task = asyncio.create_task(self._keep_lease_alive(run_id, job_task))
        try:
            if should_start_run:
                await self._run_service.start_run(run_id)
            is_stopped = await self._stream_graph(
                generate_text_graph, graph_input, graph_run_config, run_id
            )
            # Stopped before the run ends: a heartbeat that outlived the lease clearing
            # would find the lease gone and cancel a job that is already finishing.
            await self._stop_heartbeat(heartbeat_task)
            if is_stopped:
                await self._run_service.release_lease(
                    run_id, self._background_job_service.worker_id
                )
                return
            state_snapshot = await generate_text_graph.aget_state(graph_run_config)
            await self._finish(run_id, state_snapshot)
        except asyncio.CancelledError:
            await self._run_service.release_lease(run_id, self._background_job_service.worker_id)
            raise
        except Exception as background_exception:
            await self._run_service.fail_run(
                run_id, type(background_exception).__name__, str(background_exception)
            )
            raise
        finally:
            await self._stop_heartbeat(heartbeat_task)

    async def _stream_graph(
        self,
        generate_text_graph: CompiledStateGraph,
        graph_input: object,
        graph_run_config: dict[str, object],
        run_id: int,
    ) -> bool:
        """Returns whether it stopped early because the process is shutting down. A review
        pause ends the stream on its own.

        A node's failure is already recorded by the instrumentation wrapper, which then
        re-raises. Anything else that breaks — the checkpointer, the graph itself — has no
        step to own it, so the run is failed here rather than left RUNNING forever."""
        try:
            # durability="sync" saves each step's checkpoint before the next chunk arrives,
            # so stopping between steps never loses the step that just finished.
            graph_stream = generate_text_graph.astream(
                graph_input, graph_run_config, stream_mode="updates", durability="sync"
            )
            async with aclosing(graph_stream):
                async for _ in graph_stream:
                    if self._background_job_service.is_stopping:
                        return True
        except Exception as graph_exception:
            await self._run_service.fail_run(
                run_id, type(graph_exception).__name__, str(graph_exception)
            )
            raise
        return False

    async def _keep_lease_alive(self, run_id: int, job_task: asyncio.Task[Any] | None) -> None:
        """Renews the lease until cancelled. When it can't — someone else owns the run now —
        the job is cancelled so the two don't run side by side."""
        worker_id = self._background_job_service.worker_id
        while True:
            await asyncio.sleep(self._generate_text_settings.lease_heartbeat_seconds)
            try:
                is_renewed = await self._run_service.renew_lease(
                    run_id, worker_id, self._build_lease_expires_at()
                )
            except Exception:
                # A failed write isn't a lost lease; the next beat tries again.
                logger.warning("lease_renewal_failed", run_id=run_id, exc_info=True)
                continue

            if not is_renewed:
                logger.warning("lease_lost", run_id=run_id, worker_id=worker_id)
                if job_task is not None:
                    job_task.cancel()
                return

    async def _stop_heartbeat(self, heartbeat_task: asyncio.Task[None]) -> None:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)

    async def _finish(self, run_id: int, state_snapshot: StateSnapshot) -> None:
        if state_snapshot.next:
            await self._run_service.record_awaiting_review(run_id)
        else:
            await self._run_service.complete_run(run_id)

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

    def _build_run_result(
        self,
        find_run_result: FindGenerateTextRunByIdentityResult,
        last_step: str | None,
        content: str,
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
            poll_interval_ms=self._generate_text_settings.poll_interval_ms,
        )
