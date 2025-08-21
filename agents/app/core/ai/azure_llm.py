from core.ai.llm import LLM
from openai import AzureOpenAI
from openai.types.chat.chat_completion import ChatCompletion


class AzureLLM(LLM):
    def __init__(self, api_key: str, base_url: str, deployment: str, api_version: str):
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=base_url,
            azure_deployment=deployment,
            api_version=api_version,
        )

    def generate_text(self, model: str, query: str) -> ChatCompletion:
        completion = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}],
        )
        return completion
