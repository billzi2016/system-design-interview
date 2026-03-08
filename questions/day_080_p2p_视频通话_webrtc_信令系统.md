# 第 80 天：设计 P2P 视频通话（WebRTC 信令系统）

> 生成日期：2026-03-07

---

## 题目背景  
P2P 视频通话系统基于 WebRTC 实现音视频流的端到端传输，**信令服务器**负责用户匹配、会话建立、网络穿透等控制消息的转发。该系统用于在浏览器或移动端快速发起一对一/多人实时视频通话。

## 面试场景设定  
> **面试官**：  
> “假设我们要为一家社交应用构建一个全新的 WebRTC 信令系统，使用户能够在网页和 App 上随时发起视频通话。请你从零开始设计该系统的整体架构，重点说明核心功能、容量估算以及关键的技术难点。”

## 功能性需求  

| 编号 | 功能描述 |
|------|----------|
| 1 | **用户登录 & 会话身份校验**：使用 OAuth/JWT 完成鉴权，获取唯一的 `user_id` 与 `session_token`。 |
| 2 | **呼叫发起 / 接收**：用户可以发起单人或多人通话，系统需要把 `offer`、`answer`、ICE candidate 等信令消息实时转发给目标端。 |
| 3 | **在线状态与可达性检测**：维护用户在线/离线状态，支持 NAT/防火墙穿透（STUN/TURN）协商。 |
| 4 | **通话控制**：支持挂断、静音、切换摄像头、添加/移除参与者等控制指令。 |
| 5 | **通话历史 & 元数据持久化**：记录通话开始结束时间、参与者列表、时长、是否成功等，用于统计与审计。 |
| 6 | **安全与权限**：所有信令必须加密传输（TLS），并校验消息的发送者是否有权向目标发送信令。 |

## 非功能性需求  

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **DAU（日活跃用户）** | 2,000,000 人 | 假设高峰期有 15% 同时在线并可能发起通话。 |
| **并发通话数** | 150,000 场 | 估算 30% 在线用户处于通话中（包括单人、多人）。 |
| **信令 QPS** | 30,000 QPS 峰值 | 每场通话在建立阶段平均产生 200 条信令（offer/answer/ICE），加上心跳、控制指令等。 |
| **端到端信令延迟** | ≤ 150 ms（99.9%） | 影响用户感知的通话建立速度。 |
| **系统可用性** | 99.95%（月度累计不可用时间 ≤ 3.6 h） | 业务对实时通信要求高。 |
| **存储容量** | 约 10 TB/年 | 记录通话元数据、日志、审计信息（约 200 KB/通话）。 |

## 系统边界  

**本题需要实现/考虑的范围**  
- 信令服务器的设计（API、协议、负载均衡、水平扩展、容错）。  
- 用户鉴权、在线状态管理、信令转发、通话元数据持久化。  
- 与 STUN/TURN 服务器的交互（仅接口层面，不要求实现 TURN 本身）。  

**不在本题范围**  
- 音视频媒体流的编解码、传输、质量控制（交给 WebRTC 浏览器实现）。  
- TURN 服务器的部署与容量规划。  
- 客户端 UI、SDK 细节实现。  
- 计费、广告、第三方社交关系图等业务层面功能。  

## 提示与追问  

1. **扩展性**：如果要支持 **千人大会议**，信令层需要做哪些改动？如何控制信令风暴？  
2. **容错**：在信令节点失效或网络分区时，如何保证已经建立的通话不受影响？会采用什么一致性模型？  
3. **安全**：除了 TLS，你会在信令层再加入哪些安全机制（如消息签名、重放攻击防护）？如何在高并发下保持低延迟？  

---

# 题解

# 方案解答

> **温馨提示**：本答案面向 **零经验的系统设计新人**，所以每一步都会解释「**为什么这么做**」以及「**不这么做会有什么后果**」。先从最小可用系统（MVP）出发，逐层添加 **高可用、扩展性、可靠性** 的能力，帮助你在面试中从 **思路 → 细节 → 风险** 完整展示自己的设计能力。

---

## ## 解题思路总览

| 步骤 | 目标 | 关键输出 |
|------|------|----------|
| 1️⃣ | **把需求翻译成技术指标**（并发、QPS、时延、可用性） | 需求拆解、容量估算 |
| 2️⃣ | **画出最小可用系统（MVP）** | 单机信令服务 + DB + 负载均衡 |
| 3️⃣ | **逐步演进为分布式高可用架构** | 多机信令层、服务发现、容错、水平扩展 |
| 4️⃣ | **落地到数据库模型 & API** | 表结构、REST/WebSocket 接口、消息格式 |
| 5️⃣ | **细化每个组件的实现细节** | 认证、在线状态、消息路由、持久化、监控 |
| 6️⃣ | **讨论扩展、容错、安全** | 千人会议、分区、TLS+签名、防重放 |
| 7️⃣ | **准备面试追问** | 关键点的补充说明 |
| 8️⃣ | **总结经验教训** | 难点、常见错误、学习建议 |

> **核心思路**：先让系统「能跑」——单机、同步、简单；再让系统「跑得稳」——容错、监控、降级；最后让系统「跑得快」——水平扩展、流量控制、异步化。

---

## ## 第一步：理解需求与规模估算

### 1. 功能性需求要点

| 编号 | 关键点 | 关联的技术点 |
|------|--------|--------------|
| 1 | 登录/鉴权（OAuth + JWT） | 身份校验、统一入口、无状态 token |
| 2 | 呼叫发起/接收（offer/answer/ICE） | 实时双向消息、WebSocket / SSE |
| 3 | 在线状态 & NAT 穿透 | 心跳、Presence、STUN/TURN 协商 |
| 4 | 通话控制（挂断、静音、加人） | 业务指令、广播/单播 |
| 5 | 通话历史持久化 | 数据库写入、归档 |
| 6 | 安全（TLS、权限校验） | 端到端加密、消息签名 |

### 2. 非功能性需求转化为数值指标

| 指标 | 目标值 | 计算方式/来源 |
|------|--------|----------------|
| **DAU** | 2,000,000 | 已给 |
| **高峰并发在线** | 15% * 2,000,000 = **300,000** | 假设 15% 同时在线 |
| **并发通话** | 30% * 300,000 ≈ **90,000** 场（保守 150,000） | 题目给 150k，取上限 |
| **信令 QPS** | 30,000 QPS 峰值 | 150k 场 × 200 条 / 10s ≈ 30k |
| **单条信令大小** | 1 KB 左右 | JSON/WebSocket 消息 |
| **带宽需求** | 30,000 QPS × 1 KB ≈ **30 MB/s** ≈ 240 Mbps | 只算信令，媒体流不计 |
| **存储** | 10 TB/年 ≈ 200 KB/通话 × 150k 场 × 365 ≈ 10.9 TB | 与需求匹配 |
| **时延** | ≤ 150 ms（99.9%） | 对信令路由路径的要求 |
| **可用性** | 99.95%（≈ 3.6 h/月） | 故障恢复时间 ≤ 5 min，单点失效要规避 |

### 3. 初步容量估算

| 资源 | 估算公式 | 结果（峰值） |
|------|----------|--------------|
| **信令服务器实例** | QPS / 每实例最大 QPS（10k） | 30,000 / 10,000 ≈ **3 台**（预留 2 倍冗余 → 6 台） |
| **连接数** | 在线用户 * 每用户平均连接数（1） | 300,000 连接 |
| **WebSocket 连接** | 每台服务器承载连接数 = 300k / 6 ≈ **50k** | 常规服务器可支持 50k TCP 连接（调大 `ulimit`） |
| **数据库写入** | 通话元数据 150k / 天 ≈ 1.74 k / 秒 | MySQL / PostgreSQL 主从足够 |
| **缓存（在线状态）** | 在线用户 * 状态大小（≈ 100B） = 30 MB | Redis 集群 1‑2 GB 足够 |

> **如果直接跳到 10 台机器**，会浪费资源且增加运维复杂度；如果只部署 1‑2 台则会出现 **CPU/网络瓶颈**、**单点故障**，无法满足可用性要求。上述估算帮助我们在 **“最小可用系统”** 与 **“大规模生产系统”** 之间找到平衡点。

---

## ## 第二步：高层架构设计

### 1. MVP（最小可用系统）

```
┌─────────────┐      ┌─────────────┐
│   客户端①   │←WebSocket→│   信令服务   │
└─────────────┘      └─────────────┘
        ▲                     │
        │（REST 登录）        │
        ▼                     ▼
┌─────────────┐      ┌─────────────┐
│   客户端②   │←WebSocket→│   信令服务   │
└─────────────┘      └─────────────┘
```

- **单机**（或最小 2 台）部署信令服务，使用 **WebSocket** 双向实时通道。
- **REST API** 完成登录、获取 JWT。
- **Redis**（单实例）缓存在线状态。
- **MySQL** 持久化通话历史。

> **优点**：实现快、概念清晰、可演示。  
> **缺点**：**单点故障**、**水平扩展受限**、**连接数上限**。

### 2. 逐步演进的生产级架构

```
                           +-------------------+
                           |   API Gateway     |
                           +-------------------+
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
+-----------------+        +-----------------+        +-----------------+
|  Load Balancer  |        |  Load Balancer  |        |  Load Balancer  |
+-----------------+        +-----------------+        +-----------------+
        │                        │                        │
   ┌────┴────┐              ┌────┴────┐              ┌────┴────┐
   │ Signal  │  …… (N)      │ Signal  │  …… (N)      │ Signal  │
   │ Server  │              │ Server  │              │ Server  │
   └────┬────┘              └────┬────┘              └────┬────┘
        │                        │                        │
   ┌────▼────┐              ┌────▼────┐              ┌────▼────┐
   │  Redis  │  (Cluster)   │  Redis  │  (Cluster)   │  Redis  │
   │  Cache  │              │  Cache  │              │  Cache  │
   └────┬────┘              └────┬────┘              └────┬────┘
        │                        │                        │
   ┌────▼────┐              ┌────▼────┐              ┌────▼────┐
   │ MySQL   │  (Master/  │ MySQL   │  (Replica) │ MySQL   │
   │  Master │   Slave)   │  Slave  │              │  Slave  │
   └─────────┘              └─────────┘              └─────────┘
```

#### 关键组件说明

| 组件 | 作用 | 关键技术/实现 |
|------|------|---------------|
| **API Gateway** | 统一入口、统一鉴权、流量控制、TLS 终止 | Kong / Nginx + Lua / Envoy |
| **Load Balancer** (L4) | 将 TCP/WebSocket 连接均匀分配到 Signal Server | LVS / Nginx TCP、Consistent Hash（用户 ID） |
| **Signal Server** | 业务核心：WebSocket 连接、消息路由、心跳、会话管理 | Go/Node.js/Java，使用 **actor model**（如 Akka）提升并发 |
| **Redis Cluster** | 在线状态、短期缓存、分布式锁、消息幂等标记 | `SETEX`, `PUB/SUB`（可选） |
| **MySQL 主从** | 通话元数据持久化、审计查询 | InnoDB、分区表、读写分离 |
| **STUN/TURN** | NAT 穿透协商（只提供接口） | 公有云 Coturn / 自建 |
| **监控报警** | Prometheus + Grafana、日志（ELK） | QPS、连接数、延迟、错误率 |
| **服务发现** | Signal Server 动态注册/下线，供 LB 使用 | Consul / etcd |

> **为什么要加这些层？**  
> - **API Gateway**：统一鉴权、限流，防止恶意流量直接冲击 Signal Server。  
> - **Load Balancer**：WebSocket 长连接需要 **L4** 负载，避免 HTTP 层的握手开销。  
> - **Redis Cluster**：单机缓存难以支撑 300k 在线用户，且需要 **高可用**。  
> - **MySQL 主从**：写入量不高，但查询（审计、统计）频繁，需要读写分离提升性能。  
> - **监控**：实时发现 “时延 > 150 ms” 或 “连接数爆炸”，快速定位故障。  

---

## ## 第三步：数据库设计

### 1. 业务实体概览

| 实体 | 主键 | 关键属性 | 备注 |
|------|------|----------|------|
| **User** | `user_id` (bigint) | `username`, `email`, `created_at` | 只存基础信息，鉴权交给统一 OAuth 服务 |
| **Session** | `session_token` (uuid) | `user_id`, `issued_at`, `expires_at` | JWT 解析后可不落库，仅用于审计 |
| **Call** | `call_id` (uuid) | `type` (single/multi), `start_time`, `end_time`, `status` | 记录一次完整通话 |
| **CallParticipant** | `call_id` + `user_id` (复合键) | `joined_at`, `left_at`, `role` (host/guest) | 多人会议关联表 |
| **SignalLog** (归档) | `log_id` (bigint auto) | `call_id`, `sender_id`, `receiver_id`, `msg_type`, `payload`, `ts` | 供审计、排障使用，周期归档到冷存储 |
| **Presence** (缓存) | `user_id` | `online` (bool), `node_id`, `last_heartbeat` | 存在 Redis，TTL 30s |

### 2. 表结构（MySQL 示例）

```sql
-- 通话表
CREATE TABLE `call` (
  `call_id`        CHAR(36)    NOT NULL PRIMARY KEY,
  `type`           ENUM('single','multi') NOT NULL,
  `host_user_id`   BIGINT NOT NULL,
  `start_time`     DATETIME(3) NOT NULL,
  `end_time`       DATETIME(3) NULL,
  `status`         ENUM('ongoing','ended','failed') NOT NULL,
  INDEX idx_start_time (start_time)
) ENGINE=InnoDB PARTITION BY RANGE (YEAR(start_time)) (
  PARTITION p2024 VALUES LESS THAN (2025),
  PARTITION p2025 VALUES LESS THAN (2026),
  PARTITION pmax  VALUES LESS THAN MAXVALUE
);

-- 参与者表
CREATE TABLE `call_participant` (
  `call_id`    CHAR(36)    NOT NULL,
  `user_id`    BIGINT      NOT NULL,
  `joined_at`  DATETIME(3) NOT NULL,
  `left_at`    DATETIME(3) NULL,
  `role`       ENUM('host','guest') NOT NULL,
  PRIMARY KEY (`call_id`,`user_id`),
  INDEX idx_user (user_id)
) ENGINE=InnoDB;

-- 信令日志（归档表，写入后使用分区或外部工具压缩）
CREATE TABLE `signal_log` (
  `log_id`      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `call_id`     CHAR(36)        NOT NULL,
  `sender_id`   BIGINT          NOT NULL,
  `receiver_id` BIGINT          NOT NULL,
  `msg_type`    VARCHAR(32)     NOT NULL,
  `payload`     JSON            NOT NULL,
  `ts`          TIMESTAMP(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  INDEX idx_call (call_id),
  INDEX idx_ts   (ts)
) ENGINE=InnoDB PARTITION BY HASH (YEAR(ts)) PARTITIONS 12;
```

### 3. 为什么使用这些设计？

- **UUID**（36 字符）作为 `call_id`：跨机器唯一，便于分布式写入，不依赖自增序列导致热点。
- **分区表**：通话数据随时间增长，分区可以快速删除旧数据（归档到冷存储）并提升查询性能。
- **`call_participant`** 采用 **复合主键**：保证同一次通话同用户只出现一次，避免重复记录。
- **`signal_log`** 采用 **JSON** 存储原始信令，便于以后回放调试；但生产环境可仅在异常时写入，以降低写入压力。
- **Presence 缓存** 放在 Redis：读写频繁、时效性强，使用 **TTL** 自动失效，避免显式下线导致“僵尸”状态。

---

## ## 第四步：核心 API 设计

> 为了兼顾 **实时性** 与 **可维护性**，我们把 **登录/鉴权** 走 **REST**，把 **信令** 走 **WebSocket**（或 **Bidirectional gRPC**），两套协议各司其职。

### 1. REST 接口（HTTPS + JWT）

| 方法 | 路径 | 请求体 | 响应体 | 说明 |
|------|------|--------|--------|------|
| POST | `/api/v1/auth/login` | `{ "provider":"google","access_token":"..." }` | `{ "access_token":"jwt", "refresh_token":"...", "expires_in":3600 }` | OAuth → JWT |
| POST | `/api/v1/auth/refresh` | `{ "refresh_token":"..." }` | `{ "access_token":"jwt", "expires_in":3600 }` | 刷新 token |
| GET  | `/api/v1/user/me` | Header: `Authorization: Bearer <jwt>` | `{ "user_id":12345, "username":"alice" }` | 查询自身信息 |
| GET  | `/api/v1/call/:call_id/summary` | Header: JWT | `{ "call_id":"...", "type":"multi", "participants":[...], "duration":123 }` | 事后查询通话记录 |

**安全点**：所有 REST 接口强制 **HTTPS**，JWT 中携带 `exp`、`iss`、`sub`，服务端验证签名（使用 **RS256**）并检查 `aud` 与业务系统匹配。

### 2. WebSocket 消息协议（JSON）

> **约定**：所有消息都有统一的 **`type`** 字段，`payload` 为业务内容。所有消息均 **加密（TLS）**，可选 **消息签名**（后文安全章节）。

```json
// 客户端 -> 服务器：鉴权（首次建立 WebSocket 后必须发送）
{
  "type": "auth",
  "payload": {
    "access_token": "jwt"
  }
}
```

```json
// 服务器 -> 客户端：鉴权结果
{
  "type": "auth_result",
  "payload": {
    "code": 0,          // 0 成功，非 0 失败
    "user_id": 12345,
    "msg": "ok"
  }
}
```

```json
// 呼叫发起（单人或多人）
{
  "type": "call_invite",
  "payload": {
    "call_id": "uuid",
    "target_user_ids": [23456, 34567],
    "sdp_offer": "...",          // base64 编码的 SDP
    "media_capabilities": { ... }
  }
}
```

```json
// 目标端收到邀请
{
  "type": "call_invite",
  "payload": { ... }   // 与上面相同
}
```

```json
// ICE Candidate 发送
{
  "type": "ice_candidate",
  "payload": {
    "call_id": "uuid",
    "target_user_id": 23456,
    "candidate": { "candidate":"...", "sdpMid":"...", "sdpMLineIndex":0 }
  }
}
```

```json
// 控制指令（挂断、静音、加人等）
{
  "type": "call_control",
  "payload": {
    "call_id": "uuid",
    "action": "hangup" | "mute" | "add_participant",
    "params": { ... }
  }
}
```

```json
// 心跳（客户端每 15s 发送一次）
{
  "type": "heartbeat",
  "payload": {}
}
```

#### 响应规范（统一错误码）

| code | 含义 | 说明 |
|------|------|------|
| 0    | 成功 | 正常业务返回 |
| 1001 | 鉴权失败 | JWT 无效或过期 |
| 2001 | 参数错误 | 必填字段缺失、格式错误 |
| 3001 | 调度错误 | 目标用户不在线、已离线 |
| 4001 | 业务冲突 | 已有同 ID 的通话正在进行 |
| 5000 | 服务器内部错误 | 未捕获异常 |

### 3. 为什么分离 REST 与 WebSocket？

- **REST** 更适合一次性请求/响应（登录、查询历史），易于使用 CDN、缓存、网关等已有设施。
- **WebSocket** 需要 **长连接**、**低时延**、**双向推送**，在业务层面可以直接把消息路由到对应的 **socket**，不必每次都走 HTTP 轮询。
- 分离后 **安全审计** 更清晰：REST 日志集中在 API Gateway，WebSocket 日志在 Signal Server。

---

## ## 第五步：详细组件设计

下面按照 **数据流**（登录 → 建立连接 → 发起呼叫 → 结束）逐层展开关键实现细节。

### 1. 鉴权与会话管理

1. **OAuth → JWT**  
   - 客户端向统一 **Auth Service**（可以是社交平台或自建）获取 `access_token`（短效）。  
   - 后端 **Auth Service** 验证后返回 **JWT**（签名使用 RSA 私钥）。  
2. **WebSocket 鉴权**  
   - 客户端连接后，第一条必须是 `auth` 消息。  
   - 服务端验证 JWT（签名、过期、`aud`、`iss`）。验证通过后把 `user_id` 绑定到当前 **socket**（存入本地 map）并写入 **Redis**：`SETEX user:{user_id} node:{node_id} 30`。  
   - 若验证失败，直接 **关闭连接** 并返回错误码。  

> **不做鉴权**：任何人都能直接连接并发送信令，导致**安全风险**和**资源被滥用**。  

### 2. 在线状态（Presence）管理

| 步骤 | 说明 |
|------|------|
| **心跳** | 客户端每 15 s 发送 `heartbeat`，服务端刷新 Redis TTL（30 s）并更新 `last_heartbeat`。 |
| **下线** | 当连接关闭（网络异常或主动关闭），服务端立即 `DEL user:{user_id}`。 |
| **查询** | 业务（如呼叫发起）先查询 Redis `GET user:{target_id}` 判断是否在线。若返回 `node_id`，则直接把消息路由到对应 Signal Server。 |
| **容错** | 若 Redis 失效，Signal Server 采用 **本地 fallback**（维护 `in-memory` 用户→node 映射），但只能保证 **短时间**（几秒）内不丢失。 |

### 3. 消息路由与转发

#### 3.1 单机内部（同节点）  
- 使用 **ConcurrentHashMap<user_id, WebSocketSession>** 存储本机所有在线用户的连接对象。  
- 收到 `call_invite`，遍历 `target_user_ids`：  
  - 若 `target_user` 在本机 map 中，直接 **push** 消息。  
  - 若不在本机，走 **跨节点路由**（下节）。

#### 3.2 跨节点路由（分布式）

1. **节点注册**：每个 Signal Server 启动时向 **Consul/etcd** 注册 `node_id`、IP、Port。  
2. **消息中转**：  
   - **方式 A（推荐）**：使用 **NATS / Kafka** 主题 `signal.{target_user_id}`，所有节点 **订阅** 自己负责的用户（基于一致性哈希分配）。  
   - **方式 B**：直接 **RPC**（gRPC）调用目标节点的内部推送接口。  
3. **幂等**：在消息 payload 中加入 **`msg_id`（UUID）**，接收端用 Redis `SETNX` 防止重复消费。  

> **不使用跨节点中转**：会导致 **消息丢失**（发送到错误机器）或 **网络分区时全局不可达**。  

### 4. 呼叫建立流程（单人示例）

```
1. A 登录 → 获得 JWT → 建立 WebSocket 连接 → 鉴权成功
2. B 同上，保持在线状态
3. A 发送 call_invite（包含 SDP offer）给服务器
4. 服务器查询 Redis → B 在线且在节点 N2
5. 服务器通过 NATS 将消息发送到 N2
6. N2 收到后推送给 B 的 WebSocket
7. B 返回 call_answer（SDP answer） → 服务器同样路由回 A
8. 双方开始 ICE candidate 互相发送（同路由方式）
9. 媒体流直接走 STUN/TURN → 与信令层无关
10. 通话结束后 A/B 任意一方发送 call_control(hangup)
11. 服务器更新 `call`、`call_participant` 表，写入 MySQL
12. 服务器清理该 `call_id` 在 Redis 中的临时状态（如房间锁）
```

### 5. 多人会议（核心差异）

- **房间概念**：`call_id` 即为会议房间 ID。所有参与者加入同一房间。  
- **广播**：当任意用户发送信令（ICE、控制），服务器 **广播** 给房间内除发送者外的全部用户。  
- **规模控制**：为防止 **信令风暴**（每个用户每秒发送大量 ICE），在 **Signal Server** 做 **速率限制**（如 200 msg/s/用户）并 **聚合**：把同一时间段的 ICE candidate 合并成一个数组后一次性发送。  

### 6. 持久化与日志

| 场景 | 操作 | 实现细节 |
|------|------|----------|
| 通话开始 | `INSERT` `call` + `call_participant` | 使用 **事务** 保证原子性 |
| 每条信令（可选） | `INSERT` `signal_log` | 异步写入（Kafka → Flink → HDFS）降低主库压力 |
| 通话结束 | `UPDATE` `call` `end_time`、`status` | 同步写，确保审计完整 |
| 归档 | 每月/每季 **导出** 到对象存储（OSS/MinIO） | 使用 **MySQL Partition** + **pt-archiver** |

### 7. 监控 & 报警

- **Prometheus** 指标（Signal Server）  
  - `ws_active_connections`、`ws_message_rate`、`signal_latency_ms`、`error_rate`。  
- **Grafana** Dashboard：实时监控 QPS、在线用户、节点 CPU/内存。  
- **报警**（Alertmanager）  
  - `signal_latency_ms > 150ms for 2m` → 通知 SRE。  
  - `ws_active_connections > 45k per node` → 自动扩容。  

---

## ## 第六步：扩展性与高可用设计

### 1. 支持千人大会议的信令层改造

| 改动点 | 目的 | 具体实现 |
|--------|------|----------|
| **分层房间** | 将会议拆分为 **子房间**（SFU）或 **层级广播**，降低单节点广播量 | 每 200 人一个子房间，子房间之间只转发必要的控制消息（如 mute） |
| **信令聚合** | 把大量 ICE candidate 合并，减少消息条数 | 服务器内部维护 `ice_buffer[user]`，每 50ms 批量发送 |
| **限流 & 速率限制** | 防止单用户或恶意客户端把信令压垮服务器 | Token Bucket（200 msg/s）+ 动态调节阈值 |
| **基于消息队列的异步转发** | 将实时转发拆分为 **生产者 → 消费者**，平滑突发流量 | NATS Streaming / Kafka Topic `call.{call_id}`，消费者负责广播 |
| **热点分片** | 将同一个大型会议的信令分配到 **多台 Signal Server**（基于 `call_id` 哈希） | Consistent Hash Ring，确保同一会议的消息始终走同一组节点，降低跨节点网络延迟 |

> **如果不做这些**：千人会议的 **全员广播**（O(N²)）会导致 **网络拥塞**、**CPU 飙升**，瞬间把信令层压垮。

### 2. 容错与一致性

| 场景 | 失效点 | 影响 | 解决方案 |
|------|--------|------|----------|
| **Signal Server 单点失效** | 某节点宕机 | 该节点上的用户掉线、信令不可达 | **无状态** 设计 + **会话恢复**：客户端检测 WebSocket 断开后自动重连，重新鉴权，服务器从 Redis 拉取 `presence`，恢复会话 |
| **Redis 故障** | 缓存不可用 | 在线状态失效、消息幂等失效 | **Redis Cluster** + **哨兵**，并在代码中加入 **fallback to DB**（短时查询 MySQL） |
| **网络分区**（节点之间失联） | 消息路由受阻 | 部分用户之间信令失联，但已有通话仍可继续（媒体流已建立） | **CAP**：选取 **可用性 + 分区容忍**，保证已建立的通话不受影响。消息在分区恢复后使用 **重试 + 幂等** 机制补发 |
| **MySQL 主库宕机** | 写入不可用 | 新通话无法落库，审计缺失 | **主从双写**（主库故障自动切换到备库）+ **写入队列**（Kafka）缓冲写入，待主库恢复后批量落库 |

**一致性模型**  
- **在线状态**：**最终一致性**（Redis TTL + 心跳），短暂失效可容忍。  
- **通话元数据**：**强一致性**（事务写入 MySQL），因为审计必须可靠。  
- **信令**：**弱一致性**（尽力而为），只要 99.9% 的消息到达即可，采用 **幂等 ID + 重试**。

### 3. 安全机制（TLS 之外）

| 机制 | 目的 | 实现方式 |
|------|------|----------|
| **消息签名** | 防止被篡改、伪造 | 使用 **HMAC‑SHA256**，密钥为每个用户的 **session secret**（在 JWT 中携带），服务器在收到消息后校验 `signature` 字段 |
| **防重放** | 防止旧的信令被恶意重放 | 每条消息携带 **timestamp**（毫秒）和 **nonce**（一次性随机数），服务器检查时间窗口（≤ 5 s）并使用 Redis `SETNX nonce` 防重放 |
| **权限校验** | 只能向已加入通话的成员发送信令 | 在每条信令处理前查询 `call_participant`，确认 `sender_id` 与 `call_id` 的对应关系 |
| **速率限制** | 防止 DoS | 对每个 `user_id` 使用 **Token Bucket**（200 req/s）和 **IP 限流** |
| **安全审计日志** | 事后溯源 | 所有鉴权、控制指令、错误均写入审计日志（ELK），并加密存储（AES‑256） |

> **TLS** 已经保障了 **传输层** 的机密性和完整性，但 **业务层** 仍可能被 **内部恶意用户** 利用伪造消息。加入 **HMAC** 能在 **高并发** 场景保持 **低开销**（仅一次哈希运算）。

### 4. 自动化运维

| 工具 | 用途 |
|------|------|
| **Kubernetes** | 容器化部署 Signal Server、Redis、MySQL（StatefulSet），实现弹性伸缩、滚动升级 |
| **Helm Chart** | 统一管理服务配置（TLS 证书、环境变量） |
| **Istio/Linkerd** | 服务网格，提供 **mTLS**、流量监控、故障注入（演练） |
| **Chaos Monkey** | 演练节点失效、网络分区，验证容错设计 |
| **CI/CD (GitHub Actions)** | 自动化单元、集成测试，部署到 k8s 集群 |

---

## ## 第七步：常见面试追问与回答

下面列出面试官常见的追问，并提供 **思路** 与 **简要答案**，帮助你在现场快速组织语言。

| 追问 | 关键点 | 推荐答案要点 |
|------|--------|--------------|
| **Q1：千人会议的信令会不会形成风暴？怎么限制？** | 信令聚合、分层广播、速率限制 | 1）把同一时间段的 ICE candidate 合并；2）把 1000 人分成 5‑10 个子房间，每个子房间只向本子房间广播；3）使用 Token‑Bucket 对每个用户限流（如 200 条/秒），超限直接丢弃或返回错误。 |
| **Q2：如果信令服务器挂了，已建立的通话会怎样？** | 媒体流已走 STUN/TURN，信令只负责控制 | 已建立的媒体流不受影响，通话仍能进行；但后续的控制指令（挂断、静音）会失效。客户端会检测 WebSocket 断开，自动重连并恢复会话（从 Redis 拉取通话状态）。 |
| **Q3：为什么不直接使用 HTTP 长轮询或 SSE？** | 实时性 & 双向推送 | WebSocket 在 **单连接** 上实现 **全双工**，时延更低（<10 ms），且省去 HTTP Header 开销。SSE 只能服务器 → 客户端单向，且在移动端不稳定。 |
| **Q4：如何保证消息的幂等性？** | msg_id + 去重表 | 每条信令带唯一 `msg_id`（UUID），Signal Server 在 Redis `SETNX msg_id 1 EX 60`，如果已存在直接丢弃，保证一次消费。 |
| **Q5：选用哪种数据库？为什么不使用 NoSQL？** | 事务 & 关系查询 | 通话历史需要 **强一致**、**事务**（一次插入 `call` + `participants`），以及 **复杂查询**（统计、分页），关系型数据库更合适。NoSQL 可用于缓存（Redis）或日志归档（Cassandra），但不适合作为主库。 |
| **Q6：如何做流量的弹性伸缩？** | 监控阈值 + 自动扩容 | 通过 Prometheus 监控 `ws_message_rate`、CPU，使用 **Horizontal Pod Autoscaler**（k8s）根据 QPS 或 CPU 自动扩容 Signal Server；Redis 使用 **Cluster** 自动分片；MySQL 采用 **读写分离** + **ProxySQL** 做动态路由。 |
| **Q7：如果用户在不同网络（Wi‑Fi、4G）切换，信令会不会中断？** | 重连 & 会话恢复 | 客户端检测网络变化后 **重新建立 WebSocket**，带上同一 JWT，服务器通过 Redis `presence` 恢复 `user_id → node_id` 映射，业务层继续使用同一 `call_id`。 |
| **Q8：如何防止恶意用户发送大量无效信令耗尽资源？** | 鉴权、速率限制、黑名单 | 1）所有请求必须携带有效 JWT；2）对每个 `user_id` 使用 Token‑Bucket 限流；3）对异常行为（如连续 5 次 4001 错误）加入 **Redis 黑名单**，短时间内拒绝。 |
| **Q9：为什么不把信令直接写入 Kafka 再由消费者发送？** | 可靠性 vs 时延 | Kafka 能保证持久化，但写入/消费的 **额外延迟**（≈10‑20 ms）可能超出 150 ms 端到端要求；在实时性极高的呼叫建立阶段，**同步推送**更合适；但在千人会议的 **广播** 场景，可使用 **Kafka + consumer** 进行批量转发，权衡时延与可扩展性。 |
| **Q10：如果要支持 Web & 原生 App 双端，需要考虑哪些差异？** | 协议兼容、网络环境 | 1）Web 使用 **WebSocket**，App 可使用 **gRPC‑Web** 或 **WebSocket**；2）移动端网络不稳定，需要更强的 **重连/心跳** 机制；3）App 可能需要 **二进制协议**（Protobuf）降低带宽。 |


---

## ## 心得与反思

### 1. 本题最难的 1‑2 个设计决策及思考过程

| 决策 | 难点 | 思考路径 |
|------|------|----------|
| **① 信令层的实时性 vs 可扩展性** | 需要在 **低时延（≤150 ms）** 与 **水平扩展（千人会议）** 之间取得平衡。 | - 先确定 **WebSocket** 为主路径（低时延）。<br>- 评估 **全局广播** O(N²) 的瓶颈，决定 **分层子房间 + 速率限制**。<br>- 引入 **消息聚合** 与 **NATS/Kafka** 的 **异步转发**，在千人场景下把时延控制在 100 ms 以内。 |
| **② 容错策略（单点失效 vs 会话保持）** | 信令服务器宕机不应导致已建立的通话中断，但用户仍需恢复控制指令。 | - 采用 **无状态** 设计：所有会话信息保存在 **Redis**（presence、房间映射）。<br>- 客户端检测 **WebSocket 断开** 后自动 **重连**，服务器从 Redis 拉取状态完成恢复。<br>- 选取 **最终一致性** 对在线状态，**强一致性** 对通话元数据。|

### 2. 新手最容易犯的错误（至少 2 条）

| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **只考虑单机实现**（忽视水平扩展） | 当 QPS 达到 30k，单机 CPU、网络、连接数会迅速成为瓶颈，系统不可用。 | 从 **MVP** 起步后，立刻规划 **负载均衡 + 多实例**，并使用 **无状态** 设计，方便水平扩展。 |
| **把所有信令都持久化到关系库** | 每条 ICE/offer/answer 都写入 MySQL，导致写入 TPS 远超 DB 能力，甚至出现锁争用。 | 只持久化 **关键业务事件**（通话开始/结束、控制指令），**信令日志**可采用 **异步队列 + 冷存储**，或只在异常时写入。 |
| **未做消息幂等处理** | 客户端网络抖动导致重复发送，接收端会产生重复 ICE，破坏连接。 | 为每条消息生成 **全局唯一 msg_id**，在 Redis 进行 **一次性消费**（SETNX）或在业务层判断已处理。 |
| **忽视安全细节，仅靠 TLS** | 内部恶意用户可以伪造 `call_control`，导致会议被随意挂断。 | 在业务层加入 **HMAC 签名**、**时间戳+nonce 防重放**、**权限校验**（只能对已加入的房间发送）等。 |

### 3. 学习建议和可延伸的方向

| 方向 | 推荐学习资源 | 关键点 |
|------|--------------|--------|
| **WebSocket 与实时协议** | 《High Performance Browser Networking》章节、`socket.io` 源码 | 握手、心跳、负载均衡、水平扩展 |
| **分布式缓存（Redis）** | 《Redis 实战》、Redis 官方文档的 Cluster & Sentinel | 高可用、分片、TTL、去重 |
| **消息队列（NATS / Kafka）** | 《Designing Data-Intensive Applications》、官方文档 | 发布/订阅、背压、幂等 |
| **容错一致性模型** | 《CAP Theorem》、《Distributed Systems: Concepts and Design》 | 强/弱一致、最终一致、分区容忍 |
| **监控 & 可观测性** | Prometheus + Grafana 官方教程、OpenTelemetry | 指标、追踪、日志聚合 |
| **WebRTC 深入** | WebRTC 官方文档、Google `webrtc.org` 教程 | STUN/TURN 协商、ICE 过程、媒体流路由 |
| **Kubernetes & Service Mesh** | 《Kubernetes Patterns》、Istio 官方 docs | 自动扩容、滚动升级、mTLS、流量控制 |
| **安全** | OWASP Top 10、《Security Engineering》 | HMAC、JWT、Replay 防护、速率限制 |

> **实战建议**：先用 **Docker Compose** 搭建单机版 Signal Server + Redis + MySQL，跑 `wrk` 或 `autocannon` 验证 QPS 与时延；再迁移到 **K8s**，开启 **HPA**、**Redis Cluster**，逐步实现高可用。这样既能巩固理论，又能积累实战经验，面试时更有说服力。

---
