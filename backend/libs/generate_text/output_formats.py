from abc import ABC, abstractmethod

from libs.generate_text.results import ValidateOutputResult


class BaseGenerateTextOutputFormat(ABC):
    def normalize_output(self, output_text: str) -> str:
        return output_text

    @abstractmethod
    def validate_output(self, output_text: str) -> ValidateOutputResult: ...
