from typing import Annotated

from fastapi import Depends, Request
from starlette.datastructures import State

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import AuthUserDep, LlmServiceDep, build_llm_service
from apps.api.domains.generate_text.dtos import GenerateBlogPostDto
from libs.core.exceptions import ServiceUnavailableException
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.services import (
    GenerateTextInstrumentationService,
    GenerateTextNodeService,
    GenerateTextRunHandoffQueueService,
    GenerateTextRunLeaseService,
    GenerateTextRunPickupService,
    GenerateTextRunService,
    GenerateTextService,
    GenerateTextStepService,
)
from libs.llm.services import LlmService
from libs.personas.results import FindUserPersonaResult
from libs.personas.services import PersonaService


def build_generate_text_service(app_state: State, llm_service: LlmService) -> GenerateTextService:
    """Builds the generate-text service from app state."""
    graph_checkpointer = app_state.graph_checkpointer
    if graph_checkpointer is None:
        # No checkpointer when Redis isn't on database 0
        raise ServiceUnavailableException("Text generation is unavailable")

    app_settings: AppSettings = app_state.settings
    db_session_factory = app_state.db_session_factory
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    generate_text_step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    generate_text_run_handoff_queue_service = GenerateTextRunHandoffQueueService(
        redis_client=app_state.redis_client
    )
    generate_text_run_lease_service = GenerateTextRunLeaseService(
        run_service=generate_text_run_service,
        handoff_queue_service=generate_text_run_handoff_queue_service,
        background_job_service=app_state.background_job_service,
        generate_text_settings=app_settings.generate_text,
    )
    generate_text_instrumentation_service = GenerateTextInstrumentationService(
        run_service=generate_text_run_service, step_service=generate_text_step_service
    )
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service, generate_text_settings=app_settings.generate_text
    )
    generate_text_graph_builder_registry = GenerateTextGraphBuilderRegistry(
        node_service=generate_text_node_service,
        instrumentation_service=generate_text_instrumentation_service,
        generate_text_settings=app_settings.generate_text,
    )
    return GenerateTextService(
        graph_builder_registry=generate_text_graph_builder_registry,
        run_service=generate_text_run_service,
        step_service=generate_text_step_service,
        lease_service=generate_text_run_lease_service,
        checkpointer=graph_checkpointer,
        background_job_service=app_state.background_job_service,
        generate_text_settings=app_settings.generate_text,
    )


def build_generate_text_run_pickup_service(app_state: State) -> GenerateTextRunPickupService:
    """Builds the pickup service whose loops lifespan runs."""
    app_settings: AppSettings = app_state.settings
    generate_text_run_service = GenerateTextRunService(
        db_session_factory=app_state.db_session_factory
    )
    generate_text_run_handoff_queue_service = GenerateTextRunHandoffQueueService(
        redis_client=app_state.redis_client
    )
    generate_text_run_lease_service = GenerateTextRunLeaseService(
        run_service=generate_text_run_service,
        handoff_queue_service=generate_text_run_handoff_queue_service,
        background_job_service=app_state.background_job_service,
        generate_text_settings=app_settings.generate_text,
    )
    return GenerateTextRunPickupService(
        generate_text_service=build_generate_text_service(app_state, build_llm_service(app_state)),
        lease_service=generate_text_run_lease_service,
        handoff_queue_service=generate_text_run_handoff_queue_service,
        run_service=generate_text_run_service,
        background_job_service=app_state.background_job_service,
        generate_text_settings=app_settings.generate_text,
    )


def get_generate_text_service(request: Request, llm_service: LlmServiceDep) -> GenerateTextService:
    return build_generate_text_service(request.app.state, llm_service)


GenerateTextServiceDep = Annotated[GenerateTextService, Depends(get_generate_text_service)]


async def get_generate_text_persona(
    request: Request,
    dto: GenerateBlogPostDto,
    auth_user: AuthUserDep,
) -> FindUserPersonaResult:
    db_session_factory = request.app.state.db_session_factory
    async with db_session_factory() as db_session:
        persona_service = PersonaService(db_session=db_session)
        return await persona_service.find_user_persona(dto.persona_identity, auth_user)


GenerateTextPersonaDep = Annotated[FindUserPersonaResult, Depends(get_generate_text_persona)]
