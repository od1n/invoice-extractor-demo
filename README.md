# 📄 Invoice Extractor — AI Document Processing Demo

Turn invoices, receipts and delivery notes (photos, scans, PDFs-as-images) into **clean, validated, structured data** — exported to Excel/CSV or pushed into your system.

Built with **FastAPI + Claude Vision**. Handles printed and handwritten documents, in English and Spanish, any layout.

> 🎯 This is a public demo of my document-processing pipeline. The production version (in daily use at a manufacturing company since 2025) adds: database integration, ERP write-back, multi-document types (production sheets, purchase orders, customs/export documents), token-authenticated internal API, and multi-backend support (Claude / Groq / local Ollama).

## What it does

1. **Drop a batch of images** on the web UI (works from a phone on the same network — snap & upload).
2. Claude Vision reads each document like a careful human: vendor, tax IDs, dates, line items, taxes, totals.
3. **Arithmetic validation** flags anything suspicious (line totals that don't multiply out, subtotal/tax/total mismatches) for human review — no silent errors.
4. **Export to Excel or CSV**, one row per line item, ready for your accounting workflow.

## Why AI instead of classic OCR?

Classic OCR (Tesseract & co.) gives you *text*. This gives you *data*: it understands **any layout** without templates, reads handwriting, infers structure (which number is the tax, which is the total), and admits what it can't read (`null`, never invented values). Cost: ~$0.001–0.01 per document with Claude Haiku.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env       # add your ANTHROPIC_API_KEY
uvicorn main:app --port 8080
# open http://localhost:8080
```

## Sample output

```json
{
  "found": true,
  "invoice_number": "F-004512",
  "date": "2026-07-14",
  "vendor": {"name": "Distribuidora El Sol C.A.", "tax_id": "J-12345678-9"},
  "currency": "USD",
  "line_items": [
    {"description": "Resina PVC 6200B saco 25kg", "quantity": 40, "unit_price": 31.5, "total": 1260.0}
  ],
  "subtotal": 1260.0,
  "tax_rate": 16,
  "tax_amount": 201.6,
  "total": 1461.6
}
```

## Stack

FastAPI · Claude API (vision) · openpyxl · vanilla JS (zero frontend dependencies)

## Hire me

I build document-processing pipelines, workflow automation (n8n / Python) and AI integrations that run in production — not notebooks.

- 15+ years inside a real manufacturing/export operation: I know what messy paperwork looks like.
- Production systems in daily use: ERP with OCR digitization, multi-tenant SaaS, self-hosted automation.

📫 Contact: through my GitHub profile — freelance profiles coming soon.

## License

MIT — use it, learn from it, build on it.
