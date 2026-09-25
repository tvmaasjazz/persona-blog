from typing import Annotated

from fastapi import Depends, Request

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import LlmServiceDep
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
    generate_text_node_service = GenerateTextNodeService(llm_service=llm_service)
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
    )


GenerateTextServiceDep = Annotated[GenerateTextService, Depends(get_generate_text_service)]
