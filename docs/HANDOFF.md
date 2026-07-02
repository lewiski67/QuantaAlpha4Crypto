# Handoff / Current Status

> **每日任务在 [`docs/PLAN.md`](PLAN.md)。** 新会话开始时先读那里，再回来看本文背景。

Living document for seamless project continuity. Update at meaningful
checkpoints (not every turn): when task state, decisions, or next steps change.
Stable facts (architecture, conventions, commands) belong in `CLAUDE.md`, not here.

_Last updated: 2026-07-02 (1.2 完成: _vol_norm_returns)_

## Current state

- Crypto migration landed on `main` and is **pushed to `origin/main`**.
- Project handed from Codex to Claude Code. `.codex/` and empty `.agents/`
  removed; `AGENTS.md` renamed to `CLAUDE.md`.
- Duplicate-code debt paid down (commits `3e7e962`, `8986586`): shared helpers
  now live in `mining/_utils.py` (`_redact_secrets`, `_progress`) and
  `evaluation/metrics.py` (`_simple_sharpe`, `_forward_returns`, `_rank_ic`,
  `_max_drawdown`, `_annualization_factor`). `_simple_sharpe` unified on grid
  semantics per user decision (empty -> NaN, zero-vol loss -> -inf); this
  changed portfolio backtest sharpe for degenerate cases.
- 102 tests pass. `old/` and `/artifacts/` gitignored, reference-only.
- Local `docs/prd/` and `docs/tasks/` removed — Codex-era deviation; PRDs and
  task breakdowns now go to GitHub Issues via `to-prd`/`to-issues` + `gh`.
  Recover from git `92b40de` if needed.
- Root design notes moved to `docs/design/`. `dynamic_threshold_methods.md` later
  deleted (obsolete under the new paradigm — no thresholds in discovery).
  `strategy_core_architecture_plan.md` kept (superseded on methodology, retained
  for deployment-layer detail). `CLAUDE.md` updated with PRD/HANDOFF conventions.
- **Methodology overhaul decided AND documented** (see
  `docs/design/factor-system-architecture.md`). Time-series (per-symbol) not
  cross-sectional; pure statistical screening (no grid/threshold/strategy-Sharpe
  at the factor layer); market neutralization (external BTC/index proxy) +
  autocorrelation-corrected t-stats + walk-forward purge/embargo;
  orthogonality/incremental-IC intake against a new Base Factor Model;
  multiple-testing deflation via a Trial Registry. Thresholds, sizing, regime,
  risk all move to a future portfolio-construction layer (regime dissolves into
  the risk model, no explicit filter). **NautilusTrader is the committed single
  backtest/live engine** (decided 2026-06-29; not for discovery; promote to an
  ADR when that layer is built). Improved evolutionary search is designed but
  deferred (design doc §3.12).
- **Docs aligned to the new paradigm** (committed `e29465c`): wrote **ADR-0012**
  (paradigm) and **ADR-0013** (purge/embargo); marked ADR-0001/0002/0003/0009/0011
  superseded/amended; rewrote `CONTEXT.md`; banners on the two old design docs;
  `CLAUDE.md` + research log noted as in-transition. Code is NOT yet changed —
  `evaluation/` still has the old grid/gates; the docs now describe the target.
- **全生命周期计划写定**（`docs/PLAN.md`）：螺旋迭代 0–4 → ★RC → Phase D–F。
  **迭代 0（行走骨架）已完成并提交**（0.1/0.2/0.3 + tz 修复，89 tests 全绿）；下一步迭代 1。

迭代 1.1 完成（2026-07-02，walk-forward + 按时间戳 purge，TDD，96 tests 全绿，**未 commit**）：
- **替换** `evaluation/walk_forward.py`（旧三段 train/val/test 日历-delta 构造器是死代码：
  零生产调用、无专门测试——直接删，不并存）。新 `build_walk_forward_windows(sample_index,
  horizon, train_window=180D, test_window=30D, step=30D, execution_lag_bars=1)`：**rolling +
  两段(train/test)**，砍 validation 段（因子零自由参数，无超参可选→留出多余）。每窗吐
  已 purge 的 `train_index` + `test_index`（MultiIndex 子集，`.loc` 即用）。
- **purge 按时间戳，不数根数**（关键决策，多轮讨论定案）：训练行 `entry+horizon >= test_start`
  即剔除；`entry` = per-symbol 下一根 bar（**entry 对齐 = t+1+horizon**，复用 `_forward_returns`
  的 `shift(-1)` 语义，`_label_exit_timestamps` helper）。**用 t+horizon 会漏一根 bar 泄漏**
  （under-purge，非保守）——已证伪，用 entry 对齐零漏。缺口回归测试锁死时间戳语义（01-04 的
  entry 跨缺口进 test→正确 purge）。
- **embargo 不加**：前向 walk-forward 每窗 train 整体在 test 之前，embargo（剔 test 之后的
  train）无对象可作用→是 no-op，加它属 speculative feature（tdd skill 禁）。**留到 CPCV 阶段**
  再加（那时 test 夹在两 train 中间才有可测行为）。ADR-0013 的 embargo 要求由 CPCV 满足。
- 边界层 vs 样本层：**等价**（同一不等式移项 `entry+horizon≥test_start` ⟺ `entry≥test_start−horizon`），
  实现选边界层（单 cutoff 向量化）、输出样本索引。当前真实数据（37 币 1m，Δ 恒 60s 零缺口，
  实测）均匀→A≡B；选时间戳法是口径卫生（与标签同源）+ 抗未来混频，非当前数据必需。
- 测试 `tests/test_walk_forward.py`（新，9 例）：tracer 两段切分 / purge 核心保证 /
  **缺口回归（时间戳≠根数）** / **step 默认继承 test_window→test 段无缝** / **显式 step 覆盖（可重叠）** /
  无尾部残窗 / 空索引→[]（守死循环）/ 非正窗口→raise。
- **step 默认继承 test_window**（方案2，追加于 1.1）：签名 `step=None`，不传时 `step=test_window`。
  理由：pooled OOS NW 的正确性前提是 **`step==test_window`**（连续 test 段错位量=step、段长=test_window，
  相等才无缝平铺→pooled 流是单一连续 OOS 区间）。`step<test` 重叠→bar 双计；`step>test` 留缝→
  拼接处伪自相关。原来两个默认值都 30D 只是**撞巧相等**、代码不强制，改 test 忘改 step 会**静默算错**。
  现在默认做对（无缝），仍允许显式传 step 做 CPCV/加密 ICIR 采样等高级用法（责任交调用方）。
- **pooled OOS NW 口径（1.5 待接线的既定设计，已讨论定案）**：headline 显著性 = **各 test 段逐 bar
  贡献流 `x_t=(score−μ_段)(ret−μ_段)` 拼接后跑一次 NW**（每段用段内 μ 去中心化再拼，避免跨段均值污染）。
  默认 `step==test_window` 下 test 段日历连续→拼接缝是**真相邻**、NW 该保留该项,**无需分段掩码**
  （早前"接缝伪自相关"顾虑仅在 step>test 时成立，默认配置下作废）。稳定性另走 **ICIR = 各窗口 IC 的
  mean/std**（显著性要合 bar 做大功效、稳定性要保留窗口离散度，两条线相反,不互替）。
- **因子因果性审计改为强制**（2026-07-02，方案A，泄漏审计发现的独立缺口，非 PLAN 1.x 条目）：
  `evaluate_directional_factor` 的 `input_lookback_window` 不传即 raise——审计（16 抽查点
  截断重算对拍，验证因子无前视+声明回看诚实）从选配变成每个因子进评估的强制关卡。原状态下
  不传参数审计整体跳过，`shift(-1)` 类非因果因子会静默拿高 IC，是当时最实在的泄漏口。
  连带:`judge_single_factor` 增加必传 `input_lookback_window` 参数;CLI round config 把
  `input_lookback_window` 列为必填字段并接线(原来 CLI 从不读该键→评估层永远 None)。
  防未来不依赖声明诚实(审计右边界硬编码在 t),声明只定左边界(过去用量诚实性)+实盘预热语义。
  mining 中间层(batch_runner/proposal/runner/round)的 `None` 默认保留——真实 CLI 流已必填,
  None 流到评估层会带清晰错误信息失败;该链路迭代 3 重写时再收紧。多频因子声明=各成分回看
  时长的最大值(时间量,非根数),与审计机制天然兼容。
- **V1/V2 分轨决策（2026-07-02，ADR-0014,用户拍板）**：经两天 alpha/beta 定位长讨论
  （方向性 vs 市场中性两条路径、对冲机制、费用算术、事件化交易),用户决定 **V1 = 方向性**：
  标签 = vol-norm 后的 **raw forward return**（无市场残差化）,单腿事件化交易 BTC/ETH/SOL,
  horizon 锁 ~15min–4h。**V2 = 市场中性**：`_market_residual` 残差标签 + β 对冲,解锁日级+。
  评估机器标签无关,V2 切换只换标签函数。V1 三护栏（缺一会踩克隆/伪显著/伪分散坑）：
  ①horizon 锁短端（raw 标签日级+被大盘单一趋势主导,统计失效）；②Base Factor Model 保留
  TSMOM 增量基准（克隆杀手）；③库相关性检查 + 风险层按 ~1 个相关赌注计。事件化的阈值
  不进因子层（零自由参数）——2.5 分桶单调性验证"越极端越准"结构,阈值留部署层对费用算术定。
  关键实测依据：corr(ETH,BTC)=0.82,大盘解释 ETH 方差 67%,残差 σ≈57% 总 σ
  （`alpha_beta_decomposition.png`,真实日线 2024–2026）；费用算术:同 horizon 单腿占优,
  但短 horizon 毛利(IC×σ≈1–4bp)vs 固定费用(taker RT 8–10bp)是 V1 主要生死线,
  迭代 4 按事件化换手裁决。old/QuantaAlpha 是第三条路径（横截面相对收益/指增：CSRankNorm
  标签+Top-k 纯多头+对标基准）,N=2–3 退化不可迁移（ADR-0012 Context 第 1 条）。
- **挖掘框架评估结论（2026-07-02）**：`mining/` 骨架 + 设计文档 §3.2/§3.8 目标**保留,
  不为 V1/V2 分建两套**（生成与判决解耦→标签无关）；接线重做仍按迭代 3 原计划。V1/V2 新增
  两条并入迭代 3（已写进 PLAN 3.2/3.3/3.5 与设计文档 §3.2/§3.12）：①产物全链路加
  `label_mode` 轨道字段,库/feedback 按轨隔离；②novelty feedback 的**库快照按轨道切**
  （同一机制在两种标签下=两个独立假设,混喂快照会让 LLM 误跳过未测的另一轨版本）；
  §3.12 进化搜索维持 DEFERRED,其 fitness 公式是 V2 语言,V1 语境须改为对 TSMOM 基准的增量。
迭代 1.2 完成（2026-07-02,TDD,108 tests 全绿,**未 commit**）:
- `evaluation/metrics.py` 新增 `_vol_norm_returns`（V1 标签,ADR-0014）+ `_trailing_volatility`
  + `_VOLATILITY_FLOOR`。标签 = `_forward_returns / (σ̂_trailing × √bars_per_horizon)`。
- **设计决定全部逐项与用户确认**（讨论+实验依据,均真实数据）:①窗口 trailing **7D 按时间戳**
  per-symbol（1D 会事件自吞噬+分母内生;20D 对 crypto regime 太钝;7D 整除周周期）;
  ②**简单滚动 std** 非 EWMA（EWMA 事件时刻分母瞬涨 31% 压扁事件标签;实测两者标签相关
  0.997,判决无差,少一个 λ 参数）;③输入=面板原生 bar 简单收益（**频率无关**,调用方重采样,
  与信号频率一致）;④**满窗 warmup**（不足 7D→NaN,每币丢开头 7D）;⑤floor **仅防零**
  （ε=1e-12,不塑形）;⑥**√h 缩放**（对下一小时真实 RV 赛马:与直接 h 尺度估计**平局**
  （RMSE/QLIKE/Spearman 差 <1% 且方向翻覆）,工程定胜负——一条 σ̂ 序列服务全 horizon 网格;
  √h 恒定偏差 ~4% 对 IC 无影响;两半自洽实验:直接法自噪 ±5%、√h 法 ±2.4%（厚尾放大,
  高斯理论 0.7% 不成立））;⑦**接线留 1.5**（PLAN 1.5 行已写明三合一手术:换标签+接
  walk-forward+审计每因子一次）。
- 真实数据验证（BTC 1m 129 万根,0.76s）:**归一化标签 std=1.0035≈1**（单位方差自洽,
  √h 与 trailing σ̂ 咬合正确）;首个有效标签恰在面板开始+7D;全部有限;|label| p50=0.45,
  p99=3.6。
- 测试 `tests/test_metrics.py` +10 例:除以 trailing std / √h 缩放（精确 −0.05 手算例）/
  **缺口时间戳窗口回归**（bar-count 会跨缺口误取）/ 默认 7D 满窗 warmup / 零波动 floor 有限 /
  **per-symbol 自归一化**（10× 振幅两币标签相等）/ 分钟频 / 亚 bar horizon raise / 非正窗口 raise。
- **下一步 1.3（V1 重定义）**：Base Factor Model 仅作增量 IC 基准（TSMOM(20)/波动率(20)/
  资金费率均值(8期)）,`residualize()` 推迟 V2;或直接跳 1.4（衰减曲线,**horizon 网格待拍**,
  V1 锁 ~15min–4h）——顺序可与用户确认。

## Next steps

见 **`docs/PLAN.md`** — 当前迭代任务、验收标准、完整路线图均在那里。

关键决策备忘（不在 PLAN.md 里的）：
- propose→evaluate→feedback 循环必须接新统计评估（迭代 0–2），**不能先接旧
  `grid.py`/`gates.py` 让 loop 跑通再换**——旧 eval 产生的 feedback 本身是错的。

PLAN 增补（2026-06-30，多 horizon 评估 + 经济先验定位，未写代码）：
- 迭代 1 加 **1.5 多 horizon 评估编排**（`factor.py` 吃 `horizons` 网格返回整条 profile，
  不塌缩单点）；1.4 标注 **horizon 网格取值未定**（须按 crypto 机制尺度自定）。
- 多 horizon 纪律写明：评估≠max-over-horizon≠固定单 horizon；horizon 是因子假设的一部分，
  用「连续宽带 vs 孤立尖峰」判真伪；终审在迭代 4 扣成本组合夏普。
- 迭代 2 接上缺口：衰减曲线扫的每个 horizon **计入 Trial Registry / deflation**；
  **经济先验不建模块**——只记录事前 metadata（`mining/proposal.py`→`registry.py`/`library.py`）
  + 声明 vs 实测 horizon 一致性检查（`gates.py`）；真机制判断停 RC 人工门，evaluation 不调 LLM。
- 执行间隔（t+1 进场，标签 `close[t+1+horizon]/close[t+1]-1`）已实现（2026-06-30）：
  `_forward_returns` 加 `execution_lag_bars=1` 默认参数（positional entry + time-based exit）；
  `evaluate_directional_factor` 透传。70 tests 全绿。**迭代 0.1 完成。**
  旧测试（测 IC/alignment index/trailing window 等）显式传 `execution_lag_bars=0` 保留原语义。

真实数据接通 + tz bug 修复（2026-07-01）：
- 本机真实数据在 `/home/lewiski/crypto_data/candles/<SYMBOL>/1m.jsonl`（37 币含 BTC/ETH/SOL，
  2024-01-01→2026-06-17，BTC 1m 约 129 万根）。用 `data.py` 的 `load_binance_crypto_panel_data`
  加载（`source_format="binance_spot_candles_jsonl"`, `product_type="spot"`）。**注意列名带前缀
  `spot_close` 等**，因子要按 `_default_close_column` 约定挑列，别写死 `data["close"]`。
- **修了 `_forward_returns` 的 tz bug**（`evaluation/metrics.py`）：原 entry 时间戳用
  `pd.to_datetime(...values)` 重建会**丢时区**，真实 tz-aware(UTC) 数据 reindex 全对不上→
  forward return 全 NaN→IC 全 NaN。改用 `pd.DatetimeIndex(pd.Series(...).shift())` 保时区。
  合成数据(tz-naive)没暴露此 bug。加回归测试 `test_forward_returns_preserve_tz_aware_index`。**89 tests 全绿**。
- **首个真实判决**（BTC 2024 H1, 波动率归一化短期反转因子, window=20）：全 horizon(1/3/5/15/60min)
  IC≈0、|NW_t|≤1.6 → **indistinguishable-from-noise**。裸价格反转在 1m BTC 上无独立 edge——
  管线诚实工作的证据。注:这是**单全样本、未市场中性、未 walk-forward**,不是研究结论。

迭代 0.3 完成（2026-07-01，全样本 IC + NW 端到端判决，TDD）：
- `evaluation/metrics.py` 加 `_bars_per_horizon(index, horizon)`：per-symbol 时间戳 diff 众数推
  bar 间隔 Δ，`lag = round(horizon/Δ)`；多 symbol Δ 不一致 raise；样本不足 raise；非正 horizon
  raise。**定了 `lag=H_bars`**（NW 惯例）。
- `evaluation/factor.py`：`FactorEvaluation` 加 `nw_tstat` 字段；新 `_nw_ic_tstat` 产逐 bar
  x_t=(score−mean)(ret−mean) 调 `_nw_tstat`。**0.3 骨架两处已知粗糙（迭代 1 修）**：①x_t
  **pooled**（非 per-symbol demean），按 (symbol,timestamp) 排序让同 symbol 连续，跨 symbol
  边界项少量虚假；②Δ 从**完整 panel 网格**读（只对非填充干净因子成立，粗频/填充留迭代 1）。
- `mining/loop.py`（新，最小）：`judge_single_factor` + `_verdict_label`（|t|≥阈值→signal，
  NaN→insufficient-data，否则 noise）+ `format_verdict`。**只 import evaluation**（守依赖方向，
  module-boundary 测试通过）。端到端 smoke：动量因子→IC+0.19 NW_t+2.53→signal。
- 测试：`test_metrics.py`（+7 `_bars_per_horizon`）、`test_factor_callable_evaluation.py`
  （+1 nw_tstat 有限且符号同 IC）、`test_mining_loop.py`（新，4 例）。**88 tests 全绿**。
- **迭代 0（行走骨架）完成并提交。** 0.1 早已在 `8ed30da`；本次提交收 0.2 + 0.3 + tz 修复
  + 真实数据接通。**尚未 push**（等用户确认）。

迭代 0.2 完成（2026-07-01，NW 自相关修正 t-stat，TDD）：
- `evaluation/metrics.py` 加 `_nw_tstat(series, lag)`：吃逐 bar 贡献序列 x_t，出 Newey-West
  (Bartlett 核) HAC t-stat。**只改标准误、不动点估计**；`lag=0` 精确退化朴素；边界
  （空 / T≤lag / 零方差 / 非正 long-run var）→ NaN；`lag` 必填无默认。
- 设计决策（已定）：`_nw_tstat` 是**纯统计工具**，不知道 IC/horizon；`lag` 单位是 bar 根数，
  由调用方用 `horizon / bar间隔` 算好传入。换算 helper `_bars_per_horizon`（从时间戳众数推
  bar 节奏）归 `evaluation/metrics.py`，**留到 0.3 接线时写**，不放 `mining/`（守依赖方向）。
- per-symbol vs pooled 的 x_t 怎么产 → 迭代 1，0.2 不碰。
- 测试 `tests/test_metrics.py`（新文件，6 例）：正自相关 `|t_NW|<|t_naive|` 且不翻符号；
  `lag=0`==朴素；白噪声 `lag>0` NW≈朴素；空/样本不足/零方差→NaN。**76 tests 全绿**。
- **未 commit**（迭代 0 未结束，0.3 单切分 IC 判决脚本待做）。

PLAN 增补（2026-07-01，非 IC 统计支柱 + 截面发现 backlog，未写代码）：
- 迭代 2 加 **2.5 信号分桶条件收益单调性**（`evaluation/metrics.py` 计算层
  `_conditional_return_profile` + `gates.py` 单调性谓词）：唯一同时满足「与 IC 正交 + 小 N
  时间序列可用 + 纯统计无交易 + 低复杂度」的非 IC 支柱，抓 Rank IC 漏掉的非线性/尾部结构。
  吃 1.2/1.3 的 vol-norm 市场残差收益。**纪律**：hit rate/MI/高阶矩只作诊断/升级，不进常规 gate。
- 记 backlog：**截面发现（信息宇宙 ≠ 可交易宇宙）**——N=2–3 是可交易数，其他币信息可作特征/代理；
  截面发现是"搜索效率层"（与进化搜索同类），发现流程正确前不做。
- 措辞更正:早先"失去截面信息"不准确——丢的是"可交易集上截面多空组合"（自带中性、需多腿交易），
  信息本身没丢。

PLAN 增补（2026-07-01，0.3 改为全样本、砍 train/test 切分，未写代码）：
- **决策**：原 0.3"单 train/test 切分 → 样本外 IC"改为**全样本 IC + NW 显著性**，砍切分。
  理由：单个写定、零自由参数因子的评估**无拟合、无选因子**，holdout 统计上多余；业界评估
  原语（predictive regression / Fama-MacBeth）就是全样本 + HAC(NW)，不留出。切分的价值是
  非平稳/持续性检验 → 归 **walk-forward（迭代 1）**；多重检验去膨胀 → 迭代 2。分层：全样本
  IC+NW=评估原语(0.3) → walk-forward(1.x) → deflation(2.x)。**红线：别停在单因子全样本当研究判决交易。**
- PLAN 已改：迭代 0 消除/退出问题措辞、0.3 任务行（文件补 `metrics.py`+`factor.py`）、验收行，
  加"为什么 0.3 不切分"blockquote。
- 0.3 三件事（未写）：`_bars_per_horizon`（Timedelta→lag 根数：per-symbol、对齐+dropna 后
  存活样本间距众数推 Δ，`lag=round(horizon/Δ)`，多 symbol Δ 不一致报错，**不照抄
  `_annualization_factor` 拍平写法**）；`factor.py` 接线产 x_t 调 `_nw_tstat` 挂进
  `FactorEvaluation`（全样本）；`mining/loop.py` 最小判决脚本。
- 两个写代码前待钉小决策：① NW lag 用 `H_bars` 还是 `H_bars−1`（倾向 `H_bars`）；② 前值填充
  的粗频因子 0.3 不处理（只做非填充干净情形），留迭代 1 per-symbol x_t 一起定。

PLAN 增补（2026-07-01，block bootstrap 定位为条件触发 deferred，未写代码）：
- 迭代 1 验收后加 **DEFERRED block bootstrap** 备忘：NW 是渐近方法，若迭代 1 walk-forward
  后 test 窗口过短 / 残差非正态则补 `_block_bootstrap_pvalue`（`evaluation/metrics.py`）作为
  NW 的替代/交叉验证，Research Gate(2.2) 可切换或并用。**不满足触发条件不写**——先让 NW
  在真实样本量跑，由数据决定。对应设计文档 §3.5 "Newey-West / block bootstrap" 并列。

## Open decisions

- **Rename the project?** "QuantaAlpha" is inherited from the dead A-share/Qlib
  system this no longer resembles. Not wrong semantically (quant + alpha), but
  creates a "same product as old QuantaAlpha" false impression. Deferred: a
  rename is high-cost, zero-functional-value churn (package name, pyproject,
  console script, CLI command names, repo dir, git remote, all docs/tests).
  Re-evaluate **after the methodology migration lands**, as one deliberate pass —
  not now, where it would tangle with the evaluation/ rewrite.
- Whether to delete the merged `crypto-migration` branch (already in `main`).
- Whether the removed Codex `engineering-workflow` skill is worth recovering
  (recoverable: `git show 92b40de:.codex/skills/engineering-workflow/SKILL.md`).

## Known cleanup debt

Tracked in `CLAUDE.md` under "Known cleanup debt". Keep the two in sync: this
file holds the *plan/status*, `CLAUDE.md` holds the *standing list*.
