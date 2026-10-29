"""Proveedor Gemini — usa `response_schema` (Structured Outputs del SDK de
Google) construido directamente desde el JSON Schema de Pydantic.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from receipt_parser.models import ReceiptExtraction
from receipt_parser.prompts import VISION_SYSTEM_PROMPT
from receipt_parser.providers.base import VisionReceiptProvider


class GeminiReceiptProvider(VisionReceiptProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(self, image_bytes: bytes, mime_type: str) -> ReceiptExtraction:
        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                "Lee este ticket/recibo.",
            ],
            config=types.GenerateContentConfig(
                system_instruction=VISION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ReceiptExtraction,
                temperature=0.1,
            ),
        )

        if response.parsed is None:
            raise RuntimeError("Gemini no devolvió una extracción estructurada válida.")
        return ReceiptExtraction.model_validate(response.parsed)
