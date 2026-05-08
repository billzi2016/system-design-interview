# 第 18 天：设计 Spotify

> 生成日期：2026-05-08

---

## 题目背景
Spotify 是一家全球领先的音乐流媒体平台，提供海量歌曲、播客和个性化推荐。用户可以在线点播、离线下载、创建播放列表并与朋友共享音乐。

## 面试场景设定
> **面试官**：  
> “今天我们来聊一聊如何设计一个类似 Spotify 的音乐流媒体系统。请你从零开始，设计一个能够支撑全球数亿用户同时在线听歌的服务。首先，你会把系统拆分成哪些核心模块？接下来我们一起细化每个模块的实现细节。”

## 功能性需求
1. **音乐点播**：用户可以随时播放任意歌曲或播客，支持顺序播放、随机播放、单曲循环等模式。  
2. **离线下载**：付费用户可以将歌曲/播客下载到本地设备，后续无需网络即可离线播放。  
3. **个性化推荐**：基于用户的历史行为、收藏、社交关系，实时生成每日推荐、歌单和电台。  
4. **播放列表管理**：用户可以创建、编辑、删除播放列表，支持协作编辑（多人共同维护同一列表）。  
5. **社交分享**：用户能够将正在播放的歌曲或歌单分享至社交平台或发送给好友，好友可直接点击播放。  
6. **广告投放（免费用户）**：在免费用户播放时插入音频/视频广告，确保广告不影响用户体验。

## 非功能性需求
| 指标 | 估算值 | 说明 |
|------|--------|------|
| **日活跃用户 (DAU)** | 2.5 亿 | 假设覆盖全球主要市场 |
| **每用户平均并发流** | 0.02 条流/秒 | 1 分钟内发起一次播放请求 |
| **峰值 QPS (播放请求)** | 50 万 QPS | 2.5 亿 × 0.02 |
| **平均播放延迟** | ≤ 150 ms | 从用户点击播放到音频开始播放的时延 |
| **系统可用性** | 99.99%（每月约 4.3 分钟不可用） | 关键业务要求高可用 |
| **存储容量** | 约 300 PB | 估算 1 亿首歌曲 × 5 GB（平均码率+冗余） + 用户离线缓存 |

> **注**：以上数字为大致估算，实际设计时可根据业务模型进行细化。

## 系统边界
**本题范围内**（需要设计）  
- 音乐内容的存储、分发与缓存层（CDN、对象存储）  
- 播放请求的路由、鉴权、计费与限流  
- 推荐系统的核心数据流（离线特征计算、实时召回）  
- 播放列表与用户收藏的 CRUD 接口  
- 离线下载的加密、版权校验与失效管理  
- 广告插入的策略与计费模型  

**本题范围外**（不必详细设计）  
- 前端（移动端/网页） UI 细节  
- 版权谈判、音乐版权数据库的法律合规流程  
- 第三方社交平台的 OAuth 集成细节  
- 具体的机器学习模型实现（只需说明整体流程）  
- 运维监控告警系统的实现细节（只需提及需求）

## 提示与追问
1. **缓存策略**：  
   - “如果我们要在全球范围内部署 CDN，如何决定哪些歌曲放在边缘缓存，缓存失效策略如何设计？”  

2. **高并发流控**：  
   - “面对突发的流量峰值（如热门歌单上线），你会怎样在入口层进行限流与降级，保证核心播放服务不被压垮？”  

3. **离线下载的安全性**：  
   - “用户下载的音频文件需要防止非法分发，你会采用哪些加密或 DRM 方案，同时兼顾跨平台播放的兼容性？”  

---

# 题解

# 设计一个全球化的 Spotify 类音乐流媒体系统  
> **目标**：从最小可用系统（MVP）出发，逐步演进到满足 **亿级并发、秒级延迟、99.99% 可用** 的分布式架构。  
> **适用对象**：对系统设计完全没有经验的后端新人，所有概念、决策、可能的坑都会一步一步解释。

---  

## ## 解题思路总览  

1. **先把需求拆成“业务能力”**（点播、下载、推荐、播放列表、社交、广告）。  
2. **估算规模**（DAU、QPS、存储），把数字写下来，后面所有的容量、并发、扩容都基于它。  
3. **画出高层架构**：前端 → 网关 → 业务服务 → 存储/缓存 → 对象存储 → CDN。先只保留核心路径（点播），其余功能（推荐、广告）后期再挂。  
4. **逐层细化**：  
   - **网络层**（DNS、负载均衡、限流）  
   - **服务层**（鉴权、播放调度、计费）  
   - **数据层**（关系型、NoSQL、搜索、对象存储）  
   - **缓存层**（本地缓存、Redis、CDN）  
5. **把每个业务能力映射到具体的微服务**，并思考它们的 **接口（API）**、**数据模型**、**容错/扩容**。  
6. **针对非功能需求**（延迟、可用性、容量）逐项设计：  
   - 延迟 → **CDN + Edge Cache + 近端调度**  
   - 可用性 → **多活、跨地域、熔断、降级**  
   - 存储 → **对象存储 + 多副本 + 分层冷热**  
7. **最后准备面试常见追问的答案**，并写出自己的心得体会。  

下面按照 **从小到大、从概念到实现** 的顺序展开。  

---  

## ## 第一步：理解需求与规模估算  

### 1. 功能需求拆解  

| 编号 | 功能 | 对应业务能力 | 关键点 |
|------|------|--------------|--------|
| 1 | 音乐点播 | **实时流媒体** | 低延迟、支持播放模式、版权校验 |
| 2 | 离线下载 | **文件分发 + DRM** | 付费校验、加密、失效检测 |
| 3 | 个性化推荐 | **大数据 + 机器学习** | 实时召回、离线特征、冷启动 |
| 4 | 播放列表管理 | **CRUD + 协作** | 多用户编辑冲突、版本控制 |
| 5 | 社交分享 | **短链 + 统计** | 防刷、可追踪 |
| 6 | 广告投放 | **动态插入 + 计费** | 免费用户流控、广告位调度 |

> **新手提示**：先把“最核心、最必须先上线”的功能挑出来，通常是 **音乐点播 + 鉴权 + 基础播放列表**。其它功能可以后期通过 **事件驱动**、**异步任务** 挂钩实现。

### 2. 非功能需求量化  

| 指标 | 估算值 | 推导/备注 |
|------|--------|-----------|
| **DAU** | 250 M | 题目给定 |
| **每用户并发流** | 0.02 流/s | 1 分钟一次播放请求 |
| **峰值 QPS** | 500 k QPS | 250 M × 0.02 |
| **平均播放延迟** | ≤150 ms | 从点击→音频开始 |
| **可用性** | 99.99% | 每月 ≤4.3 min 故障 |
| **存储容量** | ~300 PB | 1 亿首 × 5 GB（含冗余） |
| **带宽需求** | 约 100 Tbps（假设 5 Mbps/流） | 500 k × 5 Mbps ≈ 2.5 Tbps 峰值（需要多地域分摊） |

> **思考**：如果我们直接把 300 PB 放在单个对象存储集群里，**网络瓶颈、单点故障、扩容成本** 都会失控。必须采用 **分层存储+多地域复制** 的方案。

---  

## ## 第二步：高层架构设计  

### 1. MVP（最小可用系统）  

```
[客户端] -> DNS -> [L4/7 LB] -> [API Gateway] -> 
   -> Auth Service
   -> Playback Service (点播调度)
   -> Metadata Service (歌曲信息、版权)
   -> Object Storage (S3/OSS) -> CDN Edge
```

- **只保留** 点播、鉴权、元数据查询。  
- 推荐、广告、下载等功能先不实现，只保留 **占位的 Event Bus**（后期可订阅）。  

### 2. 完整的可扩展架构  

```
                            +-------------------+
                            |   Global DNS/Anycast
                            +--------+----------+
                                     |
                     +-------------------------------+
                     |    Global L7 Load Balancer    |
                     +----------------+--------------+
                                      |
                +---------------------+---------------------+
                |                                           |
         +------+------+                              +-----+------+
         | API Gateway |                              |  Edge LB  |
         +------+------+\                             +-----+------+
                |        \_______________________________/   |
                |                                         |
   +------------+------------+          +-----------------+----------------+
   |                         |          |                                   |
+--+--+                 +----+----+ +---+----+                         +----+----+
| Auth|                 | Playback| | Recommend|                         |  Ads   |
|Srv  |                 | Srv     | | Srv      |                         | Srv    |
+-----+                 +----+----+ +----+-----+                         +-------+
   |                        |          |                                 |
   |   +--------------------+----------+----------------------+          |
   |   |  +-----------------+-------------------+      |   |          |
   |   |  |  Metadata Service (SQL/NoSQL)         |      |   |          |
   |   |  +-----------------+-------------------+      |   |          |
   |   |                                            |   |          |
   |   |   +----------------------+   +----------------------+    |
   |   |   |   Song Object Store  |   |   User Data Store    |    |
   |   |   |   (S3/OSS)           |   |   (RDS/NoSQL)        |    |
   |   |   +----------+-----------+   +----------+-----------+    |
   |   |              |                        |                |
   |   |   +----------v-----------+   +--------v--------+         |
   |   |   |   CDN Edge Cache     |   |   Redis Cache   |         |
   |   |   +----------------------+   +-----------------+         |
   +---+----------------------------------------------------------+

```

#### 关键组件解释  

| 组件 | 作用 | 关键技术选型（示例） | 为什么要这么选 |
|------|------|--------------------|----------------|
| **DNS/Anycast** | 将用户请求路由到最近的入口节点 | Cloudflare DNS、阿里云 DNS | **全局负载均衡**，降低 DNS 查询 RTT |
| **Global L7 Load Balancer** | 统一入口、做限流、TLS 终止 | Nginx+Lua、Envoy、ALB | 支持 **基于 IP/用户/租户** 的细粒度限流，防止突发流量直接冲垮后端 |
| **API Gateway** | 统一协议（REST/gRPC）、鉴权、流控、灰度发布 | Kong、APISIX、AWS API GW | 把公共职责抽出来，业务服务只关注业务逻辑 |
| **Auth Service** | 登录、Token 发放、权限校验（付费/免费） | OAuth2 + JWT + Redis Session | **JWT** 能让后端无状态校验，**Redis** 用来做黑名单、单点登录 |
| **Playback Service** | 接收播放请求、选择最近的 CDN 节点、返回播放 URL（带签名） | Go/Java + gRPC | 必须是 **低延迟**、**高并发** 的语言，gRPC 更省网络开销 |
| **Metadata Service** | 歌曲/专辑/歌手信息查询、版权校验 | MySQL（强一致）+ ElasticSearch（全文） | 元数据关系强一致，搜索需要 **倒排索引** |
| **Recommend Service** | 实时召回、离线特征计算、结果缓存 | Spark + Flink + Redis + Python模型 | **离线** 用 Spark 生成特征，**实时** 用 Flink 计算召回，**Redis** 缓存热点推荐 |
| **Ads Service** | 广告位匹配、计费、插入点返回 | MySQL + Redis + Kafka | 广告调度需要 **事务**（计费），实时流量需要 **低延迟**（Kafka） |
| **Object Store** | 原始音频文件（加密） | Amazon S3 / 阿里云 OSS（多 AZ） | 需要 **高耐久**（11 9）、**大容量**、**分块上传** |
| **CDN Edge Cache** | 靠近用户的音频缓存层 | Akamai / CloudFront / 自建 CDN | **降低回源带宽**、满足 **≤150 ms** 的播放延迟 |
| **Redis Cache** | 元数据、播放 URL、用户 Session 缓存 | Redis Cluster (主从+分片) | 读热点极高，Redis 提供 **毫秒级** 读取 |
| **Message Queue** | 跨服务异步事件（播放统计、广告计费、推荐日志） | Kafka | 解耦、削峰、提供 **可靠日志** 供离线计算 |

> **新手注意**：在 MVP 里可以把 **API Gateway + Auth** 合并到同一个服务，只要后期可以平滑迁移到独立网关即可。  

---  

## ## 第三步：数据库设计  

### 1. 数据模型总览  

| 类别 | 典型表/集合 | 主键 | 重要字段 | 访问模式 |
|------|------------|------|----------|----------|
| **用户** | `users` (RDS) | `user_id` | email, password_hash, tier(premium/free), created_at | 读写均匀，需强一致 |
| **歌曲元数据** | `songs` (MySQL) | `song_id` | title, album_id, artist_id, duration, bitrate, license_id, file_key, created_at | 读多写少，支持关联查询 |
| **专辑** | `albums` (MySQL) | `album_id` | name, artist_id, release_date | 读多 |
| **艺术家** | `artists` (MySQL) | `artist_id` | name, bio | 读多 |
| **播放列表** | `playlists` (MySQL) | `playlist_id` | owner_id, name, collaborative_flag, created_at | CRUD，列表页查询 |
| **播放列表‑歌曲关联** | `playlist_songs` (MySQL) | `(playlist_id, position)` | song_id, added_by, added_at | 按位置分页读取 |
| **用户收藏** | `user_favorites` (MySQL) | `(user_id, song_id)` | liked_at | 点赞/收藏的快速查询 |
| **离线下载任务** | `download_tasks` (MySQL) | `task_id` | user_id, song_id, status, expires_at, drm_key_id | 状态流转（pending→ready→expired） |
| **广告位** | `ad_slots` (MySQL) | `slot_id` | ad_type, duration, price_cpm | 播放时实时匹配 |
| **播放日志** | `play_events` (Kafka → HDFS/ClickHouse) | - | user_id, song_id, timestamp, device, region | 大规模写入，供离线推荐使用 |
| **搜索索引** | `song_index` (ElasticSearch) | `_id = song_id` | title, artist, lyrics, tags | 全文检索、模糊匹配 |

> **为什么分成两类**：  
> - **强一致、关系型**（RDS）用于 **业务关键**（用户、付费、播放列表）——需要事务、外键约束。  
> - **搜索、日志** 用 **NoSQL/ES/ClickHouse**，因为 **写入吞吐大**、**查询方式多样**（全文、聚合）。

### 2. 表结构示例（MySQL）  

```sql
-- 用户表
CREATE TABLE users (
    user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash CHAR(64) NOT NULL,
    tier ENUM('FREE','PREMIUM') NOT NULL DEFAULT 'FREE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 歌曲表
CREATE TABLE songs (
    song_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    album_id BIGINT UNSIGNED,
    artist_id BIGINT UNSIGNED,
    duration INT NOT NULL,               -- 秒
    bitrate INT NOT NULL,                -- kbps
    license_id BIGINT UNSIGNED,
    file_key VARCHAR(512) NOT NULL,      -- 对象存储路径/加密ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_title (title),
    INDEX idx_artist (artist_id)
) ENGINE=InnoDB;
```

### 3. 冷热分层（对象存储）  

| 层级 | 存储介质 | 典型文件 | 访问频率 | 目的 |
|------|----------|----------|----------|------|
| **热层** | SSD-backed OSS (如 S3 IA) | 最近 30 天的热门歌曲 | 高 | 提供最快的回源速度 |
| **冷层** | 低成本 HDD (S3 Standard-IA) | 老歌、低播放率曲目 | 低 | 节省成本 |
| **归档层** | Glacier / Deep Archive | 版权到期、极少访问的曲目 | 极低 | 法律保存需求 |

> **缓存失效策略**：在 CDN Edge 使用 **LRU + TTL**；TTL 依据歌曲热度自动调节（热点 1 h，冷门 24 h）。

---  

## ## 第四步：核心 API 设计  

> 这里仅列出 **最关键** 的几个接口，实际项目会有更多细粒度的 CRUD 与监控接口。

### 1. 鉴权 / 登录  

| 方法 | 路径 | 请求 | 响应 | 说明 |
|------|------|------|------|------|
| `POST` | `/api/v1/auth/login` | `{ "email":"...", "password":"..." }` | `{ "access_token":"jwt", "refresh_token":"..." }` | 采用 **JWT**，30 min 失效，refresh 7 day |
| `POST` | `/api/v1/auth/refresh` | `{ "refresh_token":"..." }` | `{ "access_token":"jwt" }` | 刷新 token |

### 2. 播放点播  

| 方法 | 路径 | 请求 | 响应 | 说明 |
|------|------|------|------|------|
| `GET` | `/api/v1/playback/start` | `?song_id=12345&mode=shuffle` (Header: `Authorization: Bearer <jwt>`) | `{ "play_url":"https://cdn.example.com/xyz?sign=abc", "expires":300, "bitrate":320 }` | **Play URL** 为签名的临时链接，**TTL** 5 min，防止盗链 |
| `POST` | `/api/v1/playback/heartbeat` | `{ "song_id":12345, "position":30 }` | `200 OK` | 客户端每 15 s 上报一次，用于 **计费/广告插入** |

### 3. 歌曲元数据查询  

| 方法 | 路径 | 请求 | 响应 | 说明 |
|------|------|------|------|------|
| `GET` | `/api/v1/metadata/song/{song_id}` | Header: `Authorization` | `{ "song_id":..., "title":"...", "artist":"...", "duration":210, "license":"PREMIUM" }` | 读取 **Redis**，若 miss 再查询 MySQL 并写回缓存 |

### 4. 播放列表 CRUD  

| 方法 | 路径 | 请求 | 响应 | 说明 |
|------|------|------|------|------|
| `POST` | `/api/v1/playlists` | `{ "name":"My Rock", "collaborative":false }` | `{ "playlist_id":9876 }` | 创建 |
| `GET` | `/api/v1/playlists/{id}` | – | `{ "playlist_id":9876, "songs":[...], "owner":... }` | 分页返回 `songs`（`limit/offset`） |
| `POST` | `/api/v1/playlists/{id}/songs` | `{ "song_id":12345, "position":10 }` | `200 OK` | 添加/移动 |
| `DELETE` | `/api/v1/playlists/{id}/songs/{song_id}` | – | `204 No Content` | 删除 |

### 5. 离线下载（付费校验 + DRM）  

| 方法 | 路径 | 请求 | 响应 | 说明 |
|------|------|------|------|------|
| `POST` | `/api/v1/download/request` | `{ "song_id":12345 }` | `{ "download_url":"https://cdn.example.com/xyz?drm=token", "expires":86400 }` | 先校验用户 `tier==PREMIUM`，返回 **带 DRM token** 的链接 |
| `GET` | `/api/v1/download/status/{task_id}` | – | `{ "status":"READY", "expires_at":... }` | 查询下载任务进度 |

### 6. 广告位获取（免费用户）  

| 方法 | 路径 | 请求 | 响应 | 说明 |
|------|------|------|------|------|
| `GET` | `/api/v1/ads/slot` | `?position=pre-roll&user_id=...` | `{ "ad_id":555, "media_url":"https://ad.cdn.com/xyz.mp3", "duration":30, "tracking_url":"https://ad.trk.com/..." }` | 客户端在播放前先请求广告，播放完后回调 `tracking_url` 计费 |

---  

## ## 第五步：详细组件设计  

下面针对每个核心模块展开 **实现细节、技术选型、数据流、容错**，并回答提示中的追问。

### 1. **入口层（DNS + Global LB）**  

| 设计点 | 方案 | 解释 |
|--------|------|------|
| **Anycast DNS** | Cloudflare/阿里 DNS + Anycast IP | 同一个 IP 在全球多个 POP（Point of Presence）上宣布，用户自动就近解析到最近的入口，降低 RTT。 |
| **全局 L7 LB** | Envoy/NGINX + Lua 脚本 | 能在第 4 层做 **TLS 终止**，在第 7 层做 **IP/用户/付费等级** 的**细粒度限流**（Token Bucket），防止热点歌曲一次性冲垮后端。 |
| **限流/降级** | **分层**：<br>① 全局 QPS 上限 1M <br>② 免费用户 0.8× ③ 付费用户 1.2× | 当全局流量超阈值，先**降级**免费用户的 **广告位**（减少回源），保持付费用户可用。 |

> **为什么不直接把 CDN 当入口**：因为 CDN 只能缓存**已有的对象**，而**播放请求**需要先走业务层做鉴权、计费、广告插入等业务，直接进入 CDN 会绕过这些关键步骤。

### 2. **鉴权 & 计费**  

- **JWT**：在登录成功后颁发，包含 `user_id`, `tier`, `exp`. 客户端每次请求在 `Authorization: Bearer` 头部带上。  
- **黑名单/会话失效**：使用 **Redis Set**（`revoked_jwt:{jti}`）存放被撤销的 `jti`（JWT ID），每次校验时查询 O(1)。  
- **计费**：免费用户播放时记录 **play_event**（song_id、timestamp、user_id）并推送到 Kafka。广告服务消费后实时扣费。付费用户只记录 **播放日志**，不计费。  

### 3. **播放调度（Playback Service）**  

#### 3.1 请求处理流程  

```
1. API Gateway → Playback Service (gRPC)
2. 鉴权：解析 JWT，获取 user_id、tier
3. 元数据查询：先读 Redis cache，miss → MySQL → 写回 Redis
4. 版权校验：若 song.license 不匹配 tier，返回错误
5. 广告检查（免费用户）：
   - 调用 Ads Service → 获取 pre-roll / mid-roll 广告信息
6. CDN 节点选择：
   - 根据用户 IP → GeoIP → 最近的 CDN POP
   - 生成签名 URL（HMAC+TTL），防盗链
7. 返回给前端：play_url、ad_info、expire
8. 前端开始播放 → 每 15 s 心跳上报（用于计费、广告统计）
```

#### 3.2 CDN 边缘缓存  

- **签名 URL**：`https://cdn.example.com/song/12345?sign=HMAC_SHA256(secret, path|expiry)`  
- **TTL**：5 min（可调），防止一次泄漏后长期被盗用。  
- **缓存键**：`song_id|bitrate|region` → 同一首歌不同码率/不同地区分别缓存。  

#### 3.3 多码率自适应（ABR）  

- 将同一首歌曲切片（比如每 10 s）为 **多个码率**（128/256/320 kbps）。  
- 播放器使用 **MPEG‑DASH** 或 **HLS** 协议，客户端根据网络状况切换码率。  
- **存储**：每首歌的切片文件放在同一个 `file_key` 目录下，CDN 自动做分片缓存。

### 4. **元数据 & 搜索**  

- **MySQL**：存放结构化关系（song ↔ album ↔ artist）。使用 **InnoDB**，**读写分离**（主库写，多个从库读）。  
- **ElasticSearch**：建立 `song_index`，字段 `title`, `artist_name`, `lyrics`, `tags`。使用 **同步机制**（Canal / Debezium）将 MySQL binlog 同步到 ES，保证搜索实时性。  
- **缓存**：热门歌曲的完整元数据（包括 URL、license）放在 **Redis Hash**，TTL 10 min，热点命中率 > 90%。  

### 5. **推荐系统**  

#### 5.1 离线特征计算  

- **每天一次**：使用 **Spark** 读取 `play_events`（ClickHouse）和 `user_favorites`，生成用户向量、歌曲向量。  
- **输出**：写入 **HBase / Cassandra**（按用户分区），供实时召回使用。  

#### 5.2 实时召回  

- **Flink** 实时消费 `play_events`，更新用户最近行为（最近 30 min），在 **Redis** 中维护 **最近 100 条** 交互。  
- 当用户打开首页时，**Recommend Service** 先查 **Redis**（实时热点），再补足 **离线向量**（从 HBase）做 **召回 + 排序**，最终返回 **前 20 条** 推荐。  

#### 5.3 推荐 API  

```
GET /api/v1/recommend/home?limit=20
```

返回结构：

```json
{
  "recommendations": [
    {"song_id":123, "title":"...", "artist":"...", "reason":"Based on your recent rock plays"},
    ...
  ]
}
```

### 6. **播放列表（协作编辑）**  

- **乐观锁**：在 `playlist_songs` 表加入 `version` 字段，每次写入时 `WHERE version = X`，冲突时返回 409，客户端重新拉取。  
- **事件流**：对每次编辑产生 **PlaylistEvent**（add/remove/move），写入 Kafka，供 **推荐**、**审计** 使用。  
- **分页**：使用 `limit/offset` 或 **keyset pagination**（`position > last_position`）提升大列表的读取性能。  

### 7. **离线下载 & DRM**  

| 步骤 | 关键技术 | 说明 |
|------|----------|------|
| **下载请求** | Playback Service → DRM Service | 检查用户 `tier==PREMIUM`，生成 **一次性 DRM token**（有效期 24 h）。 |
| **文件加密** | AES‑128 GCM + 业务自定义密钥 | 在上传到 OSS 时就加密，**每首歌使用不同密钥**（Key ID 存在 `songs.drm_key_id`）。 |
| **播放端解密** | 集成 **Widevine / PlayReady** SDK（Android/iOS） | 客户端在本地拿到 DRM token，向 **License Server** 请求解密密钥，解密后本地缓存。 |
| **防盗链** | URL 签名 + CDN 防盗链 + 设备指纹绑定 | CDN 只接受带签名的 URL；License Server 绑定 **device_id**，同一 token 只能在同一设备解密。 |
| **失效与撤销** | Redis TTL + 定期轮询 | 当用户取消付费或下载过期，立即在 Redis 中标记 `drm_revoked:{token}`，Playback 时拒绝。 |

> **为什么要加 DRM**：仅靠签名 URL 防止外链，仍然可以被抓包后分享。DRM 通过 **硬件绑定** 与 **动态密钥**，大幅提升破解成本。

### 8. **广告插入**  

- **广告位模型**：`slot_id`, `ad_type` (pre-roll, mid-roll), `duration`, `cpm`, `target_audience`。  
- **插入策略**：  
  1. 播放请求到达 Playback Service，若 `user.tier==FREE`，调用 **Ads Service**。  
  2. Ads Service 根据 **用户画像**（兴趣标签、地域）从 **广告库** 选取合适广告（实时竞价）。  
  3. 返回 **ad_info**（media_url、tracking_url）。  
  4. 客户端先播放广告，广告播放结束后调用 `ad_tracking_url`，Ads Service 记录 **曝光** 与 **点击**，计费。  

- **降级**：当广告系统不可用，直接返回 **空广告**，Playback Service 仍返回正常 `play_url`，保证核心业务不中断。  

### 9. **监控 & 统计**  

| 维度 | 采集点 | 存储 | 用途 |
|------|--------|------|------|
| **QPS / Latency** | API Gateway Nginx日志 + Prometheus | TSDB | 实时告警、容量规划 |
| **播放成功率** | Playback Service 返回码 | ClickHouse | 业务健康度 |
| **缓存命中率** | Redis INFO + CDN日志 | Grafana | 优化缓存策略 |
| **广告 ROI** | Ads Service 计费日志 | MySQL | 收入结算 |
| **异常日志** | ELK (Filebeat → Logstash → Kibana) | Elasticsearch | 故障定位 |

> **新手提示**：先把 **关键业务指标（KPI）** 写在白板上，再决定监控系统的细粒度。不要一开始就想把所有日志都写进数据库，成本太高。

---  

## ## 第六步：扩展性与高可用设计  

### 1. **水平扩展**  

- **无状态服务**（API Gateway、Playback、Auth、Recommend、Ads）使用 **容器化（Docker）+Kubernetes**，通过 **Horizontal Pod Autoscaler** 根据 CPU/QPS 自动伸缩。  
- **数据库读写分离**：主库负责写，多个从库负责读，使用 **ProxySQL** 或 **HAProxy** 实现读写路由。  
- **对象存储**：使用 **多AZ 多Region**，自动复制 3 副本，单点故障不影响访问。  

### 2. **容错与冗余**  

| 场景 | 方案 |
|------|------|
| **服务实例宕机** | Kubernetes **Pod 重启** + **Service** 自动发现 |
| **单机磁盘故障** | MySQL 主从复制 + 自动故障转移（MHA/Orchestrator） |
| **CDN 节点失效** | 同城多 POP（Anycast）自动切换 |
| **网络分区** | 客户端降级到最近的 **备份 Region**，使用 **DNS TTL 低**（30 s）实现快速切换 |
| **限流触发** | 熔断器（Hystrix/Resilience4j）返回 **友好错误**（如 “系统繁忙，请稍后再试”）并记录指标 |

### 3. **数据一致性策略**  

| 数据类型 | 一致性要求 | 采用的技术 |
|----------|------------|------------|
| **用户账户/付费信息** | 强一致 | MySQL 主库事务 + 2PC（跨服务） |
| **播放日志** | 最终一致 | Kafka → ClickHouse（批量写） |
| **缓存** | 读写不一致容忍 | 采用 **Cache‑Aside**，写时同步 DB，读时若 miss 再查 DB |
| **广告投放计费** | 强一致 | 事务性 MySQL 表 + 幂等设计（唯一 `ad_exposure_id`） |

### 4. **灾备（DR）**  

- **跨 Region 同步**：使用 **MySQL Group Replication** 或 **TiDB** 实现跨大洲多活。  
- **灾备演练**：每月一次 **故障切换** 演练，验证 **DNS TTL**、**数据同步延迟**、**客户端容错**。  

### 5. **安全性**  

| 风险 | 防护措施 |
|------|----------|
| **恶意爬虫/盗链** | CDN **Referer**、**签名 URL**、IP 白名单 |
| **账号泄露** | 双因素认证（SMS + Authenticator） |
| **数据泄露** | **AES‑256** 对象存储加密 + **KMS** 管理密钥，**最小权限 IAM** |
| **DDoS** | **Global WAF** + **流量清洗**（Scrubbing Center） |
| **DRM 破解** | **硬件绑定** + **频繁轮换密钥**（每次下载生成新 token） |

---  

## ## 第七步：常见面试追问与回答  

### Q1. **如果我们要在全球范围内部署 CDN，如何决定哪些歌曲放在边缘缓存，缓存失效策略如何设计？**  

**答案要点**  

1. **缓存热点判定**  
   - **基于播放量**：每天统计每首歌曲的 **PV**，前 5% 设为 **热点**。  
   - **地域分布**：将热点再细分到 **Region**（如北美、欧洲、东南亚），若某地区占比 > 20% 则该地区单独缓存。  

2. **缓存分层**  
   - **Edge Cache**（CDN） → **Regional Cache**（自建或云厂商的 **Regional POP**） → **Origin（OSS）**。  
   - **TTL** 采用 **动态**：  
     - **热点**：1 h（可根据命中率自动调节）  
     - **冷门**：24 h → 7 d（超过 30 d 未访问则逐出）  

3. **失效机制**  
   - **LRU + LFU** 双策略：LRU 处理新内容，LFU 保护长期热点。  
   - **主动失效**：当版权到期或下架时，发送 **Purge** 请求至 CDN，立即失效对应 `file_key`。  

4. **实现细节**  
   - 使用 **CDN API**（如 `POST /purge`）在 **Song Service** 中集成。  
   - **监控**：通过 CDN 提供的 **Cache Hit Ratio** 与 **Origin Bandwidth** 指标，动态调参。  

### Q2. **面对突发的流量峰值（如热门歌单上线），你会怎样在入口层进行限流与降级，保证核心播放服务不被压垮？**  

**答案要点**  

1. **分层限流**  
   - **全局 Token Bucket**：在 Global L7 LB 处设定 QPS 上限（如 1M），当超出时直接返回 `429 Too Many Requests`。  
   - **业务级限流**：在 API Gateway 对 **免费用户**、**付费用户**、**不同地域** 设置不同配额（例如免费用户 80% 配额）。  

2. **热点保护**  
   - 对 **热点歌曲**（最近 10 min 播放次数激增）启用 **热点熔断**：如果单首歌曲的 QPS 超过阈值（如 10k QPS），返回 **备用音质**（低码率）或 **延迟加载**。  

3. **降级策略**  
   - **免费用户**：在流量紧张时**关闭广告**或**降低广告频次**，释放计费服务资源。  
   - **付费用户**：**保持全功能**，但可临时将 **缓存失效时间**延长，减少回源压力。  

4. **快速弹性扩容**  
   - **预热**：在大型活动（如周末、明星发布）前提前 **手动扩容** Playback Service + CDN。  
   - **自动伸缩**：K8s HPA 根据 **CPU/请求率** 自动扩容，配合 **Cluster Autoscaler** 增加节点。  

5. **监控报警**  
   - 设置 **QPS、错误率、CPU** 的阈值报警，触发 **Ops** 手动干预或 **自动降级**。  

### Q3. **用户下载的音频文件需要防止非法分发，你会采用哪些加密或 DRM 方案，同时兼顾跨平台播放的兼容性？**  

**答案要点**  

1. **文件层面加密**  
   - 在上传到对象存储前使用 **AES‑128 GCM** 加密，每首歌曲单独生成 **Content Key**，存放在 **KMS**（Key Management Service）。  

2. **DRM 授权服务器**  
   - **License Server**（基于 Widevine / PlayReady）接收 **DRM token**（一次性、带有效期），返回 **Content Key**（经过设备公钥加密的密钥）。  

3. **客户端集成**  
   - 移动端（Android/iOS）使用官方 **DRM SDK**（ExoPlayer + Widevine，AVFoundation + FairPlay），Web 端使用 **EME（Encrypted Media Extensions）** + **MSE**。  

4. **防盗链**  
   - 下载链接为 **签名 URL**（HMAC+TTL），CDN 校验签名后才返回加密文件。  
   - **License Server** 检查 **device_id**、**user_id** 与 **token** 的对应关系，防止同一 token 被多设备使用。  

5. **失效与撤销**  
   - 当用户取消付费或下载期限到期，立即在 **Redis** 中标记 `drm_revoked:{token}`，License Server 拒绝解密请求。  

6. **兼容性**  
   - **多 DRM 方案**（Widevine、PlayReady、FairPlay）并行部署，客户端根据平台选择对应实现。  
   - **统一 Content Key 管理**：KMS 生成的原始密钥统一存储，分别包装成各平台所需的加密格式。  

### Q4. **如果用户在离线状态下打开已经下载的歌曲，系统如何保证播放不受网络影响且仍能计费/统计？**  

**答案要点**  

- **离线统计 SDK**：在客户端集成 **本地计数器**，记录每首已下载歌曲的播放次数、时长。  
- **加密本地缓存**：播放前先解密本地文件，解密过程不依赖网络。  
- **同步机制**：设备每次恢复网络时，向 **Playback Service** 上报离线日志（幂等 `play_event_id`），服务端进行 **去重**、**计费**。  
- **冲突处理**：若用户在多设备离线播放同一歌曲，使用 **全局唯一的 event_id（UUID）**，服务端确保一次计费。  

---  

## ## 心得与反思  

### 1. 本题最难的 1‑2 个设计决策  

| 决策 | 挑战点 | 思考过程 |
|------|--------|----------|
| **全局 CDN 与边缘缓存的热点划分** | 必须在 **存储成本** 与 **用户体验** 之间找到平衡；错误的热点判定会导致热点歌曲频繁回源，增加延迟，或导致缓存占满导致热点被驱逐。 | 先用 **播放量统计**（实时流）+ **地域分布** 做初步划分；再通过 **缓存命中率监控** 动态调节 TTL；加入 **主动下线**（版权到期）机制防止“死缓存”。 |
| **离线下载的 DRM 兼容性** | 需要兼顾 **多平台（Android、iOS、Web）**、**安全性** 与 **性能**（解密不影响播放流畅）。如果只用单一 DRM，可能在某平台上不可用；如果不加 DRM，容易泄漏。 | 采用 **行业标准 DRM（Widevine/PlayReady/FairPlay）**，统一 **KMS** 管理原始密钥；在下载阶段仅做 **文件层加密**（AES），播放阶段交给平台 DRM SDK 完成授权解密；这样既保证安全，又利用现成的跨平台实现。 |

### 2. 新手最容易犯的错误（至少 2 条）  

1. **把所有功能一次性全部实现**  
   - **结果**：系统过于复杂、难以在面试中完整阐述，容易遗漏关键细节。  
   - **建议**：先画出 **MVP**（点播 + 鉴权），把推荐、广告、下载等留作 **扩展点**，在后续章节逐步补充。  

2. **忽视缓存与 CDN 的作用，直接把所有请求打到后端数据库**  
   - **结果**：QPS 直接压垮 MySQL，延迟远超 150 ms，系统不可用。  
   - **建议**：先在 **API Gateway** 加入 **Cache‑Aside**，把热点歌曲元数据、播放 URL、搜索结果放入 **Redis/ES**，再考虑 **CDN** 的边缘缓存。  

### 3. 学习建议和可延伸的方向  

| 方向 | 学习资源 | 说明 |
|------|----------|------|
| **分布式系统基础** | 《Designing Data‑Intensive Applications》、MIT 6.824 课程 | 理解 CAP、事务、复制、一致性模型。 |
| **微服务与容器化** | 官方 Kubernetes 文档、Istio Service Mesh | 掌握服务发现、熔断、流量治理。 |
| **大数据与实时流处理** | 《Streaming Systems》、Flink 官方文档 | 推荐系统、播放日志的离线/实时计算。 |
| **内容分发网络（CDN）** | Akamai、CloudFront 技术白皮书 | CDN 缓存层次、边缘计算、签名 URL。 |
| **数字版权管理（DRM）** | Widevine / PlayReady / FairPlay 官方文档 | 了解跨平台加密、授权流程。 |
| **广告系统** | 《Real‑Time Bidding》、Google AdX 体系 | 学习广告召回、计费、去重。 |
| **系统监控 & Observability** | Prometheus + Grafana、OpenTelemetry | 从一开始就埋点、告警、追踪。 |

> **小技巧**：在准备面试时，先把 **业务流程**（用户点播 → 鉴权 → 选 CDN → 播放）用 **时序图** 画出来，再逐层拆解。这样既能展示你对系统整体的把握，又能自然引出每个子系统的设计细节。  

---  

**祝你在面试中从容阐述，给面试官留下“能把复杂系统拆解成可管理模块，并且考虑到高并发、容错、版权安全”的好印象！** 🎧🚀
