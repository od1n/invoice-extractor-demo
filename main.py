# ════════════════════════════════════════════════════════════════════════
# main.py — Invoice Extractor Demo (FastAPI + Claude Vision)
# Run:   uvicorn main:app --port 8080 --reload
# Open:  http://localhost:8080
# ════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import io
import json
from datetime import datetime

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

import extractor

app = FastAPI(title="Invoice Extractor Demo", version="1.0")

# In-memory batch for the demo session (no database needed)
BATCH: list[dict] = []

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Invoice Extractor — Claude Vision</title>
<style>
 :root{color-scheme:light dark}
 body{font-family:system-ui,sans-serif;max-width:880px;margin:2rem auto;padding:0 1rem}
 h1{font-size:1.4rem} .muted{opacity:.7;font-size:.9rem}
 .drop{border:2px dashed #888;border-radius:12px;padding:2.5rem;text-align:center;cursor:pointer;margin:1rem 0}
 .drop.over{border-color:#4a7;background:rgba(70,170,120,.08)}
 table{border-collapse:collapse;width:100%;font-size:.85rem;margin-top:1rem}
 td,th{border:1px solid #8884;padding:.35rem .5rem;text-align:left}
 .warn{color:#c60;font-size:.85rem}
 .ok{color:#4a7}
 button{padding:.5rem 1rem;border-radius:8px;border:1px solid #888;cursor:pointer;margin-right:.5rem}
 #spin{display:none}
</style></head><body>
<h1>📄 Invoice Extractor <span class="muted">— AI-powered, batch-ready</span></h1>
<p class="muted">Drop invoice/receipt images below. Data is extracted with Claude Vision,
validated arithmetically, and exportable to Excel/CSV. Demo by Jacques — automation &amp; AI integration developer.</p>
<div class="drop" id="drop">Drop images here or click to select<br>
 <input type="file" id="file" accept="image/*" multiple style="display:none"></div>
<p id="spin">⏳ Extracting…</p>
<div id="out"></div>
<p><button onclick="location.href='/api/export/xlsx'">⬇ Export Excel</button>
 <button onclick="location.href='/api/export/csv'">⬇ Export CSV</button>
 <button onclick="fetch('/api/clear',{method:'POST'}).then(()=>render([]))">Clear batch</button></p>
<script>
const drop=document.getElementById('drop'),file=document.getElementById('file'),
      out=document.getElementById('out'),spin=document.getElementById('spin');
drop.onclick=()=>file.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add('over')};
drop.ondragleave=()=>drop.classList.remove('over');
drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');send(e.dataTransfer.files)};
file.onchange=()=>send(file.files);
async function send(files){
  spin.style.display='block';
  for(const f of files){
    const fd=new FormData();fd.append('file',f);
    await fetch('/api/extract',{method:'POST',body:fd});
  }
  const r=await fetch('/api/batch');render(await r.json());
  spin.style.display='none';
}
function render(rows){
  if(!rows.length){out.innerHTML='';return}
  let h='<table><tr><th>#</th><th>Invoice</th><th>Date</th><th>Vendor</th><th>Total</th><th>Checks</th></tr>';
  rows.forEach((r,i)=>{const d=r.data;
    h+=`<tr><td>${i+1}</td><td>${d.invoice_number??'—'}</td><td>${d.date??'—'}</td>
        <td>${d.vendor?.name??'—'}</td><td>${d.total??'—'} ${d.currency??''}</td>
        <td>${r.warnings.length?'<span class=warn>⚠ '+r.warnings.join('; ')+'</span>':'<span class=ok>✓ ok</span>'}</td></tr>`});
  out.innerHTML=h+'</table>';
}
fetch('/api/batch').then(r=>r.json()).then(render);
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return PAGE


@app.post("/api/extract")
async def api_extract(file: UploadFile = File(...)) -> JSONResponse:
    content = await file.read()
    try:
        data = extractor.extract_invoice(content, file.filename or "doc.jpg")
    except Exception as exc:  # surface extraction errors to the UI, don't crash the batch
        return JSONResponse({"error": str(exc)}, status_code=502)
    entry = {
        "filename": file.filename,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "data": data,
        "warnings": extractor.validate(data),
    }
    BATCH.append(entry)
    return JSONResponse(entry)


@app.get("/api/batch")
def api_batch() -> list[dict]:
    return BATCH


@app.post("/api/clear")
def api_clear() -> dict:
    BATCH.clear()
    return {"ok": True}


def _flat_rows() -> list[dict]:
    """One row per line item, with invoice header repeated — the shape accountants want."""
    rows = []
    for e in BATCH:
        d = e["data"]
        base = {
            "file": e["filename"],
            "invoice_number": d.get("invoice_number"),
            "date": d.get("date"),
            "vendor": (d.get("vendor") or {}).get("name"),
            "vendor_tax_id": (d.get("vendor") or {}).get("tax_id"),
            "currency": d.get("currency"),
            "subtotal": d.get("subtotal"),
            "tax_amount": d.get("tax_amount"),
            "total": d.get("total"),
            "warnings": "; ".join(e["warnings"]),
        }
        items = d.get("line_items") or [{}]
        for it in items:
            rows.append({**base,
                         "item": it.get("description"),
                         "quantity": it.get("quantity"),
                         "unit_price": it.get("unit_price"),
                         "line_total": it.get("total")})
    return rows


@app.get("/api/export/csv")
def export_csv() -> StreamingResponse:
    import csv
    rows = _flat_rows()
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=invoices.csv"})


@app.get("/api/export/xlsx")
def export_xlsx() -> StreamingResponse:
    from openpyxl import Workbook
    rows = _flat_rows()
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    if rows:
        ws.append(list(rows[0].keys()))
        for r in rows:
            ws.append(list(r.values()))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=invoices.xlsx"})
