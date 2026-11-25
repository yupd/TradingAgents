from brief.fetch import StockFacts
from brief.rules import Flag
from brief.summarize import summarize


class FakeLLM:
    def __init__(self):
        self.seen = []

    def invoke(self, messages):
        self.seen.append(str(messages))

        class M:
            content = "1. 主力净流入。\n2. 量能放大。\n倾向：偏多"

        return M()


def test_summary_has_lean_and_keeps_facts():
    llm = FakeLLM()
    facts = StockFacts(code="600519", name="贵州茅台", missing=[], fund_flow="主力净流入 1.2 亿")
    entry = summarize(facts, [Flag("volume_spike", "放量", "量比 2.5")], llm)
    assert entry.lean == "偏多"
    assert "1.2 亿" in llm.seen[-1]
    assert "放量" in llm.seen[-1]


def test_one_stock_failure_does_not_raise():
    from brief.summarize import safe_summarize

    class Boom:
        def invoke(self, messages):
            raise TimeoutError("slow")

    entry = safe_summarize(StockFacts(code="600519", name="贵州茅台"), [], Boom())
    assert entry.code == "600519" and entry.lean == "中性" and "摘要失败" in entry.summary


def test_news_source_line_is_reported():
    from brief.summarize import _sources

    facts = StockFacts(code="600519", name="贵州茅台",
                       announcements=["Source: 东财公告 | As of: 2026-06-01 10:00"])
    assert any("东财公告" in line for line in _sources(facts))
