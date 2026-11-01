# data/ — what's needed here

## 1. `data/macro_docs/` (RAG knowledge base) — REQUIRED
Macro commentary, sector thematic reports, and RBI/SEBI policy notes. Both PDFs and .txt/.md work.
Use PDFs that have a text layer (not scanned) — otherwise retrieval quality will suffer.

| Document | Why it's needed |
|---|---|
| RBI Monetary Policy statements (latest + last 2-3) | Rate-cycle context for the macro-risk agent |
| Sector thematic broker reports (IT, BFSI, OMC, etc.) | Sector-level rationale beyond raw numbers |
| Concall transcripts (per company, per quarter) | Management commentary the Fundamental agent can cite |
| Macro commentary (crude, gold, DXY, 10Y yield) | Feeds the Macro-Risk agent's keyword/context scan |
| SEBI circulars relevant to research/advisory | If pursuing SEBI-RA registration for the product |

## 2. Optional (to improve accuracy)
- `data/sector_benchmarks.csv` — sector-average margins/D-E ratios, so flags can be relative to the sector
  instead of a single fixed threshold (currently the thresholds are hardcoded in `pipeline.py`'s `classify_fundamentals`).
- `data/ohlc/` — real OHLCV history per ticker, to replace the simplified close-only ATR proxy with a true ATR.

## 3. Generated (don't commit)
- `data/faiss_index/` — built by `make index`; rebuild it (`/reindex`) whenever the docs change.

## 4. Test data
- `samples/` — created by `python generate_samples.py` (synthetic annual-report-style PDFs; not real company financials).
- If you use real client/portfolio data, keep **masking/consent** in mind — this is a research-assist tool, not
  SEBI-registered advice unless you hold a valid RA license.
