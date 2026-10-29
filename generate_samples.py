"""Sample annual-report-style PDFs (+ one scanned PNG) — har ek mein alag research scenario.
Price series PDF mein nahi hota (market data se aata hai), isliye alag se prices.json mein.
Run: python generate_samples.py  ->  samples/*.pdf + samples/prices.json + samples/expected.json
"""
import json
import random
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

OUT = Path("samples"); OUT.mkdir(exist_ok=True)


def trend_prices(start: float, drift: float, seed: int, n: int = 30) -> list[float]:
    """Deterministic (seeded) synthetic closing-price series with a given per-day drift."""
    rnd = random.Random(seed)
    prices = [start]
    for _ in range(n - 1):
        noise = rnd.uniform(-1, 1) * (abs(drift) * 0.4 + 2)
        prices.append(round(max(1.0, prices[-1] + drift + noise), 2))
    return prices


def make(fname, *, company="Nimbus Industries Ltd", fy="FY26", revenue_cr=None, net_profit_cr=None, eps=None,
         revenue_growth_yoy_pct=None, net_profit_growth_yoy_pct=None, operating_margin_pct=None,
         debt_to_equity=None, promoter_holding_pct=None, blank=False):
    ss = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(OUT / fname), pagesize=A4, topMargin=36, bottomMargin=36)
    el = [Paragraph("ANNUAL REPORT — FINANCIAL HIGHLIGHTS (excerpt)", ss["Title"]),
          Paragraph(f"<b>{company}</b> — {fy}", ss["Normal"]), Spacer(1, 12)]
    if blank:
        el.append(Paragraph("(Financial statement pages not included in this excerpt — "
                             "image-only scan of the chairman's letter follows.)", ss["Normal"]))
        doc.build(el)
        return
    rows = [["Metric", "Value"],
            ["Revenue (Cr)", f"{revenue_cr:,.1f}" if revenue_cr is not None else "-"],
            ["Net Profit (Cr)", f"{net_profit_cr:,.1f}" if net_profit_cr is not None else "-"],
            ["EPS", f"{eps:.2f}" if eps is not None else "-"],
            ["Revenue Growth YoY (%)", f"{revenue_growth_yoy_pct}" if revenue_growth_yoy_pct is not None else "-"],
            ["Net Profit Growth YoY (%)", f"{net_profit_growth_yoy_pct}" if net_profit_growth_yoy_pct is not None else "-"],
            ["Operating Margin (%)", f"{operating_margin_pct}" if operating_margin_pct is not None else "-"],
            ["Debt to Equity", f"{debt_to_equity}" if debt_to_equity is not None else "-"],
            ["Promoter Holding (%)", f"{promoter_holding_pct}" if promoter_holding_pct is not None else "-"]]
    t = Table(rows, colWidths=[220, 150])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .5, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    el.append(t)
    doc.build(el)


SCENARIOS = {
    # fname: (pdf kwargs, prices, macro_text, expected_verdict, why)
    "01_clean_grower_uptrend.pdf": (
        dict(company="Zenith Software Ltd", revenue_cr=12500, net_profit_cr=2100, eps=42.5,
             revenue_growth_yoy_pct=22, net_profit_growth_yoy_pct=28, operating_margin_pct=24,
             debt_to_equity=0.3, promoter_holding_pct=55),
        trend_prices(1500, 4, seed=1), "Markets steady, no major catalysts this week.",
        "BUY", "Grower + Uptrend + clean macro, all agents agree"),
    "02_margin_decline_straggler.pdf": (
        dict(company="Orion Textiles Ltd", revenue_cr=3400, net_profit_cr=-120, eps=-3.1,
             revenue_growth_yoy_pct=-5, net_profit_growth_yoy_pct=-20, operating_margin_pct=6,
             debt_to_equity=1.0, promoter_holding_pct=45),
        trend_prices(400, -4, seed=2), "Markets steady, no major catalysts this week.",
        "AVOID", "Straggler + Downtrend, all agents agree bearish"),
    "03_high_leverage_payer.pdf": (
        dict(company="Coastal Power Ltd", revenue_cr=8900, net_profit_cr=650, eps=11.2,
             revenue_growth_yoy_pct=8, net_profit_growth_yoy_pct=5, operating_margin_pct=15,
             debt_to_equity=2.2, promoter_holding_pct=48),
        trend_prices(900, 0, seed=3), "Markets steady, no major catalysts this week.",
        "HOLD", "Payer but HIGH_LEVERAGE warning blocks a clean BUY"),
    "04_fundamentals_vs_technical_conflict.pdf": (
        dict(company="Vertex Pharma Ltd", revenue_cr=5600, net_profit_cr=980, eps=19.4,
             revenue_growth_yoy_pct=24, net_profit_growth_yoy_pct=30, operating_margin_pct=26,
             debt_to_equity=0.2, promoter_holding_pct=60),
        trend_prices(2200, -5, seed=4), "Markets steady, no major catalysts this week.",
        "REVIEW_REQUIRED", "Grower fundamentals (Bullish) vs Downtrend technical (Bearish) — conflict"),
    "05_fundamentals_vs_macro_conflict.pdf": (
        dict(company="Sentinel Auto Ltd", revenue_cr=7200, net_profit_cr=1100, eps=16.8,
             revenue_growth_yoy_pct=19, net_profit_growth_yoy_pct=21, operating_margin_pct=20,
             debt_to_equity=0.4, promoter_holding_pct=58),
        trend_prices(1100, 4, seed=5),
        "US 10-year yield spiking on inflation fears, crude oil surging on geopolitical sanctions and war risk, "
        "recession warnings from multiple desks, rate hike expectations rising.",
        "REVIEW_REQUIRED", "Grower + Uptrend (Bullish) vs Risk-Off macro (Bearish) — conflict"),
    "06_missing_financials.pdf": (
        dict(blank=True),
        trend_prices(1000, 1, seed=6), "Markets steady, no major catalysts this week.",
        "REVIEW_REQUIRED", "FUNDAMENTALS_DATA_INCOMPLETE — extraction found no revenue/profit"),
}

if __name__ == "__main__":
    exp = {}
    for fname, (kw, prices, macro, verdict, why) in SCENARIOS.items():
        make(fname, **kw)
        exp[fname] = {"expected_verdict": verdict, "expected_flags": why,
                      "macro_text": macro, "ticker": fname.split("_", 1)[1].replace(".pdf", "").upper()[:10]}
        (OUT / "prices.json")  # placeholder so linter doesn't flag unused import path pattern
    # Scanned-style PNG (OCR path test): clean grower PDF -> image, light blur/rotation
    try:
        from pdf2image import convert_from_path
        from PIL import ImageFilter
        im = convert_from_path(str(OUT / "01_clean_grower_uptrend.pdf"), dpi=200)[0].convert("L") \
            .rotate(0.8, expand=True, fillcolor=255).filter(ImageFilter.GaussianBlur(0.6))
        im.save(OUT / "07_scanned_clean.png")
        exp["07_scanned_clean.png"] = {"expected_verdict": "BUY", "expected_flags": "OCR path test (same as 01)",
                                       "macro_text": "Markets steady, no major catalysts this week.", "ticker": "ZENITH"}
    except Exception as e:
        print("PNG skip:", e)

    prices_out = {fname: SCENARIOS[fname][1] for fname in SCENARIOS}
    prices_out["07_scanned_clean.png"] = SCENARIOS["01_clean_grower_uptrend.pdf"][1]
    (OUT / "prices.json").write_text(json.dumps(prices_out, indent=2))
    (OUT / "expected.json").write_text(json.dumps(exp, indent=2, ensure_ascii=False))
    print(f"{len(exp)} samples -> {OUT}/")
