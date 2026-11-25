"""One cheap model call per stock: facts in, a short view out."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .fetch import StockFacts
from .rules import Flag


@dataclass(frozen=True)
class BriefEntry:
    code: str
    name: str
    summary: str
    lean: str                    # 偏多 / 中性 / 偏空
    flags: list[Flag]
    sources: list[str]
    missing: list[str]


_LEAN_RE = re.compile(r"(?:倾向|结论)\s*[:：]\s*(偏多|中性|偏空)")
_SOURCE_RE = re.compile(r"Source: ([^|\n]+) \| As of: ([^\n]+)")


def _source_line(label: str, text: str) -> str | None:
    match = _SOURCE_RE.search(text or "")
    return f"{label}: {match.group(1).strip()} | As of: {match.group(2).strip()}" if match else None


def _sources(facts: StockFacts) -> list[str]:
    sources = []
    if facts.quote is not None:
        sources.append(f"quote: {facts.quote.source} | As of: {facts.quote.as_of}")
    if facts.bars:
        sources.append(f"bars: {facts.bars[-1].source} | As of: {facts.bars[-1].date}")
    for label, text in (("fund_flow", facts.fund_flow), ("lockup", facts.lockup)):
        line = _source_line(label, text)
        if line:
            sources.append(line)
    for text in facts.announcements:
        line = _source_line("news", text)
        if line:
            sources.append(line)
    return sources


def _prompt(facts: StockFacts, flags: list[Flag]) -> str:
    flag_lines = "\n".join(f"- {flag.label}: {flag.detail}" for flag in flags) or "（无）"
    announcement = "\n".join(facts.announcements)[:2000] or "（无）"
    return f"""你是一名 A 股研究助理。只使用下面给出的事实写简报，不得补充任何数字或新闻。

代码：{facts.code}  名称：{facts.name}

规则标记：
{flag_lines}

资金流：
{facts.fund_flow[:2000] or '（无）'}

解禁：
{facts.lockup[:1000] or '（无）'}

公告/资讯：
{announcement}

请输出 3–5 条要点（每条一行），最后一行写“倾向：偏多/中性/偏空”。
数字必须与上面事实一致；数据缺失就直接写缺失。"""


def summarize(facts: StockFacts, flags: list[Flag], llm) -> BriefEntry:
    response = llm.invoke(_prompt(facts, flags))
    text = getattr(response, "content", str(response)).strip()
    match = _LEAN_RE.search(text)
    lean = match.group(1) if match else "中性"
    summary = text.replace(match.group(0), "").strip() if match else text + "\n（摘要解析失败，倾向按中性处理）"
    return BriefEntry(code=facts.code, name=facts.name, summary=summary, lean=lean,
                      flags=list(flags), sources=_sources(facts), missing=list(facts.missing))


def safe_summarize(facts: StockFacts, flags: list[Flag], llm) -> BriefEntry:
    """One stock's failure must not cost the whole brief."""
    try:
        return summarize(facts, flags, llm)
    except Exception as exc:
        return BriefEntry(code=facts.code, name=facts.name, summary=f"摘要失败：{type(exc).__name__}",
                          lean="中性", flags=list(flags), sources=_sources(facts),
                          missing=list(facts.missing))
