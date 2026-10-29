"""Tests de la regla de negocio del total real — corren sin API key, sin red,
sin IA. Esto es a propósito: la parte que más importa que esté bien (cuánto
pagó la persona de verdad) nunca debería depender de que un modelo de
lenguaje "se porte bien" en cada corrida.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from receipt_parser.models import ReceiptExtraction, compute_total_real


class TestComputeTotalReal:
    def test_usa_el_total_impreso_cuando_existe(self) -> None:
        """Caso real que motivó este proyecto: el ticket trae Subtotal 250,00,
        Descuento 30,00 y Total 220,00 impreso. El resultado tiene que ser
        220,00 — nunca 250,00 (el bug clásico de "subtotal confundido con total")."""
        total = compute_total_real(
            printed_total=Decimal("220.00"),
            subtotal=Decimal("250.00"),
            discount=Decimal("30.00"),
        )
        assert total == Decimal("220.00")

    def test_calcula_restando_cuando_no_hay_total_impreso(self) -> None:
        total = compute_total_real(
            printed_total=None,
            subtotal=Decimal("250.00"),
            discount=Decimal("30.00"),
        )
        assert total == Decimal("220.00")

    def test_sin_descuento_el_total_es_el_subtotal(self) -> None:
        total = compute_total_real(printed_total=None, subtotal=Decimal("180.50"), discount=None)
        assert total == Decimal("180.50")

    def test_sin_datos_suficientes_devuelve_none(self) -> None:
        assert compute_total_real(printed_total=None, subtotal=None, discount=None) is None

    def test_nunca_devuelve_un_total_negativo(self) -> None:
        """Un descuento mayor al subtotal (dato inconsistente del OCR) no
        puede producir un total negativo — se clampa a 0."""
        total = compute_total_real(
            printed_total=None,
            subtotal=Decimal("100.00"),
            discount=Decimal("150.00"),
        )
        assert total == Decimal("0.00")


class TestReceiptExtraction:
    def test_total_real_es_una_propiedad_calculada(self) -> None:
        extraction = ReceiptExtraction(
            proveedor="Posto Exemplo",
            subtotal=Decimal("250.00"),
            descuento=Decimal("30.00"),
            categoria="fuel",
        )
        assert extraction.total_real == Decimal("220.00")

    def test_rechaza_montos_negativos(self) -> None:
        with pytest.raises(ValidationError):
            ReceiptExtraction(subtotal=Decimal("-10.00"))

    def test_rechaza_descuento_mayor_que_subtotal_en_la_entrada_del_modelo(self) -> None:
        """Validación a nivel de esquema: un modelo de visión que devuelva un
        descuento mayor que el subtotal está devolviendo datos inconsistentes
        — mejor fallar explícito que silenciosamente producir un total raro."""
        with pytest.raises(ValidationError):
            ReceiptExtraction(subtotal=Decimal("100.00"), descuento=Decimal("150.00"))
