"""Gemini API client."""

from collections.abc import AsyncIterator

from google import genai
from google.genai.types import GenerateContentConfig

from app.config import settings

SYSTEM_INSTRUCTION = """\
あなたはアシスタントです。
ユーザーの入力には [PERSON_1], [EMAIL_1], [PHONE_1] などのプレースホルダーが含まれることがあります。
これらは個人情報を保護するための識別子です。

以下のルールを必ず守ってください：
- プレースホルダーは絶対に変更・省略・言い換えしないでください。
- 大文字小文字、角括弧、アンダースコア、番号をすべてそのまま維持してください。
- 例: [PERSON_1] を「その人」「Aさん」などに言い換えてはいけません。
- 例: [EMAIL_1] を「メールアドレス」などに言い換えてはいけません。
- 回答内でプレースホルダーを参照する場合も、入力と完全に同じ文字列を使ってください。
"""


class LlmClient:
    """Sends prompts to Google Gemini and returns responses."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    async def generate(self, prompt: str) -> str:
        """Send a prompt to Gemini and return the generated text."""
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )
        return response.text

    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt to Gemini and yield text chunks as they arrive."""
        stream = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )
        async for response in stream:
            if response.text:
                yield response.text
