# 第 1 天：设计 Discord

> 生成日期：2026-05-25

---

## 题目背景
Discord 是一个面向游戏玩家及社区的实时语音、视频、文字聊天平台，支持创建服务器（Server）和频道（Channel），用户可以在其中进行即时通讯、文件共享以及社区管理等操作。

## 面试场景设定
> **面试官**：  
> “我们现在需要设计一个类似 Discord 的即时聊天系统，核心目标是支持大规模的实时语音/文字频道以及高并发的消息投递。请从需求、架构到关键技术点逐步展开你的设计思路。”

## 功能性需求
1. **用户注册与登录**  
   - 支持邮箱/手机号/第三方 OAuth 登录，保持会话状态。  
2. **服务器（Server）与频道（Channel）管理**  
   - 创建/删除服务器、文字频道、语音频道；设置角色与权限。  
3. **实时文字聊天**  
   - 发送、接收、编辑、删除消息；支持消息顺序、已读回执、表情、文件/图片上传。  
4. **实时语音通话**  
   - 多人语音频道，支持加入/离开、静音、降噪、回声消除；要求端到端延迟 ≤ 100 ms。  
5. **推送与离线消息**  
   - 当用户离线时，服务器持久化消息并在用户恢复在线后推送；支持移动端推送通知。  
6. **搜索与历史记录**  
   - 按关键词、时间范围搜索文字消息，支持分页浏览。

## 非功能性需求
| 指标 | 估算值 | 说明 |
|------|--------|------|
| **DAU（每日活跃用户）** | 2,000 万 | 目标覆盖全球主流游戏社区 |
| **并发在线用户峰值** | 1,000 万 | 同时在线的用户数 |
| **QPS（消息写入）** | 150,000 req/s | 文字消息写入峰值（平均 1 条/秒/活跃用户） |
| **消息投递延迟** | ≤ 200 ms（文字）<br>≤ 100 ms（语音） | 从发送端到接收端的端到端时延 |
| **可用性** | 99.95%（全年累计） | 计划每年累计宕机时间 < 4 小时 |
| **存储容量** | 约 500 PB | 文字+媒体（图片/视频）持久化 2 年后归档，假设 1 GB/活跃用户/年 |

## 系统边界
**本题范围内需要设计的功能**  
- 用户身份认证、服务器/频道管理、实时文字与语音聊天、离线消息持久化与推送、搜索与历史记录。  
- 基础的监控、日志、故障恢复机制。

**不在本题范围（可说明但不必实现）**  
- 视频通话、屏幕共享等高级媒体功能。  
- 跨平台客户端（桌面/移动）实现细节。  
- 付费增值服务（如 Nitro）以及营销系统。  
- 机器学习推荐/内容审查系统。  
- 第三方 Bot 平台的完整生态（仅需预留 API 接口）。

## 提示与追问
1. **伸缩性**：  
   - “如果日活从 2,000 万增长到 5,000 万，你会如何扩展消息写入层和语音转发层？”  

2. **一致性与顺序**：  
   - “文字频道需要保证消息的全局顺序吗？如果需要，你会选哪种一致性模型？”  

3. **语音通道实现**：  
   - “在低延迟的语音频道里，你会采用哪些编解码器、传输协议以及服务器部署策略来满足 100 ms 的端到端延迟？”  

---

# 题解

# Discord 类即时聊天系统设计详解  
> **适读对象**：刚入行的后端新人，系统设计经验几乎为零。  
> **目标**：从最小可运行的 MVP（最小可行产品）一步步构建到能够支撑 **2000 万 DAU、1000 万并发在线** 的高可用分布式系统。每一步都解释「为什么」而不是仅给出「做什么」。

---

## ## 解题思路总览
1. **先把需求拆解成**「功能块」与「非功能块」  
   - 功能块：用户/身份、服务器/频道、文字聊天、语音聊天、离线推送、搜索。  
   - 非功能块：高并发、低延迟、可用性、扩展性、监控、灾备。  

2. **先做最小可用系统（MVP）**  
   - 单体后端 + 单库 + 同步 HTTP/WebSocket。  
   - 只实现「文字聊天」+「基本鉴权」+「持久化」的核心路径。  

3. **逐步拆分**  
   - 把 **读写分离**、**缓存**、**消息队列**、**搜索服务**、**语音转发层**等抽象为独立组件。  
   - 每拆一次，就在 **可用性**、**扩展性**、**故障隔离** 上提升一个层级。  

4. **在每个层级都要回答**  
   - **为什么要这么做？**（问题驱动）  
   - **不这么做会出现什么痛点？**（风险说明）  

5. **最终交付**  
   - 完整的 **高层架构图**（文字）  
   - 详细的 **数据库 schema** 与 **分区/索引策略**  
   - **核心 API**（REST + WebSocket）设计  
   - **关键组件**（消息写入、投递、语音转发、搜索、推送）的内部实现思路  
   - **扩展/高可用** 方案（多 AZ、CDN、容灾）  
   - **常见面试追问** 的标准答案  

---

## ## 第一步：理解需求与规模估算  

| 需求 | 关键点 | 对系统的直接影响 |
|------|--------|-------------------|
| **用户注册/登录** | 多种 OAuth、会话持久化 | 需要统一的 **Auth Service**，安全存储密码/Token |
| **Server/Channel 管理** | 角色/权限、层级结构 | 数据模型必须支持 **层级树** 与 **ACL**（访问控制列表） |
| **实时文字聊天** | 发送/编辑/删除、顺序、已读、表情、文件 | **强一致性**（同一频道内顺序），**高吞吐**（150k QPS） |
| **实时语音** | 多人、低延迟 ≤100 ms、回声消除 | **实时转发**（UDP/QUIC），**媒体服务器** 需要做负载均衡 |
| **离线推送** | 持久化 + 移动端推送 | **消息持久化** + **Push Service**（APNs/FCM） |
| **搜索 & 历史** | 关键字、时间范围、分页 | **全文检索**（Elasticsearch）需要同步写入 |
| **非功能需求** | 高并发、低延迟、高可用、海量存储 | 决定 **水平扩展、分区、缓存、容灾** 的整体方案 |

### 1️⃣ 规模估算（基于题目提供的指标）

| 指标 | 计算方式 | 结果 |
|------|----------|------|
| **活跃用户** | DAU = 20M，假设 70% 同时在线 | 14M 同时在线 |
| **峰值并发在线** | 题目给 10M，保守取 10M | 10M 真实并发 |
| **消息写入 QPS** | 150k req/s（文字） | 150,000 条/秒 |
| **每条消息大小** | 平均 200B（文字+元数据） | 30 MB/s ≈ 240 Mbps |
| **语音流量** | 假设 64 kbps × 2 M 并发语音用户 | 128 Mbps |
| **存储** | 500 PB / 2 年 ≈ 250 PB/年 ≈ 680 TB/天 | 需要 **对象存储 + 多副本** |
| **读/写比例** | 读 ≈ 写的 5 倍（浏览历史、搜索） | 读取峰值 ≈ 750k req/s |

> **为什么要做这些数字？**  
> 只有把需求量化为「每秒多少请求」「每秒多少流量」才能决定 **网络带宽**、**CPU 核数**、**磁盘 IOPS**、**分区键** 等关键技术选型。如果不量化，往往会在后期出现「瓶颈突发」导致系统崩溃的风险。

---

## ## 第二步：高层架构设计  

### 2.1 MVP（单体）架构
```
+-------------------+
|   API Gateway     |  <-- REST + WebSocket 入口
+-------------------+
        |
        v
+-------------------+
|   Application     | 业务逻辑（用户、频道、消息）
+-------------------+
        |
        v
+-------------------+
|   Relational DB   | MySQL (单实例)
+-------------------+
```
- **优点**：实现快、调试方便、一次性跑通核心流程。  
- **缺点**：单点故障、无法水平扩展、无法满足 150k QPS。

### 2.2 第一层拆分：**微服务 + 读写分离**
```
          +-------------------+        +-------------------+
          |   API Gateway     | <--->  |   Auth Service    |
          +-------------------+        +-------------------+
                |  (REST/WebSocket)          |
                v                              v
          +-------------------+        +-------------------+
          |   Chat Service    | <--->  |   User Service    |
          +-------------------+        +-------------------+
                |  (gRPC)                     |
                v                              v
      +-------------------+          +-------------------+
      |   Message DB (R)  |          |   User DB (R)     |
      +-------------------+          +-------------------+
                ^                              ^
                |  (MySQL 主从复制)            |
      +-------------------+          +-------------------+
      |   Message DB (W)  |          |   User DB (W)     |
      +-------------------+          +-------------------+
```
- **读写分离**：主库负责写，多个从库提供读，降低写库压力。  
- **服务拆分**：每个服务只负责单一领域，易于水平扩容、团队协作。  

### 2.3 完整高可用分布式架构（满足 2k DAU、10M 并发）

```
                           +-------------------+
                           |   CDN / Edge DNS |
                           +-------------------+
                                    |
        --------------------------------------------------------------------
        |                       全球流量入口（L7）                        |
        |                (Anycast + GSLB, 如 Cloudflare, AWS Global)      |
        --------------------------------------------------------------------
                                    |
                 +------------------+-------------------+
                 |                  |                   |
      +----------------+   +----------------+   +----------------+
      |  API Gateway   |   |  Auth Service  |   |  Rate Limiter |
      +----------------+   +----------------+   +----------------+
                 |                  |                   |
        ---------------------------------------------------------
        |                     Service Mesh (Istio)               |
        ---------------------------------------------------------
                 |                  |                   |
   +-----------------+   +-----------------+   +-----------------+
   |  Chat Service   |   |  Voice Service  |   |  Notification   |
   +-----------------+   +-----------------+   +-----------------+
        |  (gRPC)               |  (WebRTC/UDP)         | (Push)
        v                       v                       v
+----------------+   +-------------------+   +-------------------+
|  Message Queue |   |  Media (SFU)      |   |  Push Provider    |
|  (Kafka)       |   |  (Janus/Mediasoup)|   |  (FCM/APNs)       |
+----------------+   +-------------------+   +-------------------+
        |                       |                       |
        v                       v                       v
+----------------+   +-------------------+   +-------------------+
|  Message Store |   |  Voice Relay      |   |  Push Store       |
|  (Cassandra)   |   |  (Redis Streams)  |   |  (Redis)          |
+----------------+   +-------------------+   +-------------------+
        |                       |                       |
        v                       v                       v
+----------------+   +-------------------+   +-------------------+
|  Search Index  |   |  Metrics/Logging  |   |  Monitoring       |
|  (ES)          |   |  (Prometheus)     |   |  (Grafana)        |
+----------------+   +-------------------+   +-------------------+
```

#### 关键技术选型说明
| 组件 | 备选技术 | 选型理由 |
|------|----------|----------|
| **API Gateway** | Kong / AWS API GW / Nginx | 支持 **路由、限流、鉴权**，可水平扩容 |
| **Auth Service** | JWT + Redis Session | JWT 免状态，Redis 存放刷新 Token，兼容 OAuth |
| **Chat Service** | Go / Java (Spring Boot) | 高并发、成熟的 gRPC 框架 |
| **Message Queue** | **Kafka**（分区+副本） | 持久化、顺序保证、吞吐 100k+ QPS |
| **Message Store** | **Cassandra**（宽列） | 按 **ChannelID+MessageID** 分区，天然水平扩展 |
| **Search** | Elasticsearch | 近实时全文检索，支持高并发查询 |
| **Voice Service** | **Mediasoup**（SFU） + **QUIC/UDP** | 低延迟、支持多路复用、可水平扩容 |
| **Push** | FCM / APNs + Redis 订阅 | 可靠的移动推送，Redis 做消息去重 |
| **Metrics** | Prometheus + Grafana | 业界标准监控体系 |

> **为什么要把消息写入、投递、存储分离？**  
> - **写入**（Kafka Producer）只负责把用户的「发送请求」落盘，**不阻塞**业务线程。  
> - **投递**（Chat Service Consumer）从 Kafka 读取，做「顺序检查、ACK、推送」等业务，**可以弹性伸缩**。  
> - **存储**（Cassandra）只负责持久化，不参与业务逻辑，提升 **读写解耦** 与 **故障隔离**。

---

## ## 第三步：数据库设计  

### 3.1 关系型 DB（用户、服务器、角色、权限）  
使用 **MySQL**（或 Aurora PostgreSQL）做强一致的事务操作。  

| 表名 | 主键 | 关键字段 | 索引 | 备注 |
|------|------|----------|------|------|
| **users** | `user_id (BIGINT AUTO)` | `email, phone, password_hash, created_at` | 唯一索引 `email`, `phone` | 用户基本信息 |
| **auth_tokens** | `token_id (UUID)` | `user_id, refresh_token, expires_at` | 索引 `user_id` | JWT 刷新 token（存 Redis 也可） |
| **servers** | `server_id (BIGINT)` | `owner_id, name, created_at` | 索引 `owner_id` | Discord “Server” |
| **channels** | `channel_id (BIGINT)` | `server_id, type (TEXT/VOICE), name, position` | 索引 `server_id` | 频道层级 |
| **roles** | `role_id (BIGINT)` | `server_id, name, permissions` | 索引 `server_id` | 角色定义 |
| **member_roles** | `server_id, user_id, role_id` | 复合主键 | 索引 `user_id` | 多对多关系 |
| **channel_acl** | `channel_id, role_id, allow_mask, deny_mask` | 复合主键 | 索引 `role_id` | 细粒度权限控制 |

> **为什么把用户相关数据放 MySQL？**  
> - 需要 **强事务**（注册、密码更新、角色变更）  
> - 数据量相对 **消息** 少（几千万条），单表规模可接受。  

### 3.2 宽列存储（消息） – Cassandra  

**表结构（CQL）**

```cql
CREATE TABLE messages (
    server_id    bigint,
    channel_id   bigint,
    message_id   timeuuid,          // 基于时间的唯一 ID，保证顺序
    sender_id    bigint,
    content      text,
    attachments  list<text>,       // 对象存储 URL
    edit_history list<text>,
    created_at   timestamp,
    edited_at    timestamp,
    PRIMARY KEY ((server_id, channel_id), message_id)
) WITH CLUSTERING ORDER BY (message_id ASC);
```

- **分区键**：`(server_id, channel_id)` → 同一频道的所有消息落在同一个分区，查询时只扫一个分区，**读取延迟低**。  
- **Clustering Key**：`message_id`（时间有序） → 保证 **频道内顺序**。  
- **副本因子**：`3`（跨 AZ） → 满足 **99.95% 可用**。

#### 3.2.1 消息 ID 生成
- 使用 **UUIDv1**（基于时间+机器 MAC）或 **Snowflake**。  
- **保证全局递增**，方便在搜索、分页时使用 `WHERE message_id > last_seen_id`。

#### 3.2.2 索引 & 二级查询
- **全文检索**：写入成功后异步推送到 **Elasticsearch**（Kafka → Logstash → ES）。  
- **时间范围查询**：Cassandra 自带 `created_at`，可配合 **TTL**（如 2 年后自动删除）  

### 3.3 媒体对象存储（图片、文件、语音）  

| 存储方案 | 结构 | 优点 |
|----------|------|------|
| **对象存储**（AWS S3 / OSS） | `bucket / user_id / server_id / channel_id / uuid.ext` | 高可用、按需扩容、直接 CDN 加速 |
| **元数据** | 存在 `attachments` 列表里，只保存 URL 与 MIME | 轻量化，读取时不需访问对象存储 |

> **为什么不把文件直接放 DB？**  
> 大文件会导致 **IO 争用**，并显著增加 **备份/恢复** 成本。对象存储天然支持 **分块上传** 与 **CDN 加速**，更符合成本/性能需求。

---

## ## 第四步：核心 API 设计  

### 4.1 鉴权（OAuth + JWT）  

| 方法 | URL | 请求体 | 响应 | 说明 |
|------|-----|--------|------|------|
| `POST` | `/api/v1/auth/login` | `{ "email": "...", "password": "..." }` | `{ "access_token": "...", "refresh_token": "...", "expires_in": 3600 }` | 返回 JWT，放在 `Authorization: Bearer` 里 |
| `POST` | `/api/v1/auth/refresh` | `{ "refresh_token": "..." }` | 同上 | 刷新 Access Token |
| `GET` | `/api/v1/auth/me` | Header `Authorization` | `{ "user_id": ..., "email": "...", "roles": [...] }` | 获取当前登录用户信息 |

> **为什么使用 JWT 而非 Session ID？**  
> - **无状态**，后端不需要存放会话，可直接水平扩容。  
> - **跨服务**（API Gateway → Chat Service）只要验证签名即可。

### 4.2 服务器 & 频道管理  

| 方法 | URL | 请求体 | 响应 | 备注 |
|------|-----|--------|------|------|
| `POST` | `/api/v1/servers` | `{ "name": "My Server" }` | `{ "server_id": 12345 }` | 创建 Server |
| `POST` | `/api/v1/servers/{sid}/channels` | `{ "type":"TEXT", "name":"general" }` | `{ "channel_id": 987 }` | 创建频道 |
| `GET` | `/api/v1/servers/{sid}` | — | Server+Channel 列表 | 前端渲染左侧导航 |
| `PATCH` | `/api/v1/channels/{cid}` | `{ "name":"new name" }` | 200 OK | 编辑频道（权限校验） |

### 4.3 文字聊天（WebSocket）  

**连接**：`ws://chat.example.com/ws?access_token=xxx`  

| 消息类型 | 方向 | 数据结构（JSON） | 说明 |
|----------|------|-------------------|------|
| `JOIN_CHANNEL` | Client → Server | `{ "type":"JOIN_CHANNEL", "channel_id":123 }` | 进入频道，服务器返回最近 N 条消息 |
| `NEW_MESSAGE` | Client → Server | `{ "type":"NEW_MESSAGE", "channel_id":123, "content":"hello", "attachments":[...] }` | 服务器写入 Kafka，返回 `message_id` |
| `MESSAGE_DELIVERED` | Server → Client | `{ "type":"MESSAGE_DELIVERED", "channel_id":123, "message":{...} }` | 实时推送给同频道其他在线用户 |
| `EDIT_MESSAGE` | Client → Server | `{ "type":"EDIT_MESSAGE", "channel_id":123, "message_id":"uuid", "new_content":"..." }` | 只允许发送者或管理员编辑 |
| `DELETE_MESSAGE` | Client → Server | `{ "type":"DELETE_MESSAGE", "channel_id":123, "message_id":"uuid" }` | 软删，标记 `is_deleted` |
| `READ_ACK` | Client → Server | `{ "type":"READ_ACK", "channel_id":123, "last_read_message_id":"uuid" }` | 用于已读回执，可写入 Redis 计数 |

> **为什么使用 WebSocket 而不是纯 HTTP?**  
> - 实时聊天需要 **双向推送**，WebSocket 可以保持长连接，省去轮询的 **网络开销** 与 **延迟**。  
> - 对于文字消息，**可靠传输**（TCP）更重要；对语音则另有 UDP/QUIC 方案。

### 4.4 语音聊天（WebRTC + SFU）  

| 步骤 | 描述 |
|------|------|
| 1️⃣ **信令**：客户端通过 **WebSocket**（/api/v1/voice/signal）发送 `JOIN_VOICE`，携带 `channel_id`、`SDP offer` |
| 2️⃣ **SFU 选路**：Voice Service（基于 Mediasoup）创建 **Router**、**Transport**，返回 `SDP answer` |
| 3️⃣ **媒体流**：浏览器/客户端使用 **UDP/QUIC** 直接向 SFU 发送 Opus 编码的 RTP 包，SFU 做 **转发（Selective Forwarding）**，只把每路音频转发给其他订阅者 |
| 4️⃣ **控制**：`MUTE/UNMUTE`、`DEAFEN` 通过信令通道通知 SFU，SFU 只转发或屏蔽对应流 |

> **为什么不使用 MCU（全混合）？**  
> - MCU 必须把所有音频解码混合后再编码，CPU 消耗巨大，且 **延迟 > 100 ms**。  
> - **SFU** 只转发原始 RTP，CPU 低，且可以做到 **端到端 < 100 ms**（只受网络与排队延迟影响）。

### 4.5 推送 & 离线消息  

| 场景 | 处理流程 |
|------|----------|
| **用户在线** | 消息经 Kafka → Chat Service → WebSocket 直接推送 |
| **用户离线** | 消息写入 Cassandra + 写入 Elasticsearch。Chat Service 将 `message_id` 记录到 **Redis ZSET** `offline:{user_id}`（score=timestamp）。当用户下次登录时，后端读取 ZSET，批量拉取对应消息，推送给客户端并清空 ZSET。 |
| **移动端推送** | 同步把离线消息写入 **Push Queue**（Kafka topic `push_events`），Push Service 读取后调用 FCM/APNs，附带 **badge count**。 |

---

## ## 第五步：详细组件设计  

### 5.1 消息写入路径（文字）  

```
Client (WebSocket) --> API Gateway --> Chat Service (gRPC) --> Kafka (topic: channel-<id>) --> 
   Consumer (Chat Worker) --> 1) Cassandra (store) 2) Redis (real‑time cache) 3) ES (index)
```

#### 关键点
1. **Kafka 分区策略**  
   - Partition Key = `channel_id` → 同一频道的所有消息落同一分区，保证 **顺序**。  
   - 分区数 = `#servers × avg_channels_per_server`（可动态扩容）。  

2. **写入成功的 ACK**  
   - 客户端收到 `MESSAGE_DELIVERED` 只在 **Kafka 写入成功** 后返回，保证 **至少一次** 投递。  

3. **幂等性**  
   - 消息 ID (`message_id`) 在 Producer 端生成，Consumer 端对同一 `message_id` 做 **幂等写入**（Cassandra `INSERT IF NOT EXISTS`）。

### 5.2 消息投递路径（文字）  

```
Chat Worker (Consumer) --> Reads from Kafka partition
   |
   +--> Push to all online users via Redis Pub/Sub (channel: online:{channel_id})
   |          |
   |          +--> API Gateway → WebSocket Server → each client
   |
   +---> Write to Cassandra (persist)
   |
   +---> Write to Elasticsearch (async)
```

- **Redis Pub/Sub** 用来实现 **低延迟广播**，只要用户在 `online:{channel_id}` 集合里，即可实时收到。  
- 当某台机器的 WebSocket Server 失效，**Pub/Sub** 的消息仍会被其他机器消费，**不会丢失**。

### 5.3 语音转发（SFU）  

```
Client A ----> UDP/QUIC ----> Mediasoup Router (Media Node 1) ----> UDP/QUIC ----> Client B
                ^                                         ^
                |-- Signaling (WebSocket) via API GW ----|
```

- **Media Node** 按照 **区域（Region）** 部署，例如 `us-east-1`, `eu-west-1`，客户端就近连接。  
- **负载均衡**：使用 **Consistent Hash**（hash(user_id) % N) → 固定路由到同一个 Media Node，避免跨节点转发产生额外延迟。  
- **弹性伸缩**：监控每个 Media Node 的 **CPU/网络 I/O**，当达到阈值时自动 **水平扩容**（新增节点，使用服务发现更新路由表）。

### 5.4 搜索服务  

1. **写入**：Chat Worker 将消息的 `content`, `attachments`, `sender_id`, `timestamp` 发送到 **Kafka topic `search_sync`**。  
2. **同步**：Logstash / Kafka Connect 读取该 topic，写入 **Elasticsearch** 索引 `messages-<yyyy.mm>`（按月分片）。  
3. **查询 API**：`GET /api/v1/search?guild_id=...&keyword=...&from=...&size=20` → Search Service → ES → 返回 `message_id` 列表 → 再批量从 Cassandra 拉取完整内容（避免 ES 返回不完整字段）。

> **为什么不直接在 Cassandra 做全文检索？**  
> Cassandra 只支持二级索引，检索性能和功能远不如 ES；使用 ES 能实现 **高亮、模糊、分词**，且查询延迟 < 50 ms。

### 5.5 监控、日志、容灾  

| 维度 | 监控指标 | 工具 |
|------|----------|------|
| **系统** | CPU、Mem、Disk I/O、Network | Prometheus Node Exporter |
| **服务** | QPS、错误率、延迟（p99） | Prometheus + Grafana |
| **业务** | 在线人数、活跃频道数、消息堆积长度（Kafka lag） | Kafka Exporter, Custom Exporter |
| **日志** | 请求链路、异常栈 | ELK (Filebeat → Logstash → Kibana) |
| **告警** | 关键阈值触发（CPU>80% 连续 5min） | Alertmanager + PagerDuty |

**容灾**  
- **多 AZ 部署**：每个服务（Kafka、Cassandra、Redis、Media Node）至少 3 副本跨不同可用区。  
- **跨 Region 复制**：使用 **Cassandra 跨 Region Replication**（或 DynamoDB Global Tables）以及 **Kafka MirrorMaker** 同步关键 topic。  
- **灾难恢复演练**：每月模拟单 AZ 故障，验证自动故障转移。

---

## ## 第六步：扩展性与高可用设计  

### 6.1 当 DAU 从 20M 增长到 50M  

| 目标 | 方案 |
|------|------|
| **写入吞吐**（150k → 375k QPS） | - **Kafka** 扩大分区数（每个频道 1 分区 → 多分区），使用 **生产者批量压缩**（batch.size、linger.ms）<br>- **Chat Service** 横向扩容（K8s HPA）<br>- **Cassandra** 增加节点，重新平衡 Token |
| **语音并发**（假设 2M → 5M 语音用户） | - 按 **Region** 再细分 **Zone**，每个 Zone 部署更多 **Media Nodes**<br>- 使用 **QUIC** 取代 UDP，跨 NAT/防火墙更稳健<br>- 采用 **动态码率自适应**（64kbps → 96kbps） |
| **搜索负载** | - **Elasticsearch** 增加节点，使用 **Hot/Warm** 节点分层<br>- 将 **热点频道** 的索引提前写入 **Hot** 节点，降低冷数据查询延迟 |
| **缓存层** | - 使用 **Redis Cluster**，分片数提升至 1024，减小单键热点<br>- 引入 **CDN** 缓存常用媒体（图片、表情包） |
| **网络** | - 在核心节点前使用 **Anycast** + **Global Load Balancer**，把用户流量路由到最近的 Edge 节点<br>- 对 **WebSocket** 采用 **TLS termination** 在 Edge，后端内部使用 **mTLS** 保证安全 |

### 6.2 一致性与顺序  

- **文字频道**：  
  - **强顺序** 只在**单频道内部**保证（Kafka 分区 + Cassandra clustering key）。  
  - **全局顺序**（跨频道）不需要，降低系统复杂度。  

- **读写模型**：  
  - **写**：`POST /messages` → Kafka → 顺序写入分区 → **至少一次**（幂等）  
  - **读**：从 **Cassandra** 拉取最新 N 条（可加 **Cache**） → **最终一致**（短暂的复制延迟 < 100 ms）  

> **如果不做分区保证顺序**，会导致同一频道的消息乱序，用户体验极差；如果强求全局顺序，则会把所有消息压到同一个分区，吞吐直接受单分区上限（≈ 5k QPS），无法满足需求。

### 6.3 容错与降级  

| 场景 | 降级策略 |
|------|----------|
| **Kafka 失效** | 使用 **本地缓冲队列**（磁盘写入）临时缓存，恢复后批量补齐 |
| **Cassandra 超时** | 读取走 **Redis Cache**（最近 10k 条），写入走 **写入日志**，稍后批量同步 |
| **Media Node 超载** | 将用户自动转移到 **备份 Region**，并提示 “语音质量受限” |
| **搜索服务不可用** | 暂时返回 “搜索功能维护中”，但仍能正常收发消息 |
| **Push Service 失效** | 只保留离线消息在 Redis，等服务恢复后统一下发 |

---

## ## 第七步：常见面试追问与回答  

### Q1️⃣ **如果文字频道需要全局顺序该怎么办？**  

- **答案**：  
  1. 使用 **单全局 Kafka Topic**（所有消息同一分区），这会把吞吐压到单分区上限（≈ 5k QPS），显然不可行。  
  2. 采用 **分布式全序协议**（如 **Paxos/Raft**）在每条消息写入前进行共识，延迟会大幅提升（> 30 ms），不符合实时聊天的需求。  
  3. **实际业务**：全局顺序并非必要，只需要**频道内部**顺序即可。若业务真的需要（如金融交易），则把该类业务抽离成单独的 **顺序服务**（单独的 Kafka 分区），而不是把所有聊天都放进去。  

### Q2️⃣ **语音通道如何保证 ≤100 ms 的端到端延迟？**  

- **答案**：  
  1. **协议层**：使用 **WebRTC** + **SRTP**（加密）+ **QUIC**（UDP+拥塞控制），避免 TCP 的三次握手和重传导致的额外时延。  
  2. **编解码**：采用 **Opus**（采样率 48 kHz，码率 16–64 kbps），在保持音质的前提下具备 **低编码延迟**（≈ 5 ms）。  
  3. **网络路径**：  
     - **就近路由**：通过 **Anycast DNS + Edge LB** 把客户端直接连到最近的 **Media Node**，跨 Region 的 RTT 通常 < 30 ms。  
     - **SFU** 只转发 RTP，不做混音/转码，CPU 开销极低，转发延迟 < 5 ms。  
  4. **服务器调度**：Media Node 采用 **CPU‑affinity** 与 **实时调度**（Linux `SCHED_RR`），保证音频帧在 20 ms 内被处理。  
  5. **监控**：对每条 RTP 包的 **发送‑接收时间戳** 进行实时统计，若出现 > 100 ms 的抖动，自动 **降级码率** 或 **切换到备用节点**。  

### Q3️⃣ **Kafka 消费延迟如果堆积会怎样？如何处理？**  

- **答案**：  
  - **堆积原因**：消费者处理能力不足、后端 DB 写慢、网络拥塞。  
  - **影响**：消息在 Kafka 中滞后，导致 **实时聊天延迟** 增大，用户体验下降。  
  - **处理办法**：  
    1. **水平扩容** 消费者实例（使用 **Kafka Consumer Group**），自动分摊分区。  
    2. **调优批量大小**（`fetch.min.bytes`、`max.poll.records`）和 **并发处理**（线程池），提升单实例吞吐。  
    3. **监控 Lag**（Kafka Exporter），当 Lag 超过阈值（如 5 s）触发 **自动弹性伸缩**。  
    4. **后备队列**：如果 DB 写入慢，先把消息写入 **Redis Stream**，等 DB 恢复后再批量同步。  

### Q4️⃣ **为什么要使用两套存储（Cassandra + Elasticsearch）而不是只用一种？**  

- **答案**：  
  - **Cassandra**：为 **高吞吐、写放大** 设计，适合 **时间序列**、**宽列** 场景，支持 **线性扩容**，且天然 **强一致**（可调）写入。查询只能基于主键或二级索引，无法实现复杂全文检索。  
  - **Elasticsearch**：专为 **全文检索、聚合、排序** 优化，倒排索引提供 **亚秒级** 查询，但写入成本高，且不适合做 **强一致** 的持久化存储。  
  - **组合使用**：写入时先写 Cassandra（确保可靠），异步同步到 ES（实现搜索），两者各司其职，兼顾 **可靠性** 与 **查询体验**。  

### Q5️⃣ **如果某个数据中心完全宕机，系统还能正常服务吗？**  

- **答案**：  
  1. **跨 AZ 多副本**：Cassandra、Kafka、Redis 都配置 **RF=3**，即使一个 AZ 完全失联，仍有两副本可提供读写。  
  2. **跨 Region 同步**：使用 **Kafka MirrorMaker** 与 **Cassandra 多 Region Replication**，把关键数据实时复制到另一个 Region。  
  3. **流量切换**：全局 **Anycast DNS** + **GSLB** 自动把用户请求路由到健康的 Region。  
  4. **失效恢复**：故障恢复期间，写入仍在剩余 Region 完成，故障结束后使用 **双写冲突解决**（基于时间戳）把缺失的数据回补。  

---

## ## 心得与反思  

### 1️⃣ 本题最难的设计决策  
| 决策 | 思考过程 |
|------|----------|
| **消息顺序与一致性模型** | 初始想把所有聊天都放在同一个 Kafka 分区来保证全局顺序，后发现吞吐受单分区限制（≈5k QPS）根本无法满足 150k QPS。于是转向「**频道内部顺序**」+ 「**最终一致**」模型：每个频道一个分区，Cassandra 按 `message_id` 排序。这样既满足业务（用户只在同频道关心顺序），又保留了系统的水平扩展能力。 |
| **语音低延迟实现** | 先考虑传统的 **RTMP/RTSP**，但这些基于 TCP，延迟大；后研究 **WebRTC+SFU**，发现需要自行搭建 **Media Server**（如 Mediasoup）并处理 NAT/防火墙穿透。最终决定采用 **QUIC** + **Opus** 编码，利用 **边缘节点** 部署 Media Node，确保 100 ms 以内的端到端时延。此决策涉及网络协议、编解码、部署拓扑的综合权衡。 |

### 2️⃣ 新手最容易犯的错误（至少两条）  
1. **一次性把所有功能全部画在同一个单体里**  
   - **后果**：代码耦合、部署困难、单点故障、扩容受限。  
   - **建议**：先实现最小可用的「文字聊天 + 鉴权」单体，跑通核心业务后再逐步拆分为微服务、加入消息队列、缓存等。  

2. **忽视消息顺序和幂等性**  
   - **后果**：用户会看到乱序或重复消息，体验极差；在高并发下容易出现「写入冲突」导致数据不一致。  
   - **建议**：在设计时就决定使用 **唯一消息 ID**、**Kafka 分区**、**Cassandra 幂等写入**（`INSERT IF NOT EXISTS`），并在消费者侧做好 **去重**。  

### 3️⃣ 学习建议和可延伸的方向  
- **系统设计基础**：阅读《Designing Data‑Intensive Applications》《Scalable Web Architecture & Distributed Systems》。  
- **深入消息系统**：掌握 **Kafka**、**RabbitMQ**、**Pulsar** 的内部机制、分区与复制原理。  
- **数据库进阶**：了解 **Cassandra**、**ScyllaDB** 的内部数据模型、压缩、Compaction；学习 **Elasticsearch** 的倒排索引与分片调优。  
- **实时媒体**：研究 **WebRTC**、**SFU vs MCU**，实践搭建 **Mediasoup** 或 **Janus**。  
- **云原生实践**：Kubernetes、Istio、Prometheus/Grafana、CI/CD（Argo CD）以及 **Chaos Engineering**（故障注入）提升系统韧性。  
- **面试实战**：每次练习都先写 **需求拆解 → 规模估算 → 高层图 → 关键组件**，并准备 **2–3 条常见追问** 的答案，形成自己的「思考框架」。  

> **温馨提示**：系统设计面试更看重 **思考过程** 与 **权衡取舍**，而不是记住某一套「固定答案」。把每一步的「为什么」说清楚，面试官就会感受到你对分布式系统的深刻理解。祝你面试顺利，早日成为可靠的后端工程师！ 🚀  
