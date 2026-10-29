#!/usr/bin/env python3
"""CLI de ejemplo — procesa un ticket y muestra el resultado.

Uso:
    python cli.py samples/ticket_con_descuento.jpg
    python cli.py samples/ticket_con_descuento.jpg --provider gemini
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from receipt_parser.parser import ReceiptParser, build_default_parser


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Extrae datos estructurados de un ticket/recibo.")
    parser.add_argument("image_path", help="Ruta a la imagen del ticket.")
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        help="Sobrescribe RECEIPT_PARSER_PROVIDER solo para esta corrida.",
    )
    args = parser.parse_args()

    if args.provider:
        import os

        os.environ["RECEIPT_PARSER_PROVIDER"] = args.provider

    receipt_parser: ReceiptParser = build_default_parser()
    result = receipt_parser.parse_file(args.image_path)

    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
