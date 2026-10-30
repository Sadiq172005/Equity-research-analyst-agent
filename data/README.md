# data/ — kya kya chahiye

## 1. `data/macro_docs/` (RAG knowledge base) — ZAROORI
Macro commentary, sector thematic reports, and RBI/SEBI policy notes. PDFs ya .txt/.md dono chalenge.
Text-layer wale PDFs lo (scanned nahi) — warna retrieval kharab hoga.

| Document | Kyun chahiye |
|---|---|
| RBI Monetary Policy statements (latest + last 2-3) | Rate-cycle context for the macro-risk agent |
| Sector thematic broker reports (IT, BFSI, OMC, etc.) | Sector-level rationale beyond raw numbers |
| Concall transcripts (per company, per quarter) | Management commentary the Fundamental agent can cite |
| Macro commentary (crude, gold, DXY, 10Y yield) | Feeds the Macro-Risk agent's keyword/context scan |
| SEBI circulars relevant to research/advisory | If pursuing SEBI-RA registration for the product |

## 2. Optional (accuracy badhane ke liye)
- `data/sector_benchmarks.csv` — sector-average margins/D-E ratios, so flags can be relative to sector not a
  single fixed threshold (abhi fixed thresholds hardcoded hain in `pipeline.py`'s `classify_fundamentals`).
- `data/ohlc/` — real OHLCV history per ticker, to replace the simplified close-only ATR proxy with a true ATR.

## 3. Generated (commit mat karo)
- `data/faiss_index/` — `make index` se banta hai; docs badle to dobara build karo (`/reindex`).

## 4. Test data
- `samples/` — `python generate_samples.py` (synthetic annual-report-style PDFs; real company financials nahi hain).
- Real client/portfolio data use karo to **masking/consent** dhyan mein rakho — ye research assist tool hai, not
  SEBI-registered advice unless you hold a valid RA license.
