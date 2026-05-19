# 第 7 天：设计 Snapchat

> 生成日期：2026-05-19

---

# 系统设计面试题 – Snapchat（即时多媒体社交平台）

## 1. 题目背景
Snapchat 是一款以“阅后即焚”为核心的移动社交应用，用户可以发送图片、视频（Snap）以及文字聊天，对方在观看后内容会自动删除。它强调实时、短暂、私密的多媒体交互体验。

## 2. 面试场景设定
> **面试官**：  
> “我们现在来讨论如何设计一个类似 Snapchat 的即时多媒体社交系统。请你从高层次出发，阐述系统的整体架构，并重点说明如何支撑海量用户的 Snap 发送/接收、阅后即焚以及高可用的聊天功能。可以先从需求入手，然后逐步展开设计细节。”

## 3. 功能性需求
| 编号 | 功能描述 |
|------|----------|
| 1 | **发送 Snap**：用户可以拍摄照片或 1–10 秒短视频，添加文字、滤镜、贴纸后发送给单个或多个好友。 |
| 2 | **阅后即焚**：接收方打开 Snap 后，计时结束后自动删除，且在发送方、接收方、服务器端均不再保留该内容。 |
| 3 | **即时聊天（Chat）**：支持文字、表情、语音消息的实时双向会话，消息需保证顺序并在对方离线时持久化。 |
| 4 | **Stories（瞬时故事）**：用户可以将 Snap 保存至 24 小时可见的个人 Stories，供所有好友浏览。 |
| 5 | **好友关系管理**：添加/删除好友、分组、隐私设置（如阻止、仅限好友可看）。 |
| 6 | **内容发现（Discover）**：展示品牌、媒体合作伙伴的短视频流（本题可视为只读的 CDN 分发）。 |

## 4. 非功能性需求（带估算）

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **日活跃用户（DAU）** | 150 Million | 参考公开数据，假设在高峰期全球活跃用户量。 |
| **峰值 QPS（Snap 发送）** | 120 K QPS | 计算方式：150M DAU × 0.2 Snap/用户/天 ÷ 86400 s ≈ 35 K，考虑促销活动等峰值约 3 倍。 |
| **聊天消息 QPS** | 250 K QPS | 每位活跃用户平均 1.5 条聊天消息/天。 |
| **端到端平均延迟** | ≤ 200 ms（发送 → 接收） | 对即时聊天和 Snap 观看体验要求。 |
| **可用性** | 99.9%（每月累计停机 ≤ 43 分钟） | 必须保证核心发送/接收功能高可用。 |
| **存储容量** | 约 250 PB（原始 Snap + 备份 + Stories） | 估算：150M DAU × 0.2 Snap/用户/天 × 5 MB/Snap × 30 天保留 + 备份系数 2×。 |
| **数据一致性** | 最终一致性（聊天消息使用强一致性，Snap 使用弱一致性） | 平衡性能与用户体验。 |

> **注**：以上数值为面试估算，实际实现可根据业务细化。

## 5. 系统边界
**本题需要实现的范围**  
- Snap 的上传、加密、临时存储、阅后即焚删除流程。  
- 实时聊天的消息路由、顺序保证、离线存储。  
- 用户身份认证、好友关系管理（基本 CRUD）。  
- Stories 的写入、24 小时自动过期。  
- 基础监控、限流、容错（如重试、降级）。  

**本题不考虑的功能**  
- AR 滤镜、地理位置标签的实时渲染（视为客户端实现）。  
- 广告投放系统、商业合作伙伴的内容审核流程。  
- 推送通知的细粒度实现（仅要求提供接口）。  
- 跨平台（iOS/Android/Web）具体 UI 细节。  
- 法律合规（GDPR、未成年保护）只在高层讨论，不要求实现细节。

## 6. 提示与追问
1. **数据持久化与删除策略**  
   - “Snap 在用户观看后需要立即从所有节点删除，你会如何设计多副本存储的安全擦除流程？”  

2. **高并发消息分发**  
   - “在峰值 120 K QPS 的 Snap 发送场景下，如何保证消息的低延迟送达并避免热点单点？”  

3. **可用性与容错**  
   - “如果某个存储区域（Region）出现网络分区，系统应如何保证‘阅后即焚’的强一致性以及聊天消息的可达性？”  

---  
**请在面试中围绕以上需求展开系统设计，包括但不限于：**  
- 整体架构图（前端、API 网关、业务服务、存储、缓存、CDN、消息队列等）  
- 关键数据模型与分区策略  
- 读写路径、缓存层次、异步处理  
- 可靠性设计（冗余、故障转移、监控）  
- 成本与扩展性权衡  

祝你面试顺利！

---

# 题解

# 系统设计面试题 – Snapchat（即时多媒体社交平台）完整解答

> **本文面向“零经验”后端新人**，从 **最小可用系统**（MVP）一步步搭建到 **高可用、可扩展的大型分布式系统**。每一步都会解释 **为什么** 这样做、**不这么做** 会出现什么问题。请跟随章节顺序阅读，做好笔记，面试时可以直接复盘。

---

## ## 解题思路总览  

1. **先把需求拆解**：把功能性需求、非功能性需求、系统边界全部列清楚，明确哪些是必须实现，哪些可以先不管。  
2. **估算规模**：根据 DAU、QPS、存储量做出粗略的容量预估，帮助后面选技术栈和分区策略。  
3. **从最小可用系统（MVP）出发**：只保留最核心的几块（用户、Snap 上传/下载、聊天、简单存储），用单体或少量服务快速实现业务。  
4. **逐层演进**：在 MVP 基础上，**水平拆分**、**加入缓存/消息队列**、**多活部署**、**跨地域容灾**，一步步满足 99.9% 可用、200 ms 延迟等 NFR。  
5. **每个关键点都要回答 “为什么要这样做？”**，并给出 **不这样做的后果**（单点、数据不一致、容量爆炸等）。  

下面按照 **七个章节** 逐一展开。  

---  

## ## 第一步：理解需求与规模估算  

### 1. 功能性需求梳理（核心 vs 可选）

| 编号 | 功能 | 是否 MVP 必要 | 备注 |
|------|------|--------------|------|
| 1 | 发送 Snap（图片/短视频） | ✅ 必须 | 需要上传、加密、临时存储、分发 |
| 2 | 阅后即焚 | ✅ 必须 | 关键竞争差异点 |
| 3 | 实时聊天 | ✅ 必须 | 文字、表情、语音 |
| 4 | Stories（24h 可见） | ✅ 必须 | 与 Snap 类似的存储/过期机制 |
| 5 | 好友关系管理 | ✅ 必须 | 基础 CRUD、分组、阻止 |
| 6 | 内容发现（Discover） | ❌ 可选 | 只读 CDN，后期可加 |

> **MVP**：实现 1~5，6 交给 CDN 直接提供即可。

### 2. 非功能性需求（NFR）解读  

| 指标 | 目标 | 为何重要 |
|------|------|----------|
| DAU 150M | 业务规模基准 | 决定整体容量、并发 |
| Snap 发送峰值 120 K QPS | 高并发写入 | 必须支撑上传、分发、删除 |
| 聊天消息 QPS 250 K | 实时双向流 | 需要低延迟、顺序保证 |
| 延迟 ≤ 200 ms | 用户体验 | 超过 300 ms 体验明显下降 |
| 可用性 99.9% | 商业 SLA | 每月停机 ≤ 43 min |
| 存储 250 PB | 大数据量 | 需要分层存储、冷热分离 |
| 数据一致性 | Snap 弱一致，聊天强一致 | 权衡性能与业务需求 |

### 3. 粗略容量估算（便于后续选型）

| 项目 | 计算方式 | 结果 |
|------|----------|------|
| **每日 Snap 上传** | 150M × 0.2 Snap/用户 ≈ 30M Snap | 30 M |
| **单 Snap 大小** | 假设 5 MB（图片+视频平均） | 5 MB |
| **每日存储需求** | 30M × 5 MB ≈ 150 TB | 150 TB |
| **30 天保留（包括 Stories）** | 150 TB × 30 ≈ 4.5 PB | 4.5 PB |
| **备份 ×2** | 4.5 PB × 2 = 9 PB | 9 PB |
| **加上索引、日志等 10%** | ≈ 10 PB | **≈ 10 PB**（实际估算 250 PB 为安全上限） |

> **注意**：实际业务会有高峰、热点用户、地区差异，这里只做“上限估算”，后续会通过分区、冷热分层进一步压缩成本。

---

## ## 第二步：高层架构设计  

### 1. 从 MVP 到完整系统的层次划分  

```
+-------------------+      +-------------------+      +-------------------+
|   Mobile/Web App | ---> |   API Gateway /   | ---> |   Front‑End      |
|   (iOS, Android) |      |   Edge Layer      |      |   Load Balancer  |
+-------------------+      +-------------------+      +-------------------+
                                 |   |
                                 |   | (REST/GRPC + Auth Token)
                                 v   v
          +----------------------+--------------------------+
          |   微服务层 (User, Snap, Chat, Story, Friend)   |
          +----------------------+--------------------------+
               |          |          |          |
               |          |          |          |
   +-----------+---+  +---+----------+---+  +---+----------+
   |  Snap Service  |  |  Chat Service   |  |  Friend Service |
   +-----------+---+  +-----------+-----+  +-----------+----+
               |                |                |
        +------v------+   +-----v------+   +-----v------+
        | Object Store|   | Message   |   | Relational |
        | (S3/OSS)    |   | Queue (Kafka) | | DB (Postgres)|
        +-------------+   +------------+   +--------------+
               |                |                |
        +------v------+   +-----v------+   +-----v------+
        | CDN (Cache) |   | Cache (Redis) | | Cache (Redis)|
        +-------------+   +--------------+ +--------------+
```

#### 关键层次说明  

| 层级 | 作用 | 关键技术（示例） | 为什么要这样做 |
|------|------|-----------------|----------------|
| **客户端** | 拍摄、编辑、加密、上传、拉取、渲染 | iOS/Android SDK | 业务入口，负责本地加密（端到端） |
| **API Gateway / Edge** | 统一入口、TLS 终止、限流、鉴权、路由 | Kong / Amazon API GW / Envoy | 防止直接暴露内部服务，统一治理 |
| **微服务层** | 按业务拆分（User、Snap、Chat、Story、Friend） | Spring Boot / Go / Rust + Docker | 业务解耦、独立扩展、团队协作 |
| **Snap Service + Object Store** | 大文件上传、加密、临时存储、CDN 分发、删除 | S3/OSS + 分块上传 + 生命周期规则 | 对象存储天然支持大文件、分区、弹性伸缩 |
| **Chat Service + Message Queue** | 实时双向消息、顺序、离线存储 | Kafka / Pulsar + WebSocket / gRPC | Kafka 提供持久化、分区、顺序；WebSocket 实时 |
| **Friend Service + Relational DB** | 关系型查询、事务、唯一约束 | PostgreSQL / MySQL（主从） | 好友关系需要强一致性、复杂查询 |
| **缓存层** | 读热点、热点 Snap URL、聊天会话状态 | Redis (Cluster) | 减少 DB/OSS 访问，降低延迟 |
| **CDN** | 静态内容（Snap、Stories）全球加速 | CloudFront / Akamai | 让用户在 200 ms 以内拿到媒体文件 |
| **监控/日志/追踪** | 可观测性 | Prometheus + Grafana + ELK + Jaeger | 及时发现故障、定位瓶颈 |

### 2. MVP 版最简化部署图  

- **单体服务**（User+Snap+Chat+Friend）跑在一台 8C/32G 机器上  
- **对象存储**：本地 MinIO（兼容 S3）  
- **消息队列**：单节点 Kafka  
- **数据库**：单实例 PostgreSQL  
- **缓存**：单实例 Redis  

> **目的**：让面试官看到你先能实现业务，随后再说如何拆分、扩容。  

### 3. 关键设计点概览（后面章节会细化）

1. **Snap 上传采用分块上传 + 客户端加密** → 防止中间节点泄露。  
2. **阅后即焚的“多副本安全擦除”**：使用 **对象锁定 + 生命周期 + 幂等删除 API**，结合 **后台 GC**。  
3. **聊天顺序**：使用 **Kafka Partition = (conversation_id % N)**，保证同一会话所有消息落在同一分区。  
4. **Stories 24h 自动过期**：对象存储生命周期规则 + DB TTL。  
5. **限流 & 防刷**：在 API Gateway 通过 **IP+UserID 令牌桶** 限制每秒发送 Snap 上限。  
6. **故障转移**：每个微服务部署在 **3 台不同可用区**，使用 **服务注册/发现（Consul/Eureka）** + **负载均衡**。  

---  

## ## 第三步：数据库设计  

### 1. 选型原则  

| 数据 | 访问模式 | 选型 | 说明 |
|------|----------|------|------|
| **用户、好友、会话元数据** | 事务、强一致、复杂查询 | **关系型 DB**（PostgreSQL） | 支持唯一约束、JOIN、事务 |
| **Snap 元数据（ID、URL、TTL、加密信息）** | 按 Snap ID 快速查询、批量扫描 | **NoSQL KV**（Cassandra / DynamoDB） | 高写入吞吐、水平扩展、TTL 原生 |
| **聊天消息** | 顺序读取、持久化、分区 | **分布式日志**（Kafka） + **Cache**（Redis） | Kafka 本身是持久化日志，顺序保证 |
| **媒体文件** | 大对象、流式下载、CDN 分发 | **对象存储**（S3/OSS） | 自动弹性、分区、生命周期 |
| **监控/日志** | 写多读少 | **时序库**（Prometheus） + **ELK** | 业务外部关注点 |

> **注意**：本章节只列出“核心”表/集合，实际系统会有更多辅助表（如安全审计、设备信息等），这里不展开。

### 2. 关键数据模型（示例）  

#### 2.1 Users（关系型）  

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | BIGINT PK | 全局唯一，自增或 Snowflake |
| `username` | VARCHAR(32) UNIQUE | 登录名 |
| `email` | VARCHAR(64) UNIQUE | 可选 |
| `password_hash` | VARCHAR(255) | BCrypt |
| `created_at` | TIMESTAMP | 注册时间 |
| `status` | ENUM(active, disabled, banned) | 账户状态 |
| `profile_pic_url` | VARCHAR(256) | CDN URL（可选） |

#### 2.2 Friends（关系型）  

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | BIGINT PK, FK → Users | 发起方 |
| `friend_id` | BIGINT PK, FK → Users | 被加方 |
| `group_name` | VARCHAR(32) | 分组，可空 |
| `created_at` | TIMESTAMP | 加为好友时间 |
| `blocked` | BOOLEAN | 是否屏蔽 |

> **联合主键** `(user_id, friend_id)` 防止重复。

#### 2.3 SnapMeta（NoSQL KV）  

| 主键 | `snap_id`（UUID） |
|------|-------------------|
| `owner_id` | BIGINT |
| `type` | ENUM(photo, video) |
| `size_bytes` | INT |
| `encrypted_key` | VARBINARY(256) （对称密钥经用户公钥加密） |
| `media_url` | VARCHAR(512) （对象存储 URL） |
| `ttl_seconds` | INT （阅后即焚倒计时） |
| `expires_at` | TIMESTAMP （首次观看后计算） |
| `status` | ENUM(pending, delivered, viewed, deleted) |
| `created_at` | TIMESTAMP |
| `recipients` | LIST<BIGINT> （接收方 ID） |
| `viewed_by` | MAP<BIGINT, TIMESTAMP> （已读时间） |

> **TTL**：使用 **Cassandra TTL** 或 **DynamoDB TTL** 自动过期，配合后台 GC 确保彻底删除。

#### 2.4 ChatMessage（Kafka + Redis）  

- **Kafka 消息结构**（Avro/Protobuf）  

```proto
message ChatMessage {
  string conversation_id = 1;   // 由双方 user_id hash 得到
  int64   sender_id      = 2;
  int64   receiver_id    = 3;
  int64   msg_id         = 4;   // Snowflake
  bytes   payload        = 5;   // 文本、表情、语音（已加密）
  int64   timestamp      = 6;
  enum    type           = 7;   // TEXT, EMOJI, VOICE
}
```

- **Redis 缓存**（Hash）  

Key: `chat:conv:{conversation_id}` → Hash  
Field: `msg:{msg_id}` → JSON（最近 100 条）  

> **作用**：离线用户登录时快速拉取未读消息，减少 Kafka 拉取次数。

#### 2.5 StoryMeta（NoSQL KV）  

| 主键 | `story_id`（UUID） |
|------|-------------------|
| `owner_id` | BIGINT |
| `media_url` | VARCHAR(512) |
| `created_at` | TIMESTAMP |
| `expires_at` | TIMESTAMP （创建后 24h） |
| `viewed_by` | SET<BIGINT> （可选统计） |
| `status` | ENUM(active, expired) |

> 通过 **对象存储生命周期** 在 24h 后自动删除文件，DB 中的 `expires_at` 通过 **后台清理任务** 标记为 `expired`。

### 3. 分区 / 分片策略  

| 数据 | 分区键 | 分区方式 | 目的 |
|------|--------|----------|------|
| Users / Friends | `user_id` | **Hash 分片**（PostgreSQL 分区表或 Sharding） | 均匀分布写入，避免热点用户导致单库瓶颈 |
| SnapMeta | `owner_id` | **Hash 分片**（Cassandra Partition Key） | 同一用户的 Snap 集中在同一节点，便于 TTL GC |
| StoryMeta | `owner_id` | **Hash 分片** | 同上 |
| Kafka Chat | `conversation_id % N` | **固定分区** | 同一会话顺序保证 |
| Redis 缓存 | `conversation_id` | **一致性哈希** | 避免热点节点，支持水平扩容 |

> **不做分区** 的后果：单库写入会随 DAU 成线性增长，极易在高峰期出现 **CPU/IO 瓶颈**，导致 **写超时、服务不可用**。

---  

## ## 第四步：核心 API 设计  

> 这里使用 **REST + JSON** 作为外部 API，内部服务间采用 **gRPC**（高效二进制）或 **Kafka**（异步）。所有请求均通过 **API Gateway**，携带 **JWT**（或 OAuth2）做鉴权。

### 1. 鉴权与安全  

| 步骤 | 描述 |
|------|------|
| **登录** | `POST /auth/login` → 返回 **JWT**（短期）+ **Refresh Token**（长期） |
| **签名** | 每个请求在 Header 中加入 `Authorization: Bearer <jwt>` |
| **TLS** | 全链路 HTTPS，防止中间人窃取 Snap 加密密钥 |
| **端到端加密** | 客户端使用 **对称加密（AES‑GCM）** 加密媒体内容，密钥使用接收方的 **公钥** 加密后随元数据一起发送。服务器只保存加密后的二进制，无法解密。 |

### 2. Snap 相关 API  

| 方法 | 路径 | 说明 | 关键参数 | 返回 |
|------|------|------|----------|------|
| `POST /snap/upload/init` | 初始化上传，返回 **UploadId**、**分块上传 URL**（S3 Pre‑Signed） | 客户端先获取上传凭证 | `owner_id`, `recipients[]`, `ttl_seconds`, `media_type` | `{upload_id, part_urls[]}` |
| `PUT /snap/upload/complete` | 完成分块上传，返回 **snap_id** | `upload_id`, `encrypted_key`（对称密钥经接收方公钥加密） | `{snap_id}` |
| `GET /snap/{snap_id}` | 拉取 Snap（返回 **预签名 URL**） | `snap_id`, `viewer_id`（鉴权） | 302 重定向到 CDN URL（有效期短） |
| `POST /snap/{snap_id}/viewed` | 客户端告知已观看，服务器记录 **viewed_at** 并触发 **计时删除** | `snap_id`, `viewer_id` | `{status: "viewed"}` |
| `DELETE /snap/{snap_id}` | 手动撤回（发送方在未被观看前） | `snap_id`, `owner_id` | `{status: "deleted"}` |

#### 关键实现细节  

- **分块上传**：利用 S3 的 **Multipart Upload**，客户端直接把数据写入对象存储，后端仅保存 **元数据**（`snap_id`, `media_url`），避免大文件经过业务服务器成为瓶颈。  
- **阅后即焚计时**：`viewed_at` + `ttl_seconds` → 计算 `expires_at`。后台 **GC Worker** 每分钟扫描 `expires_at <= now` 的记录，调用 **DeleteObject** 并更新 DB 状态。  
- **安全擦除**：对象存储 **Versioning + Delete Marker** + **Lifecycle**，确保删除后 **不可恢复**（覆盖或加密擦除）。  

### 3. Chat 相关 API  

| 方法 | 路径 | 说明 | 参数 | 返回 |
|------|------|------|------|------|
| `POST /chat/message` | 发送单条消息 | 通过 **WebSocket**/gRPC 直接推送，若离线则写入 Kafka | `{conversation_id, sender_id, receiver_id, payload, type}` | `{msg_id, status:"sent"}` |
| `GET /chat/history` | 拉取历史消息（分页） | 从 **Kafka**（offset）或 **Redis** 缓存读取 | `conversation_id, limit, before_msg_id` | `messages[]` |
| `GET /chat/unread` | 获取未读计数 | 从 Redis 中的 **ZSET**（score=timestamp） | `user_id` | `{conversation_id: count}` |
| `POST /chat/typing` | 输入状态（可选） | 通过 **WebSocket** 推送 | `{conversation_id, user_id, is_typing}` | - |

#### 实现要点  

- **顺序保证**：Kafka **分区** = `hash(conversation_id) % N`，同一会话所有消息在同一分区，天然 FIFO。  
- **离线存储**：消费端（Chat Service）在写入 Kafka 后立即写入 **Redis**（最近 100 条）和 **MySQL**（长期归档）。离线用户登录时，读取 Redis + MySQL 合并返回。  
- **幂等**：`msg_id` 使用 **Snowflake** 全局唯一 ID，服务端对重复 `msg_id` 幂等处理，防止网络重试导致重复展示。  

### 4. 好友 & Story API（简要）  

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST /friend/add` | 添加好友 |
| `DELETE /friend/{friend_id}` | 删除/阻止 |
| `GET /friend/list` | 列表（分页） |
| `POST /story/upload` | 类似 Snap 上传，但 `ttl = 24h` |
| `GET /story/{owner_id}` | 拉取某用户的 Stories（返回 CDN URL 列表） |
| `GET /story/feed` | 拉取好友的 Stories（分页） |

> **Stories** 与 Snap 的主要区别在于 **TTL 固定 24h**，可以直接使用对象存储的 **Lifecycle Policy**（24h 后自动删除），无需额外后台计时器。  

---  

## ## 第五步：详细组件设计  

下面分别对 **Snap Service**、**Chat Service**、**Friend Service**、**存储层**、**监控/容错** 进行深入拆解。

### 1. Snap Service  

#### 1.1 主要职责  

- 接收 **上传初始化** 请求，生成 **UploadId** 与 **预签名 URL**（S3）  
- 记录 **Snap 元数据**（owner、recipients、ttl、加密信息）  
- 处理 **观看通知**，启动 **计时删除**  
- 提供 **Snap 拉取**（签名 URL）  
- 实现 **安全删除**（阅后即焚 & 手动撤回）  

#### 1.2 关键模块  

| 模块 | 功能 | 关键技术/实现 |
|------|------|----------------|
| **Auth Middleware** | JWT 校验、UserId 注入 | Go‑Echo 中间件 |
| **Upload Manager** | 调用对象存储 SDK 生成 **multipart upload**、保存 `upload_id` | S3 SDK `CreateMultipartUpload` |
| **Metadata Store** | 写入/查询 SnapMeta（NoSQL） | Cassandra DAO |
| **Encryption Service** | 生成随机 AES‑GCM 密钥、使用接收方公钥 RSA‑OAEP 加密 | libsodium / BouncyCastle |
| **View Tracker** | 接收 `POST /snap/{id}/viewed`，记录 `viewed_at` | Cassandra Update + Redis 缓存 |
| **Expiry Worker** | 定时扫描 `expires_at`，调用 **DeleteObject**，标记 DB 为 `deleted` | 每分钟一次，使用 **distributed lock**（Zookeeper/Redis RedLock） |
| **Deletion API** | 手动撤回（未观看前） | 同上，立即触发删除流程 |

#### 1.3 流程图（文字版）  

```
Client -> API GW -> Snap Service (init) -> S3 (CreateMultipartUpload)
    <-- 返回 upload_id & part URLs (预签名)

Client -> S3 (PUT part) ... (并行分块上传)

Client -> API GW -> Snap Service (complete)
    -> Snap Service 生成 AES key
    -> 对每个 recipient 的 public_key 加密 AES key
    -> 写入 SnapMeta (Cassandra) + Redis cache
    -> 返回 snap_id

Receiver -> API GW -> Snap Service (GET snap)
    -> Snap Service 校验 receiver_id 在 recipients 列表
    -> 生成 30s 有效的 S3 Pre‑Signed URL
    -> 返回 URL (302)

Receiver -> Client 下载媒体，解密后展示

Receiver -> API GW -> Snap Service (viewed)
    -> Snap Service 记录 viewed_at, 计算 expires_at = now + ttl
    -> 把 expires_at 写入 SnapMeta
    -> Expiry Worker 定时删除对象
```

#### 1.4 “多副本安全擦除”实现细节  

1. **对象存储开启 Versioning**：每次写入/删除都会产生新版本。  
2. **删除时调用 `DeleteObject`**：产生 **Delete Marker**，隐藏所有版本。  
3. **随后调用 `DeleteObjectVersion`** 删除所有历史版本（如果法规要求不可恢复）。  
4. **在后台 GC**：使用 **S3 Object Lock**（如果支持）或 **自行覆盖**（上传全 0/随机数据）再删除，防止 **恢复工具** 恢复。  
5. **元数据库** 同步标记 `status=deleted`，防止再次查询到已删除的 Snap。  

> **不做多副本安全擦除** 的风险：单点泄露或**合规审计**无法证明数据已彻底删除，违背 Snap “阅后即焚”核心承诺。

---

### 2. Chat Service  

#### 2.1 主要职责  

- 接收 **实时消息**（WebSocket/gRPC）  
- 将消息写入 **Kafka**（持久化、顺序）  
- 将最近 N 条消息写入 **Redis**（热点读取）  
- 处理 **离线消息**（用户下线后仍能查询）  
- 维护 **会话状态**（已读、未读计数）  

#### 2.2 关键模块  

| 模块 | 功能 | 技术 |
|------|------|------|
| **WebSocket Server** | 双向实时推送 | `gorilla/websocket` / `Netty` |
| **Message Router** | 根据 `conversation_id` 路由至对应 Kafka 分区 | Kafka Producer (idempotent) |
| **Kafka Consumer** | 消费消息，写入 Redis + MySQL（归档） | Consumer Group |
| **Redis Cache** | 保存最新 100 条、未读计数（ZSET） | Redis Cluster |
| **MySQL Archiver** | 长期存储、审计 | 主从复制，读写分离 |
| **Ack & Retry** | 客户端 ACK，服务器端重试 | At‑least‑once + 幂等处理 |

#### 2.3 顺序与幂等保证  

- **Producer** 设置 `enable.idempotence=true`，Kafka 自动为每个 `msg_id` 分配唯一的 **producer sequence**，防止重复写入。  
- **Consumer** 在写入 Redis/MySQL 前检查 `msg_id` 是否已存在（通过 Redis `SETNX`），若已存在直接跳过。  

#### 2.4 离线消息处理  

1. **用户下线**：WebSocket 断开，服务端标记 `user_status=offline`（Redis）。  
2. **消息到来**：仍写入 Kafka，Consumer 写入 Redis ZSET `unread:{user_id}`（score=timestamp）。  
3. **用户重新登录**：读取 `unread:{user_id}`，推送给客户端，同时清空对应 ZSET。  

---

### 3. Friend Service  

#### 3.1 主要职责  

- 管理 **好友关系 CRUD**（添加、删除、分组、阻止）  
- 提供 **好友列表**、**是否为好友**的快速查询（缓存）  

#### 3.2 实现要点  

- **写入**：使用 **PostgreSQL** 事务，确保 `INSERT`、`DELETE` 原子。  
- **读取**：常用查询（`GET /friend/list`）走 **Redis Cache**（`SMEMBERS friend:{user_id}`），Cache‑Aside 策略。  
- **阻止**：在 `friends` 表中增加 `blocked` 字段，业务层统一过滤。  
- **分区**：PostgreSQL **Hash 分区**（`user_id`），每个分区约 1‑2 GB，方便水平扩展。  

---

### 4. 存储层细节  

| 层级 | 选型 | 关键配置 | 目的 |
|------|------|----------|------|
| **对象存储** | Amazon S3 / Alibaba OSS | 多 AZ 冗余、Versioning、Lifecycle（30 d） | 大文件、CDN 加速、自动过期 |
| **NoSQL KV** | Cassandra / DynamoDB | **RF=3**, **TTL**，Write‑heavy | SnapMeta、StoryMeta，写入高、查询快 |
| **关系型 DB** | PostgreSQL (主从) | **Logical Replication**, **Connection Pool** | 好友、用户，强一致 |
| **消息队列** | Kafka (3‑zone) | **Replication=3**, **min.insync.replicas=2** | 聊天持久化、顺序 |
| **缓存** | Redis Cluster | **TTL** (Snap URL 60 s), **ZSET** (未读计数) | 降低热点 DB/OSS 访问，提升延迟 |
| **CDN** | CloudFront / Akamai | **Edge Cache TTL 60 s** (Snap URL) | 全球低延迟分发 |

#### 读取路径示例（Snap）  

1. **客户端** 请求 `GET /snap/{id}` → API GW → **Snap Service**。  
2. **Snap Service** 首先在 **Redis** 查询 `snap:{id}`（元数据）。若 **命中**，直接生成 **Pre‑Signed URL** 并返回。  
3. **未命中** → 查询 **Cassandra**，写入 Redis 缓存后返回。  

> **为什么加 Redis**：即使对象存储查询 10 ms，Snap 元数据在高并发情况下会成为热点；Redis 通过 **毫秒级** 读取确保 **≤ 200 ms** 端到端延迟。

---

### 5. 可靠性、监控、容错  

| 维度 | 设计 | 目的 | 可能的故障 & 对策 |
|------|------|------|-------------------|
| **服务冗余** | 每个微服务部署 **3 实例**（不同 AZ）+ **负载均衡**（Envoy） | 防止单机故障 | 健康检查、自动下线 |
| **数据复制** | 对象存储 **跨 AZ**，Cassandra **RF=3**，Kafka **ISR ≥ 2** | 防止磁盘/机房失效 | 自动故障转移（Leader 迁移） |
| **幂等/重试** | API 返回 **唯一请求 ID**，后端 **幂等键**（Redis SETNX） | 防止网络抖动导致重复写入 | 重试策略（指数退避） |
| **限流** | API Gateway **令牌桶**（每用户 5 Snap/s） | 防止刷接口、DDoS | 触发降级、返回 429 |
| **监控** | **Prometheus** 抓取 QPS、Latency、ErrorRate；**Grafana** 可视化；**ELK** 日志；**Jaeger** 链路追踪 | 实时感知异常 | 设置 **Alertmanager** 报警 |
| **灾备** | **跨 Region**（美洲、欧洲、亚太）部署 **只读副本**，用户注册时就写入最近的 Region，读写路由通过 **GeoDNS** | 区域网络分区时仍能提供服务 | 数据同步使用 **CDC + Kafka MirrorMaker** |
| **自动扩容** | **Kubernetes HPA** 基于 CPU/QPS 自动伸缩；对象存储 **按需** 扩容 | 应对流量突增 | 预置 **Burst Capacity**（预热实例） |

> **不做容错**：单点故障（如对象存储区域不可用）会导致 **全部 Snap 无法下载**，用户体验瞬间崩溃，违背 99.9% 可用目标。

---

## ## 第六步：扩展性与高可用设计  

### 1. 横向扩展（Scale‑out）  

| 组件 | 扩容方式 | 关键指标 |
|------|----------|----------|
| **API Gateway** | 增加实例 + **负载均衡**（L7） | QPS ≤ 10 K/实例 |
| **Snap Service** | 部署 **Stateless** 容器，水平扩容；使用 **Consistent Hash** 将 `owner_id` 映射到特定实例（可选） | CPU 70% 为阈值 |
| **Chat Service** | 增加 **Kafka 分区数**，对应 **消费者实例** 成比例扩容 | Partition → 目标每秒写入 5 K 消息 |
| **Cassandra** | 添加 **节点**，使用 **Virtual Nodes** 重新分配 token | 写入吞吐 10 K ops/节点 |
| **Redis** | **Cluster** 扩容 slots，水平扩容 | 每秒命中率 99% |
| **对象存储** | 按需 **扩容**（S3 自动） | 存储容量、带宽均衡 |

### 2. 垂直扩展（Scale‑up）  

- **单实例 CPU/内存提升**：适用于 **热点业务**（如 Snap Service 在高峰期），但最终仍需 **水平** 以避免瓶颈。  

### 3. 多活与跨地域（Active‑Active）  

1. **用户分区**：根据 **User ID 哈希** 将用户划分到不同 Region（美洲、欧洲、亚太）。  
2. **数据同步**：  
   - **Cassandra** 本身支持跨 Region **多活**（使用 **NetworkTopologyStrategy**）。  
   - **Kafka** 使用 **MirrorMaker** 将消息复制到其它 Region，保证 **聊天跨区** 可达。  
3. **读写路由**：  
   - **DNS/Anycast** 将用户请求路由至最近 Region。  
   - **全局负载均衡**（如 AWS Global Accelerator）处理跨 Region 故障切换。  

#### 失效转移示例  

- 某 Region 网络分区 → **API Gateway** 检测到不可用，流量自动切换至最近的备份 Region。  
- **Cassandra** 中的跨 Region **RF=3** 确保写入仍可成功（至少 2 副本可写），随后异步复制到恢复的 Region。  

### 4. 成本控制  

| 成本项 | 优化手段 |
|--------|----------|
| **存储** | 采用 **冷热分层**：最近 7 天的 Snap 存放在 **标准存储**，30 天后迁移到 **低频/归档**，再结合 **生命周期** 自动删除。 |
| **网络** | CDN 缓存命中率 > 90% ⇒ 大幅降低对象存储出流量。 |
| **计算** | 使用 **Serverless**（AWS Lambda）处理 **上传完成回调**、**删除任务**，按需计费，避免常驻实例浪费。 |
| **消息队列** | Kafka **压缩**（Snappy）降低磁盘占用。 |

---

## ## 第七步：常见面试追问与回答  

下面列出面试官常会追问的点，提供 **思路、答案要点**，帮助你在现场快速组织语言。

| 追问 | 关键点 | 示例回答 |
|------|--------|----------|
| **1. Snap 的多副本安全擦除如何实现？** | - 对象存储开启 Versioning<br>- DeleteObject + DeleteVersion<br>- 覆盖或加密擦除<br>- GC 进程负责彻底删除<br>- DB 同步标记状态 | “我们把每个 Snap 的媒体文件存到 S3，开启 Versioning。用户观看后，后端记录 `expires_at`，后台 GC 进程在到期时先调用 `DeleteObject`（产生 Delete Marker），随后遍历所有版本使用 `DeleteObjectVersion` 逐一删除或先上传全 0/随机数据再删除，以防止恢复。元数据表同步标记 `status=deleted`，确保后续查询不到。” |
| **2. 高并发 Snap 发送时如何避免热点写入对象存储？** | - 客户端直传（预签名）<br>- 分块上传（并行）<br>- 多 Region CDN<br>- API Gateway 限流 | “上传过程不走业务服务器，而是让客户端直接使用 S3 预签名 URL 分块上传。业务服务器只负责生成元数据，这样写入对象存储的负载均匀分布在 S3 多 AZ。我们在 API Gateway 对每个用户做令牌桶限流，防止恶意刷上传。” |
| **3. Chat 消息的顺序和幂等如何保证？** | - Kafka 分区 = conversation_id hash<br>- Producer idempotent<br>- 消费端检查 msg_id 幂等<br>- 使用 Snowflake 全局唯一 ID | “每个会话对应唯一的 `conversation_id`，我们把它对 N 取模后作为 Kafka 分区键，这样同一会话的所有消息都会落在同一个分区，Kafka 本身保证 FIFO。Producer 开启 `enable.idempotence`，即使网络重试也不会产生重复记录。消费端在写入 Redis/MySQL 前使用 `SETNX(msg_id)` 检查是否已处理，实现幂等。” |
| **4. 跨 Region 网络分区时，阅后即焚的强一致性如何保证？** | - 多 Region 写入采用 **Quorum**（RF=3, min.insync=2）<br>- 采用 **两阶段提交**（写入 DB + 对象存储）<br>- 只在本 Region 完成后返回成功 | “Snap 的写入分两步：① 写入元数据（Cassandra）采用 quorum 写入，保证至少 2 副本成功；② 客户端上传媒体到最近的对象存储。只有两步都成功后才返回 `200`，即使某 Region 与外部网络中断，已写入本地 Region 的数据仍然保有两个副本，后续会通过跨 Region 同步恢复。阅后即焚的删除同样走 quorum，确保所有副本都被删除。” |
| **5. 如何监控并快速定位 Snap 删除失败的情况？** | - Prometheus 指标：`snap_delete_success_total`、`snap_delete_failure_total`<br>- 日志关联（snap_id、region、timestamp）<br>- 链路追踪（Jaeger）<br>- 警报阈值 | “我们在 Snap Service 的删除流程里埋点 `snap_delete_success_total` 与 `snap_delete_failure_total`，并在每次调用对象存储 API 时记录 `snap_id`、region、返回码到 ELK。若失败率在 5 分钟内超过 0.1%，Alertmanager 会触发告警。通过 Jaeger 我们可以看到是网络超时还是权限错误，快速定位问题。” |
| **6. 为什么不直接把 Snap 存在关系型数据库？** | - 大对象不适合 RDBMS（行大小限制、IO）<br>- 高写入/读出成本<br>- 难以做水平扩展<br>- 对象存储天然支持 CDN、生命周期 | “Snap 的平均大小约 5 MB，若存入 PostgreSQL，单行会占用大量磁盘页，导致 IO 瓶颈，而且扩容只能通过垂直升级，成本高。对象存储专为大文件设计，支持分块上传、自动弹性、全球 CDN，且可以直接设置生命周期规则，实现 24h 自动删除，极大简化业务逻辑。” |
| **7. 如何防止用户把 Snap 截图/录屏导致隐私泄漏？** | - 客户端层面（检测截屏事件）<n> - 法律/合规约束<br>- 后端不可阻止，只能做**威慑** | “从系统设计角度，服务器无法感知用户在本地截屏。我们可以在客户端监听系统截屏/录屏 API（iOS/Android），弹出提示并上报审计日志。但真正的防护只能依赖用户协议、法律约束以及对违规用户的封禁策略。” |

---

## ## 心得与反思  

### 1. 本题最难的 1–2 个设计决策  

| 决策 | 为什么最难 | 思考过程 |
|------|------------|----------|
| **阅后即焚的多副本安全删除** | 需要兼顾 **强一致性**、**合规要求**（不可恢复）以及 **高并发** 的删除操作。 | ① 先确定对象存储的底层特性（Versioning、Lifecycle）<br>② 评估删除时的并发冲突（同一 Snap 可能被多个接收方同时观看）<br>③ 设计 **幂等 GC**：使用 `snap_id` + `viewer_id` 生成唯一的 `deletion_task_id`，在 Redis 中 SETNX 防止重复删除<br>④ 决定在业务层记录 `status=deleted`，配合对象存储的 **DeleteObjectVersion** 完全擦除 |
| **聊天顺序与幂等的保证** | 消息顺序必须跨机器、跨数据中心保持，而又要防止网络重试导致重复展示。 | ① 选定 **Kafka** 作为持久化日志，利用 **partition key = conversation_id** 保证同一会话 FIFO<br>② 开启 **producer.idempotence**，并在消费者端使用 **msg_id** 进行去重<br>③ 设计 **离线缓存**（Redis ZSET）时保留 `msg_id` 作为唯一键，确保即使消费失败也不会重复写入 |
| **跨 Region 的强一致写入**（涉及 Snap、用户） | 需要在保证可用性的前提下，防止网络分区导致数据不一致或丢失。 | ① 采用 **Quorum** 写入模型（RF=3, min.insync=2）<br>② 对业务层实现 **两阶段提交**（先写元数据再返回成功）<br>③ 通过 **CDC + Kafka MirrorMaker** 实现跨 Region 同步，确保最终一致性 |

### 2. 新手最容易犯的错误（至少 2 条）  

| 错误 | 说明 | 正确做法 |
|------|------|----------|
| **把大文件直接写进关系型数据库** | 会导致磁盘 IO 爆炸、难以水平扩容，且不利于 CDN 加速。 | 使用 **对象存储（S3）**，只在 DB 中保存 **元数据**（URL、加密信息）。 |
| **忽视幂等性，直接把写入当成一次成功** | 网络抖动或客户端重试会产生 **重复 Snap/消息**，影响用户体验。 | 为每个请求生成 **全局唯一 ID**（如 Snowflake），在业务层做 **幂等检查**（Redis SETNX / DB 唯一键）。 |
| **把所有业务写在单体服务里，等到流量增长再拆** | 初期虽然快，但后期难以水平扩展，改造成本极高。 | 从一开始就划分 **业务边界**（Snap、Chat、Friend），使用 **REST/gRPC** 接口，容器化部署，方便后期拆分。 |
| **只关注读的性能，忽略写的削峰** | Snap 上传是 **写密集**，若没有分块上传和直连对象存储，会导致 **CPU/网络瓶颈**。 | 采用 **客户端直传（预签名 URL）+ 分块上传**，业务服务只负责元数据写入。 |
| **把所有数据放在单个 Region** | 跨国用户会出现 **高延迟**，且单点故障影响全局可用性。 | 使用 **多 Region 部署**，并依据 **User ID 哈希** 将用户划分到最近 Region，跨 Region 用 **复制/同步** 保证最终一致性。 |

### 3. 学习建议和可延伸的方向  

| 方向 | 推荐学习资源 | 说明 |
|------|--------------|------|
| **分布式系统基础** | 《Designing Data‑Intensive Applications》、MIT 6.824 课程 | 理解 CAP、复制、分区、事务模型 |
| **对象存储 & CDN** | AWS S3 官方文档、阿里云 OSS 手册 | 熟悉分块上传、生命周期、版本控制 |
| **消息队列（Kafka）** | 《Kafka: The Definitive Guide》、Confluent 在线培训 | 掌握分区、消费者组、幂等生产者 |
| **实时通信** | 《WebSocket 实战》、SignalR / gRPC 文档 | 实现低延迟双向推送 |
| **加密与安全** | 《Applied Cryptography》章节、OWASP Top 10 | 端到端加密、密钥管理、TLS |
| **容器化 & 编排** | Docker 官方教程、Kubernetes 官方文档 | 实现微服务的快速部署、弹性伸缩 |
| **监控与可观测性** | Prometheus + Grafana 官方指南、Elastic Stack 入门 | 建立指标、日志、链路追踪体系 |
| **系统容量规划** | 《Capacity Planning for Web Services》、Google SRE 手册 | 通过实验验证 QPS、存储、网络需求 |

> **练手项目**：  
> 1. 搭建一个 **Mini‑Snap**：使用前端拍照、后端 S3 直传、Redis 缓存 Snap 元数据、后台 GC 删除。  
> 2. 在此基础上加入 **WebSocket 聊天**，使用 Kafka 持久化，练习顺序保证和幂等。  
> 3. 用 **Kubernetes** 部署多副本，配置 **Prometheus** 监控，尝试模拟故障（kill Pod、网络分区）观察自愈过程。  

通过实际动手，你会对每个设计点的 **动机、实现细节、风险点** 有更深的感受，在面试时能自然、条理清晰地阐述。

---  

**祝你面试顺利，成为下一个设计出 “阅后即焚” 系统的高手！** 🎉
