import os, json, shutil, tempfile
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from pydantic import BaseModel
from pipeline import analyze_stock, analyze_batch, rag_answer, build_index

app = FastAPI(title="AI Equity Research Analyst-in-a-Box", version="1.0")
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tiff"}


class Ask(BaseModel):
    question: str


class BatchItem(BaseModel):
    ticker: str
    query: str
    price_series: List[float]
    macro_text: str = ""
    concall_text: str = ""


def _save(f: UploadFile) -> str:
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type {ext}. Allowed: {sorted(ALLOWED)}")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    shutil.copyfileobj(f.file, tmp); tmp.close()
    return tmp.name


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(
    ticker: str = Form(...),
    query: str = Form(...),
    price_series: str = Form(..., description="JSON array of closing prices, e.g. [1500,1503,...]"),
    macro_text: str = Form(""),
    concall_text: str = Form(""),
    file: Optional[UploadFile] = File(None, description="Annual report / broker note PDF (optional)"),
):
    try:
        prices = json.loads(price_series)
    except json.JSONDecodeError:
        raise HTTPException(400, "price_series must be a JSON array of numbers.")
    path = _save(file) if file else None
    try:
        return analyze_stock(path, macro_text, concall_text, ticker, query, prices)
    finally:
        if path:
            os.unlink(path)


@app.post("/analyze-batch")
def analyze_batch_ep(items: List[BatchItem] = Body(...)):
    """Ek watchlist ke saare tickers ek saath — PDFs nahi, sirf price series + macro/concall text (daily run)."""
    results = analyze_batch([i.model_dump() for i in items])
    summary = {}
    for r in results:
        v = r.get("report", {}).get("verdict", "ERROR")
        summary[v] = summary.get(v, 0) + 1
    return {"summary": summary, "results": results}


@app.post("/ask")
def ask(body: Ask):
    return rag_answer(body.question)


@app.post("/reindex")
def reindex():
    build_index()
    return {"status": "reindexed"}
