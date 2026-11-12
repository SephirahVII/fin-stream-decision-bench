# equity-event-001 v1.4.0：跨模型评测（DeepSeek V4.1 Flash vs V4 Pro）

- 日期：2026-11-12
- Case：`equity-event-001`（benchmark `extreme-financial-events` 1.4.0）
- 平台：LiteEval `90ed715`（未修改平台代码）
- 任务包 release：`4caedfcf283a429d975519b79d833fea`（task package 0.4.2，judge_timeout 480）
- Workflow harness：`benchmark.equity-event-stream`（revision `c5464596314e49619c45eda8bd73aec0`）
- Agent harness：`community.json-action` 1.3.0（revision `aefbf42b10244b85ba767180a6af4c59`）
- Judge：DeepSeek V4.1 Flash（connection `2e3e1a77…`，与目标模型解耦，两模型共用同一 judge 连接）

本报告是 v3.3.1 评分改造（[`equity-event-001-v3.3.1-report.md`](equity-event-001-v3.3.1-report.md)）之后的补充：按用户要求，用同一 API key 下的两个模型各做 3 次独立 rollout，检查新评分体系在跨模型上的区分度、稳定性与工程可行性。

## 1. 评测协议

| 项目 | 设置 |
| --- | --- |
| 目标模型 | `deepseek-flash`（DeepSeek-V4.1-Flash，connection `2e3e1a77…`）与 `deepseek-v4-pro`（DeepSeek-V4-Pro，connection `64e487bd…`） |
| Rollouts | 每模型 3 次，**6 个 run 并发启动**（stagger 8 s） |
| 任务包 / harness / judge | 两模型完全相同；judge 固定为 Flash |
| 预算 | 120 actions / 2400 s 业务时钟目标预算 / 480 s judge 预算 |
| 执行时间 | 2026-11-12 17:34–18:12（CST） |

## 2. 结果总览

| 模型 | run | score | outcome | wall (s) | target phase (s) | judge (s) | model calls | actions / invalid | input / cached / output / reasoning tokens |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| Flash | f1 | **50.45%** | fail | 356.6 | 165.1 | 191.6 | 44 | 41 / 6 | 1,237,387 / 1,163,776 / 62,140 / 54,540 |
| Flash | f2 | **43.01%** | fail | 405.2 | 294.3 | 110.9 | 59 | 56 / 15 | 1,927,020 / 1,846,656 / 69,678 / 61,847 |
| Flash | f3 | **47.03%** | fail | 463.1 | 300.5 | 162.6 | 45 | 42 / 4 | 1,419,653 / 1,336,704 / 82,331 / 71,708 |
| **Flash 汇总** | 3 | **mean 46.83%、sd 3.72、min 43.01、max 50.45** | | | | | 44–59 | | |
| Pro | p1 | **30.94%** | fail | 1,277.8 | 1,152.1 | 125.8 | 43 | 40 / 1 | 1,413,546 / 1,324,800 / 93,580 / 88,323 |
| Pro | p2 | **31.82%** | fail | 1,611.5 | 1,454.6 | 156.9 | 49 | 46 / 1 | 1,808,527 / 1,711,744 / 119,398 / 113,382 |
| Pro | p3 | **34.69%** | fail | 1,597.2 | 1,462.5 | 134.7 | 47 | 44 / 1 | 1,520,167 / 1,440,128 / 117,138 / 110,746 |
| **Pro 汇总** | 3 | **mean 32.48%、sd 1.96、min 30.94、max 34.69** | | | | | 43–49 | | |

- Flash：mean **46.83**（sd 3.72）。此前 v1.4.0 最终配置 4 次的 mean 42.01（sd 1.50）；两次批次合计 7 次 mean 43.9，说明同一模型在 LLM rubric 上存在跨批次波动（主要是 analysis/evidence 的 binary criteria）。
- Pro：mean **32.48**（sd 1.96），三次全部落在 **30–40** 带内，且方差明显小于 Flash。
- Pro 慢很多：target 阶段 19.2–24.4 分钟（Flash 2.8–5.0 分钟），仍远低于 2400 s 目标预算；judge 时间相近（126–157 s）。
- Pro invalid actions 仅 1 次/run（Flash 4–15 次），JSON action 协议遵循更好；两模型都完成三阶段提交、audit=1.0。

## 3. 逐 check 对比（3 次均值 ± sd）

| check | weight | Flash | Pro | 差异（Flash−Pro） |
| --- | ---: | ---: | ---: | ---: |
| `forecast_composite` | 55 | 0.2603 ± 0.0247 | 0.2111 ± 0.0490 | +0.049 |
| `probabilities` | 5 | 0.4008 ± 0.0937 | 0.2283 ± 0.2353 | +0.173 |
| `one_off_analysis` | 2 | 1.0000 ± 0 | 1.0000 ± 0 | 0 |
| `reconciliation_actuals` | 2 | 0.9948 ± 0 | 0.9948 ± 0 | 0 |
| `tenq_verification` | 2 | 0.9278 ± 0.0987 | 0.8708 ± 0.0987 | +0.057 |
| `timeliness` | 1 | 1.0000 ± 0 | 1.0000 ± 0 | 0 |
| `audit_integrity` | 2 | 1.0000 ± 0 | 1.0000 ± 0 | 0 |
| `evidence_chain` | 10 | 0.8667 ± 0.1155 | 0.5667 ± 0.1155 | **+0.300** |
| `analysis_logic` | 13 | 0.4103 ± 0.2221 | 0.1282 ± 0.1175 | **+0.282** |
| `handover_quality` | 8 | 0.9583 ± 0.0722 | 0.4583 ± 0.0722 | **+0.500** |
| **总分** | 100 | **46.83 ± 3.72** | **32.48 ± 1.96** | **+14.35** |

加权贡献（3 次均值）：Flash 中 forecast 14.32、evidence 8.67、handover 7.67、analysis 5.33；Pro 中 forecast 11.61、evidence 5.67、handover 3.67、analysis 1.67。**分差主要来自三个分析质量 rubric（evidence/logic/handover = 31 分），不是预测数值本身**（forecast 仅差 2.7 分贡献）。

## 4. 原因分析（基于提交证据，不基于印象）

同一评分器下，Pro 的**事实提取与对账仍然很强**：one_off 1.0、reconciliation 0.9948、audit 1.0、timeliness 1.0，tenq 0.87（低于 Flash 的 0.93，主要差在 segment margin / TAC 一两个数值）；预测数值略差（forecast 0.211 vs 0.260）。

差距集中在**分析交付与交接质量**：

1. **Verification summary 明显更短**（同题同证据）：抽样的 Flash verification summary 为 2,315–3,699 字符（含 forecast-vs-actual 逐项、GAAP→core 桥、研究教训、残余不确定性），Pro 为 884–1,381 字符（更像"状态确认"）：例如 p1 的 verification summary 只有 884 字符，主要复述实际数字与 one-off 金额，**没有逐项对比盘前预测、没有列出应修订的研究假设、没有给出残余不确定性与量级**——这正是 H1/H3/H4 判 0 的直接原因；这也使 evidence rubric 中 claim-level locator 与 one-off 税务/股本桥解释不足（E2/E4 失分）。
2. **分析逻辑（L1–L5）差异**：Pro 对 9 指标预测的 rationale 大多集中在收入/Cloud 增长假设，缺少逐指标 anchor 与概率推理（L2），且没有把 release 后的新信息转成"下一个研究步骤"（L3/L5 失分）。
3. **概率事件**：Pro 的 p1 给出 net 0.3 / eps 0.1，净收入事件 realized（+3.25%）未 beat 预期，Brier=0.25 → BSS=0；另外两次 0.215/0.47。整体低于 Flash（0.29–0.47），但样本少。
4. **协议与鲁棒性**：Pro invalid actions 每 run 仅 1 次，Flash 4–15 次；Pro 的长 wall time 来自单次推理更慢（reasoning tokens 88–113k vs Flash 55–72k），不是环境错误或超时。

## 5. 解释与限制（重要）

1. **这不是"Pro 更弱"的结论**：两模型都完成了同一任务并得到可审计分数；差异集中在"可交接的专业分析文档"这一评测维度。Pro 的 factual extraction 与 reconciliation 同样接近满分，说明本 case 的预测/对账部分对强模型已接近饱和，而分析交付部分开始产生区分。
2. **存在 benchmark 风格偏差风险**：本 case 的 rubric 与权重是在 Flash 的轨迹上迭代校准的（v1.3.0–v1.4.0），H1–H5 等判据对"把 forecast-vs-actual、教训、残余不确定性写进 summary"的结构有明确要求；Pro 的简洁风格可能部分反映的是**沟通风格差异**而非分析能力缺陷。因此：
   - 不应据此断言 v4-pro 的分析能力低于 Flash；
   - 若要用于模型横向比较，建议增加人工/第三方对 Pro 轨迹的盲评，或补充"格式中性"的 rubric 变体（但不应对单一模型调参）；
   - 报告的合理用法是"在本 case 的既有评分定义下，两模型的分数分布"，而非通用能力排序。
3. Pro 是否"更慢"影响公平性：目标预算是 2400 s，Pro 用 19–24 min 仍在预算内；若未来模型更慢，需要按协议调整预算并重新校准，不能混用。
4. 样本量：每模型 3 次；Flash 与 v1.4.0 历史 7 次合计 mean 43.9（sd 更大），批次间 LLM judge 波动约 ±3 pp；Pro 3 次 sd 1.96，暂未观察到随机失败（judge 错误 0 次）。
5. 该评测对 judge 模型固定为 Flash：若换 judge 模型，分数可能变化；跨 judge 模型不可直接比较。

## 6. 工程结论

- 同一任务包/harness/judge 配置下，两个模型**并发**各 3 次完整跑通（无 timeout、无 judge 错误、无 unscored），说明 v1.4.0 的 480 s judge 预算与 json_action harness 在慢模型上也稳健。
- Pro 的 wall time 达 21–27 分钟（target 阶段 19–24 分钟），主要成本来自长 reasoning；token 成本约为 Flash 的 1.1–1.3 倍（input 相近、output/reasoning 约高 50–90%）。
- 复现命令与执行 id：

```
release 4caedfcf283a429d975519b79d833fea（task package 0.4.2）
workflow revision c5464596314e49619c45eda8bd73aec0
agent harness aefbf42b10244b85ba767180a6af4c59

liteeval benchmark run 4caedfcf… --project <PROJECT> \
  --agent-harness aefbf42b… --workflow-harness c5464596… \
  --target-connection <FLASH|PRO_CONNECTION> --judge-connection <FLASH_CONNECTION> --trusted-local
```

| 模型 | execution id |
| --- | --- |
| Flash f1 | `9f6601b4f39f4bdd83125fd71f6d7b1a` |
| Flash f2 | `5816e46a96944e6ebca81e94998a5d83` |
| Flash f3 | `db4eaa2f8e9947ef992a590f93cc95e1` |
| Pro p1 | `14d9b2a841a942c1812571fa5607db19` |
| Pro p2 | `daa366ef0a7a4a009c939226043918e7` |
| Pro p3 | `88d8993b6a194d22a577bf5dce5bf4e8` |

## 7. 后续建议

1. 对 Pro 的 3 条轨迹做人工盲评，确认 evidence/handover 的低分是否属于 rubric 期望（写交接文档）与模型风格（简洁状态汇报）的错配；若是，考虑在 rubric 中把"内容是否包含"与"是否按指定结构呈现"拆开，而不是降低要求。
2. 若要支持模型横向比较，建议把 judge 模型固定、judge 采样方差纳入报告（每模型 ≥3 次），并同时报告 scoring_coverage。
3. 预测类 check 对强模型已接近饱和（Flash forecast 0.26 / Pro 0.21，满分 1.0），后续若继续加难，优先增加需要多步状态维护与纠偏的决策内容（见 `docs/design/other-cases.md` 的 Case B/D），而不是继续压缩预测容差。
