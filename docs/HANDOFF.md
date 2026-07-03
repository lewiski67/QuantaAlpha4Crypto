# Handoff / Current Status

> **每日任务在 [`docs/PLAN.md`](PLAN.md)。** 新会话开始时先读那里，再回来看本文背景。

Living document for seamless project continuity. Update at meaningful
checkpoints (not every turn): when task state, decisions, or next steps change.
Stable facts (architecture, conventions, commands) belong in `CLAUDE.md`, not here.

_Last updated: 2026-07-03 晚 (ADR-0016 记分卡定案；1.4 细分为 1.4.0–1.4.10 专节；文档已全改，代码未动)_

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
  `strategy_core_architecture_plan.md` kept at the time (superseded on methodology,
  retained for deployment-layer detail), then **deleted by user 2026-07-02**
  (recover from git history if needed). `CLAUDE.md` updated with PRD/HANDOFF conventions.
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
  horizon 锁 ~1min–4h（2026-07-02 从 15min–4h 下扩,见下方 1.3 之后的记录）。**V2 = 市场中性**：
  `_market_residual` 残差标签 + β 对冲,解锁日级+。
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
- **1.3 范围收窄讨论（2026-07-02，未写代码）**：Base Factor Model 原定三条基准
  （TSMOM(20)/波动率(20)/资金费率均值(8期)）逐条推敲后有实质调整：
  - **加第四条基准：短周期反转**。真实 BTC 数据实测（15min/1h/4h lookback×horizon 网格）：
    V1 目标 horizon 带（15min–4h）上**反转 IC 全面为正、动量 IC 全面为负**——裸动量在这个
    尺度上不是主导效应，反转才是。外部文献交叉验证（非训练记忆，WebSearch 实查）：
    Shen et al. (2020) 用市场+规模+**反转**三因子给 crypto 定价（不是动量）；
    《Momentum or Reversal: Which is the Appropriate Third Factor for Cryptocurrencies?》
    本身就是这个问题的学术辩题；Wen et al. (2022) 日内研究证实动量反转共存、随流动性/
    跳跃/宏观事件切换主导权。**结论：加反转基准，理由是外部文献+自己数据双重印证**，
    不是我们独家发现。
  - **TSMOM/反转窗口无业界公认数字可抄**：查证发现 crypto 因子文献几乎全是横截面/周频
    大样本设定（Liu-Tsyvinski 系列），和我们「N=2–3、per-symbol、15min–4h 时序」的设定
    不匹配（同 ADR-0012 已判定的横截面退化问题）。日内文献只证实现象存在，未给出公认
    窗口值。**决定：像 1.2 的 7D 一样，用真实数据网格测出窗口，不抄外部数字**——待做。
  - **波动率基准暂不建，推迟**：字面定义（score=波动率水平）没有方向，测不出与有符号
    标签的相关性；时序适配的替代是杠杆效应（score=波动率*变化*，非水平）但**未在 crypto
    上验证过**，且业界另一条主流做法（BAB/低波动异象）是横截面排序法，同样在 N=2–3 下
    退化不可用。波动率风险溢价（VRP）路径需要期权隐含波动率数据（如 Deribit DVOL）——
    **当前数据管线只有 Binance 现货+USD-M 永续，无期权数据，此路不通**。此外 1.2 的
    vol-norm 标签已在标签层削平"变相押波动尺度"的优势，这条基准的边际防御价值存疑。
    **复活条件：接入期权数据，或有人验证杠杆效应在 crypto 上成立**。
  - **V1 最终基准集（三条）**：TSMOM + 反转（窗口待用真实数据网格法测定）+ 资金费率均值
    （8期=~64h，已有交易所结算周期的结构依据，无需改动）。
- **TSMOM/反转基准形态再调整（2026-07-02，讨论中，未写代码）**：三个币在窗口网格上的
  动量/反转符号**不一致**（BTC/SOL 短 lookback 反转显著、长 lookback 动量微弱；ETH 恰好
  相反——长 lookback 动量显著）。**改用"两个固定窗口点（短≈15min、长≈4h）的原始 trailing
  return 数值"当回归自变量**，不预先判定方向/符号；候选因子对这两个变量回归取残差，
  系数正负由数据自己决定每个币该算动量还是反转，不需要人工分币指定。已用户确认。
- **重大范围决定：暂时只做合约，不做现货（2026-07-02，用户明确拍板，见 memory
  `project_futures_only_no_spot`）**：交易、回测、因子评估**全部层面**只用 Binance
  USD-M 永续合约数据，现货排除（理由：现货手续费经济账算不过来）。本机合约数据完整
  （`/home/lewiski/crypto_data/external/binance/futures/<SYMBOL>/`：um_klines_1m +
  mark/premium/funding，BTC/ETH/SOL 三个币都有）。**影响审计**：
  - 今天的 TSMOM/反转窗口网格测试**已在合约上补测**，结论与现货一致（数字几乎相同，
    详见下方留档数字），不受影响。
  - **1.2 的真实数据校验（label std=1.0035）、σ̂ 估计量赛马（simple std vs EWMA）、
    alpha/beta 分解图，当时全部用的是现货**——函数本身不认产品类型（喂什么面板都能跑，
    不需要改代码），但这些数字的经验结论**尚未在合约数据上复核**，是下一步的待办。
  - ADR-0004 现货和合约都列为候选执行场地，未排除现货——这次决定进一步收窄为合约专用，
    暂定为临时决定，不一定永久，若成为长期决定应补一条 ADR 或修订 ADR-0004。
- **①合约复核完成**：1.2 的 std≈1 校验（合约 0.9832 vs 现货 1.0035）、σ̂ 赛马
  （simple/EWMA 相关 0.9647 vs 0.965）在合约数据上结论一致，7D/simple std 不受产品切换影响。

迭代 1.3 完成（2026-07-02，TDD，121 tests 全绿，**未 commit**）——`evaluation/base_model.py`：
- **窗口最终确定（split-sample 验证，非网格最大值）**：短=**2min**、长=**4h**，BTC/ETH/SOL
  USD-M 合约上拆半（前 1.25 年/后 1.25 年）复现,两半 NW 均 >2。之前口头定的 15min/4h 被
  用户追问后证伪（15min 对 ETH 两半均不到 2）；1min 因买卖价差反弹噪声风险未采用，2min 是
  三币两半都稳的最短点。
- **动量/反转不再是两个预判方向的独立基准，合并成一个 trailing-return 家族**：
  `base_factor_scores(data)` 只出原始数值（不取符号），方向留给 `incremental_significance`
  的回归系数决定——BTC/SOL 在短窗口自然拟合出负载荷（反转），ETH 在长窗口自然拟合出正载荷
  （动量），不需要人工分币判定。真实数据依据：三币窗口网格上动量/反转的符号本就不一致
  （BTC/SOL 短端反转显著、长端弱；ETH 短端弱、长端动量显著），验证过合约与现货结论一致。
- **资金费率基准：测过、放弃**。简单均值（1–21 期，8h–168h）+ 三种非线性构造（符号/z-score/
  极端分位）在三币三 horizon 上全部测过，最高才 NW≈1.83（ETH 极端事件版），未过显著性门槛，
  放弃写入 V1。复活条件：横截面构造，或更丰富的持仓/清算数据。
- **波动率基准：维持推迟**（1.3 讨论初期已判，见上文范围收窄记录）。
- **`incremental_significance(candidate_score, label, data, lag)`**：候选与基准都用同一套
  `sign(score) × label` 因子收益流构造（`_factor_return_stream`），FWL 定理提取截距做
  NW 显著性检验（不能直接对"带截距回归"的残差测均值——那样恒为零，是本次开发中修的第一个
  真 bug）。**第二个真 bug**：百万行真实数据上，完全克隆的候选因子系数精确拟合成 1.0/0/0，
  但 `lstsq` 舍入误差在残差里留下 ~1e-16 量级噪声，NW 把这噪声放大成虚假的 |t|=3.6——加了
  相对方差护栏（残差方差 < 候选流方差的 1e-8 倍 → 直接判 NaN）修正。真实数据端到端验证
  （ETH 1h horizon）：完全克隆→NaN，纯随机偏置信号→NW 1.06（弱），真实独立信号→NW 69.28
  （强烈存活）——三种情况判决正确。
- 数据源：全部合约（USD-M futures），遵守"暂时不做现货"决定。

**V1 horizon 带下扩：15min–4h → 1min–4h（2026-07-02，用户拍板）**：
- 补测 1min/5min horizon（此前只测过 15min/1h/4h）,发现短窗口(2min)反转效应在
  **5min horizon 上最强、三币两半都稳健**——普遍强于 15min（如 ETH 从 -2.53/-2.82 升到
  -3.55/-5.83）。若 V1 从 15min 起步,等于把已知最强的 horizon 排除在挖掘范围外。
  1min horizon 本身偏弱不稳（ETH 两半 -1.02/-4.63,不一致,疑似 forward 标签在 1 分钟尺度
  被买卖价差反弹污染）,但用户决定连同 1min 一起下扩,个体候选因子在 1min 上仍要过同样的
  NW/split-sample 门槛，不因为在带内就免检。
- 长窗口(4h,ETH 动量)在 1min/5min 上测不出效应（尺度失配，4h 趋势预测不了下一分钟）——
  长端 15min–4h 结论不受影响。
- 已改：ADR-0014 护栏①、PLAN.md V1/V2 分轨说明。1.3 的 base_model.py **不受影响**——
  `SHORT_WINDOW=2min`/`LONG_WINDOW=4h` 是输入回看窗口，和 horizon 是两个独立的轴
  （见对话记录：用户曾问"2min/4h是输入窗口还是horizon"，已澄清）。
- **下一步**：~~1.4（IC 衰减曲线）~~ → 已被 ADR-0016 重排为 **1.4.0–1.4.10 记分卡
  计算层专节**（PLAN 有独立小节,逐子任务列了已知的坑）,见下方 2026-07-03 晚记录。

**SOL 极端反转探索性研究（2026-07-02，纯分析，未写代码，未改 base_model.py）**：
用 1.3 的短窗口(2min trailing return)在 SOL 合约上叠加事件化(仅在幅度超过滚动 30D
99.9% 分位时出手，防泄漏用 trailing 分位而非全样本分位——过程中发现并修正了一次全样本
分位造成的前视泄漏)，15min horizon，反转方向：
- **初步结果看着不错**：毛利 +17.7bp/笔（盖过 9bp 手续费墙），NW 达 3.05，按月拆
  27/30 月均笔为正，月度 ICIR 0.87——是这整轮探索里唯一经得住多层验证的候选信号形态。
- **但深入压力测试后判定当前不可用**：①10 倍杠杆下最差单笔(-19.21%)会直接爆仓，且五笔
  最差交易挤在同一次崩盘的 30 分钟内（高度相关，非独立尾部风险）；②波动率止盈止损**让
  情况变差**（反转策略的固有特性：利润常需先经历逆向波动才展开，止损在反转发生前就把
  仓位震出局）；③按 30 分钟去重砍掉扎堆信号后，毛利从 17.7bp 崩到 2.2bp——说明相当一部分
  表观利润本就来自和尾部风险绑定的同一批崩盘期交易，去风险和保利润不可兼得；④用"单笔最多
  亏 2% 本金"倒推仓位，扣实际费用后月均收益为**负**（-0.06%）。
- **结论**：这个具体信号在统计层面真实（Research Gate 会通过），但扣风险扣成本后站不住
  （Trading Gate/迭代4 会拒绝）——是"统计显著≠能交易"这条原则的一次完整实测案例，值得
  作为反面教材保留，不代表短窗口反转基准本身没用（它仍然是合格的 1.3 参照物，见上文）。
- 未触发任何代码改动：`base_model.py` 的角色是给候选因子当基准，不是自己被当成候选因子
  去优化止损/仓位——这次探索是"如果有人把它直接当因子用会怎样"的压力测试，结果支持
  现有设计（基准就该只是基准）。

**迭代 1.4 设计已定案（2026-07-03，用户拍板，尚未写代码——明天开写）**：

- **horizon 网格（用户指定，9 点）**：`1min, 5min, 10min, 15min, 30min, 45min, 1h, 2h, 4h`。
  短端加密覆盖反转效应密集区（1.3 实测 5min/15min 最强），长端稀疏覆盖动量类效应
  （ETH 在 1h/2h/4h 上的窗口）。这组值要写成 `evaluation/metrics.py` 里的常量
  `V1_HORIZON_GRID`（命名待写代码时确认），版本化、不可被挖掘循环搜索。
- **`_decay_profile` 函数设计**（PLAN 1.4 原定位置 `evaluation/metrics.py`）：
  - 签名大致为 `_decay_profile(data, scores, horizons=V1_HORIZON_GRID, price_column="close", execution_lag_bars=1) -> list[DecayPoint]`；
  - `DecayPoint` 是个 frozen dataclass：`horizon: pd.Timedelta, ic: float, nw_tstat: float`；
  - 对网格里每个 horizon：调 1.2 的 `_vol_norm_returns(data, horizon, ...)` 算标签，和
    `scores` 对齐算 `ic = corr(scores, label)`；NW 显著性走 `factor.py` 现有
    `_nw_ic_tstat` 同款口径（`(score-mean)*(label-mean)` 贡献流,不是 `base_model.py`
    的 `sign(score)*label` 因子收益流——**这两种 NW 口径不同,decay profile 测的是
    IC 本身的显著性,不是方向性赌注的显著性**,注意别混用）；lag 用
    `_bars_per_horizon(data.index, horizon)`。
  - 边界：数据不足（对齐后 <2 行）→ 该 horizon 返回 `(NaN, NaN)`，不报错，不中断其余
    horizon 的计算。
  - **不做 walk-forward 接线**（和 1.2/1.3 一样，评估流程接线统一在 1.5）。
- **TDD 计划**（今天写到一半，已回退保证仓库干净——`tests/test_metrics.py` 现在
  是 121 tests 全绿的干净状态，明天从这里继续）：
  1. `V1_HORIZON_GRID` 常量值校验；
  2. `_decay_profile` 返回的点数、顺序、horizon 值和输入网格一致；
  3. 合成数据验证：分数按某个 horizon 的标签构造出强相关，`_decay_profile` 应在
     **匹配的 horizon 上报出高 IC**，其余 horizon 上较低——验证"读出来的衰减曲线
     形状是对的"，不是空转；
  4. NW 的 lag 确实随 horizon 变化（用 `_bars_per_horizon`），不是写死常量；
  5. 数据不足时该 horizon 返回 NaN 不报错，不影响其余 horizon；
  6. 不传 `horizons` 参数时，默认吃 `V1_HORIZON_GRID`。
- **明天开工顺序**：先写这批测试（红），再写 `_decay_profile` 实现（绿），跑真实合约
  数据验证（BTC/ETH/SOL 上跑一次 3.1.3 的两个基准 score，看衰减曲线形状是否符合
  已知规律——短端反转 15min/5min 峰值、ETH 长端动量 1h 附近峰值——作为端到端合理性检查，
  不是新增结论，是复核 1.4 实现和已知手工测试结果一致）。

**ADR-0015 评估范式重定标（2026-07-03，用户拍板，文档已改、代码未动）**：

起因：CLV 因子探索（用户提出的 Close Location Value，bar 内收盘位置）。先按现状管线测了
bar 级全样本 IC+NW（raw CLV 三币全负 IC、1min–15min \|t\| 2–6.5、4h 衰减到不显著；delta/
reversal 变体弱于 raw，无增量），后又换 vol-norm 标签复测（数字几乎不变——比值型因子对
vol-norm 不敏感）。用户追问"数据量越大 NW 越大，这东西怎么区分因子"，引发全天方法论审查，
每一步都做了 WebSearch 验证（不凭训练记忆），最终推翻现状评估口径：

- **核心结论**：单标时序因子评估存在两条正统——学术推断传统（预测性回归斜率 + HAC/NW，
  全样本）和交易评估传统（sign 策略收益流 + 一致性 + 多重检验修正，STW 1999 / CFM 两世纪
  趋势 / MOP 2012 / PSR-DSR / 机构 OOS 清单）。前者的判读惯例（t>2/3）在 T≈几百的月频/日频
  regime 校准，**不能平移到 n≈130 万分钟 bar**（NW 修正后有效样本仍 10⁴–10⁵，任何结构性
  非零相关都显著，t 只剩"不显著=可信死刑"单向信息）。佐证：GHLZ 2018 日内动量拿着高频数据
  仍按"一天一观测"检验；从业者记分牌（WorldQuant Fitness、CTA 清单）无 t-stat 无 IC。
- **新口径（ADR-0015）**：核心=Factor Return Stream 毛 Sharpe（记分牌）+ 跨币×跨窗口符号
  一致性（真假，验证宇宙=本机 35 个合约币、分流动性层，交易宇宙仍 BTC/ETH/SOL）+
  incremental significance（对 base model，构造不变）。显著性=日级聚合流（UTC 日求和 X_d，
  ~900 观测，点估计精确保持、日内自相关吸收进块方差）的普通 t=日频 Sharpe 检验，**只当
  杀手锏**（|t|>3 仅否决权，过线≠好），最终须算在 walk-forward OOS 流上（in-sample t 不作数）；
  升级路径 t→PSR（厚尾）→DSR（迭代 2 Trial Registry）。IC/rank IC 降为诊断（专管"越极端
  越准"的幅度排序问题，事件化前提/2.5 分桶单调性）。
- **NW 处置**：bar 级 NW（`_nw_ic_tstat` 及 lag=`_bars_per_horizon` 口径）**冻结不删**——
  它是学术传统的正确实现，错在 regime 不在血统。`_nw_tstat` 原语保留。**若日后要用 NW 的
  迁移规范已记进 ADR-0015 §Decision 5**：只作用于日级序列、lag_days 默认 1 但须先画 X_d 的
  ACF 实证（crypto 24/7 无收盘、"日"边界无独立性依据）、多币同日合进一个块（corr 0.82，
  symbol-day 分块会虚报 n 3 倍）、`incremental_significance` 的残差流同病同药（1.5 接线时做）。
- **文档已改**：ADR-0015 新建；PLAN 0.3 blockquote 加修正注 + 1.4/1.5/2.2 重定标；设计文档
  §3.5 指标表重写 + overlapping-returns caveat 更新；CONTEXT.md 受控语言更新（Factor Return
  Stream 升核心对象、IC Stability→Sign Consistency、Incremental IC→Incremental Significance、
  Decay Profile y 轴改 stream Sharpe、Research Gate/Factor Evaluation Report 谓词集重写）。
- **代码未动（下一批实现，按 TDD）**：①`_decay_profile`（1.4）按新 y 轴实现；②日级分块
  杀手锏（`_daily_block_tstat` 类原语，测试清单已在会话中列出：点估计不变性/iid 等价/自相关
  收缩/tz 日边界/缺口日/多币合块）；③`mining/loop.py` 阈值 2.0→3.0、`"signal"`→
  `"passes-noise-screen"`；④CLV 按新口径重验（bar 级"显著"结论全部待复核；方向一致性与
  4h 死刑结论仍立）。
- **CLV 探索现状**：脚本在 `$CLAUDE_JOB_DIR/tmp/`（会话临时区，未入库）；三步验证只完成
  vol-norm 复测，split-sample 与 incremental_significance 未做——等新评估口径落地后按新
  标准重跑，不在旧口径上继续。
- **V1 挖掘范围收紧为纯单标时序（2026-07-03，用户拍板）**：V1 候选因子只允许单标
  时序构造——因子只读**自己币**的历史数据、只在自己时间轴上找规律。排除：跨币排序/
  相对强弱等截面构造（ADR-0012 原判），**以及跨币特征输入（lead-lag 类,如用 BTC 走势
  当 ETH 因子输入）——后者需用户显式解锁才能开**。不受影响：35 币验证宇宙（单标评估
  的跨币复制实验,非截面构造）；截面发现 backlog 维持 deferred。
- **V1/V2 产物命名（2026-07-03，用户拍板，已入 CONTEXT.md）**：V1 挖出的 edge 叫
  **Timing Alpha**（择时 alpha：total-return 预测、单腿、带市场暴露、不得宣称中性）；
  V2 的叫 **Residual Alpha**（残差/idio alpha：市场残差预测、须带对冲腿才能兑现）。
  依据：业界(Two Sigma/Citadel)对 signal/alpha 混叫、不靠命名区分——区分靠预测标签
  （total vs residual/idio）+ 组合层对冲 + PnL 归因（factor vs idio PnL，多经理平台
  语境）；Grinold-Kahn 教科书 alpha 正式定义=expected residual return。"alpha" 永远是
  相对基准的（factor zoo：昨天的 alpha 是今天的 beta），项目内禁用裸 "alpha"，必须带
  轨道限定。连带修掉 CONTEXT.md 两处 ADR-0014 之前的陈旧（Effective Factor 写死
  market-neutral、Forward Return 写死 market residual）。同日早前设计文档 §1 流程图/
  §3.4 base set 表/§3.6 pass conditions 的陈旧也已修（用户发现流程图与计划不对应）。

**ADR-0016 Factor Scorecard 定案（2026-07-03 晚，用户全程逼问出来的，文档已改、代码未动）**：

起因：用户连续追问"统计层到底该拿什么评估单标时序因子——按业界实际,不按我们文档写了什么"。
逐项审计（推理+WebSearch 双验证,权威锚 = AFML Ch.14 Backtest Statistics / mlfinlab 实现,
交叉 MOP/Lempérière 复制传统 + HM/Cumby-Modest/Pesaran-Timmermann 方向检验文献）：

- **13 行记分卡定案**（全部定义在 sign×vol-norm 流上,各行带血统标签 A 多血统业界/
  B 单一血统(AFML)/C 学术/D 自造）：Sharpe、日级 t（日级聚合是 D 级自造校准,形式是 A）、
  PSR/DSR、赌注数、每笔毛 edge(bp)、分期表+符号计数、基准相关+增量 alpha、条件方向命中
  （HM/PT 形态）、回撤/Calmar/TuW、偏峰、HHI（正负分开）、换手/半衰期/滞后敏感性、
  市场暴露三件套（对同币 buy-and-hold 相关 + 控市场 alpha + ratio of longs）+ 衰减曲线。
- **审计抓出的错误与修正**：①**IC/Rank IC 是横截面词汇渗漏**,单标时序无出处（学术对应物
  是预测回归斜率/OOS R²,Campbell-Thompson 血统,已随 bar 级 NW 冻结）——项目内禁用,
  幸存诊断改名"时序预测相关性"[D]；②**朴素 hit rate 在漂移市场有偏**（常多因子牛市白得
  高胜率）,正规形态=涨跌分开的条件命中+HM/PT 列联检验,且文献明示序列相关下 oversize→
  须日级化；③**真漏项:每笔毛 edge**（费用墙算术的分子,SOL 案例手工算过的 17.7bp 就是它）;
  ④**真漏项:市场暴露**（AFML 白纸黑字 correlation to underlying——V1 方向性因子可能退化成
  变相常多,趋势基准 spanning 抓不住,必须显式测）。
- **两条实现红线**：市场暴露基准=**同币** buy-and-hold（ETH 对 BTC 回归=跨币输入,V2 地盘）;
  分桶分位数必须 trailing（全样本分位=前视,SOL 案例踩过）。
- **方法论决定（用户拍板）**：**先实现全部指标计算,角色分配后置**——每次评估吐完整记分卡,
  谁否决/谁排名/谁诊断维持 ADR-0015 工作假设,等 1.5 真实数据记分卡出来再最终定案。
- **1.4 重排（用户两轮矫正后定形）**：初版塞成"1.4a 全指标+1.4b 衰减曲线"两行,被用户
  打回（"每行指标都可能有大量问题,塞一个小任务是滥竽充数"——历史证据支持:1.2 一个标签
  函数=一个迭代,1.3 一个基准=一个迭代）。终版 = PLAN 独立专节 **1.4.0–1.4.10**,按共享
  机器分族,每个子任务列了已知的坑、独立 TDD/commit/验收:0 流构造器提升(补直属测试)、
  1 日级聚合+headline Sharpe/t(最重,tz/缺口日/多币合块/X_d ACF 实证;loop.py 落地件在此)、
  2 赌注核算族("一笔"的定义)、3 分布族+PSR、4 路径族(vol-norm 流 DD 单位=σ 的口径问题)+
  HHI、5 条件方向命中(HM/PT)、6 市场暴露三件套、7 分期表、8 滞后敏感性、9 衰减曲线、
  10 真实数据整卡验收(退出闸门)。**headline Sharpe 定义在日级聚合流上**(bar 级重叠采样
  std 标度不干净;日级=业界日频 PnL Sharpe,√365)——本日补钉规格,已写进 ADR-0016 第 1/2 行。
- **文档已改**：新 ADR-0016;ADR-0015 加 Amended-by;设计文档 §3.5 指标表整体换成记分卡
  （§1 流程图/§3.6/§3.7/§6 连带修）;CONTEXT.md 新增 Factor Scorecard + Time-series
  Predictive Correlation 词条、修 Decay Profile/Factor Evaluation Report/Crypto Evaluation
  Core/Market Neutralization/Sign Consistency/Candidate Horizon 的 IC 措辞、
  **修 Walk-forward 词条陈旧**（还写着三段式 30d validation,1.1 已砍）;PLAN 1.4 专节/1.5/
  2.2/2.3 重写、迭代 1 标题去 IC 化、2.5 blockquote 加更新注、4.5 的 ADR 编号冲突修掉。
- **今天口头澄清但不改设计的**：挖掘全流程六步走查（LLM 只写因子/修代码/读判决,判决全在
  代码谓词,机制判断留 RC 人工门——LLM 可当分析员做红队/文献对拍/简报,不当法官）;Sharpe
  的角色=尺子不是闸门（无过线阈值是决定,不是遗漏）;RC 送审排序按 Sharpe 是推论不是已定规范。

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
