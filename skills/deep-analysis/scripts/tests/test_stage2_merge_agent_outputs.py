from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


def test_merge_agent_outputs_updates_panel_and_agent_analysis(monkeypatch, tmp_path):
    import build_agent_inputs as bai
    from lib import cache as cache_mod

    monkeypatch.setattr(cache_mod, "CACHE_ROOT", tmp_path / ".cache")

    panel = {
        "ticker": "601899.SH",
        "investors": [
            {"investor_id": "buffett", "signal": "neutral", "score": 62, "headline": "old", "reasoning": "old"},
            {"investor_id": "zhao_lg", "signal": "neutral", "score": 50, "headline": "old2", "reasoning": "old2"},
        ],
    }
    cache_mod.write_task_output("601899.SH", "panel", panel)
    cache_mod.write_task_output("601899.SH", "agent_analysis", {"agent_reviewed": False})

    cache_mod.write_cache_json("601899.SH", "agent_outputs/panel_value_growth.json", {
        "group": "value_growth",
        "investors": [
            {"investor_id": "buffett", "signal": "bullish", "score": 88, "headline": "new head", "reasoning": "new reason"}
        ],
    })
    cache_mod.write_cache_json("601899.SH", "agent_outputs/qual_macro_policy.json", {
        "group": "macro_policy",
        "dimensions": {
            "3_macro": {"evidence": [{"url": "https://example.com"}], "associations": [], "conclusion": "macro ok"},
            "13_policy": {"evidence": [{"url": "https://example.com/policy"}], "associations": [], "conclusion": "policy ok"},
        },
    })

    merged_panel, merged_agent = bai.merge_agent_outputs("601899.SH")

    buffett = next(i for i in merged_panel["investors"] if i["investor_id"] == "buffett")
    assert buffett["signal"] == "bullish"
    assert buffett["score"] == 88
    assert merged_agent["qualitative_deep_dive"]["3_macro"]["conclusion"] == "macro ok"
    assert "panel_value_growth.json" in merged_agent["_merged_agent_outputs"]["panel_files"]
