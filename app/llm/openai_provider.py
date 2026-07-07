import json

from openai import OpenAI

from app.config import settings


class OpenAIProvider:
    def __init__(self):
        self._client = OpenAI(api_key=settings.openai_api_key)

    def chat_json(self, system: str, user: str, *, model: str, temperature: float = 0.2, max_tokens: int = 600) -> dict:
        resp = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        resp = self._client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in resp.data]
