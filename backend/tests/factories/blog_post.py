from libs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.inputs import StepOptionInput


def build_blog_post_options_input(
    *,
    outline: StepOptionInput | None = None,
    draft: StepOptionInput | None = None,
    humanize: StepOptionInput | None = None,
) -> BlogPostOptionsInput:
    return BlogPostOptionsInput(
        outline=outline, draft=draft or StepOptionInput(), humanize=humanize
    )
