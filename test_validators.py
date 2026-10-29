"""Offline tests — LLM/API key ke bina chalte hain: python test_validators.py
Covers the deterministic signal engines only (classify_fundamentals, compute_technical, macro_risk_scan) —
the same functions the multi-agent graph's fundamental/technical/macro nodes call."""
from pipeline import FinancialMetrics, classify_fundamentals, compute_technical, macro_risk_scan


def codes(flags):
    return {f.code for f in flags}


# --- fundamentals ---
grower = FinancialMetrics(revenue_cr=10000, net_profit_cr=1500, revenue_growth_yoy_pct=22,
                          net_profit_growth_yoy_pct=25, operating_margin_pct=22, debt_to_equity=0.4,
                          promoter_holding_pct=55)
view, flags = classify_fundamentals(grower)
assert view.classification == "Grower" and view.stance == "Bullish", view
assert codes(flags) == set(), codes(flags)

payer_high_leverage = FinancialMetrics(revenue_cr=8000, net_profit_cr=600, revenue_growth_yoy_pct=8,
                                       net_profit_growth_yoy_pct=5, operating_margin_pct=15,
                                       debt_to_equity=2.2, promoter_holding_pct=48)
view, flags = classify_fundamentals(payer_high_leverage)
assert view.classification == "Payer" and view.stance == "Neutral", view
assert "HIGH_LEVERAGE" in codes(flags)

straggler = FinancialMetrics(revenue_cr=3000, net_profit_cr=-100, revenue_growth_yoy_pct=-5,
                             net_profit_growth_yoy_pct=-20, operating_margin_pct=6, debt_to_equity=1.0)
view, flags = classify_fundamentals(straggler)
assert view.classification == "Straggler" and view.stance == "Bearish", view
assert {"PROFIT_DECLINE", "LOW_MARGIN"} <= codes(flags)

empty = FinancialMetrics()
view, flags = classify_fundamentals(empty)
assert view.classification == "Unclassified"
assert "FUNDAMENTALS_DATA_INCOMPLETE" in codes(flags)

# --- technical ---
uptrend_prices = [100 + i * 3 for i in range(30)]
view, flags = compute_technical(uptrend_prices)
assert view.trend == "Uptrend" and view.stance == "Bullish", view
assert codes(flags) == set(), codes(flags)

downtrend_prices = [200 - i * 3 for i in range(30)]
view, flags = compute_technical(downtrend_prices)
assert view.trend == "Downtrend" and view.stance == "Bearish", view

view, flags = compute_technical([100, 101, 99])
assert view.stance == "Insufficient data"
assert "INSUFFICIENT_PRICE_DATA" in codes(flags)

volatile_prices = [100 + ((-1) ** i) * 15 for i in range(30)]
view, flags = compute_technical(volatile_prices)
assert "HIGH_VOLATILITY" in codes(flags)

# --- macro ---
clean_view, clean_flags = macro_risk_scan("Markets steady, no major catalysts this week.")
assert clean_view.stance == "Risk-On"
assert codes(clean_flags) == set()

risky_view, risky_flags = macro_risk_scan(
    "US 10-year yield spiking on inflation fears, crude oil surging on geopolitical war risk.")
assert risky_view.stance == "Risk-Off"
assert "MACRO_RISK_OFF" in codes(risky_flags)

print("All validator tests passed ✅")
