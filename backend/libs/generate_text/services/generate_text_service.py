from uuid import UUID, uuid4

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot

from libs.auth.results import AuthUser
from libs.generate_text.exceptions import (
    GenerateTextThreadNotFoundException,
    GenerateTextThreadNotPausedException,
)
from libs.generate_text.inputs import GenerateTextInput, ResumeGenerateTextInput
from libs.generate_text.results import GenerateTextResult
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextStatusType


class GenerateTextService:
    def __init__(self, generate_text_graph: CompiledStateGraph) -> None:
        self._generate_text_graph = generate_text_graph

    async def generate_text(
        self, generate_text_input: GenerateTextInput, auth_user: AuthUser
    ) -> GenerateTextResult:
        thread_identity = uuid4()
        initial_state = GenerateTextState(
            auth_user_id=auth_user.id,
            auth_user_identity=auth_user.identity,
            text_type=generate_text_input.text_type,
            prompt_text=generate_text_input.prompt_text,
        )
        graph_run_config = {"configurable": {"thread_id": str(thread_identity)}}
        await self._generate_text_graph.ainvoke(initial_state, graph_run_config)

        state_snapshot = await self._generate_text_graph.aget_state(graph_run_config)
        return self._build_result(thread_identity, state_snapshot)

    async def resume_generate_text(
        self,
        thread_identity: UUID,
        resume_generate_text_input: ResumeGenerateTextInput,
        auth_user: AuthUser,
    ) -> GenerateTextResult:
        graph_run_config = {"configurable": {"thread_id": str(thread_identity)}}
        state_snapshot = await self._generate_text_graph.aget_state(graph_run_config)
        self._ensure_owned_thread(state_snapshot, auth_user)

        if not state_snapshot.next:
            raise GenerateTextThreadNotPausedException(
                f"Generate text thread {thread_identity} is not awaiting review"
            )

        resume_payload = {
            "is_approved": resume_generate_text_input.is_approved,
            "feedback_text": resume_generate_text_input.feedback_text,
        }
        await self._generate_text_graph.ainvoke(Command(resume=resume_payload), graph_run_config)

        new_state_snapshot = await self._generate_text_graph.aget_state(graph_run_config)
        return self._build_result(thread_identity, new_state_snapshot)

    def _ensure_owned_thread(self, state_snapshot: StateSnapshot, auth_user: AuthUser) -> None:
        if not state_snapshot.values:
            raise GenerateTextThreadNotFoundException("Generate text thread not found")

        generate_text_state = GenerateTextState.model_validate(state_snapshot.values)
        if generate_text_state.auth_user_identity != auth_user.identity:
            raise GenerateTextThreadNotFoundException("Generate text thread not found")

    def _build_result(
        self, thread_identity: UUID, state_snapshot: StateSnapshot
    ) -> GenerateTextResult:
        generate_text_state = GenerateTextState.model_validate(state_snapshot.values)
        status = (
            GenerateTextStatusType.AWAITING_REVIEW
            if state_snapshot.next
            else GenerateTextStatusType.COMPLETED
        )
        return GenerateTextResult(
            thread_identity=thread_identity,
            status=status,
            content=generate_text_state.draft_text,
            character_count=len(generate_text_state.draft_text),
        )
