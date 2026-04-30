# Ops Fault Diagnosis - Multi-Agent System

基于多 Agent 协作的运维故障诊断系统，自动完成从告警降噪、根因定位、修复建议到复盘报告的全链路诊断闭环。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (编排器)                      │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │ 🔍 告警   │──>│ 🎯 根因   │──>│ 🔧 修复   │──>│ 📋 复盘   │ │
│  │ 聚合Agent │   │ 定位Agent │   │ 建议Agent │   │ Agent    │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│       │              │              │              │        │
│       v              v              v              v        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              SharedContext (共享上下文)                │   │
│  │   拓扑 | 告警 | 日志 | 指标 | 变更 | 诊断结果        │   │
│  └──────────────────────────────────────────────────────┘   │
│       │              │              │              │        │
│       v              v              v              v        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                EventBus (事件总线)                     │   │
│  │            Agent 推理过程 → CLI 实时展示              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 4 Agent 协作流程

| Phase | Agent | 核心能力 | Claude 调用 |
|-------|-------|---------|------------|
| 1 | 告警聚合 Agent 🔍 | 50+ 条原始告警 → 1-2 个事件（拓扑感知降噪） | 1-2 次 |
| 2 | 根因定位 Agent 🎯 | 多步长链推理：表面症状→调用链追踪→日志深挖→变更关联 | 3-5 次 |
| 3 | 修复建议 Agent 🔧 | 生成含可执行脚本的修复方案（风险评级+置信度） | 1-2 次 |
| 4 | 复盘 Agent 📋 | 时间线重建、影响评估、改进项、经验教训 | 1 次 |

**根因定位 Agent 的长链推理是核心展示环节**：不直接跳到结论，而是从表面症状出发沿调用链逐层下钻，每步记录"检查了什么→观察到了什么→意味着什么"，形成完整证据链。

## 内置故障场景

| # | 场景 | 根因 | 级联链路 |
|---|------|------|---------|
| 1 | 数据库连接池耗尽级联 | payment-svc v2.3.1 连接泄漏 + db-primary 连接池缩容 | db-primary → payment-svc → order-svc → api-gateway → web-frontend |
| 2 | 内存泄漏 OOM Kill 级联 | order-svc 缓存模块内存泄漏 | order-svc OOM → CrashLoopBackOff → api-gateway 503 → 上下游流量下降 |
| 3 | 磁盘满级联 | db-primary 日志轮转配置错误 | db-primary 磁盘 100% → WAL 写入失败 → 主从延迟 → 读取不一致 |

每个场景包含完整的模拟数据：告警风暴（~50 条）、故障特征日志、异常指标时序、变更记录（含噪声和干扰项）。

## 服务拓扑

```
                    [web-frontend]
                         |
                    [api-gateway]
                    /     |      \
             [user-svc] [order-svc] [product-svc]
                  |       /     \         |
                  |  [payment-svc]  [inventory-svc]
                  |       |
             [notification-svc]  [db-primary]
                                      |
                                 [db-replica]
```

10 个微服务，11 条调用关系，支持 BFS 最短路径查询和上下游级联推导。

## 快速开始

### 环境要求

- Python 3.10+
- Anthropic API Key

### 安装

```bash
cd ops-fault-diagnosis
pip install -r requirements.txt
```

### 配置 API Key

方式一：环境变量
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

方式二：创建 `.env` 文件
```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 运行

交互模式（选择场景和速度）：
```bash
python main.py
```

直接指定场景：
```bash
python main.py -s 1              # 场景1: DB连接池耗尽级联
python main.py -s 2              # 场景2: 内存泄漏 OOM Kill
python main.py -s 3              # 场景3: 磁盘满级联
```

速度控制：
```bash
python main.py -s 1 --speed fast   # 快速模式，Agent 间无停顿
python main.py -s 1 --speed normal # 正常模式（默认），Agent 间间隔 1 秒
python main.py -s 1 --speed step   # 逐步模式，每阶段需按 Enter 继续
```

## 项目结构

```
ops-fault-diagnosis/
├── main.py                              # 入口：CLI 参数解析，启动编排器
├── requirements.txt                     # 依赖：anthropic, rich, pydantic, click, python-dotenv
├── .env.example
│
├── models/                              # Pydantic 数据模型
│   ├── alerts.py                        #   Alert, AlertSeverity, AlertBatch
│   ├── incidents.py                     #   Incident, CorrelationGroup
│   ├── topology.py                      #   ServiceTopology（含图遍历算法）
│   ├── logs.py                          #   LogEntry
│   ├── metrics.py                       #   MetricDataPoint, MetricAnomaly
│   ├── changes.py                       #   ChangeRecord
│   ├── diagnosis.py                     #   RootCauseAnalysis, FixPlan, PostIncidentReview
│   └── shared_context.py                #   SharedContext — Agent 间的共享状态
│
├── agents/                              # 4 个专业化 Agent
│   ├── base_agent.py                    #   BaseAgent 抽象类（流式调用 + 事件回调）
│   ├── alert_aggregation.py             #   Agent 1: 告警聚合
│   ├── root_cause.py                    #   Agent 2: 根因定位（长链推理）
│   ├── fix_suggestion.py                #   Agent 3: 修复建议
│   ├── post_incident.py                 #   Agent 4: 复盘报告
│   └── prompts/                         #   各 Agent 的系统提示词
│       ├── alert_aggregation.md
│       ├── root_cause.md
│       ├── fix_suggestion.md
│       └── post_incident.md
│
├── simulation/                          # 数据模拟层
│   ├── topology_builder.py              #   微服务拓扑构建
│   ├── alert_generator.py               #   告警风暴生成（含重复和噪声）
│   ├── log_generator.py                 #   日志生成（故障特征 + 正常噪声）
│   ├── metrics_generator.py             #   指标时序生成（含异常注入）
│   ├── change_generator.py              #   变更记录生成
│   └── scenarios/
│       ├── base_scenario.py             #   场景基类
│       ├── connection_pool_exhaustion.py  # 场景1: DB连接池耗尽
│       ├── memory_leak_oom.py             # 场景2: 内存泄漏 OOM
│       └── disk_full_cascade.py           # 场景3: 磁盘满级联
│
├── orchestrator/                        # 编排层
│   ├── orchestrator.py                  #   4 Agent 流水线编排
│   └── event_bus.py                     #   进程内事件总线
│
├── cli/                                 # 终端 UI
│   ├── display.py                       #   Rich 实时渲染
│   ├── theme.py                         #   颜色、头像、样式定义
│   └── interactive.py                   #   交互式场景选择菜单
│
└── utils/
    └── streaming.py                     #   Claude 流式调用 + JSON 提取
```

## 关键设计

### Agent 通信模式

Agent 间不直接调用，通过 `SharedContext` 共享状态：

```
Agent 1 → context.incidents       → Agent 2
Agent 2 → context.root_cause_analyses → Agent 3
Agent 3 → context.fix_plans       → Agent 4
Agent 4 → context.reviews
```

### 事件回调解耦

Agent 通过 `event_callback` 发出推理过程，CLI 通过 `EventBus` 订阅并实时渲染。Agent 层不依赖任何 CLI 代码。

### Prompt Caching

系统提示词启用 Anthropic 的 prompt caching，同一会话内多次调用复用缓存，降低 Token 消耗。

### 结构化输出

每个 Agent 要求 Claude 返回结构化 JSON，通过 `extract_json_block()` 处理 markdown 包裹和部分 JSON 恢复。

## CLI 效果

运行后终端将实时展示每个 Agent 的推理过程：

```
═══════════════════════════════════════════════════════
 🔍 PHASE 1  Alert Aggregation
═══════════════════════════════════════════════════════

 🔍 Alert Aggregation Agent thinking...
  > Received 51 raw alerts spanning 8 services
  > De-duplicating alerts... found 12 unique
  > Correlating by service topology...
  ✅ Result: 1 incident (51 alerts → 1 incident)

═══════════════════════════════════════════════════════
 🎯 PHASE 2  Root Cause Analysis
═══════════════════════════════════════════════════════

 🎯 Root Cause Localization Agent thinking...
  > Step 1: Tracing call chain from surface symptom...
  > Step 2: Deep diving on db-primary...
  > Step 3: Cross-referencing recent changes...
  > Step 4: Synthesizing root cause analysis...
  ✅ Root cause: payment-svc connection leak + db pool reduction
     Confidence: 92% | Evidence chain: 4 steps

... (Phase 3, Phase 4)

═══════════════════════════════════════════════════════
 INCIDENT SUMMARY DASHBOARD
═══════════════════════════════════════════════════════

  Raw Alerts          51
  Deduplicated        12
  Root Cause          db-primary
  Confidence          92%
  Fix Suggestions     3

  🔧 Rollback payment-svc to v2.3.0 and restore max_connections=200
     Risk: LOW | Confidence: HIGH
```

## Tech Stack

- **LLM**: Anthropic Claude API (claude-sonnet-4-6)
- **Language**: Python 3.10+
- **Data Models**: Pydantic v2
- **CLI**: Rich + Click
- **Architecture**: Multi-Agent + SharedContext + EventBus
