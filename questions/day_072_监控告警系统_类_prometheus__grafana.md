# 第 72 天：设计 监控告警系统（类 Prometheus + Grafana）

> 生成日期：2026-03-15

---

# 监控告警系统设计题（类 Prometheus + Grafana）

## 题目背景
监控告警系统用于实时采集、存储、查询大规模时序指标，并提供可视化仪表盘与灵活的告警规则。业务团队依赖它快速定位故障、评估容量并进行容量规划。

## 面试场景设定
> **面试官**：  
> “假设我们要在公司内部搭建一套类似 Prometheus + Grafana 的监控告警平台，请你从零开始设计整体架构。请先说明系统的核心模块以及它们之间的交互，然后逐步展开细节。”

## 功能性需求
1. **时序数据采集**  
   - 支持 Pull（HTTP/HTTPS）和 Push（Pushgateway）两种方式，能够对数十万台机器的数千个指标进行抓取。  
2. **高效存储与压缩**  
   - 将采集到的时序数据以列式/块压缩方式持久化，支持基于标签的快速检索。  
3. **查询与可视化**  
   - 提供类似 PromQL 的查询语言，支持聚合、子查询和跨时间范围的计算，结果能够在 Grafana‑style 的仪表盘中实时展示。  
4. **告警规则引擎**  
   - 支持基于阈值、百分位、预测模型等多种告警条件，能够对符合条件的时间序列触发告警并通过 webhook、邮件、短信等渠道发送。  
5. **多租户与权限管理**  
   - 不同业务团队之间的数据隔离，支持基于角色的访问控制（只读/编辑/管理员）。  
6. **数据保留与降采样**  
   - 自动对历史数据进行降采样（如 1m → 5m → 1h），并在保留期限到达后删除或归档。

## 非功能性需求（带具体数字估算）
| 指标 | 目标值 | 备注 |
|------|--------|------|
| **每日活跃指标数（DAU）** | 10 M 条 | 包括业务自定义指标 |
| **查询 QPS** | 2 000 QPS（峰值） | 95% 在 500 QPS 以下 |
| **写入吞吐** | 500 k 次写入/秒（每次约 1 KB） | 对应约 500 GB/天原始数据 |
| **查询延迟** | 99th 百分位 < 200 ms | 包括聚合、跨时间范围 |
| **系统可用性** | 99.9%（月度） | 包括采集、存储、查询三大块 |
| **存储容量** | 100 TB/个月（压缩后） | 支持 12 个月滚动存储，旧数据归档至冷存储 |

> **注**：以上数字基于假设的企业级规模，可根据实际业务规模做适度上下调。

## 系统边界
**本题范围内**（需要考虑设计实现）  
- 时序数据的采集、存储、压缩、查询与告警全流程。  
- 多租户数据隔离、权限控制与仪表盘渲染。  
- 高可用部署、水平扩展与故障恢复方案。

**本题范围外**（不必详细设计）  
- 底层硬件选型（如具体服务器型号、网络拓扑）。  
- 与外部监控系统（如 OpenTelemetry、Zipkin）的统一采集。  
- 复杂的机器学习预测模型（仅需留出扩展口）。  
- 具体的 UI/UX 细节实现（仅需说明交互层的功能即可）。

## 提示与追问
1. **数据压缩与查询性能的平衡**  
   - “如果我们把压缩比提升到 80%，会对查询延迟产生怎样的影响？你会怎么设计索引或缓存来缓解？”  

2. **告警去抖动与沉默（Silencing）机制**  
   - “在高频波动的指标上，如何防止告警风暴？请描述你会加入哪些去抖动/抑制策略？”  

3. **水平扩展与一致性**  
   - “面对写入吞吐突增（例如全公司同步部署新特性导致瞬时写入 2×），你会如何在不牺牲数据一致性的前提下扩容存储层？”  

---

# 题解

# 监控告警系统设计（类 Prometheus + Grafana）  

> **适读对象**：刚入行的后端同学，几乎没有系统设计经验。  
> **目标**：从最小可用系统（MVP）一步步构建到满足题目中 **功能性 + 非功能性** 要求的完整分布式平台，并解释每一步“为什么”。  

> **写作风格**：手把手、层层递进、概念加粗、关键点用列表/表格呈现，便于复盘。  

---  

## ## 解题思路总览  

1. **先把需求拆成“必备”与“可选”。**  
   - 必备：采集、写入、压缩存储、查询（PromQL）、告警、权限。  
   - 可选（后期再迭代）：多租户细粒度隔离、冷热分层、机器学习预测、Grafana 完整 UI。  

2. **用“最小可用系统（MVP）”** 验证思路：  
   - 单节点 **Prometheus** + **Grafana**（开源） 能跑通采集‑写‑查‑告警。  
   - 在此基础上，**抽象出每个模块的职责**，为后面水平扩展留接口。  

3. **围绕“瓶颈”逐层扩容**：  
   - **写入吞吐** → 需要分片的时序存储（TSDB）+ 多写入入口（Agent/Remote‑Write）。  
   - **查询 QPS / 延迟** → 建立查询路由、查询缓存、索引优化。  
   - **高可用** → 主备/多副本、故障转移、数据同步。  

4. **把每个非功能需求量化**（容量、QPS、延迟），并据此选型（压缩算法、块大小、网络协议）。  

5. **在每一步都回答“如果不这么做会怎样”。** 这样在面试时能自然展示风险意识。  

下面依次展开。  

---  

## ## 第一步：理解需求与规模估算  

### 1. 功能性需求梳理  

| 功能 | 核心点 | 对应模块 |
|------|--------|----------|
| 时序数据采集 | Pull (HTTP) + Push (Pushgateway) | **Scrape Manager / Pushgateway** |
| 高效存储与压缩 | 列式/块压缩、标签检索 | **TSDB（时序数据库）** |
| 查询 & 可视化 | PromQL、聚合、跨时间窗口 | **Query Engine + Grafana** |
| 告警规则引擎 | 阈值/百分位/预测、Webhook、抑制 | **Alert Manager** |
| 多租户 & 权限 | 数据隔离、RBAC | **Authz Service** |
| 数据保留 & 降采样 | 自动降采样、TTL 删除 | **Compaction + Down‑sample Service** |

### 2. 非功能性需求量化（基于题目给的数字）  

| 指标 | 计算方式 | 结果 | 备注 |
|------|----------|------|------|
| **每日写入量** | 500 k 写入/秒 × 1 KB ≈ 500 GB/天 | 500 GB 原始 | 需压缩到 100 TB/个月 ≈ 3.3 TB/天 |
| **压缩率** | 3.3 TB / 0.5 TB ≈ **6.6×** (≈ 85% 压缩) | 与题目 80% 目标相符 | 采用 **GORILLA / Gorilla+Snappy** 等 |
| **每日活跃指标** | 10 M 条 | 约 10 M * 8 bytes(label) ≈ 80 MB 元数据 | 需要高效的 **标签索引** |
| **查询 QPS** | 峰值 2 k QPS，95% ≤ 500 QPS | 需要 **查询路由 + 缓存** | 采用 **查询层水平扩展** |
| **查询延迟** | 99th < 200 ms | 需要 **块查询 + 并行聚合** | 需要 **CPU 与内存足够** |
| **存储容量** | 100 TB/个月压缩后 | 约 3.3 TB/天 | 需要 **冷热分层**（热 30 TB，冷 70 TB） |

### 3. 关键约束  

1. **写入突增**（2×） → 必须 **弹性扩容**，写入路径不成为单点。  
2. **多租户隔离** → **租户 ID** 必须作为标签参与分片，防止跨租户查询。  
3. **高可用 99.9%** → 单点故障容忍时间 ≤ 43 分钟/天。  

---  

## ## 第二步：高层架构设计  

### 1. 结构概览（从左到右）  

```
[采集层] --> [写入入口层] --> [时序存储层] --> [查询/分析层] --> [可视化/告警层]
```

#### 1.1 采集层  

- **Scrape Manager**（Pull）  
  - 负责周期性 HTTP GET 抓取目标 `/metrics`。  
  - 支持 **自适应调度**（动态发现、负载均衡）。  

- **Pushgateway**（Push）  
  - 短暂/批量任务（CI、Job）Push 指标。  
  - 为 **短暂任务** 提供可靠的缓冲区。  

#### 1.2 写入入口层  

- **Remote Write API**（HTTP/2 + protobuf）  
  - 所有采集节点（Prometheus 实例或自研 Agent）将压缩后的样本批量发送。  
  - **负载均衡**：使用 **Consistent Hash** 将写入请求路由到对应的 **TSDB Shard**。  

- **Ingress Service**（可选）  
  - 统一的 **gRPC** 接口，做 **身份校验、租户映射、流量整形**。  

#### 1.3 时序存储层  

- **TSDB Shard**（水平分片）  
  - 每个 Shard 包含 **Write-Ahead Log (WAL)** + **Immutable Blocks**（列式压缩）  
  - **Compaction**：周期性把 WAL 合并成块，执行 **Down‑sample**。  

- **元数据服务（Meta Store）**  
  - 保存 **租户 → Shard 映射、标签索引、块位置**。  
  - 可使用 **etcd / Consul** 作为强一致性键值存储。  

#### 1.4 查询/分析层  

- **Query Frontend**（Gateway）  
  - 接收 PromQL，解析后拆分为子查询分发到多个 **TSDB Shard**。  
  - **查询缓存**（LRU / Redis）缓存最近的查询结果或中间聚合。  

- **Aggregator**（可选）  
  - 对跨 Shard、跨时间段的聚合在 **查询层** 做 **并行 reduce**，降低单节点负载。  

#### 1.5 可视化 & 告警层  

- **Grafana**（或自研 Dashboard）  
  - 只负责 UI，向 **Query Frontend** 发 PromQL。  

- **Alert Manager**  
  - 从 **TSDB** 拉取规则表达式的执行结果（或直接由 Query Frontend 推送）。  
  - 实现 **抑制、分组、去抖动**，支持 **Webhook、Email、SMS**。  

#### 1.6 统一认证/授权  

- **Auth Service**（OAuth2 / LDAP）  
  - 生成 **JWT**，在每次请求中携带 `tenant_id` 与 `role`。  
  - **RBAC** 决策在 **Query Frontend** 与 **Write Ingress** 统一校验。  

### 2. 为何要这么拆？

| 设计 | 不这么做会出现什么问题 |
|------|-----------------------|
| **采集层 & 写入入口分离** | 把 Scrape 直接写本地磁盘会导致单节点写入瓶颈、无法统一做流量控制。 |
| **水平分片的 TSDB** | 单机 TSDB 随着指标量增长会出现 **磁盘 I/O 饱和**、**查询慢**，且无法满足 99.9% 可用。 |
| **Meta Store** | 没有统一元数据会导致 **标签查询全表扫描**，查询延迟失控。 |
| **Query Frontend + Cache** | 直接访问底层 Shard，跨分片聚合在客户端完成，网络开销大，**QPS** 难以提升。 |
| **统一 Authz** | 每个组件自行实现权限会导致 **不一致**，安全隐患。 |

---  

## ## 第三步：数据库设计  

### 1. 时序数据模型  

| 字段 | 类型 | 说明 |
|------|------|------|
| `tenant_id` | string | 多租户隔离键，参与分片 |
| `metric_name` | string | 如 `cpu_usage` |
| `labels` | map<string,string> | 动态标签（`instance`, `job`, `region` 等） |
| `timestamp` | int64 (nanosecond) | UTC 时间 |
| `value` | float64 | 指标数值 |

> **实现**：在磁盘层面采用 **列式压缩块**（每个块 2 h 数据），内部结构类似 **Prometheus TSDB**：  
- **时间戳列**采用 **delta‑of‑delta + varint** 编码。  
- **数值列**采用 **Gorilla**（XOR）压缩。  
- **标签索引**采用 **倒排索引** + **B‑Tree**（存放在 Meta Store）。  

### 2. 块（Chunk）设计  

| 属性 | 解释 |
|------|------|
| **块大小** | 2 h（可配置）——兼顾写入吞吐与查询粒度。 |
| **块文件结构** | `meta.json`（块元信息） + `chunks.dat`（压缩列） + `index.bin`（标签倒排）。 |
| **压缩比** | 6~8×（≈ 85%）| 

### 3. 元数据（Meta Store）  

- **Key**：`/tenants/{tenant_id}/metrics/{metric_name}/{labels_hash}` → **BlockList**（有序块指针）  
- **存储**：使用 **etcd**（强一致）或 **CockroachDB**（分布式 SQL）  
- **查询**：PromQL 解析后生成 **时间范围 + label filter** → 直接定位对应块列表 → 并行读取。  

### 4. 降采样（Down‑sample）  

| 原始粒度 | 降采样目标 | 聚合方式 | 保存位置 |
|----------|------------|----------|----------|
| 1 s      | 1 m        | avg/min/max | 同 Shard，标记 `resolution=1m` |
| 1 m      | 5 m        | avg/min/max | 同上 |
| 5 m      | 1 h        | avg/min/max | 同上 |

- **实现**：每次 **Compaction** 完成后，触发 **Down‑sample Job**，写入新分辨率块，保留原始块 30 天后删除。  

---  

## ## 第四步：核心 API 设计  

> 统一使用 **REST + protobuf**（或 **gRPC**）做外部交互，内部服务间使用 **gRPC**（低延迟、强类型）。  

### 1. Remote Write（写入入口）  

```http
POST /api/v1/write
Content-Type: application/x-protobuf
Authorization: Bearer <jwt>

message WriteRequest {
  string tenant_id = 1;
  repeated Sample samples = 2;
}
message Sample {
  string metric = 3;                // metric_name
  map<string, string> labels = 4;   // key/value
  int64 timestamp = 5;              // ns
  double value = 6;
}
```

- **批量**：一次请求 1–10 KB，降低网络开销。  
- **幂等**：采用 **timestamp+metric+labels** 唯一键，重复写入会被覆盖。  

### 2. Remote Read（查询入口）  

```http
POST /api/v1/query
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "tenant_id": "teamA",
  "promql": "sum(rate(http_requests_total[5m])) by (service)",
  "start": 1685107200000,
  "end":   1685110800000,
  "step":  60000
}
```

- **返回**：`application/json`，结构同 Prometheus `/api/v1/query_range`。  

### 3. Alert Rule 管理  

```http
POST /api/v1/alerts/rules
{
  "tenant_id": "teamA",
  "name": "high_cpu",
  "expr": "avg_over_time(cpu_usage[5m]) > 0.9",
  "for": "5m",
  "labels": {"severity":"critical"},
  "annotations": {"summary":"CPU > 90%"}
}
```

- **Rule Engine**：在 **Alert Manager** 中以 **PromQL** 表达式实时评估。  

### 4. RBAC / 租户管理  

```http
POST /api/v1/tenants
{
  "tenant_id": "teamA",
  "owner": "alice@example.com",
  "roles": [
    {"user":"bob@example.com","role":"admin"},
    {"user":"carol@example.com","role":"viewer"}
  ]
}
```

- **返回**：JWT 包含 `tenant_id`、`role`，后续请求统一校验。  

---  

## ## 第五步：详细组件设计  

下面按功能模块逐一展开实现细节、技术选型、关键算法。  

### 1. 采集层（Scrape Manager + Pushgateway）  

| 子模块 | 关键技术 | 设计要点 |
|--------|----------|----------|
| **Scrape Scheduler** | Go 协程 + **Exponential backoff** | - 动态发现（Consul / Kubernetes Endpoints）<br>- 每台机器 **分片**（基于 hash(`instance`)）避免全局拉满 |
| **HTTP Client** | HTTP/2 + **gzip** | - 并发度 5–10<br>- 失败重试，最大重试次数 3 |
| **Pushgateway** | 简单的 **Key‑Value store**（LevelDB）+ HTTP API | - 短暂任务（CI）Push → 存入内存+磁盘缓冲<br>- 定时 **TTL** 清理，防止长期占用 |
| **Metric Exporter** | Open-source Exporter（Node Exporter, JMX Exporter） | - 统一 **/metrics** 格式（Prometheus exposition format） |

#### 为什么要使用 Pull+Push？

- **Pull**：天然的 **负载均衡**（Prometheus 负责调度），适合长期、稳定的服务。  
- **Push**：短暂批处理、CI/CD 步骤无法被主动抓取，需要主动 Push。  

### 2. 写入入口层（Remote Write Service）  

- **入口**：`Ingress`（gRPC） → `Write Router`（Consistent Hash） → **Shard**  
- **一致性**：采用 **写前日志 (Write‑Ahead Log)**，保证宕机恢复不丢数据。  
- **流控**：基于 **Token Bucket** 对每个租户进行速率限制，防止单租户写入冲击全局。  

**伪代码（写入路由）**  

```go
func RouteWrite(req *WriteRequest) {
    // 1. 校验 JWT，取 tenant_id
    tenant := req.TenantId
    // 2. 对每个 Sample 计算分片 key
    for _, s := range req.Samples {
        shardKey := hash(tenant + s.Metric + s.LabelsHash()) % NumShards
        shard := shardPool[shardKey]
        shard.Append(s)               // async write to WAL
    }
}
```

### 3. 时序存储层（TSDB Shard）  

#### 3.1 写路径  

1. **WAL**（顺序追加） → **磁盘文件**（每 1 GB 滚动）  
2. **内存缓冲区**（ChunkBuilder）实时压缩，周期性 flush 到 **Immutable Block**。  

#### 3.2 读路径  

1. **查询路由**根据时间范围和标签过滤查找 **Block 索引**。  
2. 并行 **IO** 读取对应块，解压后在 **内存** 进行聚合（如 `rate`、`sum`）。  

#### 3.3 Compaction & Down‑sample  

- **两层 Compaction**：  
  - **Level‑0**：小块合并为 2 h Block。  
  - **Level‑1**：对已压缩的 Block 再做 **降采样**（生成 1 m、5 m、1 h 分辨率）。  
- **实现**：使用 **goroutine worker pool**，每个 Shard 独立运行，避免跨节点锁。  

#### 3.4 索引设计  

| 索引 | 类型 | 用途 |
|------|------|------|
| **Metric Name → Block List** | B‑Tree | 快速定位对应 metric 的所有块 |
| **Label Inverted Index** | Roaring Bitmap | `labelKey=labelValue` → bitmap of block IDs |
| **Time Range Index** | Sorted array | 通过二分定位块的时间跨度 |

> **查询示例**：`cpu_usage{instance="10.0.0.1",job="app"}[5m]` →  
> 1. 先在 **Metric Name Index** 找到所有块；  
> 2. 再用 **Label Inverted Index** 交集过滤；  
> 3. 最后依据 **Time Range** 只读需要的块。  

### 4. 查询层（Query Frontend & Aggregator）  

- **Parser**：将 PromQL 解析成 **AST** → **Execution Plan**（子查询树）。  
- **Planner**：基于 **shard metadata** 把子查询分发到多个 TSDB Shard。  
- **Executor**：并行执行子查询，返回 **partial results**（时间序列片段）。  
- **Reducer**：在前端或专门的 **Aggregator** 节点做 **最终聚合**（如 `sum by (service)`）。  

#### 缓存策略  

| 缓存层 | 内容 | 失效策略 |
|--------|------|----------|
| **Result Cache** | 完整查询结果（JSON）| LRU，TTL 30 s（对实时指标可短） |
| **Series Cache** | 单个时间序列的最近 N 条点 | LFU，TTL 5 min |
| **Meta Cache** | 标签索引 → Block List | 10 min TTL，刷新时重新读取 Meta Store |

> **为什么要缓存**：在高 QPS 场景下，**相同的仪表盘** 常常重复请求相同时间范围的聚合；缓存可以把查询延迟从 **150 ms** 降到 **30 ms**，显著提升用户体验。  

### 5. 告警层（Alert Manager）  

- **Rule Evaluation**：每 30 s 拉取一次 **Rule Evaluation Task** → **PromQL** → 产生 **Series of alerts**。  
- **去抖动 / 抑制**：  
  - **Silence Window**（`for`） → 只有持续满足阈值的时间超过 `for` 才触发。  
  - **Inhibit Rules**：高优先级告警（如 `node_down`）可以抑制同一实例的低优先级告警（如 `cpu_high`）。  
- **通知渠道**：通过 **Webhook**（支持自定义） → **Alertmanager** 再转发至 **Email / SMS / PagerDuty**。  

#### 防止告警风暴的技巧  

1. **阈值平滑**：使用 `avg_over_time(metric[5m])` 而非单点值。  
2. **Rate‑limit**：对同一告警同一时间只能发送 N 条（N=1），后续通过 **repeat interval** 重复。  
3. **分组聚合**：`group_by(instance)` → 合并同类告警，减少噪声。  

### 6. 多租户与权限管理  

- **租户隔离**：所有数据行都带有 `tenant_id`，写入路由、块索引均基于租户分片。  
- **RBAC**：  
  - **Viewer**：只能查询（`GET /query`）  
  - **Editor**：查询 + 写入（`POST /write`）  
  - **Admin**：全部权限 + 租户成员管理  
- **实现**：在 **Auth Service** 中签发 **JWT**，在每个入口统一解析并放入 **Context**，后续所有业务判断使用 `ctx.TenantID` 与 `ctx.Role`。  

---  

## ## 第六步：扩展性与高可用设计  

### 1. 写入路径的水平扩容  

| 场景 | 方案 |
|------|------|
| **正常写入（500 k/s）** | 10 台 **Write Ingress** + 20 台 **TSDB Shard**（每 shard 50 k/s） |
| **突增 2×** | **弹性伸缩**：使用 **Kubernetes HPA** 或 **自动扩容脚本**，临时再起 10 台 Shard，Consistent Hash 自动把新写入分配到新节点（hash 环环） |
| **不牺牲一致性** | 写入采用 **WAL + Commit Log**，每个写入在本地持久化后立即 **异步复制** 到 **备份 Shard**（复制因子 2），读请求可从任意副本拉取，写入成功即视为持久化。 |

> **为什么不使用 CAP 中的 “弱一致”**：监控数据是 **时间序列**，稍微的延迟（几秒）是可以接受的，但 **丢失** 则不可接受——尤其是告警阈值点。复制因子 2 能在单机故障时保证不丢失。  

### 2. 查询层的弹性  

- **Query Frontend** 部署 **N+1** 实例，使用 **Consul Service Mesh** 进行 **client‑side load balancing**。  
- **Cache 集群**（Redis Cluster）支持 **水平扩容**，热点查询自动分散。  
- **读写分离**：热点最近 30 天的数据放在 **SSD**，老数据（>30 天）迁移到 **对象存储（S3/OSS）**，查询层先查询 SSD，若未命中再查询冷层。  

### 3. 存储层容灾  

| 维度 | 方案 |
|------|------|
| **单机故障** | 每个 Shard 有 **热备份副本**（跨机房）使用 **Raft** 进行日志同步。 |
| **机房级别灾难** | **跨区域复制**：每个块完成压缩后异步上传到 **对象存储**（如 MinIO），在灾难恢复时重新挂载为只读 TSDB。 |
| **数据恢复** | 通过 **WAL** + **Snapshot**（每 12 h）进行 **点时间恢复**（PITR）。 |

### 4. 运维与监控自身  

- **自监控**：本系统的每个组件都暴露 **Prometheus metrics**（如 `ingress_write_latency_seconds`、`tsdb_compaction_duration_seconds`），并由 **同一套平台** 监控。  
- **告警**：设置 **系统级告警**（写入延迟 > 5 s、磁盘利用率 > 80%）防止自身崩溃。  

### 5. 迁移/升级策略  

1. **蓝绿发布**：新版本的 **Write Ingress** 与 **TSDB Shard** 并行运行，老流量逐步切换。  
2. **滚动升级**：对 **Query Frontend** 使用 **滚动重启**，保证 QPS 不掉线。  
3. **数据格式兼容**：在 **Compaction** 期间保留旧块的 **schema version**，新旧块可以共存，查询层根据块版本选择解码方式。  

---  

## ## 第七步：常见面试追问与回答  

### Q1️⃣  “如果把压缩比提升到 80%，会对查询延迟产生怎样的影响？你会怎么设计索引或缓存来缓解？”  

**回答要点**  

- **压缩比 80%** → **块体积更小**，磁盘 **IO** 下降，**写入** 更快，但 **解压** 需要 CPU。  
- **查询延迟** 主要受 **IO + 解压 + 聚合** 三部分影响。  
  - **IO**：更小的块意味着 **更少的读取**，有利于延迟。  
  - **CPU**：解压时间随压缩比线性增长（约 10‑20% 额外 CPU）。  
- **缓解措施**  
  1. **列式块缓存**：在查询节点使用 **LRU** 缓存最近读取的块，命中率高时几乎不再解压。  
  2. **预计算聚合**：对热点指标（CPU、内存）在 **Compaction** 时同步生成 **聚合块**（如 1 m、5 m 平均），查询时直接读取聚合块，省去解压+聚合。  
  3. **向量化解压**：使用 **SIMD**（如 `github.com/pierrec/lz4/v4`）并行解压，提高 CPU 利用率。  

**结论**：压缩比提升会让 **IO** 更好、**CPU** 稍增。通过 **块缓存 + 预聚合 + SIMD**，可以把查询 99th 延迟保持在 **<200 ms**。  

---  

### Q2️⃣  “在高频波动的指标上，如何防止告警风暴？请描述你会加入哪些去抖动/抑制策略？”  

**回答要点**  

| 策略 | 说明 | 示例 |
|------|------|------|
| **阈值平滑** | 用 `avg_over_time`、`max_over_time` 而非瞬时值 | `avg_over_time(cpu_usage[5m]) > 0.9` |
| **持续时间 (`for`)** | 必须连续满足阈值 **N** 分钟后才触发 | `for: 5m` |
| **抑制规则 (Inhibit)** | 当高优先级告警出现时，自动抑制同实例的低优先级告警 | `node_down` 抑制 `cpu_high` |
| **告警去抖动** | 同一告警在 **repeat_interval** 内只发送一次 | `repeat_interval: 30m` |
| **分组聚合** | 同一时间窗口内相同标签的告警合并为一条 | `group_by: [instance]` |
| **阈值自适应** | 基于历史分位数动态调节阈值（如 95th percentile） | `percentile_over_time(request_latency[1h]) > 0.95` |
| **Rate‑limit** | 对同一渠道的发送速率进行限制（如 10 条/分钟） | Alertmanager `receiver` 中配置 `rate_limit` |

**实现**：在 **Alert Manager** 中配置上述规则，所有规则在 **Rule Evaluation** 阶段统一计算，随后进入 **Inhibit → Group → Rate‑limit → Notification** 流程。  

---  

### Q3️⃣  “面对写入吞吐突增（例如全公司同步部署新特性导致瞬时写入 2×），你会如何在不牺牲数据一致性的前提下扩容存储层？”  

**回答要点**  

1. **弹性写入入口**  
   - **Ingress** 使用 **Kubernetes HPA** 或 **自研 Autoscaler**，依据 **CPU/网络 I/O** 自动扩容。  
   - 新增节点后 **Consistent Hash Ring** 自动重新分配 **shardKey**，无需手动迁移。  

2. **写入路径幂等 & 重试**  
   - 客户端（Prometheus Agent）在写入失败时 **指数退避** 重试，保证最终写入成功。  

3. **数据复制**  
   - **写入** 采用 **同步复制**（Raft）至 **副本节点**（复制因子 2）。  
   - **扩容** 时新节点加入 **Raft 集群**，自动进行 **日志复制**，旧节点的 WAL 会同步至新节点。  

4. **不牺牲一致性**  
   - 采用 **线性写入**：只有多数副本 ACK（如 2/3）后返回成功。  
   - 若突增导致 **写入延迟** 超阈值，可临时 **提升写入批次大小**（降低每次 RPC 开销）或 **开启写入缓冲**（内存 Queue）来平滑流量。  

5. **监控扩容过程**  
   - 为 **扩容** 设置 **监控指标**（`ingress_queue_length`、`shard_write_latency`），自动触发 **报警** 与 **回滚**。  

**结论**：通过 **自动弹性扩容 + 一致性复制 + 幂等写入**，可以在突增期间保持 **数据不丢失**、**查询可用**，并在流量恢复后逐步收回临时节点，成本可控。  

---  

## ## 心得与反思  

### 1. 本题最难的 1‑2 个设计决策及思考过程  

| 决策 | 难点 | 思考路径 |
|------|------|----------|
| **时序存储的压缩与查询的平衡** | - 高压缩率降低磁盘占用，却增加解压 CPU。<br>- 查询需要快速定位块，否则会全表扫描。 | 1. 先评估 **写入量** 与 **压缩率**（目标 85%）。<br>2. 选定 **Gorilla+Snappy** 组合（CPU 友好）。<br>3. 为每块建立 **倒排标签索引** 与 **时间范围索引**，让查询只读取必要块。<br>4. 引入 **块缓存** 与 **预聚合块** 作为查询加速层。 |
| **多租户的数据隔离 + 高可用** | - 租户间需强隔离，防止跨租户查询泄露。<br>- 同时保证写入/查询的 HA，不产生热点。 | 1. 把 **tenant_id** 设计为 **第一层标签**，在 **Consistent Hash** 中参与分片，使同租户数据自然落在同一组 Shard。<br>2. 在 **Meta Store** 中记录租户 → Shard 映射，查询时先校验租户。<br>3. 每个 Shard 使用 **复制因子 2**（Raft）实现 HA。<br>4. 为防热点，**租户‑Shard** 采用 **hash‑mod** 而不是单一租户专属节点。 |

### 2. 新手最容易犯的错误（至少 2 条）  

| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把 Prometheus 单节点当作最终方案** | 随着指标量增大，磁盘 I/O、查询延迟、单点故障都会失控。 | 从 MVP 开始，明确 **拆分写入/查询/存储**，为每层预留水平扩展接口。 |
| **忽视标签索引的成本** | 查询时会出现 **全表扫描**，导致 99th 延迟飙升至秒级。 | 为每个 **labelKey‑labelValue** 建立 **倒排索引**，并在 **Meta Store** 中维护块‑标签映射。 |
| **只考虑写入吞吐而不考虑压缩后存储成本** | 数据量快速膨胀，磁盘很快耗尽，导致不可用。 | 设计 **压缩块格式**、**分辨率降采样**、**冷热分层**，并提前估算 **压缩比** 与 **存储容量**。 |

### 3. 学习建议和可延伸的方向  

1. **系统设计基础**  
   - 熟悉 **CAP 定理、BASE、CAP vs. ACID**，了解 **一致性/可用性/分区容忍** 的 trade‑off。  
   - 阅读 **《Designing Data‑Intensive Applications》**，重点章节：时序数据库、日志结构存储、分片与副本。  

2. **时序数据库内部实现**  
   - 深入阅读 **Prometheus TSDB**、**InfluxDB**、**ClickHouse**（列式存储）源码。  
   - 实验 **Gorilla 编码**、**Snappy**、**LZ4** 对比，了解压缩 vs. CPU 的平衡。  

3. **分布式一致性协议**  
   - 学习 **Raft**、**Paxos**，动手实现一个简化版的 **日志复制**，体会 **leader 选举** 与 **故障恢复**。  

4. **查询语言实现**  
   - 参考 **PromQL**、**SQL** 的解析器实现（如 **antlr**），练习把 **AST** 转换成 **执行计划**。  

5. **可观测性**  
   - 实际部署 **Prometheus + Grafana**，观察 **scrape latency、write latency**，思考如何把监控系统本身纳入监控。  

6. **云原生部署**  
   - 了解 **Kubernetes Operator**（如 **Prometheus Operator**）的原理，尝试编写自己的 **TSDB Operator** 实现自动扩容、备份。  

---  

### 小结  

从 **单节点 MVP** → **分片 TSDB** → **多租户 HA**，我们逐层解决了 **写入吞吐、查询延迟、压缩存储、告警可靠性** 等核心挑战。  
在面试时，**先说整体思路**（模块划分、数据流向），**再逐点展开**（每个模块为何这样设计，若不这样会有什么问题），**最后补充扩展/故障恢复方案**，即可展示系统设计的完整能力。  

祝你面试顺利，玩转监控告警系统！ 🚀  
