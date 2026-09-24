from typing import Annotated

from fastapi import Depends, Request

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import LlmServiceDep
from libs.core.exceptions import ServiceUnavailableException
from libs.generate_text.graphs import build_generate_text_graph
from libs.generate_text.services import GenerateTextService


def get_generate_text_service(request: Request, llm_service: LlmServiceDep) -> GenerateTextService:
    app_settings: AppSettings = request.app.state.settings
    graph_checkpointer = request.app.state.graph_checkpointer
    if graph_checkpointer is None:
        # lifespan says why: RediSearch only indexes Redis database 0.
        raise ServiceUnavailableException("Text generation is unavailable")

    generate_text_graph = build_generate_text_graph(
        llm_service=llm_service,
        generate_text_settings=app_settings.generate_text,
        checkpointer=graph_checkpointer,
    )
    return GenerateTextService(generate_text_graph)


GenerateTextServiceDep = Annotated[GenerateTextService, Depends(get_generate_text_service)]
