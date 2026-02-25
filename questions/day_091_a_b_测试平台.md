# 第 91 天：设计 A/B 测试平台

> 生成日期：2026-02-24

---

## 题目背景
A/B 测试平台用于帮助产品团队在生产环境中对新功能、页面布局或算法进行对照实验，通过随机分配流量到不同变体，收集关键指标并统计显著性，从而做出数据驱动的决策。

## 面试场景设定
> **面试官**：  
> “假设我们要为公司构建一个高可用、可扩展的 A/B 测试平台。请你从零开始设计整体架构，重点说明流量分配、实验管理、数据收集与分析的实现思路，并考虑系统在高并发和大数据量下的表现。”

## 功能性需求
1. **实验创建与管理**  
   - 支持 UI/API 创建实验、设置实验名称、描述、实验组（A、B、…）、权重分配、实验起止时间、目标指标等。  
   - 支持实验的暂停、终止、克隆、版本回滚。

2. **实时流量分配**  
   - 对进入系统的用户请求（如 HTTP 请求）进行快速、可配置的随机或基于属性的分流，保证实验组权重准确落地。  
   - 支持分层抽样（如先抽取用户 ID，再抽取实验组）以及分布式一致性哈希，以保证同一用户在实验期间落在同一组。

3. **指标采集与埋点**  
   - 提供 SDK（Web、iOS、Android）以及服务端埋点接口，收集自定义业务指标（点击、转化、收入等）以及平台级指标（曝光、响应时间）。  
   - 支持批量上传、实时上报两种模式。

4. **实验数据存储与分析**  
   - 自动聚合实验数据（PV、UV、转化率、累计收入等），生成实验报告。  
   - 支持显著性检验（t‑test、卡方检验）和置信区间计算，并可配置多变量实验（MVT）。

5. **权限控制与审计**  
   - 基于企业 LDAP/OAuth 实现角色（管理员、产品经理、分析师）权限划分。  
   - 记录所有实验操作日志，支持审计查询。

6. **监控与告警**  
   - 实时监控流量分配偏差、指标异常波动、系统健康状态。  
   - 当关键阈值（如实验组分配误差 > 5%）触发告警。

## 非功能性需求
| 指标 | 目标值 | 说明 |
|------|--------|------|
| **日活跃用户 (DAU)** | 10 Million | 平台需要支撑公司全部产品的日活用户访问量。 |
| **流量分配 QPS** | 30,000 QPS | 对每个请求进行实验分配的峰值吞吐量（包括 API 与 SDK 上报）。 |
| **单次分配/埋点延迟** | ≤ 30 ms | 流量分配和埋点写入的 99% 请求响应时间。 |
| **可用性** | 99.95% (每月累计停机 ≤ 22 分钟) | 关键业务（流量分配、数据上报）必须高度可用。 |
| **存储容量** | 300 TB (一年全量实验原始日志) | 包含原始埋点、实验元数据、分析结果等。 |
| **数据一致性** | 最终一致性，≤ 5 分钟内可查询到最新实验指标 | 为保证报表实时性，需在短时间内完成聚合。 |

## 系统边界
**本题范围内**  
- 实验的创建、流量分配、埋点采集、数据聚合、显著性分析以及权限/审计功能。  
- 高可用的分布式架构设计（负载均衡、缓存、消息队列、存储分层等）。  
- 监控、告警与扩缩容策略。

**不考虑**  
- 前端 UI 的具体实现细节（仅需说明交互流程）。  
- 第三方 BI 工具的可视化集成（只需提供 API/导出接口）。  
- 对接业务方的业务逻辑实现（如推荐系统的具体算法），仅关注平台层面的通用能力。  
- 法律合规（GDPR、数据脱敏）细节，只需在权限控制中提及。

## 提示与追问
1. **流量分配的一致性**  
   - “如果同一个用户在实验期间跨多个业务线请求，如何保证他始终落在同一实验组？请讨论一致性哈希 vs. Cookie/Token 方案的优缺点。”

2. **海量埋点数据的实时聚合**  
   - “在 30 k QPS 的写入压力下，如何设计数据管道（如 Kafka + Flink/Spark）以实现 5 分钟内的指标可查询？”  
   - “若出现数据倾斜（某实验组流量异常集中），你会如何处理？”

3. **容错与灾备**  
   - “当某个分区的流量分配服务节点失效时，系统如何快速切流且不影响实验分配精度？”  
   - “请说明你会如何做跨地域的灾备以及数据恢复策略。”

---  
请基于以上信息进行系统设计，阐述关键组件、技术选型、数据流向以及扩展/容错方案。祝你面试顺利！

---

# 题解

# 📘 A/B 测试平台系统设计全流程手把手教学  

> **写给**：刚入行的后端小伙伴、第一次参加系统设计面试的同学  
> **目标**：从「最小可用系统」一步步演进到「高可用、可扩展」的完整方案，过程中每一个技术选型、每一次架构折中都写明 **为什么**，帮助你在面试时有条不紊地表达。  

---  

## 目录
1. [解题思路总览](#解题思路总览)  
2. [第一步：理解需求与规模估算](#第一步理解需求与规模估算)  
3. [第二步：高层架构设计](#第二步高层架构设计)  
4. [第三步：数据库设计](#第三步数据库设计)  
5. [第四步：核心 API 设计](#第四步核心-api-设计)  
6. [第五步：详细组件设计](#第五步详细组件设计)  
7. [第六步：扩展性与高可用设计](#第六步扩展性与高可用设计)  
8. [第七步：常见面试追问与回答](#第七步常见面试追问与回答)  
9. [心得与反思](#心得与反思)  

---  

## 解题思路总览
> **核心思路**：先把系统拆成 **「实验管理」**、**「流量分配」**、**「埋点上报」**、**「实时聚合 & 分析」** 四大功能块；再围绕 **高并发、低时延、数据可靠** 三大非功能需求，分别给每块挑选最合适的技术栈与部署方式。  

**步骤拆解**  

| 步骤 | 目的 | 产出 |
|------|------|------|
| 1️⃣ 需求拆解 & 规模估算 | 明确业务边界、算出流量、存储、时延等硬指标 | QPS、DAU、存储容量、时延预算 |
| 2️⃣ 高层架构草图 | 把功能块映射到具体的服务、数据流向 | 组件图、调用链 |
| 3️⃣ 数据模型设计 | 记录实验元数据、埋点原始日志、聚合结果 | 表结构、主键/索引策略 |
| 4️⃣ API 定义 | 前端/SDK 与平台交互的入口 | REST/Proto 接口、错误码 |
| 5️⃣ 关键组件细化 | 每个服务内部如何实现（缓存、分布式一致性等） | 代码/伪码、技术选型解释 |
| 6️⃣ HA & 扩展 | 失效恢复、跨地域容灾、水平扩容方案 | 多副本、负载均衡、弹性伸缩 |
| 7️⃣ 面试追问准备 | 预演常见“如果…怎么办？”的答案 | 结构化、数据驱动的答复 |

> **为什么要这么做？**  
> - **逐层递进**：先把最小可用系统（MVP）搭起来，确保每个功能块都有明确的职责；再在此基础上逐步加「缓存」「异步化」「多活」等特性，避免一开始就设计过度、浪费时间。  
> - **新手友好**：每一步都有「为什么」的解释，帮助你在面试时不只是说「用了 Kafka」，还能阐述「因为需要高吞吐且天然支持持久化」的原因。  

---  

## 第一步：理解需求与规模估算  

### 1️⃣ 功能需求梳理（从业务角度出发）

| 大块 | 子需求 | 关键点 |
|------|--------|--------|
| 实验管理 | 创建/编辑/暂停/终止/克隆/回滚 | UI + API，需持久化实验元数据 |
| 流量分配 | 实时、权重精准、同用户一致性、属性分流 | 需要在每一次业务请求入口快速返回实验组 |
| 埋点采集 | SDK（Web、iOS、Android）+ 服务端上报，支持批量/实时 | 业务指标 + 平台指标 |
| 数据聚合 & 分析 | PV/UV/转化/收入等实时聚合，显著性检验 | 5 分钟内可查询，支持多变量实验 |
| 权限 & 审计 | LDAP/OAuth、角色划分、操作日志 | 安全合规 |
| 监控 & 告警 | 流量偏差、指标异常、系统健康 | 及时发现并处理异常 |

### 2️⃣ 非功能需求转化为数字指标  

| 指标 | 目标值 | 计算方式/来源 |
|------|--------|----------------|
| **DAU** | 10 M | 假设 1.5 B 日请求，峰值 30 k QPS |
| **流量分配 QPS** | 30 k QPS | 每次业务请求都要走分配服务 |
| **埋点写入 QPS** | 30 k QPS（上报） | 与分配 QPS 同等量级 |
| **单次分配/埋点延迟** | ≤ 30 ms (99% ≤) | 需要缓存、无锁快速路径 |
| **可用性** | 99.95%（月停机 ≤ 22 min） | 主备切换 ≤ 30 s，故障自动恢复 |
| **存储容量** | 300 TB / 年 | 估算：原始日志 2 KB/条 × 30 k QPS × 86400 s ≈ 5 TB/天 → 约 1.8 PB/年，实际会做压缩/分层，保留 300 TB 热数据 |
| **数据一致性** | 最终一致 ≤ 5 min | 实时流式聚合 + 近实时查询层 |

> **注意**：在面试里，你可以先把 **DAU、QPS、存储** 三个数字算出来，展示你有 **“从业务到技术的转化能力”**，再再说 *“我们会做压缩、冷热分层来满足 300 TB 的目标”。  

### 3️⃣ 规模估算（关键公式）  

1. **写入流量（原始日志）**  
   - 单条日志大小 ≈ 2 KB（包含 user_id、experiment_id、event_type、timestamp、属性）  
   - QPS = 30 k → 每秒写入 60 MB → **每日 ≈ 5 TB**  

2. **聚合后存储**（每日聚合结果）  
   - 每个实验 10 个指标 × 1 KB ≈ 10 KB  
   - 假设同时运行 500 个实验 → 5 MB/天 → 可忽略不计  

3. **索引需求**  
   - 常查询维度：experiment_id、user_id、event_time、group_id  
   - 需要为这些列建立 **复合索引**，以支撑快速检索与聚合。  

> **为什么要做这些估算？**  
> - 给后面的 **技术选型**（Kafka 分区数、数据库容量、缓存大小）提供硬性依据。  
> - 防止「后期性能爆炸」的尴尬情形。  

---  

## 第二步：高层架构设计  

### 1️⃣ MVP（最小可用系统）草图  

```
┌─────────────┐      ┌───────────────┐
│ 业务系统 (Web│      │ 业务系统 (App)│
│  /API)      │      │               │
└─────┬───────┘      └───────┬───────┘
      │流量分配请求            │流量分配请求
      ▼                         ▼
┌───────────────────────────────┐
│   Traffic Allocation Service   │
│   (REST + 本地缓存)            │
└───────┬─────────────┬──────────┘
        │             │
        │分配结果返回 │
        ▼             ▼
   业务代码使用   业务代码使用
   实验组 ID     实验组 ID
        │             │
        ▼             ▼
┌───────────────────────────────┐
│   埋点 SDK / 上报 API          │
│   (Batch / Real‑time)          │
└───────┬─────────────┬──────────┘
        │             │
        ▼             ▼
   Kafka Topic (event)   Kafka Topic (event)
        │                     │
        ▼                     ▼
┌───────────────────────────────┐
│   Stream Processing (Flink)    │
│   – 实时聚合（5min 窗口）      │
│   – 异常检测 & 告警           │
└───────┬─────────────┬──────────┘
        │             │
        ▼             ▼
┌─────────────────────┐   ┌─────────────────────┐
│  OLAP Store (ClickHouse)│   │  实验元数据库 (PostgreSQL)│
└─────────────┬───────┘   └───────┬───────────────┘
              │                 │
              ▼                 ▼
   API for Report / Dashboard   Auth & Audit Service
```

> **说明**  
> - **Traffic Allocation Service**：负责把每个请求映射到实验组，返回 `group_id`。实现方式采用 **本地缓存 + 一致性哈希**，确保 **≤ 30 ms** 的响应。  
> - **Kafka + Flink**：提供 **高吞吐、持久化、天然的分区** 能力；Flink 负责 **5 分钟滚动窗口聚合**，满足「≤ 5 min 可查询」的要求。  
> - **ClickHouse**：列式 OLAP，适合 **PV/UV/转化率** 这类聚合查询，查询毫秒级返回。  
> - **PostgreSQL**：存储实验元数据、权限、审计日志，事务需求较强。  

### 2️⃣ 关键技术选型背后的思考  

| 需求 | 备选技术 | 最终选型 | 选型理由 |
|------|----------|----------|----------|
| **流量分配** | 1) 直接在业务服务里实现 2) 单独的微服务 | **独立微服务 + 本地缓存** | - 解耦业务与实验平台 <br> - 可统一管理实验配置 <br> - 支持灰度发布、滚动升级 |
| **缓存** | Redis / 本地 LRU / Consul KV | **本地 LRU + 备份到 Redis** | - 本地缓存 99% 命中 → <30 ms <br> - Redis 负责失效同步、热更新 |
| **埋点上报** | 1) HTTP/HTTPS 同步 2) Kafka 异步 3) Pulsar | **Kafka** | - 高吞吐、天然分区、持久化 <br> - 社区成熟、生态完整 |
| **流处理** | Spark Streaming / Flink / Storm | **Flink** | - 低延迟、状态管理强、支持 **exactly‑once** <br> - 窗口聚合 + 事件时间处理 |
| **聚合查询** | MySQL / PostgreSQL / ClickHouse / Druid | **ClickHouse** | - 列式存储 → 高压缩比、聚合快 <br> - 支持 **INSERT … SELECT**，适合实时写入 |
| **实验元数据** | MySQL / PostgreSQL / CockroachDB | **PostgreSQL** | - 关系型事务需求（实验创建、编辑） <br> - 支持复杂查询（审计、权限） |
| **权限中心** | LDAP / OAuth2 / Keycloak | **Keycloak + LDAP** | - 统一 SSO、角色管理 <br> - 与企业已有 LDAP 对接 |
| **监控 & 告警** | Prometheus + Grafana / ELK | **Prometheus + Alertmanager** + **Grafana** | - 时间序列监控，适配 QPS、延迟 <br> - Alertmanager 支持多渠道告警 |
| **服务注册/发现** | Consul / Nacos / Eureka | **Consul** | - 支持健康检查、KV 存储（实验配置） |
| **容错/灾备** | 主从复制、跨地域多活 | **Kafka 跨集群 MirrorMaker** + **ClickHouse 多副本** | - 保证数据不丢、查询可跨地域读取 |

---  

## 第三步：数据库设计  

### 1️⃣ 实验元数据库（PostgreSQL）  

| 表名 | 说明 | 关键字段 | 索引 |
|------|------|----------|------|
| `experiments` | 实验基本信息 | `id PK`, `name`, `description`, `status`, `start_time`, `end_time`, `created_by` | `idx_status`, `idx_time_range` |
| `experiment_groups` | 每个实验的变体（A/B/…） | `id PK`, `experiment_id FK`, `group_name`, `weight` | `idx_experiment_id` |
| `experiment_metrics` | 目标指标定义 | `id PK`, `experiment_id FK`, `metric_name`, `metric_type` (counter/float) | `idx_experiment_id` |
| `experiment_audit` | 操作日志 | `id PK`, `experiment_id FK`, `op_type`, `op_user`, `op_time`, `detail JSONB` | `idx_experiment_id`, `idx_op_time` |
| `users_roles` | 权限映射 | `user_id PK`, `role` (admin/pm/analyst) | `idx_role` |

> **为什么使用 PostgreSQL？**  
> - 需要 **事务**（实验创建、组权重更新必须原子）  
> - 支持 **JSONB**（审计日志灵活存储）  
> - 社区成熟，易于与 **Keycloak** 进行关联  

### 2️⃣ 原始埋点日志（Kafka + ClickHouse）  

**Kafka Topic 结构（ProtoBuf）**  

```proto
message EventLog {
  string event_id = 1;          // UUID
  string user_id = 2;           // 全局唯一
  string experiment_id = 3;     // 所属实验
  string group_id = 4;          // 实验变体
  string event_type = 5;        // click / conversion / revenue …
  map<string, string> props = 6; // 自定义属性（device, country …）
  int64 timestamp = 7;          // ms epoch
}
```

**ClickHouse 表**（分区、TTL、压缩）  

```sql
CREATE TABLE ab_test_events (
    event_id   String,
    user_id    String,
    experiment_id String,
    group_id   String,
    event_type LowCardinality(String),
    props      Nested(key String, value String),
    ts         DateTime64(3, 'UTC')
) 
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ts)               -- 每天一个分区，便于 TTL 删除
ORDER BY (experiment_id, group_id, ts)    -- 适合实验/组维度聚合
TTL ts + INTERVAL 180 DAY DELETE;         -- 保留 180 天热点数据，之后冷数据可压缩或迁移
```

> **为什么使用 ClickHouse 而不是 Hive/Impala？**  
> - **查询延迟**：ClickHouse 在秒级聚合上比 Hive 快 10‑100 倍，满足「5 分钟内可查询」的需求。  
> - **压缩率**：列式存储对相同实验_id、group_id 的重复值压缩极好，节省存储。  

### 3️⃣ 聚合结果表（ClickHouse）  

```sql
CREATE TABLE ab_test_metrics (
    experiment_id String,
    group_id      String,
    window_start DateTime64(3, 'UTC'),
    window_end   DateTime64(3, 'UTC'),
    metric_name  LowCardinality(String),
    metric_value Float64,
    user_cnt     UInt64,
    event_cnt    UInt64
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(window_start)
ORDER BY (experiment_id, group_id, metric_name, window_start);
```

> **SummingMergeTree** 自动对相同键做 **sum**，适合 Flink 按窗口写入后再聚合。  

---  

## 第四步：核心 API 设计  

> **原则**：RESTful + JSON（便于前端与 SDK 调用），关键路径使用 **ProtoBuf + gRPC**（内部服务间）提升性能。  

### 1️⃣ 实验管理 API（对外）  

| 方法 | 路径 | 请求体 | 响应体 | 说明 |
|------|------|--------|--------|------|
| `POST` | `/api/v1/experiments` | `{name, description, groups:[{name, weight}], start_time, end_time, metrics:[...]}` | `{experiment_id}` | 创建实验 |
| `GET` | `/api/v1/experiments/{id}` | — | `ExperimentDetail` | 查询实验详情 |
| `PATCH` | `/api/v1/experiments/{id}` | `{status, groups, metrics}` | `{}` | 更新（暂停、终止、权重） |
| `POST` | `/api/v1/experiments/{id}/clone` | `{new_name, start_time}` | `{new_experiment_id}` | 克隆 |
| `GET` | `/api/v1/experiments/{id}/audit` | — | `[AuditLog]` | 查看审计日志 |

**错误码示例**  

| Code | 含义 |
|------|------|
| 4000 | 参数校验错误 |
| 4001 | 权重总和不等于 100% |
| 4030 | 权限不足 |
| 4040 | 实验不存在 |
| 5000 | 系统内部错误 |

### 2️⃣ 流量分配 API（内部，供业务系统调用）  

**使用 gRPC**（低时延、二进制）  

```proto
service TrafficAllocation {
  // 根据用户属性返回实验组
  rpc GetGroup (AllocationRequest) returns (AllocationResponse);
}

message AllocationRequest {
  string user_id = 1;
  map<string, string> attributes = 2; // 如 device, country, version
}

message AllocationResponse {
  string experiment_id = 1;
  string group_id = 2;
  string reason = 3; // 如 "hash_match", "attribute_rule"
}
```

- **缓存**：业务服务在第一次调用时会把返回的 `experiment_id+group_id` 缓存到本地 LRU，后续直接读取，**避免再次网络往返**。  
- **一致性**：如果实验配置发生变化，**Consul KV** 会推送 **配置版本号**，本地缓存失效后重新拉取。  

### 3️⃣ 埋点上报 API（对外）  

| 方法 | 路径 | 请求体 | 响应体 | 说明 |
|------|------|--------|--------|------|
| `POST` | `/api/v1/events/batch` | `[EventLog]` (JSON 或 protobuf) | `{accepted: n, rejected: m}` | 批量上报（推荐） |
| `POST` | `/api/v1/events` | `EventLog` | `{status: "ok"}` | 实时上报（低频） |

> **实现**：API 层仅做 **合法性校验** → 直接写入 **Kafka**（生产者异步批量发送），返回 `202 Accepted`，保证 **≤ 30 ms** 的响应。  

### 4️⃣ 报表查询 API（对外）  

| 方法 | 路径 | 请求体 | 响应体 | 说明 |
|------|------|--------|--------|------|
| `GET` | `/api/v1/reports/{experiment_id}` | `?group=&metric=&start=&end=` | `ReportResult` | 实时查询聚合指标 |
| `GET` | `/api/v1/reports/{experiment_id}/significance` | `?alpha=0.05` | `SignificanceResult` | 返回 t‑test / 卡方检验结果 |

**返回示例**（JSON）  

```json
{
  "experiment_id": "exp_20240401_01",
  "group_metrics": [
    {
      "group_id": "A",
      "pv": 123456,
      "uv": 54321,
      "conversion": 0.043,
      "revenue": 1234.56
    },
    {
      "group_id": "B",
      "pv": 124000,
      "uv": 54500,
      "conversion": 0.050,
      "revenue": 1300.00
    }
  ],
  "significance": {
    "metric": "conversion",
    "p_value": 0.012,
    "significant": true,
    "confidence_interval": [0.004, 0.012]
  }
}
```

---  

## 第五步：详细组件设计  

下面把每个关键块拆解为 **内部子模块**，并解释「为什么」采用该实现方式。  

### 1️⃣ Traffic Allocation Service  

#### 1.1 架构图  

```
┌───────────────────────┐
│  Consul KV (Config)   │
│   - experiment cfg    │
│   - version token    │
└───────▲───────▲───────┘
        │       │
        │       │
┌───────┴───────┴───────┐
│  Traffic Allocation   │
│  Service (Go/Java)   │
│  + HTTP(gRPC)入口    │
│  + 本地 LRU Cache    │
│  + 一致性哈希模块    │
│  + 属性规则引擎      │
└───────▲───────▲───────┘
        │       │
        │       │
   业务服务    业务服务
  (Web,API)   (App)
```

#### 1.2 工作流程  

1. **启动时**：从 Consul 拉取所有实验配置，生成 **版本号**（如 `v20240401_001`），放入 **本地 LRU**。  
2. **请求进来**：  
   - 读取 `user_id`、业务属性。  
   - **先检查本地缓存**：若命中返回 `experiment_id+group_id`。  
   - **未命中** → 进入 **分配算法**：  
     - **属性规则**（如 `country=US` → 实验 X）优先匹配。  
     - 若无属性匹配，则使用 **一致性哈希**：`hash(user_id + experiment_version) % 10000` 与组权重映射。  
   - 将结果写入 **本地 LRU**（TTL = 5 min），返回给业务。  
3. **实验配置变更**：Consul 触发 **Watch**，服务收到 `config_version` 更新，清空对应实验的本地缓存，使后续请求重新计算。  

#### 1.3 一致性哈希实现要点  

| 步骤 | 代码伪例（Go） | 说明 |
|------|----------------|------|
| 1. 计算 hash | `h := murmur3.Sum64([]byte(userID + version))` | MurmurHash 快速且分布均匀 |
| 2. 归一化到 0‑10000 | `slot := int(h % 10000)` | 方便与权重（千分比）比较 |
| 3. 权重映射 | `cum := 0; for _, g := range groups { cum += g.Weight; if slot < cum { return g.ID } }` | 权重总和应为 10000（即 100%） |

**为什么不直接用 Cookie/Token？**  

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Cookie / Token** | 客户端持久，跨请求自然保持一致 | 1️⃣ 需要前端改动并保证安全；2️⃣ 跨业务线（不同域名）难统一；3️⃣ 失效或被清除导致重新分配 |
| **一致性哈希 + 本地缓存** | 完全后端控制，无需改动客户端；可以在分布式环境下保证 **相同 user_id** 在同一实验版本中映射相同组；失效只影响局部缓存 | 需要保证 hash 函数与权重映射的 **确定性**；在实验配置升级时会导致一次全量「重新分配」——这正是我们希望的（新实验版本） |

### 2️⃣ 埋点上报服务  

#### 2.1 架构  

```
┌───────────────────────────────┐
│   Ingress (NGINX/Envoy)        │
│   - TLS termination            │
│   - Rate limiting (IP, QPS)    │
└───────▲───────────────▲───────┘
        │               │
        │ HTTP/HTTPS   │ gRPC (proto)
┌───────┴───────┐ ┌─────┴─────┐
│  Event API    │ │  Event API │
│  (REST)       │ │ (gRPC)    │
└───────▲───────┘ └─────▲─────┘
        │               │
        ▼               ▼
   Kafka Producer  Kafka Producer
        │               │
        ▼               ▼
   Kafka Topic (events) (same topic)
```

#### 2.2 关键实现  

- **批量写入**：业务 SDK 按 **N 条**（默认 20 条）或 **时间窗口**（100 ms）一次性发送，降低网络次数。  
- **异步 Producer**：使用 **Kafka Producer** 的 **batch.size**、**linger.ms** 参数，内部自动合并，同一分区的记录会一次性刷盘，提升吞吐。  
- **幂等性**：开启 **Kafka 幂等生产者**（`enable.idempotence=true`），防止网络重试导致的重复埋点。  
- **数据校验**：API 层仅做 **Schema 验证**（字段必填、时间合法），不做业务聚合，保持 **低延迟**。  

#### 2.3 为什么不用直接写 DB？  

| 方案 | 优点 | 缺点 |
|------|------|------|
| **直接写入 MySQL/ClickHouse** | 简单、即写即查 | 1️⃣ 写入压力大（30 k QPS）导致 DB 成本爆炸；2️⃣ 没有天然的 **持久化缓冲**，一旦 DB 瞬时不可用会丢数据 |
| **Kafka + Flink** | 高吞吐、持久化、天然的 **背压**，可以 **离线/实时** 双模式 | 增加系统复杂度，需要维护 Kafka 集群 |  

### 3️⃣ 实时流处理（Flink）  

#### 3.1 处理流程  

1. **Source**：Kafka Consumer（`events` topic），使用 **exactly‑once** 语义（`checkpointing`）。  
2. **KeyBy**：`keyBy(experiment_id, group_id, metric_name)` → 确保同一实验组的相同指标在同一 task 中聚合。  
3. **Window**：**滚动窗口** 5 min，**事件时间**（`timestamp`） + **Watermark**（延迟 2 min）  
4. **Aggregation**：自定义 `AggregateFunction` 计算 **PV、UV、转化次数、收入总和**，同时维护 **去重 UV**（使用 **HyperLogLog**）  
5. **Sink**：写入 ClickHouse（`ab_test_metrics`）+ **报警**（若分配偏差 > 5%）  

#### 3.2 关键代码（简化）  

```java
DataStream<EventLog> source = env
    .addSource(new FlinkKafkaConsumer<>(topic, new ProtobufDeserializationSchema<>(), props))
    .assignTimestampsAndWatermarks(
        WatermarkStrategy.<EventLog>forBoundedOutOfOrderness(Duration.ofMinutes(2))
            .withTimestampAssigner((e, ts) -> e.getTimestamp()));

source
    .keyBy(e -> Tuple3.of(e.getExperimentId(), e.getGroupId(), e.getEventType()))
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .aggregate(new MetricAggregator(), new MetricWindowFunction())
    .addSink(new ClickHouseSink(...));
```

- **MetricAggregator**：累计 `event_cnt`，使用 `HyperLogLog` 计 `uv`，对 `revenue` 进行 sum。  
- **MetricWindowFunction**：把窗口起止时间、实验/组信息拼装成 ClickHouse 写入结构。  

#### 3.3 为什么选 Flink 而不是 Spark Structured Streaming？  

| 特性 | Flink | Spark Structured Streaming |
|------|------|----------------------------|
| **低延迟** | < 1 s（因为是流式） | 通常 2‑5 s（micro‑batch） |
| **状态一致性** | 原生 **exactly‑once** checkpoint | 需要额外配置两阶段提交 |
| **窗口灵活** | 支持 event‑time、session、滚动、滑动等 | 也支持，但实现上稍繁琐 |
| **生态** | 与 Kafka、ClickHouse、Prometheus 集成成熟 | 生态同样丰富但在实时指标场景不如 Flink 主流 |

### 4️⃣ 聚合查询层（ClickHouse）  

- **查询 API**：通过 **RESTful**（FastAPI/Go Gin）包装 ClickHouse SQL，做 **权限过滤**（只能查询自己有权限的实验）。  
- **缓存**：热点报告（如当天实验）放入 **Redis**，TTL 30 s，减轻 ClickHouse 并发查询压力。  

#### 示例查询 SQL  

```sql
SELECT
    group_id,
    sumIf(event_cnt, event_type = 'pv') AS pv,
    uniqExactIf(user_id, event_type = 'pv') AS uv,
    sumIf(event_cnt, event_type = 'conversion') / sumIf(event_cnt, event_type = 'pv') AS conversion_rate,
    sumIf(metric_value, event_type = 'revenue') AS revenue
FROM ab_test_events
WHERE experiment_id = 'exp_20240401_01'
  AND ts BETWEEN toDateTime('2024-04-01 00:00:00')
              AND toDateTime('2024-04-01 23:59:59')
GROUP BY group_id;
```

### 5️⃣ 权限、审计、监控  

| 模块 | 技术 | 关键点 |
|------|------|--------|
| **认证** | Keycloak + LDAP | SSO、OAuth2 token、角色映射 |
| **授权** | RBAC（基于实验/业务线） | API gateway 检查 `role` → 只允许对应实验的 CRUD |
| **审计** | PostgreSQL `experiment_audit` 表 + ElasticSearch | 实时写入审计日志 → Kibana 进行搜索 |
| **监控** | Prometheus (exporter) + Grafana | QPS、latency、error rate、Kafka lag、Flink checkpoint latency |
| **告警** | Alertmanager + PagerDuty | 阈值：`allocation_error_rate > 0.5%`、`group_weight_deviation > 5%`、`clickhouse query latency > 200ms` |

---  

## 第六步：扩展性与高可用设计  

### 1️⃣ 高可用（HA）设计要点  

| 场景 | 失效点 | 备份/容错方案 |
|------|--------|----------------|
| **Traffic Allocation Service** | 单实例宕机 | 多副本部署在不同机器，使用 **Consul health check** 自动剔除失效节点；**LVS / Nginx** 负载均衡。 |
| **Kafka** | 分区 Leader 失效 | 每个分区 **replication factor = 3**，自动选举新 Leader。 |
| **Flink** | Job Manager 故障 | **High‑availability mode**（Zookeeper/HA‑ZooKeeper）保存 checkpoint，Job Manager 自动恢复。 |
| **ClickHouse** | 节点宕机 | **Distributed** 表 + **ReplicatedMergeTree**，查询会自动路由到存活副本。 |
| **PostgreSQL** | 主库故障 | **Streaming Replication** + **Patroni** 自动故障转移。 |
| **跨地域灾备** | 整个机房失效 | - **双活部署**（北京 & 上海）<br>- **Kafka MirrorMaker** 将日志同步至备份集群<br>- **ClickHouse** 使用 **replicated distributed** 跨地域复制（异步）<br>- **DNS 轮询 + 健康检查** 将流量切到备份机房，切换时间 ≤ 30 s |

### 2️⃣ 横向扩容（Scale‑out）  

| 组件 | 扩容维度 | 关键指标 |
|------|----------|----------|
| **Traffic Allocation** | **水平扩容**（增加实例） | QPS 线性提升；Consul 自动发现新实例 |
| **Kafka** | **分区数**、**Broker 数** | 通过 **topic partitions = 30 k QPS / 10 k per partition** ≈ 3 分区/秒，实际设 100 分区，保证每个分区的写入 ≤ 3 k QPS |
| **Flink** | **Task Manager**（CPU+内存） | 任务并行度 = 分区数；每 1 GB 内存可处理约 5 k QPS |
| **ClickHouse** | **节点**（Shard）+ **Replica** | 按数据量（TB）水平拆分；每个节点磁盘 IOPS ≥ 5000 |
| **Redis** | **分片**（Cluster） | QPS 30 k → 3 k/实例，设 10 节点集群 |

### 3️⃣ 数据倾斜处理  

- **现象**：某实验组流量异常集中导致对应 Kafka 分区或 Flink task 负载过高。  
- **应对**：  
  1. **预先均衡分区**：使用 **`experiment_id + group_id`** 作为 Kafka **Key**，确保同一实验组的数据落在同一分区，但在实验创建时 **对实验进行 hash**，把实验 ID 重新映射到多个 **逻辑分区**（比如 `hash(experiment_id) % N`），避免单实验占满一个分区。  
  2. **Flink 动态重分配**：开启 **rebalance()**，让 Flink 在检测到某个 task CPU > 80% 时自动 **repartition**。  
  3. **热点实验限流**：在 Traffic Allocation Service 对异常实验组返回 **“已满”**（或降权），并发送告警。  

### 4️⃣ 监控与自动化运维（SRE）  

- **仪表盘**：  
  - **Traffic Allocation**：请求数、错误率、缓存命中率、分配偏差（实际 vs. 配置）  
  - **Kafka**：Lag、吞吐、磁盘使用、ISR 数量  
  - **Flink**：Checkpoint 成功率、处理延迟、task 健康状态  
  - **ClickHouse**：查询 QPS、慢查询、磁盘 I/O  
- **自动伸缩**（K8s HPA / 自研 Autoscaler）：  
  - **Traffic Allocation**：CPU > 70% → 增 replica  
  - **Kafka**：Broker 磁盘使用 > 70% → 添加 broker 并扩分区  
  - **Flink**：TaskManager CPU > 80% → 增 TaskManager  
- **灾难恢复演练**：每月一次 **故障注入**（关闭单个 broker、kill traffic service），验证自动切换时间 < 30 s。  

---  

## 第七步：常见面试追问与回答  

> **提示**：面试官往往会围绕「一致性」「性能瓶颈」「容灾」等点追问。下面给出结构化答案模板，帮助你快速组织语言。  

### 1️⃣ “如果同一个用户跨业务线请求，如何保证实验组一致？”  

**答案框架**  

1. **需求**：同一 `user_id` 在实验期间必须落在同一组，避免实验偏差。  
2. **方案**：  
   - **一致性哈希 + 实验版本号**：`hash(user_id + experiment_version)` → **确定的 slot** → 与权重映射。  
   - **本地缓存**：第一次计算后把 `user_id → group_id` 放在业务服务本地 LRU，后续请求直接读取，**不依赖 Cookie**。  
3. **对比 Cookie/Token**：  
   - Cookie 需要前端配合，跨域、失效、被清除的问题。  
   - Token 需要统一的签发中心，且会增加业务层的复杂度。  
4. **容错**：实验配置更新时，版本号变化导致 **重新计算**，这正是我们想要的“新实验生效”。  
5. **扩展**：如果业务要求 **跨地域保持一致**，可以把 `user_id` 的 hash 结果存到 **全局 KV（Consul）**，但成本与延迟要权衡。  

### 2️⃣ “30 k QPS 的埋点写入，如何保证 5 分钟内可查询？”  

**答案要点**  

- **Kafka 充当持久化缓冲**：生产者异步批量发送，`linger.ms=50`、`batch.size=64KB`，保证高吞吐且不丢数据。  
- **Flink 实时流处理**：使用 **event‑time窗口**（5 min）进行聚合，checkpoint 每 30 s，**exactly‑once**，因此 **5 min 内聚合结果已落库**。  
- **ClickHouse**：列式写入极快，聚合查询在毫秒级完成。  
- **监控**：通过 Kafka lag 与 Flink checkpoint 延迟监控，确保 **lag ≤ 2 min**；若超过阈值，自动报警并可临时切换到 **批处理（Spark）** 补齐缺失窗口。  

### 3️⃣ “流量分配服务节点失效，如何快速切流且不影响实验精度？”  

**答案结构**  

1. **服务发现 + 健康检查**：使用 **Consul** 注册每个 Traffic Allocation 实例，定时健康检查（HTTP/200）。  
2. **负载均衡**：前端采用 **LVS/Nginx**（Layer 4）或 **Envoy**（Layer 7）做轮询 + 健康检查，失效节点自动剔除。  
3. **缓存失效**：每个实例本地 LRU 与全局 Consul KV 保持 **版本号**，失效后新实例会重新加载配置，**保证分配逻辑一致**。  
4. **数据一致性**：因为分配是 **无状态**（只读实验配置），新实例只要拿到最新配置，即可保持 **权重误差 ≤ 0.1%**。  
5. **故障恢复**：实例恢复后自动重新加入 pool，Consul 会把最新的配置推送。  

### 4️⃣ “跨地域灾备怎么做？数据恢复时如何保证不丢失？”  

**答案要点**  

- **双活部署**：北京、上海两套完整系统（Traffic, Kafka, Flink, ClickHouse, PostgreSQL）。  
- **数据同步**：  
  - **Kafka MirrorMaker** 将所有 `events` 主题异步复制到备份集群，**复制延迟 ≤ 1 min**。  
  - **ClickHouse** 使用 **ReplicatedMergeTree** + **distributed**，每个 shard 在两个地域都有副本（异步复制），保证查询可从任意副本读取。  
  - **PostgreSQL** 采用 **Logical Replication** → 备库实时同步实验元数据。  
- **故障切换**：  
  - DNS TTL 设置为 30 s，故障时将域名指向备份机房的 LB。  
  - 客户端 SDK 通过 **配置中心** 获取最近的实验版本号，自动切换到备份流量分配服务。  
- **恢复**：故障恢复后，使用 **Kafka 重放**（保留 7 天）把未消费的日志重新写入 Flink，保证 **0 数据丢失**。  

### 5️⃣ “如果某实验组流量异常集中导致热点怎么办？”  

**答案要点**  

- **前置均衡**：在实验创建时，对 **experiment_id** 做 hash，**分配到多个 Kafka 分区**（`key = hash(experiment_id) % partition_num`），避免单实验占满一个分区。  
- **Flink 重分区**：使用 `rebalance()` 或 `rescale()` 动态调度任务，确保热点任务可以迁移到空闲节点。  
- **业务侧限流**：Traffic Allocation Service 在检测到某组 **实际流量/权重偏差 > 5%** 时，返回 **降权**（临时把权重调低），并发送告警。  
- **监控**：实时统计每组的 QPS，若单组 QPS > 2×平均，则触发自动扩容或降权。  

---  

## 心得与反思  

### 1️⃣ 本题最难的设计决策  

| 决策 | 思考过程 |
|------|----------|
| **流量分配的一致性实现** | 必须在 **毫秒级** 内返回，同时保证 **跨业务线、跨机房** 的同一用户一致。<br>① 初始想法是用 **Cookie**，但发现跨域、被清除、隐私合规是大坑。<br>② 再考虑 **中心化 Redis**，但每次查询都要网络往返，难满足 ≤ 30 ms。<br>③ 最终选择 **一致性哈希 + 本地 LRU**，把“一致性”放在 **哈希函数**，把“快”放在 **本地缓存**，兼顾了时延、可扩展性与容错。 |
| **实时聚合的技术选型** | 需要 **30 k QPS** 的写入，且 **5 分钟内** 能查询。<br>① Spark Structured Streaming 延迟 2‑5 s，算可以，但 **checkpoint + exactly‑once** 实现更复杂。<br>② Flink 原生支持 **event‑time窗口**、**exactly‑once**，且在 **Kafka** 上的 **Back‑pressure** 能自动控制流速，最适合。<br>③ 选 ClickHouse 作为 OLAP，原因是 **列式压缩 + 高并发聚合**，比传统关系型 DB 更符合大数据查询。 |

### 2️⃣ 新手最容易犯的错误（至少两条）  

| 错误 | 说明 | 如何避免 |
|------|------|----------|
| **把流量分配写成有状态的中心化服务** | 把每个用户的实验组保存在数据库或缓存中，导致 **单点瓶颈**、**扩容困难**。 | 采用 **无状态** + **哈希** 的方式，只在 **配置中心** 保存实验元数据；业务侧本地缓存即可。 |
| **直接把埋点写入关系型数据库** | QPS 30 k 会把 MySQL/PostgreSQL 推到 **磁盘 I/O** 瓶颈，成本高、可用性差。 | 使用 **Kafka** 作为持久化缓冲，再由 **流处理** 写入列式 OLAP（ClickHouse）或大数据存储。 |
| **忽视数据倾斜** | 只按 `experiment_id` 做分区，某实验组流量突增会导致单分区卡顿。 | 在 **Kafka** 生产时使用 **`hash(experiment_id + group_id)`** 作为 key，或者对实验做 **二次哈希**，再结合 **Flink 动态重分配**。 |
| **监控只看 CPU** | 只监控 CPU、内存，忽视 **Kafka lag、Flink checkpoint 延迟、分配偏差**，故障时难以定位。 | 设计 **全链路监控仪表盘**，包括业务指标、系统指标、异常告警阈值。 |

### 3️⃣ 学习建议与可延伸方向  

1. **基础功**：  
   - 熟悉 **分布式系统的 CAP 与 BASE**，理解 *强一致*、*最终一致* 的 trade‑off。  
   - 掌握 **HTTP、REST、gRPC** 的基本设计原则。  
2. **核心技术**：  
   - **Kafka**：了解 Producer/Consumer、分区、ISR、Exactly‑once 语义。  
   - **Flink**：熟悉 DataStream API、Window、State、Checkpoint。  
   - **ClickHouse**：列式存储概念、MergeTree、分区、TTL。  
   - **Consul / Etcd**：服务注册、KV 配置中心。  
3. **实验平台业务**：  
   - 学习 **A/B 测试的统计学**（t‑test、卡方检验、贝叶斯方法），在面试中可以展示对「显著性」的深入理解。  
   - 了解 **实验指标的定义**（曝光、点击、转化、收入），以及 **去重 UV** 的实现（HyperLogLog）。  
4. **实战练习**：  
   - 用 **Docker Compose** 搭建 **Kafka + Flink + ClickHouse** 小集群，跑一套 **模拟埋点 → 实时聚合** 的 demo。  
   - 实现一个 **Traffic Allocation Service**（Go/Java），尝试 **本地 LRU + Consul** 配置热更新。  
5. **进一步阅读**：  
   - 《Designing Data‑Intensive Applications》 – 章节：流式系统、分区、容错。  
   - 《Principles of Distributed Machine Learning》 – 了解实验平台在机器学习模型迭代中的角色。  
   - 官方文档：Kafka、Flink、ClickHouse、Consul、Keycloak。  

> **一句话总结**：  
> 设计 A/B 测试平台的核心是 **“让实验分配既快速又一致，让埋点既可靠又可实时聚合”**。围绕这两大目标，逐层引入 **缓存、异步管道、列式存储、自动化运维**，即可构建出满足 **高可用、可扩展** 的系统。祝你面试顺利，早日成为平台级架构师！ 🚀
