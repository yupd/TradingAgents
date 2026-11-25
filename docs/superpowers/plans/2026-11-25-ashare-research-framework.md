# A 股投研工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 0.7.x 底座上裁出一套自维护的 A 股投研工具：每天批量出中文简报，偶尔对单票做 7 分析师完整深挖。

**Architecture:** fork 上游 `TradingAgents` 0.7.x，删除回测/持仓/记忆与全部非 A 股数据源；新增 `vendors/a_share`（mootdx 行情 + AkShare/东财/新浪 公告研报新闻信号）与独立于 Agent 图的 `brief/` 薄管道；深挖继续走 LangGraph 图，7 个分析师，中文输出。

**Tech Stack:** Python 3.12、LangGraph/LangChain（沿用上游）、mootdx、AkShare、pandas、pytest、uv/pip。

**Spec:** `docs/superpowers/specs/2026-11-25-ashare-research-framework-design.md`

## Global Constraints

- Python `>=3.12`；运行用本机 `~/.local/share/vibe-astock-python312/bin/python3` 建 venv。
- 目标仓库：`~/work/TradingAgents`（fork：`https://github.com/yupd/TradingAgents`）；基线 `0.7.x`（`9fa1196`），开发分支 `feat/ashare-research`。不要 push、不要改 main。
- 许可：Apache-2.0；保留上游 LICENSE 与版权头；新增 `NOTICE` 注明 fork 与从 astock/A-share 移植的部分。
- 数据只允许免费源：mootdx、AkShare、东财/腾讯/新浪直连；不得引入付费 API。
- 时间口径：历史深挖截止 `trade_date 15:00`；财报按公告日；公告/研报/新闻按发布时间；当天盘后数据不进入当天历史结论。
- 数据缺失必须返回 `NO_DATA_AVAILABLE` / `DATA_UNAVAILABLE` 哨兵或明确降级说明，**不得估算或编造数字**。
- 输出中文；深挖评级固定五档 `Buy/Overweight/Hold/Underweight/Sell`，无法解析记 `REVIEW`，不得默认 `Hold`。
- 报告路径：`reports/brief/YYYY-MM-DD.md`、`reports/deep/<code>/<YYYY-MM-DD>/`。
- 不新增推送、Web UI、交易执行、组合持仓、回测、跨轮记忆。
- 所有测试默认离线（monkeypatch 数据源），真实接口测试加 `@pytest.mark.integration`。
- 提交信息中文，遵循 `type: 标题` 格式，不加签名。

## Review Focus

1. **历史深挖的前视偏差**：D 日盘后发布的公告/龙虎榜不得进入 D 日结论；用户期望"复盘 2026-06-01"看到的是当天已知信息。→ Task 5、Task 7 的 as-of 测试。
2. **财报没有公告日**：数据源缺 `publish_date` 时，用户期望明确"无法按时点过滤"，而不是静默用最新版。→ Task 4 的缺日期测试。
3. **代码格式变体**：`600519` / `SH600519` / `600519.SH` / `600519.SS` 应等价；`0700.HK` 不得被送进 A 股数据源。→ Task 3、Task 9 的路由测试。
4. **免费源整体失败**：mootdx/AkShare 全挂时，用户期望看到"数据不可用"而不是崩溃或空字符串。→ Task 4、Task 5、Task 7 的失败链测试。
5. **模型编造数字**：简报与深挖报告中的每个数字必须有来源与日期；数据缺失的股票要显式标出。→ Task 11、Task 12 的渲染断言。

---

## File Structure

```
~/work/TradingAgents/                 # 分支 feat/ashare-research，基线 0.7.x
├── tradingagents/
│   ├── agents/
│   │   ├── analysts/{market,sentiment,news,fundamentals,policy,hot_money,lockup}_analyst.py
│   │   ├── researchers/ managers/ risk_mgmt/ trader/          # 沿用 0.7.x
│   │   ├── tools.py                     # 修改：新增信号工具、快照改路由
│   │   ├── rating.py                    # 修改：中文映射
│   ├── graph/
│   │   ├── setup.py                     # 修改：7 分析师、去掉 memory 节点
│   │   ├── trading_graph.py             # 修改：去掉 memory/portfolio
│   │   └── propagation.py               # 修改：去掉 past_context/memory_note
│   ├── dataflows/
│   │   ├── router.py                    # 修改：a_share vendor 注册
│   │   ├── config.py                    # 沿用
│   │   ├── symbols.py                   # 沿用；市场选路放 a_share/market.py
│   │   └── vendors/
│   │       ├── a_share/
│   │       │   ├── __init__.py
│   │       │   ├── types.py             # dataclass：DailyBar/Snapshot/StatementRow/NewsItem
│   │       │   ├── symbols.py           # parse_ashare / market_of
│   │       │   ├── calendar.py          # 交易日历
│   │       │   ├── quotes.py            # mootdx→东财→腾讯→新浪
│   │       │   ├── fundamentals.py      # 新浪/东财三表，按公告日过滤
│   │       │   ├── news.py              # 公告/研报/快讯/财新
│   │       │   ├── signals.py           # 游资/资金/北向/解禁/行业/预期
│   │       │   ├── format.py            # typed → 0.7.x 字符串契约
│   │       │   └── market.py            # apply_market_config(按市场设 vendor)
│   │       └── yahoo/                   # 仅保留港股所需
│   ├── reporting.py / report_html.py    # 修改：来源与截止时间抬头，去掉 memory
│   └── default_config.py                # 修改：data_vendors、去掉 settlement 配置
├── brief/
│   ├── __init__.py
│   ├── watchlist.py
│   ├── fetch.py
│   ├── rules.py
│   ├── summarize.py
│   └── render.py
├── cli/{main.py,run.py,models.py,...}   # 修改：deep / brief / resume
├── tests/
├── watchlist.yaml
├── NOTICE
└── README.md
```

---

### Task 1: 在 fork 的 0.7.x 基线上建分支并删掉非目标模块

**Files:**
- Create: `~/work/TradingAgents`（fork 仓库，分支 `feat/ashare-research`）
- Delete: `tradingagents/backtest.py`、`tradingagents/portfolio.py`、`tradingagents/memory/`、`tradingagents/dataflows/vendors/{sec_edgar,fred,polymarket,alpha_vantage,reddit,stocktwits}*`、`Dockerfile`、`docker-compose.yml`
- Delete: 直接以被删模块为主题的测试（见 Step 3）
- Create: `tests/test_removed_modules.py`

**Interfaces:**
- Consumes: 无
- Produces: 一个可导入、可跑测试的 fork；`tradingagents.memory`、`tradingagents.backtest`、`tradingagents.portfolio` 不再存在。

- [ ] **Step 1: 建分支与环境**

```bash
git clone https://github.com/yupd/TradingAgents.git ~/work/TradingAgents
cd ~/work/TradingAgents
git checkout 0.7.x
git switch -c feat/ashare-research
~/.local/share/vibe-astock-python312/bin/python3 -m venv .venv
.venv/bin/pip install -e . pytest
git add -A && git commit -m "chore: 在 0.7.x 基线上建立 A 股开发分支"
```

注意：基线是 `0.7.x`（`9fa1196`），不是 `main`（main 已是 TypeScript v1.0.0）。不要 push。

- [ ] **Step 2: 写失败测试**

```python
# tests/test_removed_modules.py
import importlib.util

def test_removed_modules_are_gone():
    for name in ("tradingagents.memory", "tradingagents.backtest", "tradingagents.portfolio"):
        assert importlib.util.find_spec(name) is None, f"{name} should be removed"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_removed_modules.py -v`
Expected: FAIL（模块仍存在）

- [ ] **Step 4: 删除模块与测试**

```bash
rm -rf tradingagents/memory tradingagents/backtest.py tradingagents/portfolio.py
rm -rf tradingagents/dataflows/vendors/sec_edgar tradingagents/dataflows/vendors/fred.py \
       tradingagents/dataflows/vendors/polymarket.py tradingagents/dataflows/vendors/alpha_vantage \
       tradingagents/dataflows/vendors/reddit.py tradingagents/dataflows/vendors/stocktwits.py
rm tests/test_backtest.py tests/test_memory_log.py tests/test_cli_memory_log.py \
   tests/test_memory_pointintime.py tests/test_portfolio_context.py tests/test_fred.py \
   tests/test_polymarket.py tests/test_sec_edgar.py tests/test_alpha_vantage_hardening.py \
   tests/test_reddit_fallback.py tests/test_stocktwits_resilience.py tests/test_social_lookahead.py
rm -f Dockerfile docker-compose.yml
```

其余引用被删模块的测试（`test_graph_end_to_end.py`、`test_dataflows_config.py`、`test_vendor_routing.py`、`test_news_lookahead.py`、`test_undated_tools_as_of.py`、`test_instrument_identity.py`、`test_symbol_normalization_paths.py`、`test_rating_integrity.py`、`test_cache_writes.py`、`test_cli_commands.py`、`test_report_html.py`、`test_structured_agents.py`、`test_structured_agent_prompts.py`、`test_no_data_handling.py`、`test_checkpoint_resume.py`、`test_get_scrubbed.py`、`test_post_screen.py`、`test_statement_knowledge_time.py`、`test_fundamentals_lookahead.py`）**不得整文件跳过**：删掉只针对已删功能的用例，保留其余，改到能跑。

- [ ] **Step 5: 清理导入，让包可导入**

修改 `tradingagents/dataflows/vendors/__init__.py`、`tradingagents/dataflows/router.py`、`tradingagents/agents/tools.py`、`tradingagents/default_config.py` 中指向已删模块的导入与配置项；从分析师提示词与工具列表里删掉 `get_macro_indicators`、`get_prediction_markets`、Reddit/StockTwits 相关内容。把 `tradingagents/__init__.py` 的 `__version__` 改为 `0.1.0`。

- [ ] **Step 6: 运行测试**

Run: `pytest tests/test_removed_modules.py -v && python -c "import tradingagents"`
Expected: PASS；导入无报错。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore: 删除回测/持仓/记忆与非 A 股数据源"
```

---

### Task 2: 去掉记忆/持仓残留，主干测试转绿

**Files:**
- Modify: `tradingagents/graph/trading_graph.py`、`graph/setup.py`、`graph/propagation.py`、`agents/state.py`、`agents/managers/portfolio_manager.py`、`reporting.py`、`report_html.py`、`cli/main.py`、`cli/run.py`、`default_config.py`
- Test: `tests/test_no_memory_surfaces.py`、`tests/test_cli_commands.py`

**Interfaces:**
- Consumes: Task 1 的删减结果
- Produces: `TradingAgentsGraph(selected_analysts, debug, config, callbacks)` 不再接受/写入 `past_context`、`memory_note`；`write_report_tree(final_state, ticker, save_path, settings=None, html=True)` 保持签名；CLI 无 `backtest`、无 `--portfolio`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_no_memory_surfaces.py
from tradingagents.agents.state import AgentState
from tradingagents.reporting import _header

def test_state_has_no_memory_keys():
    annotations = AgentState.__annotations__
    assert "past_context" not in annotations
    assert "memory_note" not in annotations

def test_report_header_has_no_memory_line():
    assert "Memory log" not in _header("600519", {"final_trade_decision": "Rating: Hold"}, None)
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_no_memory_surfaces.py -v`
Expected: FAIL（键与抬头仍存在）

- [ ] **Step 3: 删除残留**

- `trading_graph.py`：删 `from tradingagents.memory import ...`、`self.memory_log`、`_memory_step`、`_memory_as_of`、`settle_pending`、`settle_all_pending`、`store_decision`，`setup_graph` 不再传 `memory_node`。
- `setup.py`：删 `memory_node` 参数与 `Memory Log` 节点。
- `propagation.py`、`agents/state.py`：删 `past_context`、`memory_note`。
- `portfolio_manager.py`：删拼接 `past_context` 的段落。
- `reporting.py:44`、`report_html.py:243`：删 memory 抬头行。
- `tests/conftest.py`：删 `TRADINGAGENTS_MEMORY_LOG_PATH` 的设置与 memory 相关 fixture。
- `default_config.py`：删 `memory_log_path`、`memory_log_max_entries`、`benchmark_*`、`holding_period_days`。
- `cli/main.py`、`cli/run.py`：删 `backtest` 命令、`--portfolio` 选项及 `portfolio` 参数。

- [ ] **Step 4: 跑相关测试并修复**

Run: `pytest tests/test_no_memory_surfaces.py tests/test_graph_end_to_end.py tests/test_cli_commands.py -v`
Expected: PASS（CLI 测试按新命令集重写，不允许 skip）

- [ ] **Step 5: 跑全量**

Run: `pytest -q`
Expected: PASS；若有收集错误，继续清理到全绿。

- [ ] **Step 6: Commit**

```bash
git commit -am "refactor: 移除记忆、持仓与回测残留入口"
```

---

### Task 3: A 股代码解析、市场选路与交易日历

**Files:**
- Create: `tradingagents/dataflows/vendors/a_share/__init__.py`、`symbols.py`、`calendar.py`、`market.py`
- Test: `tests/test_ashare_symbols.py`、`tests/test_ashare_calendar.py`、`tests/test_market_routing.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `parse_ashare(raw: str) -> AStockSymbol`（`AStockSymbol.code: str` 六位、`.exchange: Literal["SH","SZ","BJ"]`、`.yahoo: str`、`.display: str`），非法输入抛 `ValueError`
  - `market_of(raw: str) -> Literal["CN","HK"]`，其他抛 `ValueError`
  - `previous_trade_date(value: str) -> str`、`is_trade_date(value: str) -> bool`、`get_trade_dates() -> tuple[date, ...]`
  - `apply_market_config(raw: str, config: dict) -> dict`：返回按市场改写的 config（CN → `a_share`；HK → `yfinance`）
- `market_of` 与 `apply_market_config` 都在 `a_share/market.py`。

- [ ] **Step 0: 加依赖并做 pandas 兼容性检查**

在 `pyproject.toml` 的 `dependencies` 加入 `akshare`、`mootdx`、`pyyaml`（先不写上界），然后：

```bash
.venv/bin/pip install -e .
.venv/bin/python -c "import pandas, akshare, mootdx, yaml; print(pandas.__version__)"
```

若 pandas 3 与 AkShare/mootdx 冲突，在 `pyproject.toml` 固定 `pandas==2.3.*`，并在本任务 commit message 中写明原因；不冲突则保留上游 `pandas>=3.0.6`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ashare_symbols.py
import pytest
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare
from tradingagents.dataflows.vendors.a_share.market import market_of

@pytest.mark.parametrize("raw", ["600519", "SH600519", "600519.SH", "600519.SS", "sh600519"])
def test_shanghai_variants(raw):
    s = parse_ashare(raw)
    assert (s.code, s.exchange, s.yahoo, s.display) == ("600519", "SH", "600519.SS", "600519.SH")

@pytest.mark.parametrize("raw,exchange", [("000001", "SZ"), ("SZ000001", "SZ"), ("300750", "SZ"),
                                          ("688017", "SH"), ("830799", "BJ"), ("430047", "BJ")])
def test_exchange_inference(raw, exchange):
    assert parse_ashare(raw).exchange == exchange

@pytest.mark.parametrize("raw", ["0700.HK", "AAPL", "", "60051", "6005190"])
def test_rejects_non_ashare(raw):
    with pytest.raises(ValueError):
        parse_ashare(raw)

def test_market_routing():
    assert market_of("600519") == "CN"
    assert market_of("600519.SH") == "CN"
    assert market_of("0700.HK") == "HK"
    with pytest.raises(ValueError):
        market_of("AAPL")
```

```python
# tests/test_ashare_calendar.py
from datetime import date
import tradingagents.dataflows.vendors.a_share.calendar as cal

def test_previous_trade_date_skips_holiday(monkeypatch):
    monkeypatch.setattr(cal, "_load_dates", lambda: (date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 9)))
    assert cal.previous_trade_date("2026-10-02") == "2026-09-30"
    assert cal.is_trade_date("2026-09-30") is True
    assert cal.is_trade_date("2026-10-02") is False
```

```python
# tests/test_market_routing.py
from tradingagents.dataflows.vendors.a_share.market import apply_market_config
from tradingagents.default_config import DEFAULT_CONFIG

def test_cn_uses_ashare():
    cfg = apply_market_config("600519", DEFAULT_CONFIG)
    assert cfg["data_vendors"]["core_stock_apis"] == "a_share"
    assert cfg["data_vendors"]["fundamental_data"].startswith("a_share")

def test_hk_uses_yfinance():
    cfg = apply_market_config("0700.HK", DEFAULT_CONFIG)
    assert cfg["data_vendors"]["core_stock_apis"] == "yfinance"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_ashare_symbols.py tests/test_ashare_calendar.py tests/test_market_routing.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

- `symbols.py`：正则接受 `^(SH|SZ|BJ)?(\d{6})(\.(SH|SS|SZ|BJ))?$`；6/9 开头 → SH（900 为沪 B），0/2/3 开头 → SZ（200 为深 B），4/8 开头 → BJ；统一大写。
- `calendar.py`：`_load_dates()` 调 `ak.tool_trade_date_hist_sina()` 并缓存；测试通过 monkeypatch 注入。
- `market.py`：`.HK` 后缀 → HK；能被 `parse_ashare` 解析 → CN；否则 `ValueError("unsupported market")`。`apply_market_config` 深拷贝 config，按市场覆盖 `core_stock_apis`/`technical_indicators`/`fundamental_data`/`news_data` 的 vendor 串。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_ashare_symbols.py tests/test_ashare_calendar.py tests/test_market_routing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: A 股代码解析、市场选路与交易日历"
```

---

### Task 4: 行情与快照（mootdx → 东财 → 腾讯 → 新浪）

**Files:**
- Create: `vendors/a_share/types.py`、`quotes.py`、`format.py`、`http.py`
- Test: `tests/test_ashare_quotes.py`

**Interfaces:**
- Consumes: `parse_ashare`、`previous_trade_date`
- Produces:
  - `@dataclass DailyBar: date: str; open/high/low/close/volume: float; source: str; as_of: str`
  - `@dataclass Snapshot: code: str; name: str; price: float; prev_close: float; change_pct: float; volume: float; turnover_rate: float | None; pe_ttm: float | None; pb: float | None; source: str; as_of: str`
  - `get_daily_bars(sym: AStockSymbol, start: str, end: str) -> list[DailyBar]`
  - `get_snapshot(sym: AStockSymbol) -> Snapshot`（**仅实时**；历史日期一律走 `get_verified_market_snapshot`，由日线截断生成，不读实时接口）
  - `get_stock_data(symbol: str, start_date: str, end_date: str) -> str`（0.7.x 字符串契约）
  - `get_verified_market_snapshot(symbol: str, curr_date: str, look_back_days: int = 30) -> str`
  - `get_indicators(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str`（用 stockstats 在本地日线上算，不再依赖 Yahoo）
  - `http.em_get(url: str, params: dict | None = None, timeout: int = 15, retries: int = 3)`：东财域名 0.5s 限速、浏览器头、指数退避重试；所有东财/新浪/腾讯请求都走它
  - 全部失败时返回 `"NO_DATA_AVAILABLE: ..."` 或 `"DATA_UNAVAILABLE: ..."`，不得抛裸异常给 Agent。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ashare_quotes.py
import pandas as pd
import pytest
import tradingagents.dataflows.vendors.a_share.quotes as q
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

BARS = pd.DataFrame({"date": ["2026-11-20", "2026-11-21"], "open": [10.0, 10.2],
                     "high": [10.5, 10.6], "low": [9.9, 10.1], "close": [10.2, 10.4],
                     "volume": [1000, 1200]})

def test_daily_uses_mootdx_first(monkeypatch):
    monkeypatch.setattr(q, "_mootdx_bars", lambda sym, s, e: BARS)
    monkeypatch.setattr(q, "_em_bars", lambda *a: (_ for _ in ()).throw(AssertionError("fallback used")))
    bars = q.get_daily_bars(parse_ashare("600519"), "2026-11-18", "2026-11-21")
    assert [b.close for b in bars] == [10.2, 10.4]
    assert bars[0].source == "mootdx"

def test_daily_falls_back_to_eastmoney_then_tencent(monkeypatch):
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(q, "_em_bars", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(q, "_tencent_bars", lambda sym, s, e: BARS)
    bars = q.get_daily_bars(parse_ashare("000001"), "2026-11-18", "2026-11-21")
    assert bars[0].source == "tencent"

def test_all_fail_returns_sentinel(monkeypatch):
    for name in ("_mootdx_bars", "_em_bars", "_tencent_bars", "_sina_bars"):
        monkeypatch.setattr(q, name, lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    text = q.get_stock_data("600519", "2026-11-18", "2026-11-21")
    assert text.startswith(("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE"))

def test_format_has_source_and_as_of(monkeypatch):
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: BARS)
    text = q.get_stock_data("600519", "2026-11-18", "2026-11-21")
    assert "Source: mootdx" in text and "As of: 2026-11-21" in text

def test_indicators_use_local_bars(monkeypatch):
    import pandas as pd, numpy as np
    idx = pd.date_range("2026-08-01", periods=60, freq="D")
    bars = pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "open": 10.0,
                         "high": np.linspace(10, 11, 60), "low": 9.5,
                         "close": np.linspace(10, 11, 60), "volume": 1000})
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: bars)
    text = q.get_indicators("600519", "rsi", "2026-09-29", 30)
    assert "Source: mootdx" in text and "RSI" in text

def test_verified_snapshot_historical_never_reads_live(monkeypatch):
    monkeypatch.setattr(q, "get_snapshot", lambda *a: (_ for _ in ()).throw(AssertionError("live used")))
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: BARS)
    text = q.get_verified_market_snapshot("600519", "2026-11-21")
    assert "2026-11-21" in text and "Source: mootdx" in text

def test_em_get_retries_three_times(monkeypatch):
    import tradingagents.dataflows.vendors.a_share.http as h
    calls = {"n": 0}
    def down(*a, **k):
        calls["n"] += 1
        raise RuntimeError("down")
    monkeypatch.setattr(h.requests, "get", down)
    monkeypatch.setattr(h.time, "sleep", lambda _s: None)
    import pytest
    with pytest.raises(RuntimeError):
        h.em_get("https://push2.eastmoney.com/api/qt/stock/get")
    assert calls["n"] == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_ashare_quotes.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

- `_mootdx_bars`：`mootdx.quotes.Quotes.factory(market=..., multithread=True)` 拉日线（移植 astock 的连接探测/重试，保留其版权注释）。
- `_em_bars`：东财 `push2his` 日 K；`_tencent_bars`：腾讯 `fqkline`；`_sina_bars`：新浪 `open/hq`。
- 回退顺序固定，任一成功即停；记录 `source`。
- `get_stock_data` 用 `previous_trade_date` 截断 `end_date`，格式化表格 + 页脚（来源、截止日、复权说明）。
- 快照：腾讯 `qt.gtimg.cn` 为主（含名称、PE/PB、换手），失败回退东财；`get_snapshot` 只用于当天。
- `get_verified_market_snapshot`：取日线截断到 `curr_date`，输出最近收盘、MA/RSI/MACD 与近 30 日收盘；**不读实时接口**。
- `http.py`：把 A-share fork 的请求补丁改成**显式函数**（不全局 monkeypatch `requests.get`），负责东财 0.5s 限速、浏览器头、3 次指数退避；后续所有 HTTP 模块复用。
- `get_indicators`：取日线后用 `stockstats` 计算；支持 `rsi/macd/boll/ma/ema/atr/kdj`；输出表格 + `Source: <bars 来源>`。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_ashare_quotes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: A 股行情多源回退与快照"
```

---

### Task 5: 三表与基本面（按公告日过滤）

**Files:**
- Create: `vendors/a_share/fundamentals.py`
- Test: `tests/test_ashare_fundamentals.py`

**Interfaces:**
- Consumes: `parse_ashare`
- Produces:
  - `@dataclass StatementRow: period: str; publish_date: str | None; values: dict[str, float]; source: str`
  - `get_statement(sym, kind: Literal["income","balance","cashflow"], freq: Literal["annual","quarterly"], as_of: str) -> list[StatementRow]`
  - `get_fundamentals(ticker: str, curr_date: str | None = None) -> str`
  - `get_income_statement(ticker, freq="quarterly", curr_date=None) -> str`、`get_balance_sheet`、`get_cashflow`（同签名）
  - 公告日缺失的行：从历史模式剔除，并在输出页脚写明 `N periods withheld: no publish date`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ashare_fundamentals.py
import pytest
import tradingagents.dataflows.vendors.a_share.fundamentals as f
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

ROWS = [
    {"period": "2026-09-30", "publish_date": "2026-10-28", "revenue": 100.0},
    {"period": "2026-06-30", "publish_date": "2026-08-20", "revenue": 90.0},
    {"period": "2025-09-30", "publish_date": None, "revenue": 80.0},
]

def test_historical_filters_by_publish_date(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    rows = f.get_statement(parse_ashare("600519"), "income", "quarterly", "2026-09-15")
    assert [r.period for r in rows] == ["2026-06-30"]

def test_current_uses_latest(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    rows = f.get_statement(parse_ashare("600519"), "income", "quarterly", None)
    assert rows[0].period == "2026-09-30"

def test_missing_publish_date_is_withheld_and_said(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    text = f.get_income_statement("600519", "quarterly", "2026-09-15")
    assert "withheld: no publish date" in text
    assert "2025-09-30" not in text.split("withheld")[0]

def test_source_and_as_of_in_header(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    text = f.get_income_statement("600519", "quarterly", "2026-09-15")
    assert "Source:" in text and "As of:" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_ashare_fundamentals.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- `_load_statement(kind, exchange, code, freq)`：新浪财务三表（`money.finance.sina.com.cn`）为主，东财 `datacenter` 兜底；统一列名，保留 `publish_date`。
- `get_statement`：`as_of is None` → 取最新；否则 `publish_date <= as_of` 的最近一期（同一报告期重复披露取公告日最新）。
- 字符串格式：表头含 `Source: ... | As of: ... | Freq: ...`；单位统一为元，页脚写明。
- `get_fundamentals`：公司概况 + 估值 + 最新财务摘要，全部带来源；估值无历史时点值时标 `current snapshot, not historical`。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_ashare_fundamentals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: A 股三表与基本面，按公告日做时点过滤"
```

---

### Task 6: 公告、研报、快讯与全局新闻

**Files:**
- Create: `vendors/a_share/news.py`
- Test: `tests/test_ashare_news.py`

**Interfaces:**
- Consumes: `parse_ashare`
- Produces:
  - `@dataclass NewsItem: title: str; published_at: str; source: str; url: str | None`
  - `get_announcements(sym, start: str, end: str) -> list[NewsItem]`
  - `get_research_reports(sym, start: str, end: str) -> list[NewsItem]`
  - `get_news(ticker: str, start_date: str, end_date: str) -> str`
  - `get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str`
  - 所有历史过滤：`published_at <= f"{end_date} 15:00"`；`end_date` 为运行日时截止到运行时刻。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ashare_news.py
import tradingagents.dataflows.vendors.a_share.news as n
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

ITEMS = [
    {"title": "盘中公告", "published_at": "2026-06-01 10:00", "source": "东财"},
    {"title": "盘后公告", "published_at": "2026-06-01 16:30", "source": "东财"},
]

def test_history_cuts_at_close(monkeypatch):
    monkeypatch.setattr(n, "_load_announcements", lambda *a: ITEMS)
    titles = [i.title for i in n.get_announcements(parse_ashare("600519"), "2026-06-01", "2026-06-01")]
    assert titles == ["盘中公告"]

def test_live_run_includes_after_close(monkeypatch):
    monkeypatch.setattr(n, "_now", lambda: "2026-06-01 20:00")
    monkeypatch.setattr(n, "_load_announcements", lambda *a: ITEMS)
    titles = [i.title for i in n.get_announcements(parse_ashare("600519"), "2026-06-01", "2026-06-01")]
    assert titles == ["盘中公告", "盘后公告"]

def test_news_failure_returns_sentinel(monkeypatch):
    monkeypatch.setattr(n, "_load_announcements", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(n, "_load_research", lambda *a: [])
    text = n.get_news("600519", "2026-06-01", "2026-06-01")
    assert "DATA_UNAVAILABLE" in text or "NO_DATA_AVAILABLE" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_ashare_news.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- 公告：东财 `np-anotice-stock` / AkShare `stock_notice_report`。
- 研报：东财 `reportapi`（评级、机构、PDF 链接）。
- 快讯：东财全球快讯；财新 `stock_news_main_cx` 默认关闭（配置开关）。
- `get_news` 合并研报 + 快讯，标题/时间/来源/链接，页脚注明来源与截止。
- `get_global_news`：财联社 + 东财，按 `look_back_days` 与 `limit` 截断。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_ashare_news.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: A 股公告、研报、快讯与全局新闻"
```

---

### Task 7: 资金与情绪信号（热门榜/概念/资金流/北向/龙虎榜）

**Files:**
- Create: `vendors/a_share/signals.py`
- Test: `tests/test_ashare_signals.py`

**Interfaces:**
- Consumes: `parse_ashare`、`previous_trade_date`
- Produces（全部返回格式化字符串，带来源与 `As of`，历史日期不得用实时值）：
  - `get_hot_stocks(curr_date: str = "") -> str`
  - `get_concept_blocks(ticker: str) -> str`
  - `get_fund_flow(ticker: str, curr_date: str, include_history: bool = True) -> str`
  - `get_northbound_flow(curr_date: str, include_history: bool = False) -> str`
  - `get_dragon_tiger_board(ticker: str, curr_date: str, look_back_days: int = 30) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ashare_signals.py
import tradingagents.dataflows.vendors.a_share.signals as s

def test_fund_flow_history_mode_refuses_realtime(monkeypatch):
    monkeypatch.setattr(s, "_fetch_fund_flow", lambda *a: {"main_net": 1.2e8})
    text = s.get_fund_flow("600519", "2026-06-01", include_history=False)
    assert "实时" not in text and "2026-06-01" in text

def test_dragon_tiger_lists_seats(monkeypatch):
    monkeypatch.setattr(s, "_fetch_lhb", lambda *a: [{"date": "2026-05-28", "seat": "机构专用", "net": 3.0e7}])
    text = s.get_dragon_tiger_board("600519", "2026-06-01")
    assert "机构专用" in text and "2026-05-28" in text

def test_signal_failure_degrades(monkeypatch):
    monkeypatch.setattr(s, "_fetch_lhb", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    text = s.get_dragon_tiger_board("600519", "2026-06-01")
    assert "DATA_UNAVAILABLE" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_ashare_signals.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- 移植 astock `a_stock.py` 中 `get_hot_stocks`、`get_concept_blocks`、`get_fund_flow`、`get_northbound_flow`、`get_dragon_tiger_board`，保留版权头，改为本仓 `_fetch_*` 内部函数便于测试。
- 历史模式：用历史日线/接口历史数据；只有实时端的接口（热门榜、概念当日涨幅）在历史模式显式输出 `历史日期不提供实时快照`，不填当前值。
- 每个函数的页脚：`Source: <接口> | As of: <日期>`。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_ashare_signals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: A 股资金与情绪信号数据"
```

---

### Task 8: 事件与预期信号（解禁/一致预期/行业对比/内部人）

**Files:**
- Create: `vendors/a_share/signals.py`（追加）
- Test: `tests/test_ashare_signals_events.py`

**Interfaces:**
- Consumes: `parse_ashare`
- Produces:
  - `get_lockup_expiry(ticker: str, curr_date: str, forward_days: int = 90) -> str`
  - `get_profit_forecast(ticker: str, curr_date: str) -> str`
  - `get_industry_comparison(ticker: str, curr_date: str, top_n: int = 20) -> str`
  - `get_insider_transactions(ticker: str, curr_date: str | None = None) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ashare_signals_events.py
import tradingagents.dataflows.vendors.a_share.signals as s

def test_lockup_filters_announced_after_as_of(monkeypatch):
    rows = [{"announced": "2026-05-01", "expiry": "2026-07-01", "ratio": 3.2},
            {"announced": "2026-06-10", "expiry": "2026-08-01", "ratio": 1.0}]
    monkeypatch.setattr(s, "_fetch_lockups", lambda *a: rows)
    text = s.get_lockup_expiry("600519", "2026-06-01")
    assert "2026-07-01" in text and "2026-08-01" not in text

def test_forecast_flags_historical_snapshot(monkeypatch):
    monkeypatch.setattr(s, "_fetch_forecast", lambda *a: {"eps": 5.2, "coverage": 12})
    text = s.get_profit_forecast("600519", "2026-06-01")
    assert "current snapshot, not historical" in text

def test_insider_uses_ashare_wording(monkeypatch):
    monkeypatch.setattr(s, "_fetch_holders", lambda *a: [{"name": "某某", "change": -1.2}])
    text = s.get_insider_transactions("600519")
    assert "减持" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_ashare_signals_events.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- 移植 astock 的 `get_lockup_expiry`、`get_profit_forecast`、`get_industry_comparison`、`get_insider_transactions`（mootdx F10 股东研究 / 东财增减持）。
- 解禁按 `announced <= curr_date` 且 `expiry >= curr_date` 过滤。
- 一致预期、行业对比在历史模式标注"当前快照，非历史时点值"。
- 内部人语义为"股东/高管增减持、大宗交易"，输出中文用"增持/减持"。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_ashare_signals_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: A 股解禁、一致预期、行业对比与股东增减持"
```

---

### Task 9: 路由注册与工具包装

**Files:**
- Modify: `tradingagents/dataflows/router.py`、`tradingagents/default_config.py`、`tradingagents/agents/tools.py`、`vendors/a_share/format.py`
- Test: `tests/test_ashare_routing.py`、`tests/test_ashare_tools.py`

**Interfaces:**
- Consumes: Task 4–8 的所有字符串函数
- Produces:
  - `VENDOR_METHODS[method]["a_share"]` 覆盖：`get_stock_data`、`get_indicators`、`get_fundamentals`、`get_balance_sheet`、`get_cashflow`、`get_income_statement`、`get_news`、`get_global_news`、`get_verified_market_snapshot`、`get_insider_transactions`、`get_profit_forecast`、`get_hot_stocks`、`get_concept_blocks`、`get_fund_flow`、`get_northbound_flow`、`get_dragon_tiger_board`、`get_lockup_expiry`、`get_industry_comparison`
  - `DEFAULT_CONFIG["data_vendors"]` 的 A 股能力默认 `a_share`；港股相关保留 `yfinance`
  - `tools.py` 新增同名 `@tool` 包装；`get_verified_market_snapshot` 改为 `route_to_vendor`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ashare_routing.py
from tradingagents.dataflows import router

def test_ashare_registered_for_core_methods():
    for method in ("get_stock_data", "get_fundamentals", "get_news", "get_dragon_tiger_board"):
        assert "a_share" in router.VENDOR_METHODS[method]

def test_configured_ashare_chain(monkeypatch):
    monkeypatch.setitem(router.get_config(), "data_vendors",
                        {"core_stock_apis": "a_share", "news_data": "a_share"})
    assert router.get_vendor("core_stock_apis") == "a_share"
```

```python
# tests/test_ashare_tools.py
from tradingagents.agents.tools import get_verified_market_snapshot

def test_snapshot_is_routed(monkeypatch):
    calls = {}
    def fake(method, *args, **kwargs):
        calls["method"] = method
        calls["args"] = args
        return "ok"
    monkeypatch.setattr("tradingagents.agents.tools.route_to_vendor", fake)
    out = get_verified_market_snapshot.invoke(
        {"symbol": "600519", "curr_date": "2026-06-01", "trade_date": "2026-06-01"})
    assert out == "ok"
    assert calls["method"] == "get_verified_market_snapshot"
    assert calls["args"] == ("600519", "2026-06-01", 30)
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_ashare_routing.py tests/test_ashare_tools.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- `router.py`：导入 a_share 方法并加入 `VENDOR_METHODS`；`TOOLS_CATEGORIES` 增加 `signal_data` 分类；`OPTIONAL_CATEGORIES` 加 `signal_data`（信号失败降级不中断）。
- `default_config.py`：`data_vendors` 改为 `core_stock_apis/technical_indicators/fundamental_data/news_data/signal_data: "a_share"`；保留 `macro_data`/`prediction_markets` 为空并删除对应 vendor 选项。
- `tools.py`：新增 6 个信号工具包装；`get_verified_market_snapshot` 改为路由。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_ashare_routing.py tests/test_ashare_tools.py -v && pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: A 股数据源注册与 Agent 工具包装"
```

---

### Task 10: 评级中文映射与情绪分析师改造

**Files:**
- Modify: `tradingagents/agents/rating.py`、`agents/analysts/sentiment_analyst.py`
- Test: `tests/test_rating_chinese.py`、`tests/test_sentiment_ashare.py`

**Interfaces:**
- Consumes: Task 9 的工具
- Produces:
  - `extract_rating(text: str) -> str | None` 支持 `买入/增持/持有/减持/卖出` 与 `Buy/Overweight/Hold/Underweight/Sell`；`Rating: 买入`、`评级：增持`、`最终评级 **卖出**` 均能解析；无法解析返回 `None`
  - 情绪分析师 A 股路径只用 `get_news`、`get_fund_flow`、`get_hot_stocks`、`get_stock_data`，不引用 Reddit/StockTwits

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rating_chinese.py
import pytest
from tradingagents.agents.rating import extract_rating

@pytest.mark.parametrize("text,expected", [
    ("评级：买入", "Buy"), ("最终评级 **增持**", "Overweight"),
    ("Rating: Hold", "Hold"), ("给予减持评级", "Underweight"),
    ("目标价 18 元", None),
])
def test_chinese_rating(text, expected):
    assert extract_rating(text) == expected

def test_rating_line_wins_over_consensus():
    assert extract_rating("Consensus rating: Buy\n\nOur rating: 卖出") == "Sell"
```

```python
# tests/test_sentiment_ashare.py
from tradingagents.agents.analysts.sentiment_analyst import build_ashare_system_message

def test_ashare_sentiment_blocks_cover_four_sources():
    text = build_ashare_system_message(news_block="NEWS", flow_block="FLOW",
                                       hot_block="HOT", price_block="PRICE")
    for block in ("NEWS", "FLOW", "HOT", "PRICE"):
        assert block in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_rating_chinese.py tests/test_sentiment_ashare.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- `rating.py`：加中英词表与中文标签正则（`评级|评分|投资建议`），优先"自身评级行"再退化为全文。
- `sentiment_analyst.py`：A 股分支改为预取 `get_news` + `get_fund_flow` + `get_hot_stocks` + `get_stock_data` 四块数据，交给新的 `build_ashare_system_message(...)` 拼提示词；提示词写明"情绪证据 = 资金流 + 热门榜 + 量价 + 新闻"。非 A 股（港股）分支保留原有 StockTwits/Reddit 逻辑。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_rating_chinese.py tests/test_sentiment_ashare.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: 中文评级解析与 A 股情绪分析师"
```

---

### Task 11: 移植政策/游资/解禁三个分析师

**Files:**
- Create: `agents/analysts/policy_analyst.py`、`hot_money_analyst.py`、`lockup_analyst.py`
- Modify: `agents/__init__.py`、`graph/setup.py`、`graph/analyst_execution.py`、`graph/trading_graph.py`、`cli/selections.py`、`cli/models.py`
- Test: `tests/test_seven_analysts.py`

**Interfaces:**
- Consumes: Task 7–9 的信号工具
- Produces:
  - `create_policy_analyst(llm)`、`create_hot_money_analyst(llm)`、`create_lockup_analyst(llm)`
  - `GraphSetup.setup_graph(selected_analysts=("market","social","news","fundamentals","policy","hot_money","lockup"))`
  - 深挖默认 7 个；港股运行时只用前 4 个

- [ ] **Step 1: 写失败测试**

```python
# tests/test_seven_analysts.py
from tests.test_graph_end_to_end import ScriptedModel
from tradingagents.agents import (create_policy_analyst, create_hot_money_analyst,
                                  create_lockup_analyst)
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup

DEFAULT = ("market", "social", "news", "fundamentals", "policy", "hot_money", "lockup")

def test_factories_exist():
    for factory in (create_policy_analyst, create_hot_money_analyst, create_lockup_analyst):
        assert callable(factory)

def test_setup_accepts_seven():
    llm = ScriptedModel()
    logic = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)
    graph = GraphSetup(llm, llm, logic, max_tool_rounds=2).setup_graph(list(DEFAULT))
    assert {"Policy Analyst", "Hot Money Analyst", "Lockup Analyst"} <= set(graph.nodes)
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_seven_analysts.py -v`
Expected: FAIL（工厂与节点不存在）

- [ ] **Step 3: 实现**

- 从 astock 移植三个分析师的提示词与节点，文件头注明来源与改动；中文提示词，工具集分别为：
  - policy：`get_news`、`get_global_news`、`get_industry_comparison`
  - hot_money：`get_dragon_tiger_board`、`get_fund_flow`、`get_hot_stocks`、`get_concept_blocks`、`get_northbound_flow`、`get_industry_comparison`
  - lockup：`get_lockup_expiry`、`get_insider_transactions`、`get_fundamentals`、`get_news`
- `setup.py`：分析师注册表加三个 key；`trading_graph.py` 默认 `selected_analysts` 改为 7 个；港股入口传前 4 个。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_seven_analysts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: 新增政策、游资、解禁分析师"
```

---

### Task 12: 简报管道（数据与规则部分）

**Files:**
- Create: `brief/__init__.py`、`watchlist.py`、`fetch.py`、`rules.py`
- Test: `tests/test_brief_watchlist.py`、`tests/test_brief_rules.py`、`tests/test_brief_fetch.py`

**Interfaces:**
- Consumes: Task 4–8 的 typed/字符串函数
- Produces:
  - `@dataclass WatchItem: code: str; notes: str = ""`
  - `load_watchlist(path: Path) -> list[WatchItem]`
  - `@dataclass StockFacts: code: str; name: str = ""; symbol: AStockSymbol | None = None; quote: Snapshot | None = None; bars: list[DailyBar] = field(default_factory=list); announcements: list[str] = field(default_factory=list); reports: list[str] = field(default_factory=list); fund_flow: str = ""; lockup: str = ""; missing: list[str] = field(default_factory=list)`
  - `collect_facts(item: WatchItem, trade_date: str) -> StockFacts`
  - `@dataclass Flag: kind: str; label: str; detail: str`
  - `compute_flags(facts: StockFacts) -> list[Flag]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_brief_watchlist.py
import pytest
from pathlib import Path
from brief.watchlist import load_watchlist

def test_load_and_dedupe(tmp_path):
    p = tmp_path / "w.yaml"
    p.write_text("stocks:\n  - code: 600519\n    notes: 白酒\n  - code: 600519\n  - code: 000001\n", encoding="utf-8")
    items = load_watchlist(p)
    assert [i.code for i in items] == ["600519", "000001"]
    assert items[0].notes == "白酒"

def test_invalid_code_raises(tmp_path):
    p = tmp_path / "w.yaml"
    p.write_text("stocks:\n  - code: 0700.HK\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_watchlist(p)
```

```python
# tests/test_brief_rules.py
from brief.rules import compute_flags
from brief.fetch import StockFacts
from tradingagents.dataflows.vendors.a_share.types import DailyBar, Snapshot

def _snap(**kw):
    base = dict(code="600519", name="贵州茅台", price=10.0, prev_close=9.0, change_pct=0.0,
                volume=1000.0, turnover_rate=1.0, pe_ttm=20.0, pb=3.0,
                source="mootdx", as_of="2026-11-25 15:00")
    base.update(kw)
    return Snapshot(**base)

def _bars(volumes):
    return [DailyBar(date=f"2026-10-{i + 1:02d}", open=9.0, high=9.5, low=8.9, close=9.0,
                     volume=v, source="mootdx", as_of="2026-11-25 15:00")
            for i, v in enumerate(volumes)]

def facts(**kw):
    base = dict(code="600519", name="贵州茅台", quote=None, bars=[], announcements=[],
                reports=[], fund_flow="", lockup="", missing=[])
    base.update(kw)
    return StockFacts(**base)

def test_limit_up_flag():
    flags = compute_flags(facts(quote=_snap(change_pct=10.0)))
    assert any(f.kind == "limit_up" for f in flags)

def test_volume_spike_flag():
    flags = compute_flags(facts(quote=_snap(volume=3000), bars=_bars(volumes=[1000]*20)))
    assert any(f.kind == "volume_spike" for f in flags)

def test_missing_data_is_reported():
    flags = compute_flags(facts(missing=["quote", "fund_flow"]))
    assert any(f.kind == "data_missing" and "quote" in f.detail for f in flags)
```

```python
# tests/test_brief_fetch.py
from brief import fetch
from brief.watchlist import WatchItem

def test_collect_records_failures_without_raising(monkeypatch):
    monkeypatch.setattr(fetch, "get_snapshot", lambda sym: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(fetch, "get_daily_bars", lambda *a: [])
    monkeypatch.setattr(fetch, "get_news", lambda *a: "")
    monkeypatch.setattr(fetch, "get_fund_flow", lambda *a: "")
    monkeypatch.setattr(fetch, "get_lockup_expiry", lambda *a: "")
    facts = fetch.collect_facts(WatchItem(code="600519"), "2026-11-25")
    assert facts.code == "600519"
    assert "quote" in facts.missing
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_brief_watchlist.py tests/test_brief_rules.py tests/test_brief_fetch.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- `watchlist.py`：YAML `stocks:` 列表；`parse_ashare` 校验；重复代码去重保留首条。
- `fetch.py`：按代码并发（上限 3）调用 typed 函数；单只失败记入 `missing`，不中断整批；当日行情不缓存，历史数据按缓存键复用。
- `rules.py`（阈值写进常量，便于改）：
  - `limit_up/limit_down`：主板 ±10%、创业/科创 ±20%、名称含 ST ±5%，按 `change_pct` 与阈值比较
  - `volume_spike`：当日量 / 20 日均量 ≥ 2
  - `ma20_break`：收盘跌破/站上 MA20
  - `drawdown`：60 日高点回撤 ≥ 15%
  - `unlock_soon`：未来 90 天内有解禁
  - `rating_downgrade`：最近研报评级低于上次
  - `data_missing`：任何缺失项一条

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_brief_watchlist.py tests/test_brief_rules.py tests/test_brief_fetch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: 简报自选股、取数与规则化信号"
```

---

### Task 13: 简报的模型摘要、渲染与 CLI

**Files:**
- Create: `brief/summarize.py`、`brief/render.py`
- Modify: `cli/main.py`、`cli/run.py`
- Test: `tests/test_brief_summarize.py`、`tests/test_brief_render.py`、`tests/test_cli_brief.py`

**Interfaces:**
- Consumes: Task 12 的 `WatchItem`、`StockFacts`、`Flag`
- Produces:
  - `@dataclass BriefEntry: code: str; name: str; summary: str; lean: Literal["偏多","中性","偏空"]; flags: list[Flag]; sources: list[str]; missing: list[str]`
  - `summarize(facts: StockFacts, flags: list[Flag], llm) -> BriefEntry`
  - `render_brief(trade_date: str, entries: list[BriefEntry], out_dir: Path) -> Path`
  - CLI：`brief [--date YYYY-MM-DD] [--watchlist PATH]`
  - `render_brief(trade_date, entries, out_dir)` 写 `out_dir/<trade_date>.md`
  - 报告固定包含：每只票的代码/名称、结论、要点、规则标记（若有）、一行 `数据来源：<source | As of ...>`；缺失数据的票写 `数据不可用：<字段列表>`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_brief_summarize.py
from brief.summarize import summarize
from brief.fetch import StockFacts
from brief.rules import Flag

class FakeLLM:
    def __init__(self):
        self.seen = []
    def invoke(self, messages):
        self.seen.append(str(messages))
        class M: content = "1. 主力净流入。\n2. 量能放大。\n倾向：偏多"
        return M()

def test_summary_has_lean_and_keeps_facts():
    llm = FakeLLM()
    facts = StockFacts(code="600519", name="贵州茅台", missing=[], fund_flow="主力净流入 1.2 亿")
    entry = summarize(facts, [Flag("volume_spike", "放量", "量比 2.5")], llm)
    assert entry.lean == "偏多"
    assert "1.2 亿" in llm.seen[-1]          # 事实进入了提示词
    assert "放量" in llm.seen[-1]
```

```python
# tests/test_brief_render.py
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
```

```python
# tests/test_cli_brief.py
from typer.testing import CliRunner
from cli.main import app

def test_brief_command_runs(monkeypatch, tmp_path):
    monkeypatch.setattr("cli.main.run_brief", lambda **kw: tmp_path / "brief.md")
    result = CliRunner().invoke(app, ["brief", "--date", "2026-11-25", "--watchlist", "w.yaml"])
    assert result.exit_code == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_brief_summarize.py tests/test_brief_render.py tests/test_cli_brief.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- `summarize.py`：每只票一次 `llm.invoke`（模型取 `create_tier_client(config, "quick").get_llm()`），提示词要求"只能使用给定事实，不得补充数字"，输出 3–5 条要点 + 倾向；解析失败时倾向记 `中性` 并在报告中标 `摘要解析失败`；prompt 里带上规则标记，事实块按字段截断（新闻/研报各最多 10 条）。
- `render.py`：单文件 Markdown；按倾向分组；每只票小节含结论、要点、标记、来源行；头部写数据截止、模型、生成时间；无数据票单独列出。
- CLI：`brief` 命令串起 watchlist → fetch → rules → summarize → render；退出码 0；任一票失败不影响整体。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_brief_summarize.py tests/test_brief_render.py tests/test_cli_brief.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: 简报摘要、渲染与 CLI 入口"
```

---

### Task 14: 深挖入口、报告抬头与文档收尾

**Files:**
- Modify: `cli/main.py`、`cli/run.py`、`tradingagents/reporting.py`、`tradingagents/report_html.py`
- Create: `README.md`、`NOTICE`、`watchlist.yaml`、`scripts/smoke.sh`
- Test: `tests/test_cli_deep.py`、`tests/test_report_header.py`

**Interfaces:**
- Consumes: 前面全部任务
- Produces:
  - CLI：`deep <code> [date] [--debate N] [--resume]`
  - A 股默认 7 分析师；`.HK` 默认 4 分析师；其他代码 `ValueError` 退出码 2
  - `run_deep(code: str, date: str | None = None, selected_analysts: list[str] | None = None, resume: bool = False) -> int`
  - 报告抬头固定包含 `Model:`、`Provider:`、`Data as of:`；不含 memory 行

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cli_deep.py
from typer.testing import CliRunner
from cli.main import app

def test_deep_routes_market(monkeypatch):
    seen = {}
    monkeypatch.setattr("cli.main.run_deep", lambda code, **kw: seen.setdefault("code", code) or 0)
    result = CliRunner().invoke(app, ["deep", "600519", "2026-11-25"])
    assert result.exit_code == 0 and seen["code"] == "600519"

def test_cn_seven_hk_four_analysts(monkeypatch):
    seen = {}
    monkeypatch.setattr("cli.main.run_deep",
                        lambda code, **kw: seen.setdefault(code, kw.get("selected_analysts")) or 0)
    CliRunner().invoke(app, ["deep", "600519", "2026-11-25"])
    CliRunner().invoke(app, ["deep", "0700.HK", "2026-11-25"])
    assert len(seen["600519"]) == 7
    assert len(seen["0700.HK"]) == 4

def test_deep_rejects_unsupported(monkeypatch):
    result = CliRunner().invoke(app, ["deep", "AAPL"])
    assert result.exit_code == 2
```

```python
# tests/test_report_header.py
from tradingagents.reporting import _header

def test_header_has_provenance():
    settings = {"llm_provider": "deepseek", "deep_think_llm": "deepseek-v4-pro",
                "data_as_of": "2026-11-25"}
    text = _header("600519", {"final_trade_decision": "Rating: 买入"}, settings)
    assert "Model: deepseek-v4-pro" in text
    assert "Provider: deepseek" in text
    assert "Data as of: 2026-11-25" in text
    assert "Memory log" not in text
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_cli_deep.py tests/test_report_header.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

- `deep`：`market_of` 选分析师集；`apply_market_config` 设 vendor；交易日回退；报告落 `reports/deep/<code>/<date>/`；`--resume` 用最近 checkpoint。
- `reporting.py`/`report_html.py`：抬头读 `settings["deep_think_llm"]`、`settings["llm_provider"]`、`settings["data_as_of"]`；删 memory 行。CLI 调 `write_report_tree` 时把 `data_as_of=trade_date` 合并进 `run_settings()`。
- `README.md`：安装（3.12 venv、`pip install -e .`）、模型配置、`brief`/`deep` 用法、watchlist 格式、数据源与已知限制、验收命令。
- `NOTICE`：上游 fork、astock/A-share 移植清单。
- `.env.example`：只保留模型 provider 所需变量（DeepSeek/OpenAI/Anthropic 等）与 `TRADINGAGENTS_*` 覆盖项，删掉 FRED 等已移除服务。
- `watchlist.yaml`：示例 3 只票。
- `scripts/smoke.sh`：`pytest -q` + `python -m cli.main brief --date <today>` 的手动集成提示（不自动跑真实接口）。
- 依赖锁定：生成并提交 `uv.lock`（项目已装 uv 时）或 `requirements.lock.txt`（`.venv/bin/pip freeze`），README 写明按锁文件安装。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_cli_deep.py tests/test_report_header.py -v && pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: 深挖入口、报告来源抬头与使用文档"
```

---

## 验收（全部任务完成后）

```bash
pytest -q
python -m cli.main brief --date 2026-11-25
python -m cli.main deep 600519 2026-11-25
python -m cli.main deep 0700.HK 2026-11-25
```

预期：简报在 10 分钟内生成且每只票有来源/截止时间；深挖 10–15 分钟出中文报告、评级可解析；港股走 yfinance 且只用 4 个分析师；断网时报告显式写"数据不可用"。
