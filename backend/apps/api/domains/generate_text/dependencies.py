from typing import Annotated

from fastapi import Depends, Request

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import AuthUserDep, LlmServiceDep
from apps.api.domains.generate_text.dtos import GenerateBlogPostDto
from libs.core.exceptions import ServiceUnavailableException
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.services import (
    GenerateTextInstrumentationService,
    GenerateTextNodeService,
    GenerateTextRunService,
    GenerateTextService,
    GenerateTextStepService,
)
from libs.personas.results import FindUserPersonaResult
from libs.personas.services import PersonaService


def get_generate_text_service(request: Request, llm_service: LlmServiceDep) -> GenerateTextService:
    graph_checkpointer = request.app.state.graph_checkpointer
    if graph_checkpointer is None:
        # lifespan says why: RediSearch only indexes Redis database 0.
        raise ServiceUnavailableException("Text generation is unavailable")

    app_settings: AppSettings = request.app.state.settings
    db_session_factory = request.app.state.db_session_factory
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    generate_text_step_service = GenerateTextStepService(db_session_factory=db_session_factory)
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
        checkpointer=graph_checkpointer,
        background_task_service=request.app.state.background_task_service,
        generate_text_settings=app_settings.generate_text,
    )


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
