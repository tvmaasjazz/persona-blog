from pydantic import BaseModel

from libs.generate_text.inputs import StepOptionInput


class BlogPostOptionsInput(BaseModel):
    outline: StepOptionInput | None = None
    draft: StepOptionInput = StepOptionInput()
    humanize: StepOptionInput | None = None
