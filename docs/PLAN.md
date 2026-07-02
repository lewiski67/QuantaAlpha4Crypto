# QuantaAlpha 全生命周期计划（螺旋骨架 + 门控发布）

_开始日期: 2026-06-30_

## 方法论（按风险和可逆性分段）

- **研究前段（迭代 0–4）→ 风险驱动螺旋。** 不逐层做完，而是先一根最薄的纵向
  骨架穿到底，每个迭代消除当前最大的不确定性，且**始终保持端到端可跑**。研究
  的核心是**快速证伪**——用最便宜的路径走到"此路不通"。
- **评估核心 → 测试先行（TDD）。** t+1 对齐、purge/embargo、市场残差、NW t-stat
  这些数值原语一旦写错会静默污染所有结论。先用已知答案的合成数据写测试，再写实现。
- **部署后段（Phase D–F）→ 门控分批发布。** 真金不可逆。每道门标准**提前定死**，
  不达标不放行。这一段要保守，不要速度。

> 「天数」是工程工作量估计。**★RC 研究检查点是经验性硬门，无法排期**——跑不出
> alpha 就停在那里迭代，可能数周到数月。任何把上线标成固定日期的计划都是自欺。

每次迭代结束检查清单：
1. `PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -o cache_dir=/tmp/pytest_cache_quantaalpha tests -q` 全绿
2. **端到端能跑出一个数**（不是某层单元通过就算）
3. `git commit` + 更新 `docs/HANDOFF.md` + `git push`

---

## 研究前段：螺旋迭代

每个迭代头部写明：**消除哪个不确定性 / 退出问题 / 端到端产物**。

### 迭代 0 — 行走骨架（2–3 天）

- **消除：** 数据流通不通？这套东西能不能对一个因子给出一个带显著性的统计判决？
- **退出问题：** "一个因子，从 panel 到一个全样本 IC + NW 显著性数字，端到端跑通了吗？"
- **刻意不做：** Base Factor Model、purge/embargo、市场中性、Trial Registry、
  正交性、回测、循环、进化、数据扩展。全部砍掉。

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 0.1 | t+1 执行对齐 | `evaluation/metrics.py`、`evaluation/factor.py` | 加执行间隔：t 出信号 → **t+1 进场** → 标签 `close[t+1+horizon]/close[t+1]-1`。改 `_forward_returns` 加 `execution_lag_bars=1` 参数，`evaluate_directional_factor` 透传；TDD 写测试锁住对齐语义 |
| 0.2 | NW 自相关修正 t-stat（TDD） | `evaluation/metrics.py` | **先写测试**：合成正自相关序列 NW t-stat < naive；再写 `_nw_tstat` |
| 0.3 | 全样本 IC 判决脚本 | `evaluation/metrics.py`、`evaluation/factor.py`、`mining/loop.py`（最小） | `_bars_per_horizon`（Timedelta→lag 根数）+ `factor.py` 接线产 x_t 调 `_nw_tstat` + 脚本：一个因子 → **全样本** IC + NW t-stat → 打印一个数。**不切分** |

**验收：** 跑一个手写因子，端到端打印出**全样本 IC 与 NW t-stat**。若信号与噪声无异，
你已用 3 天而非 12 天逼近了"有没有 alpha 迹象"。

> **为什么 0.3 不做 train/test 切分（2026-07-01 决策）：** 单个、写定、**零自由参数**
> 的因子评估**没有拟合、没有选因子**，holdout 在统计上多余——业界评估原语（predictive
> regression / Fama-MacBeth）就是**全样本 + HAC(Newey-West)标准误**，不做留出。切分/留出
> 的价值是**非平稳/持续性**检验，那是 **walk-forward（迭代 1）** 的活；多重检验去膨胀是
> **迭代 2**。故三件事分层：全样本 IC+NW = 评估原语（0.3）→ walk-forward（1.x）→ deflation
> （2.x）。**会犯错的做法是停在单因子全样本就当研究判决拿去交易。**

### 迭代 1 — 让 IC 判决可信（~3 天）

- **消除：** 这个 IC 是真信号，还是 look-ahead / 自相关 / 市场 beta 的假象？
- **退出问题：** "样本外 IC 在去除前视、自相关膨胀、市场暴露后还站得住吗？"

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1.1 | walk-forward + purge/embargo（TDD） | `evaluation/walk_forward.py` | **先测**：purge 后训练/测试无重叠；`_make_windows(purge_bars=horizon, embargo_bars=0)` |
| 1.2 | vol-norm 标签（TDD）【V1 重定义，ADR-0014】 | `evaluation/metrics.py` | `_vol_norm_returns`。**`_market_residual`（OLS）推迟到 V2**——V1 标签 = vol-norm 后的 raw forward return（方向性），见 ADR-0014 |
| 1.3 | ✅ Base Factor Model 完成（2026-07-02，121 tests）【V1 重定义，ADR-0014】 | `evaluation/base_model.py` | 最终形态与原计划不同：**动量/反转合并成一个 trailing-return 家族**（不预判方向，回归系数决定），两个固定窗口——短=2min、长=4h（split-sample 实测，非网格最大值，三币 BTC/ETH/SOL 合约验证）。**资金费率、波动率基准均测过后放弃**（无信号/无方向定义，详见 HANDOFF）。`incremental_significance(candidate_score, label, data, lag)`：候选与基准同构 `sign(score)×label` 因子收益流，FWL 提取截距做 NW 检验，含大样本浮点噪声护栏。`residualize(...)` 残差化标签变换仍推迟到 V2 |
| 1.4 | IC 衰减曲线（计算层） | `evaluation/metrics.py` | `_decay_profile(scores, returns, horizons)`，horizon 是读出来的不是搜出来的。**`horizons` 网格取值未定**——业界无统一标准，须按 crypto 机制尺度自定（秒级→日级，够宽够密罩住经济上合理的整条带），这是必须自己拍的设计项 |
| 1.5 | 多 horizon 评估编排 + 标签/walk-forward 统一接线 | `evaluation/factor.py` | `evaluate_directional_factor` 从单 horizon 升级为吃 `horizons` 网格、返回整条 profile 进 `FactorEvaluation`。**评估对象是整条曲线，不塌缩成单点**。**同一次手术完成三件事**（决策于 1.2,避免混血过渡态）：①标签从裸 forward return 换成 **vol-norm 版**（除以 1.2 的 `_vol_norm_returns` 分母,V1/ADR-0014）；②接入 1.1 的 walk-forward 切窗（pooled OOS NW + ICIR 口径见 HANDOFF）；③审计改为每因子跑一次、不随 horizon 数翻倍 |

**验收：** 同一因子在完整 walk-forward + vol-norm 标签 + NW 修正下重跑，IC 判决是诚实的。
此处可能直接证伪迭代 0 看到的"信号"——那也是有价值的结果。

> **V1/V2 分轨（ADR-0014，2026-07-02）：** V1 = **方向性**（vol-norm raw return 标签，
> 单腿事件化交易，horizon 锁定 **~1min–4h**（2026-07-02 从 15min–4h 下扩，实测 5min
> 是反转效应最强最稳的 horizon）；BTC 条款推广到全部币）；V2 = 市场中性
> （`_market_residual` 残差标签 + 对冲，解锁日级以上 horizon）。评估机器标签无关,
> 切换只换标签函数。V1 三护栏：horizon 锁短端 / TSMOM 增量基准 / 库相关性检查
> + 风险层按 ~1 个相关赌注计。

> **Block bootstrap（DEFERRED，条件触发，不排期）：** NW（0.2）是**渐近**方法，
> 序列够长时够用。**触发条件**：迭代 1 上 walk-forward 后，若 test 窗口过短
> （NW 的 t 分布近似不可信）或残差严重非正态，则补 **block bootstrap** 作为
> 自相关稳健显著性的替代/交叉验证——对逐 bar 序列做分块重采样构造经验分布，
> 绕开"选 L"和正态假设。落点 `evaluation/metrics.py`（`_block_bootstrap_pvalue`），
> Research Gate（2.2）可切换或并用。**纪律：不满足触发条件不写**——提前写属于为
> 可能不存在的问题写代码；先让 NW 在真实样本量上跑，由数据决定是否需要。设计
> 文档 §3.5 的 "Newey-West / block bootstrap" 并列即此意。

> **多 horizon 评估的纪律（贯穿 1.4/1.5 → 2.x）：** 评估**不是** max-over-horizon，
> 也不是固定单 horizon。horizon 是**因子假设的一部分**，由经济机制事前声明；在网格上
> 看整条衰减曲线，用**「连续宽带 vs 孤立尖峰」**区分真信号与噪声——超短端（1–5min）
> 被微结构噪声压住、中长端一整片显著，正是真信号的标志性长相，不可因单点差而错杀。
> 终审仍在迭代 4 的扣成本组合夏普（把 horizon 整合掉）。读出准则（带的连续性/显著性
> 阈值）作为纯统计谓词落在 2.2。

### 迭代 2 — 多重检验 + 库正交性（~3 天）

- **消除：** 这个信号是真的，还是多重检验的运气 / 与已知因子冗余？
- **退出问题：** "deflation 后仍显著，且对 Base Model + 现有库正交吗？"

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 2.1 | Trial Registry | `evaluation/registry.py` | `register/count/load`，JSON Lines，记录**所有**候选含被拒。**记录事前 metadata：经济机制文本 + 声明 horizon**（审计 + deflation 计数用）。**衰减曲线扫的每个 horizon 计入 trials**——扫网格本身要付多重检验代价 |
| 2.2 | Research Gate = 纯统计谓词 | `evaluation/gates.py` | 移除 Sharpe；接 NW t-stat + deflated p（`p*count`）+ ICIR 阈值。**加衰减带谓词**（连续宽带 + 显著性，对应 1.4/1.5 的读出准则）+ **声明 horizon vs 实测带一致性检查**（声明"8h 回归"却只在 5min 工作→机制不符，标记） |
| 2.3 | 库存 Factor Return Stream + 增量 IC | `evaluation/library.py` | `add_factor(id, stream, meta)`→parquet；`incremental_ic(...)`；`is_orthogonal(0.05)`。**`meta` 存机制文本 + 声明 horizon**（审计） |
| 2.4 | grid.py 标 DEPRECATED | `evaluation/grid.py` | 顶部 banner，保留文件免 import 崩 |
| 2.5 | 信号分桶条件收益单调性（非 IC 支柱，TDD） | `evaluation/metrics.py`、`evaluation/gates.py` | 计算层 `_conditional_return_profile(scores, returns, n_buckets)`：按信号分位分桶，出每桶平均收益（**V1 吃 vol-norm raw return,V2 换残差收益**,ADR-0014）。这是 V1 事件化交易形态的核心证据（验证"越极端越准"的结构；阈值本身留给部署层,因子层零自由参数）；Gate 谓词：桶均值单调性（Spearman on bucket means）+ 顶底桶差 NW 显著。**先测**：合成单调关系→通过；U 型/非单调（IC 显著但形状坏）→拦截 |

**验收：** 完整 Research Gate 路径 NW-tstat deflation → orthogonality → **单调性** → accept/reject，
全有测试。grid/threshold 搜索不再被调用。

> **经济先验的归处（不要建模块）：** 经济先验**大部分不能代码化**，硬塞统计函数是假严谨。
> 可代码化的只有两块：①**事前假设记录**——机制 + 声明 horizon 起源于 `mining/proposal.py`
> （LLM 提因子时一并产出），作为 metadata 往下传，存档进 `registry.py`(2.1) 和 `library.py`(2.3)；
> ②**机制-horizon 一致性检查**——声明 vs 实测带，纯统计，落在 `gates.py`(2.2)。
> **「这是真机制还是事后编故事」的判断停在 RC 人工门**（见下方 Phase RC），不进代码。
> **边界**：机制文本起源于 `mining/`，但 `evaluation/` 只把它当传入的 metadata + 做一致性
> 检查，**绝不在 `evaluation/` 里调 LLM 做经济分析**（守 `CLAUDE.md` 的 evaluation 不调 LLM 铁律）。

> **为什么只加分桶单调性这一根非 IC 支柱（2.5 的取舍）：** 业界统计筛选不止 IC——还看分位数
> 多空收益、换手/成本、因子 Sharpe。但换手/成本/Sharpe 按"零交易参数"不变量归 Trading Gate；
> 分位数**截面**多空因 N=2–3 退化不可用。**唯一同时满足「与 IC 正交 + 小 N 时间序列可用 + 纯
> 统计无交易 + 低复杂度」的支柱，就是按信号强度分桶的条件收益单调性**——它抓 Rank IC 系统性
> 漏掉的**非线性/尾部结构**（IC 显著但只有极端分位有效、中间反向的假因子会被它拦）。**纪律：
> 因子层判据要吝啬**，每加一个 gate 维度就多一条过拟合自由度；hit rate（与 IC 冗余）、非线性
> 依赖 MI（小样本估计噪声大、难 deflate）、高阶矩预测（仅按因子机制逐个启用）都**只作诊断/
> 升级工具，不进常规 gate**。仅当 RC 出现「IC 显著却回测不赚」时才升级到 MI 等。

> **截面发现 / 信息宇宙 ≠ 可交易宇宙（backlog，暂不做）：** N=2–3 指**可交易**标的数；几百个流动
> 币的信息**没丢**，可作特征/市场代理/残差化目标（Base Model §3.4 已用）。丢的只是"可交易集上的
> 截面多空组合"这个自带市场中性、需交易多腿的构造物。**潜在效率增强**：用几百币宇宙做**截面发现**
> （每时点几百观测，高统计功效筛机制），再把幸存机制拿到 2–3 个可交易标的做 **per-symbol 时间序列
> 终审**（终审必须在可交易标的上，因那才是 P&L）。当前设计默认直接在 per-symbol 提+评因子；截面
> 发现是"搜索效率层"，与进化搜索(§3.12)同类——**发现流程正确前不做**，仅当"2–3 标的统计功效不足、
> 机制看不清"成为真实瓶颈才上。

### 迭代 3 — 闭合挖因子循环（~3 天）

- **消除：** 自动化提案能持续产出**正交**新因子，还是 LLM 反复提相关机制？
- **退出问题：** "propose→evaluate→feedback 一轮能跑，且反馈把已覆盖方向挡掉吗？"

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 3.1 | 循环协调器 | `mining/loop.py` | `run_discovery_loop(config, n_rounds)`：proposal→runner→Research Gate→library |
| 3.2 | 正交性反馈注入 proposal | `mining/proposal.py` | 已入库 mechanism 摘要注入 LLM（"以下已覆盖，提正交方向"）。**库快照按轨道切**（ADR-0014）：V1 轮只喂 `label_mode=directional_v1` 条目、V2 轮只喂 V2 条目——同一机制在两种标签下是两个独立假设，查重必须各查各的,混喂会让 LLM 误跳过未测的另一轨版本 |
| 3.3 | 断开旧 grid 调用链 + 轨道标记 | `mining/batch_runner.py`、`mining/round.py` | 路由到新 Research Gate。**产物全链路加 `label_mode` 字段**（ADR-0014）：manifest/报告/库条目/Trial Registry 统一标注 `directional_v1 \| market_neutral_v2`；库与 feedback 按轨隔离,V1 结论仅算方向性证据,V2 声明须残差标签下重评 |
| 3.4 | Loop smoke 测试 | `tests/test_mining_loop.py` | mock LLM 验证一轮完整路径（含轨道隔离:V1 轮快照不含 V2 条目,反之亦然） |
| 3.5 | _(可选/可延后)_ 进化搜索 | `mining/evolution.py` | fitness=deflated incremental IR；niching；LLM 变异算子。设计文档 §3.12，**仅当搜索成瓶颈才做**。**fitness 公式按轨道适配**（§3.12 原文是 V2 语言"residualizing against base model"；V1 语境下=对 TSMOM 基准的增量,勿照抄） |

**验收：** CLI 跑 `run_discovery_loop` 多轮，库稳定增长，重复机制被反馈挡住。

### 迭代 4 — 净成本现实检验（~4 天）

- **消除：** 统计上显著的毛信号，扣完 Binance 成本后还净正、可交易吗？
- **退出问题：** "过 Research Gate 的因子，组合后过 Trading Gate 吗？"
- **为什么现在才上 NautilusTrader：** IC 证伪比回测便宜，毛信号先筛；这是 RC 的
  第二次触碰（毛信号 → 净可交易性），与 Research/Trading 两层门的语义一致。

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 4.1 | 连续加权 + 组合构建 | `evaluation/portfolio.py` | `rank_weight=(rank-0.5)/N`（无阈值）；`combine_factors`；`vol_scale(target_vol=0.15)` |
| 4.2 | NautilusTrader 接入 | `quantaalpha_crypto/backtest/` | `FactorStrategy(Strategy)` signal→order，同对象 backtest+live；`costs.py` fees/slippage/funding；`runner.py` |
| 4.3 | Trading Gate 谓词 | `evaluation/gates.py` | 输入回测输出，查 portfolio net Sharpe / max DD；与 Research Gate 分离 |
| 4.4 | 端到端集成测试 | `tests/test_backtest_integration.py` | Research accept→backtest→Trading accept/reject 全路径 |
| 4.5 | ADR-0014 | `docs/adr/` | NautilusTrader committed single engine |

**验收：** 一个过 Research Gate 的因子，端到端跑到带成本的 portfolio Sharpe 判决。

> **数据扩展（横切，按需插入任意迭代）：** `data.py` 接 OI / Long-Short Ratio；
> feature/tradable universe 分离；自动拉取 Binance 历史数据脚本。某迭代需要才做。
> **清理（持续）：** 删 `grid.py`、规范 `tests/` 文件名、提 `prompts.yaml`、删 README transition banner。

---

## ★ Phase RC — 研究检查点（硬门，开放式）

**整个项目的真正瓶颈，不是工程。** 迭代 0–4 给了你能问 RC 的工具，RC 才回答有没有钱赚。

- **做什么：** 配真实研究方向（`docs/research/`），多轮跑 `run_discovery_loop`，
  积累 Factor Library，监控 Registry 计数与 deflated 显著性，过 Trading Gate 的入选。
- **放行标准（提前定死，事后不许调低）：**
  - ≥ **3–5 个互相正交**的因子，单独跑都过 Trading Gate（net-positive after cost）
  - 组合后 walk-forward 样本外 Sharpe **跨窗口稳定**（不是单窗口幸运）
  - 因子有经济先验解释，不是纯数据挖掘
- **不通过：** 回研究方向迭代（新机制 / 新数据 / 新 universe），**不进 Phase D**。
  诚实记录每次实验到 `docs/research/`。这个循环可能数周到数月。

---

## Phase D — 风险管理层（~5 天，RC 通过后）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| D.1 | 动态协方差 | `risk/covariance.py` | EWMA / Ledoit-Wolf 收缩；因子间 + 资产间 |
| D.2 | 组合层风险预算 | `risk/budget.py` | 单因子 vol-scale 升级为组合 risk parity / vol-target |
| D.3 | 回撤控制 | `risk/drawdown.py` | 回撤触发 de-gross，非硬止损 |
| D.4 | 资金费率敞口 | `risk/funding.py` | perp funding 累计敞口上限 |
| D.5 | 流动性/冲击约束 | `risk/liquidity.py` | 单标的最大仓位=f(ADV)；大单拆分 |
| D.6 | 压力测试/VaR | `risk/stress.py` | 312 / LUNA / FTX 情景重放；VaR/CVaR |
| D.7 | 风控接入回测 | `backtest/runner.py` | 验证风控不显著吃掉 alpha |

**验收：** 带风控 walk-forward，Sharpe 下降可控，最大回撤显著改善。

---

## Phase E — 影子/纸面交易（~10 天工程 + 持续观察）

| # | 任务 | 说明 |
|---|------|------|
| E.1 | live 数据接入 | Binance WebSocket；同一 Strategy 切 live 数据 |
| E.2 | 纸面交易引擎 | 真实行情、模拟撮合、零真金 |
| E.3 | 实盘成本校准 | 纸面成交对比回测假定 slippage/fees |
| E.4 | 监控 + 告警 | 信号/持仓/PnL/风控状态面板 |
| E.5 | 实盘-回测对账 | live vs backtest signal 逐 bar 归零 |
| E.6 | 运营 runbook | 启停/断线/数据缺失/紧急平仓流程 |
| **观察期** | **不可压缩** | 纸面跑**数周**，确认 live PnL 与回测预期一致 |

**放行标准：** 纸面 PnL 落在回测预期置信区间内；无重大执行/数据/对账问题。

---

## Phase F — 正式上线（分批放量，运营主导）

| 阶段 | 资金 | 持续 | 退出标准 |
|------|------|------|----------|
| F.1 最小真金 | 可承受全损 | 2–4 周 | 实盘成交/成本/PnL 与纸面一致 |
| F.2 小额 | 目标 ~10% | 4–8 周 | Sharpe/回撤在预期内，无运营事故 |
| F.3 半仓 | 目标 ~50% | 8 周+ | 容量/冲击未显著衰减 alpha |
| F.4 满仓 | 目标 100% | 持续 | — |

**贯穿全程：** 实时风控熔断（单日最大亏损 / 回撤硬上限 → 自动 de-gross/停机）；
密钥资金安全（API 权限最小化、提币白名单、冷热分离）；因子衰减监控（live IC
跌破阈值 → 退役）；**定期回 RC 补因子**。
**任一批放量出现实盘-预期偏离，回退一档，不硬上。**

---

## 依赖与形态

```
迭代0 → 迭代1 → 迭代2 → 迭代3 → 迭代4 → ★RC → D → E → F
  └ 每个迭代端到端可跑，消除当前最大不确定性 ┘    └ 门控保守 ┘
                                    ↑___________________↓
                              （alpha 衰减后持续回 RC 补因子）
```

- **前段是螺旋不是瀑布：** 每个迭代纵向穿透，尽早证伪。迭代 0 在第 3 天就触碰
  "有没有 alpha 迹象"，而不是等 12 天工程做完。
- **★RC 唯一不能排期**，也是最可能停住项目的地方。工程做完 ≠ 有钱赚。
- **后段是门控不是迭代：** 真金阶段要瀑布式纪律，每道门提前定死，出偏离回退。
- **上线后是循环不是终点：** alpha 衰减是常态，RC→D→E→F 持续转。
```
