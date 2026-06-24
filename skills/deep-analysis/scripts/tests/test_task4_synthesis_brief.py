from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


def test_task4_brief_contains_required_sections(monkeypatch, tmp_path):
    import build_agent_inputs as bai
    from lib import cache as cache_mod

    monkeypatch.setattr(cache_mod, "CACHE_ROOT", tmp_path / ".cache")
    monkeypatch.setattr(bai, "read_cache_json", lambda *args, **kwargs: {"tasks": []})

    raw = {
        "ticker": "002475.SZ",
        "market": "A",
        "_integrity": {"coverage_pct": 88, "critical_missing": False},
        "dimensions": {
            "0_basic": {"data": {"name": "立讯精密", "industry": "电子", "price": 32.1, "market_cap_raw": 230000000000, "pe_ttm": 24.1, "pb": 4.0}},
            "2_kline": {"data": {"stage": 2, "kline_stats": {"high_60d": 35.0}}},
            "20_valuation_models": {"data": {"summary": {"dcf_intrinsic": 36.8, "lbo_irr_pct": 18.5}}},
            "21_research_workflow": {"data": {"headline": {"target_price": 40.0, "upside_pct": 24.6, "rating": "BUY"}}},
            "22_deep_methods": {"data": {"summary": {"ic_recommendation": "BUY"}}},
        },
    }
    dims = {"fundamental_score": 81.0, "dimensions": {}}
    panel = {
        "panel_consensus": 69.0,
        "signal_distribution": {"bullish": 1, "neutral": 1, "bearish": 1, "skip": 0},
        "investors": [
            {"investor_id": "duan", "name": "段永平", "group": "E", "signal": "bullish", "score": 90},
            {"investor_id": "burry", "name": "Burry", "group": "C", "signal": "bearish", "score": 22},
            {"investor_id": "simons", "name": "Simons", "group": "G", "signal": "neutral", "score": 58},
        ],
    }

    bai.build_agent_inputs("002475.SZ", raw=raw, dims=dims, panel=panel)
    brief = cache_mod.read_cache_json("002475.SZ", "agent_inputs/task4_synthesis_brief.json")

    assert brief["ticker"] == "002475.SZ"
    assert brief["overall_inputs"]["fundamental_score"] == 81.0
    assert "top_bulls" in brief["great_divide_candidates"]
    assert "top_bears" in brief["great_divide_candidates"]
    assert "agent_outputs/panel_value_growth.json" in brief["pending_agent_outputs"]
