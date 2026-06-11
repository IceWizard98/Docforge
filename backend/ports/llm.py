from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMConfig:
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, config: LLMConfig | None = None) -> str:
        ...

    @abstractmethod
    async def generate_structured(
        self, prompt: str, response_model: type, config: LLMConfig | None = None
    ) -> dict:
        ...
