# deep-analysis 128K 本地模型文件驱动改造方案

## 背景与问题定义

`deep-analysis` 当前是“脚本产出 JSON + agent 读取大量 JSON/规则/网页材料再继续推理”的混合工作流。  
对 Claude / 云端大上下文模型，这种设计还能工作；但对 `oMLX + Qwen3.6` 这类 `128K context` 的本地模型，Stage 1 之后的 agent 介入层很容易因为上下文过长触发压缩、截断或降质，最终损失最大的是 Task 2.5 / Task 3 / Task 4 这些最依赖高质量判断的阶段。

问题不在“是否已经落盘”本身，而在：

1. 已落盘的大文件会被 agent 再次整体读回上下文。
2. sub-agent 输入边界没有在代码层真正收紧，很多约束只停留在文档里。
3. Stage 2 只消费 `agent_analysis.json`，没有消费更细粒度的 agent 中间产物。
4. `SKILL.md`、`references`、`run_real_test.py` 已经出现文件化改造与旧流程并存的漂移状态。

本次改造目标是：在不破坏现有主产物契约的前提下，把 agent 工作流改成“分阶段 brief 输入 + 分阶段结果回写 + stage2 自动合并”的文件驱动执行方式。

## 为什么当前 workflow 会在 128K 本地模型上触发上下文压缩

### 已经文件化但仍会被重新读回上下文的内容

- `.cache/{ticker}/raw_data.json`
- `.cache/{ticker}/dimensions.json`
- `.cache/{ticker}/panel.json`
- `.cache/{ticker}/agent_analysis.json`
- 6 个定性维度的原始抓取材料
- 51 位投资者规则引擎结果、persona、knowledge、pass/fail rules

### 主要上下文黑洞

1. **Task 3 投资者评审**
   - 当前 `run_real_test.stage1()` 只写出 `panel.json`，然后要求 agent 读取完整 `panel.json` 并按组 role-play。
   - 旧版 `references/task3-agent-evaluation.md` 仍假定 sub-agent 读 `raw_data + features + rule_engine_results + investor_knowledge`。
   - `SKILL.md` 已经写入 `0_raw_data_summary.json / 2a/2b/2c/2d` 的新流程，但代码里并没有生成这些文件。

2. **Task 2.5 六维定性深挖**
   - 文档要求 3 个 sub-agent 并行深挖 6 个维度。
   - 但输入仍围绕 `.cache/{ticker}/raw_data.json` 全量维度和网页材料展开，缺乏真正的最小输入文件。

3. **Task 4 综合叙事**
   - 当前 `stage2()` 只读 `raw_data / dimensions / panel / agent_analysis`。
   - agent 若不先自行把大量中间判断重新折叠进 `agent_analysis.json`，stage2 就无法消费更细粒度的结果。

### 结论

当前系统本质上是：

- 脚本阶段：文件驱动
- agent 阶段：大上下文驱动
- 报告阶段：再回到文件驱动

本次改造要解决的是中间这一层。

## 当前实现中哪些阶段已经文件化

### 已经稳定文件化的阶段

1. `stage1()` 会写：
   - `raw_data.json`
   - `dimensions.json`
   - `panel.json`
   - `_data_gaps.json`
2. `stage2()` 会读：
   - `raw_data.json`
   - `dimensions.json`
   - `panel.json`
   - `agent_analysis.json`
3. `stage2()` 会写：
   - `synthesis.json`
   - 报告 HTML / PNG

### 只在文档中存在、代码中未真正实现的文件化约定

1. `0_raw_data_summary.json`
2. `2a_value_growth.json`
3. `2b_macro_tech.json`
4. `2c_china_quant.json`
5. `2d_youzi.json`

### 仍然依赖长上下文的阶段

1. 投资者 role-play 输入准备
2. 定性 6 维深挖输入准备
3. Task 4 叙事合成的事实收束

## 改造目标

1. 保留现有主文件契约：
   - `raw_data.json`
   - `dimensions.json`
   - `panel.json`
   - `agent_analysis.json`
   - `synthesis.json`
2. 新增一层 agent 专用中间文件，避免 agent/sub-agent 直接消费过大的主文件。
3. 把 Task 3 / Task 2.5 / Task 4 改成：
   - stage1 生成 briefs
   - sub-agent 只读 briefs
   - sub-agent 写结构化结果文件
   - stage2 自动合并这些结果
4. 允许 agent 只在必要时回看大文件，而不是默认依赖完整上下文。

## 非目标

1. 不重命名主产物文件。
2. 不重写整条 pipeline。
3. 不调整 fetcher 业务逻辑。
4. 不处理与 128K 上下文问题无关的界面、文案、重构。

## 设计原则

1. **主契约不动，新增层优先**
2. **brief 必须确定性生成，不依赖模型总结**
3. **每个 sub-agent 只读当前任务的最小输入**
4. **中间结果必须落盘，不能只存在于会话上下文**
5. **stage2 要能自动消费 agent 中间产物，而不是完全依赖人工再粘回**
6. **新旧流程兼容**
   - 新文件不存在时，旧流程仍能跑
   - 新文件存在时，优先走新流程

## 新增文件结构

在 `.cache/{ticker}/` 下新增：

```text
.cache/{ticker}/
├── raw_data.json
├── dimensions.json
├── panel.json
├── agent_analysis.json
├── synthesis.json
├── _data_gaps.json
├── agent_inputs/
│   ├── executive_summary.json
│   ├── panel_value_growth.json
│   ├── panel_macro_tech.json
│   ├── panel_china_quant.json
│   ├── panel_youzi.json
│   ├── qual_macro_policy.json
│   ├── qual_industry_events.json
│   ├── qual_cost_transmission.json
│   └── task4_synthesis_brief.json
└── agent_outputs/
    ├── panel_value_growth.json
    ├── panel_macro_tech.json
    ├── panel_china_quant.json
    ├── panel_youzi.json
    ├── qual_macro_policy.json
    ├── qual_industry_events.json
    └── qual_cost_transmission.json
```

## 新增中间文件 schema

### 1. `agent_inputs/executive_summary.json`

用途：所有 agent 的共享最小事实层。

```json
{
  "ticker": "601899.SH",
  "name": "紫金矿业",
  "market": "A",
  "industry": "有色金属",
  "key_facts": {
    "price": 18.56,
    "market_cap_yi": 4800,
    "pe_ttm": 17.2,
    "pb": 2.9,
    "roe_5y_avg": 18.4,
    "revenue_growth_3y_cagr": 0.21,
    "fcf_yield": 0.05,
    "dividend_yield": 0.018
  },
  "technical_snapshot": {
    "stage": 2,
    "distance_to_60d_high_pct": -8.2,
    "ma_alignment": "bullish",
    "macd_state": "golden_cross",
    "volume_state": "expanding"
  },
  "institutional_snapshot": {
    "dcf_intrinsic": 20.73,
    "dcf_safety_margin_pct": -11.8,
    "lbo_irr_pct": 21.7,
    "target_price": 22.5,
    "upside_pct": 21.2,
    "ic_recommendation": "BUY"
  },
  "data_quality": {
    "coverage_pct": 91,
    "gaps": ["13_policy"],
    "critical_missing": false
  },
  "a_share_flags": {
    "is_a_share": true,
    "has_lhb_data": true,
    "recent_limit_up": 1
  }
}
```

### 2. `agent_inputs/panel_*.json`

用途：Task 3 各分组 sub-agent 的最小输入。

```json
{
  "group": "value_growth",
  "ticker": "601899.SH",
  "name": "紫金矿业",
  "summary_ref": "agent_inputs/executive_summary.json",
  "investors": [
    {
      "investor_id": "buffett",
      "name": "巴菲特",
      "group": "A",
      "signal": "neutral",
      "score": 62,
      "headline": "规则引擎骨架 headline",
      "reasoning": "规则引擎骨架 reasoning",
      "pass": [],
      "fail": []
    }
  ],
  "focus_metrics": ["pe_ttm", "roe_5y_avg", "fcf_yield", "industry"],
  "data_gaps": ["13_policy"]
}
```

### 3. `agent_inputs/qual_*.json`

用途：Task 2.5 三个 sub-agent 的最小输入。

```json
{
  "group": "macro_policy",
  "ticker": "601899.SH",
  "name": "紫金矿业",
  "industry": "有色金属",
  "summary_ref": "agent_inputs/executive_summary.json",
  "dimensions": {
    "3_macro": { "data": {} },
    "13_policy": { "data": {} }
  },
  "questions_ref": "references/task2.5-qualitative-deep-dive.md#dim-3--宏观环境",
  "existing_gaps": []
}
```

### 4. `agent_inputs/task4_synthesis_brief.json`

用途：Task 4 叙事层的最小输入。

```json
{
  "ticker": "601899.SH",
  "name": "紫金矿业",
  "executive_summary_ref": "agent_inputs/executive_summary.json",
  "overall_inputs": {
    "fundamental_score": 78.2,
    "panel_consensus": 73.4
  },
  "great_divide_candidates": {
    "top_bulls": [],
    "top_bears": []
  },
  "institutional_modeling": {},
  "risk_dimensions": [],
  "catalysts": [],
  "pending_agent_outputs": [
    "agent_outputs/panel_value_growth.json",
    "agent_outputs/panel_macro_tech.json",
    "agent_outputs/panel_china_quant.json",
    "agent_outputs/panel_youzi.json",
    "agent_outputs/qual_macro_policy.json",
    "agent_outputs/qual_industry_events.json",
    "agent_outputs/qual_cost_transmission.json"
  ]
}
```

### 5. `agent_outputs/panel_*.json`

用途：Task 3 各组判断结果。

```json
{
  "group": "value_growth",
  "investors": [
    {
      "investor_id": "buffett",
      "signal": "bullish",
      "score": 78,
      "headline": "ROE 五年均值 18% 且铜金双轮驱动，但估值已不便宜。",
      "reasoning": "2-3 句推理",
      "override_rule_engine": true,
      "override_reason": "实际商业质量强于规则引擎单点估值惩罚"
    }
  ],
  "summary": "价值成长派偏多，但估值分歧明显。"
}
```

### 6. `agent_outputs/qual_*.json`

用途：Task 2.5 的结构化结论输出。

```json
{
  "group": "macro_policy",
  "dimensions": {
    "3_macro": {
      "evidence": [],
      "associations": [],
      "conclusion": "1-2 句结论"
    },
    "13_policy": {
      "evidence": [],
      "associations": [],
      "conclusion": "1-2 句结论"
    }
  }
}
```

## 具体改动点

### A. `scripts/lib/cache.py`

新增：

1. `write_cache_json(ticker, relative_path, data)`
2. `read_cache_json(ticker, relative_path)`
3. `cache_path(ticker, relative_path)`

目的：支持 `.cache/{ticker}/agent_inputs/...`、`.cache/{ticker}/agent_outputs/...` 这样的嵌套路径，而不破坏现有 `write_task_output/read_task_output`。

### B. 新增 `scripts/build_agent_inputs.py`

职责：

1. 从 `raw_data.json / dimensions.json / panel.json` 生成 `agent_inputs/executive_summary.json`
2. 按投资者分组切出 4 份 `panel_*.json`
3. 按 6 维定性任务切出 3 份 `qual_*.json`
4. 生成 `task4_synthesis_brief.json`

要求：

- 完全确定性
- 不调用模型
- 不修改主产物

### C. `scripts/run_real_test.py`

#### `stage1()` 改动

在 `panel.json` 写入后，追加：

1. 自动调用 `build_agent_inputs()`
2. 在终端提示新文件路径
3. 更新提示文案，从“读 panel.json / 写 agent_analysis.json”改为：
   - 读 `agent_inputs/panel_*.json`
   - 写 `agent_outputs/panel_*.json`
   - 读 `agent_inputs/qual_*.json`
   - 写 `agent_outputs/qual_*.json`
   - 最后再写 `agent_analysis.json`

#### `stage2()` 改动

新增合并逻辑：

1. 若存在 `agent_outputs/panel_*.json`
   - 自动合并回 `panel.json`
2. 若存在 `agent_outputs/qual_*.json`
   - 自动合并进 `agent_analysis.qualitative_deep_dive`
3. 若存在 `task4_synthesis_brief.json`
   - 允许主 agent 只使用 brief 做 Task 4

原则：

- 如果中间文件不存在，不影响旧流程。
- 如果存在，则优先消费。

### D. `skills/deep-analysis/SKILL.md`

需要统一成与代码一致的真实文件驱动流程：

1. 删除当前文档里“部分已经 file-based、部分仍沿用旧上下文流程”的漂移描述。
2. 明确 Task 3 使用：
   - `agent_inputs/panel_*.json`
   - `agent_outputs/panel_*.json`
3. 明确 Task 2.5 使用：
   - `agent_inputs/qual_*.json`
   - `agent_outputs/qual_*.json`
4. 明确 Task 4 使用：
   - `agent_inputs/task4_synthesis_brief.json`
   - 已合并后的 `agent_analysis.json`

### E. `references/task3-agent-evaluation.md`

彻底改成与新流程一致：

1. 不再写“sub-agent 读 raw_data + features + investor_knowledge”
2. 改为“sub-agent 只读对应的 `agent_inputs/panel_*.json`”
3. 输出固定写到 `agent_outputs/panel_*.json`

### F. `references/task2.5-qualitative-deep-dive.md`

补充文件驱动边界：

1. 输入来自 `agent_inputs/qual_*.json`
2. 输出写到 `agent_outputs/qual_*.json`
3. 主 agent 最后再将它们折叠进 `agent_analysis.json`

### G. 测试

新增测试：

1. `test_build_agent_inputs.py`
   - 验证能从最小 raw/dims/panel 生成所有 `agent_inputs/*`
2. `test_stage2_merge_agent_outputs.py`
   - 验证 stage2 会自动合并 `panel_*.json` 和 `qual_*.json`
3. `test_task4_synthesis_brief.py`
   - 验证 Task 4 brief 包含必要字段

## 与现有产物和上游结构的兼容策略

1. 主文件名保持不变。
2. `agent_inputs/`、`agent_outputs/` 是新增层，不替代主文件。
3. stage2 在没有新文件时继续兼容旧流程。
4. 文档和代码要同步，不允许再出现“文档说有 summary 文件，代码没有”的漂移。

## 风险点

1. `SKILL.md` 现有内容很长，局部修补容易继续产生漂移。
2. 某些 agent 输出字段若不完整，自动合并时需要更强防御。
3. 现有测试可能更多覆盖旧主流程，新路径需要补最小但有效的覆盖。

## 回滚思路

1. 所有新能力都建立在新增文件层之上。
2. 如果新流程异常，只要不生成 `agent_inputs/agent_outputs`，旧流程仍可工作。
3. 代码层不删除旧逻辑，只加优先路径和回退路径。

## 验证方案

1. 单元验证 `build_agent_inputs.py`
2. 单元验证 `stage2` 自动合并
3. grep 检查文档与代码中的文件名引用一致
4. 若环境允许，运行最小 `pytest` 子集验证新增路径

## 当前发现的关键冲突（实施前必须解决）

1. `SKILL.md` 已写入 file-based `0_raw_data_summary.json / 2a/2b/2c/2d` 流程，但代码未实现。
2. `references/task3-agent-evaluation.md` 仍保留旧版“读 raw_data + features”的长上下文模式。
3. 当前系统没有统一的 agent 中间文件生成器，导致文件化只能靠文档约定而不是代码保证。

本次实施以“新增 `agent_inputs/agent_outputs` 双层协议”解决以上冲突。
