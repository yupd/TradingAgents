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

## 用 Claude Code 当前的网关

Claude Code 的网关是 Anthropic 兼容入口，同时也提供 `/chat/completions`。TradingAgents 用 `openai_compatible` 接它，且**不需要把密钥复制到 `.env`**：当没有设置 `TRADINGAGENTS_LLM_BACKEND_URL` / `OPENAI_COMPATIBLE_API_KEY` 时，会自动继承当前进程的 `ANTHROPIC_BASE_URL` 和 `ANTHROPIC_AUTH_TOKEN`。

`.env` 只需：

```ini
TRADINGAGENTS_LLM_PROVIDER=openai_compatible
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-flash
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-flash
```

在 Claude Code 的终端里直接运行即可。若在普通 shell 里运行，先把网关配置导入：

```bash
export ANTHROPIC_BASE_URL=...   # 取 ~/.claude/settings.json 的 env
export ANTHROPIC_AUTH_TOKEN=... # 同上；不要写进仓库
```

也可以显式指定 `TRADINGAGENTS_LLM_BACKEND_URL` 与 `OPENAI_COMPATIBLE_API_KEY`，显式值优先。

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

# 每日大盘复盘（--date 省略时取最近交易日）
.venv/bin/python -m cli.main market --date 2026-11-26

# 追加基本面四节（宏观/估值/资金/盈利）；只支持最新交易日
.venv/bin/python -m cli.main market --fundamentals
```

报告路径：

- 简报：`reports/brief/YYYY-MM-DD.md`
- 深挖：`reports/deep/<CODE>/<YYYY-MM-DD>/complete_report.md`
- 大盘复盘：`reports/market/YYYY-MM-DD.md`

大盘复盘先确定性收集指数趋势、成交量、情绪与行业强弱，再调用一次模型写叙述，报告固定七节。数据口径：不含北向资金；行业强弱只有当日数据，历史报告标注不可用；成交额一节仅当日沪/深/合计，20 日量能倍数按指数成交量计算，见「指数趋势」表格下的脚注；东方财富限流时对应区块降级为「数据缺口」，不会导致整份报告失败。

### 基本面模式（--fundamentals）

在「新闻与政策」之后、「数据缺口」之前追加四节，数字均由代码取数，模型只解释：

- **宏观基本面**：CPI、PPI、PMI、社零、固定资产投资、进出口六项。均为月度数据，每行标注统计期（如「2026年10月份」），不推断发布日期；固投为自年初累计同比；PMI 行数值为制造业 PMI（非制造业见注），进出口行数值为出口同比（进口同比见注）。
- **估值水平**：并列展示第三方 PE(TTM) 及其近 120 个月分位，与中证官方的市盈率 1/2、股息率 1/2；分位窗口不足 120 个月时按实际窗口标注。两套口径均对应沪深300，不合并、不互校，官方值以中证指数为准。
- **资金面**：沪/深两市融资融券余额（亿元），按共同交易日对齐后给出合计、5 日变化和实际 as-of；数据源滞后时写实际日期，不冒充报告交易日。
- **盈利概览**：最近季末报告期，按个股财报加权聚合的净利润同比、营收同比与覆盖率，并注明公告截止日；覆盖率低于 80% 标注「覆盖不足」。

请求预算：默认模式 12 次请求、60 秒；`--fundamentals` 约增加 22 次（宏观 6 + 估值 2 + 两融 2 + 盈利分页约 12）。设计上限 40 次请求、120 秒；单测断言默认 12 次、基本面新增 22 次（合计 34 次），耗时未在单测中断言。

基本面只支持最新交易日：不带 `--date` 或 `--date` 等于最新交易日时正常取数；`--date` 早于最新交易日时不发起任何基本面请求，四节统一写「历史模式不可用」。

## Docker 运行

Web UI 与 CLI 在同一镜像内，默认启动 Web UI（Streamlit，端口 8501）。

前置：Docker 与 Compose 插件；`.env` 与本地运行共用。

```bash
cp .env.example .env        # 填模型 key（已有则跳过）
mkdir -p data reports       # 分析结果/缓存/断点与 CLI 报告的宿主目录
docker compose up -d --build
```

打开 <http://localhost:8501>。状态与日志：

```bash
docker compose ps
docker compose logs -f web
docker compose down         # 停止；./data 保留
```

`./data` 对应容器内 `~/.tradingagents`：`logs/` 是分析报告，`cache/` 是数据缓存，另有断点与未完成任务状态。CLI 的 `deep`/`brief`/`market` 报告写到 `./reports`。迁入本机历史：

```bash
mkdir -p data
cp -r ~/.tradingagents/logs/. data/logs/
```

同一镜像跑 CLI（交互式命令加 `-it`）：

```bash
docker compose run --rm web tradingagents --help
docker compose run --rm web tradingagents deep 600519 2026-11-25
```

改端口两种方式：在 `.env` 设 `STREAMLIT_SERVER_PORT=8599`，Compose 会同步容器端口、宿主机映射与健康检查；或只改 `ports` 左侧（如 `"8601:8501"`，容器内仍是 8501）。

容器内用户是 uid 1000。若宿主机当前用户不是 1000，`./data` 可能不可写：

```bash
sudo chown -R 1000:1000 data
```

国内网络构建慢或失败时，覆盖构建源（apt 参数填镜像主机名）：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
APT_MIRROR=mirrors.tuna.tsinghua.edu.cn \
docker compose build
```

说明：

- 镜像不含 `.env`；配置只通过 `env_file` 在运行时注入。
- 服务监听 `0.0.0.0:8501` 且无鉴权，仅限本机/内网使用；公网部署需自行加反向代理与认证。
- 健康检查走 `/_stcore/health`，`docker compose ps` 显示 `healthy` 即可用。

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
