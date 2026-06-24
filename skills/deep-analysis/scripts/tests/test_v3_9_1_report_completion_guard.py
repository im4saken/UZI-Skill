from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_stage2_uses_strict_standalone_size_guard():
    import run_real_test as rrt

    assert rrt.MIN_STANDALONE_REPORT_BYTES >= 400 * 1024


def test_task5_docs_have_stop_rule():
    skill = (ROOT.parent / "SKILL.md").read_text(encoding="utf-8")
    task5 = (ROOT.parent / "references" / "task5-report-assembly.md").read_text(encoding="utf-8")

    assert "不要反复读取/复查 HTML 内容" in skill
    assert "不允许进入“我再看看 report content”式的循环自检" in task5
