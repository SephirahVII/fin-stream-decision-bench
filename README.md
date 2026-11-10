# fin-stream-decision-bench

评估 Agent 在**持续更新的金融数据流下作出及时、可审计决策**的能力。

一个 case 对应一次连续的值班会话：市场数据、追缴通知、交易回执按业务时钟分时释放，信息流不断刷新；Agent 必须在各融资与交收窗口关闭之前完成风险识别、筹资决策、指令执行与纠偏，并留下可复算的交接记录。所有金额、合同与交收由确定性仿真器结算，评分由独立命令 Judge 离线复算账本——分数可复核、可重评、可版本化。

## 题型定位

与静态题库不同，本 bench 的核心变量是**时间与状态**：

- 信息只在各自的业务时点可见，未来材料不可预读；
- 资金窗口有真实截止与到账时滞（回购 09:15 截止/09:25 到账，授信授权需 8 个业务分钟……）；
- 通知会改版、指令会被拒、来款会挂账、结算指令集会切换——分析正确但行动超时同样失败；
- 平稳与对冲对照情景检验"不误报、不浪费"。

## Case 构成（v1.0.0，7 个 case）

| Case | 家族 | 数据流特征 | 定位 |
| --- | --- | --- | --- |
| `ldi-margin-001/002/003` | LDI 值班 L0 | 两分支共享 09:12 前事件流后分叉（拒单/正常），平稳对照测误报 | 流程验收 |
| `treasury-duty` | Treasury network L8 | 多实体多币种、通知改版、FX 匹配失败、SSI 改版、共享额度、到期偿还 | 运营基线（Flash 100 / M3 61.39，校准中） |
| `source-treasury-stress/quiet/hedged` | Source treasury 0.3.0 | 不给内部现金与预测，须从银行记录、交易注册表、CSA 协议与市场因子重建风险台账 | 校准候选（压力均分 Flash 66.43 / M3 100） |

难度校准目标：当期强模型与成熟 Agent 在冻结 Harness、预算与 rubric 下实测均分约 30–40/100。各家族实测分布与已知局限见 `docs/calibration/`。保留金额变体不随本仓库分发。

## 运行

依赖 LiteEval 平台（≥ `90ed715`，支持单次运行解析多个 Workflow 控制器）：

```powershell
python -m liteeval.interfaces.cli.main benchmark validate .
python -m liteeval.interfaces.cli.main harness workflows/financial-stress --project PROJECT_ID
python -m liteeval.interfaces.cli.main harness workflows/treasury-network --project PROJECT_ID
python -m liteeval.interfaces.cli.main harness workflows/source-treasury --project PROJECT_ID
python -m liteeval.interfaces.cli.main benchmark run RELEASE_ID --project PROJECT_ID \
  --agent-harness AGENT_REVISION --workflow-harness WF1 --workflow-harness WF2 --workflow-harness WF3 \
  --target-connection CONNECTION_ID --trusted-local
```

每个 case 的 `[workflow]` 段声明其控制器 ID，平台按任务匹配对应控制器。

## 目录

```text
dataset.toml      # 7 case，默认 2400s 任务预算 / 30s Judge 预算
tasks/            # 各 case 的 prompt、公开工作区、私有情景 fixture、Judge
workflows/        # 三个 Workflow 控制器（仿真器 + 事件流释放）
docs/design/      # 设计稿（含难度递进与下一版方向）
docs/calibration/ # 固定协议、实测分布与失败模式分析
docs/proposals/   # 新题型原型设计
```

## 设计约束

- 题包层迭代：平台代码不改，除非 bench 格式确实无法表达；
- 既有运行的原始输出、权重、评分与版本不改写；难度迭代发新版本；
- 判分不使用 LLM Judge：所有检查为确定性程序，重评不调用被测模型；
- 环境故障记 unscored，不记零分；跨版本分数不混算均值。
