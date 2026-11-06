from typing import Literal

from pydantic import BaseModel

from libs.content_items.inputs import RecordContentItemViewInput

ReadPercentInt = Literal[0, 25, 50, 75, 100]


class RecordContentItemViewDto(BaseModel):
    read_percent: ReadPercentInt

    def to_input(self) -> RecordContentItemViewInput:
        return RecordContentItemViewInput(read_percent=self.read_percent)
