## Summary

This PR introduces a file-driven agent pipeline for `deep-analysis`, aimed at local models with limited context windows such as `oMLX + Qwen3.6 (128K)`.

The core change is to stop treating the agent layer as a long-context continuation of `raw_data.json` and instead split agent work into staged filesystem artifacts:

- `agent_inputs/*` for deterministic briefs
- `agent_outputs/*` for sub-agent results
- `stage2()` auto-merge of file-based outputs back into canonical artifacts

The canonical task files remain unchanged:

- `raw_data.json`
- `dimensions.json`
- `panel.json`
- `agent_analysis.json`
- `synthesis.json`

## What Changed

### Code

- Added nested cache JSON helpers in `skills/deep-analysis/scripts/lib/cache.py`
- Added `skills/deep-analysis/scripts/build_agent_inputs.py`
  - builds `agent_inputs/executive_summary.json`
  - builds grouped `panel_*.json` briefs
  - builds grouped `qual_*.json` briefs
  - builds `task4_synthesis_brief.json`
  - merges `agent_outputs/*` back into `panel.json` / `agent_analysis.json`
- Updated `skills/deep-analysis/scripts/run_real_test.py`
  - `stage1()` now generates `agent_inputs/*`
  - `stage2()` now auto-merges `agent_outputs/*`

### Docs

- Synced `skills/deep-analysis/SKILL.md` to the new file-driven flow
- Updated `references/task3-agent-evaluation.md`
- Updated `references/task2.5-qualitative-deep-dive.md`
- Added root-level `spec.md` as the implementation blueprint

### Tests

Added:

- `test_build_agent_inputs.py`
- `test_stage2_merge_agent_outputs.py`
- `test_task4_synthesis_brief.py`

## Why

Before this change, the repository was already partially file-based at the script layer, but the agent layer still depended on re-reading large artifacts into context:

- full `raw_data.json`
- large `panel.json`
- 6-dimension qualitative materials
- investor group reasoning inputs

That pattern is fragile for 128K local models and degrades the exact stages where model quality matters most:

- Task 2.5 qualitative deep dive
- Task 3 investor role-play
- Task 4 synthesis / narrative generation

This PR narrows each sub-agent to the smallest task-specific input file and preserves intermediate reasoning as structured files.

## Validation

Completed:

- `python3 -m py_compile` on:
  - `build_agent_inputs.py`
  - `run_real_test.py`
  - `lib/cache.py`
  - the three new test files
- Minimal runtime validation of:
  - `build_agent_inputs()`
  - `merge_agent_outputs()`

Known limitation during this branch:

- `pytest` is not installed in the current environment
- full end-to-end smoke test depends on installing missing runtime packages (`akshare`, `pandas`, etc.)

## Compatibility

- Old main artifacts remain intact
- New file-driven artifacts are additive
- If `agent_inputs/*` / `agent_outputs/*` are absent, the old path still works

## Follow-up

- Run a real ticker smoke test after runtime dependencies are installed
- Add stricter schema checks for `agent_outputs/*`
- Consider one more pass to reduce duplicated guidance in `SKILL.md`
