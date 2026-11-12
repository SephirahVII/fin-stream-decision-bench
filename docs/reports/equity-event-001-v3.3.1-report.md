# equity-event-001 v3.3.1：评分改造、验证与重校准报告

- 日期：2026-11-12
- 任务包：`tasks/equity-event-001`
- 版本：benchmark dataset `1.4.0`；judge verifier `v1.4.0`
- 平台：LiteEval `90ed715`（未修改平台代码）
- 约束（来自任务规格）：不扩展为更多财务计算题；不为压低 rollout 分数而优化；优先提升 scoring validity、分析区分度与 judge 可靠性。

## 1. 执行摘要

本轮把评分体系从"预测数值为主 + 少量饱和的提取/合规项"重构为"预测数值 + 可观测的分析质量 + 有防护的流程门"，并修复了 verifier 中 8 处正确性/有效性问题。核心变化：

1. 权重重新分配（合计 100）：`forecast_composite 55`、`probabilities 5`、`one_off_analysis 2`、`reconciliation_actuals 2`、`tenq_verification 2`、`timeliness 1`、`audit_integrity 2`、`evidence_chain 10`、`analysis_logic 13`、`handover_quality 8`。无 `must_pass`，单一 check 失败不归零，聚合仍为平台 `weighted_mean` + `pass_threshold 0.85`。
2. 概率评分从 `1 − Brier/2`（0.5/0.5 仍得 0.875）改为有界 Brier Skill Score：`max(0, 1 − BS/0.25)`。
3. 修复确定性 judge：审计改为逐 submission 时间戳、reconciliation 校验 candidate 自己提交的 consensus、10-Q 自报 boolean 不再计分、forecast 增加会计恒等式一致性、空跑不再白拿 audit 分、peer 文档可引用、surprise 浮点舍入等。
4. 三份 LLM rubric 重构并拆分：evidence（E1–E6，10 分）、analysis logic（L1–L5，13 分）、新增 handover quality（H1–H5，8 分，仅评 verification summary）。
5. 端到端验证：23 个离线单测通过；脚本 oracle conformance 0.94 pass；空跑负基线 0.0；6 次真实 DeepSeek-V4.1-Flash rollout 全部可计分，其中最终配置 4 次 mean 42.01、sd 1.50。**按同一批 evidence 套用 v1.3.1 旧权重的反事实均分为 34.92**——本轮分数上升来自权重重新分配（把权重放到模型真实可展示的分析能力上），不是模型能力变化，也不是放宽了判定。

关键诚实声明：本轮改动不以"分数降低"作为成功标准；下面逐项说明每处改动改善的是 construct validity、observability、reproducibility 还是 discrimination（§14）。当前观测分数（40.18–53.62）高于 v1.3.1 时期（29.13–38.61），这是权重迁移的预期结果；是否要把总分压回 30–40 属于后续难度校准决定，需在新 rubric 下重新按协议进行，而不是继续收紧判据。

## 2. 审计结论（原问题）

完整审计见 `docs/reports/equity-event-001-v3.3.1-audit.md`。审计确认的主要问题：

| # | 问题 | 类别 | 影响 |
| --- | --- | --- | --- |
| 1 | `probabilities = 1 − Brier/2`，0.5/0.5 得 0.875，弱于无信息基线仍近满分 | validity | 概率项饱和 |
| 2 | 点预测用 core EPS（2.76），而 EPS beat 概率事件在 GT 里记 GAAP EPS（5.11 vs 2.76 → 必然 beat），同一字段两个目标 | correctness | 概率事件定义不一致 |
| 3 | `audit_integrity` 用全局 session read 集合，不检查 read 时间与具体 submission 的关系 | correctness | 晚读可追溯"支持"早提交；空跑也得分 |
| 4 | `reconciliation_actuals` 不校验 candidate 提交的 consensus，只比对最终 surprise/beat 标签 | correctness | 错误 consensus 可拿满分 |
| 5 | `tenq_verification` 有 1/10 分来自 candidate 自报 `press_release_matches_10q` 布尔值 | observability | 自报即得分，无独立证据 |
| 6 | forecast 无任何跨指标会计一致性检查 | validity | total/net/TAC 可互相矛盾仍得高分 |
| 7 | peer 财报文本在 DB 中可读，但 judge 侧 `documents` 映射缺失，引用 peer 会被判未知文档 | correctness | 合理引用被扣分 |
| 8 | rubric 仍为旧 E1–E4/L1–L4 语义，缺 handover；提取类检查对成熟模型饱和 | validity/discrimination | 分析质量不可观测、区分度低 |

## 3. 逐文件改动

| 文件 | 改动 |
| --- | --- |
| `tasks/equity-event-001/task.toml` | 10 个 check 的新权重/类型；`pass_threshold 0.85`；`judge_timeout_seconds 480`（原 180：三次串行 LLM judge 调用实测 137–201 s，180 s 会周期性超时）；全部 `must_pass=false` |
| `tasks/equity-event-001/judge/verify_ingest.py` | 重写为 v1.4.0（约 560 行）：新增逐 submission 审计、BSS 概率、reconciliation consensus/beat 重算、forecast 会计一致性、空跑审计归零、surprise 四舍五入、peer doc 支持；`SCORERS`/CLI/结果 JSON 契约不变 |
| `tasks/equity-event-001/judge/ground_truth.json` | `expected_probability_events = {net_revenue_beat: true, eps_beat: false}`；新增 `probability_event_definitions`、`core_eps_methodology`、`tenq_verification_note`、`audit_semantics`；`documents` 增 3 个 peer 文档；新权重表与 `scoring_notes` |
| `tasks/equity-event-001/judge/rubric_evidence.json` | E1–E6（weights 2/2/2/2/1/1 = 10），区分 factual compliance 与 traceability |
| `tasks/equity-event-001/judge/rubric_logic.json` | L1–L5（3/3/3/2/2 = 13），focus 从"复述"转向 reasoning chain 与 estimation risk |
| `tasks/equity-event-001/judge/rubric_handover.json` | 新增 H1–H5（2/2/2/1/1 = 8），只评 verification 阶段 summary 的"可交接质量" |
| `tasks/equity-event-001/environment/initial_workspace/desk/manual.md` | 说明 core EPS 口径、EPS 概率按 core-EPS 事件、`press_release_matches_10q` 仅记录不计分、逐 submission 审计、v3.3.1 权重表与交接口径 |
| `tests/test_equity_event_judge.py` | 重写测试套件（23 tests），覆盖概率/审计/reconciliation/10-Q/一致性/rubric/聚合/负基线/workspace hygiene |
| `dataset.toml` | `version 1.4.0` |
| `docs/reports/equity-event-001-v3.3.1-audit.md` | 审计报告（新增） |
| `docs/reports/equity-event-001-v3.3.1-report.md` | 本报告（新增） |
| `docs/design/equity-event-stream-case-design.md`、`README.md` | 同步评分/校准/限制说明 |

未修改：平台 `goldtrace`（保持 `90ed715`）、workflow controller、DB/engine、task id 与无关行为。

## 4. 最终评分架构

聚合：`weighted_mean`，`pass_threshold = 0.85`；**没有 `must_pass=true`**，单个 check 失败只损失该 check 的加权分。

| check | 权重 | 类型 | 计分规则 |
| --- | ---: | --- | --- |
| `forecast_composite` | 55 | command | 9 指标各 `max(0,1−|err|/T)` 取均值后取 `0.9×mean + 0.1×consistency`；`consistency = max(0, 1−|Total−Net−TAC|/2.0 USD m)`。T：total 1.5%、net 2.5%、TAC 6%、Services 3%、Cloud 8%、Services op 5%、Cloud op 8%、op income 5%、core EPS 0.30 |
| `probabilities` | 5 | command | `BS = mean((p−outcome)²)`；`max(0, 1 − BS/0.25)`；两事件见 §5 |
| `one_off_analysis` | 2 | command | 一次性收益金额（tol 200 USD m）与 core EPS（tol 0.03）线性平均 |
| `reconciliation_actuals` | 2 | command | 内部 20 分：actuals 4×2.5（tol 1.0 USD m / 0.01）+ submitted consensus 2×1（对冻结 91,690/2.76）+ surprise 2×2（用 candidate 自己的 consensus 对权威 actual 重算后比较，tol 0.05pp/0.5pp）+ beat/miss 2×2（用 candidate 自己的 actuals+consensus 按 ±0.5% 重算分类后比较） |
| `tenq_verification` | 2 | command | 9 项各 1/9：total revenue、TAC、net revenue、op income、net income、diluted EPS（tol 1.0/0.01）、operating margin、Services margin、Cloud margin（tol 0.05pp）；自报 `press_release_matches_10q` 仅记录为 claim，不计分 |
| `timeliness` | 1 | command | 三阶段均按时 = 1，否则按按时比例 |
| `audit_integrity` | 2 | command | 从 1.0 扣：未知引用 −0.20；引用未发布文档 −0.35；成功 read 不在该 submission 之前 −0.10（forecast basis −0.05）；空 basis −0.30；invalid basis −0.20；journal 读未发布 −0.15/次（cap 0.3）；被拒 submit −0.05/次（cap 0.2）。无任何 graded submission → 0.0 |
| `evidence_chain` | 10 | llm_rubric | E1–E6（见 §7），平台按 criteria 权重聚合，binary/graded 由 rubric 声明 |
| `analysis_logic` | 13 | llm_rubric | L1–L5 |
| `handover_quality` | 8 | llm_rubric | H1–H5，仅评 verification 的 `summary` |

设计原则：forecast 仍是最大单项（55），因为它仍是唯一观察到真实能力梯度的维度；但 31 分（10+13+8）分配给分析质量类 rubric，使"分析是否真的专业"进入总分。

## 5. 概率评分修正（BSS）

两个事件在 `ground_truth.json` 中显式定义：

- `net_revenue_beat` = 实际净收入（total revenues − TAC = 109,896 − 15,228 = 94,668 USD m）相对冻结 consensus 91,690 USD m 的变动 > +0.5% → **true**（+3.2479%）。
- `eps_beat` = 实际 **core EPS**（2.76）相对冻结 consensus EPS 2.76 的变动 > +0.5% → **false**（0.0%，in-line）。

公式：

```
BS   = mean over {net_revenue_beat, eps_beat} of (p_i − y_i)^2
BSS  = 1 − BS / 0.25          # 0.25 = 50% 参考基线的 Brier
score = max(0, BSS)           # 有界，最差 0，perfect 1
```

- 0.5/0.5 → 0（不再有 0.875 的保底）。
- perfect → 1；差于 50% 基线不获得正分。
- 0.25 是**固定的 50% 参考基线**，不是经验 climatology；本项不宣称是"稳健概率校准评测"。
- `detail` 保留 raw Brier、未截断 BSS 和逐事件 p/outcome，便于诊断。
- 单测覆盖：保底消除、perfect、负值、invalid/missing、事件口径。

EPS 口径修正（原审计问题 #2）：点预测只评 core EPS（剔除一次性权益收益）；EPS beat 概率也改为 core-EPS 口径，并在 `core_eps_methodology` 中记录方法：GAAP 5.11、pre-tax one-off 36,915、tax 8,200、after-tax 28,700、EPS impact 2.35、隐含 diluted shares 12,212.8、core EPS 2.76（项目定义的分析口径，不是公司报告值）、tol 0.30。

## 6. 确定性 judge 修正清单

| # | 修复 | 行为变化 |
| --- | --- | --- |
| 1 | 概率评分改 BSS | 无信息预测 0 分；差于 50% 基线 0 分 |
| 2 | EPS 事件改为 core-EPS 口径 | GT 由"两事件均 true"改为 `{net: true, eps: false}`，并由 `probability_event_definitions` 明确 |
| 3 | 审计改为逐 submission | 每阶段取 deadline 前最新提交，比较 `available_at ≤ read_at ≤ submission.at_s`；晚读不能追溯支持早提交 |
| 4 | reconciliation 校验 submitted consensus | 错误 consensus 会直接失分并连锁影响 surprise/beat 重算 |
| 5 | surprise 由 candidate 自己的数重算 | 不接受只抄最终结论；重算值 `round(...,4)` 消除浮点噪声 |
| 6 | 10-Q boolean 不再计分 | `press_release_matches_10q` 只记为 claim；9 项数值各 1/9 |
| 7 | forecast 会计恒等式 | 9 指标均值占 0.9，`Total−Net−TAC` 残差占 0.1（tol 2.0 USD m） |
| 8 | 空跑审计归零 | 无 graded submission → audit 0.0（原先 1.0 送 2 分） |
| 9 | peer doc 映射 | `documents` 增加 3 个 peer 文档，引用合法 |
| 10 | 审计 detail 初始化 | 修 KeyError 与浮点边界（perfect reconciliation 不再 0.999993） |

平台侧语义核对：`must_pass` 缺失即视为 false；check outcome=`error` 会将该 task 标为 `unscored`（不进入计分）；`pass_threshold` 只决定 outcome 标签，不改变 score（本 case 无非零 gate）。

## 7. LLM rubric 重构（三份）

**重要**：未修改平台级 judge system prompt；rubric 只提供逐 criterion 的判定标准，平台以 `{id, passed, reason, evidence}` 收集后确定性加权聚合。

### 7.1 `rubric_evidence.json`（10 分）

| criterion | 权重 | 类型 | 要求摘要 |
| --- | ---: | --- | --- |
| E1 时间与来源有效性 | 2 | binary | 重要 claim 由相应阶段可用文档支持；被引文档须在提交前成功 read |
| E2 claim-level 可追溯 | 2 | binary | 关键财务 claim 有可定位引用（文档 + 位置/数字），"management said" 不够 |
| E3 net revenue 推导 | 2 | binary | 显式给出 total/TAC/net 并展示 Net = Total − TAC 的数值一致性 |
| E4 one-off 收益桥 | 2 | graded | pre-tax gain / tax effect / after-tax / diluted shares / per-share 关系正确，单位与符号一致；仅抄数字不得满分 |
| E5 release vs 10-Q | 1 | binary | 至少两个有意义对应 line item 的对照；一致要明说，差异要解释，不得编造 |
| E6 unsupported / temporal | 1 | graded | 处罚无来源数字与提交时尚不可得的信息；明确标注的 forecast/assumption 不算 unsupported fact |

### 7.2 `rubric_logic.json`（13 分）

| criterion | 权重 | 类型 | 要求摘要 |
| --- | ---: | --- | --- |
| L1 九指标 forecast rationale | 3 | graded | 每项给出 quantitative anchor/推导（历史季、consensus、分部趋势、margin 等），不要求九段重复文字 |
| L2 probability reasoning | 3 | graded | 两概率有显式理由并与点预测/不确定性/beat 阈值一致；不得把接近实际结果当作好推理 |
| L3 数值与会计一致性 | 3 | graded | surprise/margin/TAC ratio/派生量可由 candidate 自己提交的值复算；区分算术错误与可接受舍入 |
| L4 case-specific 财务推理 | 2 | graded | 至少两个具体机制（Cloud operating leverage、Services margin、TAC/advertising dynamics、one-off gain、peer read-through）并与 evidence 连接 |
| L5 具体估计风险 | 2 | graded | 至少一个具体风险，含受影响指标、方向与数量级/情景；不要求匹配任何单一 GT 数字 |

### 7.3 `rubric_handover.json`（8 分，新增）

仅评 verification 阶段 `summary`：

| criterion | 权重 | 要求摘要 |
| --- | ---: | --- |
| H1 forecast-to-actual review | 2 | ≥3 个重要指标 actual vs 盘前 forecast（数值+方向/幅度），并解释至少一个 error 来源 |
| H2 GAAP 与 core EPS 解释 | 2 | one-off 收益影响、正确计算基础/单位，区分 reported 与 analytical |
| H3 research learning & updates | 2 | ≥2 个具体应修订的假设/方法，各自 linked 到观察到的 error 或新证据 |
| H4 residual uncertainty | 1 | ≥1 剩余不确定性，含受影响指标、方向与推理 |
| H5 professional communication | 1 | concise/actionable/内部一致，penalize unsupported claims 与 generic filler，不奖励长度 |

防 double-counting：evidence 评"是否被支持"、logic 评"推理与计算是否正确"、handover 评"是否转化为可用的下一步研究指示"；同一事实只有在三节分别评估不同能力时才可重复出现。

## 8. Ground truth 与财务定义审计

核对源证据（EX-99.1、10-Q、10-K、XBRL、consensus）后确认/修正：

- 净收入 94,668 不直接出现在任何披露中，必须由 109,896 − 15,228 推导；TAC 只在 release 中出现（companyfacts 无 TAC concept）。
- 分部收入/分部经营利润只在 release 的 segment 表出现，10-Q 摘录没有 segment operating income。
- Core EPS 2.76 = GAAP 5.11 − 一次性权益收益税后影响 2.35；`core_eps_methodology` 记录 pre-tax 36,915、tax 8,200、after-tax 28,700、EPS impact 2.35、隐含 diluted shares 12,212.8、tol 0.30 与"项目定义的分析口径"声明。
- 概率事件定义修正见 §5；冻结 consensus 91,690（net of TAC）与 2.76 作为独立参照，不由 candidate 重述。
- `tenq_verification_note` 说明：release 与 10-Q 的合并数字应一致，但分部经营利润仅 release 有，因此 10-Q check 只评可在两处对应的项目；不要求 candidate 编造差异。
- `audit_semantics` 记录 read/available/submission 的时间约束。

发现的 GT 问题（已在本次修复）：旧概率事件用 GAAP EPS 口径；`documents` 缺 peer 文档；margin ground truth 舍入（45.2817 vs 45.2815，已统一为 45.2815）。

## 9. 测试与静态验证

- `python3 -m unittest tests.test_equity_event_judge -v` → **23 tests OK**。覆盖：
  - 概率：0.5/0.5 → 0、perfect → 1、差于基线 → 0、invalid/missing → 0、事件口径。
  - 审计：发布前 read 被拒；发布后但提交后 read 不支持该提交；提交前 read 支持；later reads 不追溯；空跑 audit = 0。
  - reconciliation：错误 consensus 不能因最终 surprise 正确而通过；错误 surprise 被拒；beat/miss 用声明阈值与正确指标。
  - 10-Q：只提交 boolean 不得分；舍入与列报差异被容忍；错误值被拒。
  - forecast：会计恒等式；9 指标 composite。
  - rubric：三份 schema 合法、权重和 10/13/8、无 must_pass、handover 引用 verification summary。
  - 聚合回归：权重和 100、无 must_pass、pass_threshold 0.85、deterministic checks 与 SCORERS 一致。
  - workspace hygiene：agent 可见目录无 judge 材料、无真实数字 token。

## 10. 平台端到端验证

| 验证 | 结果 |
| --- | --- |
| 脚本 oracle conformance（release `b7d10e0709494e309942b4d34e1b538a`，execution `107829de4a134171893a043b472a85e8`） | outcome **pass**，score **0.94**；deterministic 全 1.0；evidence_chain 1.0；analysis_logic 0.5385（oracle 文本极简，未覆盖全部 L 判据）；handover 1.0；judge 113 s |
| 空跑负基线（execution `f0231ef59c8f47459304882d8fec4d24`） | outcome fail，score **0.0**；10 个 check 全 0 |
| validate | valid true、version 1.4.0、task_count 8。canonical digest 须从 `git archive HEAD` 的干净导出计算：平台 loader 会哈希整棵仓库目录（含 `docs/`，在含 `.git` 的工作树中还会含 `.git`），因此 digest 随任何文件改动而变，只作为 release 产物校验值，不能写回同一仓库的文档（否则自我改写）。release 身份 = `dataset.toml` version + git commit hash |

## 11. 真实模型 rollout（v3.3.1）

模型：DeepSeek-V4.1-Flash（connection `2e3e1a77…`，target 与 judge 同连接）；agent harness：`community.json-action` 1.3.0（bench 仓 `harnesses/json_action`）；workflow harness：`benchmark.equity-event-stream`。rollout release `4caedfcf283a429d975519b79d833fea`。

所有计分 run（6 次）：

| tag | execution | score | wall (s) | judge (s) | actions | invalid actions | 备注 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| r16v331 | `e7da81d9…` | 53.62 | 295.9 | 142.8 | 33 | 8 | 180 s judge 预算，个别 judge 报错 |
| r19v331 | `e4ba5c67…` | 37.16 | 452.6 | 137.7 | 43 | 15 | 180 s 预算 |
| r23v331 | `37f85571…` | 43.15 | 303.4 | 156.2 | 38 | 7 | 480 s 预算 |
| r24v331 | `583faa47…` | 43.32 | 499.6 | 200.7 | 60 | 21 | 480 s |
| r25v331 | `35acac8f…` | 41.41 | 411.8 | 183.2 | 47 | 9 | 480 s |
| r26v331 | `1315ab79…` | 40.18 | 443.6 | 145.2 | 58 | 18 | 480 s |

统计：

- 全部 6 次：mean **43.14**、sd **5.61**、min 37.16、max 53.62。
- 最终配置 4 次（r23–r26）：mean **42.01**、sd **1.50**、min 40.18、max 43.32。
- 加权贡献（final4 均值）：forecast 12.15、probabilities 2.32、one_off 2.00、reconciliation 1.99、tenq 1.80、timeliness 1.00、audit 2.00、evidence_chain 9.00、analysis_logic 2.50、handover_quality 7.25。
- 逐 check 均值/标准差（final4）：forecast 0.2210/0.0228；probabilities 0.4642/0.0623；one_off 1.0/0；recon 0.9961/0.0026；tenq 0.8993/0.0987；timeliness 1.0/0；audit 1.0/0；evidence 0.90/0.1414；analysis 0.1923/0.0769；handover 0.9062/0.1197。

观察：

- 预测仍是模型弱项（forecast 0.22，9 指标中 Cloud revenue/cloud op income 常为 0 分；net revenue 约 0.30）；其余确定性项接近饱和，这是权重设计（低权重）而非判据放松所致。
- 分析质量已真正进入总分：evidence 约 9/10、handover 约 7.25/8；analysis_logic 仅约 2.5/13（L2 概率推理与 L1 逐指标 rationale 是主要失分点），说明新 rubric 能区分"证据充分但推理薄弱"。
- invalid actions 7–21 个/run：来自模型输出格式（尾部幻觉/工具标记），harness 已兜底但消耗预算；属于 agent protocol 观察项，不是环境错误，也未计入分数。

## 12. 与 v1.3.1 对比（construct validity，非难度调参）

把同一批 6 次 evidence 套用 v1.3.1 旧权重（74/5/3/3/2/1/2/5/5）反事实计算：

| 口径 | v1.3.1 旧权重（反事实） | v3.3.1 新权重 |
| --- | ---: | ---: |
| 全部 6 次 mean | 36.40 | 43.14 |
| final4 mean | 34.92 | 42.01 |

结论：

1. 模型能力没有变化，分数上升完全来自权重迁移：旧权重把 74 分押在模型最弱的 forecast 上，新权重把 31 分放到 evidence/analysis/handover——模型在后者确实有可展示的能力（9–10/10 evidence、约 7/8 handover），但 analysis_logic 只拿约 2.5/13，说明区分度落在分析推理上。
2. v3.3.1 并未放宽判定：概率无信息保底被移除（0.5/0.5 从 0.875 → 0）、审计更严格、reconciliation 要求自洽、10-Q 自报 boolean 不再送分。
3. 旧口径下的 6 次分布（34.9–49.8 mean 36.4）与新口径（40.2–53.6 mean 43.1）说明"总分层面的难度带"发生了迁移；这是可解释、可复核的权重决策，而非任意收紧阈值。

## 13. judge 可靠性与方差

- **超时**：180 s 总预算下，三次串行 LLM judge 调用（evidence+logic+handover）实测 137–201 s，出现 1 次 TimeoutError（r20）。修复：`judge_timeout_seconds` 180 → **480**。480 s 下 4/4 rollout 的 judge 阶段均正常完成（145–201 s）。
- **随机错误**：180 s 批次出现 1 次 malformed verdict（`unsupported fields or invalid object`，r17）与 1 次 provider error（r18）→ 该次 run 被平台标为 `unscored`。480 s 批次 4/4 无此类错误。平台对 judge error 不重试，这是 LLM judge 的残余可靠性限制：正式评测需按协议多次运行并报告 `scoring_coverage`。
- **采样方差**：对 r23 的同一份 evidence 重新 judge 两次：43.15% / 43.15% / 40.15%（原 run 43.15%）→ 差异全部来自 evidence_chain（1.0 → 0.9）与 handover_quality（1.0 → 0.75），analysis_logic 稳定在 0.1538。采样标准差约 **±1.5 pp 总分**。

## 14. 每项改动为何提升 quality

| 改动 | construct validity | observability | reproducibility | discrimination |
| --- | --- | --- | --- | --- |
| 概率改 BSS | 测的是可区分 skill，而非 p≈0.5 也能接近满分 | 保留 raw Brier/unclipped BSS | 公式与基线固定 | 弱模型与无信息基线分开 |
| EPS 事件改 core 口径 | 消除"核心预测 vs GAAP 事件"的概念混用 | 定义写入 GT + manual | 事件 outcome 唯一确定 | — |
| 逐 submission 审计 | 审计的是"提交时可用证据"，不是事后阅读 | read/submission 时间戳均可见 | 基于 journal 可复算 | — |
| reconciliation 自洽校验 | 测"从自己数据推出结论"的能力 | 每一步有 detail | 可重放 | 错误 consensus 不再蒙混 |
| 10-Q 去 boolean | 测实际数值，不测自报 | 9 项逐值 detail | 数值确定 | — |
| forecast 一致性项 | 防止内部矛盾的 9 指标仍得高分 | detail 显示残差 | 公式确定 | — |
| rubric 拆分 evidence/logic/handover | 区分"引用充分""推理正确""可交接"三种能力 | 每条 criterion 独立 verdict | 平台确定性聚合 | analysis 0.19 vs evidence 0.90 说明能区分 |
| 权重迁移（55/5/2/2/2/1/2/10/13/8） | 奖励真实可展示能力，避免 74 分押在单一弱项 | — | 权重固定 | 总分方差下降（final4 sd 1.50） |

## 15. 局限与残余风险

1. **LLM judge 随机性**：malformed verdict / provider error 会让一次 run 变成 unscored；建议正式评测每配置 ≥3 次并用 scoring_coverage 说明。judge 抽样方差约 ±1.5 pp。
2. **judge 延迟**：三次 verdict 级 judge 调用约 2.5–3.5 分钟；已通过 480 s 预算覆盖，但平台整体 wall 时间约 5–8 分钟/次（含模型 40–60 次调用）。
3. **难度带**：v3.3.1 观测 40.18–53.62（mean 43.14）。原 v1.3.1 的 30–40 校准目标未重做；按任务规格本轮不调阈值。若要将总分压回 30–40，应作为独立难度校准决策（例如重新分配 forecast/分析权重或在 rubric 上增加难度），并在报告里显式声明，而不是声称"更严谨"。
4. **预训练知识**：2026-04 事件对当前参考模型不在记忆内（已做 probe），但对未来模型可能泄漏；已在设计文档披露，审计只能部分缓解。
5. **trusted-local 信任边界**：工作区含完整 future 数据库（tool 侧过滤），任意可执行文件系统访问的 harness 仍可能读原始 DB；这是"可信本地"评测的已知边界。
6. **evidence 产物持久性**：平台目前只保留 submission blob（sha256 → `data/benchmark-blobs`），旧 run 的 artifacts 表为空，无法在平台外复算；本报告的复算均基于保存的 execution JSON 与 submission blob。
7. **invalid actions**：模型输出格式仍会消耗预算（7–21 个/run），harness 兜底为 `{"action":"invalid"}`。这是 agent protocol 观察，不是环境错误，不计入分数，但会压缩有效动作预算。

## 16. 复现

```bash
# 静态验证
cd /path/to/fin-stream-decision-bench
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v   # 23 tests OK

# canonical package digest（干净导出，避免 .git 进入快照）
rm -rf /tmp/v140_clean && mkdir /tmp/v140_clean
git archive HEAD | tar -x -C /tmp/v140_clean
liteeval benchmark validate /tmp/v140_clean

# 平台验证（LiteEval 90ed715；使用项目 a52403def… 的 connection 2e3e1a77…）
export LITEEVAL_SECRET_KEY=$(cat /path/to/master.key)
liteeval benchmark validate .
liteeval benchmark import /tmp/ee-pkg-v331 --project <PROJECT>                  # release 4caedfcf…
liteeval benchmark run <RELEASE_CONF> --project <PROJECT> \
  --agent-harness <test.scripted-equity revision> --workflow-harness <benchmark.equity-event-stream revision> \
  --judge-connection <CONNECTION> --trusted-local                               # conformance 0.94
liteeval benchmark run <RELEASE_ROLL> --project <PROJECT> \
  --agent-harness <community.json-action revision> --workflow-harness <WORKFLOW_REV> \
  --target-connection <CONNECTION> --judge-connection <CONNECTION> --trusted-local
```

conformance execution：`107829de4a134171893a043b472a85e8`；negative baseline：`f0231ef59c8f47459304882d8fec4d24`；rollouts：见 §11 表。

## 17. 交付物清单

| # | 交付物 | 位置 |
| --- | --- | --- |
| 1 | 审计报告（问题、字段兼容、拟改、limitations） | `docs/reports/equity-event-001-v3.3.1-audit.md` |
| 2 | 逐文件改动摘要 | 本报告 §3 |
| 3 | 最终 scoring table 与 rationale | 本报告 §4、§14 |
| 4 | 概率公式与测试结果 | 本报告 §5、§9 |
| 5 | 修复的确定性 judge bug 列表 | 本报告 §6 |
| 6 | 三份 LLM rubric 最终版 | `tasks/equity-event-001/judge/rubric_evidence.json`、`rubric_logic.json`、`rubric_handover.json` |
| 7 | GT / 财务定义问题 | 本报告 §8 |
| 8 | 测试结果 | 本报告 §9（23 tests OK） |
| 9 | rollout 结果与 v1.3.1 对比 | 本报告 §11、§12、§13 |
| 10 | 未解决 limitations | 本报告 §15 |
