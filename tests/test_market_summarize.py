from market.fetch import (
    IndexQuote,
    Industries,
    MarketFacts,
    MarketNews,
    Sentiment,
    Turnover,
)
from market.rules import Trend
from market.summarize import (
    Summary,
    facts_block,
    safe_summarize,
    summarize_market,
    validate_numbers,
)


def _full_facts() -> MarketFacts:
    return MarketFacts(
        trade_date="2026-11-25",
        indices=[
            IndexQuote(
                name="上证",
                code="sh000001",
                close=3456.78,
                change_pct=1.23,
                return_5d=2.10,
                return_20d=3.40,
                return_60d=-1.20,
                ma20=3400.00,
                ma60=3350.00,
                volume_ratio=1.15,
            )
        ],
        turnover=Turnover(sh=5000.12, sz=6500.34, total=11500.46, note="沪深股票成交额"),
        sentiment=Sentiment(
            limit_up=45, limit_down=3, broken=8, broken_rate=15.1, max_streak=5
        ),
        industries=Industries(
            gainers=[("半导体", 3.2), ("电池", 2.1)],
            losers=[("银行", -1.5), ("保险", -0.9)],
            as_of="2026-11-25 15:00",
            note="仅当日，历史不可用",
        ),
        news=[
            MarketNews(title="央行降准", published_at="2026-11-25 09:00", source="东财")
        ],
        trend=Trend("上行", True, True, True),
    )


def test_sections_appear_in_fixed_order():
    block = facts_block(_full_facts())
    headings = ["## 档位", "## 指数", "## 成交额", "## 情绪", "## 行业", "## 新闻"]
    positions = [block.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert block.startswith("# 大盘事实 2026-11-25")


def test_full_facts_render_key_values():
    block = facts_block(_full_facts())
    assert "3456.78" in block
    assert "合计：11500.46 亿元" in block
    assert "涨停：45" in block
    assert "炸板率：15.1%" in block
    assert "半导体 +3.2%" in block
    assert "银行 -1.5%" in block
    assert "仅当日，历史不可用" in block
    assert "趋势：上行" in block
    assert "收盘>MA20: 是" in block


def test_news_line_is_labelled_as_unverified():
    block = facts_block(_full_facts())
    assert "- [东财 2026-11-25 09:00] 央行降准（媒体口径，未核实）" in block


def test_partial_data_has_no_dangling_units():
    facts = MarketFacts(
        trade_date="2026-11-25",
        indices=[IndexQuote(name="上证", code="sh000001", close=3456.78)],
        turnover=None,
    )
    block = facts_block(facts)
    assert "不可用%" not in block
    assert "涨跌 不可用" in block
    assert "不可用 亿元" not in block
    assert "## 成交额\n不可用" in block


class _FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[str] = []

    def invoke(self, prompt: str):
        self.calls.append(prompt)
        return type("Message", (), {"content": self.content})()


def test_summarize_calls_model_once_with_facts_and_constraints():
    llm = _FakeLLM("  要点一\n要点二  ")
    summarize_market(_full_facts(), llm)

    assert len(llm.calls) == 1
    prompt = llm.calls[0]
    assert "# 大盘事实" in prompt
    assert "趋势：上行" in prompt
    assert "3–5 条" in prompt
    assert "不得引入事实之外的数字" in prompt
    assert "不得改档位" in prompt


def test_summarize_returns_stripped_model_content():
    llm = _FakeLLM("  解释文本  ")
    assert summarize_market(_full_facts(), llm) == "解释文本"


def test_summarize_accepts_plain_string_result():
    class _StringLLM:
        def invoke(self, prompt: str) -> str:
            return " 纯文本 "

    assert summarize_market(_full_facts(), _StringLLM()) == "纯文本"


_FACTS_TEXT = "上证收于 3476.88\n涨停 70 家\n成交额 6,539.10 亿元"


def test_validate_numbers_drops_sentence_with_unknown_number():
    text = "上证收于 3476.88。预计明日 9999 点。涨停 70 家。成交额 6539.10%。"
    result = validate_numbers(text, _FACTS_TEXT)

    assert result.dropped == 1
    assert "9999" not in result.text
    assert "3476.88" in result.text
    assert "涨停 70 家" in result.text
    assert "6539.10%" in result.text


def test_validate_numbers_leaves_text_without_numbers_untouched():
    text = "市场情绪回暖，暂无数据。"
    assert validate_numbers(text, _FACTS_TEXT) == Summary(text=text, dropped=0)


def test_validate_numbers_all_invalid_yields_empty_text():
    text = "明日 9999 点。支撑 8888 点！"
    result = validate_numbers(text, _FACTS_TEXT)

    assert result.text == ""
    assert result.dropped == 2


def test_validate_numbers_drops_chunk_with_mixed_numbers_whole():
    result = validate_numbers("上证 3476.88 与 9999 点。", _FACTS_TEXT)

    assert result.text == ""
    assert result.dropped == 1


def test_missing_groups_render_unavailable_without_raising():
    block = facts_block(MarketFacts(trade_date="2026-11-25"))
    assert "趋势：无法判定" in block
    assert block.count("不可用") == 5
    for heading in (
        "## 档位",
        "## 指数",
        "## 成交额",
        "## 情绪",
        "## 行业",
        "## 新闻",
    ):
        assert heading in block


class _RaisingLLM:
    def invoke(self, prompt: str):
        raise RuntimeError("model down")


def test_safe_summarize_degrades_when_model_raises():
    result = safe_summarize(_full_facts(), _RaisingLLM())

    assert result.text == "摘要生成失败"
    assert result.dropped == 0


def test_safe_summarize_degrades_when_all_sentences_dropped():
    result = safe_summarize(_full_facts(), _FakeLLM("- 目标 9999 点。"))

    assert result.text == "摘要生成失败"
    assert result.dropped == 1


def test_safe_summarize_keeps_valid_sentences_and_dropped_count():
    llm = _FakeLLM("- 上证收于 3456.78。\n- 目标 9999 点。")
    result = safe_summarize(_full_facts(), llm)

    assert result.text == "- 上证收于 3456.78。"
    assert result.dropped == 1
    assert "已丢弃" not in result.text


def test_safe_summarize_drops_northbound_sentences():
    llm = _FakeLLM("- 指数放量上行。\n- 北向资金今日净流入。")
    result = safe_summarize(_full_facts(), llm)

    assert "北向" not in result.text
    assert "指数放量上行。" in result.text


def test_safe_summarize_drops_conflicting_trend_level_sentence():
    llm = _FakeLLM("- 指数放量上行。\n- 市场转为下行。")
    result = safe_summarize(_full_facts(), llm)

    assert "下行" not in result.text
    assert result.text == "- 指数放量上行。"


def test_safe_summarize_drops_trend_wording_when_trend_unknown():
    facts = _full_facts()
    facts.trend = None
    llm = _FakeLLM("- 市场维持震荡。\n- 成交额 11500.46 亿元。")

    result = safe_summarize(facts, llm)

    assert "震荡" not in result.text
    assert "11500.46" in result.text


def test_safe_summarize_falls_back_when_every_claim_is_dropped():
    result = safe_summarize(_full_facts(), _FakeLLM("- 市场转入下行。"))

    assert result.text == "摘要生成失败"
