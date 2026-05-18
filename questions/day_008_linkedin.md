# 第 8 天：设计 LinkedIn

> 生成日期：2026-05-18

---

## 1. 题目背景  
LinkedIn 是一个面向职场的专业社交平台，用户可以创建个人职业档案、建立职业人脉、发布和查找招聘信息以及获取行业资讯。

## 2. 面试场景设定  
> **面试官**：  
> “今天我们来一起设计一个高可用、可扩展的 LinkedIn 核心系统。请你从需求出发，先给出系统的整体结构，然后逐步深入到关键组件的设计。我们先从最核心的功能——**个人档案与人脉网络**开始讨论，接下来请你阐述如何支撑每天数亿用户的查询、写入以及实时推荐。”

## 3. 功能性需求  

| 编号 | 功能描述 |
|------|----------|
| F1 | **用户注册 & 登录**：支持邮箱/手机号注册、OAuth 第三方登录、密码重置。 |
| F2 | **个人档案管理**：用户可以编辑、查看自己的职业经历、教育背景、技能标签、公开度设置。 |
| F3 | **人脉关系**：发送/接受连接请求、删除连接、查看二度/三度人脉图谱。 |
| F4 | **动态流（Feed）**：展示好友/关注的人的动态（职位变动、文章、分享），支持点赞、评论、转发。 |
| F5 | **招聘与求职**：发布职位、投递简历、搜索岗位、匹配推荐。 |
| F6 | **实时推荐**：基于用户画像、行为日志向用户推荐潜在连接、岗位、内容。 |

（实际实现时可以选取其中 4–5 项重点实现，其他作为加分项）

## 4. 非功能性需求  

| 指标 | 估算值 | 说明 |
|------|--------|------|
| **DAU** | 3.5 亿 | 全球活跃用户，假设 30% 为日活 |
| **QPS（查询）** | 150 k QPS | 主要是 Feed、搜索、人脉图谱等读请求 |
| **QPS（写入）** | 30 k QPS | 包括发布动态、发送连接请求、职位投递等 |
| **平均响应时延** | ≤ 200 ms（99%） | 前端交互感知阈值 |
| **可用性** | ≥ 99.99%（年宕机 ≤ 52 分钟） | 商业关键系统 |
| **存储规模** | 约 150 PB | 个人档案、动态、职位信息、日志等（假设 10 KB/用户 + 100 GB/天日志） |
| **一致性要求** | **强一致**（用户关系、职位投递）<br>**最终一致**（Feed、推荐） | 根据业务场景划分 |

## 5. 系统边界  

**本题范围内需要设计的功能**  
- 用户身份认证、个人档案、连接请求、人脉图谱查询、Feed 读取与写入、招聘信息的基本 CRUD、实时推荐的核心 pipeline。  
- 数据存储、缓存、搜索/索引、消息队列、异步计算、监控报警等关键基础设施。  

**本题范围外（不考虑）**  
- 企业内部 HR 管理系统、广告投放平台、移动端离线同步、视频/音频上传与转码、跨地区法律合规（GDPR）细节、聊天/即时通讯功能、第三方企业招聘服务的深度集成。  

## 6. 提示与追问  

1. **数据模型与分区**  
   - “如果把用户的关系图存储在关系型数据库和图数据库之间，你会如何选型？如何实现水平分区以支撑 300 M+ 用户？”  

2. **高并发写入冲突**  
   - “在大量用户同时发送连接请求的场景下，如何保证‘双向连接’的一致性并避免脏读？”  

3. **实时推荐系统**  
   - “请描述从用户行为日志到推荐结果展示的完整流水线，包括数据采集、特征工程、模型推理、结果缓存的技术选型和延迟控制。”  

---

# 题解

## 解题思路总览
本篇答案把 **从“我连需求都看不懂”** 到 **“可以在白板上完整阐述高可用的 LinkedIn 核心系统”** 的全过程拆成若干层次，**每一步都会解释“为什么要这么做，若不这么做会出现什么问题”。  
阅读顺序建议：

1. **先看需求与规模估算**，弄清楚系统要支撑多少用户、多少 QPS、哪些功能必须强一致、哪些可以最终一致。  
2. **再看高层架构**，了解系统如何划分子系统、如何通过网关、缓存、消息队列等基础设施实现“可扩展+高可用”。  
3. **随后深入到数据库、API、关键组件**，这里会解释选型（关系型、图数据库、搜索引擎…）以及分区、索引、事务方案。  
4. **最后讨论容灾、监控、扩容**，以及面试官常追问的细节。  

> **新手提示**：在面试中，**先把需求说清楚** 再去画系统图，千万别一上来就画出“一堆微服务”。需求是所有设计的根基，缺了需求再好的架构也是空中楼阁。

---

## 第一步：理解需求与规模估算

| 类别 | 关键点 | 解释 |
|------|--------|------|
| **核心业务** | 个人档案、关系网络、Feed、招聘、实时推荐 | 这些是**读写混合**且对一致性要求不一样的业务。 |
| **用户规模** | 3.5 亿 DAU（≈30% 全球用户） | 这意味着 **每日活跃用户 ≈ 1.05 亿**。 |
| **流量** | 150 k QPS 查询、30 k QPS 写入 | 读取占 5:1，写入相对少但涉及事务（如建立双向关系）。 |
| **性能目标** | 99.99% 可用、99% 请求 ≤200 ms | 系统必须具备**容错**、**快速失败**、**熔断**等机制。 |
| **存储** | 150 PB（≈10 KB/用户 + 100 GB/天日志） | 数据量极大，需要 **冷热分离**、**分布式存储**。 |
| **一致性** | 强一致：关系、投递<br>最终一致：Feed、推荐 | 业务对**事务**的要求不同，后端设计要对应。 |
| **选定功能**（面试可聚焦） | ① 用户注册/登录 ② 个人档案 ③ 人脉关系 ④ Feed ⑤ 实时推荐 | 其余功能（招聘、消息）可以在后期补充。 |

**规模换算（帮助画容量图）**  

| 项目 | 计算方式 | 结果 |
|------|----------|------|
| **每日写入** | 30 k QPS × 86 400 s ≈ 2.6 B 次/天 | 主要是动态、连接请求、简历投递 |
| **每日读取** | 150 k QPS × 86 400 s ≈ 13 B 次/天 | Feed、搜索、关系查询 |
| **单用户档案大小** | 10 KB（结构化） | 1.05 亿 × 10 KB ≈ 1 PB（结构化） |
| **日志/行为数据** | 100 GB/天 ≈ 36 TB/年 | 适合写入型分布式文件系统（HDFS、S3） |

> **思考点**：如果不先做这些数字估算，后面会出现“数据库单机撑不住”“缓存命中率太低”等明显的 **容量/性能瓶颈**。

---

## 第二步：高层架构设计

### 2.1 整体分层
```
┌───────────────────────┐
│   前端 (Web / Mobile)  │
└───────▲───────▲───────┘
        │       │
   ┌────▼─────┐ ┌────▼─────┐
   │ API GW   │ │ CDN /   │
   │ (REST+gRPC)│ │ Edge   │
   └────▲─────┘ └────▲─────┘
        │            │
   ┌────▼─────────────────────────────┐
   │   业务微服务层 (User, Graph, Feed,│
   │   Recruit, Recommendation, Auth) │
   └────▲─────────────────────────────┘
        │
   ┌────▼─────┐   ┌───────▼───────┐
   │ Cache    │   │ Message Queue │
   │ (Redis)  │   │ (Kafka)       │
   └────▲─────┘   └───────▲───────┘
        │               │
   ┌────▼─────────────────▼───────┐
   │   数据存储层                 │
   │   ├─关系型 DB (MySQL)       │
   │   ├─图数据库 (Neo4j/Janus) │
   │   ├─搜索引擎 (Elasticsearch)│
   │   ├─对象存储 (S3/HDFS)      │
   │   └─时序/日志 (ClickHouse) │
   └──────────────────────────────┘
```

### 2.2 关键设计原则

| 原则 | 为什么要这么做 | 不这样做会怎样 |
|------|----------------|----------------|
| **职责分离** | 每个微服务只负责单一业务域（用户、关系、Feed 等），便于独立扩容、独立部署 | 代码耦合、改动影响全局，难以水平扩展 |
| **统一网关** | 集中做鉴权、限流、日志、协议转换，前端只需要一个入口 | 每个服务都要重复实现安全、限流，流量冲击全链路 |
| **缓存层** | 读热点（用户档案、Feed）放到 Redis，降低 DB 访问压力 | 高 QPS 时直接压垮底层关系型/图库 |
| **异步化** | 写操作（动态、关系）先写入 Kafka → 后端消费者落库、生成 Feed、更新推荐模型 | 同步写入导致响应时间 >200 ms，且写热点容易出现锁竞争 |
| **冷热分离** | 冷数据（历史档案、日志）放对象存储/列式仓库，热数据（当前 Feed、关系）放高性能 DB | 冷数据直接放在热点 DB 会导致磁盘 IO 爆炸 |
| **容错 & 限流** | 在网关、服务、消息队列层面加熔断、限流、重试，保证单点故障不蔓延 | 某节点宕机会导致全链路阻塞，服务不可用 |

### 2.3 关键技术选型（理由）

| 组件 | 候选技术 | 选型理由 |
|------|----------|----------|
| **API 网关** | Kong / Nginx + Lua / Envoy | 支持高并发、插件化鉴权、限流、灰度发布 |
| **关系型 DB** | MySQL（Percona）+ Galera / Aurora | 事务强一致、成熟的二级索引、读写分离方案成熟 |
| **图数据库** | Neo4j (Enterprise) 或 JanusGraph + Cassandra | **强一致** 的关系查询（两度/三度人脉），支持 **水平分片**（Cassandra） |
| **搜索/索引** | Elasticsearch | 关键词搜索、过滤、排序（职位、用户）性能优异 |
| **缓存** | Redis Cluster | 支持分片、主从复制、持久化，读写 latency < 1 ms |
| **消息队列** | Kafka (3 复制) | 高吞吐、持久化、天然的流式计算入口 |
| **离线/实时计算** | Flink + Spark | Flink 负责实时特征、推荐；Spark 负责离线模型训练 |
| **对象存储** | Amazon S3 / MinIO | 大文件、日志、图片等的冷热存储 |
| **监控** | Prometheus + Grafana + Alertmanager | 指标采集、可视化、自动报警 |
| **日志** | ELK (Elasticsearch + Logstash + Kibana) | 集中化日志，便于排错、审计 |

---

## 第三步：数据库设计

### 3.1 业务模型划分

| 业务子系统 | 主要数据实体 | 访问模式 | 推荐存储 |
|------------|--------------|----------|----------|
| **用户/档案** | User、Profile、Skill、Education | 读：个人主页、搜索<br>写：编辑档案 | MySQL（强一致） + Elasticsearch（全文搜索） |
| **关系网络** | Connection（双向）、ConnectionRequest、Block | 读：二度/三度人脉图<br>写：发送/接受请求、删除 | **图数据库**（Neo4j/JanusGraph） |
| **Feed** | Post、Like、Comment、Share | 读：时间线分页<br>写：发布动态、点赞 | MySQL（写） → Kafka → Flink → Redis（热点 Feed） |
| **招聘** | Job, Application, Company | 读：职位搜索、筛选<br>写：发布职位、投递简历 | MySQL + Elasticsearch |
| **推荐** | UserFeature、ItemFeature、Score | 读：实时推荐结果<br>写：行为日志、模型输出 | ClickHouse（时序）+ Redis（缓存）+ Kafka（日志） |

### 3.2 关系型数据库表结构（示例）

```sql
-- users 表：核心身份信息（强一致）
CREATE TABLE users (
    user_id        BIGINT PRIMARY KEY,
    email          VARCHAR(255) UNIQUE,
    phone          VARCHAR(20)  UNIQUE,
    password_hash  VARBINARY(60),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status         ENUM('ACTIVE','SUSPENDED','DELETED')
) ENGINE=InnoDB;

-- profiles 表：用户公开档案（可分区）
CREATE TABLE profiles (
    user_id        BIGINT PRIMARY KEY,
    full_name      VARCHAR(100),
    headline       VARCHAR(200),
    summary        TEXT,
    location       VARCHAR(100),
    industry       VARCHAR(100),
    visibility     ENUM('PUBLIC','CONNECTIONS','PRIVATE') DEFAULT 'PUBLIC',
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB
PARTITION BY HASH(user_id) PARTITIONS 256;  -- 水平分区，降低单分区热点
```

> **为什么要分区**：单表 100 M+ 行在高并发读写时会出现 **锁竞争**、**磁盘 IO** 爆炸。Hash 分区把数据均匀散到 256 个物理节点，单节点压力降低到 1/256。

### 3.3 图数据库模型

```
Vertex: User (user_id, name, headline)
Edge: CONNECTED (since, status)   -- 双向关系
Edge: REQUESTED (direction, timestamp)   -- 单向请求
Edge: BLOCKED (timestamp)
```

- **双向连接**：在创建连接时，写入 **两条 CONNECTED 边**（A→B, B→A），事务使用 **两阶段提交**（2PC）或 **Neo4j 的 ACID** 保证强一致。  
- **查询二度人脉**：`MATCH (u:User {id:$uid})-[:CONNECTED*2]-(friend) RETURN friend LIMIT 100`，图数据库天然支持 **多跳遍历**，而在 MySQL 中需要递归查询或预计算，代价大。

### 3.4 索引与搜索

| 需求 | 索引/结构 |
|------|-----------|
| 按 `email` / `phone` 登录 | 唯一 B‑Tree 索引（MySQL） |
| 档案搜索（关键词、行业、位置） | Elasticsearch inverted index + 同义词词库 |
| 人脉快速过滤（同公司、同学校） | 图数据库属性索引 + ES 再过滤 |
| Feed 按时间排序 | Redis Sorted Set (score = timestamp) |
| 推荐基于特征向量相似度 | Faiss / HNSW 索引（离线放在向量库） |

---

## 第四步：核心 API 设计

> **原则**：RESTful + gRPC 混合使用。**读请求**（查询）使用 **REST**，**高频内部调用**（如 Feed 生成）使用 **gRPC** 以获得更低的序列化开销。

### 4.1 鉴权与统一返回格式

```json
{
  "code": 0,               // 0=成功, >0=错误码
  "msg": "OK",
  "data": {...},
  "traceId": "xxxx-xxxx-xxxx"
}
```

- 所有 API 必须在 Header 中携带 `Authorization: Bearer <jwt>`，网关负责 JWT 校验并注入 `user_id` 到上下文。

### 4.2 示例 API 列表

| 方法 | 路径 | 功能 | 关键参数 | 返回 |
|------|------|------|----------|------|
| `POST /api/v1/auth/register` | 注册 | email/phone、密码、验证码 | `{email, phone, password, code}` | `user_id` |
| `POST /api/v1/auth/login` | 登录 | 支持密码、OAuth、验证码 | `{type, credential}` | `jwt, refresh_token` |
| `GET /api/v1/users/{uid}` | 查看个人档案 | `uid`（公开/私密校验） | - | `UserProfile` |
| `PUT /api/v1/users/{uid}/profile` | 编辑档案 | `uid` 必须是当前登录用户 | `ProfileBody` | `success` |
| `POST /api/v1/connections/request` | 发送连接请求 | `target_user_id` | - | `request_id` |
| `POST /api/v1/connections/accept` | 接受请求 | `request_id` | - | `connection_id` |
| `GET /api/v1/connections/{uid}?degree=2` | 查询二度人脉 | `uid`、`degree` | - | `UserList` |
| `POST /api/v1/feed` | 发布动态 | `content`, `media_ids` | - | `post_id` |
| `GET /api/v1/feed?uid={uid}&page={n}` | 拉取时间线 | `uid`、`page`、`size` | - | `PostList` |
| `GET /api/v1/recommendations?type=people&uid={uid}&limit=20` | 推荐人脉 | `uid`、`type` | - | `UserList` |
| `GET /api/v1/jobs/search?q=engineer&location=NY` | 搜索职位 | `q`, `location`, `page` | - | `JobList` |

### 4.3 接口幂等性

- **写操作**（POST/PUT）必须 **幂等**。采用 **UUID 事务 ID**（如 `request_id`）在后端做幂等校验，防止网络重试导致重复创建连接或重复发布动态。

### 4.4 错误码约定

| Code | 含义 | 场景 |
|------|------|------|
| 0 | 成功 | - |
| 1001 | 参数错误 | 缺少必填字段 |
| 1002 | 鉴权失败 | JWT 失效 |
| 2001 | 资源不存在 | 查询不到用户 |
| 3001 | 业务冲突 | 已经是好友，不能再次发送请求 |
| 5000 | 系统错误 | DB 超时、服务不可达 |

---

## 第五步：详细组件设计

### 5.1 鉴权 & 登录流程

1. **前端** 收集邮箱/手机号 + 验证码 → 调用 `/auth/register`。  
2. **API GW** 校验请求频率（防刷） → 转发到 **Auth Service**（Go/Java）。  
3. **Auth Service**  
   - 验证码检查（Redis 临时存储）  
   - 密码使用 **bcrypt** + **pepper** 加盐存储  
   - 写入 `users` 表（强一致）  
   - 生成 **JWT**（HS256）和 **Refresh Token**（存于 Redis，TTL 30d）  
4. **登录** 同理，支持 **OAuth**（Google、Microsoft） → 第三方返回 `id_token` → 通过 **OpenID Connect** 验证后创建/查询本地用户。  

> **为什么使用 JWT + Redis Refresh**：JWT 天生 **无状态**，可直接在网关验证，降低 auth 服务的吞吐压力；Refresh Token 存 Redis 可随时失效（注销/密码修改），兼顾安全。

### 5.2 个人档案服务（User Service)

- **读路径**  
  1. API GW → User Service → 先读 **Redis**（Cache），若 miss 再查询 **MySQL** + **Elasticsearch**（组合返回），结果写回 Redis（TTL 5 min）。  
- **写路径**  
  1. 前端 PUT → API GW → User Service → 事务写入 MySQL（主库） → 发送 **Kafka** `profile_updated` 事件 → 消费者更新 **ES 索引** 与 **Redis** 缓存。  

> **强一致需求**：用户编辑档案必须立即在查询时可见（尤其是对自己），所以写入 MySQL 后同步更新缓存，采用 **写后读**（Read‑After‑Write）策略。

### 5.3 关系网络服务（Graph Service）

#### 5.3.1 双向连接的事务实现
- **步骤**  
  1. **发送请求**：`ConnectionRequest` 写入 MySQL（事务表），发送 Kafka `request_sent`。  
  2. **接受请求**：服务读取请求记录 → 开启 **Neo4j** 事务：  
     - `CREATE (a)-[:CONNECTED {since: now()}]->(b);`  
     - `CREATE (b)-[:CONNECTED {since: now()}]->(a);`  
  3. **提交**：若两条 edge 都成功，提交事务；若冲突（已是好友），回滚并返回 **业务冲突**。  

- **冲突防护**：使用 **唯一约束** `UNIQUE (a,b)` 防止并发创建重复 edge。Neo4j 会返回 `ConstraintViolationException`，业务层捕获并返回 3001。

#### 5.3.2 二度/三度人脉查询
- **实现**：  
  - **实时查询**：`MATCH (u:User{id:$uid})-[:CONNECTED*2]-(friend) RETURN friend LIMIT 100`（Neo4j）。  
  - **热点缓存**：对活跃用户的二度人脉做 **定时预计算**（每 5 min）并写入 Redis Set，读取时直接 `SMEMBERS`，降低图库负载。  

#### 5.3.3 分区策略
- **水平分片**：使用 **JanusGraph + Cassandra** 时，以 `user_id` 哈希分布到不同的 Cassandra 节点。Neo4j Enterprise 版也提供 **Causal Clustering**，通过 **sharding key**（用户 ID）将图划分到不同机器，保证跨分片查询仍然可用（内部路由）。

### 5.4 Feed 服务（Feed Service）

#### 5.4.1 写流程（发布动态）
1. 前端 POST `/feed` → API GW → Feed Service → **写入 MySQL `posts` 表**（持久化）并立即 **写入 Kafka `post_created`**。  
2. **Kafka Consumers**（Flink）读取事件，执行两件事：  
   - **Fan‑out**：将该动态的 ID 推送到 **所有粉丝的 Redis Sorted Set**（key:`feed:{fan_id}`，score=timestamp）。  
   - **持久化**：将 `post_id` 与 `user_id` 的映射写入 **Cassandra**（用于离线计算）。  

> **为什么使用 Fan‑out 而不是 Pull**：Pull 模型（每次查询时遍历所有粉丝）在用户粉丝数大（>10k）时会导致 **查询延迟** 超标。Fan‑out 将写放大到 **写时一次**，读取时只做 **分页读取**（O(1)），符合 200 ms 延迟目标。

#### 5.4.2 读流程（拉取 Feed）
1. API GW → Feed Service → 直接查询 **Redis Sorted Set** `feed:{uid}`，使用 `ZREVRANGEBYSCORE` 分页。  
2. 若缓存 miss（新用户或缓存失效），回源到 **MySQL**（查询最近 N 条）并补齐缓存。  

#### 5.4.3 去重 & 排序
- **去重**：因为同一条动态可能因用户多次转发而出现多条记录，Fan‑out 时使用 **Redis ZADD NX**（仅在不存在时加入）。  
- **业务排序**：基本按时间排序；后期可加入 **权重分数**（点赞数、互动度）通过 **Score = timestamp + α·engagement**，在 Fan‑out 时计算。

### 5.5 推荐系统（Recommendation Service）

#### 5.5.1 数据管道
| 步骤 | 技术 | 说明 |
|------|------|------|
| **行为采集** | 前端 SDK → Kafka `user_behavior` | 浏览、点赞、点击、搜索均实时写入 |
| **实时特征计算** | Flink (窗口 5 s) → ClickHouse (实时表) | 统计最近 7 天的活跃度、兴趣向量 |
| **离线特征 & 训练** | Spark + TensorFlow → 模型文件 (Embedding) | 每日离线批处理，生成用户/物品向量 |
| **向量检索** | Faiss / HNSW (部署为服务) | 近似最近邻搜索，返回 Top‑N 候选 |
| **结果缓存** | Redis (TTL 30 min) | API 调用时直接读取，降低 latency |

#### 5.5.2 延迟控制
- **端到端延迟** ≈ 1 s  
  - 采集 → Kafka (≤100 ms)  
  - Flink 实时特征 → ClickHouse (≈200 ms)  
  - 在线召回（向量检索）+ 缓存 (≈300 ms)  
  - 总体 ≤ 1 s，满足“实时推荐”要求。

#### 5.5.3 推荐 API 示例
```http
GET /api/v1/recommendations?type=people&uid=12345&limit=20
```
- **内部流程**：  
  1. 检查 Redis `rec:people:12345`，若命中直接返回。  
  2. 若 miss，调用 **Recommendation Service**（gRPC） → 读取用户特征向量 → 向量检索 → 排序 + 业务规则过滤 → 返回并写入 Redis。  

### 5.6 消息队列与异步任务

| 场景 | 生产者 | 消费者 | 目的 |
|------|--------|--------|------|
| `profile_updated` | User Service | ES Indexer、Search Sync | 保持搜索索引同步 |
| `post_created` | Feed Service | Fan‑out Processor (Flink) | 写入粉丝 Feed |
| `connection_accepted` | Graph Service | Notification Service | 推送系统通知、邮件 |
| `user_behavior` | 前端 SDK | Real‑time Feature (Flink) | 实时推荐特征更新 |
| `job_applied` | Recruit Service | Email Service, CRM | 发送确认邮件、后续跟进 |

- **Kafka 分区**：依据 **业务键**（如 `user_id`）进行 **Key‑based Partitioning**，保证同一用户的所有事件落到同一分区，便于 **顺序消费**（避免乱序导致状态不一致）。

### 5.7 监控、日志、灰度发布

- **指标**（Prometheus）  
  - QPS、Latency（P99、P95）  
  - Cache Hit Ratio、DB Connection Pool 使用率  
  - Kafka Lag、Consumer 消费速率  
- **告警**（Alertmanager）  
  - Latency > 250 ms 持续 2 min → 报警  
  - Cache Miss Ratio > 30% → 检查热点迁移  
- **日志**（ELK）  
  - 结构化 JSON，统一 `traceId` 跨服务追踪  
- **灰度/蓝绿**  
  - 使用 **Canary Deployment**（K8s）+ **Istio** 路由，先让 5% 流量走新版本，观察指标后逐步放大。

---

## 第六步：扩展性与高可用设计

### 6.1 横向扩容

| 组件 | 扩容方式 | 关键指标 |
|------|----------|----------|
| **API Gateway** | 增加实例 + L4 LB (Consul/Envoy) | QPS ≤ 200k / 实例 |
| **Auth Service** | Stateless，水平扩容 | JWT 验签 CPU |
| **User Service** | 多副本 + 读写分离（Master/Slave） | MySQL 主库写入，Slave 供查询 |
| **Graph Service** | **Causal Cluster** (Neo4j) 或 JanusGraph + Cassandra | 每个分片 10k QPS |
| **Feed Service** | Redis Cluster + Sharding | 每个 shard 100k QPS |
| **Recommendation Service** | 多实例 + 负载均衡（gRPC） | 向量检索每秒 10k 次 |
| **Kafka** | 增加 Broker + Partition | 每个 Topic 10k TPS |

### 6.2 高可用（HA）设计要点

1. **无单点**  
   - 每层都有 **至少 3 台** 实例（Gateway、DB Master、Cache Master）  
   - 使用 **负载均衡 + 健康检查** 自动剔除故障节点  

2. **数据复制**  
   - **MySQL**：主-从双活（GTID），自动故障转移（MHA）  
   - **Redis**：主从复制 + Sentinel 自动故障切换  
   - **Kafka**：副本数 3，ISR（In‑Sync Replicas）保证写入成功后才 ack  

3. **容灾**  
   - **跨可用区**（AZ）部署：同一业务的副本分布在不同 AZ，单 AZ 故障不影响整体可用性。  
   - **灾备中心**：每日快照（MySQL、Cassandra）同步到另一地区，必要时切换 DNS。  

4. **限流 & 熔断**  
   - **网关** 对每个 IP、每个用户 ID 设置 QPS 上限（如 1000 QPS）  
   - **服务内部** 使用 **Hystrix/Resilience4j** 实现 **熔断**，防止下游故障向上蔓延。  

5. **数据恢复**  
   - **MySQL Binlog** + **Kafka Connect** 将变更同步到 **ClickHouse** 作审计。  
   - **Redis AOF** + **RDB** 双模式备份，定时复制到对象存储。  

### 6.3 性能调优技巧

| 场景 | 调优点 | 参考指标 |
|------|--------|----------|
| **热点用户 Feed** | 对热点用户使用 **专用缓存**（热点预热） | 缓存命中率 > 90% |
| **关系查询** | 对 **常用二度/三度** 关系做 **物化视图**（每日批处理）并放入 Redis | 查询 latency < 30 ms |
| **写放大** | 批量 **Kafka Producer**（batch.size=64KB）降低网络开销 | 每秒网络请求数下降 30% |
| **搜索** | ES 分片数 = 3 × 机器数，开启 **doc_values**、**keyword** 字段 | QPS 20k，查询 latency < 100 ms |
| **推荐** | 使用 **GPU 加速** 向量检索（Faiss GPU） | 每秒检索 100k 向量 |

---

## 第七步：常见面试追问与回答

### Q1️⃣ “如果把用户的关系图存储在关系型数据库和图数据库之间，你会如何选型？如何实现水平分区以支撑 300 M+ 用户？”

**回答要点**  
1. **业务需求**：人脉查询需要 **多跳遍历**（二度、三度），关系型 DB（MySQL）只能靠 **递归 CTE** 或 **预计算表**，在 300 M+ 用户、每秒上万查询的情况下 **性能极差**。  
2. **图数据库优势**：天然的 **节点/边** 结构、**指数级遍历**、**灵活的属性查询**，能够在 **毫秒级** 完成二度人脉查询。  
3. **选型**  
   - **Neo4j Enterprise**：提供 **ACID 事务**、**Causal Clustering**（读写分离），适合强一致的“双向连接”。  
   - **JanusGraph + Cassandra**：如果业务对 **水平扩展** 要求更高（>10 B 边），可以使用 JanusGraph 结合分布式后端（Cassandra/HBase）实现 **无限水平扩展**。  
4. **水平分区（Sharding）**  
   - **哈希分区**：以 `user_id % N` 将用户划分到不同图库实例。Neo4j Causal Cluster 会自动路由；JanusGraph 通过 **PartitionKey**（user_id）把顶点和它的出边存放同一分区，保证本地遍历不跨网络。  
   - **跨分区查询**：Neo4j 支持 **跨分片路由**，JanusGraph 则在查询时自动并行访问多个分区，返回合并结果。  
5. **数据迁移**：采用 **双写**（MySQL + Graph DB）+ **后台迁移脚本**，逐步切换查询层，避免一次性迁移导致服务不可用。  

### Q2️⃣ “在大量用户同时发送连接请求的场景下，如何保证‘双向连接’的一致性并避免脏读？”

**回答要点**  
1. **业务规则**：连接请求必须是 **单向**（A→B），接受后变为 **双向**（A↔B）。  
2. **事务模型**  
   - 使用 **Neo4j**（或 JanusGraph）提供的 **ACID** 事务：在同一个事务里 **创建两条 CONNECTED 边**，并对 **唯一约束** (`UNIQUE (a,b)`) 进行检查。  
   - 若采用 **关系型 DB**（MySQL）存储连接表：使用 **两阶段提交（2PC）** 或 **分布式事务管理器（如 Seata）**，保证两条记录（A→B、B→A）要么全部成功，要么全部回滚。  
3. **幂等/防重复**  
   - 在 `connection_requests` 表加入 **唯一键** (`requester_id, target_id`) 防止重复请求。  
   - 接受请求时先检查 `connection` 表是否已存在对应记录，若存在直接返回成功，避免因并发导致 **重复边**。  
4. **避免脏读**  
   - 对外提供 **读取接口** 时，使用 **Read‑Committed** 或 **Repeatable‑Read** 隔离级别，确保读取到的连接状态是已提交的。  
   - 读取热点（如 “是否已经是好友”）使用 **Redis Cache**，但在写成功后立即 **刷新缓存**（Cache‑Aside），并在缓存失效期间使用 **锁（RedLock）** 防止读取到旧状态。  

### Q3️⃣ “请描述从用户行为日志到推荐结果展示的完整流水线，包括数据采集、特征工程、模型推理、结果缓存的技术选型和延迟控制。”

**回答要点**（结构化叙述）  
1. **数据采集**  
   - 前端 SDK（JS、移动）实时发送用户行为（点击、浏览、点赞）到 **Kafka topic `user_behavior`**。  
   - 使用 **Kafka Producer** 的 **batch.size=64KB、linger.ms=20**，兼顾网络吞吐与实时性。  

2. **实时特征计算**  
   - **Flink** 从 `user_behavior` 按 **用户 ID** 分组，使用 **滚动窗口 5 s** 计算最近 7 天的活跃度、兴趣标签计数。  
   - 计算结果写入 **ClickHouse** 实时表 `user_features_rt`（列式存储，支持快速点查）。  

3. **离线特征 & 模型训练**  
   - 每日一次 **Spark** 作业读取 **ClickHouse**、**MySQL**、**Graph DB** 的全量特征，生成 **用户/岗位向量**（DeepWalk、GraphSAGE）。  
   - 训练完的模型保存到 **HDFS**，并部署 **Faiss** 向量检索服务（GPU 加速）。  

4. **在线召回（模型推理）**  
   - 当前端请求推荐时，**Recommendation Service** 读取 **Redis** 中的用户最新特征向量（由 Flink 写入）。  
   - 调用 **Faiss RPC** 进行 **ANN** 检索，返回 Top‑N 候选 ID。  
   - 再通过 **业务规则过滤**（如 已是好友、黑名单），并结合 **实时交互分数**（点赞、评论）做二次排序。  

5. **结果缓存**  
   - 最终候选列表写入 **Redis**（key: `rec:people:{uid}`）TTL 30 min。  
   - 若用户在 TTL 内再次请求，直接返回缓存，降低模型调用次数。  

6. **延迟控制**  
   - **端到端** ≤ 1 s：  
     - Kafka → Flink ≤ 100 ms  
     - ClickHouse 读取 ≤ 50 ms  
     - Faiss 检索（GPU） ≤ 150 ms  
     - 业务过滤 & 排序 ≤ 100 ms  
   - 通过 **监控**（Prometheus `recommendation_latency_seconds`）设置 **SLA 警戒线**（0.8 s），超时则直接返回 **缓存结果**或 **热点推荐**（基于热门岗位）。  

### Q4️⃣ “如果流量突发到 2 倍，系统怎么自适应扩容？”

**要点**  
- **自动伸缩**（K8s HPA）监控 **CPU/Memory**、**QPS**、**Kafka Lag**，自动 **水平扩容**微服务实例。  
- **Redis Cluster** 使用 **Redis‑Cluster‑Manager** 动态 **resharding**，在节点加入后自动迁移槽位。  
- **Kafka** 通过 **分区数** 预留足够（如 300 分区），在负载提升时 **增加 Broker**，并使用 **ReassignPartitions** 工具重新均衡。  
- **前端** 使用 **CDN** 缓存静态资源，减轻网关压力。  
- **熔断/降级**：在突发期间对非核心业务（如 推荐）开启 **Cache‑Only** 模式，降低后端计算压力。  

---

## 心得与反思

### 1. 本题最难的 1–2 个设计决策及思考过程
| 决策 | 难点 | 思考路径 |
|------|------|----------|
| **关系网络的存储选型** | 人脉查询需要多跳遍历，且用户规模 300 M+，单机关系型 DB 无法满足延迟要求。 | - 先列出查询场景（二度、三度、人脉推荐）<br>- 评估 MySQL、PostgreSQL 的递归 CTE 性能 → 发现 O(N²) 难以扩展。<br>- 对比图数据库的遍历复杂度 O(k)（k 为跳数）以及天然的边属性支持。<br>- 再考虑强一致需求 → 选 Neo4j（支持 ACID）或 JanusGraph+Cassandra（更好水平扩展）。 |
| **写放大 vs 读取延迟的权衡（Feed Fan‑out）** | 动态发布后需要推送给数万甚至数十万粉丝，若采用 Pull 模式会导致查询延迟爆炸。 | - 计算写入放大系数：用户平均粉丝数 ~ 500，写 1 条动态 → 500 条写入 Redis。<br>- 评估 Redis 写吞吐（可达 100k QPS/节点），确定可以接受放大。<br>- 设计异步 Fan‑out（Kafka+Flink）解耦写入与推送，确保发布接口 < 200 ms。 |

### 2. 新手最容易犯的错误（至少 2 条）
| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把所有业务都塞进单体服务或单库** | 随着用户增长，单点故障、性能瓶颈、难以水平扩展。 | 按业务域拆分微服务，使用 **读写分离、分库分表**，关键业务（关系、Feed）单独使用专门存储。 |
| **只考虑强一致而忽视业务的最终一致需求** | 对 Feed、推荐使用强事务会导致大量锁竞争、延迟 > 200 ms。 | 区分 **强一致**（关系、投递）和 **最终一致**（Feed、推荐），采用异步消息、缓存、幂等写来降低耦合。 |

### 3. 学习建议和可延伸的方向
1. **系统设计基础**：熟练掌握 **CAP 定理、ACID vs BASE、分布式事务**，这些概念是解释选型的根基。  
2. **深入一两个关键技术**：  
   - **图数据库**：阅读 Neo4j 官方文档、实践 Cypher 查询，了解 Causal Clustering。  
   - **实时流处理**：学习 Flink 的窗口、状态后端、Exactly‑Once 语义。  
3. **实战练习**：在本地搭建 **Docker‑Compose** 版的微服务（Spring Boot + MySQL + Redis + Kafka），模拟用户注册、发动态、查询人脉，观察瓶颈。  
4. **关注监控与容量规划**：系统设计面试常问 “如果流量翻倍怎么办”，准备 **指标树**（QPS、Latency、Cache Hit Ratio）以及 **自动伸缩** 方案。  
5. **阅读优秀案例**：LinkedIn、Facebook、Twitter 的公开架构文章（如 “LinkedIn’s Real‑Time Recommendations”），对比自己的设计与业界实践。  

---

> **结语**  
系统设计并不是一次性写出完美图，而是 **思考业务、拆解功能、权衡取舍、用合适的技术实现** 的过程。掌握了需求分析、容量估算、分层架构、存储选型、容错设计这些“核心能力”，在面试中即使遇到全新业务也能快速搭建出合理的方案。祝你面试顺利，设计出自己的“LinkedIn”！ 🚀
