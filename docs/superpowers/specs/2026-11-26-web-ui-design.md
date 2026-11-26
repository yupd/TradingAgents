# TradingAgents Web UI 移植设计

> 日期：2026-11-26。对象：`~/work/TradingAgents`（fork `yupd/TradingAgents`，分支 `feat/ashare-research`）。
> 来源：`~/work/github/stock/TradingAgents-astock/web/`（下称 astock）。方案 A：原样移植 UI + 重写后端适配层。

## 意图

`brief` 和 `deep` 目前只有 CLI：一次 7 分析师深挖要跑很久，终端里看不到分阶段进度，中断后只能靠 `--resume` 重来，历史报告要自己去翻目录。把 astock 的 Streamlit 模块移过来，得到：

- 浏览器里发起 A 股全 7 分析师分析；
- 实时进度、暂停/继续/停止、断点续跑；
- 分节展示报告，导出 Markdown/PDF；
- 历史记录与未完成任务列表；
- 运行结束同时落盘到 `results_dir`，CLI 和网页看到同一份结果。

## 目标

1. 网页能启动一次完整 A 股分析，进度面板按阶段点亮。
2. 支持暂停（当前步骤后停）、继续、停止（清空断点）；出错后保留断点，可从侧栏续跑。
3. 完成后展示 7 份分析师报告、多空辩论、交易员、风控、最终决策，并提供 MD/PDF 下载。
4. 历史记录扫描 `results_dir` 下的 `full_states_log_*.json`，点开即可回看。
5. 分析结束写状态日志与报告目录（与 CLI 同格式），网页与 CLI 互相可见。
6. 默认模型配置来自 `.env`（本机为 `openai_compatible` + `deepseek-flash` + 网关），侧栏可临时改。

## 非目标

- 不移植质量门控（`data_quality_summary`）、`missing_data` 缺失台账与重试、Agent SDK 订阅覆盖、中文股票名 → 代码、数据起始日期（`market_lookback_days`）。
- 不做多用户、登录、远程部署；只按本机单用户使用设计。
- 除“状态日志补 3 个字段”这一处增量修改外，不改动分析逻辑、提示词、数据层、CLI 行为。
- 不支持港股/美股/加密货币；输入只接受 A 股代码。

## 反目标

- 不复制 astock 的 `prepare_graph_run/finalize_graph_run/close_graph_run` 调用方式——本 fork 没有这些方法。
- 不为 web 单独造一套图执行逻辑；复用 `TradingAgentsGraph` 现有 API。
- 不把 `streamlit`/`fpdf2` 放进核心依赖。

## 约束

| 约束 | 影响 |
|---|---|
| 本 fork 图 API：`begin_checkpoint → create_run_state → stream_run → record_decision → clear_checkpoint_on_success → end_checkpoint` | `runner.py` 必须重写 |
| `stream_run` 顶层 chunk 是**增量**，不是完整状态 | 必须逐块 `merged.update(chunk)`，最后用合并态 |
| 分析师在子图中运行，子图 task 结果以 report dict 返回 | 进度检测同时读子图 report 与合并态 |
| checkpoint 线程 ID 绑定了分析师集合与 config 摘要 | 改模型后续跑会开新断点；这是既有行为，不修 |
| 本 fork 没有 `judge_decision` 字段 | 辩论/风控页改用 `investment_plan` / `final_trade_decision` |
| 本 fork 没有中文名→代码 | 输入只收代码；展示名从报告文本尽力抽取 |
| `.env` 由 `load_dotenv(override=True)` 读入 | 启动后改 `.env` 需重启 web |
| 打包 `packages.find` 目前只含 `tradingagents*`, `cli*` | 需加 `web*` |

## 备选方案

- **A（已选）原样移植 + 适配层**：保留 UI、进度、暂停/续跑、历史、PDF；重写 runner、裁剪后端缺失功能。完整度最高，风险集中在后台线程与断点。
- **B 只读报告浏览器**：只读 CLI 产出的 JSON，不能发起分析。最稳但失去核心价值。
- **C 极简运行页**：输入→跑→看，砍掉历史/暂停/PDF。代码最少但半成品。

选 A。

## 文件布局

```
web/
  __init__.py
  app.py                  # 页面、CSS、状态机、_build_config
  launch.py               # `tradingagents-web` 入口
  runner.py               # 后台线程与图执行适配（重写）
  progress.py             # ProgressTracker + 11 阶段
  history.py              # 历史与未完成任务
  stock_display.py        # 代码归一化与展示名
  pdf_export.py           # MD/PDF 导出（裁剪缺失数据提示）
  components/
    __init__.py
    sidebar.py            # 输入、模型配置、暂停/停止、历史
    progress_panel.py     # 进度面板（无质量门控）
    report_viewer.py      # 报告页（无缺失面板）
tests/
  test_web_history.py
  test_web_model_selection.py
  test_web_runner.py      # 新增：阶段检测与停止清理
  test_stock_display.py
  test_pdf_export.py
```

## 核心设计

### 0. 核心小改动：状态日志补 3 个字段

`tradingagents/graph/trading_graph.py::_log_state()` 目前只写 4 份分析师报告，漏了 `policy_report`、`hot_money_report`、`lockup_report`。网页历史页、历史 MD/PDF 都读这份 JSON，不补则永远少三段。

- 在 `entry` 中增加三个字段，取值用 `final_state.get("policy_report", "")` 形式（旧测试构造的状态没有这些键，不能 KeyError）。
- 同步更新 `tests/test_cli_display.py` 等断言，新增一条“7 份报告都落盘”的测试。
- 只增字段，不改任何已有字段或 CLI 其它行为。

### 1. runner 适配

```python
graph = TradingAgentsGraph(ANALYSTS, config=config, debug=False, callbacks=[stats])
if fresh:                                                 # 侧栏“开始分析”总是 fresh
    graph.clear_checkpoint_on_success(ticker, trade_date) # 必须在 begin_checkpoint 之前
tid = graph.begin_checkpoint(ticker, trade_date)          # None 表示未启用
init = graph.create_run_state(ticker, trade_date)
args = graph.propagator.get_graph_args(callbacks=[stats])
if tid is not None:
    args["config"]["configurable"]["thread_id"] = tid

merged: dict = {}
stream = graph.stream_run(graph.checkpoint_input(init), **args)
try:
    for messages, chunk in stream:
        tracker.wait_if_paused()
        if tracker.stop_requested: break
        if chunk is not None:
            merged.update(chunk)
            _detect_completed_stages(merged, chunk, tracker)
            _infer_active_stage(tracker)
        record_incomplete_task(...)
        tracker.update_stats(...)
finally:
    stream.close()          # 让 stream_run 的 finally 关掉 LangGraph 流
    graph.end_checkpoint()
```

- 正常结束：`normalize_report_state_mentions(merged, ticker)` → `graph.record_decision(...)` → `graph.clear_checkpoint_on_success(...)` → `graph.save_reports(merged, ticker)`（HTML 开启），把保存路径写进 tracker，报告页显示。
- 停止：`stream.close()` → 清除未完成任务 → `clear_checkpoint_on_success` → `tracker.mark_stopped()`。
- 异常：保留断点（不 clear），`record_incomplete_task(status="error")` → `tracker.mark_error(...)`。
- 续跑：`begin_checkpoint` 检测到同签名的断点后，`checkpoint_input` 返回 `None`，LangGraph 自动续跑。
- **断点清除只在 runner 里做**：`app.py` 的 `fresh` 分支与侧栏空闲“停止”都不得直接调用 `clear_checkpoint(...)`（本 fork 需要签名，直接调会静默 no-op）。侧栏空闲停止只清未完成任务并重置 tracker；残留的断点数据库由下一次 fresh 运行在 runner 内清掉。

### 2. 阶段（12 → 11）

`market, social, news, fundamentals, policy, hot_money, lockup, debate, trader, risk, pm`。

- 分析师：7 个 `*_report` 任一出现即完成；子图 report dict 与合并态都查。
- `debate`：`investment_plan` 出现。
- `trader`：`trader_investment_plan` 出现。
- `risk` 与 `pm`：`final_trade_decision` 出现时一起完成（组合经理在风控辩论之后产出）。
- `quality_gate` 整段删除。

### 3. 报告页

- 分析师 7 段、`investment_plan` 作为“最终投资建议”。
- 多空辩论：多方/空方取自 `investment_debate_state`，研究经理标签显示 `investment_plan`。
- 交易员：`trader_investment_plan`。
- 风控：激进/保守/中性取自 `risk_debate_state`，组合经理标签显示 `final_trade_decision`。
- 删除缺失数据面板、`data_quality_summary` 展开块；删除“重新分析”按钮里依赖缺失数据的分支。
- 顶部显示信号、代码/名称、日期、耗时；底部显示本次保存路径。
- MD/PDF 下载保留。

### 4. PDF / Markdown

- `pdf_export.py` 基本原样；只改三处取数：辩论 `judge_decision → investment_plan`、交易员 `trader_investment_decision → trader_investment_plan`、风控判定改用 `final_trade_decision`，并删除 `_missing_data_warning`。
- fpdf 导入失败只禁用 PDF，不影响页面；中文字体发现顺序保留。

### 5. 侧栏与配置

- 输入：A 股代码，接受 `600519`、`SH600519`、`600519.SH`、`600519.SS` 等 `parse_ashare` 支持的写法；输入中文名直接报错。
- 日期：`st.date_input`，默认今天。
- 模型配置（折叠）：供应商列表以 `MODEL_OPTIONS` 的键为准（排除 `chatgpt`、`bedrock`），`openai_compatible` 排第一，其余保留目录顺序；显示名用一张 key→中文名映射，缺映射时直接显示 key。`MODEL_OPTIONS` 里每个供应商都有 quick/deep 选项，`Custom model ID` 哨兵沿用 astock 的处理与校验。若 `DEFAULT_CONFIG["llm_provider"]` 不在列表里（例如将来目录删了某键），把它追加到末尾，避免默认选中丢索引。
- 默认值：`DEFAULT_CONFIG` 的 `llm_provider/deep_think_llm/quick_think_llm/backend_url`（即 `.env`）。
- 不出现 Agent SDK / 订阅覆盖。
- `_build_config()`：复制 `DEFAULT_CONFIG`，覆盖界面值；`checkpoint_enabled=True`、`output_language="Chinese"`；最后 `apply_default_market_config(ticker, config)`。
- 模型校验只挂在 `start_analysis` 的唯一消费点（`app.py`），不散落到各按钮。

### 6. 历史与未完成

- `_results_dir()` 返回 `DEFAULT_CONFIG["results_dir"]`，不写死 `~/.tradingagents/logs`。
- 未完成任务索引文件保持 `~/.tradingagents/incomplete_tasks.json`；列表不再显示 step（本 fork 的 `checkpoint_step` 需要签名，网页拿不到）。
- `extract_signal`：优先 `final_rating`，其次 `extract_rating(final_trade_decision)`，最后 `"N/A"`。

### 7. 股票展示

- `_resolve_display_code`：`parse_ashare(raw).code`，失败返回原值。
- 展示名：只从 state/报告文本抽取（保留 astock 的 `_extract_stock_name_from_state`），不做网络查询。
- `normalize_stock_mentions` / `normalize_report_state_mentions` 原样保留。

### 8. app 状态机

沿用 astock：空闲欢迎页 / 运行中（每 2 秒 `st.rerun`）/ 完成 / 出错 / 查看历史。CSS 与配色保留。`load_dotenv(_PROJECT_ROOT / ".env", override=True)` 必须在导入 `DEFAULT_CONFIG` 之前。

### 9. 打包与入口

- `pyproject.toml`：新增可选依赖 `web = ["streamlit>=1.45.0", "fpdf2>=2.8.6"]`；`packages.find` 加 `web*`；新增脚本 `tradingagents-web = "web.launch:main"`。
- 安装与启动：

```bash
cd ~/work/TradingAgents
.venv/bin/pip install -e ".[web]"
.venv/bin/python -m web.launch
# 或 .venv/bin/tradingagents-web
```

### 10. 测试

- 移植并适配：`test_web_history`（往返、完成即隐藏、信号抽取）、`test_web_model_selection`（哨兵、校验、消费点）、`test_stock_display`（代码格式、state 回退、归一化）、`test_pdf_export`（字体缺失可跳过）。
- 新增 `test_web_runner`：假图对象喂 chunk，验证 7 分析师/辩论/交易员/风控+PM 阶段推进；停止时清断点与任务；异常时保留断点；`fresh` 在 `begin_checkpoint` 之前清断点。
- 更新 `test_cli_display`：状态日志包含 7 份分析师报告；旧状态缺键时不报错。
- 测试不依赖真实 Streamlit：沿用 astock 的 fake streamlit 注入方式。

## 给实现者的决定

- 进度条比例、CSS 细节、文案沿用 astock。
- 每次成功运行都调用 `save_reports`（CLI 行为一致），不做开关。
- 测试里假图的粒度自行决定，但必须覆盖“增量 chunk 合并”和“停止清理”两条。

## 风险

- Streamlit 的 daemon thread + `st.rerun` 轮询是本模块最脆的地方；astock 已运行验证，但本 fork 的 `stream_run` 关闭语义需首跑确认（停止操作是否能在 1–2 秒内收尾）。
- 断点续跑对 config 摘要敏感：网页改了模型后续跑会从头开始，界面需要提示。
- 免费数据源限流仍会让某阶段报告变成 `DATA_UNAVAILABLE`，网页不额外补救，只原样展示。
