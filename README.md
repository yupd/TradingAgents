# TradingAgents A 股研究工具

在 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) `0.7.x` 上裁剪出的自维护 A 股投研工具：

- **每日简报**：对 `watchlist.yaml` 里的自选股，一次生成一份中文 Markdown 简报；每只票一次轻量模型调用，数字由代码从数据源取，不由模型编。
- **单票深挖**：7 个分析师（市场/情绪/新闻/基本面/政策/游资/解禁）→ 多空辩论 → 研究经理 → 交易员 → 三风控 → 组合经理，输出中文 Markdown + HTML 报告。
- **不做**：交易执行、组合持仓、回测、决策结算、推送、Web UI。

## 安装

要求 Python ≥ 3.12。

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env        # 填模型 key
```

本机可用现成运行时：

```bash
~/.local/share/vibe-astock-python312/bin/python3 -m venv .venv
```

## 模型

模型走 OpenAI 兼容接口（DeepSeek、OpenAI、Anthropic、Google、Ollama/vLLM 等）。最少配置：

```ini
TRADINGAGENTS_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
```

## 使用

```bash
# 每日简报
.venv/bin/python -m cli.main brief --date 2026-11-25

# 深挖一只 A 股
.venv/bin/python -m cli.main deep 600519 2026-11-25

# 深挖港股（只用上游 4 个分析师，走 yfinance）
.venv/bin/python -m cli.main deep 0700.HK
```

报告路径：

- 简报：`reports/brief/YYYY-MM-DD.md`
- 深挖：`reports/deep/<CODE>/<YYYY-MM-DD>/complete_report.md`

## 自选股

`watchlist.yaml`：

```yaml
stocks:
  - code: "600519"
    notes: 白酒龙头
  - code: "000001"
```

## 数据源

- 行情/指标：mootdx → 东财 → 腾讯 → 新浪
- 三表/基本面：东财 datacenter（按公告日过滤）；mootdx/腾讯只做当前快照
- 公告/研报/新闻：东财
- 资金流/龙虎榜/解禁/概念/北向/预期：东财 / AkShare

历史深挖的截止口径：行情按交易日，财报按公告日，公告/研报/新闻按发布时间 ≤ 当天 15:00；没有历史时点值的数据会显式标注，不使用当前值冒充历史值。

## 数据源限制

- 全部为免费公开源，接口会变；`pytest` 的离线测试不会发现线上接口失效，需定期跑 `pytest -m integration` 或手动跑一次简报。
- AkShare/mootdx 的接口字段可能随版本漂移；关键字段变化时报告会显式写 `DATA_UNAVAILABLE`，不会静默补数。
- 仅供个人研究，不对外分发抓取数据。

## 测试

```bash
.venv/bin/pytest -q
bash scripts/smoke.sh        # 打印简报/深挖的手动验收命令
```

## 来源与许可

Apache-2.0。fork 自 TauricResearch/TradingAgents 0.7.x；A 股数据层与政策/游资/解禁分析师的写法参考 TradingAgents-astock 与 TradingAgents-A-share。详见 `NOTICE`。
