# A 股投研工具（自研，基于 0.7.x）设计文档

> 日期：2026-11-25。状态：草案，待确认。底座：[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) `0.7.x`（`9fa1196`，v0.7.1，2026-10-27）。参考：[TradingAgents-astock](https://github.com/simonlin1212/tradingagents-astock) v0.5.22、[TradingAgents-A-share](https://github.com/hkwsg/TradingAgents-A-share)（main，2026-06-08）。三者均为 Apache-2.0。

## 意图

做一套**自己完全控得住、长期可维护**的 A 股投研工具，替代/补足现有的 astock 与 TradingAgents-CN：

- 每天收盘后对自己维护的 10–30 只自选股出一份中文研究简报。
- 偶尔对一只票做完整深挖：4+3 个分析师、多空辩论、风控、组合经理决策。
- 代码、数据管道、提示词都在自己仓库里；数据源坏了能在小时内换掉，而不是等作者更新。

## 目标 / 非目标 / 反目标

**目标**

1. 简报：一次命令产出当日全部自选股的 Markdown 简报，单只成本低（1 次模型调用），全程可离线复查数据来源与日期。
2. 深挖：单票完整多 Agent 流程，中文输出，10–15 分钟内完成，断点可恢复。
3. 可维护：数据层有窄接口与契约测试；依赖锁死；删掉一切不用的代码。
4. 可解释：每个数字标注数据源与截至日期；规则化信号（涨跌停、放量、解禁、评级下调）由代码计算，不交给模型。

**非目标（v1 不做）**

- 交易执行、下单、撮合、组合盈亏管理。
- 决策结算、回测、命中率统计（代码保留在 0.7.x 上游，将来可搬回）。
- 推送（飞书/微信）、Web UI、多用户、权限、部署服务。
- 美股、加密、外汇、期货、宏观（FRED）等非 A 股/港股能力。
- 港股简报（港股深挖保留，走 yfinance）。

**反目标（出现即说明走偏）**

- 变成通用多市场框架，或追求与上游同步升级。
- 为了"功能全"保留不用的模块。
- 让模型生成数据（所有财务/行情数字必须来自数据层并有来源标记）。

## 约束

- Python ≥ 3.12，复用本机 python-build-standalone 3.12 运行时（系统 3.14 受 PEP 668 限制）。
- 数据只用免费源：mootdx（行情/财务）+ AkShare（公告/研报/新闻/信号/日历），必要时直连东财/腾讯/新浪做回退。
- 模型走既有 OpenAI 兼容网关（DeepSeek 等），不新增付费数据服务。
- 仅个人研究使用，不对外分发抓取数据。
- 个人业余维护：优先少代码、少依赖、少自动化。
- **pandas 版本**：先沿用上游 `pandas>=3.0.6`；M1 开头做一次 AkShare/mootdx 兼容性 spike。若冲突，锁 `pandas 2.3.x` 并记录哪些上游测试因此调整（两个参考 fork 都跑在 2.3）。

## 已选方案

考虑过三种（2026-11-25 讨论）：

| 方案 | 内容 | 结论 |
|---|---|---|
| A. 精简 fork | 以 0.7.x 为底座，删除不用的模块与非 A 股数据源，接入 A 股数据层与简报流程 | **选中** |
| B. 薄壳重写 | 新写 ~3k 行、不用 LangChain/LangGraph | 否决：编排/结构化输出/重试要重新踩坑，且失去 1000 个测试的回归网 |
| C. fork astock 改造 | 改动最少 | 否决：底座更旧，规则写死在提示词里，不符合长期可控 |

选 A 的理由：维护风险落在能读、能测的代码上；辩论编排、结构化输出、断点续跑这些最容易出隐性 bug 的部分已有现成测试。代价是 LangGraph/LangChain 依赖与"上游冻结后框架问题自己扛"。

## 已决定的细节

1. **底座**：0.7.x 分支，独立新仓库（建议 `~/work/ashare-research`），保留 Apache-2.0 与上游 NOTICE。
2. **深挖分析师共 7 个**：上游 4 个（市场/情绪/新闻/基本面）+ 移植 astock 的政策、游资、解禁 3 个。
3. **砍掉**：`tradingagents/backtest.py`、`portfolio.py`、`memory/`（log/settlement/reflection），以及 CLI 中对应命令。
4. **数据源**：行情以 mootdx 为主（回退东财→腾讯→新浪）；**三表/财务指标以新浪（带 `publish_date`）与东财/AkShare（`NOTICE_DATE`）为主**，mootdx 只提供行情与当前财务快照；公告、研报、新闻、龙虎榜、资金流、北向、概念、解禁、日历走 AkShare/东财。
5. **两条路径**：简报不走 Agent 图；深挖走完整图。两者只共享数据层、符号/日期/单位规范与报告规范。
6. **简报形态**：每只票一次轻量模型调用，输入是代码生成的紧凑事实块；结论用三档（偏多/中性/偏空）+ 风险标记，不沿用五档评级。
7. **深挖评级**：沿用 0.7.x 五档（Buy/Overweight/Hold/Underweight/Sell），解析时补中文映射（买入/增持/持有/减持/卖出）。无评级记为 REVIEW，不默认成 Hold。
8. **不做 lookahead**：历史日期深挖只使用该日期前已披露的数据；财务按公告日过滤，行情按交易日截断。
9. **报告**：Markdown 落 `reports/`，按交易日分目录；深挖额外生成自包含 HTML（沿用 0.7.x 报告器）。报告头写明模型、数据源、截至日期。
10. **断点续跑**：保留 SqliteSaver 检查点；不做跨轮记忆。
11. **不加推送**：v1 只写文件；推送以后单独讨论。
12. **港股边界**：入口按代码后缀分流——6 位数字走 A 股（7 分析师），`.HK` 走 yfinance（只用上游 4 个分析师）。`data_vendors` 仍按能力全局配置，选路在入口与 `a_share` vendor 内部完成，不做的市场直接报"不支持"，不静默混用。

## 架构

### 模块图（目标形态）

```
ashare-research/
├── tradingagents/                 # fork 自 0.7.x，删减后
│   ├── agents/                    # 7 分析师 + 多空 + 经理 + 交易员 + 3 风控 + PM
│   │   ├── analysts/              # market, sentiment, news, fundamentals,
│   │   │                          # policy, hot_money, lockup
│   │   ├── researchers/ managers/ risk_mgmt/ trader/
│   │   └── rating.py              # 五档 + 中文映射 + REVIEW 兜底
│   ├── graph/                     # setup / trading_graph / propagation /
│   │   │                          # conditional_logic / checkpointer / analyst_execution
│   ├── dataflows/
│   │   ├── router.py              # 方法→vendor 路由（改为 a_share 优先）
│   │   ├── symbols.py             # A 股代码规范化（600519 / SH600519 / 600519.SH）
│   │   ├── date_window.py         # 交易日窗口与 as-of 截断
│   │   └── vendors/
│   │       ├── a_share/           # 新增：typed 核心 + 字符串适配
│   │       │   ├── quotes.py      # 日线、快照、复权
│   │       │   ├── fundamentals.py# 三表、财务指标、估值
│   │       │   ├── news.py        # 公告、研报、快讯
│   │       │   ├── signals.py     # 龙虎榜、资金流、北向、概念、解禁、行业对比
│   │       │   ├── calendar.py    # 交易日历
│   │       │   └── format.py      # typed → 0.7.x 字符串契约
│   │       └── yahoo/             # 仅保留港股所需
│   ├── reporting/                 # 沿用：Markdown / HTML
│   └── cli/                       # deep / brief / resume / models
├── brief/                         # 新增：简报管道（不依赖 Agent 图）
│   ├── fetch.py                   # 按自选股并发取事实
│   ├── signals.py                 # 规则化标记（涨跌停、放量、破位、解禁、评级变动）
│   ├── prompt.py                  # 单只事实块 → 一次模型调用
│   ├── render.py                  # 单文件中文简报
│   └── watchlist.py               # watchlist.yaml 读取
├── tests/
└── watchlist.yaml                 # 用户维护
```

### 数据层契约

- **typed 核心**：每个能力返回 dataclass（含 `as_of`、`source`、单位、原始值），供简报直接使用。
- **字符串适配**：`format.py` 把 typed 结果格式化为 0.7.x 工具要求的字符串（带 `Source: ... | As of: ...` 页脚），供 Agent 读取。
- **路由**：`data_vendors` 按能力配置，A 股能力只有 `a_share`；港股 `get_stock_data`/`get_news` 等回退 `yfinance`。
- **回退链**：行情 mootdx → 东财 → 腾讯 → 新浪；三表/财务 新浪（带公告日）→ 东财/AkShare；mootdx 财务仅用于当前快照；新闻/研报/公告/信号 AkShare → 东财直连。
- **缓存**：按（能力、代码、日期窗口）落 parquet/JSON，缓存键含数据源与拉取时间；历史日期允许复用，当日行情不缓存。
- **限流**：东财 0.5s/请求 + 3 次指数退避（沿用 A-share fork 的做法）；mootdx 串行并复用连接。

### 数据时点与口径（实现约定）

| 数据 | 时点字段 | 历史深挖口径 |
|---|---|---|
| 日线/快照 | 交易日收盘 | 只用 `date ≤ D` 的已收盘会话 |
| 三表/财务指标 | 公告日（新浪 `publish_date`、东财 `NOTICE_DATE`） | 只取公告日 ≤ D 的版本；同一报告期有多版本时按公告日取当时最新 |
| 公告/研报/新闻 | 发布时间 | ≤ D 15:00（收盘）才进入当日结论 |
| 龙虎榜/资金流/北向 | 当日盘后披露 | ≤ D 的披露日；D 当天盘后数据不进入 D 的历史深挖 |
| 解禁 | 解禁公告日 | 只列公告日 ≤ D 且解禁日在 D 之后的事件 |
| PE/PB/一致预期 | 无完整历史时点值 | 历史模式下显式标注 `current snapshot, not historical` 或不提供，**不静默用当前值代替历史值** |

- 当天收盘后运行的简报属于"当前视图"，截止时间记为运行时刻，并在报告头写明。
- 每类数据在 typed 结果里必须带 `as_of` 与 `source`；契约测试断言缺失时点字段的行为。

### a_share vendor 函数清单（7 个分析师 + 简报共用）

- 行情与财务：`get_stock_data`、`get_indicators`（本地 stockstats）、`get_fundamentals`、`get_balance_sheet`、`get_cashflow`、`get_income_statement`、`get_verified_market_snapshot`（A 股实现，替代上游 Yahoo 硬编码）。
- 信息：`get_news`、`get_global_news`、`get_insider_transactions`（A 股口径：股东/高管增减持、大宗交易，替代美股 insider）。
- 信号：`get_profit_forecast`、`get_hot_stocks`、`get_concept_blocks`、`get_dragon_tiger_board`、`get_fund_flow`、`get_northbound_flow`、`get_industry_comparison`、`get_lockup_expiry`。
- 日历：`get_trade_calendar`、`previous_trade_date`、`is_trade_date`。
- 情绪口径：**不移植雪球 CSV 缓存**；A 股情绪分析师按 astock 的做法，用新闻 + 资金流 + 热门榜 + 量价四类硬数据推断情绪（astock 曾因"只看新闻推情绪"出过问题，见其注释 #61）。

### 简报流程（每日）

1. 读 `watchlist.yaml`（代码、可选别名/备注、可选关注阈值）。
2. 并发（上限 3）为每只票取事实：最近 60 个交易日日线、当日快照、资金流、公告、研报与评级变动、快讯、龙虎榜（若上榜）、解禁（未来 90 天）、北向持股（若标的在互联互通范围）、估值（PE/PB）。
3. 代码计算规则标记：涨跌停、放量（量比/量能分位）、跌破/站上 MA20、阶段回撤、临近解禁、评级下调、龙虎榜净买入/卖出。
4. 每只票一次模型调用：紧凑事实 + 规则标记 + 用户备注 → 3–5 条要点 + 三档倾向 + 风险标记。
5. 汇总为单份 Markdown：市场概览（可选一次额外调用）→ 按倾向分组 → 每只票的小节（结论、要点、数据来源与日期）。
6. 原始事实落 `reports/brief/<date>/facts/`，便于事后核对；简报正文不出现无来源数字。

### 深挖流程（按需）

`deep <code> [trade_date]`：

1. 解析代码与交易日（非交易日回退到最近交易日）。
2. 7 个分析师并行取数并出报告（市场/情绪/新闻/基本面/政策/游资/解禁）。
3. 多头/空头各 1 轮辩论（可配置 1–3 轮）→ 研究经理给投资计划 → 交易员 → 三风控 → 组合经理最终评级。
4. 输出 Markdown + HTML；评级五档；报告头列模型、供应商、数据截至时间。
5. 检查点开启；中断后 `deep --resume` 从最近节点继续。

## 需要删除的上游内容

| 删除 | 原因 |
|---|---|
| `tradingagents/backtest.py`、`portfolio.py`、`memory/` | v1 不做结算/回测/持仓/记忆 |
| `vendors/sec_edgar`、`fred`、`polymarket`、`alpha_vantage`、`reddit`、`stocktwits` | 非 A 股/港股能力，且各自带维护面 |
| 美股/加密/外汇/期货分支与 CLI 入口 | 同上 |
| 多市场宏观、预测市场、内部人（美股口径）提示词 | 无关或 A 股口径不同 |
| 相关测试与 fixtures | 随模块一并删除；保留 graph/agents/reporting 测试 |

删除后第一件事：跑测试，把仍引用已删模块的测试一并清理，**保证主干测试全绿再开发**。

## 新增与改造估算（低置信度，供排期）

| 工作 | 估计 |
|---|---|
| fork + 删除 + 测试修复 | 2–3 天（上游 90 个测试文件里约 38 个引用待删模块） |
| A 股数据层（typed + 字符串适配 + 回退 + 缓存） | 800–1200 行，4–6 天 |
| 契约测试（录制 fixtures + 集成 smoke） | 300–400 行，2 天 |
| 简报管道（含 watchlist、规则、渲染） | 300–500 行，2–3 天 |
| 深挖适配（符号/日历/提示词中文/评级） | 1–2 天 |
| 移植 3 个分析师 + 信号数据 | 600–800 行，3–4 天 |
| 总净代码 | 约 5–6k 行（删后） |
| 单人业余节奏 | 3–4 周 |

## 测试策略

- **单元**：数据适配器用录制 fixtures（脱敏），断言单位、日期、缺失值处理；符号规范化；规则标记；评级解析（中英文）；简报渲染快照。
- **契约**：每类数据一个固定样本，验证返回结构与来源字段；fixtures 失效即说明上游格式变了。
- **集成**：`pytest -m integration` 打真实接口，手动/定时跑，不进默认测试集；允许失败告警。
- **回归**：保留 0.7.x 中仍适用的 graph/agents/reporting 测试。
- **验收**：`brief --date 今天` 对 20+ 只票 10 分钟内出报告，所有数字有来源与日期；`deep 600519` 10–15 分钟出报告且评级可解析；断网/接口失败时输出明确的"数据不可用"，不编造。

## 里程碑与验证

1. **M0 底座**：新仓库、0.7.x 代码、删除清单执行、测试全绿。验证：`pytest` 通过，`deep` 对一只 A 股能跑到"无数据"而不是崩溃。
2. **M1 数据层**：a_share vendor + 符号/日历 + 契约测试。验证：600519/000001/300750 三类代码均能取到行情、三表、公告、研报。
3. **M2 简报**：`brief` 端到端。验证：20 只票 10 分钟内产出，人工抽查 3 只的数字与来源。
4. **M3 深挖（4 分析师）**：中文报告、评级解析、断点恢复。验证：茅台/宁德各跑一次，报告无空章节，中断可续。
5. **M4 7 分析师**：政策/游资/解禁接入并进入辩论。验证：数据缺失时降级有说明；深挖时长 ≤15 分钟。
6. **M5 收尾**：报告样式、README、运维脚本（cron 示例）、性能与 token 统计。

## 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| AkShare 接口变更/反爬 | 简报大面积失败 | 契约测试早发现；每类数据保留 2 条回退；接口封装在一处 |
| mootdx 服务器/协议 | 行情与财务不可用 | 连接池 + 可达性探测（移植 astock）；回退东财/腾讯/新浪 |
| 免费数据 ToS/合规 | 个人可用、不可分发 | 仅本地使用，不提交抓取数据，不对外提供接口 |
| 未来数据泄漏（lookahead） | 回看结论虚高 | 财务按公告日、行情按交易日截断；测试含"历史日期不看未来"用例 |
| 上游冻结 | 框架 bug 无人修 | 锁依赖；LangGraph 升级按年评估；保留测试做升级安全网 |
| 模型成本 | 简报/深挖烧钱 | 简报单次调用 + 紧凑事实；深挖默认 1 轮辩论；CLI 显示 token 用量 |
| 提示词质量 | 结论空泛或编数据 | 所有数字来自数据层；提示词明确"只能用给定事实"；验收含抽查 |
| 个人时间不足 | 半途而废 | 先交付 M2 简报（每天能用），深挖与 7 分析师增量交付 |

## 留给实现者的决定

以下不改变产品形态，实现时按常识定并记录：

- `watchlist.yaml` 的具体字段（建议：`code`、`name`、`notes`、`alert: {price_above/below, volume_ratio}`）。
- 简报"市场概览"是否单独调用一次模型（建议：默认做，可关）。
- 财新新闻是否默认关闭（建议：默认关闭，配置开启）。
- 缓存格式（parquet vs JSON，建议：小表 JSON，行情 parquet）。
- 报告文件名与目录层级（建议：`reports/brief/2026-11-25.md`、`reports/deep/600519/2026-11-25/`）。
- 是否保留 HTML 报告（建议保留，依赖已在上游）。

## 署名与许可

- 保留上游 Apache-2.0 LICENSE 与版权头；新增 `NOTICE` 说明 fork 来源与移植自 astock/A-share 的部分。
- 移植 astock 的数据函数与分析师提示词时，保留原始版权声明，并在文件头注明来源与改动。
