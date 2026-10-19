from abc import ABC, abstractmethod

from libs.generate_text.results import ValidateOutputResult


class BaseGenerateTextOutputFormat(ABC):
    """The format one step's LLM output must follow."""

    def normalize_output(self, output_text: str) -> str:
        """Returns the output unchanged unless a format overrides it."""
        return output_text

    @abstractmethod
    def validate_output(self, output_text: str) -> ValidateOutputResult:
        """Returns the problems found in the output, empty when it follows the format."""
        ...
