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
