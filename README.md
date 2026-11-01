# AI Equity Research Analyst-in-a-Box

Upload an annual report / broker note (PDF or scan) → OCR → structured financial extraction → deterministic
Fundamental + Technical signal engines → RAG-grounded Macro-Risk scan → **verdict + key risks + action list +
subscriber digest message**.

## Architecture
```
Annual report (PDF/scan) → OCR (pdfplumber / Tesseract) → Extractor Agent (LLM → Pydantic FinancialMetrics)
  → Fundamental Agent (deterministic: Payers/Growers/Stragglers) → Technical Agent (deterministic: EMA10/20 trend, ATR proxy)
  → Macro-Risk Agent (deterministic keyword scan, RAG-grounded context) → Synthesis Agent (conflict/data-gap guard)
  → Advisor Agent (verdict, risks, actions, subscriber note)      [LangGraph StateGraph]
FastAPI: /analyze  /analyze-batch  /ask  /reindex  /health   →  Docker → AWS
```
Design choice: **trend/ratio math is checked in code, not by the LLM** — the LLM is only used for extraction and
for writing the macro explanation and narrative. The Advisor can only return "BUY" when no warning/error flag is
present, and if the agents disagree with each other the system escalates on its own to `REVIEW_REQUIRED`
(a hard guard).

## Quick start (pyproject)
```bash
cp .env.example .env            # add your OPENAI_API_KEY
make install samples test index eval
make api   # or: make ui
```
Data checklist: `data/README.md`. Regenerate the notebook: `python build_notebook.py`.

## Run locally
```bash
pip install -r requirements.txt          # + apt: tesseract-ocr poppler-utils
export OPENAI_API_KEY=sk-...
python test_validators.py                # offline tests (no key needed) — deterministic engines only
# add RBI policy notes, sector reports, and concall transcripts to data/macro_docs/
uvicorn app:app --reload                 # http://localhost:8000/docs
curl -F file=@samples/01_clean_grower_uptrend.pdf \
     -F ticker=ZENITH -F query="Give me a research view" \
     -F price_series='[1500,1504,1508,...]' \
     -F macro_text="Markets steady this week." \
     localhost:8000/analyze
curl -X POST localhost:8000/ask -H 'Content-Type: application/json' -d '{"question":"How does a rising US 10-year yield affect IT services valuations?"}'
```

## Samples + Streamlit UI
```bash
pip install -r requirements-dev.txt
python generate_samples.py               # writes 6 PDFs + 1 scanned PNG + prices.json + expected.json to samples/
streamlit run streamlit_app.py           # http://localhost:8501
```
| Sample | Expected |
|---|---|
| 01_clean_grower_uptrend | BUY |
| 02_margin_decline_straggler | AVOID |
| 03_high_leverage_payer | HOLD (HIGH_LEVERAGE warning blocks a clean BUY) |
| 04_fundamentals_vs_technical_conflict | REVIEW_REQUIRED (Bullish fundamentals vs Bearish technical) |
| 05_fundamentals_vs_macro_conflict | REVIEW_REQUIRED (Bullish fundamentals/technical vs Risk-Off macro) |
| 06_missing_financials | REVIEW_REQUIRED (FUNDAMENTALS_DATA_INCOMPLETE) |
| 07_scanned_clean.png | BUY (OCR path — same company as 01, scanned/blurred) |

The UI has 3 tabs: single stock (upload a file or pick a sample, with ticker/prices/macro inputs), batch
watchlist (CSV download), and Ask macro/sector. Enter a deployed API URL in the sidebar to point the same UI
at the AWS-hosted service instead of running the pipeline locally.

## AWS deployment (simplest: ECR + App Runner)
```bash
aws ecr create-repository --repository-name equity-research-analyst --region ap-south-1
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.ap-south-1.amazonaws.com
docker build -t equity-research-analyst . && docker tag equity-research-analyst:latest <ACCOUNT>.dkr.ecr.ap-south-1.amazonaws.com/equity-research-analyst:latest
docker push <ACCOUNT>.dkr.ecr.ap-south-1.amazonaws.com/equity-research-analyst:latest
```
Then in the Console go to **App Runner → Create service** → source: the ECR image, port `8000`, env var
`OPENAI_API_KEY` (better via Secrets Manager), health check path `/health`, 1 vCPU / 2 GB.
Alternative: a t3.small EC2 instance running `docker run -p 80:8000 -e OPENAI_API_KEY=... <image>`.
Tip: keep `data/faiss_index` in S3 and download it on startup so you don't re-embed on every deploy.

## Important notes
- Fundamental thresholds (D/E 1.5x, margin 10%, growth 15%) are fixed starting points, not sector-calibrated —
  see `data/README.md` for adding a sector-benchmark CSV.
- The technical engine uses a close-to-close ATR proxy; swap in real OHLCV data for a true ATR/relative-volume read.
- Rate-sensitivity and macro-flag logic (yield, crude, geopolitical terms) should be reviewed periodically — it's a
  keyword-level deterministic scan, not a trained sentiment model.
- This tool *assists* research; it is not SEBI-registered investment advice unless the operator holds a valid
  Research Analyst license — disclose that clearly if monetized.

## Demo script (capstone presentation)
1. Clean grower, uptrend → BUY. 2. Straggler, downtrend → AVOID. 3. Payer with high D/E → HOLD (flagged, not
blocked outright). 4. Strong fundamentals but a downtrend chart → REVIEW_REQUIRED (fundamentals vs. technical
conflict — the system refuses to guess). 5. Strong stock, but macro context loaded with yield/crude/war risk →
REVIEW_REQUIRED (macro overrides a clean BUY). 6. `/analyze-batch` → run a 2-3 stock watchlist and show the
summary counts.
