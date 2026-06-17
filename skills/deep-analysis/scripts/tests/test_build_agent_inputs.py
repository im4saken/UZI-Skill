from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


def _sample_raw():
    return {
        "ticker": "601899.SH",
        "market": "A",
        "_integrity": {"coverage_pct": 91, "critical_missing": False},
        "dimensions": {
            "0_basic": {"data": {"name": "紫金矿业", "industry": "有色金属", "price": 18.56, "market_cap_raw": 480000000000, "pe_ttm": 17.2, "pb": 2.9, "dividend_yield_ttm": 1.8}},
            "1_financials": {"data": {}},
            "2_kline": {"data": {"stage": 2, "ma_alignment": "bullish", "macd_state": "golden_cross", "volume_state": "expanding", "kline_stats": {"high_60d": 20.0, "recent_limit_up": 1}}},
            "3_macro": {"data": {"summary": "macro"}},
            "7_industry": {"data": {"summary": "industry"}},
            "8_materials": {"data": {"summary": "materials"}},
            "9_futures": {"data": {"summary": "futures"}},
            "13_policy": {"data": {"summary": "policy"}},
            "15_events": {"data": {"summary": "events"}},
            "16_lhb": {"data": {"records": [1]}},
            "20_valuation_models": {"data": {"summary": {"dcf_intrinsic": 20.73, "dcf_safety_margin_pct": -11.8, "lbo_irr_pct": 21.7, "comps_verdict": "便宜"}}},
            "21_research_workflow": {"data": {"headline": {"target_price": 22.5, "upside_pct": 21.2, "rating": "BUY"}}},
            "22_deep_methods": {"data": {"summary": {"ic_recommendation": "BUY"}}},
        },
    }


def _sample_dims():
    return {
        "fundamental_score": 78.2,
        "dimensions": {
            "1_financials": {
                "score": 7,
                "weight": 1.2,
                "roe_5y_avg": 18.4,
                "roe_5y_min": 12.1,
                "revenue_growth_3y_cagr": 0.21,
                "fcf_yield": 0.05,
            },
            "13_policy": {
                "score": 3,
                "weight": 1.0,
                "name": "政策与监管",
                "reasons_fail": ["政策不确定性"],
            },
        },
    }


def _sample_panel():
    return {
        "panel_consensus": 73.4,
        "signal_distribution": {"bullish": 2, "neutral": 1, "bearish": 1, "skip": 0},
        "investors": [
            {"investor_id": "buffett", "name": "巴菲特", "group": "A", "signal": "bullish", "score": 82, "headline": "h1", "reasoning": "r1", "pass": [], "fail": []},
            {"investor_id": "wood", "name": "木头姐", "group": "B", "signal": "neutral", "score": 55, "headline": "h2", "reasoning": "r2", "pass": [], "fail": []},
            {"investor_id": "soros", "name": "索罗斯", "group": "C", "signal": "bearish", "score": 28, "headline": "h3", "reasoning": "r3", "pass": [], "fail": []},
            {"investor_id": "livermore", "name": "利弗莫尔", "group": "D", "signal": "bullish", "score": 75, "headline": "h4", "reasoning": "r4", "pass": [], "fail": []},
            {"investor_id": "duan", "name": "段永平", "group": "E", "signal": "bullish", "score": 88, "headline": "h5", "reasoning": "r5", "pass": [], "fail": []},
            {"investor_id": "simons", "name": "西蒙斯", "group": "G", "signal": "neutral", "score": 58, "headline": "h6", "reasoning": "r6", "pass": [], "fail": []},
            {"investor_id": "jensen_huang", "name": "黄仁勋", "group": "H", "signal": "bullish", "score": 80, "headline": "h7", "reasoning": "r7", "pass": [], "fail": []},
            {"investor_id": "serenity", "name": "Serenity", "group": "I", "signal": "neutral", "score": 61, "headline": "h8", "reasoning": "r8", "pass": [], "fail": []},
            {"investor_id": "zhao_lg", "name": "赵老哥", "group": "F", "signal": "bullish", "score": 77, "headline": "h9", "reasoning": "r9", "pass": [], "fail": []},
        ],
    }


def test_build_agent_inputs_generates_expected_files(monkeypatch, tmp_path):
    import build_agent_inputs as bai
    from lib import cache as cache_mod

    monkeypatch.setattr(cache_mod, "CACHE_ROOT", tmp_path / ".cache")
    monkeypatch.setattr(bai, "read_task_output", lambda *args, **kwargs: None)
    monkeypatch.setattr(bai, "read_cache_json", lambda *args, **kwargs: {"tasks": [{"dim": "13_policy", "field": "headline"}]})

    created = bai.build_agent_inputs("601899.SH", raw=_sample_raw(), dims=_sample_dims(), panel=_sample_panel())

    expected = {
        "executive_summary",
        "agent_inputs/panel_value_growth.json",
        "agent_inputs/panel_macro_tech.json",
        "agent_inputs/panel_china_quant.json",
        "agent_inputs/panel_youzi.json",
        "agent_inputs/qual_macro_policy.json",
        "agent_inputs/qual_industry_events.json",
        "agent_inputs/qual_cost_transmission.json",
        "agent_inputs/task4_synthesis_brief.json",
    }
    assert expected.issubset(set(created.keys()))

    exec_summary = cache_mod.read_cache_json("601899.SH", "agent_inputs/executive_summary.json")
    assert exec_summary["name"] == "紫金矿业"
    assert exec_summary["a_share_flags"]["is_a_share"] is True

    vg = cache_mod.read_cache_json("601899.SH", "agent_inputs/panel_value_growth.json")
    assert {i["investor_id"] for i in vg["investors"]} == {"buffett", "wood"}

    cq = cache_mod.read_cache_json("601899.SH", "agent_inputs/panel_china_quant.json")
    assert {i["group"] for i in cq["investors"]} == {"E", "G", "H", "I"}
