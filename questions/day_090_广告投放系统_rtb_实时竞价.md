# 第 90 天：设计 广告投放系统（RTB 实时竞价）

> 生成日期：2026-02-25

---

## 题目背景
广告投放系统（RTB 实时竞价）用于在用户访问网页或 App 时，瞬间完成广告位的竞价、选取、投放并上报效果数据。系统需要在毫秒级别完成从请求接收、竞价决策到返回广告的全链路，保证广告主的 ROI 与平台的收入。

---

## 面试场景设定
> **面试官**：  
> “假设我们要构建一个能够支撑全球规模的 RTB 实时竞价系统，请先从整体架构出发，说明你会如何设计它的核心组件以及它们之间的交互。随后我们会逐步深入到存储、容错、性能等细节。”

---

## 功能性需求
1. **实时竞价请求接收**：能够在用户浏览页面时接收来自 SSP（Supply‑Side Platform）的 OpenRTB 请求。  
2. **快速广告过滤与匹配**：基于广告主的投放策略（地域、设备、兴趣等）在毫秒级过滤候选广告。  
3. **竞价算法执行**：对候选广告进行打分、预算检查、频次控制等，选出最高出价的广告返回。  
4. **日志与效果上报**：实时记录请求、竞价结果、点击、转化等事件，并提供查询接口。  
5. **预算与频次控制**：保证广告主的每日/小时预算不超额，防止同一用户短时间内看到同一广告。  
6. **对外 API（OpenRTB 2.5）兼容**：对接多家 SSP 与 DSP，支持标准的 JSON 请求/响应格式。

---

## 非功能性需求（估算值）

| 指标 | 目标值 | 备注 |
|------|--------|------|
| **日活跃用户（DAU）** | 5,000,000 | 主要指浏览页面的终端用户 |
| **每秒请求量（QPS）** | 150,000 QPS 峰值 | 约 13 亿次/日请求 |
| **平均响应时延（RT）** | ≤ 30 ms（99.9% 请求） | 包括网络、业务处理、返回 |
| **系统可用性** | 99.99%（月度累计停机 ≤ 4.38 小时） | 需支持热备、自动故障转移 |
| **存储量** | 10 PB 以上（日志、历史数据） | 以每年 3 PB 增长为基准 |
| **预算一致性延迟** | ≤ 1 秒 | 实时扣减广告主预算，防止超支 |

---

## 系统边界
**本题范围内需要考虑的功能**  
- RTB 请求的接收、过滤、竞价、返回全链路。  
- 广告主预算、频次控制的实时校验。  
- 关键日志（请求、竞价、点击、转化）的写入与查询。  
- 高可用、水平扩展、容错机制的设计。

**本题范围外（不必实现）**  
- 创意素材的存储与 CDN 分发。  
- 广告创意的创意审核、创意生成工具。  
- 复杂的机器学习模型训练（只需提供调用接口即可）。  
- 第三方数据合作（如 DMP）细节，仅需说明如何接入。  
- 账单结算系统（仅需说明数据交付方式）。

---

## 提示与追问
1. **数据一致性**：在高并发下，如何保证广告主的预算扣减既快速又不出现超支？可以讨论分布式锁、预扣款、幂等设计等方案。  
2. **容量预估**：如果 QPS 突增至 300,000，系统需要怎样扩容？请说明水平扩展的粒度（请求层、竞价层、存储层）以及自动扩缩容的策略。  
3. **容错与降级**：在某一机房网络分区导致部分 DSP 无法响应时，系统应如何快速降级保证整体响应时延？可以涉及熔断、超时、备份广告池等机制。

---

# 题解

# RTB 实时竞价系统设计全流程手把手教学  

> **写给对象**：零经验的后端小伙伴，本文会从最小可用系统出发，层层递进，解释每一步“为什么这么做”，帮助你在面试中从容作答。  

> **阅读提示**：先通读一次整体思路（**解题思路总览**），随后按章节顺序逐步消化。遇到不懂的概念，记得回到前面的解释，它们已经被拆解成最易懂的粒度。  

---  

## 解题思路总览  

1. **先把需求拆解成“业务功能 + 非功能约束”。**  
2. **估算规模**（QPS、并发、存储），判断系统到底是“单机可以跑”还是“必须分布式”。  
3. **画最小可用系统（MVP）**：只保留核心路径——接收 OpenRTB 请求 → 过滤 → 竞价 → 返回。  
4. **在 MVP 基础上逐层补齐**：  
   - **持久化**（广告主、预算、日志）  
   - **实时约束**（预算、频次）  
   - **高可用/容错**（分片、冗余、熔断）  
   - **伸缩**（水平扩容、自动扩容）  
5. **把每个组件的职责、技术选型、交互协议写清楚**，并解释选型原因、备选方案以及不这么做会出现的问题。  
6. **准备面试追问**：一致性、容量突增、降级等。  

下面，我们一步一步展开。  

---  

## 第一步：理解需求与规模估算  

### 1. 功能性需求要点  

| 编号 | 需求 | 关键点 |
|------|------|--------|
| 1 | **实时请求接收** | OpenRTB JSON，来源是 SSP，毫秒级响应 |
| 2 | **快速过滤 & 匹配** | 依据地域、设备、兴趣等多维度过滤 |
| 3 | **竞价算法** | 打分、预算、频次检查，选最高出价 |
| 4 | **日志与上报** | 记录请求、竞价、点击、转化，支持查询 |
| 5 | **预算 & 频次控制** | 实时扣减，防止超支、频繁曝光 |
| 6 | **OpenRTB 2.5 兼容** | 标准化 JSON 接口，对接多家 SSP/DSP |

### 2. 非功能性需求（给出硬指标）  

| 指标 | 目标 | 含义 |
|------|------|------|
| **DAU** | 5,000,000 | 同时在线的终端用户数 |
| **峰值 QPS** | 150,000 | 大约 13 亿次/日请求 |
| **99.9% RT ≤ 30 ms** | 包括网络 + 业务处理 | 竞争激烈，延迟直接影响收益 |
| **可用性 99.99%** | 月停机 ≤ 4.38 h | 必须热备、自动故障转移 |
| **存储 10 PB/年** | 主要是日志、历史数据 | 写多读少，归档冷存 |
| **预算一致性 ≤ 1 s** | 扣费及时，防止超支 | 必须近实时强一致性 |

### 3. 初步容量估算  

| 项目 | 计算方式 | 结果 |
|------|----------|------|
| **每秒请求数** | 150,000 QPS | 150k |
| **并发请求数** | QPS × 平均响应时间 | 150k × 0.03 s ≈ 4,500 并发 |
| **单请求数据量** | OpenRTB 请求 ≈ 1 KB, 响应 ≈ 0.5 KB | 1.5 KB |
| **网络流量** | (请求+响应) × QPS | 1.5 KB × 150k ≈ 225 MB/s ≈ 1.8 Gbps |
| **日志写入速率** | 假设每请求产生 2 条日志（请求+响应） | 2 × 1 KB × 150k ≈ 300 MB/s |
| **预算/频次检查** | 需要在 ≤ 1 ms 内完成 | 需在内存/高速缓存层完成 |

> **结论**：单机（单节点）很难满足 150k QPS、30 ms RT 以及 99.99% 可用性，必须从一开始就采用 **分布式、水平扩展** 的架构。  

---  

## 第二步：高层架构设计  

### 1. 最小可用系统（MVP）  

```
[Client] → (Load Balancer) → [RTB API Server] → [Bid Engine] → [Response]
```

- **Load Balancer**：提供 4xx/5xx 错误的快速转发，使用 DNS 轮询 + LVS/NGINX。  
- **RTB API Server**：负责解析 OpenRTB JSON，做基本校验。  
- **Bid Engine**：在内存中读取广告素材、过滤规则、预算快照，完成一次竞价。  

> **为什么先做 MVP**  
> - 能快速验证业务流程（请求 → 过滤 → 竞价 → 返回）是否正确。  
> - 为后续加入持久化、容错、扩容提供清晰的基线。  

> **不这么做的后果**  
> - 直接上高可用、分库分表的复杂方案，会导致需求不明确、实现难度爆炸，面试官会觉得你没有先理清业务。  

### 2. 完整高层架构（加入所有必备模块）  

```
                       ┌─────────────────────┐
                       │      CDN / DNS      │
                       └─────────┬───────────┘
                                 │
                       ┌─────────▼───────────┐
                       │   Global Load Balancer│
                       └─────┬───────┬───────┘
            ┌─────────────────┘       └─────────────────┐
            │                                         │
   ┌────────▼─────────┐                     ┌─────────▼─────────┐
   │  Edge API Layer  │                     │  Edge API Layer   │
   │ (NGINX+TLS)      │                     │ (NGINX+TLS)       │
   └───────┬──────────┘                     └───────┬───────────┘
           │                                        │
   ┌───────▼───────┐                        ┌───────▼───────┐
   │  RTB Service  │   ←→   Message Queue  │  RTB Service  │
   │  (Stateless) │  (Kafka/RocketMQ)    │  (Stateless) │
   └───────┬───────┘                        └───────┬───────┘
           │                                        │
   ┌───────▼───────┐                        ┌───────▼───────┐
   │   Bid Engine  │   ←→   Cache Layer   │   Bid Engine  │
   │ (Microservice)│   (Redis/ Aerospike)│ (Microservice)│
   └───────┬───────┘                        └───────┬───────┘
           │                                        │
   ┌───────▼───────┐                        ┌───────▼───────┐
   │   Budget DB   │   ←→   Persistence   │   Budget DB   │
   │ (NewSQL)      │   (PostgreSQL‑Citus)│ (NewSQL)      │
   └───────┬───────┘                        └───────┬───────┘
           │                                        │
   ┌───────▼───────┐                        ┌───────▼───────┐
   │   Log Store   │   ←→   Object Store  │   Log Store   │
   │ (ClickHouse) │   (S3/OSS)          │ (ClickHouse) │
   └───────────────┘                        └───────────────┘
```

**关键模块说明**  

| 模块 | 主要职责 | 选型建议 | 为什么选 |
|------|----------|----------|----------|
| **Global Load Balancer** | 跨地域流量分发、DNS 轮询、故障转移 | Anycast + Anycast DNS + Cloud LB (AWS Global Accelerator / GCP Cloud Load Balancing) | 全球流量均衡，降低单点压力 |
| **Edge API Layer** | TLS 终止、限流、IP 白名单、健康检查 | NGINX/Envoy + Lua 脚本 | 高性能、易扩展，支持动态限流 |
| **RTB Service** | 解析 OpenRTB、路由到业务队列 | Java/Go + gRPC/HTTP2 | 业务无状态，便于水平扩容 |
| **Message Queue** | 解耦请求接收与竞价执行，削峰 | Kafka（高吞吐）或 Pulsar | 持久化、分区、消费组天然实现负载均衡 |
| **Bid Engine** | 过滤、打分、预算/频次校验，返回 Creative | Go（低 GC）或 Rust | 需要在 **≤10 ms** 内完成全部逻辑，内存计算最省时 |
| **Cache Layer** | 广告主配置、过滤规则、预算快照的高速读取 | Redis Cluster（读写分离）或 Aerospike | 读写频繁、键值模型天然匹配 |
| **Budget DB** | 预算/频次的强一致性存储，事务扣费 | NewSQL（TiDB、CockroachDB、PostgreSQL‑Citus） | 支持 **ACID**，且可水平扩容 |
| **Log Store** | 大规模日志写入、实时查询 | ClickHouse（列式、冷热分层）或 Apache Druid | 高并发写入、低延迟聚合查询 |
| **Object Store** | 原始日志、归档、离线分析 | S3/OSS + Iceberg/Hudi | 费用低，支持 PB 级存储 |

> **设计原则**  
> 1. **分层解耦**：请求层 ↔ 业务层 ↔ 存储层，各自可以独立扩容。  
> 2. **尽量无状态**：RTB Service、Bid Engine 采用无状态服务，故障恢复只需要重新启动实例。  
> 3. **热点数据放缓存**：预算、频次、过滤规则等每秒访问量极高，必须落在毫秒级缓存。  

---  

## 第三步：数据库设计  

### 1. 关键实体概览  

| 实体 | 主键 | 主要字段 | 访问模式 |
|------|------|----------|----------|
| **Campaign（广告活动）** | campaign_id | advertiser_id, budget_daily, start_ts, end_ts, status | 按 campaign_id 查询，批量遍历过滤 |
| **Creative（创意）** | creative_id | campaign_id, material_url, price_cpm, targeting_json | 读取/写入频繁（过滤、扣费） |
| **Advertiser（广告主）** | advertiser_id | name, credit_limit, contact | 主要查询 |
| **UserFrequency（用户曝光频次）** | (user_id, creative_id, date) | cnt, last_show_ts | 实时读写 |
| **BudgetSnapshot** | (advertiser_id, date_hour) | spend, remaining_budget | 高频读写，缓存落地 |
| **Log（请求/响应/点击/转化）** | auto_id | type, ts, request_id, user_id, campaign_id, creative_id, payload | 只写不改，查询聚合 |

### 2. 关系型 vs. NewSQL  

- **预算/频次** 必须 **强一致**，因为预算超支直接导致金钱损失。传统 MySQL 单机无法满足 150k QPS，且水平扩容困难。  
- **NewSQL**（TiDB、CockroachDB、PostgreSQL‑Citus）提供 **水平分片 + 分布式事务**，兼顾 ACID 与扩展性。  

#### 表结构示例（PostgreSQL‑Citus）  

```sql
-- Campaign 表（分片键 campaign_id）
CREATE TABLE campaign (
    campaign_id BIGINT PRIMARY KEY,
    advertiser_id BIGINT NOT NULL,
    budget_daily BIGINT NOT NULL,        -- 微元（micro‑cents）
    start_ts TIMESTAMP NOT NULL,
    end_ts TIMESTAMP NOT NULL,
    status SMALLINT NOT NULL,
    targeting JSONB NOT NULL
) DISTRIBUTED BY (campaign_id);

-- Creative 表（分片键 creative_id）
CREATE TABLE creative (
    creative_id BIGINT PRIMARY KEY,
    campaign_id BIGINT NOT NULL,
    price_cpm BIGINT NOT NULL,           -- 微元 CPM
    material_url TEXT NOT NULL,
    targeting JSONB NOT NULL,
    status SMALLINT NOT NULL
) DISTRIBUTED BY (creative_id);

-- BudgetSnapshot（分片键 advertiser_id）
CREATE TABLE budget_snapshot (
    advertiser_id BIGINT,
    date_hour TIMESTAMP,                 -- 精确到小时
    spend BIGINT DEFAULT 0,
    remaining BIGINT,
    PRIMARY KEY (advertiser_id, date_hour)
) DISTRIBUTED BY (advertiser_id);

-- UserFrequency（分片键 user_id）
CREATE TABLE user_frequency (
    user_id BIGINT,
    creative_id BIGINT,
    date DATE,
    cnt INT DEFAULT 0,
    last_show_ts TIMESTAMP,
    PRIMARY KEY (user_id, creative_id, date)
) DISTRIBUTED BY (user_id);
```

### 3. 缓存层（Redis）  

- **Key 设计**  
  - `campaign:{id}` → `hash`（campaign 基本信息）  
  - `creative:{id}` → `hash`（price、targeting）  
  - `budget:{advertiser_id}:{hour}` → `string`（剩余预算，原子递减）  
  - `freq:{user_id}:{creative_id}:{date}` → `int`（曝光次数）  

- **TTL**  
  - 预算键：`1h + 5m`（防止跨小时误差）  
  - 频次键：`24h`（每日频次）  

> **为什么要把这些数据放缓存**  
> - **预算扣减** 必须在 **≤1 ms** 内完成，单靠 NewSQL 的分布式事务仍有网络往返延迟。  
> - **频次控制** 同理，需要在本地快速判断并递增。  

> **不放缓存的后果**  
> - 每个请求都要走网络到 DB，导致 **RT > 30 ms**，甚至出现超时。  

### 4. 日志存储（ClickHouse）  

- **表结构（MergeTree）**  

```sql
CREATE TABLE rtb_log (
    event_type Enum('request' = 1, 'bid' = 2, 'click' = 3, 'conversion' = 4),
    ts DateTime,
    request_id String,
    user_id UInt64,
    advertiser_id UInt64,
    campaign_id UInt64,
    creative_id UInt64,
    payload JSON,
    hour UInt32
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ts)
ORDER BY (hour, advertiser_id, campaign_id);
```

- **写入方式**：Bid Engine 通过 **Kafka → ClickHouse Sink**（Flink、Kafka‑Connect）实现 **秒级写入**。  

---  

## 第四步：核心 API 设计  

### 1. 对外 OpenRTB 2.5 接口  

| 方法 | 路径 | 请求体 | 响应体 | 关键字段 |
|------|------|--------|--------|----------|
| POST | `/rtb/bid` | OpenRTB `BidRequest`（JSON） | OpenRTB `BidResponse`（JSON） | `id`, `imp`, `device`, `geo` 等 |
| GET  | `/metrics` | — | Prometheus metrics | QPS、RT、错误率 |
| POST | `/log/click` | `{request_id, user_id, timestamp}` | 200 OK | 用于同步点击上报（异步） |

> **实现要点**  
> - **限流**：在 Edge API Layer 按 IP、Publisher ID 限流（令牌桶）。  
> - **幂等性**：每个 `request_id` 全局唯一，Click/Conversion 上报使用同一个 ID，保证重复上报不导致二次扣费。  

### 2. 内部微服务 API（Bid Engine ↔ Cache / DB）  

| 调用方 | 被调用方 | RPC 方法 | 参数 | 返回 | 超时 |
|--------|----------|----------|------|------|------|
| RTB Service | Bid Engine | `Bid(request: BidRequest) -> BidResult` | 完整请求 | 选中的 Creative + price | 20 ms |
| Bid Engine | Cache (Redis) | `GET budget:{advertiser_id}:{hour}` | key | 剩余预算（int） | 1 ms |
| Bid Engine | Cache (Redis) | `INCRBY freq:{user_id}:{creative_id}:{date}` | key, 1 | 新频次值 | 1 ms |
| Bid Engine | Budget DB | `UPDATE budget_snapshot SET spend = spend + ?, remaining = remaining - ? WHERE ...` | delta | 成功/失败 | 5 ms |
| RTB Service | Log Sink | `Produce(topic, message)` | Kafka topic | - | 异步 |

> **为什么使用 RPC 而不是直接访问 DB**  
> - **解耦**：Bid Engine 可以独立升级，不受底层 DB 变更影响。  
> - **超时控制**：可以在业务层快速返回错误，避免阻塞。  

---  

## 第五步：详细组件设计  

### 1. 请求入口（Edge API Layer）  

- **技术栈**：NGINX + Lua（OpenResty）或 Envoy + WASM。  
- **功能**：  
  - TLS 终止、HTTP/2 支持。  
  - **限流**：基于 Publisher ID、IP、全局 QPS。  
  - **请求体大小校验**（防止恶意大包）。  
  - **健康检查**：返回 200/503。  

- **代码示例（Lua）**  

```lua
-- limit_req.lua
local limit_req = require "resty.limit.req"
local lim, err = limit_req.new("req_limit", 150000, 0.1)   -- 150k QPS，burst 10%
if not lim then
    ngx.log(ngx.ERR, "failed to instantiate a limiter: ", err)
    return ngx.exit(500)
end

local key = ngx.var.remote_addr   -- 可以换成 publisher_id
local delay, err = lim:incoming(key, true)
if not delay then
    if err == "rejected" then
        return ngx.exit(429)
    end
    ngx.log(ngx.ERR, "failed to limit req: ", err)
    return ngx.exit(500)
end
```

### 2. RTB Service（Stateless）  

- **语言**：Go（低 GC、原生并发）或 Java（成熟生态）。  
- **入口函数**：`handleBidRequest(c *gin.Context)` → 解析 → 发送到 **Bid Engine**（同步调用） → 返回。  

- **关键点**：  
  - **JSON 解析**使用 **jsoniter**（比标准库快 2‑3 倍）。  
  - **请求 ID**使用 **UUID v4** 或 **Snowflake**，保证全局唯一。  
  - **异常捕获**：对内部错误返回 **204 No‑Bid**，而不是 5xx，防止影响 SSP。  

### 3. Bid Engine（微服务）  

- **部署**：K8s Deployments，Pod 数量根据 CPU 配置水平扩容。  
- **核心流程**  

  1. **过滤**：  
     - 读取 **Campaign**、**Creative** 列表（先从缓存读取，缓存未命中再查询 DB 并回填）。  
     - 根据 **geo、device、app** 等维度在 **targeting JSON** 中做匹配（使用 **gojsonq** 或自实现的二进制位过滤，速度快）。  
  2. **预算检查**（原子操作）：  
     - `budget_key = fmt.Sprintf("budget:%d:%s", advertiser_id, hour)`  
     - 使用 **Redis Lua 脚本**一次性判断剩余预算并递减，确保 **强一致**（脚本在 Redis 内部原子执行）。  
  3. **频次控制**：  
     - `freq_key = fmt.Sprintf("freq:%d:%d:%s", user_id, creative_id, date)`  
     - 同样使用 Lua 脚本读取并递增，判断是否超过阈值。  
  4. **打分 & 选优**：  
     - 计算 **eCPM = price_cpm * quality_score**（质量分可以是预先计算好的常量或实时模型调用）。  
     - 取最高 eCPM 的 Creative。  
  5. **返回**：构造 **BidResponse**（包括 `price`, `adm`（广告素材 URL）等）。  

- **Lua 脚本示例（预算扣减）**  

```lua
-- budget_decr.lua
local budget = redis.call('GET', KEYS[1])
if not budget then return -1 end
budget = tonumber(budget)
local price = tonumber(ARGV[1])
if budget < price then
    return -2   -- insufficient budget
end
redis.call('DECRBY', KEYS[1], price)
return budget - price
```

- **调用方式（Go）**  

```go
script := redis.NewScript(budgetDecrLua)
res, err := script.Run(ctx, rdb, []string{budgetKey}, price).Result()
if err != nil { /* 处理错误 */ }
if res.(int64) < 0 { /* 预算不足，过滤掉 */ }
```

### 4. 缓存同步机制  

- **热点数据**（Campaign、Creative）**全量加载**到 Redis（或 Aerospike）中，采用 **写时复制**（Write‑Through）方式：  
  - 当后台管理系统修改 Campaign 时，写入 DB 同时发布 **Kafka** 事件 `campaign_update` → **Cache Sync Service** → **Redis** 更新。  
- **预算快照**：每小时一次 **批量落盘**到 NewSQL（持久化），防止 Redis 故障导致数据丢失。  

### 5. 预算与频次的强一致实现  

| 场景 | 处理方式 | 说明 |
|------|----------|------|
| **预算扣减** | Redis Lua 脚本（原子）+ 异步落库 | 1 s 内持久化到 NewSQL，若 Redis 故障则回滚日志补偿。 |
| **频次递增** | Redis Lua 脚本（原子）+ TTL | TTL 自动失效，无需额外清理。 |
| **异常回滚** | 当 NewSQL 写入失败，使用 **补偿事务**（重新恢复 Redis 中的值） | 防止“预算扣减成功、落库失败”导致账目不一致。 |

### 6. 日志与上报  

- **实时日志**：Bid Engine 把每一次 **BidResult** 通过 **Kafka** 发送到 `rtb_bid_log` topic。  
- **Click/Conversion**：前端 SDK 调用 `/log/click` → RTB Service → 直接写入 **Kafka** `rtb_event_log`。  
- **离线分析**：Flink 从 Kafka 消费，写入 **ClickHouse**（实时 OLAP）和 **S3**（离线冷数据）。  

### 7. 监控、报警、灰度发布  

| 维度 | 指标 | 采集方式 |
|------|------|----------|
| **流量** | QPS、TPS、请求来源 IP/Publisher | Envoy/NGINX stats → Prometheus |
| **性能** | 平均/99th RT、CPU、内存 | Exporter + Grafana |
| **业务** | 成功率（Bid Win Rate）、预算剩余、频次异常 | ClickHouse 聚合查询 |
| **异常** | 超时率、熔断次数、错误码分布 | Alertmanager + Slack/邮件 |

- **灰度发布**：使用 **K8s Deployment** + **Canary**（分配 5% 流量到新版本），配合 **Istio** 流量路由。  

---  

## 第六步：扩展性与高可用设计  

### 1. 水平扩容粒度  

| 层级 | 触发扩容条件 | 扩容方式 |
|------|--------------|----------|
| **Edge API** | 网络入口 QPS 超过 80%（如 120k QPS） | 增加 Nginx/Envoy 实例 → 自动加入 L4 LB |
| **RTB Service** | CPU 使用率 > 70% 或请求排队 > 5ms | 横向增加 Pods，K8s HPA 根据 CPU/自定义指标（QPS）伸缩 |
| **Message Queue** | Partition 堆积 > 1 min | 扩容 Kafka Broker、增加 Partition 数量 |
| **Bid Engine** | 单实例并发 > 10k | 增加 Pods，Kafka Consumer Group 自动均衡分区 |
| **Cache（Redis）** | 命中率 < 90% 或内存占用 > 80% | 增加节点，采用 **Cluster** 模式（水平分片） |
| **Budget DB** | 写入 TPS > 50k | 添加节点，使用 **NewSQL** 自动分片 |
| **Log Store** | 写入速率 > 300 MB/s | 增加 ClickHouse 节点，开启 **Distributed** 表 |

> **自动扩缩容**：K8s HPA + **Cluster Autoscaler**（云平台）配合 **Prometheus Adapter**，实时监控 CPU、QPS、Queue Length。  

### 2. 故障隔离与容错  

| 故障场景 | 设计方案 | 业务影响 |
|----------|----------|----------|
| **单机/Pod 死亡** | K8s 自动重启、ReplicaSet ≥ 2 | 无请求丢失，短暂延迟 |
| **Redis 故障** | 主从复制 + Sentinel，自动故障转移；**双写**（写入新SQL） | 暂时使用旧预算快照，误差 ≤ 1 s |
| **Kafka 分区不可用** | 多副本（replication.factor=3），自动 leader 迁移 | 少量请求可能短暂排队 |
| **Budget DB 写入超时** | 采用 **幂等写入** + **补偿日志**（写入失败后重试） | 短暂预算不一致，随后自动修复 |
| **网络分区导致部分 DSP 不可达** | **熔断**（Hystrix/Resilience4j）+ **备份广告池**（本地预置低价广告） | 返回默认广告，仍满足 30 ms 时限 |
| **机房整体失联** | **多活跨地域**（每个 Region 部署完整链路），使用 **Anycast DNS** 路由流量 | 流量自动切换到其它 Region，业务不中断 |

### 3. 降级策略  

- **竞价超时降级**：Bid Engine 对每个 DSP 设定 **30 ms** 超时，若超时则直接跳过该 DSP，使用 **本地缓存的备选创意**。  
- **预算失效降级**：当 Redis 不可用，系统进入 **“预算保守模式”**：只使用 **已预留的安全预算**（如每日总预算的 90%），防止超支。  
- **日志降级**：如果 ClickHouse 写入阻塞，暂时改为 **本地文件缓冲**，后台批量补偿。  

### 4. 数据一致性方案细化  

| 操作 | 关键步骤 | 一致性保证 |
|------|----------|------------|
| **预算扣减** | 1. Redis Lua 检查并扣减<br>2. 同步写入 NewSQL（异步）<br>3. 若 NewSQL 失败，写入 **补偿表**，后续定时任务回滚 Redis | **最终一致**（≤ 1 s） |
| **频次控制** | 只在 Redis 完成原子递增，TTL 自动失效 | **强一致**（实时） |
| **广告素材更新** | 1. 写 DB<br>2. 发布 Kafka 事件<br>3. Cache Sync Service 更新 Redis | **读后即写**（缓存最终一致） |

---  

## 第七步：常见面试追问与回答  

### Q1️⃣ 预算扣减如何做到既快又不超支？  

**回答要点**：  
1. **缓存+原子脚本**：在 Redis 中维护 **budget:{advertiser_id}:{hour}**，使用 Lua 脚本一次性判断并递减，保证 **毫秒级** 原子操作。  
2. **双写持久化**：同步把扣减操作写入 NewSQL（NewSQL 支持分布式事务），若写失败记录到补偿日志，后台定时任务回滚 Redis。  
3. **幂等请求**：每个竞价请求携带唯一 `request_id`，若重复请求直接返回已扣减结果，防止因网络重试导致二次扣费。  

**如果不使用 Redis**：每次都走 NewSQL，网络往返 + 两阶段提交会导致 **RT > 30 ms**，且在高并发下锁竞争会导致超时。  

### Q2️⃣ QPS 突增到 300,000，系统如何快速扩容？  

**回答要点**：  
- **横向扩容**：K8s HPA 自动根据 **CPU**、**自定义 QPS 指标** 增加 **RTB Service** 与 **Bid Engine** Pod。  
- **消息队列**：提前预留足够的 **Partition**（如 500），在突增时通过 **Kafka Rebalance** 将分区重新分配到更多 Broker。  
- **缓存**：Redis Cluster 通过 **add-node** 动态扩容，自动重新分片，保持命中率。  
- **自动化**：使用 **Prometheus Alert** 触发 **Cluster Autoscaler**，在 CPU 持续 > 80% 30 秒内自动加机器。  
- **容量预留**：在每个层级保留 **30% 余量**（预留实例或 Spot），防止突发流量导致排队。  

### Q3️⃣ 当某个机房网络分区，导致部分 DSP 无法响应，系统如何保证整体响应时延？  

**回答要点**：  
- **熔断器**：对每个 DSP 设置 **熔断阈值**（如 5 次连续超时），熔断后直接走 **本地备份创意池**。  
- **超时控制**：Bid Engine 对每个 DSP 调用设定 **30 ms** 超时，超时即返回 “无响应”。  
- **备份广告池**：在每个地区预先缓存 **低价、通用的创意**，在外部 DSP 不可达时直接返回，保证 **RT ≤ 30 ms**。  
- **监控告警**：分区检测到后，自动通知运维并开启 **流量切换**（Anycast DNS 重新路由到其它 Region）。  

### Q4️⃣ 为什么要把日志写入 ClickHouse 而不是直接写入关系型库？  

**回答要点**：  
- **写入吞吐**：ClickHouse 支持 **每秒数百万行** 的批量写入，远高于 MySQL/PostgreSQL。  
- **查询模式**：日志主要用于 **聚合分析**（PV、CTR、收入等），列式存储天然适合。  
- **成本**：PB 级日志在关系型库成本极高，且维护难度大。  

### Q5️⃣ 系统如何实现 99.99% 的可用性？  

**回答要点**：  
1. **多活跨地域**：每个 Region 部署完整链路，Anycast DNS 进行流量切换。  
2. **冗余**：所有关键组件（LB、RTB Service、Bid Engine、Redis、Kafka、NewSQL）均采用 **至少 3 副本**。  
3. **自动故障转移**：Redis Sentinel、Kafka Controller、K8s Pod 重启，保证单点故障恢复时间 < 30 s。  
4. **灰度发布 + 蓝绿部署**：新版本上线前在小流量验证，避免全局故障。  

---  

## 心得与反思  

### 1️⃣ 本题最难的设计决策  

| 决策 | 难点 | 思考过程 |
|------|------|----------|
| **预算实时扣减的强一致性** | 必须在 **≤1 s** 内完成扣减，同时又要防止单点故障导致数据丢失。 | - 先想到直接用 NewSQL，发现网络延迟不满足 30 ms。<br>- 再考虑仅用缓存，担心宕机丢失预算。<br>- 最终折中：**Redis Lua 脚本**实现毫秒级原子扣减，**异步双写**到 NewSQL 并做补偿日志，实现“**秒级最终一致**”。 |
| **在毫秒级完成全链路过滤 & 竞价** | 需要同时满足 **过滤复杂度**（多维度）和 **预算/频次检查**（原子操作）。 | - 评估了逐条遍历、规则引擎、BitSet 等方案。<br>- 选用 **预计算的二进制位掩码 + 内存过滤**，把复杂规则压缩到 **Redis Hash** 中，查询时只做位运算，极大降低 CPU 开销。 |

### 2️⃣ 新手最容易犯的错误  

| 错误 | 说明 | 正确做法 |
|------|------|----------|
| **把所有业务都写进单体服务** | 单体难以水平扩容，热点（预算、频次）会导致性能瓶颈。 | 将 **RTB Service**、**Bid Engine**、**Cache**、**DB** 明确分层，保持 **无状态**。 |
| **忽视幂等性和去重** | 网络抖动导致请求重试，会出现 **双扣费**、**双曝光**。 | 使用 **全局唯一 request_id**，在日志/预算扣减层实现 **幂等检查**。 |
| **只关注功能不考虑监控** | 系统上线后故障定位困难，恢复慢。 | 在设计时就加入 **指标、报警、可观测性**（Prometheus + Grafana）。 |
| **只用关系型库存日志** | 写入吞吐不够，查询慢，成本高。 | 使用 **列式 OLAP**（ClickHouse）+ **对象存储**（S3）做冷热分层。 |

### 3️⃣ 学习建议与可延伸方向  

1. **基础功底**  
   - 熟悉 **OpenRTB** 协议、JSON 编码/解码。  
   - 掌握 **分布式系统** 基础概念：CAP、BASE、分片、复制、事务。  

2. **实战练习**  
   - 搭建 **小型 RTB Demo**：使用 Go + Nginx + Redis + Kafka，先实现请求 → 过滤 → 简单竞价。  
   - 在本地加入 **Prometheus** + **Grafana**，观察 QPS、RT。  

3. **深入阅读**  
   - 《Designing Data‑Intensive Applications》：了解 NewSQL、分布式事务。  
   - 《Real‑Time Bidding at Scale》：业界公开的系统架构案例（如 Google AdX、Meta）。  

4. **进阶方向**  
   - **机器学习模型**：如何在竞价阶段调用实时评分模型（如 TensorFlow Serving）。  
   - **流处理**：使用 Flink / Spark Structured Streaming 实时计算 **CTR、eCPM**。  
   - **隐私合规**：GDPR、CCPA 对用户 ID、日志存储的影响。  

> **一句话总结**：系统设计不是一次性“一次画完”，而是 **需求 → 关键瓶颈 → 逐层拆解 → 选型 → 可观测** 的迭代过程。掌握了这套思路，面对任何面试题都能从容应对。  

祝你面试顺利，设计出自己的“千亿级”RTB 系统！ 🚀  
