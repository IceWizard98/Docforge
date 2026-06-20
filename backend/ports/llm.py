from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMConfig:
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """Outcome of one tool-augmented turn: either free text or tool calls to run."""
    content: str = ""
    tool_calls: list[ToolCall] | None = None


class LLMProvider(ABC):
    # Providers that implement generate_with_tools set this True.
    supports_tools: bool = False

    @abstractmethod
    async def generate(self, prompt: str, config: LLMConfig | None = None) -> str:
        ...

    @abstractmethod
    async def generate_structured(
        self, prompt: str, response_model: type, config: LLMConfig | None = None
    ) -> dict:
        ...

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        config: LLMConfig | None = None,
    ) -> ToolResult:
        """One tool-augmented chat turn. Override in providers that support it."""
        raise NotImplementedError("This provider does not support tool calling")
