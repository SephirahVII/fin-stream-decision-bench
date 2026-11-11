# equity-event-001 — 三份独立验证报告的统一意见

验证对象：`tasks/equity-event-001`（Equity event desk: Alphabet Q1 2026 earnings night）与
`workflows/equity-event-stream`。三份报告由三个相互独立的 subagent 在互不可见的条件下完成，
只读取仓库与 `/tmp` 下的证据，分别负责 solvability、realism、anti-leak 审计：

| 报告 | 结论（验证时） | 文件 |
| --- | --- | --- |
| solvability | SOLVABLE WITH FIXES（机制可解，但旧阈值/口径下不可通过） | `docs/validation/solvability-review.md` |
| realism | FAIL（存在真值泄漏与设计-实现不一致） | `docs/validation/realism-review.md` |
| anti-leak | LEAK FOUND（manual 示例泄漏真值；失败读取使 controller 崩溃） | `docs/validation/anti-leak-review.md`，`<workdir>/leak_audit/*.json` |

## 1. 统一结论

**可行，但必须以修复后的 v1.1+ 状态交付。** 三份报告指出的阻塞项已在 bench 侧全部修复，
并由第四方（本报告作者）逐项复验；未发现伪造数据或无意泄漏。

- 真实性：所有数值来自 SEC EDGAR 真实 filing（Alphabet Q1 2026 8-K EX-99.1 / 10-Q / 10-K）、
  Yahoo Finance 真实日线、以及 ILE O19 引用的 Zacks 一致预期（公开新闻）。无合成数字。
  `data/PROVENANCE.json` + `provenance/` 记录每个文件的 sha256、字节数与来源 URL。
- 防未来泄漏：数据库物理包含全部行，但所有行带 `available_at_s`；`data_service` 在查询/读取时
  按业务时钟过滤，并在 SQLite authorizer 层拒绝写/ATTACH/扩展/隐藏表/路径穿越。30/30 行级
  availability、6/6 文档、20,777/20,777 XBRL、718/718 行情、4/4 consensus、12/12 事件均已断言；
  t=0/3600/3695/21731 等边界与真实披露时间（16:01:35 ET、21:02 ET）一致。
- 可解性：参考解 16 个动作（预算 120）即可完成三个阶段并在截止前提交；阶段 slack > 1,000 业务秒；
  确定性判分在参考解上为满分（修复 GS margin 口径后）。
- 难度：pre-release forecast 是真正的能力瓶颈（七至九个指标、真实一致预期与真实披露的差距）；
  校准结果见 `docs/reports/equity-event-001-rollout-report.md`。

## 2. 已修复清单（按报告条目）

- **B1 forecast 无法通过**：把 forecast 改为九指标复合分（total/net/TAC/Services/Cloud/
  segment operating income/consolidated operating income/core EPS），容差按指标设定；
  forecast 不再把一次性权益收益算入（core EPS 口径），并在 manual 中明确。
- **B2 manual 泄漏真值**：示例值全部改为与真值无关的虚构数字（100000.0 / 30.00）；
  新增单测 `test_agent_visible_text_does_not_contain_ground_truth_tokens` 扫描 agent 可见文件。
- **B3 10-Q 无 segment 数据**：manual 明确 segment margin 来自 release 的 segment 表，
  10-Q 用于合并数字交叉核对；verification 的 segment 项以 release 为准。
- **M1/M4/M5/M6**：设计文档与实现对齐（权重、容差、pass_threshold 0.85、120 actions、
  consensus 为 net-of-TAC 口径、LLM judge 说明）；README 重写；judge 权重与 task.toml 一致。
- **M3/M8 provenance**：`data/PROVENANCE.json` + `provenance/`（脚本、提取报告、完整 manifest）；
  post-event 材料移入 `judge/provenance/`，不在 agent 可见工作区。
- **M9 审计过软**：verification/reconciliation 强制 summary；审计同时检查 forecast basis、
  引用文档是否已发布、是否实际 read、未发布读取与 rejected submit 罚分；单测覆盖。
- **anti-leak HIGH（controller 崩溃）**：controller 捕获 `DataRejected`，失败读取记入 journal 并计入
  审计罚分，不再 rc=1 崩溃。
- **anti-leak LOW（sqlite_schema 别名）**：`FORBIDDEN` 增加 `sqlite_schema`/`sqlite_temp_*`。
- **协议健壮性（校准中发现，不是难度来源）**：DeepSeek-V4.1-Flash 偶尔输出原生工具调用标记或
  在 JSON 后追加幻觉轮次；bench 侧 `harnesses/json_action` 增加 DSML→action 转换与"提取首个 JSON
  对象"逻辑，并把 assistant 历史规范化，避免协议问题被记成推理失败（r2 的 34.7% 即此原因，已废弃）。

## 3. 残余风险（需在报告中声明）

1. 预训练知识无法从机制上消除；本 case 选 2026-04 事件并实测 DeepSeek-V4.1-Flash 回答"不知道/
   beyond knowledge cutoff"，降低了风险，但不构成绝对保证。
2. `market.db` 物理含未来行；`environment_profile=workspace` 下由 controller 的 data service 强制
   过滤。任何拥有文件系统权限的 harness 理论上可绕过读取——平台默认 `--trusted-local` 信任链内，
   已在设计文档声明。
3. evidence 由 controller 导出；judge 审计 citation/read 历史，但 controller 以外的伪造需要平台
   侧信任链（现有 harness 已封装，风险低）。
4. LLM rubric 有采样方差；已通过确定性 check 占 90% 权重、同 rubric 三次重复与轨迹复核缓解。

## 4. 交付意见

三份独立验证均指向同一结论：**数据真实、时间边界可机械验证、任务可解**；旧版本的阻塞问题
（真值泄漏、不可达 forecast、审计过软、协议崩溃）已全部修复并有单测/脚本证据。
本 case 可以进入真实模型校准（结果见 rollout 报告）；如用于正式 challenge，应固定
DeepSeek-V4.1-Flash + community.json-action + 本仓库 digests，并保留原始轨迹与 judge 输出。
