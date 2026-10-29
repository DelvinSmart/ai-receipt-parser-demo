"""Esquema estructurado del recibo y la regla de negocio del total real.

La función `compute_total_real` es intencionalmente una función PURA, sin
ninguna dependencia de IA — es la misma regla de negocio que se usa para
validar/corregir lo que el modelo de visión devuelve, y se puede testear
sin gastar ni un solo token de API (ver tests/test_models.py).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal["fuel", "expense", "unknown"]


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_total_real(
    *,
    printed_total: Decimal | None,
    subtotal: Decimal | None,
    discount: Decimal | None,
) -> Decimal | None:
    """Calcula el monto final realmente pagado.

    Regla de oro (la misma que corrige el bug real de "subtotal confundido
    con total" en producción):

    1. Si el ticket trae un total FINAL impreso (ej. "Valor a pagar",
       "Valor Total", "Total a pagar") — ese es el número correcto. Ya
       viene con cualquier descuento restado; no se recalcula nada.
    2. Si NO hay un total final impreso pero sí hay subtotal y descuento
       por separado, el total real se calcula restando: subtotal - descuento.
    3. Si no hay descuento, el total es el subtotal (o el impreso).
    4. Si no hay ningún dato suficiente, devuelve None — nunca se inventa
       un número.

    El total real NUNCA puede ser el subtotal cuando existe un descuento:
    ese es exactamente el bug que esta función previene por diseño.
    """
    if printed_total is not None:
        return _round2(printed_total)

    if subtotal is not None:
        effective_discount = discount if discount is not None else Decimal("0")
        total = subtotal - effective_discount
        return _round2(max(total, Decimal("0")))

    return None


class ReceiptExtraction(BaseModel):
    """Salida estructurada que el modelo de visión (GPT-4o / Gemini) debe
    devolver — modo de extracción PASIVA: solo describe lo que ve en la
    imagen, nunca decide ni ejecuta nada por su cuenta (ver README,
    sección "Arquitectura de seguridad").
    """

    proveedor: str | None = Field(
        default=None,
        description="Nombre del comercio/proveedor impreso en el ticket, tal cual aparece.",
    )
    fecha: date | None = Field(
        default=None,
        description="Fecha del ticket (sin hora). None si no se puede leer con certeza.",
    )
    litros: Decimal | None = Field(
        default=None,
        description="Litros de combustible, si el ticket es de una gasolinera. None en cualquier otro caso.",
    )
    subtotal: Decimal | None = Field(
        default=None,
        description="Subtotal ANTES de descuentos, si el ticket lo muestra por separado.",
    )
    descuento: Decimal | None = Field(
        default=None,
        description="Monto del descuento aplicado, si el ticket lo muestra. None si no hay descuento.",
    )
    printed_total: Decimal | None = Field(
        default=None,
        description='Total FINAL impreso en el ticket (ej. junto a "Valor a pagar"/"Total"), si existe.',
    )
    categoria: Category = Field(
        default="unknown",
        description='"fuel" si es un ticket de combustible, "expense" para cualquier otro gasto, "unknown" si no es legible.',
    )

    @field_validator("litros", "subtotal", "descuento", "printed_total")
    @classmethod
    def _no_negativos(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("Los montos no pueden ser negativos.")
        return value

    @property
    def total_real(self) -> Decimal | None:
        """El monto final que la persona pagó de verdad — ver `compute_total_real`."""
        return compute_total_real(
            printed_total=self.printed_total,
            subtotal=self.subtotal,
            discount=self.descuento,
        )

    @model_validator(mode="after")
    def _descuento_no_mayor_que_subtotal(self) -> "ReceiptExtraction":
        if self.subtotal is not None and self.descuento is not None and self.descuento > self.subtotal:
            raise ValueError("El descuento no puede ser mayor que el subtotal.")
        return self


class ParsedReceipt(BaseModel):
    """Resultado final que el módulo expone a quien lo llama — incluye el
    `total_real` ya calculado, listo para usar, junto con los datos crudos
    extraídos por la IA para auditoría/depuración.
    """

    extraction: ReceiptExtraction
    total_real: Decimal | None
    provider: str

    @classmethod
    def from_extraction(cls, extraction: ReceiptExtraction, *, provider: str) -> "ParsedReceipt":
        return cls(extraction=extraction, total_real=extraction.total_real, provider=provider)
