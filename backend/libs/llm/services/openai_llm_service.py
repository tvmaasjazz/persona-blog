from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel

from libs.llm.inputs import LlmProviderCompletionInput
from libs.llm.results import LlmProviderCompletionResult
from libs.llm.services.base_llm_provider_service import BaseLlmProviderService
from libs.llm.utils import OpenAiLlmUtils


class OpenAiLlmService(BaseLlmProviderService):
    def __init__(self, openai_client: AsyncOpenAI) -> None:
        self._openai_client = openai_client

    async def complete(
        self, provider_input: LlmProviderCompletionInput
    ) -> LlmProviderCompletionResult:
        try:
            raw_response = await self._openai_client.responses.with_raw_response.create(
                model=provider_input.model_name,
                **OpenAiLlmUtils.build_instructions_kwargs(provider_input),
                input=provider_input.user_prompt,
                max_output_tokens=provider_input.max_output_tokens,
                timeout=provider_input.request_timeout_seconds,
            )
        except OpenAIError as openai_error:
            raise OpenAiLlmUtils.map_openai_error(openai_error) from openai_error

        response = raw_response.parse()
        return OpenAiLlmUtils.build_provider_completion_result(
            response, raw_response.request_id, None
        )

    async def complete_structured(
        self, provider_input: LlmProviderCompletionInput, output_type: type[BaseModel]
    ) -> LlmProviderCompletionResult:
        try:
            raw_response = await self._openai_client.responses.with_raw_response.parse(
                model=provider_input.model_name,
                **OpenAiLlmUtils.build_instructions_kwargs(provider_input),
                input=provider_input.user_prompt,
                max_output_tokens=provider_input.max_output_tokens,
                timeout=provider_input.request_timeout_seconds,
                text_format=output_type,
            )
        except OpenAIError as openai_error:
            raise OpenAiLlmUtils.map_openai_error(openai_error) from openai_error

        response = raw_response.parse()
        return OpenAiLlmUtils.build_provider_completion_result(
            response, raw_response.request_id, response.output_parsed
        )
