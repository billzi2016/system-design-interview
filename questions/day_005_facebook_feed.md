# 第 5 天：设计 Facebook Feed

> 生成日期：2026-05-21

---

## 题目背景  
Facebook Feed（动态墙）是用户打开 Facebook 后首先看到的内容流，聚合了其好友、关注页面以及广告等信息，并依据个性化排序模型展示给用户。系统需要在海量用户、海量内容的情况下实现实时、相关性高且低延迟的内容分发。

## 面试场景设定  
> **面试官**：今天我们来讨论一下如何设计一个可以支撑全球数亿活跃用户的 Facebook Feed。请先从整体思路说起，重点考虑 **用户发帖 → 内容分发 → 用户阅读** 这条核心链路。你会如何设计系统的架构、数据模型以及关键的性能优化点？

## 功能性需求  

| 编号 | 功能描述 |
|------|----------|
| 1 | **用户发帖**：用户可以发布文字、图片、视频等多媒体内容。系统需要接收、存储并在后续 Feed 中分发。 |
| 2 | **关注/好友关系管理**：用户可以关注页面或添加好友，系统需要维护这些关系并用于 Feed 的生成。 |
| 3 | **个性化排序**：根据用户兴趣、社交关系、内容新鲜度等因素，对候选帖子进行打分并排序，返回给用户。 |
| 4 | **互动行为**：用户可以对帖子进行点赞、评论、分享，这些行为会影响后续排序并实时展示。 |
| 5 | **实时更新**：用户打开 Feed 时能够看到最近几秒内产生的新帖子或互动（如新评论），延迟尽可能低。 |
| 6 | **分页/下拉加载**：支持无限滚动，按时间或分数分页加载历史 Feed。 |

## 非功能性需求  

| 指标 | 目标值（估算） | 说明 |
|------|----------------|------|
| DAU（日活跃用户） | **3 × 10⁸**（3 亿） | 全球规模 |
| QPS（读取请求） | **2 × 10⁴**（20k） 每秒 Feed 拉取请求 | 假设 1/10 用户每秒发一次请求 |
| QPS（写入请求） | **5 × 10³**（5k） 每秒发帖、点赞、评论 | 读写比例约 4:1 |
| 端到端延迟 | **< 200 ms** | 从用户发帖到其好友看到的时间 |
| 可用性 | **99.9%**（每月约 43 分钟宕机） | 对用户体验要求高 |
| 存储容量 | **≈ 500 PB**（年增量约 50 PB） | 包含原始媒体、元数据、日志等 |

## 系统边界  

**本题需要设计并讨论的范围**  
- 用户关系模型（关注/好友）  
- 帖子写入、存储与分发（包括媒体的元数据管理）  
- Feed 的生成、排序、缓存与分页  
- 互动行为的写入、即时更新机制  
- 基本的监控、容错与扩容策略  

**本题** **不需要** 考虑的范围  
- 视频/图片的转码与 CDN 细节（可视为已有黑盒服务）  
- 广告投放系统、推荐系统的机器学习模型实现细节  
- 私信、群聊、活动等非 Feed 功能  
- 法律合规、内容审查（视为外部服务）  

## 提示与追问  

1. **粉丝（fan‑out）策略**：在用户拥有数百万粉丝的情况下，你会如何设计帖子分发的 fan‑out 机制，如何平衡实时性与成本？  
2. **排序与缓存**：请说明如何结合热点缓存（如 Top‑K 缓存）与实时计算，既保证热点内容的低延迟，又能对长尾用户提供个性化排序。  
3. **一致性模型**：在点赞、评论等互动行为的写入后，系统如何保证用户看到的 Feed 与后台数据的一致性？你会选择哪种一致性模型（强一致、最终一致等），并说明权衡原因。

---

# 题解

## 解题思路总览  

在一次面试里，**“从零开始设计 Facebook Feed”** 常常是面试官用来检验候选人对 **系统拆解、容量规划、数据模型、缓存/异步、容错、监控** 等全栈能力的。  
下面这篇答案把 **“先做最小可用系统（MVP） → 逐步加特性 → 高可用、可扩展”** 的思路展开，**每一步都会说明为什么要这么做、如果不这么做会出现什么问题**，帮助完全没有系统设计经验的同学从 “看不懂需求” 到 “能自信写出完整方案”。  

> **核心链路**：  
> 1️⃣ **用户发帖** → 写入持久化存储 + 触发分发（fan‑out）  
> 2️⃣ **Feed 生成** → 根据用户关系、排序模型挑选候选、打分、排序  
> 3️⃣ **用户阅读** → 通过缓存/实时计算返回分页结果，随后交互（点赞/评论）回写并影响后续排序  

下面依次展开每个章节。

---

## 第一步：理解需求与规模估算  

### 1️⃣ 功能需求拆解  

| 编号 | 功能 | 关键点 | 对系统的影响 |
|------|------|--------|---------------|
| 1 | 用户发帖 | 多媒体（文字、图片、视频）| 需要可靠的写入路径、媒体元数据、后续 fan‑out |
| 2 | 关注/好友关系 | 双向好友、单向关注 | 关系查询是 Feed 生成的入口 |
| 3 | 个性化排序 | 兴趣、社交、时效 | 排序计算的性能是瓶颈，需要离线特征 + 实时加权 |
| 4 | 互动行为 | 点赞/评论/分享 | 写入频繁，需要实时反映在 Feed 中 |
| 5 | 实时更新 | 秒级新帖/新评论 | 需要推送/实时读取、缓存失效 |
| 6 | 分页/下拉加载 | 基于时间/分数 | 需要支持 “向后翻页” 与 “向前刷新” 两种模式 |

### 2️⃣ 非功能需求拆解  

| 指标 | 估算 | 为什么重要 |
|------|------|-----------|
| DAU 3×10⁸ | 全球用户规模 | 决定 **横向扩展** 的上限 |
| 读取 QPS 20k/s | 1/10 用户每秒一次 Feed 拉取 | 读取是系统的 **主流流量**，需要高并发读取路径 |
| 写入 QPS 5k/s | 发帖+互动 | 写入相对较少，但 **时效性要求高** |
| 延迟 <200ms | 端到端 | 用户体验关键，尤其是 **新帖的即时可见** |
| 可用性 99.9% | 每月 43 分钟宕机 | 业务对可用性要求高，需要 **冗余、快速恢复** |
| 存储 500 PB/年 | 包括媒体、日志 | 需要 **分层存储、冷热分离**，成本控制 |

> **容量估算**（粗略）  
> - **每日新帖**：假设 5% 活跃用户每日发 1 条 ⇒ 3e8 * 0.05 ≈ 15 M 条/天  
> - **单条大小**：文字 1 KB + 1 张图片 100 KB（压缩后） ≈ 101 KB ≈ 0.1 MB  
> - **每日数据量**：15 M * 0.1 MB ≈ 1.5 TB/天 → **≈ 550 TB/年**（不算日志、备份）  
> - **互动日志**（点赞、评论）≈ 5 k QPS → 432 M/天 ≈ 0.4 TB/天  

以上估算帮助后续 **分库分表、分片、冷热存储** 的决策。

---

## 第二步：高层架构设计  

### 1️⃣ 从 MVP 开始的最小可用系统  

```
[Client] → API Gateway → Auth Service
                     |
                     ├─ Post Service (写帖子)
                     ├─ Feed Service (读 Feed)
                     └─ Interaction Service (点赞/评论)
```

- **单体数据库**（如 MySQL）存储 **用户、关系、帖子、互动**。  
- **同步调用**：客户端请求 → API Gateway → 对应业务服务 → DB。  
- **优势**：实现快速、代码少，容易验证业务流程。  
- **缺点**：单点瓶颈、难以水平扩展、无法满足 200 ms 延迟。

### 2️⃣ 逐步演进到分布式高可用架构  

```
                           +-------------------+
                           |   CDN (媒体文件) |
                           +--------+----------+
                                    |
                 +------------------+------------------+
                 |                                     |
          +------+------+                      +-------+------+
          |   Frontend  |                      |   Mobile   |
          +------+------|                      +------+------+
                 |                                   |
          +------+-------------------+---------------+------+
          |  API Gateway / Edge Layer (TLS termination, rate limit) |
          +--------------------------+------------------------------+
                                     |
               +---------------------+---------------------+
               |                                           |
   +-----------+-----------+               +---------------+---------------+
   |   Auth & Rate Limiter |               |   Traffic Router (A/B test) |
   +-----------+-----------+               +---------------+---------------+
               |                                           |
   +-----------+-----------+               +---------------+---------------+
   |   Feed Service (Read) |               |   Write Services (Post, Like, Comment) |
   +-----------+-----------+               +---------------+---------------+
               |                                           |
   +-----------+-----------+               +---------------+---------------+
   |   Fan‑out Service (Async)                |   Ranking Service (ML)          |
   +-----------+-----------+               +---------------+---------------+
               |                                           |
   +-----------+-----------+               +---------------+---------------+
   |   Timelines Store (NoSQL)  (User‑centric)  |   Interaction Store (NoSQL)   |
   +-----------+-----------+               +---------------+---------------+
               |                                           |
   +-----------+-----------+               +---------------+---------------+
   |   Relationship Service (Graph DB)           |   Metrics & Monitoring          |
   +-----------------------+--------------------+-------------------------------+
```

#### 关键组件解释  

| 组件 | 作用 | 为何要拆分 |
|------|------|-----------|
| **API Gateway** | 统一入口、TLS、限流、灰度发布 | 防止业务服务直接暴露，简化安全、运维 |
| **Auth Service** | 鉴权、生成用户 Token | 解耦鉴权，支持 OAuth、SSO |
| **Write Services** (Post / Interaction) | 负责写入、校验、落库 | 读写分离，写入流量可单独扩容 |
| **Fan‑out Service** | 异步把新帖复制到关注者的 Timeline | 解决 **“单条帖需要推送给上百万粉丝”** 的扩散问题 |
| **Timeline Store** | 每个用户的 **已排序的 Feed 列表**（预计算） | 读取路径只要查询 NoSQL，满足毫秒级延迟 |
| **Ranking Service** | 实时/离线为每条帖计算 **Score**，写回 Timeline | 将计算逻辑抽离，支持机器学习模型迭代 |
| **Interaction Store** | 点赞、评论等增量数据（可用 KV/TSDB） | 交互频繁，独立存储降低热点写入冲突 |
| **Relationship Service** | 用户‑好友/关注图（Graph DB） | 关系查询需要高效遍历，使用图数据库或专用缓存 |
| **Metrics & Monitoring** | 监控、告警、日志、链路追踪 | 高可用的必备，快速定位瓶颈 |

### 3️⃣ 数据流示例  

1. **发帖** → Post Service → 写入 **Post DB** + 发送 **Kafka** 事件 → Fan‑out Service 消费 → 把帖子 ID（和 Score）写入每个关注者的 **Timeline**（NoSQL）  
2. **读取 Feed** → Feed Service → 从 **Timeline Store** 按用户 ID 取最新 N 条（已排序） → 若 Timeline 失效则走 **实时计算路径**（查询关系、候选、Ranking） → 返回给前端  
3. **点赞** → Interaction Service → 写入 **Interaction Store** + 发送 **Kafka** → Ranking Service 收到增量 → 重新计算受影响帖子的 Score → 更新对应用户的 Timeline（增量刷新）  

---

## 第三步：数据库设计  

### 1️⃣ 关系模型 VS 文档模型  

| 数据 | 访问模式 | 推荐存储 |
|------|----------|----------|
| **用户信息**（profile） | 按 UID 查询、更新少 | RDBMS (MySQL) + Cache (Redis) |
| **用户关系**（关注/好友） | “我关注了谁”“谁关注了我” 高并发遍历 | **图数据库** (Neo4j/Dgraph) 或 **Adjacency List** 存在 Redis/SSDB |
| **帖子元数据**（ID、作者、时间、type） | 按 ID 查询、批量拉取、范围查询 | **分布式关系库**（MySQL sharding）或 **文档库**（Cassandra） |
| **Timeline**（用户 Feed 列表） | 按 UID 按 Score/时间倒序读取前 N 条 | **列式/宽表 NoSQL**（Cassandra、Scylla、HBase） |
| **互动日志**（点赞/评论） | 高并发写入、按帖子聚合统计 | **键值库**（Redis Sorted Set for likes, HBase for comments） |
| **排序特征**（机器学习特征向量） | 离线批处理、实时增量 | **对象存储**（S3）+ **Feature Store**（MLFlow） |

> **为什么不把所有数据都放 MySQL？**  
> - 读写热点（如热门帖的点赞）会导致行锁争用，单机扩展受限。  
> - Timeline 需要 **每秒上万次随机读**，传统 RDBMS 的 **行查询** 远不如列式/宽表的 **批量范围扫描** 快。  

### 2️⃣ 关键表/集合设计  

#### 2.1 用户表（MySQL）  

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id (PK) | BIGINT UNSIGNED | 全局唯一 |
| name | VARCHAR(64) | |
| email | VARCHAR(128) | |
| created_at | DATETIME | |
| status | TINYINT | 0=正常,1=封禁等 |

> **分库分表**：按 `user_id % N`（N≈256）水平分库，避免单库写热点。

#### 2.2 关系表（Redis + Graph DB）  

- **Followers Set**：`followers:{user_id}` → ZSET (member=user_id, score=follow_time)  
- **Following Set**：`following:{user_id}` → ZSET  

> **为什么使用 Redis ZSET？**  
> - 读取 “最近 N 位粉丝” 只需要 ZRANGE，时间 O(logN)。  
> - 写入（关注/取关）是 O(logN) 并且天然支持 **过期/TTL**（防止僵尸数据）。  
> - 对于数十亿用户，单机容量不足时可采用 **Redis Cluster**。

#### 2.3 帖子表（Cassandra）  

| Partition Key | Clustering Columns | 其他列 |
|---------------|--------------------|--------|
| author_id     | post_id (DESC)     | content_type, media_meta, created_at, score |

- **Partition by author** 让 **写入** 均匀分布。  
- **Clustering** 按 `post_id`（时间递增）倒序，便于作者自己翻页。  

#### 2.4 Timeline 表（Cassandra）  

| Partition Key | Clustering Columns | 其他列 |
|---------------|--------------------|--------|
| user_id       | score (DESC), post_id (DESC) | author_id, created_at, media_meta |

- **Score** 由 **Ranking Service** 计算（考虑新鲜度、社交关系、兴趣向量）。  
- **查询**：`SELECT * FROM timeline WHERE user_id=? LIMIT 20;` 直接返回已排序的 Feed。  

#### 2.5 互动表（Redis + HBase）  

- **点赞计数**：`post_like:{post_id}` → ZSET (user_id, like_time) 或 HyperLogLog（UV）  
- **评论存储**：`comment:{post_id}` → HBase 行，列族 `c:{comment_id}`（content, author, ts）  

> **实时性**：点赞直接写入 Redis，随后异步落库 HBase 供离线统计。

### 3️⃣ 缓存层  

| 数据 | 缓存策略 | 失效时机 |
|------|----------|----------|
| 用户 Profile | LRU (10 min) | 更新时主动刷新 |
| Timeline | **热点 Top‑K**（如前 100 条）放在 **Redis** | 新帖写入后主动推送到对应用户的缓存 |
| 关系集合 | LRU (5 min) | 关注/取关后立即失效 |
| 排序特征 | 本地机器学习模型缓存 | 每天/每小时刷新一次 |

> **为什么要多层缓存？**  
> - **热点 Feed**（明星、热门页）访问频率极高，放在 **Redis** 能把读取延迟降到 **1‑2 ms**。  
> - 冷门用户的 Timeline 仍然保存在 **Cassandra**，避免 Redis 爆炸。  

---

## 第四步：核心 API 设计  

下面给出最常用的几组 API，采用 **RESTful + gRPC** 双协议（前端使用 REST，内部服务间使用 gRPC），并说明 **请求‑响应时序**。

### 1️⃣ 发帖（Post）  

| 方法 | URL | 请求体 | 响应 | 关键流程 |
|------|-----|--------|------|----------|
| POST | `/api/v1/posts` | `{author_id, content, media_ids, type}` | `{post_id, status}` | 1. Auth → 2. Post Service 写入 Post DB 3. 产生 Kafka `PostCreated` 事件 4. 返回 post_id（可选同步返回 Timeline 预热） |

> **幂等性**：使用 **client‑generated UUID** 作为 `post_id`，保证网络抖动时的 **幂等写**。

### 2️⃣ 拉取 Feed  

| 方法 | URL | 参数 | 响应 | 关键流程 |
|------|-----|------|------|----------|
| GET | `/api/v1/users/{uid}/feed` | `?cursor=timestamp|score&limit=20` | `{items:[{post_id, author, media, score, liked, comment_count}], next_cursor}` | 1. 先查 **Redis Top‑K** → 若命中返回 2. 否则查询 **Timeline Store**（Cassandra） → 若 Timeline 失效走 **实时计算路径**（查询关系、候选、Ranking） |

### 3️⃣ 点赞（Like）  

| 方法 | URL | 请求体 | 响应 | 关键流程 |
|------|-----|--------|------|----------|
| POST | `/api/v1/posts/{post_id}/like` | `{user_id}` | `{status}` | 1. 写入 **Redis ZSET** `post_like:{post_id}` 2. 发送 `LikeEvent` 到 Kafka 3. Interaction Service 异步落库 HBase 4. Ranking Service 收到事件 → 重新计算 Score → 增量更新 Timeline（只对受影响用户的前 N 条） |

### 4️⃣ 评论（Comment）  

| 方法 | URL | 请求体 | 响应 | 关键流程 |
|------|-----|--------|------|----------|
| POST | `/api/v1/posts/{post_id}/comments` | `{user_id, content}` | `{comment_id}` | 1. 写入 **HBase** `comment:{post_id}` 2. 发送 `CommentEvent` → Ranking Service（评论权重提升） 3. 更新 Timeline（同点赞） |

### 5️⃣ 关注/取关  

| 方法 | URL | 请求体 | 响应 | 关键流程 |
|------|-----|--------|------|----------|
| POST | `/api/v1/users/{uid}/follow` | `{target_id}` | `{status}` | 1. 写入 **Redis ZSET** `following:{uid}` & `followers:{target_id}` 2. 发送 `FollowEvent` → Fan‑out Service 重新为 `uid` 拉取 **最新 Timeline**（一次性全量刷新） |
| DELETE | `/api/v1/users/{uid}/follow/{target_id}` | — | `{status}` | 同上，删除集合并失效缓存 |

---

## 第五步：详细组件设计  

### 1️⃣ Fan‑out Service（异步扩散）  

#### 1.1 两种 Fan‑out 策略  

| 场景 | 策略 | 说明 |
|------|------|------|
| **普通用户**（粉丝数 < 10k） | **Push‑based**（写入每个粉丝的 Timeline） | 通过 **Kafka Consumer** 并行写入 NoSQL，延迟 < 1 s |
| **大V/明星**（粉丝数 > 10k） | **Pull‑based**（不立即写入，用户读取时实时查询） | 只把帖子写入 **“热点缓存”**，在 Feed Service 中 **实时合并** 大V 的最新 10 条帖子（从 Post DB 拉取） |

> **为什么要混合？**  
> - **全推** 会在明星发帖时产生 **数十亿写入**，成本极高。  
> - **全拉** 对普通用户会导致每次读取都要遍历大量关系，延迟大。混合可以兼顾 **成本** 与 **实时性**。

#### 1.2 实现细节  

- **Kafka Topic**：`post_created`（partition by author_id）  
- **Consumer Group**：`fanout-worker`，水平扩展（每台机器负责一段用户 ID 范围）  
- **写入路径**：  
  1. 读取 `post_id、author_id、score`  
  2. 根据 `author_id` 查询 **Followers Set**（Redis）  
  3. 对每批（如 1000 条）使用 **批量写入**（Cassandra BATCH）写入对应粉丝的 Timeline  
- **幂等**：使用 **写入时间戳** 作为列的 TTL，防止重复写入导致 Score 错误。  

### 2️⃣ Ranking Service（排序引擎）  

#### 2.1 排序模型概览  

```
Score = w1 * FreshnessScore
      + w2 * SocialScore (friendship strength)
      + w3 * InterestScore (topic similarity)
      + w4 * EngagementScore (likes/comments)
      + w5 * PaidBoost (广告）
```

- **FreshnessScore**：`exp(-Δt / τ)`（τ≈1h）  
- **SocialScore**：基于 **二度关系**（好友的好友）与 **互动强度**（过去 30 天的交互次数）  
- **InterestScore**：用户兴趣向量（L2 相似度）与帖子的主题向量点积  
- **EngagementScore**：实时累计 **点赞/评论**（加权）  

#### 2.2 实时 vs 离线  

| 计算方式 | 频率 | 数据来源 | 适用范围 |
|----------|------|----------|----------|
| **离线批处理**（Spark/Flink）| 每 30 min | 大量历史特征、用户画像 | 生成 **基础 Score 基线**，写入 **UserScore Table** |
| **实时增量**（流处理）| 每秒 | 新增点赞、评论、关注 | **Score 调整**，发送 `ScoreUpdate` 到 Kafka → Fan‑out Service **增量更新** Timeline |

#### 2.3 结果写回  

- **ScoreUpdate** 包含 `post_id, user_id, new_score`。  
- Timeline Store 采用 **Cassandra LWT（轻量级事务）** 或 **CAS** 来保证同一条记录的 **Score 原子更新**，避免并发冲突。  

### 3️⃣ Feed Service（读取层）  

#### 3.1 查询路径  

1. **Cache Hit**：先查 **Redis Top‑K**（键：`timeline:{uid}:topk`）  
2. **Cache Miss**：查询 **Cassandra Timeline**（按 Score 降序），返回 `limit` 条  
3. **Timeline 失效**（如新用户或大 V）：进入 **实时计算路径**：  
   - 拉取 **关注列表**（Redis）  
   - 对每个关注者取最近 N 条帖子（Post DB）  
   - 调用 **Ranking Service**（gRPC）进行 **Score 计算**  
   - 合并、排序后返回，并 **写回** Timeline（缓存热点）  

#### 3.2 分页实现  

- **基于 Score 的 cursor**：`cursor = last_score|post_id`  
- 通过 `WHERE score <= ? AND post_id < ?` 实现 **stable pagination**（防止插入导致分页错位）。  

#### 3.3 防止 **热点写入冲突**  

- 使用 **分区键** `user_id`，**每个用户的 Timeline** 完全独立，避免跨用户写竞争。  
- 对 **大 V** 的 Timeline，采用 **写时复制（copy‑on‑write）**：只在用户主动拉取时生成 **私有视图**，不在全局 Timeline 中写入。  

### 4️⃣ Interaction Service（点赞/评论）  

- **写入路径**：  
  1. 接收 API → 先写 **Redis**（快速返回）  
  2. 发送 **Kafka** `InteractionEvent`（包括增量特征）  
  3. 异步落库 **HBase**（持久）  
  4. 同时发送 **ScoreUpdate** 到 Ranking Service  

- **读路径**：Feed Service 在返回 Feed 时会并发查询 **Redis** `post_like:{post_id}` 与 **HBase** `comment:{post_id}`，聚合到每条 Feed 中（**热点数据**放 Redis，**全量历史**放 HBase）。  

### 5️⃣ 监控、告警、灰度发布  

| 维度 | 关键指标 | 监控方式 |
|------|----------|----------|
| **系统健康** | CPU、内存、磁盘 I/O、网络流量 | Prometheus + Grafana |
| **业务指标** | QPS、成功率、错误率、延迟（p95） | OpenTelemetry tracing + Alertmanager |
| **缓存命中** | Redis hit率、Cassandra read latency | 自定义仪表盘 |
| **异常流** | 突发的 Fan‑out 错误、Kafka backlog | Kafka Cruise Control、Dead‑Letter Queue 监控 |
| **业务异常** | 单用户 Feed 为空、点赞回写失败 | 实时日志分析（ELK） |

> **灰度发布**：使用 **Canary** 或 **Feature Flag**（LaunchDarkly）把新模型或新缓存策略先放 1% 流量，监控关键指标后逐步扩大。  

---

## 第六步：扩展性与高可用设计  

### 1️⃣ 横向扩展  

| 组件 | 扩容方式 |
|------|----------|
| API Gateway | **水平增加实例**，使用 **L4 负载均衡**（NGINX/Envoy） |
| Auth Service | Stateless → 多实例 |
| Post / Interaction Service | **无状态** → 使用 **K8s Deployment**，水平伸缩 |
| Kafka | **分区**（按 author_id）+ **副本**（≥3） |
| Cassandra / Scylla | **节点扩容**（添加机器） → 自动重新分片 |
| Redis Cluster | **分片**（hash slot）+ **副本** |
| Fan‑out Workers | **Consumer Group** 自动负载均衡 |
| Ranking Service | **模型微服务**（Stateless）→ 多实例，使用 **GPU/CPU 弹性** |

### 2️⃣ 数据冗余与容错  

- **MySQL**：主从复制（GTID）+ **自动故障转移**（MHA）  
- **Cassandra**：RF=3（每条数据 3 副本）+ **跨机房复制**（NetworkTopologyStrategy）  
- **Redis**：主从 + Sentinel 或 **Cluster** 自动故障转移  
- **Kafka**：每个 Partition 3 副本，ISR（In‑Sync Replicas）保障写入成功  
- **HBase**：RegionServer 多副本，自动恢复  

> **故障场景**  
> 1. **单点写入失败**（Post DB） → 重试 + 限流 → 失败转为 **DLQ**，后台补偿。  
> 2. **Fan‑out 任务堆积** → 监控 Kafka backlog，自动扩容 Consumer；如果仍堆积，切换到 **Pull‑based** 临时策略。  
> 3 **Timeline 缓存失效** → 读取回退到 **实时计算**，确保用户仍能看到 Feed（但可能稍慢）。  

### 3️⃣ 延迟优化  

| 环节 | 优化手段 |
|------|----------|
| 网络 | 使用 **HTTP/2 + gRPC**，保持长连接，减少 RTT |
| 写入 | **异步写**（Kafka）+ **Batch**（Cassandra） |
| Fan‑out | **并行批量写入**，每批 500‑1000 条 |
| 排序 | **缓存热点 Score**，只对新交互增量计算 |
| 读取 | **热点 Timeline** 放 Redis，查询路径 < 2 ms；Cassandra 读取 < 10 ms |
| CDN | 媒体文件直接走 CDN，Feed 只返回 **URL**，不参与业务延迟 |  

> **目标**：整体 **<200 ms** →  
> - **网络 + Auth** ≈ 20 ms  
> - **Feed Service + Cache** ≈ 30 ms  
> - **Timeline DB** ≈ 50 ms  
> - **排序/聚合** ≈ 30 ms  
> - **返回** ≈ 20 ms  

### 4️⃣ 多租户 / 地域部署  

- **全球多活**：在 **北美、欧洲、亚洲** 部署独立集群，使用 **Geo‑DNS** 将用户请求路由到最近机房。  
- **数据同步**：跨地域使用 **Cassandra 跨 DC**（异步复制）和 **Kafka MirrorMaker**，保证 **最终一致**。  
- **容灾**：任一 DC 故障，DNS 自动切换到备份 DC，业务不间断（延迟稍升）。  

### 5️⃣ 费用控制  

| 成本项 | 控制方式 |
|--------|----------|
| 存储 | **冷热分层**：最近 30 天热点 Timeline 放 SSD，历史 Timeline 归档至对象存储（S3） |
| 计算 | **弹性伸缩**：峰值时自动扩容（K8s HPA），非高峰时缩容 |
| 网络 | **压缩**：gRPC + protobuf，减少带宽 |
| Fan‑out | **大 V Pull‑based**，避免写入暴增 |  

---

## 第七步：常见面试追问与回答  

| 追问 | 参考答案（要点） |
|------|-----------------|
| **1. 粉丝（fan‑out）策略：如果一个用户有 10M 粉丝，如何保证写入不成为瓶颈？** | - **混合推拉**：对 10M 粉丝采用 **Pull‑based**（不写入每个 Timeline），只把帖子写入 **热点缓存**；用户读取时实时合并大 V 的最新 N 条。<br>- **分段推送**：先把帖子写入 **热点 Top‑K**（如 1k 粉丝），其余粉丝在第一次打开 Feed 时进行 **异步拉取**（后台生成 Timeline）。<br>- **使用 Kafka 并行消费**，每台机器处理固定 UID 范围，避免单点写入压力。 |
| **2. 排序与缓存：如何在保证热点内容低延迟的同时，仍能对长尾用户做个性化排序？** | - **热点 Top‑K 缓存**（Redis）保存全局热度排序（Score 已计算），所有用户都能快速读取。<br>- **用户私有增量**：每个用户的 Timeline 存储 **已排序的私有列表**（包括个人兴趣加权），通过 **Ranking Service** 计算增量 Score 并写回。<br>- **读取时合并**：先取用户私有 Timeline（N 条），再从全局 Top‑K 中挑选不在私有列表的热点补齐，形成最终 Feed。 |
| **3. 一致性模型：点赞后用户看到的 Feed 与后台数据应该怎样保证一致性？** | - **写后读**：点赞写入 Redis 后立即返回成功，随后 **异步落库**。<br>- **最终一致**：Feed 中的点赞数使用 **Redis 计数**（实时）+ **后台批处理**（持久化）。<br>- **对用户可见**：因为点赞数是 **读‑写分离**，用户看到的数字是最新的 Redis 值，后台持久化在稍后完成，满足 **“读到最新写”**（Read‑Your‑Writes）而不需要强一致。 |
| **4. 如何处理 “时间线失效” 或 “缓存雪崩”？** | - **多级缓存**：Redis → 本地 LRU → Cassandra。即使 Redis 全失效，仍能从 Cassandra 拉取。<br>- **热点预热**：在热点内容写入后立即推送到缓存，使用 **写穿（write‑through）** 机制防止缓存穿透。<br>- **熔断/限流**：对 Timeline DB 查询设置 **超时**，超时返回 **空列表** 并触发后台 **异步重建**。 |
| **5. 为什么不直接在用户请求时实时遍历所有关注者的帖子？** | - **时间复杂度**：如果用户关注 5k 人，每人平均 10 条新帖，实时遍历需要 **50k 条** 数据并排序，延迟 > 500 ms。<br>- **资源浪费**：多数用户的 Feed 在短时间内不会变化，重复计算会导致 **CPU/IO** 高峰。<br>- **可扩展性**：实时遍历无法水平扩展，而 **预计算 Timeline** 能把热点查询压到缓存层，极大提升 QPS。 |
| **6. 如果要加入机器学习模型的实时特征（如最近 1 小时的点击流），如何做到低延迟？** | - **流处理**（Flink/Kafka Streams）实时聚合用户点击流，输出 **用户‑特征 KV** 到 **Redis**（TTL 1h）。<br>- **Ranking Service** 在计算 Score 时直接读取 Redis 中的实时特征。<br>- **特征缓存**：对热点用户使用 **本地内存缓存**（Guava），降低网络 RTT。 |

---

## 心得与反思  

### 1️⃣ 本题最难的 1‑2 个设计决策  

| 决策 | 难点 | 思考过程 |
|------|------|----------|
| **Fan‑out 方式的选型**（Push vs Pull） | 需要在 **成本**、**实时性**、**可扩展性** 之间找到平衡。| - 先估算最大粉丝数（>10M）导致写入量爆炸。<br>- 评估用户对大 V 内容的实时需求（秒级）。<br>- 结合业务：大 V 的热点内容占整体流量的 20% 左右，采用 **Pull‑based** 可把写入压到 80% 的普通用户。|
| **排序模型与缓存的耦合** | 排序模型频繁迭代，若直接写入缓存会导致 **缓存失效** 与 **模型回滚** 成本高。| - 将 **模型计算** 与 **缓存写入** 解耦：Ranking Service 只负责 **Score** 输出，Fan‑out/Timeline 负责 **写入**。<br>- 引入 **ScoreUpdate** 事件流，支持 **滚动回滚**（消费新模型的 Score 并重新写入）。|

### 2️⃣ 新手最容易犯的错误（至少 2 条）  

| 错误 | 为什么不行 | 正确做法 |
|------|------------|----------|
| **把所有数据都放在单体 MySQL** | 随着用户增长，写入热点（Timeline）会导致锁竞争、单点瓶颈，无法满足 20k QPS 读取。 | 按访问特性拆分：**关系数据** 用 MySQL，**热点时间线** 用 **Cassandra/Scylla**，**缓存** 用 Redis，**异步** 用 Kafka。 |
| **只实现 Push‑based Fan‑out**（每条帖子都写入所有粉丝的 Timeline） | 当明星用户拥有上百万粉丝时，单条帖子的写入量会达到 **数十亿**，导致写入延迟、磁盘 IO 爆炸。 | 采用 **混合推拉**：对普通用户 Push，对大 V Pull；对热点内容使用 **Top‑K 缓存**。 |

### 3️⃣ 学习建议和可延伸的方向  

| 方向 | 推荐学习资源 |
|------|--------------|
| **分布式缓存（Redis Cluster）** | 《Designing Data-Intensive Applications》章节 4；Redis 官方文档 |
| **消息队列 & 流处理** | Kafka 官方文档、Flink 实战教程 |
| **列式/宽表 NoSQL（Cassandra/Scylla）** | 《Cassandra: The Definitive Guide》 |
| **图数据库 & 关系查询** | Neo4j 官方教学、Dgraph 入门 |
| **机器学习排序（Learning to Rank）** | 《Learning to Rank for Information Retrieval》、Google RankNet 论文 |
| **系统可观测性** | 《Site Reliability Engineering》、OpenTelemetry 官方教程 |
| **高并发与限流** | 《Effective Go》中的并发模式、Netflix Hystrix 设计案例 |

> **一句话总结**：  
> 设计大规模 Feed 系统的核心是 **“把热点前移、把计算/写入前置、把不确定性异步化”**。先搭一个 **最小可用的读写路径**，再逐步引入 **Fan‑out、排序、缓存、容错**，每一步都要问自己 “如果流量翻十倍，这里会卡在哪儿？” 并据此演化架构。

祝你在面试中自信满满，设计出让面试官眼前一亮的方案！ 🚀  
