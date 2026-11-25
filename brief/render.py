"""One Markdown file for the day's watchlist."""

from __future__ import annotations

from pathlib import Path

from .summarize import BriefEntry

_ORDER = ("偏多", "中性", "偏空")
_HEADINGS = {"偏多": "偏多", "中性": "中性", "偏空": "偏空"}


def render_brief(trade_date: str, entries: list[BriefEntry], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{trade_date}.md"
    lines = [f"# A 股研究简报 {trade_date}", "",
             f"数据截止：{trade_date} 15:00；摘要由模型生成，数字来自数据源。", ""]
    for lean in _ORDER:
        group = [entry for entry in entries if entry.lean == lean]
        if not group:
            continue
        lines += [f"## {_HEADINGS[lean]}", ""]
        for entry in group:
            lines += [f"### {entry.code} {entry.name} — {entry.lean}", ""]
            if entry.missing:
                lines.append(f"**数据不可用：** {', '.join(entry.missing)}")
                lines.append("")
            if entry.summary:
                lines += [entry.summary, ""]
            if entry.flags:
                lines += [f"- {flag.label}：{flag.detail}" for flag in entry.flags] + [""]
            lines += [f"数据来源：{'；'.join(entry.sources) if entry.sources else '—'}", ""]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path
