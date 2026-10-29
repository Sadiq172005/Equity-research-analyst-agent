"""pipeline.py + extra sections -> equity_research_analyst.ipynb  (run: python build_notebook.py)"""
import re, nbformat as nbf
M, C = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
src = open("pipeline.py").read()
sections = dict(zip(*[iter(re.split(r"^# %% (.+)$", src, flags=re.M)[1:])] * 2))

nb = nbf.v4.new_notebook(); c = nb.cells
c += [M("""# AI Equity Research Analyst-in-a-Box — Capstone
**Problem:** Reading annual reports, broker notes, and macro news before forming a view on a stock is slow and
easy to get wrong under time pressure — a trader either skips the homework or over-trusts one signal (just the
chart, or just the story).
**Solution:** OCR the report -> deterministic fundamental + technical signal engines (code, not LLM guesses) ->
RAG-grounded macro-risk scan -> a synthesis step that escalates to a human analyst instead of auto-publishing
when the signals disagree -> an LLM writes the final narrative, under a hard guard that can't override the
deterministic flags.

**Contents:** 0 Setup · 1 Architecture · 2 Data · 3 Schemas · 4 OCR · 5 Extraction · 6 Deterministic signal
engines · 7 RAG · 8 Agents · 9 Orchestration · 10 Demo · 11 Evaluation · 12 API + UI · 13 Deployment ·
14 Limitations & next steps"""),
      M("## 0. Setup\nSystem packages (notebook ke bahar): `sudo apt install tesseract-ocr poppler-utils` (Mac: `brew install tesseract poppler`).\nPython: `pip install -e \".[all]\"` (pyproject.toml se) · `.env` mein `OPENAI_API_KEY` (`.env.example` copy karo)."),
      C("import shutil, os\nfrom dotenv import load_dotenv; load_dotenv()\nfor b in ['tesseract', 'pdftoppm']:\n    print(b, '✅' if shutil.which(b) else '❌ install karo')\nprint('OPENAI_API_KEY', '✅' if os.getenv('OPENAI_API_KEY') else '❌ .env mein set karo')"),
      M("""## 1. Architecture
```
Annual report (PDF/scan) --> OCR --> Extractor Agent (LLM -> structured metrics)
  --> Fundamental Agent (deterministic: Payers/Growers/Stragglers)
  --> Technical Agent (deterministic: EMA10/20 trend scan, ATR proxy)
  --> Macro-Risk Agent (deterministic keyword scan over RAG-retrieved context)
  --> Synthesis Agent (hard guard: conflict or missing data -> escalate, don't auto-publish)
  --> Advisor Agent (LLM narrative, can't override the guard) --> verdict/risks/actions/investor note
```
**Design decisions (same spirit as the GST copilot capstone):** (1) the actual trend/ratio **math runs in
code**, not as an LLM guess — the LLM only extracts fields and writes narrative; (2) if the three agents
disagree, or data is missing, the system routes to `REVIEW_REQUIRED` instead of letting the LLM pick a
confident side; (3) the advisor is hard-guarded: it cannot say `BUY` when a warning/error flag is present,
whatever the LLM returns."""),
      M("## 2. Data\n`data/macro_docs/` mein RBI policy notes, sector broker reports, concall transcripts (full checklist: `data/README.md`). Test annual reports: `python generate_samples.py`."),
      C("from pathlib import Path\ndocs = list(Path('data/macro_docs').glob('**/*'))\nprint(len(docs), 'docs:', [d.name for d in docs][:10])\nprint(len(list(Path('samples').glob('*.pdf'))), 'sample PDFs')")]

titles = ["Setup & Config", "Schemas", "OCR", "Extraction (LLM -> structured FinancialMetrics)",
         "Deterministic signal engines (LLM se nahi — numbers/trend code se check hote hain)",
         "RAG — macro / sector knowledge base (rate cycle, crude-gold, sector notes, concall commentary)",
         "Multi-Agent System (LangGraph): Extractor -> Fundamental/Technical/Macro -> Synthesis (hard guard) -> Advisor",
         "Orchestration — end-to-end"]
headers = {
    "Setup & Config": "### Config & LLM factory",
    "Schemas": "## 3. Schemas (Pydantic)",
    "OCR": "## 4. OCR\nDigital PDF → text layer (pdfplumber); scanned → pdf2image + Tesseract.",
    "Extraction (LLM -> structured FinancialMetrics)": "## 5. Structured extraction",
    "Deterministic signal engines (LLM se nahi — numbers/trend code se check hote hain)": "## 6. Deterministic signal engines (Fundamental + Technical + Macro-Risk)",
    "RAG — macro / sector knowledge base (rate cycle, crude-gold, sector notes, concall commentary)": "## 7. RAG over macro/sector knowledge base",
    "Multi-Agent System (LangGraph): Extractor -> Fundamental/Technical/Macro -> Synthesis (hard guard) -> Advisor": "## 8. Multi-agent system (LangGraph)",
    "Orchestration — end-to-end": "## 9. Orchestration",
}
for title in titles:
    code = sections[title].strip().replace('if __name__ == "__main__":', "if False:  # CLI — notebook mein skip")
    c += [M(headers[title]), C(code)]
    if title.startswith("Deterministic"):
        c += [M("**Offline demo — bina API key ke (pure deterministic code):**"),
              C("m = FinancialMetrics(revenue_cr=12500, net_profit_cr=2100, revenue_growth_yoy_pct=22,\n"
                "                     net_profit_growth_yoy_pct=28, operating_margin_pct=24, debt_to_equity=0.3)\n"
                "view, flags = classify_fundamentals(m)\n"
                "print(view)\n"
                "for f in flags: print(f.severity.upper().ljust(8), f.code.ljust(24), f.message)\n\n"
                "tview, tflags = compute_technical([100 + i * 3 for i in range(30)])\n"
                "print(tview)")]
    if title.startswith("RAG"):
        c += [M("Pehli baar index banao (docs badle to dobara):"),
              C("# build_index()   # uncomment — OpenAI embeddings use hote hain (cost: chhota, one-time)\n"
                "# rag_answer('How does a rising US 10-year yield typically affect IT services valuations?')")]

c += [M("## 10. End-to-end demo"),
      C("import json\n"
        "res = analyze_stock('samples/05_fundamentals_vs_macro_conflict.pdf',\n"
        "                    'US 10-year yield spiking on inflation fears, crude oil surging on geopolitical war risk, recession warnings, rate hike expectations.',\n"
        "                    '', 'SENTINEL', 'Give me a research view ahead of earnings',\n"
        "                    [1100 + i * 2 for i in range(25)])\n"
        "print(json.dumps(res['report'], indent=2, ensure_ascii=False))\n"
        "for f in res['flags']: print(f['severity'], f['code'], '-', f['message'])"),
      M("## 11. Evaluation\n`samples/expected.json` ke against verdict match (`python evaluate.py`). Deterministic-engine unit tests: `python test_validators.py`."),
      C("import json\nexp = json.load(open('samples/expected.json'))\nprices = json.load(open('samples/prices.json'))\nrows = []\n"
        "for f, e in exp.items():\n"
        "    r = analyze_stock(f'samples/{f}', e['macro_text'], '', e['ticker'], 'Give me a research view', prices[f])\n"
        "    got = r['report']['verdict']\n"
        "    rows.append((f, e['expected_verdict'], got, 'PASS' if got == e['expected_verdict'] else 'FAIL'))\n"
        "import pandas as pd; pd.DataFrame(rows, columns=['file', 'expected', 'got', 'result'])"),
      M("## 12. API + UI\n`uvicorn app:app --reload` → `/docs` · `streamlit run streamlit_app.py`. Endpoints: `/analyze`, `/analyze-batch`, `/ask`, `/reindex`, `/health`."),
      M("""## 13. Deployment (AWS)

**Simplest path — ECR + App Runner:**
```bash
aws ecr create-repository --repository-name equity-research-analyst --region ap-south-1
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.ap-south-1.amazonaws.com
docker build -t equity-research-analyst . && docker tag equity-research-analyst:latest <ACCOUNT>.dkr.ecr.ap-south-1.amazonaws.com/equity-research-analyst:latest
docker push <ACCOUNT>.dkr.ecr.ap-south-1.amazonaws.com/equity-research-analyst:latest
```
Console → **App Runner → Create service** → source: ECR image, port `8000`, env var `OPENAI_API_KEY`
(Secrets Manager se better), health check path `/health`, 1 vCPU / 2 GB.
Alternative: EC2 (t3.small) pe `docker run -p 80:8000 -e OPENAI_API_KEY=... <image>`.
Tip: `data/faiss_index` ko S3 pe rakho aur startup pe download karo taaki har deploy pe re-embed na ho.
Full commands: `README.md`."""),
      M("""## 14. Limitations & next steps
- ATR proxy is close-to-close (no OHLC) — swap in real OHLC data for a true ATR / relative volume read.
- Fundamental thresholds (D/E 1.5x, margin 10%, growth 15%) are fixed; make them sector-relative with `data/sector_benchmarks.csv`.
- Macro-risk scan is keyword-level; a dedicated macro-sentiment model would catch nuance keyword matching misses.
- RAG knowledge base needs real RBI/SEBI/broker documents in `data/macro_docs/` — the starter file is a placeholder.
- This is a research *assistant*, not SEBI-registered investment advice unless the operator holds a valid RA license — always disclose that clearly to end users.
- Handle PII (client watchlists, portfolio data) with the same care as the sample data note in `data/README.md`.""")]
nbf.write(nb, "equity_research_analyst.ipynb"); print("cells:", len(c))
