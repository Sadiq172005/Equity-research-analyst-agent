"""Streamlit UI — run: streamlit run streamlit_app.py
Default: pipeline direct import. Sidebar mein API URL do to deployed FastAPI (AWS) use karega."""
import os, json, tempfile
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Equity Research Analyst-in-a-Box", page_icon="\U0001F4C8", layout="wide")

VERDICT_UI = {"BUY": ("✅ BUY", "success"), "HOLD": ("⚠️ HOLD", "warning"),
             "AVOID": ("⛔ AVOID", "error"), "REVIEW_REQUIRED": ("\U0001F501 REVIEW REQUIRED", "info")}
SEV_ICON = {"error": "\U0001F534 error", "warning": "\U0001F7E0 warning", "info": "\U0001F535 info"}

with st.sidebar:
    st.title("\U0001F4C8 Equity Research Copilot")
    api_url = st.text_input("API URL (optional)", placeholder="http://<app-runner-url>", help="Khaali = local pipeline use hoga")
    if not api_url and not os.getenv("OPENAI_API_KEY"):
        key = st.text_input("OPENAI_API_KEY", type="password")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    st.caption("Sample annual reports `samples/` folder mein hain (python generate_samples.py).")


def run_analyze(name: str, data: bytes | None, ticker: str, query: str, prices: list, macro_text: str, concall_text: str) -> dict:
    if api_url:
        import requests
        files = {"file": (name, data)} if data else None
        r = requests.post(api_url.rstrip("/") + "/analyze", data={
            "ticker": ticker, "query": query, "price_series": json.dumps(prices),
            "macro_text": macro_text, "concall_text": concall_text,
        }, files=files, timeout=180)
        r.raise_for_status()
        return r.json()
    from pipeline import analyze_stock
    path = None
    if data:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(name).suffix) as f:
            f.write(data); path = f.name
    try:
        return analyze_stock(path, macro_text, concall_text, ticker, query, prices)
    finally:
        if path:
            os.unlink(path)


def render(res: dict):
    rep, flags = res["report"], res["flags"]
    label, kind = VERDICT_UI.get(rep.get("verdict"), (rep.get("verdict", "?"), "info"))
    getattr(st, kind)(f"**{label}** — {rep.get('summary', '')}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Errors", sum(f["severity"] == "error" for f in flags))
    c2.metric("Warnings", sum(f["severity"] == "warning" for f in flags))
    c3.metric("Technical stance", res.get("technical_view", {}).get("stance", "-"))
    if flags:
        st.subheader("Risk flags")
        st.dataframe(pd.DataFrame([{"Severity": SEV_ICON[f["severity"]], "Code": f["code"], "Message": f["message"],
                                    "Note": f.get("note") or ""} for f in flags]), width="stretch", hide_index=True)
    else:
        st.success("Deterministic checks mein koi flag nahi mila.")
    if rep.get("key_risks"):
        st.subheader("Key risks")
        for r in rep["key_risks"]:
            st.markdown(f"- {r}")
    if rep.get("action_items"):
        st.subheader("Action items")
        for a in rep["action_items"]:
            st.markdown(f"- {a}")
    if rep.get("investor_note"):
        st.subheader("Subscriber digest message")
        st.code(rep["investor_note"], language=None)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Fundamental"); st.json(res.get("fundamental_view", {}))
    with c2:
        st.caption("Technical"); st.json(res.get("technical_view", {}))
    with c3:
        st.caption("Macro"); st.json(res.get("macro_view", {}))
    with st.expander("Extracted financial metrics"):
        st.json(res.get("metrics", {}))


tab1, tab2, tab3 = st.tabs(["\U0001F4C4 Single stock", "\U0001F4DA Batch (watchlist)", "\U0001F4AC Ask macro/sector"])

with tab1:
    up = st.file_uploader("Annual report / broker note (PDF/PNG/JPG, optional)", type=["pdf", "png", "jpg", "jpeg"], key="one")
    samples = sorted(Path("samples").glob("*.[pP][dD][fF]")) + sorted(Path("samples").glob("*.png"))
    pick = st.selectbox("...ya sample chuno", ["—"] + [p.name for p in samples])
    ticker = st.text_input("Ticker", value="DEMO")
    query = st.text_input("Research question", value="Give me a research view on this stock ahead of earnings")
    price_text = st.text_area("Closing prices (comma-separated, oldest first, >=20 values)",
                              value=", ".join(str(100 + i) for i in range(25)))
    macro_text = st.text_area("Macro/news context", value="Markets steady, no major catalysts this week.")
    concall_text = st.text_area("Concall notes (optional)", value="")
    if st.button("Analyze", type="primary"):
        name, data = None, None
        if up:
            name, data = up.name, up.getvalue()
        elif pick != "—":
            name, data = pick, (Path("samples") / pick).read_bytes()
        try:
            prices = [float(x.strip()) for x in price_text.split(",") if x.strip()]
            with st.spinner("OCR → extraction → fundamental/technical/macro signals → synthesis → advice..."):
                render(run_analyze(name, data, ticker, query, prices, macro_text, concall_text))
        except Exception as e:
            st.error(f"Failed: {e}")

with tab2:
    st.caption("Watchlist ke multiple tickers ek saath — PDFs nahi, sirf price series + macro text (daily run).")
    n = st.number_input("Kitne tickers?", min_value=1, max_value=10, value=2)
    items = []
    for i in range(int(n)):
        with st.expander(f"Ticker {i+1}", expanded=(i == 0)):
            t = st.text_input("Ticker", key=f"t{i}", value=f"STOCK{i+1}")
            p = st.text_area("Prices (comma-separated)", key=f"p{i}", value=", ".join(str(100 + j) for j in range(25)))
            m = st.text_area("Macro text", key=f"m{i}", value="Markets steady, no major catalysts this week.")
            items.append({"ticker": t, "query": "Give me a research view", "macro_text": m, "concall_text": "",
                         "price_series": [float(x.strip()) for x in p.split(",") if x.strip()]})
    if st.button("Analyze all"):
        with st.spinner("Running batch..."):
            if api_url:
                import requests
                r = requests.post(api_url.rstrip("/") + "/analyze-batch", json=items, timeout=180)
                r.raise_for_status(); out = r.json()
                results = out["results"]
            else:
                from pipeline import analyze_batch
                results = analyze_batch(items)
        rows = [{"Ticker": r["ticker"], "Verdict": r["report"].get("verdict"),
                "Errors": sum(f["severity"] == "error" for f in r["flags"]),
                "Warnings": sum(f["severity"] == "warning" for f in r["flags"])} for r in results]
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "watchlist_batch_report.csv", "text/csv")
        for r in results:
            with st.expander(r["ticker"]):
                render(r)

with tab3:
    q = st.text_input("Macro/sector ka sawaal", placeholder="US yield rise se IT sector par kya asar hota hai?")
    if st.button("Ask") and q:
        with st.spinner("Searching macro/sector knowledge base..."):
            try:
                if api_url:
                    import requests
                    r = requests.post(api_url.rstrip("/") + "/ask", json={"question": q}, timeout=120); r.raise_for_status(); out = r.json()
                else:
                    from pipeline import rag_answer
                    out = rag_answer(q)
                st.markdown(out["answer"])
                st.caption("Sources: " + ", ".join(f"{s['source']} (p{s['page']})" for s in out["sources"]))
            except Exception as e:
                st.error(f"Failed: {e} — data/macro_docs/ mein docs daale hain?")
