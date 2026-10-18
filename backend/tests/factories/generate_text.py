from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.constants import STEP_OUTPUT_TEXT_KEY
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
    persona_id: int,
    tone: str | None = None,
    target_audience: str | None = None,
    additional_context: str | None = None,
    options: dict[str, Any] | None = None,
    lease_owner: str = "test-worker",
    lease_seconds: int = 60,
) -> CreateGenerateTextRunInput:
    return CreateGenerateTextRunInput(
        text_type=text_type,
        graph_name=graph_name,
        graph_version=graph_version,
        prompt_text=prompt_text,
        persona_id=persona_id,
        tone=tone,
        target_audience=target_audience,
        additional_context=additional_context,
        options=options if options is not None else {},
        lease_owner=lease_owner,
        lease_seconds=lease_seconds,
    )


async def insert_generate_text_run_row(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    text_type: TextType = TextType.BLOG_POST,
    graph_name: str = "blog_post",
    graph_version: str = "test-version",
    status: GenerateTextRunStatusType = GenerateTextRunStatusType.PENDING,
    prompt_text: str = "Write about coffee.",
    persona_id: int | None = None,
    tone: str | None = None,
    target_audience: str | None = None,
    additional_context: str | None = None,
    options: dict[str, Any] | None = None,
    content_item_id: int | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    lease_owner: str | None = None,
    lease_expires_at: datetime | None = None,
    pickup_count: int = 0,
    deleted_at: datetime | None = None,
    deleted_by_id: int | None = None,
) -> GenerateTextRunOrm:
    run_record = GenerateTextRunOrm(
        text_type=text_type,
        graph_name=graph_name,
        graph_version=graph_version,
        status=status,
        prompt_text=prompt_text,
        persona_id=persona_id,
        tone=tone,
        target_audience=target_audience,
        additional_context=additional_context,
        options=options if options is not None else {},
        content_item_id=content_item_id,
        error_code=error_code,
        error_message=error_message,
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        pickup_count=pickup_count,
        deleted_at=deleted_at,
        deleted_by_id=deleted_by_id,
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
    output_text: str | None = None,
) -> GenerateTextStepOrm:
    step_record = GenerateTextStepOrm(
        run_id=run_id,
        step_number=step_number,
        step_name=step_name,
        attempt=attempt,
        status=status,
        input=input,
        output={STEP_OUTPUT_TEXT_KEY: output_text} if output_text is not None else None,
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
    persona_name: str = "Marta Quill",
    persona_bio: str = "Writes about slow mornings and stronger coffee.",
    persona_background: str | None = None,
    persona_writing_style: str | None = None,
    persona_sample_writing: str | None = None,
    tone: str | None = None,
    target_audience: str | None = None,
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
        persona_name=persona_name,
        persona_bio=persona_bio,
        persona_background=persona_background,
        persona_writing_style=persona_writing_style,
        persona_sample_writing=persona_sample_writing,
        tone=tone,
        target_audience=target_audience,
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
    tone: str | None = None,
    target_audience: str | None = None,
    additional_context: str | None = None,
    options: BlogPostOptionsInput | None = None,
) -> GenerateTextInput[BlogPostOptionsInput]:
    return GenerateTextInput[BlogPostOptionsInput](
        text_type=text_type,
        prompt_text=prompt_text,
        tone=tone,
        target_audience=target_audience,
        additional_context=additional_context,
        options=options if options is not None else BlogPostOptionsInput(),
    )


def build_resume_generate_text_input(
    *, is_approved: bool = True, feedback_text: str | None = None
) -> ResumeGenerateTextInput:
    return ResumeGenerateTextInput(is_approved=is_approved, feedback_text=feedback_text)
