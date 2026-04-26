# 第 31 天：设计 Elasticsearch 全文检索系统

> 生成日期：2026-04-25

---

# 系统设计面试题：Elasticsearch 全文检索系统

## 1️⃣ 题目背景  
Elasticsearch 是基于 Lucene 的分布式全文检索引擎，常用于日志分析、商品搜索、内容推荐等场景。面试者需要设计一个面向 **海量用户**、**高并发查询** 的全文检索系统，满足搜索、过滤、排序等业务需求。

## 2️⃣ 面试场景设定  
> **面试官**：  
> “我们公司计划在全球范围内部署一套基于 Elasticsearch 的全文检索平台，用来为我们的电商网站提供商品搜索、智能推荐以及后台日志检索。请你从零开始设计这套系统，重点说明架构、数据流、扩展性和高可用性。我们先从核心功能开始讨论，好吗？”

## 3️⃣ 功能性需求  

| 编号 | 功能描述 |
|------|----------|
| F1 | **全文关键词搜索**：支持分词、同义词、模糊匹配，返回相关度排序的文档列表。 |
| F2 | **过滤与聚合**：按类目、品牌、价格区间、标签等维度进行过滤，并支持聚合统计（如每个类目下的商品数量）。 |
| F3 | **实时写入**：商品信息、用户行为日志等数据能够在 **≤ 1 s** 内写入索引并对外可查询。 |
| F4 | **多租户/索引隔离**：不同业务线（商品搜索、日志分析、推荐）使用独立的索引，互不干扰。 |
| F5 | **安全与权限控制**：基于角色的访问控制（RBAC），仅授权用户可以查询或写入特定索引。 |
| F6 | **监控与告警**：提供节点健康、查询慢日志、索引大小等指标的可视化监控，支持阈值告警。 |

## 4️⃣ 非功能性需求  

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **DAU（活跃用户数）** | 5 Million | 全球电商站点日活用户量。 |
| **QPS（查询每秒）** | 30 k QPS（峰值） | 高峰期搜索请求数。 |
| **写入吞吐** | 15 k 文档/s（峰值） | 商品上新、日志写入等。 |
| **查询延迟** | 99th Percentile ≤ 120 ms | 包括网络、路由、检索全部耗时。 |
| **可用性** | ≥ 99.95%（月度） | 包括节点故障、网络分区等情况下的服务可用。 |
| **存储规模** | 约 2 PB（3 年数据） | 预计每月增长 150 TB，包含倒排索引、快照等。 |

## 5️⃣ 系统边界  

**本题范围（需要设计）**  
- 索引创建、分片与副本策略。  
- 写入路径（采集、预处理、批量写入）。  
- 查询路由、负载均衡、缓存层设计。  
- 集群监控、自动扩容/缩容、故障恢复流程。  
- 安全鉴权、租户隔离方案。  

**不在本题范围（可不考虑细节）**  
- 客户端 SDK（如 Java、Python）实现细节。  
- 前端 UI 与交互设计。  
- 业务层的推荐算法（仅需提供检索接口）。  
- 第三方搜索插件（如 Kibana、Grafana）集成细节。  

## 6️⃣ 提示与追问  

| 编号 | 可能的追问 | 关注点 |
|------|-----------|--------|
| Q1 | “如果突发流量导致查询 QPS 瞬间冲到 100 k，你会如何快速缓解？” | 动态伸缩、热点缓存、熔断降级、查询限流。 |
| Q2 | “在索引规模达到 PB 级别时，如何保证倒排索引的压缩与查询性能？” | 归档/冷热分层、只读快照、字段数据类型优化、压缩算法（e.g., `best_compression`）。 |
| Q3 | “请说明当单个分片因硬件故障不可用时，系统如何保证数据不丢失且查询不受影响？” | 副本机制、分片迁移、故障检测与自动恢复、写入一致性 (primary‑replica 同步)。 |

> **提示**：面试时可先从业务需求出发，讨论索引模型与分片策略，再逐层展开写入、查询、运维等细节，最后补充安全与监控。祝你面试顺利！

---

# 题解

## 解题思路总览
> **目标**：从「零」到「可在生产环境跑」的完整设计过程，帮助没有系统设计经验的同学把握 **需求 → 规模 → 架构 → 细节 → 可用性 → 面试扩展** 的思考路径。  
> **思考框架**  
> 1. **需求拆解**：把功能需求、非功能需求、业务边界逐条写进笔记。  
> 2. **容量估算**：算出 QPS、写入速率、存储量，得到“最小可跑”机器配置。  
> 3. **高层蓝图**：画出数据流（写入 → 索引 → 查询）和核心组件（采集、ES 集群、网关、监控等）。  
> 4. **细化每个模块**：索引模型、分片/副本、路由、缓存、权限、监控、运维自动化。  
> 5. **可靠性 & 可扩展**：讨论容错、弹性伸缩、冷热分层、备份恢复。  
> 6. **面试常见追问**：提前准备答案，展示你对系统细节的掌握。  

下面按 **“从最小可用系统 → 逐步演进到高可用分布式架构”** 的顺序展开，每一步都解释 *为什么* 这样做以及 *不这么做* 会出现什么问题。

---

## 第一步：理解需求与规模估算

| 维度 | 需求/指标 | 关键点 | 估算方法 |
|------|-----------|--------|----------|
| **业务** | 商品搜索、日志检索、推荐 | 需要 **全文检索 + 过滤 + 聚合**，且 **多租户**（商品、日志、推荐） | - |
| **活跃用户** | DAU 5 Million | 说明全球并发用户量大，峰值请求会集中在少数时间段 | - |
| **查询** | 30 k QPS 峰值，99th ≤ 120 ms | 必须做到 **低延迟**，查询路径要尽可能短 | - |
| **写入** | 15 k 文档/s 峰值，≤ 1 s 可查询 | “实时”写入 → **Refresh** 周期、Bulk API | - |
| **存储** | 2 PB 3 年数据，≈150 TB/月 | 需要 **冷热分层**、压缩、快照 | - |
| **可用性** | ≥ 99.95% (≈5 min/月停机) | 必须容忍节点、机房故障，自动恢复 | - |
| **安全** | RBAC、租户隔离 | 每个业务线只能访问自己的索引 | - |

### 1.1 计算节点规模（粗略估算）

| 资源 | 计算方式 | 结果 |
|------|----------|------|
| **查询节点 CPU** | 30 k QPS × 0.5 ms（CPU） ≈ 15 000 ms/s ≈ 15 核心 | 取 2×冗余 → 32 核心机器 × 2 台 |
| **写入节点 CPU** | 15 k 文档/s × 0.3 ms ≈ 4 500 ms/s ≈ 5 核心 | 2 台 8 核机器 |
| **内存** | 每个查询线程约 200 MiB（缓存） → 32 GB 起步 | 每台 64 GB |
| **磁盘** | 2 PB / 3 年 ≈ 560 TB/年 ≈ 47 TB/月<br>使用 **热**+**温**+**冷** 分层：<br>• 热：最近 30 天 30 TB（SSD）<br>• 温：30‑180 天 150 TB（NVMe/HDD 混合）<br>• 冷：180 天以上 380 TB（HDD） | SSD 30 TB + HDD 500 TB |
| **网络** | 每秒 45 k 请求（查询+写入）× 1 KB ≈ 45 MB/s < 1 Gbps，留余量 10 Gbps | 10 GbE 交换机 |

> **为什么先算这些？**  
> - 帮助判断是单机、几机还是需要跨机房的集群。  
> - 让后面的 **分片数**、**副本数**、**节点角色划分** 有依据。  
> - 若不做容量估算，直接上大集群会导致资源浪费或资源不足（延迟、OOM）。

---

## 第二步：高层架构设计

### 2.1 整体数据流（写入 & 查询）

```
[客户端] → [API Gateway / Load Balancer] → [Auth & Rate Limiter] → 
   ├─ 写入路径 → [Ingestion Service] → [Message Queue (Kafka)] → [Bulk Processor] → [Elasticsearch Cluster (Hot Index)]
   └─ 查询路径 → [Search Router] → [Cache Layer (Redis)] → [Elasticsearch Cluster (Hot/Cold)] → [Result Formatter] → [客户端]
```

### 2.2 关键组件解释

| 组件 | 作用 | 为什么要单独拆出来 |
|------|------|-------------------|
| **API Gateway / LB** | 统一入口，做流量分发、TLS 终结、限流 | 防止单点故障，易于灰度发布 |
| **Auth & Rate Limiter** | 基于 RBAC 的鉴权 + QPS 限流 | 实现 **F5、F6**，保护后端 ES 不被冲垮 |
| **Ingestion Service** | 接收业务写入（商品、日志），做统一预处理（脱敏、统一字段） | 保证写入格式统一，便于后续扩展 |
| **Message Queue (Kafka)** | 异步缓冲写入流量，提供 **at‑least‑once** 可靠性 | 直接写 ES 会导致突发流量压垮节点，Kafka 让我们可以批量写入 |
| **Bulk Processor** | 按时间/大小批量向 ES 发送 Bulk API，调节 **refresh_interval** | 通过 Bulk 减少网络往返次数，提升吞吐 |
| **Search Router** | 根据租户、业务线、索引名将查询路由到对应 ES 节点 | 支持 **多租户/索引隔离** |
| **Cache Layer (Redis)** | 缓存热点查询结果、聚合桶 | 缓解热点查询压力，降低 99th 延迟 |
| **Elasticsearch Cluster** | 核心检索引擎，包含 **Hot / Warm / Cold** 三层节点 | 根据冷热分层实现成本最优化、查询性能 |
| **Result Formatter** | 把 ES 原始 JSON 转成业务方需要的结构（去除内部字段） | 隔离内部实现细节，提升安全性 |

### 2.3 节点角色划分（最小可跑版本）

| 角色 | 机器数（示例） | 规格 | 说明 |
|------|----------------|------|------|
| **Load Balancer** | 2 (active‑passive) | 2 CPU/4 GB | 采用 HAProxy/Nginx + Keepalived |
| **Auth & Rate Limiter** | 2 | 4 CPU/8 GB | 使用 Envoy/Zuul + Redis token bucket |
| **Kafka Brokers** | 3 | 8 CPU/32 GB + SSD | 保证分区副本数 = 2 |
| **Ingestion Workers** | 4 | 8 CPU/16 GB | 消费 Kafka，做 Batch Bulk |
| **ES Hot Nodes** | 6 | 16 CPU/64 GB + SSD 4 TB | 负责最近 30 天数据 |
| **ES Warm Nodes** | 8 | 12 CPU/48 GB + HDD 12 TB | 负责 30‑180 天 |
| **ES Cold Nodes** | 12 | 8 CPU/32 GB + HDD 30 TB | 只读、快照存储 |
| **Redis Cache** | 3 (sentinel) | 4 CPU/8 GB | 用于热点查询缓存 |
| **监控/告警** | 2 | 2 CPU/4 GB | Prometheus + Grafana |

> **为什么分层？**  
> - **热节点** 需要 SSD 低延迟满足 120 ms SLA。  
> - **温/冷节点** 采用 HDD 降低成本，且查询频率下降，可接受稍高的 I/O 延迟。  
> - 若不做冷热分层，全部使用 SSD 成本极高（2 PB × $0.15/GB ≈ $300 M/年），且磁盘利用率低。

---

## 第三步：数据库设计（Elasticsearch 索引模型）

### 3.1 索引划分（多租户）

| 业务线 | 索引前缀 | 示例 | 备注 |
|-------|----------|------|------|
| 商品搜索 | `product_` | `product_2024_09`（按月滚动） | 支持 **时间切分** + **别名** |
| 日志分析 | `log_` | `log_app_2024_09` | 按业务系统、月份划分 |
| 推荐 | `rec_` | `rec_user_2024_09` | 只读，按用户分片 |

> **实现方式**：使用 **Elasticsearch Index Alias** 为每个业务线提供统一入口（如 `product_latest`），后台定期切换别名指向新分片。

### 3.2 文档结构（以商品为例）

```json
{
  "product_id": "123456",
  "title": "Apple iPhone 15 Pro Max 256GB 深空灰",
  "description": "全新 A17 仿生芯片，支持 ProMotion 120Hz 显示屏...",
  "category": ["手机", "数码产品"],
  "brand": "Apple",
  "price": 8999.00,
  "tags": ["5G", "双摄", "全网通"],
  "attributes": {
    "color": "深空灰",
    "storage": "256GB"
  },
  "stock": 120,
  "created_at": "2024-09-12T08:30:00Z",
  "updated_at": "2024-09-13T12:00:00Z"
}
```

#### 字段映射（Mapping）要点

| 字段 | ES 类型 | 关键设置 | 说明 |
|------|---------|----------|------|
| `product_id` | `keyword` | `doc_values: true` | 精确过滤、聚合 |
| `title`、`description` | `text` | `analyzer: standard` + `search_analyzer: ik_smart`（中文）<br>`fielddata: true`（聚合） | 支持分词、同义词、模糊匹配 |
| `category`、`brand`、`tags` | `keyword` | `norms: false` | 过滤/聚合 |
| `price` | `scaled_float` (scale: 2) | `doc_values: true` | 价格范围过滤、排序 |
| `attributes.*` | `keyword` | `dynamic: true` | 可扩展属性 |
| `created_at`、`updated_at` | `date` | `format: "strict_date_time"` | 时间过滤、滚动索引依据 |
| `stock` | `integer` | `doc_values: true` | 库存过滤 |

> **为什么要显式定义 Mapping？**  
> - 默认动态映射会把长文本映射成 `text` + `keyword` 双字段，浪费磁盘。  
> - 不设置 `doc_values`，聚合会走 `fielddata`，导致堆内存 OOM。  
> - 错误的 `analyzer` 会导致搜索结果不相关。

### 3.3 分片 & 副本策略

| 索引 | 预计文档数（3 年） | 建议 **primary shards** | **replica shards** | 说明 |
|------|-------------------|------------------------|--------------------|------|
| `product_*` | 10 B（10 Billion） | 60（每 shard ~ 150 M docs） | 1 | 1 副本保证 **99.95%** 可用，跨 AZ 部署 |
| `log_*` | 20 B | 120 | 1 | 日志写入量大，分片数多以降低单 shard I/O |
| `rec_*` | 5 B | 30 | 0 (只读) | 推荐索引主要用于查询，副本可在查询层面通过 **跨集群复制** 实现 |

> **分片数的决定因素**  
> 1. **单 shard 最大容量**（Lucene 推荐 ≤ 50 GB 索引文件，超过后合并会变慢）。  
> 2. **并行查询需求**：更多 shard = 更多并行度，但也增加网络开销。  
> 3. **集群节点数**：保证每个节点上有适当数量的 shard（推荐 20‑30 个），避免 **“small shards”**（资源浪费）和 **“large shards”**（查询慢）。  

> **副本数**：  
> - **1 副本** 可在同一 AZ 失效的情况下仍提供服务；  
> - 若业务对写入一致性要求严格，可使用 **primary‑only** 写入，副本异步同步（默认 Elasticsearch 采用 `write consistency = quorum`）。  

---

## 第四步：核心 API 设计

> **原则**：RESTful + JSON，兼容官方 ES API，便于以后直接使用 ES 客户端。

### 4.1 写入 API（商品上新、日志上报）

| 方法 | 路径 | 请求体 | 关键字段 | 说明 |
|------|------|--------|----------|------|
| `POST` | `/api/v1/{tenant}/documents` | `{ "type": "product", "data": {...} }` | `type`（product/log/rec），`data`（符合对应 mapping） | **异步**：服务层写入 Kafka，返回 `202 Accepted` 与唯一 `request_id` |
| `PUT` | `/api/v1/{tenant}/documents/{id}` | `{ "data": {...} }` | `id`（业务主键） | 全量覆盖，内部转为 **upsert** |
| `POST` | `/api/v1/{tenant}/bulk` | `{ "actions": [{ "index": {...} }, { "doc": {...} }, ...] }` | 批量 upsert | 用于大批商品导入，内部直接调用 ES Bulk（跳过 Kafka） |

**返回示例**

```json
{
  "request_id": "a1b2c3d4",
  "status": "queued",
  "estimated_delay_ms": 150
}
```

### 4.2 查询 API（搜索、过滤、聚合）

| 方法 | 路径 | 请求体 | 关键字段 | 说明 |
|------|------|--------|----------|------|
| `GET` | `/api/v1/{tenant}/search` | `q=iphone&category=手机&price_min=5000&price_max=10000&sort=price_desc&page=1&size=20` | `q`（全文），`category`、`brand`、`price_*`（过滤），`sort`，`page/size` | 支持 **分页**（`from/size`），内部使用 **scroll** 处理深分页 |
| `POST` | `/api/v1/{tenant}/search/advanced` | `{ "query": {...}, "aggs": {...}, "highlight": true }` | 完整 DSL（兼容 ES），可自定义聚合 | 高级用户或内部服务使用 |
| `GET` | `/api/v1/{tenant}/suggest` | `term=iph` | `term` | 基于 **completion suggester**，返回自动补全词组 |
| `GET` | `/api/v1/{tenant}/stats` | - | - | 返回租户索引大小、文档数、热点缓存命中率等监控数据（供 Dashboard） |

**查询流程简要**

1. **Auth** → 校验租户权限。  
2. **Cache** → 先在 Redis 查询 `key = hash(tenant+query)`。命中则直接返回。  
3. **Search Router** → 根据租户、查询时间范围选择 **Hot/Warm/Cold** 节点。  
4. **ES** → 通过 `_search` DSL 执行，使用 **doc_values** 进行过滤，`_source` 只返回需要字段。  
5. **Result Formatter** → 去掉内部元数据，加入高亮字段。  
6. **Cache写回** → 将结果写入 Redis（TTL 30 s），返回给客户端。

---

## 第五步：详细组件设计

### 5.1 写入路径

```
[Client] --HTTPS--> [API Gateway] --JWT--> [Auth Service] --RateLimiter-->
   --> [Ingestion Service] --Kafka Producer--> [Kafka Topic (tenant.product)]
   --> [Kafka Consumer (Bulk Worker)] --Bulk API--> [ES Hot Nodes]
```

#### 关键技术点

| 步骤 | 技术/配置 | 目的 |
|------|-----------|------|
| **API Gateway** | Nginx + Lua (or Envoy) | TLS 终端、请求路由、日志收集 |
| **Auth** | JWT + Redis RBAC 表 | 轻量鉴权，支持 **租户/角色** |
| **Rate Limiter** | Token Bucket (Redis) | 防止突发写入冲垮后端 |
| **Kafka** | 3 副本、`acks=all`、`linger.ms=20`、`batch.size=1MB` | 提供 **持久化缓冲**，控制写入批次 |
| **Bulk Worker** | Java/Go，使用官方 `BulkProcessor`，`flushInterval=5s`、`concurrentRequests=3` | 自动分批、错误重试、幂等 |
| **ES Refresh** | `refresh_interval=1s`（可调） | 实现 **≤1 s** 实时可查询；高峰期可临时调高至 5s，降低磁盘 I/O |
| **Idempotency** | 使用业务主键 `product_id` 作为 `_id`，确保 **幂等写入** | 防止重复写入导致数据冲突 |

> **如果不使用 Kafka**：写入直接走 ES，会在流量峰值时出现 **bulk queue 过长、线程阻塞**，导致请求超时。Kafka 为写入提供了 **背压机制**。

### 5.2 查询路径

```
[Client] --HTTPS--> [API Gateway] --JWT--> [Auth Service] --RateLimiter-->
   --> [Search Router] --Cache (Redis)-->
       --> [ES Node (Hot/Warm/Cold)] --_search DSL--> [Result Formatter] --> [Client]
```

#### 关键技术点

| 步骤 | 技术/配置 | 目的 |
|------|-----------|------|
| **Search Router** | Consistent Hash + Tenant → Index Alias | 保证同租户请求路由到相同的节点组，提升缓存命中 |
| **Cache** | Redis Cluster, LRU, TTL 30s | 缓存热点查询，降低 ES 负载 |
| **热点查询识别** | 统计每分钟查询次数，超过阈值自动写入缓存 | 自动热点检测，避免手动配置 |
| **查询超时** | `search.max_buckets=25000`、`request_timeout=5s` | 防止单次查询占满线程池 |
| **分页/深分页** | 使用 `search_after` 而非 `from+size`（>10k） | 避免 **deep pagination** 导致的 **heap** 爆炸 |
| **Highlight** | `pre_tags`/`post_tags` + `fragment_size=150` | 提供前端高亮展示 |
| **安全过滤** | 在 DSL 中强制加入 `tenant_id` 过滤（字段级安全） | 防止租户越界访问 |

### 5.3 冷热分层实现

| 层级 | 数据范围 | 节点类型 | 索引设置 | 迁移策略 |
|------|----------|----------|----------|----------|
| **Hot** | 最近 30 天 | SSD 4 TB/节点 | `refresh_interval=1s`、`translog.flush_threshold_size=512mb` | 每天自动切分新索引，旧索引使用 **ILM** 移动到 Warm |
| **Warm** | 30‑180 天 | HDD + NVMe | `refresh_interval=-1`（关闭实时刷新）<br>`codec=best_compression` | ILM 定时将 Hot → Warm |
| **Cold** | >180 天 | 只读 HDD | `index.blocks.write=true`<br>`codec=best_compression` | 归档至 **S3** 快照后，仍保留在 ES 只读节点，查询时使用 **frozen** 索引 |

> **ILM（Index Lifecycle Management）**：使用官方 ILM 策略自动完成 **rollover → shrink → freeze → delete**。  
> **如果不做冷热分层**：所有数据都放在 SSD，成本不成比例，且 SSD 写放大导致寿命缩短。

### 5.4 高可用 & 故障恢复

| 场景 | 处理流程 | 关键机制 |
|------|----------|----------|
| **单节点宕机** | 节点探测（Zen Discovery）→ 副本迁移 → 重新分配分片 | **Shard Allocation Awareness**（跨 AZ） |
| **整个 AZ 故障** | 副本已跨 AZ，ES 自动把缺失分片恢复到其他 AZ | **Cluster Routing Allocation** + **Zone Awareness** |
| **Kafka Broker 故障** | 生产者自动切换到其他 Broker，消费者重新平衡分区 | **ISR（In‑Sync Replicas）** |
| **Redis 故障** | Sentinel 自动故障转移，客户端使用 `redis://sentinel/...` | **Sentinel** |
| **磁盘满** | ILM 自动 shrink → freeze → 删除过期索引 | **disk.watermark.low/high** 阈值报警 |
| **网络分区** | 采用 **majority quorum** 写入，分区恢复后通过 **recovery** 同步 | **write consistency = quorum** |

> **为什么要配置跨 AZ 副本？**  
> - 单机或单 AZ 故障时仍能提供查询，满足 **99.95%** 可用性。  
> - 不做跨 AZ，机房级别故障会导致全部副本失效，业务不可用。

### 5.5 安全与权限（RBAC）

1. **用户/角色模型**  
   - **User** → 多个 **Role**  
   - **Role** 包含 **Permission**（`index:read/write`、`tenant:*`）  

2. **实现方式**  
   - **Elasticsearch X‑Pack Security**（开源版可自行实现）  
   - 在 **API Gateway** 拦截，向 **Auth Service** 请求 token，返回 **JWT**，内嵌 `tenant_id` 与 `allowed_indices`。  
   - ES **Search Guard**（或开源插件）在每次请求前校验 `_index` 是否在白名单中。  

3. **细粒度控制**  
   - **字段级安全**：对敏感字段（如用户隐私）使用 `masked_fields`，返回 `"***"`。  
   - **文档级安全**：在查询 DSL 中强制添加 `tenant_id` 过滤子句。  

> **不做租户隔离的后果**：不同业务线可能相互读取或修改对方数据，导致数据泄露、审计难度增大，违背合规要求。

### 5.6 监控、告警与运维

| 监控指标 | 工具 | 报警阈值示例 |
|----------|------|--------------|
| **节点健康** | Elasticsearch `_cat/health`、Prometheus `es_cluster_health_status` | `status != GREEN` |
| **CPU/内存/磁盘** | Node Exporter + Grafana | CPU > 80%（5min） |
| **查询慢日志** | `index.search.slowlog.threshold.query.warn` = `500ms` | 触发 PagerDuty |
| **写入延迟** | `bulk.request_latency` | > 200 ms |
| **缓存命中率** | Redis `keyspace_hits/keyspace_misses` | < 60% |
| **Kafka Lag** | Consumer Lag metrics | > 100k 消息 |
| **快照成功率** | Snapshot API + CronJob | 失败次数 > 0 |

> **自动伸缩**  
> - **水平伸缩**：基于 **CPU**、**QPS**、**Kafka Lag** 使用 **Kubernetes HPA** 或 **Cluster Autoscaler**。  
> - **冷热分层扩容**：当 Hot 节点磁盘使用 > 70% 时，自动创建新 Hot 节点并执行 **shard rebalancing**。  

---

## 第六步：扩展性与高可用设计

### 6.1 处理突发流量（Q1 追问）

| 方案 | 实现细节 | 何时使用 |
|------|----------|----------|
| **流量限流 + 熔断** | API Gateway 中对每个租户设置 QPS 上限，超过返回 `429`；后端服务使用 Hystrix 进行熔断 | 防止突发流量导致节点崩溃 |
| **热点缓存** | 将热门查询预热到 Redis（甚至 CDN） | 10% 查询占 90% 流量时 |
| **弹性伸缩** | 基于 CPU/QPS 自动扩容 ES **Hot** 节点（K8s 或裸机） | 10 分钟内可完成节点加入 |
| **查询降级** | 对超时查询返回 **简化结果**（只返回 `id`、`title`），不做聚合/高亮 | 保证 SLA，牺牲部分功能 |
| **写入背压** | Kafka `linger.ms` 与 `batch.size` 调整，突发写入时自动缓冲 | 防止写入瞬间压垮 ES |

### 6.2 PB 级别索引压缩与查询性能（Q2）

| 技术 | 作用 |
|------|------|
| **ILM + shrink** | 大索引定期 `shrink` 成更少的分片，降低搜索开销 |
| **best_compression codec** (`zstd`、`LZ4`) | 约 30%‑40% 磁盘节省，查询时自动解压 |
| **doc_values + columnar storage** | 聚合/排序使用磁盘列式存储，避免堆内存爆炸 |
| **只读 frozen 索引** | 冷数据转为 **frozen**，只在需要时加载到内存的极小部分 |
| **分段归档** | 将超过 180 天的数据快照到对象存储（S3），并从 ES 中删除，仅在需要时 **restore** | 

> **不做这些**：单个 shard 索引文件会膨胀到几百 GB，合并、搜索都会非常慢，甚至导致 OOM。

### 6.3 单分片故障恢复（Q3）

1. **写入路径**：写入先到 primary shard，成功后同步到 replica（`ack=all`）。  
2. **故障检测**：Zen Discovery 每 1 s 检测节点心跳；若 primary 所在节点失联，系统会 **选举** 副本为新的 primary。  
3. **数据不丢失**：因为写入已同步到副本，副本持有完整的 translog，故障恢复后可继续接受写入。  
4. **查询不中断**：在选举期间，ES 会返回 `status=yellow`，但仍能对已有副本进行查询。  
5. **自动迁移**：当失效节点恢复或新节点加入，集群会 **重新平衡**，把缺失的分片复制过去。  

> **如果没有副本**：primary 节点故障导致该分片不可用，查询会返回缺失，且写入会报错，违背 **99.95%** 可用性要求。

### 6.4 迁移到多机房（跨地域）方案

- **跨集群复制（CCR）**：在每个大区部署独立 ES 集群，使用 CCR 将主集群的 **Hot** 索引实时复制到备份集群。  
- **全局负载均衡**：使用 DNS 或 **Anycast** 将用户请求路由到最近的地区。  
- **统一身份中心**：OAuth2 + JWT，在所有地区共享同一权限中心。  

> **为什么不直接把所有节点放在同一机房？**  
> - 单机房故障（自然灾害、网络中断）会导致全局不可用。  
> - 跨地域可以实现 **灾备 RTO ≤ 5 min**，满足高可用需求。

---

## 第七步：常见面试追问与回答

| 追问编号 | 追问 | 参考答案要点 |
|----------|------|--------------|
| **Q1** | “如果突发流量导致查询 QPS 瞬间冲到 100 k，你会如何快速缓解？” | 1️⃣ **流量限流**（API Gateway、令牌桶）<br>2️⃣ **热点缓存**（Redis、CDN）<br>3️⃣ **弹性伸缩**（K8s HPA、自动添加 Hot 节点）<br>4️⃣ **查询降级**（只返回 ID、关闭聚合）<br>5️⃣ **熔断**（Hystrix） |
| **Q2** | “在索引规模达到 PB 级别时，如何保证倒排索引的压缩与查询性能？” | - **ILM** + **shrink**：把大索引拆分成更小的 shard<br>- **best_compression** codec（zstd）<br>- **列式存储**（doc_values）<br>- **frozen index**（只读）<br>- **冷热分层** + **对象存储快照**<br>- **只查询必要字段**（_source filtering） |
| **Q3** | “请说明当单个分片因硬件故障不可用时，系统如何保证数据不丢失且查询不受影响？” | - **副本机制**：primary + 1 replica（跨 AZ）<br>- **写入同步**（ack=all）<br>- **Zen Discovery** 自动检测并选举新的 primary<br>- **查询仍可在副本上执行**（cluster 状态 yellow）<br>- **自动重新分配** 缺失分片到健康节点 |
| **Q4** | “如何做到每条日志 ≤ 1 s 可搜索？” | 1️⃣ **Kafka → Bulk**，批次大小 1 MB、刷新间隔 1 s<br>2️⃣ **refresh_interval=1s**（或更小）<br>3️⃣ **pipeline** 中避免 heavy ingest scripts<br>4️⃣ **使用 `doc_values`**、**disable `_source`** 只在需要时存储 |
| **Q5** | “如果某租户的查询非常慢，怎么定位问题？” | - 查看 **慢查询日志**（阈值 500 ms）<br>- 检查 **热点缓存命中率**<br>- 通过 **Kibana/Prometheus** 看 **CPU、heap 使用**<br>- 使用 **profile API** 分析 DSL 执行计划<br>- 检查 **分片分布** 是否均衡 |

---

## 心得与反思

### 1️⃣ 本题最难的设计决策

| 决策 | 思考过程 | 最终方案 |
|------|----------|----------|
| **冷热分层 + ILM** | 初始想法是把所有数据放在同一集群的 SSD，成本极高且磁盘寿命受限。随后评估了 **存储成本**（SSD ≈ $0.15/GB vs HDD $0.03/GB）和 **查询频率**（30 天内 90% 查询），决定采用 **Hot/Warm/Cold** 三层。又考虑到 **数据迁移的自动化**，选择官方 **ILM** + **shrink** + **freeze**。 | Hot（SSD）+ Warm（HDD）+ Cold（frozen）+ 快照归档 |
| **写入实时性 vs 吞吐** | 实时写入要求 ≤1 s 可查询，直接写 ES 会导致大量小批次请求，CPU/磁盘负载飙升。经过对 **Kafka** 的特性（持久化、背压）和 **Bulk API** 的吞吐对比，决定在写入路径加入 **Kafka → Bulk Worker**，并调节 `refresh_interval`。 | Kafka + Bulk Processor + 1s refresh |

### 2️⃣ 新手最容易犯的错误

| 错误 | 结果 | 正确做法 |
|------|------|----------|
| **忽视分片大小** → 随意设置 5 个 primary shard。 | 单个 shard 会超过 100 GB，合并慢、查询慢、容易 OOM。 | 依据 **预计文档数** 与 **单 shard 最大容量（≈ 50 GB）** 计算分片数，保持每节点 20‑30 个 shard。 |
| **把所有业务放在同一个索引**（商品+日志+推荐）。 | 索引映射冲突、查询性能下降、权限隔离困难。 | 按业务线使用独立索引前缀 + 别名，实现 **租户隔离**。 |
| **关闭 refresh 以提升写入**，但忘记手动刷新。 | 数据写入后长时间不可搜索，违背实时需求。 | 根据业务需求调节 `refresh_interval`（商品搜索 1 s），日志可设为更长。 |
| **在查询 DSL 中不强制加租户过滤**。 | 租户数据泄露（安全风险）。 | 在 **Search Guard** 或后端路由层统一追加 `tenant_id` 过滤子句。 |
| **使用大量 `stored_fields`** 导致磁盘膨胀。 | 索引体积激增、查询慢。 | 只在必要时使用 `stored_fields`，大多数情况下使用 `_source` 并在返回时过滤字段。 |

### 3️⃣ 学习建议与可延伸方向

| 学习方向 | 推荐资源 |
|----------|----------|
| **Elasticsearch 基础**（倒排索引、分片、副本、映射） | 官方文档 <https://www.elastic.co/guide>、《Elasticsearch 实战》 |
| **集群运维**（ILM、CCR、快照、监控） | 《Elasticsearch 运营指南》、Elastic 官方 YouTube |
| **分布式系统理论**（CAP、共识、故障恢复） | 《Designing Data‑Intensive Applications》 |
| **消息队列**（Kafka） | 《Kafka: The Definitive Guide》、Confluent 视频 |
| **容器化与自动伸缩**（K8s、Helm） | 《Kubernetes Up & Running》 |
| **安全与 RBAC** | Elastic X‑Pack Security 文档、OAuth2/JWT 教程 |
| **性能调优**（缓存、热点、查询优化） | Elastic 官方 “Performance Tuning” 白皮书、Search Profiler 使用指南 |
| **面试技巧** | “系统设计面试精讲” 系列博客、Mock 面试练习 |

> **实践最重要**：在本地搭建单机 ES，尝试 **分片/副本/ILM**，写入 1 M 文档，观察磁盘、查询延迟。随后逐步加入 **Kafka → Bulk**、**Redis 缓存**，再用 **docker‑compose** 模拟多节点集群。通过实验感受每个设计决策的真实影响，面试时才能自信阐述。

---

**祝你在面试中把系统设计环节讲得条理清晰、思路严谨，给面试官留下“既懂业务又懂技术”的好印象！** 🚀
