"""Proveedor GPT-4o — usa Structured Outputs nativo de OpenAI (el SDK genera
el JSON Schema directo del modelo Pydantic y garantiza que la respuesta
cumpla ese esquema; no hace falta parsear texto libre ni validar a mano).
"""

from __future__ import annotations

import base64

from openai import OpenAI

from receipt_parser.models import ReceiptExtraction
from receipt_parser.prompts import VISION_SYSTEM_PROMPT
from receipt_parser.providers.base import VisionReceiptProvider


class OpenAIReceiptProvider(VisionReceiptProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def extract(self, image_bytes: bytes, mime_type: str) -> ReceiptExtraction:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"

        completion = self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Lee este ticket/recibo."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format=ReceiptExtraction,
            temperature=0.1,
        )

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI no devolvió una extracción estructurada válida.")
        return parsed
