from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.graphs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.inputs import (
    CreateGenerateTextRunInput,
    CreateGenerateTextStepInput,
    GenerateTextInput,
    ResumeGenerateTextInput,
    StepOptionInput,
)
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextRunStatusType, GenerateTextStepStatusType, TextType


def build_blog_post_options_input(
    *,
    outline: StepOptionInput | None = None,
    draft: StepOptionInput | None = None,
    humanize: StepOptionInput | None = None,
) -> BlogPostOptionsInput:
    return BlogPostOptionsInput(
        outline=outline, draft=draft or StepOptionInput(), humanize=humanize
    )


def build_create_generate_text_run_input(
    *,
    text_type: TextType = TextType.BLOG_POST,
    graph_name: str = "blog_post",
    graph_version: str = "test-version",
    prompt_text: str = "Write about coffee.",
    persona_info: str | None = None,
    additional_context: str | None = None,
    options: dict[str, Any] | None = None,
) -> CreateGenerateTextRunInput:
    return CreateGenerateTextRunInput(
        text_type=text_type,
        graph_name=graph_name,
        graph_version=graph_version,
        prompt_text=prompt_text,
        persona_info=persona_info,
        additional_context=additional_context,
        options=options if options is not None else {},
    )


async def insert_generate_text_run_row(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    text_type: TextType = TextType.BLOG_POST,
    graph_name: str = "blog_post",
    graph_version: str = "test-version",
    status: GenerateTextRunStatusType = GenerateTextRunStatusType.PENDING,
    current_step: str | None = None,
    prompt_text: str = "Write about coffee.",
    persona_info: str | None = None,
    additional_context: str | None = None,
    options: dict[str, Any] | None = None,
) -> GenerateTextRunOrm:
    run_record = GenerateTextRunOrm(
        text_type=text_type,
        graph_name=graph_name,
        graph_version=graph_version,
        status=status,
        current_step=current_step,
        prompt_text=prompt_text,
        persona_info=persona_info,
        additional_context=additional_context,
        options=options if options is not None else {},
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    db_session.add(run_record)
    await db_session.flush()
    return run_record


def build_create_generate_text_step_input(
    *,
    run_id: int,
    step_name: str = "GENERATE_DRAFT",
    input: dict[str, Any] | None = None,
) -> CreateGenerateTextStepInput:
    return CreateGenerateTextStepInput(run_id=run_id, step_name=step_name, input=input)


async def insert_generate_text_step_row(
    db_session: AsyncSession,
    *,
    run_id: int,
    created_by_id: int,
    step_number: int = 1,
    step_name: str = "GENERATE_DRAFT",
    attempt: int = 1,
    status: GenerateTextStepStatusType = GenerateTextStepStatusType.RUNNING,
    input: dict[str, Any] | None = None,
) -> GenerateTextStepOrm:
    step_record = GenerateTextStepOrm(
        run_id=run_id,
        step_number=step_number,
        step_name=step_name,
        attempt=attempt,
        status=status,
        input=input,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    db_session.add(step_record)
    await db_session.flush()
    return step_record


def build_generate_text_state(
    *,
    auth_user_id: int = 1,
    auth_user_identity: UUID | None = None,
    generate_text_run_id: int = 1,
    generate_text_run_identity: UUID | None = None,
    graph_version: str = "test-version",
    text_type: TextType = TextType.BLOG_POST,
    prompt_text: str = "Write about coffee.",
    persona_info: str | None = None,
    additional_context: str | None = None,
    step_outputs: dict[str, str] | None = None,
    step_decisions: dict[str, str] | None = None,
    step_feedback: dict[str, str] | None = None,
    rewrite_counts: dict[str, int] | None = None,
    current_step_id: int | None = None,
) -> GenerateTextState:
    return GenerateTextState(
        auth_user_id=auth_user_id,
        auth_user_identity=auth_user_identity or uuid4(),
        generate_text_run_id=generate_text_run_id,
        generate_text_run_identity=generate_text_run_identity or uuid4(),
        graph_version=graph_version,
        text_type=text_type.value,
        prompt_text=prompt_text,
        persona_info=persona_info,
        additional_context=additional_context,
        step_outputs=step_outputs or {},
        step_decisions=step_decisions or {},
        step_feedback=step_feedback or {},
        rewrite_counts=rewrite_counts or {},
        current_step_id=current_step_id,
    )


def build_generate_text_input(
    *,
    text_type: TextType = TextType.BLOG_POST,
    prompt_text: str = "Write about coffee.",
    persona_info: str | None = None,
    additional_context: str | None = None,
    options: BlogPostOptionsInput | None = None,
) -> GenerateTextInput[BlogPostOptionsInput]:
    return GenerateTextInput[BlogPostOptionsInput](
        text_type=text_type,
        prompt_text=prompt_text,
        persona_info=persona_info,
        additional_context=additional_context,
        options=options if options is not None else BlogPostOptionsInput(),
    )


def build_resume_generate_text_input(
    *, is_approved: bool = True, feedback_text: str | None = None
) -> ResumeGenerateTextInput:
    return ResumeGenerateTextInput(is_approved=is_approved, feedback_text=feedback_text)
