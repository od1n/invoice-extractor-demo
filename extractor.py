# ════════════════════════════════════════════════════════════════════════
# extractor.py — Invoice/receipt data extraction using Claude Vision
# Part of invoice-extractor-demo · MIT License
# ════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

import requests

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

PROMPT_INVOICE = """You are a meticulous data-entry specialist. Extract ALL data from this invoice,
receipt or delivery note. The document may be in English or Spanish, printed or scanned.

If the image is NOT an invoice/receipt or is unreadable, set "found": false and leave the rest null.

Rules:
- Missing or illegible fields -> null. Never invent values.
- Quantities and amounts -> numbers (no currency symbols, dot as decimal separator).
- Dates -> ISO format YYYY-MM-DD when possible.
- line_items: one entry per row in the items table.

Respond ONLY with the JSON, no explanations, no code fences:
{
  "found": true,
  "document_type": "invoice",
  "invoice_number": null,
  "date": null,
  "vendor": {"name": null, "tax_id": null, "address": null, "phone": null},
  "customer": {"name": null, "tax_id": null},
  "currency": null,
  "line_items": [
    {"description": null, "quantity": 0, "unit_price": 0, "total": 0}
  ],
  "subtotal": 0,
  "tax_rate": null,
  "tax_amount": 0,
  "total": 0,
  "payment_method": null,
  "notes": null
}"""

MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp",
}


def _clean_json(raw: str) -> dict:
    """Claude occasionally wraps JSON in code fences despite instructions — strip them."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def extract_invoice(image_bytes: bytes, filename: str = "doc.jpg") -> dict:
    """Send one image to Claude Vision and return the structured invoice data."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured (see .env.example)")

    media_type = MEDIA_TYPES.get(Path(filename).suffix.lower(), "image/jpeg")
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media_type,
                    "data": base64.b64encode(image_bytes).decode(),
                }},
                {"type": "text", "text": PROMPT_INVOICE},
            ],
        }],
    }
    resp = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"]
    return _clean_json(raw)


def validate(data: dict) -> list[str]:
    """Cheap arithmetic sanity checks — flags rows for human review instead of
    silently accepting wrong numbers. Returns a list of warnings."""
    warnings: list[str] = []
    if not data.get("found"):
        return ["Document not recognized as an invoice/receipt"]

    items = data.get("line_items") or []
    for i, it in enumerate(items, 1):
        q, p, t = it.get("quantity"), it.get("unit_price"), it.get("total")
        if all(isinstance(v, (int, float)) for v in (q, p, t)) and t:
            if abs(q * p - t) > max(0.05, t * 0.02):
                warnings.append(f"Row {i}: quantity x unit_price != total ({q} x {p} != {t})")

    subtotal = data.get("subtotal")
    line_sum = sum(it.get("total") or 0 for it in items)
    if isinstance(subtotal, (int, float)) and subtotal and items:
        if abs(line_sum - subtotal) > max(0.05, subtotal * 0.02):
            warnings.append(f"Sum of line items ({line_sum:.2f}) != subtotal ({subtotal:.2f})")

    total, tax = data.get("total"), data.get("tax_amount")
    if all(isinstance(v, (int, float)) for v in (subtotal, tax, total)) and total:
        if abs((subtotal + tax) - total) > max(0.05, total * 0.02):
            warnings.append(f"subtotal + tax ({subtotal + tax:.2f}) != total ({total:.2f})")

    return warnings
