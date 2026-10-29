# %% Setup & Config
"""AI Equity Research Analyst-in-a-Box — OCR -> Extraction -> Deterministic Signals + RAG -> Multi-Agent (LangGraph)."""
import os, re, json, math
from pathlib import Path
from typing import List, Optional, TypedDict, Literal

from pydantic import BaseModel, Field

try:                                   # .env se OPENAI_API_KEY etc. load (optional)
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
DOCS_DIR = Path(os.getenv("MACRO_DOCS_DIR", "data/macro_docs"))
INDEX_DIR = Path(os.getenv("INDEX_DIR", "data/faiss_index"))
# OPENAI_API_KEY env var set karna zaroori hai (LLM + embeddings ke liye)


def get_llm():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=LLM_MODEL, temperature=0)


# %% Schemas
class FinancialMetrics(BaseModel):
    revenue_cr: Optional[float] = None
    net_profit_cr: Optional[float] = None
    eps: Optional[float] = None
    revenue_growth_yoy_pct: Optional[float] = None
    net_profit_growth_yoy_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    promoter_holding_pct: Optional[float] = None


class Flag(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    note: Optional[str] = None


class FundamentalView(BaseModel):
    classification: Literal["Grower", "Payer", "Straggler", "Unclassified"]
    stance: Literal["Bullish", "Neutral", "Bearish"]
    rationale: str


class TechnicalView(BaseModel):
    stance: Literal["Bullish", "Neutral", "Bearish", "Insufficient data"]
    trend: Optional[str] = None
    last_price: Optional[float] = None
    ema10: Optional[float] = None
    ema20: Optional[float] = None
    atr_proxy_pct: Optional[float] = None


class MacroView(BaseModel):
    stance: Literal["Risk-On", "Neutral", "Risk-Off"]
    flags: List[str] = []


class ResearchReport(BaseModel):
    verdict: Literal["BUY", "HOLD", "AVOID", "REVIEW_REQUIRED"]
    summary: str
    key_risks: List[str] = []
    action_items: List[str] = []
    investor_note: Optional[str] = None


# %% OCR
def ocr_document(path: str) -> str:
    """Annual report / broker note PDF (text-layer ya scanned) aur images dono handle karta hai."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        except Exception:
            pass
        if len(text.strip()) > 40:          # digital PDF — OCR ki zaroorat nahi
            return text
        from pdf2image import convert_from_path
        import pytesseract
        return "\n".join(pytesseract.image_to_string(im, config="--psm 6")
                         for im in convert_from_path(path, dpi=250))
    import pytesseract
    from PIL import Image, ImageOps
    im = ImageOps.grayscale(Image.open(path))
    return pytesseract.image_to_string(im, config="--psm 6")


def extract_financial_tables(path: str) -> List[List[List[str]]]:
    """Balance sheet / P&L table grids — raw text extraction column alignment ko mangle karta hai, isliye alag se."""
    if Path(path).suffix.lower() != ".pdf":
        return []
    import pdfplumber
    tables = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables += page.extract_tables()
    return tables


# %% Extraction (LLM -> structured FinancialMetrics)
EXTRACT_PROMPT = """You are an equity-research analyst extracting financial metrics from an Indian company's
annual report / broker-note text. Extract these fields: revenue_cr, net_profit_cr, eps, revenue_growth_yoy_pct,
net_profit_growth_yoy_pct, operating_margin_pct, debt_to_equity, promoter_holding_pct.
Rules: plain numbers only (no commas/currency/%); if a field is absent use null. Do NOT guess or compute a
figure that isn't stated or directly derivable from two stated numbers — copy what's printed.
REPORT TEXT:
{text}"""


def extract_financial_metrics(text: str) -> FinancialMetrics:
    llm = get_llm().with_structured_output(FinancialMetrics)
    return llm.invoke(EXTRACT_PROMPT.format(text=text[:12000]))


# %% Deterministic signal engines (LLM se nahi — numbers/trend code se check hote hain)
def classify_fundamentals(m: FinancialMetrics) -> tuple[FundamentalView, List[Flag]]:
    """Payers / Growers / Stragglers framework — pure arithmetic, LLM yahan involved nahi."""
    flags: List[Flag] = []

    if m.revenue_cr is None and m.net_profit_cr is None:
        flags.append(Flag(code="FUNDAMENTALS_DATA_INCOMPLETE", severity="error",
                          message="Revenue aur net profit dono extract nahi hue — extraction/OCR quality check karo.",
                          note="Source PDF ka text layer ya scan quality verify karo."))
        return FundamentalView(classification="Unclassified", stance="Neutral",
                               rationale="Insufficient data to classify."), flags

    growth = m.revenue_growth_yoy_pct or 0.0
    if growth > 15:
        classification, stance = "Grower", "Bullish"
    elif m.net_profit_cr is not None and m.net_profit_cr > 0:
        classification, stance = "Payer", "Neutral"
    else:
        classification, stance = "Straggler", "Bearish"

    if m.debt_to_equity is not None and m.debt_to_equity > 1.5:
        flags.append(Flag(code="HIGH_LEVERAGE", severity="warning",
                          message=f"Debt-to-equity {m.debt_to_equity} is above the 1.5x comfort zone.",
                          note="Interest-rate sensitivity badh jaati hai; rate-cycle ke saath cross-check karo."))
    if m.net_profit_growth_yoy_pct is not None and m.net_profit_growth_yoy_pct < 0:
        flags.append(Flag(code="PROFIT_DECLINE", severity="warning",
                          message=f"Net profit YoY down {m.net_profit_growth_yoy_pct}% despite revenue trend.",
                          note="Margin compression ya one-off expense check karo concall notes mein."))
    if m.operating_margin_pct is not None and m.operating_margin_pct < 10:
        flags.append(Flag(code="LOW_MARGIN", severity="warning",
                          message=f"Operating margin {m.operating_margin_pct}% is thin for a comfortable safety buffer."))
    if m.promoter_holding_pct is not None and m.promoter_holding_pct < 30:
        flags.append(Flag(code="LOW_PROMOTER_HOLDING", severity="info",
                          message=f"Promoter holding {m.promoter_holding_pct}% is on the lower side — check pledge data separately."))

    rationale = f"Revenue growth YoY {growth}%, net profit {m.net_profit_cr} Cr, op. margin {m.operating_margin_pct}%."
    return FundamentalView(classification=classification, stance=stance, rationale=rationale), flags


def _ema(values: List[float], period: int) -> float:
    """Standard exponential moving average (not a plain rolling mean)."""
    alpha = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def compute_technical(prices: List[float]) -> tuple[TechnicalView, List[Flag]]:
    """Minervini-style trend scan: price vs 10/20-period EMA + a close-to-close ATR proxy.
    Needs real daily closes >=20; for true ATR use OHLC data in production, this is a simplified proxy."""
    flags: List[Flag] = []
    if len(prices) < 20:
        flags.append(Flag(code="INSUFFICIENT_PRICE_DATA", severity="error",
                          message=f"Only {len(prices)} closing prices given; need >=20 for a trend read.",
                          note="Fetch more history from the market data provider before scoring technicals."))
        return TechnicalView(stance="Insufficient data"), flags

    ema10 = _ema(prices[-20:], 10)
    ema20 = _ema(prices[-20:], 20)
    last = prices[-1]
    deltas = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    atr_proxy_pct = round(100 * (sum(deltas[-14:]) / min(14, len(deltas))) / last, 2) if last else None

    if last > ema10 > ema20:
        trend, stance = "Uptrend", "Bullish"
    elif last < ema10 < ema20:
        trend, stance = "Downtrend", "Bearish"
    else:
        trend, stance = "Sideways", "Neutral"

    if atr_proxy_pct is not None and atr_proxy_pct > 5:
        flags.append(Flag(code="HIGH_VOLATILITY", severity="warning",
                          message=f"Close-to-close ATR proxy is {atr_proxy_pct}% of price — wide daily swings.",
                          note="Size the position smaller / widen the stop accordingly."))

    return TechnicalView(stance=stance, trend=trend, last_price=round(last, 2),
                         ema10=round(ema10, 2), ema20=round(ema20, 2),
                         atr_proxy_pct=atr_proxy_pct), flags


RISK_TERMS = ["yield", "inflation", "geopolitical", "crude", "war", "sanctions", "rate hike",
              "recession", "default", "devaluation"]


def macro_risk_scan(context: str) -> tuple[MacroView, List[Flag]]:
    """Keyword-level deterministic scan over the RAG-retrieved macro context — not an LLM guess."""
    hits = sorted({t for t in RISK_TERMS if t in context.lower()})
    stance = "Risk-Off" if len(hits) >= 2 else ("Neutral" if hits else "Risk-On")
    flags: List[Flag] = []
    if stance == "Risk-Off":
        flags.append(Flag(code="MACRO_RISK_OFF", severity="warning",
                          message=f"Macro context flags {len(hits)} risk terms: {', '.join(hits)}.",
                          note="Event risk — consider waiting for the catalyst to pass before sizing up."))
    return MacroView(stance=stance, flags=hits), flags


# %% RAG — macro / sector knowledge base (rate cycle, crude-gold, sector notes, concall commentary)
def build_index(docs_dir: Path = DOCS_DIR, index_dir: Path = INDEX_DIR):
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings

    docs = []
    for f in Path(docs_dir).glob("**/*"):
        if f.suffix.lower() == ".pdf":
            docs += PyPDFLoader(str(f)).load()
        elif f.suffix.lower() in {".txt", ".md"}:
            docs += TextLoader(str(f), encoding="utf-8").load()
    if not docs:
        raise RuntimeError(f"{docs_dir} khaali hai — macro notes/sector reports/concall transcripts yahan daalo.")
    chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150).split_documents(docs)
    vs = FAISS.from_documents(chunks, OpenAIEmbeddings(model=EMBED_MODEL))
    vs.save_local(str(index_dir))
    return vs


_VS = None


def get_retriever(k: int = 4):
    global _VS
    if _VS is None:
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings
        if Path(INDEX_DIR).exists():
            _VS = FAISS.load_local(str(INDEX_DIR), OpenAIEmbeddings(model=EMBED_MODEL), allow_dangerous_deserialization=True)
        else:
            _VS = build_index()
    return _VS.as_retriever(search_kwargs={"k": k})


def rag_answer(question: str) -> dict:
    docs = get_retriever().invoke(question)
    ctx = "\n\n".join(f"[{i+1}] ({d.metadata.get('source','?')} p{d.metadata.get('page','-')}) {d.page_content}" for i, d in enumerate(docs))
    msg = ("Answer the markets/macro question ONLY from the context. Cite sources like [1]. "
           "If context insufficient, say so — don't guess.\n\nCONTEXT:\n" + ctx + f"\n\nQUESTION: {question}")
    return {"answer": get_llm().invoke(msg).content,
            "sources": [{"source": d.metadata.get("source"), "page": d.metadata.get("page")} for d in docs]}


def get_relevant_context(docs: List[str], query: str, k: int = 4) -> str:
    """Lightweight retrieval over ad-hoc text blobs (macro news + concall notes passed in the request)
    for the macro_risk_agent — separate from the persistent FAISS index above, which holds the curated
    knowledge base used by rag_answer()/the /ask endpoint."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100).split_text("\n".join(docs))
    if not chunks:
        return ""
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings
        from langchain_community.vectorstores import FAISS
        store = FAISS.from_texts(chunks, OpenAIEmbeddings(model=EMBED_MODEL))
        return "\n---\n".join(d.page_content for d in store.similarity_search(query, k=k))
    # offline fallback: TF-IDF cosine similarity, no API key needed
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    vec = TfidfVectorizer().fit(chunks)
    sims = cosine_similarity(vec.transform([query]), vec.transform(chunks))[0]
    top = sims.argsort()[::-1][:k]
    return "\n---\n".join(chunks[i] for i in top)


# %% Multi-Agent System (LangGraph): Extractor -> Fundamental/Technical/Macro -> Synthesis (hard guard) -> Advisor
class State(TypedDict, total=False):
    ticker: str
    query: str
    file_path: Optional[str]
    raw_text: str
    metrics: dict
    price_series: List[float]
    macro_text: str
    concall_text: str
    rag_context: str
    fundamental_view: dict
    technical_view: dict
    macro_view: dict
    flags: List[dict]
    conflict_flag: bool
    report: dict


def extractor_agent(s: State) -> State:
    text = s.get("raw_text") or (ocr_document(s["file_path"]) if s.get("file_path") else "")
    metrics = extract_financial_metrics(text).model_dump() if text.strip() else FinancialMetrics().model_dump()
    docs = [text, s.get("macro_text", ""), s.get("concall_text", "")]
    ctx = get_relevant_context(docs, s["query"]) if any(docs) else ""
    return {"raw_text": text, "metrics": metrics, "rag_context": ctx}


def fundamental_agent(s: State) -> State:
    view, flags = classify_fundamentals(FinancialMetrics(**s["metrics"]))
    return {"fundamental_view": view.model_dump(), "flags": s.get("flags", []) + [f.model_dump() for f in flags]}


def technical_agent(s: State) -> State:
    view, flags = compute_technical(s.get("price_series", []))
    return {"technical_view": view.model_dump(), "flags": s.get("flags", []) + [f.model_dump() for f in flags]}


def macro_risk_agent(s: State) -> State:
    view, flags = macro_risk_scan(s.get("rag_context", "") + " " + s.get("macro_text", ""))
    return {"macro_view": view.model_dump(), "flags": s.get("flags", []) + [f.model_dump() for f in flags]}


def synthesis_agent(s: State) -> State:
    """Hard guard, decided in code — not by the LLM: if the three agents actively disagree, or if data
    was missing, the system does not let the advisor publish a confident BUY/AVOID on its own say-so."""
    stances = [s["fundamental_view"]["stance"], s["technical_view"]["stance"], s["macro_view"]["stance"]]
    bullish = sum(1 for x in stances if x in ("Bullish", "Risk-On"))
    bearish = sum(1 for x in stances if x in ("Bearish", "Risk-Off"))
    conflict = bullish > 0 and bearish > 0
    return {"conflict_flag": conflict}


def route_after_synthesis(s: State) -> str:
    has_error = any(f["severity"] == "error" for f in s.get("flags", []))
    return "flag_for_review" if (s["conflict_flag"] or has_error) else "report_generator"


def flag_for_review(s: State) -> State:
    return {"report": {
        "verdict": "REVIEW_REQUIRED",
        "summary": (f"{s['ticker']}: agents/data don't agree cleanly — "
                    f"Fundamental={s['fundamental_view']['stance']}, Technical={s['technical_view']['stance']}, "
                    f"Macro={s['macro_view']['stance']}. Escalated to a human analyst rather than auto-publishing."),
        "key_risks": [f["message"] for f in s.get("flags", []) if f["severity"] in ("error", "warning")],
        "action_items": ["Human analyst review before any position sizing."],
        "investor_note": None,
    }}


ADVISOR_PROMPT = """You are a senior Indian equity research analyst. Write in simple Hinglish.
Given the ticker, fundamental/technical/macro views and risk flags (all already computed deterministically —
do not recompute or contradict their stances), produce JSON with keys:
verdict ("BUY" | "HOLD" | "AVOID"), summary (2-3 lines), key_risks (list), action_items (list, most urgent first),
investor_note (a short 1-2 line message suitable for a subscriber Telegram/WhatsApp digest).
Do not invent numbers beyond what's given. Return ONLY JSON.

TICKER: {ticker}
FUNDAMENTAL: {fundamental}
TECHNICAL: {technical}
MACRO: {macro}
FLAGS: {flags}"""


def report_generator(s: State) -> State:
    resp = get_llm().invoke(ADVISOR_PROMPT.format(
        ticker=s["ticker"], fundamental=json.dumps(s["fundamental_view"]),
        technical=json.dumps(s["technical_view"]), macro=json.dumps(s["macro_view"]),
        flags=json.dumps(s.get("flags", []))))
    txt = re.sub(r"^```(?:json)?|```$", "", resp.content.strip(), flags=re.M).strip()
    try:
        rep = json.loads(txt)
    except json.JSONDecodeError:
        rep = {"verdict": "HOLD", "summary": txt[:400], "key_risks": [], "action_items": [], "investor_note": None}
    # Hard guard: koi warning/error flag ho to LLM "BUY" nahi keh sakta
    if any(f["severity"] in ("error", "warning") for f in s.get("flags", [])) and rep.get("verdict") == "BUY":
        rep["verdict"] = "HOLD"
    return {"report": rep}


def build_graph():
    from langgraph.graph import StateGraph, END
    g = StateGraph(State)
    g.add_node("extractor", extractor_agent)
    g.add_node("fundamental", fundamental_agent)
    g.add_node("technical", technical_agent)
    g.add_node("macro", macro_risk_agent)
    g.add_node("synthesis", synthesis_agent)
    g.add_node("flag_for_review", flag_for_review)
    g.add_node("report_generator", report_generator)
    g.set_entry_point("extractor")
    g.add_edge("extractor", "fundamental")
    g.add_edge("fundamental", "technical")
    g.add_edge("technical", "macro")
    g.add_edge("macro", "synthesis")
    g.add_conditional_edges("synthesis", route_after_synthesis,
                            {"flag_for_review": "flag_for_review", "report_generator": "report_generator"})
    g.add_edge("flag_for_review", END)
    g.add_edge("report_generator", END)
    return g.compile()


# %% Orchestration — end-to-end
_GRAPH = None


def analyze_stock(file_path: Optional[str], macro_text: str, concall_text: str,
                   ticker: str, query: str, price_series: List[float]) -> dict:
    global _GRAPH
    _GRAPH = _GRAPH or build_graph()
    out = _GRAPH.invoke({
        "ticker": ticker, "query": query, "file_path": file_path,
        "macro_text": macro_text, "concall_text": concall_text, "price_series": price_series,
    })
    return {"ticker": ticker, "metrics": out["metrics"], "fundamental_view": out["fundamental_view"],
            "technical_view": out["technical_view"], "macro_view": out["macro_view"],
            "flags": out.get("flags", []), "report": out["report"]}


def analyze_batch(requests: List[dict]) -> List[dict]:
    """Ek watchlist ke saare tickers ek saath (daily batch run)."""
    out = []
    for r in requests:
        out.append(analyze_stock(r.get("file_path"), r.get("macro_text", ""), r.get("concall_text", ""),
                                 r["ticker"], r["query"], r["price_series"]))
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(analyze_stock(sys.argv[1] if len(sys.argv) > 1 else None, "", "",
                                   "DEMO", "Give me a research view", [100 + i for i in range(25)]),
                     indent=2, ensure_ascii=False))
