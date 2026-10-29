"""Samples pe end-to-end eval: expected.json ke verdict se compare. Needs OPENAI_API_KEY for the LLM-routed
scenarios (report_generator); error/conflict-routed scenarios (flag_for_review) don't need the LLM at all.
Run: python evaluate.py"""
import json, sys
from pathlib import Path
from pipeline import analyze_stock

exp = json.loads(Path("samples/expected.json").read_text())
prices = json.loads(Path("samples/prices.json").read_text())
ok = 0
for fname, e in exp.items():
    path = str(Path("samples") / fname)
    try:
        res = analyze_stock(path, e["macro_text"], "", e["ticker"],
                            "Give me a research view on this stock", prices[fname])
        got = res["report"]["verdict"]
        codes = sorted({f["code"] for f in res["flags"]})
    except Exception as ex:
        got, codes = f"ERROR {ex}", []
    hit = got == e["expected_verdict"]; ok += hit
    print(f"{'PASS' if hit else 'FAIL'}  {fname:38s} expected={e['expected_verdict']:15s} got={str(got):15s} codes={codes}")
print(f"\n{ok}/{len(exp)} verdicts match")
sys.exit(0 if ok == len(exp) else 1)
