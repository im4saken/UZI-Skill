"""Build and merge file-driven agent inputs/outputs for deep-analysis.

This module introduces a narrow file protocol for local 128K-context models:
the pipeline still keeps canonical task files (`raw_data.json`, `panel.json`,
`agent_analysis.json`, ...), while agent/sub-agent work consumes and produces
smaller artifacts under `.cache/{ticker}/agent_inputs/` and `agent_outputs/`.
"""
from __future__ import annotations

from copy import deepcopy

from lib.cache import (
    cache_path,
    read_cache_json,
    read_task_output,
    write_cache_json,
    write_task_output,
)

PANEL_GROUPS: dict[str, tuple[str, ...]] = {
    "value_growth": ("A", "B"),
    "macro_tech": ("C", "D"),
    "china_quant": ("E", "G", "H", "I"),
    "youzi": ("F",),
}

QUAL_GROUPS: dict[str, tuple[str, ...]] = {
    "macro_policy": ("3_macro", "13_policy"),
    "industry_events": ("7_industry", "15_events"),
    "cost_transmission": ("8_materials", "9_futures"),
}

PANEL_OUTPUT_FILES = (
    "panel_value_growth.json",
    "panel_macro_tech.json",
    "panel_china_quant.json",
    "panel_youzi.json",
)
QUAL_OUTPUT_FILES = (
    "qual_macro_policy.json",
    "qual_industry_events.json",
    "qual_cost_transmission.json",
)


def _safe_float(v, default=0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", "").replace("%", "").replace("亿", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return default


def _distance_to_high_pct(kline: dict) -> float | None:
    stats = kline.get("kline_stats") or {}
    current = _safe_float(kline.get("price") or stats.get("current_price"), default=0.0)
    high = _safe_float(stats.get("high_60d") or stats.get("rolling_60d_high"), default=0.0)
    if current > 0 and high > 0:
        return round((current / high - 1.0) * 100, 2)
    return None


def _top_risks_from_dims(dims: dict) -> list[dict]:
    out = []
    for key, dim in (dims.get("dimensions") or {}).items():
        score = _safe_float(dim.get("score"), default=0.0)
        weight = _safe_float(dim.get("weight"), default=1.0)
        if score <= 4:
            out.append({
                "dim": key,
                "name": dim.get("name") or dim.get("label") or key,
                "score": score,
                "weight": weight,
                "severity": round(score * weight, 2),
                "reasons_fail": list(dim.get("reasons_fail") or []),
            })
    out.sort(key=lambda x: x["severity"])
    return out[:5]


def _build_executive_summary(ticker: str, raw: dict, dims: dict, panel: dict) -> dict:
    basic = (raw.get("dimensions", {}).get("0_basic") or {}).get("data") or {}
    kline = (raw.get("dimensions", {}).get("2_kline") or {}).get("data") or {}
    d20 = (raw.get("dimensions", {}).get("20_valuation_models") or {}).get("data") or {}
    d21 = (raw.get("dimensions", {}).get("21_research_workflow") or {}).get("data") or {}
    fin_dim = (dims.get("dimensions", {}).get("1_financials") or {})
    summary20 = d20.get("summary") or {}
    init_cov = d21.get("headline") or d21.get("initiating_coverage", {}).get("headline") or {}
    integrity = raw.get("_integrity") or {}
    gaps_doc = read_task_output(ticker, "_data_gaps") or read_cache_json(ticker, "_data_gaps.json") or {}
    gap_tasks = gaps_doc.get("tasks") or []

    return {
        "ticker": raw.get("ticker", ticker),
        "name": basic.get("name", ""),
        "market": raw.get("market", "A"),
        "industry": basic.get("industry", ""),
        "key_facts": {
            "price": _safe_float(basic.get("price")),
            "market_cap_yi": round(_safe_float(basic.get("market_cap_raw")) / 1e8, 2) if basic.get("market_cap_raw") else 0.0,
            "pe_ttm": _safe_float(basic.get("pe_ttm")),
            "pb": _safe_float(basic.get("pb")),
            "roe_5y_avg": _safe_float(fin_dim.get("roe_5y_avg")),
            "roe_5y_min": _safe_float(fin_dim.get("roe_5y_min")),
            "revenue_growth_3y_cagr": _safe_float(fin_dim.get("revenue_growth_3y_cagr")),
            "dividend_yield": _safe_float(basic.get("dividend_yield_ttm")),
            "fcf_yield": _safe_float(fin_dim.get("fcf_yield")),
        },
        "technical_snapshot": {
            "stage": kline.get("stage"),
            "distance_to_60d_high_pct": _distance_to_high_pct(kline),
            "ma_alignment": kline.get("ma_alignment") or kline.get("trend") or "",
            "macd_state": kline.get("macd_state") or "",
            "volume_state": kline.get("volume_state") or "",
        },
        "institutional_snapshot": {
            "dcf_intrinsic": summary20.get("dcf_intrinsic"),
            "dcf_safety_margin_pct": summary20.get("dcf_safety_margin_pct"),
            "lbo_irr_pct": summary20.get("lbo_irr_pct"),
            "comps_verdict": summary20.get("comps_verdict"),
            "target_price": init_cov.get("target_price"),
            "upside_pct": init_cov.get("upside_pct"),
            "rating": init_cov.get("rating") or d21.get("summary", {}).get("rec_rating"),
            "ic_recommendation": (raw.get("dimensions", {}).get("22_deep_methods") or {}).get("data", {}).get("summary", {}).get("ic_recommendation"),
        },
        "data_quality": {
            "coverage_pct": integrity.get("coverage_pct", 0),
            "critical_missing": integrity.get("critical_missing", False),
            "gaps": [t.get("dim") for t in gap_tasks if t.get("dim")],
            "top_risks": _top_risks_from_dims(dims),
        },
        "a_share_flags": {
            "is_a_share": raw.get("market") == "A",
            "has_lhb_data": bool((raw.get("dimensions", {}).get("16_lhb") or {}).get("data")),
            "recent_limit_up": int(_safe_float((kline.get("kline_stats") or {}).get("recent_limit_up"), default=0)),
        },
        "panel_snapshot": {
            "panel_consensus": panel.get("panel_consensus"),
            "signal_distribution": panel.get("signal_distribution", {}),
        },
    }


def _panel_input_name(group_key: str) -> str:
    return f"panel_{group_key}.json"


def _qual_input_name(group_key: str) -> str:
    return f"qual_{group_key}.json"


def build_agent_inputs(ticker: str, raw: dict | None = None, dims: dict | None = None, panel: dict | None = None) -> dict:
    raw = raw or read_task_output(ticker, "raw_data") or {}
    dims = dims or read_task_output(ticker, "dimensions") or {}
    panel = panel or read_task_output(ticker, "panel") or {}
    if not raw or not dims or not panel:
        raise RuntimeError(f"build_agent_inputs 缺少必要输入: ticker={ticker}")

    created: dict[str, str] = {}
    exec_summary = _build_executive_summary(ticker, raw, dims, panel)
    created["executive_summary"] = str(write_cache_json(ticker, "agent_inputs/executive_summary.json", exec_summary))

    investors = panel.get("investors") or []
    gaps_doc = read_cache_json(ticker, "_data_gaps.json") or {}
    data_gaps = [t.get("dim") for t in (gaps_doc.get("tasks") or []) if t.get("dim")]

    for group_key, group_codes in PANEL_GROUPS.items():
        group_investors = [deepcopy(inv) for inv in investors if inv.get("group") in group_codes]
        payload = {
            "group": group_key,
            "ticker": raw.get("ticker", ticker),
            "name": exec_summary.get("name", ""),
            "summary_ref": "agent_inputs/executive_summary.json",
            "investors": group_investors,
            "focus_metrics": {
                "value_growth": ["pe_ttm", "pb", "roe_5y_avg", "revenue_growth_3y_cagr", "fcf_yield"],
                "macro_tech": ["stage", "distance_to_60d_high_pct", "ma_alignment", "macd_state", "volume_state"],
                "china_quant": ["roe_5y_avg", "roe_5y_min", "revenue_growth_3y_cagr", "fcf_yield", "dividend_yield"],
                "youzi": ["market_cap_yi", "stage", "distance_to_60d_high_pct", "has_lhb_data", "recent_limit_up"],
            }.get(group_key, []),
            "data_gaps": data_gaps,
        }
        path = f"agent_inputs/{_panel_input_name(group_key)}"
        created[path] = str(write_cache_json(ticker, path, payload))

    dims_map = raw.get("dimensions") or {}
    for group_key, dim_keys in QUAL_GROUPS.items():
        payload = {
            "group": group_key,
            "ticker": raw.get("ticker", ticker),
            "name": exec_summary.get("name", ""),
            "industry": exec_summary.get("industry", ""),
            "summary_ref": "agent_inputs/executive_summary.json",
            "dimensions": {k: deepcopy(dims_map.get(k) or {}) for k in dim_keys},
            "existing_gaps": [g for g in data_gaps if g in dim_keys],
        }
        path = f"agent_inputs/{_qual_input_name(group_key)}"
        created[path] = str(write_cache_json(ticker, path, payload))

    eligible = [inv for inv in investors if inv.get("signal") != "skip"]
    by_score = sorted(eligible, key=lambda x: x.get("score", 0), reverse=True)
    top_bulls = [deepcopy(inv) for inv in by_score[:3]]
    top_bears = [deepcopy(inv) for inv in sorted(eligible, key=lambda x: x.get("score", 100))[:3]]
    task4 = {
        "ticker": raw.get("ticker", ticker),
        "name": exec_summary.get("name", ""),
        "executive_summary_ref": "agent_inputs/executive_summary.json",
        "overall_inputs": {
            "fundamental_score": dims.get("fundamental_score"),
            "panel_consensus": panel.get("panel_consensus"),
        },
        "great_divide_candidates": {
            "top_bulls": top_bulls,
            "top_bears": top_bears,
        },
        "institutional_modeling": exec_summary.get("institutional_snapshot", {}),
        "risk_dimensions": exec_summary.get("data_quality", {}).get("top_risks", []),
        "pending_agent_outputs": [
            f"agent_outputs/{name}" for name in PANEL_OUTPUT_FILES + QUAL_OUTPUT_FILES
        ],
    }
    created["agent_inputs/task4_synthesis_brief.json"] = str(
        write_cache_json(ticker, "agent_inputs/task4_synthesis_brief.json", task4)
    )
    return created


def merge_agent_outputs(ticker: str, panel: dict | None = None, agent_analysis: dict | None = None) -> tuple[dict | None, dict]:
    panel = deepcopy(panel or read_task_output(ticker, "panel"))
    agent_analysis = deepcopy(agent_analysis or read_task_output(ticker, "agent_analysis") or {})
    if panel is None:
        raise RuntimeError(f"merge_agent_outputs 缺少 panel.json: {ticker}")

    investors = panel.get("investors") or []
    by_id = {inv.get("investor_id"): inv for inv in investors}
    merged_panel_files: list[str] = []
    merged_qual_files: list[str] = []

    for filename in PANEL_OUTPUT_FILES:
        payload = read_cache_json(ticker, f"agent_outputs/{filename}")
        if not payload:
            continue
        for item in payload.get("investors") or []:
            target = by_id.get(item.get("investor_id"))
            if not target:
                continue
            for key in ("signal", "score", "headline", "reasoning"):
                if key in item:
                    target[key] = item[key]
            if "override_reason" in item:
                target["override_reason"] = item["override_reason"]
            if "override_rule_engine" in item:
                target["override_rule_engine"] = item["override_rule_engine"]
        merged_panel_files.append(filename)

    if merged_panel_files:
        write_task_output(ticker, "panel", panel)

    qd = deepcopy(agent_analysis.get("qualitative_deep_dive") or {})
    for filename in QUAL_OUTPUT_FILES:
        payload = read_cache_json(ticker, f"agent_outputs/{filename}")
        if not payload:
            continue
        dims_payload = payload.get("dimensions") or {}
        for dim_key, dim_value in dims_payload.items():
            qd[dim_key] = dim_value
        merged_qual_files.append(filename)
    if merged_qual_files:
        agent_analysis["qualitative_deep_dive"] = qd

    merge_meta = agent_analysis.get("_merged_agent_outputs") or {}
    merge_meta.update({
        "panel_files": merged_panel_files,
        "qual_files": merged_qual_files,
    })
    agent_analysis["_merged_agent_outputs"] = merge_meta

    if merged_qual_files or agent_analysis:
        write_task_output(ticker, "agent_analysis", agent_analysis)

    return panel, agent_analysis


def main(ticker: str) -> None:
    created = build_agent_inputs(ticker)
    print(f"✓ 已生成 {len(created)} 个 agent_inputs 文件")
    for k, v in created.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python build_agent_inputs.py <ticker>")
    main(sys.argv[1])
