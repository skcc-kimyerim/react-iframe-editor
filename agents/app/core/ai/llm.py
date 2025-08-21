from abc import ABC, abstractmethod


class LLM(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def generate_text(self, model: str, query: str) -> str:
        pass
