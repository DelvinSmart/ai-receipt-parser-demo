"""Interfaz común de los proveedores de visión.

Cualquier proveedor nuevo (Claude, Mistral, un modelo local, etc.) solo
necesita implementar `extract(image_bytes, mime_type) -> ReceiptExtraction`
para funcionar con el resto del módulo — el `ReceiptParser` no sabe ni le
importa qué proveedor está usando.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from receipt_parser.models import ReceiptExtraction


class VisionReceiptProvider(ABC):
    """Modo de extracción PASIVA: implementaciones de esto SOLO leen la
    imagen y devuelven datos estructurados. Ninguna implementación debe
    escribir en una base de datos, llamar otra API de negocio, ni decidir
    nada por su cuenta — esa responsabilidad es siempre de quien llama.
    """

    name: str

    @abstractmethod
    def extract(self, image_bytes: bytes, mime_type: str) -> ReceiptExtraction:
        """Lee la imagen de un ticket/factura y devuelve los datos extraídos.

        Debe lanzar una excepción si la llamada al modelo falla — nunca
        debe devolver datos inventados en silencio.
        """
        raise NotImplementedError
