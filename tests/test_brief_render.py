from brief.render import render_brief
from brief.summarize import BriefEntry


def test_render_has_source_and_as_of(tmp_path):
    e = BriefEntry(code="600519", name="贵州茅台", summary="要点", lean="偏多", flags=[],
                   sources=["quote: mootdx | As of: 2026-11-25 15:00"], missing=[])
    path = render_brief("2026-11-25", [e], tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "600519" in text and "数据来源" in text and "2026-11-25" in text


def test_render_marks_missing(tmp_path):
    e = BriefEntry(code="000001", name="平安银行", summary="", lean="中性", flags=[],
                   sources=[], missing=["quote", "fund_flow"])
    text = render_brief("2026-11-25", [e], tmp_path).read_text(encoding="utf-8")
    assert "数据不可用" in text and "quote" in text
