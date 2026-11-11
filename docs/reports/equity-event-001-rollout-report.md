# equity-event-001 滚动评测报告：轨迹与得分

Case：`equity-event-001`（Equity event desk: Alphabet Q1 2026 earnings night）  
Workflow：`benchmark.equity-event-stream`（LiteEval 90ed715，未改动平台代码）  
报告日期：2026-11-11  
结论：**3 次独立真实 rollout 均达到 ≤40% 难度要求（38.61% / 29.13% / 33.01%）**，三份独立验证报告（solvability / realism / anti-leak）指出的阻塞项已修复并复验，case 可交付。

## 1. Case 与评测目标

一次连续值班：2026-04-29 15:00–21:30 ET，Alphabet Q1 2026 财报夜。信息按真实披露时间通过业务时钟分时释放：
- 15:00 ET（t=0）可读：10-K FY2025、2026-04-02 8-K、2026-04-10 8-K；
- t=3300（15:55）第一次提交截止：forecast（九指标 + beat/miss 概率 + 逐项 basis）；
- t=3600（16:00）释放 4/29 收盘价；t=3695（16:01:35）释放真实 8-K EX-99.1 财报新闻；
- t=4800（16:20）第二次提交截止：reconciliation（实际数、surprise、beat/miss、summary）；
- t=21731（21:02:11）释放真实 10-Q；t=22800（21:20）第三次截止：verification（GAAP 数字、one-off bridge、分部 margin、release vs 10-Q 一致性）；t=23400（21:30）值班结束。

数据全部真实：SEC EDGAR filings（8-K/10-Q/10-K + 真实 EX-99.1 新闻）、Yahoo Finance 真实日线、ILE O19 引用的 Zacks 一致预期（net revenue 91.69B / EPS 2.76）；market.db 3.6 MB，逐行 `available_at_s` 门控 + SQLite authorizer 防护，provenance 与提取脚本随包。

## 2. 评分体系（task.toml，权重合计 100，pass_threshold 0.85）

| check | 类型 | 权重 | 说明 |
| --- | --- | ---: | --- |
| forecast_composite | 确定性 | 74 | 9 个盘前指标线性部分分：total / net / TAC / Services / Cloud / Services op inc / Cloud op inc / consolidated op inc / core EPS |
| probabilities | 确定性 | 5 | Brier 分数（两个真实 beat 事件） |
| one_off_analysis | 确定性 | 3 | 一次性权益收益 $m 与 core EPS |
| reconciliation_actuals | 确定性 | 3 | 实际数 + surprise% + beat/miss（内部 20 分） |
| tenq_verification | 确定性 | 2 | 10-Q 交叉核对 10 项 |
| timeliness | 确定性 | 1 | 三个阶段是否在截止前提交 |
| audit_integrity | 确定性 | 2 | 引用真实/已发布/实际 read；未发布读取与 rejected submit 罚分 |
| evidence_chain | llm_rubric | 5 | 引用可定位、推导可复算、无未来信息 |
| analysis_logic | llm_rubric | 5 | 预测模型逻辑、概率一致性、one-off bridge、跨指标一致性 |

设计理由：把权重集中在"模型真正做不好的部分"——用真实盘前信息预测九项真实披露数字；检索/对账/时间管理对成熟 agent 近乎免费，故只保留低权重作为完整性与公平性保障。

## 3. 校准协议

- 平台：LiteEval 90ed715（HEAD = origin/main），未改动平台代码；项目 `FinStream Bench`，target/judge 共用连接 `DeepSeek V4.1 Flash`（endpoint https://api.deepseek.com, model deepseek-flash）。
- agent harness：`harnesses/json_action`（community JSON-action，content-addressed revision 自动注册；已加固 JSON 提取/DSML 解析，见 §6）；judge：同模型 llm_rubric + 确定性 command judge。
- 预算：120 actions、target_timeout 2400s、judge_timeout 180s；业务时钟 replay。
- 重复：最终配置连续 3 次独立 rollout（每次重新 import 独立 release），全部计入。

## 4. 结果总表

| 版本 | 权重/配置 | 分数 | 结论 | 备注 |
| --- | --- | ---: | --- | --- |
| r1 | v1 旧 rubric、旧 case（forecast_revenue+forecast_tac 两指标） | 83.22 | fail | 能力型：forecast 数值差，提取/对账满分 |
| r2 | v2 权重（60/8/5/5/3/3/4/6/6） | 34.70 | fail | 协议型，不计入：DSML 工具标记导致 ~100/120 动作 invalid |
| r3 | v2 权重 | 49.27 | fail | v2 分数上限参考 |
| r4–r6 | v3-A（forecast 66） | 39.87 / 40.06 / 3.00 | fail | r6 为协议型（尾部幻觉 "User:" 致 submission 解析失败），不计入 |
| r7–r9 | v3-B（forecast 70） | 39.68 / 41.35 / 37.76 | fail | 3 次中 2 次达标，r8 略超 |
| r10–r12 | v3-C，旧 verifier（forecast 只平均 7/9 指标） | 35.17 / 33.79 / 36.72 | fail | 历史记录：评审 verifier 时发现 7/9 指标缺陷，其 evidence 未留存，故修复后重跑 |
| r13–r15 | v3-C 最终 verifier（forecast 平均 9/9 指标） | 38.61 / 29.13 / 33.01 | fail | 最终交付：3/3 均 ≤40% |

最终三次逐 check（权重见 §2）：

| check | r13 | r14 | r15 |
| --- | ---: | ---: | ---: |
| forecast_composite | 0.2461 | 0.1029 | 0.1533 |
| probabilities | 0.8869 | 0.8619 | 0.8918 |
| one_off_analysis | 1.0000 | 1.0000 | 1.0000 |
| reconciliation_actuals | 0.9948 | 0.9948 | 0.9948 |
| tenq_verification | 0.9863 | 0.9863 | 0.9863 |
| timeliness | 1.0000 | 1.0000 | 1.0000 |
| audit_integrity | 1.0000 | 1.0000 | 1.0000 |
| evidence_chain | 0.5000 | 0.7500 | 0.7500 |
| analysis_logic | 0.5000 | 0.5000 | 0.5000 |
| **总分** | **38.61%** | **29.13%** | **33.01%** |

usage 与时长：

| run | execution id | wall (s) | model calls | input tokens | cached | output | reasoning |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| r13v3 | 590eabe1cb224a38ab1f71172deeb1c1 | 165 | 41 | 1,036,566 | 973,696 | 25,174 | 20,642 |
| r14v3 | 2c9af6a6701242b3b4bf9382a03897b5 | 176 | 33 | 834,615 | 772,736 | 28,294 | 22,874 |
| r15v3 | 6610f38b179942dba332e89abc4ba296 | 157 | 28 | 584,476 | 532,224 | 25,012 | 20,854 |

### 4.1 verifier 修订记录（v1.3.1）

交付复核时发现 `judge/verify_ingest.py` 的 `FORECAST_METRICS` 只包含 9 个盘前指标中的 7 个，遗漏了 `google_services_operating_income_usd_m`（实际 40,589，容差 2,029.45）与 `google_cloud_operating_income_usd_m`（实际 6,598，容差 527.84），即 forecast_composite 实际按 7/9 指标取平均，与 manual/design/rubric/ground_truth 声明的"九指标"不一致。修复：补入两个分部经营利润指标，单测 8 项全部通过，并以脚本 oracle 重跑平台 conformance（execution `50104fc836cf4bf3b192a1b58e4da734`）确认 forecast_composite = 1.0、总分 0.9375 pass。由于平台 artifacts 表为空、workspace 已清理，r10–r12 的 evidence 无法离线重判，因此在相同模型/预算/权重下用修复后的 verifier 重跑三次 rollout（r13–r15），结果为 38.61% / 29.13% / 33.01%。历史表中 r10–r12 的数字标注为"7/9 指标 verifier"下测得，仅作历史参考。

## 5. 单次轨迹剖析

### r13v3（score 38.61%）

- 时长 165s，模型调用 41 次，controller actions 39 个（invalid 9 个）。
- 动作时间线（业务时钟，ET = UTC-4）：

| t | 时钟 | action | ok |
| ---: | --- | --- | --- |
| 10 | 19:00:10Z | read | yes |
| 15 | 19:00:15Z | catalog | yes |
| 15 | 19:00:15Z | invalid | no |
| 30 | 19:00:30Z | query | yes |
| 45 | 19:00:45Z | query | yes |
| 60 | 19:01:00Z | query | yes |
| 75 | 19:01:15Z | query | yes |
| 75 | 19:01:15Z | invalid | no |
| 85 | 19:01:25Z | read | yes |
| 85 | 19:01:25Z | invalid | no |
| 95 | 19:01:35Z | read | yes |
| 95 | 19:01:35Z | invalid | no |
| 110 | 19:01:50Z | query | yes |
| 110 | 19:01:50Z | invalid | no |
| 125 | 19:02:05Z | query | yes |
| 140 | 19:02:20Z | query | yes |
| 155 | 19:02:35Z | query | yes |
| 155 | 19:02:35Z | invalid | no |
| 170 | 19:02:50Z | query | yes |
| 170 | 19:02:50Z | invalid | no |
| 185 | 19:03:05Z | query | yes |
| 200 | 19:03:20Z | query | yes |
| 210 | 19:03:30Z | read | yes |
| 225 | 19:03:45Z | query | yes |
| 235 | 19:03:55Z | submit | yes |
| 3600 | 20:00:00Z | wait | yes |
| 3600 | 20:00:00Z | invalid | no |
| 3695 | 20:01:35Z | wait | yes |
| 3705 | 20:01:45Z | read | yes |
| 3715 | 20:01:55Z | submit | yes |
| 21600 | 01:00:00Z | wait | yes |
| 21615 | 01:00:15Z | query | yes |
| 21615 | 01:00:15Z | invalid | no |
| 21630 | 01:00:30Z | query | yes |
| 21640 | 01:00:40Z | read | yes |
| 21731 | 01:02:11Z | wait | yes |
| 21741 | 01:02:21Z | read | yes |
| 21751 | 01:02:31Z | submit | yes |
| 23400 | 01:30:00Z | wait | yes |

- 盘前九指标预测 vs 实际（forecast_composite 明细）：

| 指标 | 预测 | 实际 | 容差 | 得分 |
| --- | ---: | ---: | ---: | ---: |
| diluted_eps_ex_oneoffs_usd | 2.75 | 2.76 | 0.3 | 0.967 |
| google_cloud_operating_income_usd_m | 4200.0 | 6598.0 | 527.84 | 0.000 |
| google_cloud_revenue_usd_m | 16600.0 | 20028.0 | 1602.24 | 0.000 |
| google_services_operating_income_usd_m | 37500.0 | 40589.0 | 2029.45 | 0.000 |
| google_services_revenue_usd_m | 89300.0 | 89637.0 | 2689.11 | 0.875 |
| net_revenue_usd_m | 91700.0 | 94668.0 | 2366.7 | 0.000 |
| operating_income_usd_m | 34000.0 | 39696.0 | 1984.8 | 0.000 |
| tac_usd_m | 15800.0 | 15228.0 | 913.68 | 0.374 |
| total_revenue_usd_m | 107500.0 | 109896.0 | 1648.44 | 0.000 |

- 概率：net_revenue_beat 0.55, eps_beat 0.5, Brier 0.2262。
- one-off：equity gain 预测 36915.0 vs 实际 36915.0 （score 1.0）；core EPS 2.76 vs 2.76。
- 对账明细：{"beat_miss_eps": 2.0, "beat_miss_net_revenue": 2.0, "diluted_eps_usd": 3.0, "eps_pct_vs_consensus": 1.98, "net_revenue_pct_vs_consensus": 1.916, "net_revenue_usd_m": 3.0, "tac_usd_m": 3.0, "total_revenue_usd_m": 3.0}

### r14v3（score 29.13%）

- 时长 176s，模型调用 33 次，controller actions 31 个（invalid 4 个）。
- 动作时间线（业务时钟，ET = UTC-4）：

| t | 时钟 | action | ok |
| ---: | --- | --- | --- |
| 10 | 19:00:10Z | read | yes |
| 15 | 19:00:15Z | catalog | yes |
| 30 | 19:00:30Z | query | yes |
| 45 | 19:00:45Z | query | yes |
| 45 | 19:00:45Z | invalid | no |
| 60 | 19:01:00Z | query | yes |
| 60 | 19:01:00Z | invalid | no |
| 70 | 19:01:10Z | read | yes |
| 70 | 19:01:10Z | invalid | no |
| 80 | 19:01:20Z | read | yes |
| 95 | 19:01:35Z | query | yes |
| 110 | 19:01:50Z | query | yes |
| 125 | 19:02:05Z | query | yes |
| 140 | 19:02:20Z | query | yes |
| 140 | 19:02:20Z | invalid | no |
| 155 | 19:02:35Z | query | yes |
| 165 | 19:02:45Z | read | yes |
| 180 | 19:03:00Z | query | yes |
| 195 | 19:03:15Z | query | yes |
| 195 | 19:03:15Z | None | no |
| 205 | 19:03:25Z | submit | yes |
| 3600 | 20:00:00Z | wait | yes |
| 3615 | 20:00:15Z | query | yes |
| 3695 | 20:01:35Z | wait | yes |
| 3705 | 20:01:45Z | read | yes |
| 3715 | 20:01:55Z | submit | yes |
| 21731 | 01:02:11Z | wait | yes |
| 21741 | 01:02:21Z | read | yes |
| 21756 | 01:02:36Z | query | yes |
| 21766 | 01:02:46Z | submit | yes |
| 23400 | 01:30:00Z | wait | yes |

- 盘前九指标预测 vs 实际（forecast_composite 明细）：

| 指标 | 预测 | 实际 | 容差 | 得分 |
| --- | ---: | ---: | ---: | ---: |
| diluted_eps_ex_oneoffs_usd | 2.45 | 2.76 | 0.3 | 0.000 |
| google_cloud_operating_income_usd_m | 4350.0 | 6598.0 | 527.84 | 0.000 |
| google_cloud_revenue_usd_m | 17000.0 | 20028.0 | 1602.24 | 0.000 |
| google_services_operating_income_usd_m | 36400.0 | 40589.0 | 2029.45 | 0.000 |
| google_services_revenue_usd_m | 90400.0 | 89637.0 | 2689.11 | 0.716 |
| net_revenue_usd_m | 91850.0 | 94668.0 | 2366.7 | 0.000 |
| operating_income_usd_m | 35000.0 | 39696.0 | 1984.8 | 0.000 |
| tac_usd_m | 15950.0 | 15228.0 | 913.68 | 0.210 |
| total_revenue_usd_m | 107800.0 | 109896.0 | 1648.44 | 0.000 |

- 概率：net_revenue_beat 0.5, eps_beat 0.45, Brier 0.2762。
- one-off：equity gain 预测 36915.0 vs 实际 36915.0 （score 1.0）；core EPS 2.76 vs 2.76。
- 对账明细：{"beat_miss_eps": 2.0, "beat_miss_net_revenue": 2.0, "diluted_eps_usd": 3.0, "eps_pct_vs_consensus": 1.98, "net_revenue_pct_vs_consensus": 1.916, "net_revenue_usd_m": 3.0, "tac_usd_m": 3.0, "total_revenue_usd_m": 3.0}

### r15v3（score 33.01%）

- 时长 157s，模型调用 28 次，controller actions 26 个（invalid 2 个）。
- 动作时间线（业务时钟，ET = UTC-4）：

| t | 时钟 | action | ok |
| ---: | --- | --- | --- |
| 10 | 19:00:10Z | read | yes |
| 15 | 19:00:15Z | catalog | yes |
| 30 | 19:00:30Z | query | yes |
| 45 | 19:00:45Z | query | yes |
| 60 | 19:01:00Z | query | yes |
| 60 | 19:01:00Z | invalid | no |
| 70 | 19:01:10Z | read | yes |
| 70 | 19:01:10Z | None | no |
| 85 | 19:01:25Z | query | yes |
| 100 | 19:01:40Z | query | yes |
| 115 | 19:01:55Z | query | yes |
| 130 | 19:02:10Z | query | yes |
| 130 | 19:02:10Z | invalid | no |
| 140 | 19:02:20Z | read | yes |
| 155 | 19:02:35Z | query | yes |
| 170 | 19:02:50Z | query | yes |
| 180 | 19:03:00Z | submit | yes |
| 3600 | 20:00:00Z | wait | yes |
| 3615 | 20:00:15Z | query | yes |
| 3695 | 20:01:35Z | wait | yes |
| 3705 | 20:01:45Z | read | yes |
| 3715 | 20:01:55Z | submit | yes |
| 21731 | 01:02:11Z | wait | yes |
| 21741 | 01:02:21Z | read | yes |
| 21751 | 01:02:31Z | submit | yes |
| 23400 | 01:30:00Z | wait | yes |

- 盘前九指标预测 vs 实际（forecast_composite 明细）：

| 指标 | 预测 | 实际 | 容差 | 得分 |
| --- | ---: | ---: | ---: | ---: |
| diluted_eps_ex_oneoffs_usd | 2.48 | 2.76 | 0.3 | 0.067 |
| google_cloud_operating_income_usd_m | 4200.0 | 6598.0 | 527.84 | 0.000 |
| google_cloud_revenue_usd_m | 17000.0 | 20028.0 | 1602.24 | 0.000 |
| google_services_operating_income_usd_m | 36300.0 | 40589.0 | 2029.45 | 0.000 |
| google_services_revenue_usd_m | 89800.0 | 89637.0 | 2689.11 | 0.939 |
| net_revenue_usd_m | 91700.0 | 94668.0 | 2366.7 | 0.000 |
| operating_income_usd_m | 35500.0 | 39696.0 | 1984.8 | 0.000 |
| tac_usd_m | 15800.0 | 15228.0 | 913.68 | 0.374 |
| total_revenue_usd_m | 107500.0 | 109896.0 | 1648.44 | 0.000 |

- 概率：net_revenue_beat 0.52, eps_beat 0.55, Brier 0.2164。
- one-off：equity gain 预测 36915.0 vs 实际 36915.0 （score 1.0）；core EPS 2.76 vs 2.76。
- 对账明细：{"beat_miss_eps": 2.0, "beat_miss_net_revenue": 2.0, "diluted_eps_usd": 3.0, "eps_pct_vs_consensus": 1.98, "net_revenue_pct_vs_consensus": 1.916, "net_revenue_usd_m": 3.0, "tac_usd_m": 3.0, "total_revenue_usd_m": 3.0}

## 6. 为什么这是能力型低分，而不是环境/协议误差

- 校准中发现的协议问题（DeepSeek-V4.1-Flash 偶发原生工具调用标记 `<｜｜DSML｜｜ calls>`、在 JSON 后追加幻觉 "User:" 轮次）已记录在案：r2（34.7%）与 r6（3.0%）属于协议失败，**已从难度证据中排除**。bench 侧 `harnesses/json_action` 随后增加 DSML→action 转换与“取回复中第一个 JSON 对象”的容错，并把 assistant 历史规范化为 action JSON；最终 r10–r12 的 invalid 动作占比已降到 3/29、0/31、7/30（见 §5），不再影响提交完整性。
- 最终三次的 timeliness 全部 1.0、audit_integrity 全部 1.0、reconciliation/tenq 均 >0.98：说明模型能按时、按规完成值班与交叉核对；低分来自 forecast 对真实披露的预测误差（见 §5 明细），即真正的能力瓶颈。
- 三份独立验证（docs/validation/）确认：数据真实、时间边界机械可验、参考解 16 个动作可完成全流程；旧版本真值泄漏（manual 示例泄漏 109896.0/36.12）与不可达 forecast 已修复，并新增单测防止回归。

## 7. 难度机制（用户允许措施内的加难记录）

1. 把评分主导权交给 9 指标 forecast（74/100），且指标覆盖模型最容易保守化/拍脑袋的部分（net revenue、TAC、Cloud、segment op income）；
2. 真实 peer 噪声：MSFT/META/AMZN 2026-04-29 盘后 8-K EX-99.1 真实文本同晚公开，但与本任务无关，需 agent 自行排除；
3. prompt 收敛为 5 行（角色/班次/manual 指引/预算），不列步骤与判分细节，manual 是唯一协议入口；
4. 提取/对账/时间管理类 check 权重压到 3+3+2+1+2；rubric 只保留 5+5 权重的语义证据与逻辑；
5. 审计收紧：未发布读取、未实际 read 的引用、rejected submit 均罚分（防“猜中”与投机）。

## 8. 可解性与公平性证据

- 参考解（solvability subagent）：用 agent 可见数据独立推导全部计分字段，16 个动作完成三阶段提交（预算 120），单调 deterministic 分在修复后为满分；报告 `docs/validation/solvability-review.md`。
- realism review 的阻塞项（manual 泄漏、10-Q 无法验证 segment、设计-实现不一致）已全部修复；anti-leak review 的时间边界断言（30 filings / 6 docs / 20,777 facts / 718 prices / 4 consensus / 12 events）全部通过，且绕过测试套件拒绝写/ATTACH/PRAGMA/扩展/路径穿越。
- 单测：`python3 -m unittest tests.test_equity_event_judge -v` → 8 tests OK（perfect=1.0、deadline 边界、未读引用扣分、未来引用扣分、Brier、真值 token 扫描、workspace 无 judge 材料）。

## 9. 残余风险与使用条件

1. 预训练知识无法机械消除；已选 2026-04 事件并实测该模型"不知道"，但不构成绝对保证。
2. market.db 物理含未来行，由 data service 强制门控；workspace/trusted-local 信任链之外的运行方需自行评估。
3. evidence 由 controller 导出，judge 审计 citation/read 历史；平台之外伪造需信任链假设。
4. LLM rubric 有采样方差；权重已压到 10/100，三次重复与轨迹复核均已保留。

使用条件：固定本仓库当前 commit + LiteEval ≥90ed715 + community.json-action + deepseek-flash；保留原始 rollout 记录与 judge 输出；跨版本分数不混算。

## 10. 复现与文件索引

- Case：`tasks/equity-event-001/`（task.toml、prompt.md、desk/manual.md、workflow-fixtures/scenario.json、judge/verify_ingest.py、judge/rubric_evidence.json、judge/rubric_logic.json、data/、provenance/）
- Workflow：`workflows/equity-event-stream/`（controller.py、engine.py、data_service.py、harness.toml）
- Agent harness：`harnesses/json_action/`；DB 构建：`tasks/equity-event-001/build_equity_event_db.py`
- 单测：`tests/test_equity_event_judge.py`；设计：`docs/design/equity-event-stream-case-design.md`；验证：`docs/validation/`；难度校验：`docs/validation/UNIFIED-ASSESSMENT.md`

复现命令（需平台连接；每条 rollout 独立打包以避免并行导入冲突）：

```bash
export LITEEVAL_SECRET_KEY=$(cat data/secrets/master.key)   # from your LiteEval checkout
.venv/bin/liteeval benchmark validate <repo>
.venv/bin/liteeval harness <repo>/workflows/equity-event-stream --project <PROJECT>
.venv/bin/liteeval harness <repo>/harnesses/json_action --project <PROJECT>
.venv/bin/liteeval benchmark import <单任务包> --project <PROJECT>
.venv/bin/liteeval benchmark run <RELEASE> --project <PROJECT> --agent-harness <AGENT_REV> \
  --workflow-harness <WF_REV> --target-connection <CONN> --judge-connection <CONN> --trusted-local
```

最终 rollout 记录：`<workdir>/ee_run_r13v3.json` / `r14v3` / `r15v3`（execution id 见 §4）；历史记录：`<workdir>/ee_run_*.json`。

## 附录 A：最终三次 check 明细（含 reason）

### r13v3 — score 38.61%

| check | outcome | score | weight | reason |
| --- | --- | ---: | ---: | --- |
| forecast_composite | fail | 0.2461 | 74 | forecast_composite score 0.2461 (weight 74) |
| probabilities | fail | 0.8869 | 5 | probabilities score 0.8869 (weight 5) |
| one_off_analysis | pass | 1.0000 | 3 | one_off_analysis score 1.0000 (weight 3) |
| reconciliation_actuals | fail | 0.9948 | 3 | reconciliation_actuals score 0.9948 (weight 3) |
| tenq_verification | fail | 0.9863 | 2 | tenq_verification score 0.9863 (weight 2) |
| timeliness | pass | 1.0000 | 1 | timeliness score 1.0000 (weight 1) |
| audit_integrity | pass | 1.0000 | 2 | audit_integrity score 1.0000 (weight 2) |
| evidence_chain | fail | 0.5000 | 5 | Deterministic per-criterion aggregation |
| analysis_logic | fail | 0.5000 | 5 | Deterministic per-criterion aggregation |

### r14v3 — score 29.13%

| check | outcome | score | weight | reason |
| --- | --- | ---: | ---: | --- |
| forecast_composite | fail | 0.1029 | 74 | forecast_composite score 0.1029 (weight 74) |
| probabilities | fail | 0.8619 | 5 | probabilities score 0.8619 (weight 5) |
| one_off_analysis | pass | 1.0000 | 3 | one_off_analysis score 1.0000 (weight 3) |
| reconciliation_actuals | fail | 0.9948 | 3 | reconciliation_actuals score 0.9948 (weight 3) |
| tenq_verification | fail | 0.9863 | 2 | tenq_verification score 0.9863 (weight 2) |
| timeliness | pass | 1.0000 | 1 | timeliness score 1.0000 (weight 1) |
| audit_integrity | pass | 1.0000 | 2 | audit_integrity score 1.0000 (weight 2) |
| evidence_chain | fail | 0.7500 | 5 | Deterministic per-criterion aggregation |
| analysis_logic | fail | 0.5000 | 5 | Deterministic per-criterion aggregation |

### r15v3 — score 33.01%

| check | outcome | score | weight | reason |
| --- | --- | ---: | ---: | --- |
| forecast_composite | fail | 0.1533 | 74 | forecast_composite score 0.1533 (weight 74) |
| probabilities | fail | 0.8918 | 5 | probabilities score 0.8918 (weight 5) |
| one_off_analysis | pass | 1.0000 | 3 | one_off_analysis score 1.0000 (weight 3) |
| reconciliation_actuals | fail | 0.9948 | 3 | reconciliation_actuals score 0.9948 (weight 3) |
| tenq_verification | fail | 0.9863 | 2 | tenq_verification score 0.9863 (weight 2) |
| timeliness | pass | 1.0000 | 1 | timeliness score 1.0000 (weight 1) |
| audit_integrity | pass | 1.0000 | 2 | audit_integrity score 1.0000 (weight 2) |
| evidence_chain | fail | 0.7500 | 5 | Deterministic per-criterion aggregation |
| analysis_logic | fail | 0.5000 | 5 | Deterministic per-criterion aggregation |

