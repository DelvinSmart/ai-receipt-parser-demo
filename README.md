# AI Receipt Parser Demo

Módulo en Python que extrae datos estructurados de tickets/facturas (fecha,
litros, subtotal, descuento, total real) usando modelos de visión (**GPT-4o**
o **Gemini**), con **Pydantic** como contrato de salida y una regla de
negocio determinística que decide el monto final — nunca el modelo de
lenguaje por su cuenta.

## El problema real que resuelve

El OCR tradicional (y, sin cuidado, también un modelo de visión) suele
confundir el **subtotal** con el **total** cuando un ticket trae un
descuento aplicado. Un ticket típico de gasolinera se ve así:

```
Subtotal ............ R$ 250,00
Descuento ............ R$  30,00
Valor a pagar ........ R$ 220,00
```

Un extractor ingenuo que solo busca la palabra "total" en el texto puede
terminar quedándose con el **Subtotal** (250,00) en vez del monto que la
persona pagó de verdad (220,00) — sobre todo cuando el subtotal, al ser el
número más grande, "gana" en cualquier heurística de desempate por valor.
Esto es exactamente el tipo de bug silencioso que no truena en ningún test
hasta que alguien nota que sus gastos no cuadran.

Este proyecto nació de corregir ese bug exacto en una app de producción
real, y lo reconstruye acá como una pieza de portafolio independiente,
aplicando el mismo principio con dos modelos de visión distintos.

### La regla de oro (ver `receipt_parser/models.py::compute_total_real`)

1. Si el ticket trae un **total final impreso** (ej. junto a "Valor a
   pagar", "Valor Total", "Total a pagar") — ese es el número correcto.
   Ya viene con el descuento restado; nunca se recalcula.
2. Si **no** hay un total final impreso, pero sí hay subtotal y descuento
   por separado, el total real se calcula explícitamente:
   `total_real = subtotal − descuento`.
3. Sin descuento, el total es el subtotal (o el impreso).
4. Sin datos suficientes, el resultado es `None` — el módulo nunca inventa
   un número.

Esta regla está escrita **dos veces a propósito**: una vez como instrucción
para el modelo de visión (`receipt_parser/prompts.py`), y otra vez como una
función Python pura y testeada (`compute_total_real`). El modelo es el
primer filtro, la función es la red de seguridad que lo corrige si se
equivoca. Los tests de esa función (`tests/test_models.py`) corren **sin
ninguna API key, sin red, sin IA** — la parte que más importa que esté bien
nunca depende de que un LLM "se porte bien" en cada corrida.

## Arquitectura de seguridad: IA en modo de extracción pasiva

Este módulo sigue un principio simple y no negociable:

> **La IA solo lee. Nunca decide, nunca ejecuta, nunca escribe.**

- `VisionReceiptProvider.extract()` (y sus implementaciones `OpenAIReceiptProvider`
  / `GeminiReceiptProvider`) **solo** devuelven un `ReceiptExtraction` —
  un objeto de datos. No tocan una base de datos, no llaman otra API de
  negocio, no deciden si algo "se guarda" o no.
- `ReceiptParser` (la fachada pública del módulo) es igual de pasivo: recibe
  bytes de una imagen, devuelve un `ParsedReceipt` validado. Punto.
- Toda decisión de negocio (¿esto se registra?, ¿hace falta un dato
  adicional del usuario como el kilometraje?, ¿hay que pedir confirmación?)
  es responsabilidad de la aplicación que **use** este módulo — nunca del
  módulo mismo. Esto es exactamente la separación que una app real necesita:
  la IA es un ayudante de lectura, el backend sigue siendo el único dueño
  de la lógica de negocio y las validaciones.
- Las salidas están tipadas y validadas con Pydantic (`ReceiptExtraction`):
  montos negativos, un descuento mayor que el subtotal, o una categoría
  fuera del enum esperado — todo eso falla explícito en la validación, en
  vez de colarse como un dato corrupto más adelante en el flujo.

## Estructura del proyecto

```
ai-receipt-parser-demo/
├── receipt_parser/
│   ├── models.py              # Esquema Pydantic + compute_total_real (la regla de negocio)
│   ├── prompts.py              # Prompt del sistema compartido por ambos proveedores
│   ├── parser.py               # Fachada pública: ReceiptParser, build_default_parser
│   └── providers/
│       ├── base.py             # Interfaz VisionReceiptProvider
│       ├── openai_provider.py  # GPT-4o + Structured Outputs nativo de OpenAI
│       └── gemini_provider.py  # Gemini + response_schema
├── tests/
│   └── test_models.py          # Tests de la regla de negocio (sin API key)
├── cli.py                      # Ejemplo de uso por línea de comandos
├── .env.example                # Variables de entorno necesarias (sin valores reales)
└── requirements.txt
```

## Instalación

```bash
git clone <este-repo>
cd ai-receipt-parser-demo
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env y completa OPENAI_API_KEY y/o GEMINI_API_KEY
```

## Uso

### Por línea de comandos

```bash
python cli.py samples/ticket_con_descuento.jpg
python cli.py samples/ticket_con_descuento.jpg --provider gemini
```

### Como módulo en tu propio código

```python
from dotenv import load_dotenv
load_dotenv()

from receipt_parser import build_default_parser

parser = build_default_parser()  # usa RECEIPT_PARSER_PROVIDER del .env
result = parser.parse_file("samples/ticket_con_descuento.jpg")

print(result.total_real)          # Decimal("220.00") — nunca el subtotal
print(result.extraction.categoria)  # "fuel"
print(result.provider)            # "openai" o "gemini"
```

## Tests

```bash
pytest tests/ -v
```

Los tests de `compute_total_real` y `ReceiptExtraction` corren sin ninguna
clave de API — validan la regla de negocio en aislamiento, independiente
de qué tan bien se porte el modelo de visión ese día.

## Decisiones de diseño

- **Dos proveedores, una interfaz.** `VisionReceiptProvider` es una
  interfaz mínima (`extract(image_bytes, mime_type) -> ReceiptExtraction`).
  Agregar un tercer proveedor (Claude, un modelo local, etc.) no toca nada
  del resto del módulo.
- **Pydantic como contrato, no como decoración.** El esquema no solo
  tipa los campos — valida invariantes de negocio reales (montos no
  negativos, descuento ≤ subtotal) directamente en el modelo.
- **La lógica crítica nunca depende de la IA para estar bien.**
  `compute_total_real` es una función pura, testeada, y es la que de
  verdad decide el número final — el modelo de visión solo le da los
  insumos.
