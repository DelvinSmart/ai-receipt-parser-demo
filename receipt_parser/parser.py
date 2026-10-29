"""Punto de entrada principal del módulo — orquesta proveedor + validación.

Este es el único lugar que alguien que integra este módulo en una app real
necesita llamar. Todo lo demás (prompts, proveedores, el esquema) es detalle
de implementación.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from receipt_parser.models import ParsedReceipt
from receipt_parser.providers.base import VisionReceiptProvider


class ReceiptParser:
    """Fachada: recibe bytes de imagen, devuelve un `ParsedReceipt` validado.

    No escribe nada en ningún lado, no conoce bases de datos ni colas —
    es intencionalmente una caja de un solo propósito: imagen entra, datos
    estructurados salen. La aplicación que lo use decide qué hacer con el
    resultado (mostrarlo, pedir confirmación, guardarlo).
    """

    def __init__(self, provider: VisionReceiptProvider) -> None:
        self._provider = provider

    def parse_bytes(self, image_bytes: bytes, mime_type: str) -> ParsedReceipt:
        extraction = self._provider.extract(image_bytes, mime_type)
        return ParsedReceipt.from_extraction(extraction, provider=self._provider.name)

    def parse_file(self, path: str | Path) -> ParsedReceipt:
        file_path = Path(path)
        mime_type, _ = mimetypes.guess_type(file_path.name)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"'{file_path.name}' no parece ser una imagen (mime type: {mime_type}).")
        return self.parse_bytes(file_path.read_bytes(), mime_type)


def build_default_parser() -> ReceiptParser:
    """Arma el parser según `RECEIPT_PARSER_PROVIDER` del entorno — "openai" o
    "gemini". Lanza un error claro si falta la clave correspondiente, en vez
    de fallar más adelante con un error críptico de red.
    """
    provider_name = os.environ.get("RECEIPT_PARSER_PROVIDER", "openai").strip().lower()

    if provider_name == "openai":
        from receipt_parser.providers.openai_provider import OpenAIReceiptProvider

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Falta OPENAI_API_KEY en el entorno (ver .env.example).")
        return ReceiptParser(OpenAIReceiptProvider(api_key=api_key))

    if provider_name == "gemini":
        from receipt_parser.providers.gemini_provider import GeminiReceiptProvider

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Falta GEMINI_API_KEY en el entorno (ver .env.example).")
        return ReceiptParser(GeminiReceiptProvider(api_key=api_key))

    raise ValueError(f"RECEIPT_PARSER_PROVIDER desconocido: '{provider_name}' (usa 'openai' o 'gemini').")
