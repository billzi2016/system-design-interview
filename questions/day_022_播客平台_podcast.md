# 第 22 天：设计 播客平台（Podcast）

> 生成日期：2026-05-04

---

## 题目背景  
播客平台（Podcast）是一个面向移动端和 Web 端的音频内容分发系统，用户可以订阅、搜索、收听和上传播客节目，平台需要支撑海量音频文件的存储、流媒体播放以及实时推荐。

## 面试场景设定  
> **面试官**：  
> “我们现在要设计一个全球化的播客平台，核心目标是支持 **每日数千万活跃用户** 能够流畅地搜索、播放和上传音频。请你从系统架构的角度出发，完整地设计这个平台的高层结构，并说明关键的技术选型与容量规划。”  

（面试官可在候选人回答过程中适时追问细节）

## 功能性需求  

| 编号 | 功能描述 |
|------|----------|
| 1 | **用户注册/登录**：支持邮箱、手机号、第三方 OAuth（Google、Apple）登录，登录后能够管理个人资料、订阅列表。 |
| 2 | **节目搜索 & 发现**：基于关键字、标签、类别进行全文搜索，并提供热门、推荐、排行榜等发现页。 |
| 3 | **音频播放**：支持在线播放、断点续传、倍速播放、离线下载（加密）以及播放进度同步（多端）。 |
| 4 | **节目上传 & 管理**：创作者可以上传音频文件（支持 30 GB 单文件），编辑节目元数据（标题、简介、封面、标签），并查看播放/订阅统计。 |
| 5 | **订阅 & 推送**：用户可以订阅节目，平台在新集上线时推送通知（邮件、移动端推送）。 |
| 6 | **评论 & 互动**：支持对单集和节目进行评论、点赞、回复，且需要基本的内容审核机制。 |

## 非功能性需求  

| 指标 | 估算值 | 说明 |
|------|--------|------|
| **DAU（每日活跃用户）** | 30 Million | 目标在全球市场的日活量。 |
| **QPS（播放请求峰值）** | 120,000 QPS | 假设 20% 的 DAU 同时进行播放请求，峰值 2×冗余。 |
| **平均播放延迟** | < 150 ms（首帧） | 从用户发起播放到收到首帧音频的时延。 |
| **可用性** | 99.95%（年可用时间约 4.38 h） | 关键业务（播放、搜索）需要高可用。 |
| **存储容量** | 约 25 PB | 预计每集平均 150 MB，全年约 120 M 集，包含冗余与备份。 |
| **带宽** | 约 10 Tbps 峰值出站 | 120k QPS × 平均 250 kbps（音频码率） × 1.5（网络冗余）。 |

> **注**：以上数值为粗略估算，面试时可根据候选人假设进行微调。

## 系统边界  

**本题范围（需要设计）**  
- 用户身份认证、授权体系。  
- 音频上传、存储、转码、分发（CDN）。  
- 播放流控、断点续传、缓存策略。  
- 搜索引擎（全文、标签）以及推荐/排行榜的基础模型。  
- 基础的评论系统与内容审核流程（机器+人工）。  
- 监控、日志、报警、灰度发布等运维能力。

**不在本题范围（可不考虑）**  
- 具体的机器学习推荐算法细节（只需给出接口层）。  
- 广告投放系统、付费订阅结算（可视为后置业务）。  
- 多语言本地化、版权合同管理。  
- 第三方合作平台（如 Apple Podcasts、Spotify）的内容同步。  
- 详细的移动端 UI/UX 实现（只需提供 API 接口层）。

## 提示与追问  

1. **容量规划细节**  
   - “如果我们要在 6 个月内将 DAU 提升到 50 M，存储和带宽需要如何扩容？”  

2. **高可用与灾备**  
   - “请说明播放服务和搜索服务的容灾方案，如何在单点故障时保证 99.95% 可用？”  

3. **缓存与 CDN 设计**  
   - “在播放音频的场景下，如何利用边缘缓存、分片下载以及预取技术降低首帧延迟？”  

---  
*请候选人在回答时，围绕系统的 **分层架构**（前端/网关、业务层、数据层）展开，并说明关键技术选型（如使用 gRPC/REST、Kafka、Elasticsearch、对象存储、Kubernetes 等）以及它们的权衡因素。*

---

# 题解

## 解题思路总览  

先把“大而全”的需求拆解成 **最小可运行系统（MVP）**，再一步步给它加 **可用性、伸缩性、容灾** 等特性。  
整个过程可以类比搭乐高：  
1. **确定需求** → 画出**功能清单**、**流量模型**。  
2. **画高层框图** → 把系统划分成 **前端/网关 → 业务层 → 数据层**。  
3. **选技术** → 依据 **成本、成熟度、扩展性** 做权衡。  
4. **细化每块** → 数据库表、API、缓存、消息队列、对象存储、CDN…  
5. **加上高可用/容灾** → 主备、跨地域、熔断、限流等。  
6. **演练面试追问** → 预先准备容量扩容、缓存、监控等答案。  

下面我们按 **七个章节** 逐层展开，**每一步都解释“为什么这么做，若不这么做会怎样”。**  

---

## 第一步：理解需求与规模估算  

| 需求编号 | 核心业务 | 关键指标 |
|----------|----------|----------|
| 1 | 注册/登录 | 需要 **高并发写入**（新用户）与 **安全的身份校验** |
| 2 | 搜索 & 发现 | **全文检索**、**实时热榜**，QPS 受搜索流量影响 |
| 3 | 音频播放 | **流媒体**（首帧 <150 ms），**断点续传**、**多端同步** |
| 4 | 上传 & 管理 | **大文件上传**（≤30 GB），**转码**、**元数据写入** |
| 5 | 订阅 & 推送 | **事件通知**（新集上线） |
| 6 | 评论 & 互动 | **写入/读取**频繁，**审核**需求 |

### 1️⃣ 规模估算（粗略）  

| 指标 | 估算公式 | 结果 |
|------|----------|------|
| DAU | 题目给 30 M | 30 M |
| 同时在线播放用户 | DAU × 20% ≈ 6 M | 6 M |
| 峰值播放 QPS | 同时播放用户 ÷ 5s ≈ 120 k QPS | 120 k |
| 音频平均码率 | 250 kbps（常见 64–128 kbps 但留余量） | 250 kbps |
| 峰值出站带宽 | 120 k × 250 kbps × 1.5（冗余） ≈ 45 Gbps ≈ 5.6 TB/s ≈ 10 Tbps（题目给） | 10 Tbps |
| 存储 | 120 M 集 × 150 MB ≈ 18 PB + 2×副本 ≈ 36 PB → 取 25 PB 作为业务容量 | 25 PB |

> **如果不做这些估算**，后期会出现 **容量爆炸、性能瓶颈、频繁宕机** 的尴尬局面。

---

## 第二步：高层架构设计  

### 2.1 最小可用系统（MVP）  

```
[客户端] → [API Gateway (REST+Auth)] → [业务服务 (User, Podcast, Playback, Comment)]
                                     ↘
                                   [MySQL]   [Elasticsearch]   [对象存储 (S3/OSS)]
```

- **API Gateway**：统一入口，做鉴权、流量控制、限流。  
- **业务服务**：每个核心业务拆成 **微服务**（后期可以拆分），使用 **Spring Boot / Go + gRPC**。  
- **MySQL**：事务性强，存放用户、节目元数据、评论等结构化数据。  
- **Elasticsearch**：全文搜索、热榜。  
- **对象存储**：原始音频文件、转码后文件、封面图。  

> **不采用微服务**（只用单体）在 MVP 时可以降低运维成本，但随着 **DAU 30M**、**QPS 120k**，单体会出现 **CPU/内存瓶颈、部署风险**，不利于后续扩展。

### 2.2 高可用分布式架构（完整版）  

```
                ┌─────────────────────────────────────┐
                │                CDN (Edge)           │
                └───────▲──────────────────────▲───────┘
                        │                      │
                ┌───────┴───────┐      ┌───────┴───────┐
                │  Global DNS   │      │  Global Load  │
                └───────▲───────┘      │   Balancer    │
                        │          └───────▲───────┘
          ┌─────────────┼───────────────────┼─────────────┐
          │             │                   │             │
   ┌──────▼─────┐ ┌─────▼─────┐       ┌─────▼─────┐ ┌───────▼─────┐
   │  API GW    │ │  Auth Svc │       │  Rate Lim │ │  WAF / DDoS │
   └──────▲─────┘ └─────▲─────┘       └─────▲─────┘ └───────▲─────┘
          │            │                 │               │
   ┌──────┴───────┐┌───┴───────┐ ┌───────┴───────┐ ┌─────┴───────┐
   │   Service   ││   Service │ │   Service    │ │   Service   │
   │   Mesh (Istio)││   Mesh   │ │   Mesh       │ │   Mesh      │
   └──────▲───────┘└─────▲─────┘ └──────▲───────┘ └─────▲───────┘
          │            │                 │               │
   ┌──────┴───────┐┌───┴───────┐ ┌───────┴───────┐ ┌─────┴───────┐
   │   MySQL      ││   MySQL   │ │   ES Cluster │ │   Redis      │
   │   (sharding) ││ (read‑rep)│ │   (hot‑index)│ │   (cache)   │
   └──────▲───────┘└─────▲─────┘ └──────▲───────┘ └─────▲───────┘
          │            │                 │               │
   ┌──────┴───────┐┌───┴───────┐ ┌───────┴───────┐ ┌─────┴───────┐
   │ Object Store ││ Transcode │ │   Kafka       │ │   ClickHouse│
   │ (Multi‑AZ)   ││ Service   │ │   (event)     │ │   (Analytics)│
   └──────▲───────┘└─────▲─────┘ └──────▲───────┘ └─────▲───────┘
          │            │                 │               │
          └───────►─────┘──────►───────────┘───────►───────┘
                     CDN Edge Cache (Audio Segments)
```

**关键组件解释**  

| 组件 | 作用 | 选型理由 |
|------|------|----------|
| **Global DNS + Anycast** | 把用户请求路由到最近的入口节点 | 低延迟、故障自动切换 |
| **API Gateway** (Kong / Envoy) | 鉴权、限流、统一入口、灰度发布 | 支持插件化、可水平扩展 |
| **Auth Service** (OAuth2 + JWT) | 第三方登录、Token 发放、短/长 token | JWT 可无状态验证，降低中心化压力 |
| **Service Mesh** (Istio) | 流量治理、熔断、链路追踪、统一安全策略 | 隐藏微服务之间的复杂性 |
| **MySQL（主从+分片）** | 事务强、用户/节目元数据 | 读写分离、水平分片支撑 10k QPS |
| **Elasticsearch** | 关键字搜索、聚合热榜、自动补全 | 倒排索引查询 O(log N)，水平扩展 |
| **Redis** | 热点元数据缓存、播放进度、Token 黑名单 | 内存快读、支持 TTL |
| **对象存储** (Amazon S3 / Alibaba OSS) | 海量音频文件、分片存储、跨 AZ 复制 | 可靠性 99.999999%（11 9），按需弹性 |
| **Transcode Service** | 将上传的原始音频转为统一 bitrate、切片 (HLS/DASH) | 多码率、边缘缓存友好 |
| **Kafka** | 事件总线（上传完成、播放、评论） | 高吞吐、持久化、解耦业务 |
| **ClickHouse** | 实时统计（播放量、订阅增长） | 列式存储、OLAP 快速聚合 |
| **CDN Edge** | 音频分片缓存、就近加速 | 把首帧延迟压到 <150 ms |

---

## 第三步：数据库设计  

### 3.1 关系型数据库（MySQL）  

| 表名 | 主键 | 关键字段 | 说明 |
|------|------|----------|------|
| **users** | `user_id` (BIGINT PK) | email, phone, password_hash, created_at | 用户基本信息 |
| **user_oauth** | `(provider, provider_uid)` PK | user_id, access_token, refresh_token | 第三方登录绑定 |
| **podcasts** | `podcast_id` PK | title, description, cover_url, owner_user_id, created_at | 节目元数据 |
| **episodes** | `episode_id` PK | podcast_id, title, description, audio_url, duration, publish_time, status (uploaded/processing/available) |
| **subscriptions** | `(user_id, podcast_id)` PK | subscribed_at, last_notified_at |
| **comments** | `comment_id` PK | episode_id, user_id, parent_comment_id (null for top‑level), content, like_count, status (pending/approved) |
| **likes** | `(user_id, comment_id)` PK | created_at |
| **playback_progress** | `(user_id, episode_id)` PK | last_position_sec, updated_at |

- **分片（Sharding）**：按 **user_id** 哈希分库分表，解决 **写入热点**（注册、播放进度）。  
- **读写分离**：主库处理写，多个从库提供读，**缓存**（Redis）再进一步降低读库压力。  

### 3.2 搜索引擎（Elasticsearch）  

| 索引 | 文档类型 | 必要字段 | 用途 |
|------|----------|----------|------|
| **podcast_idx** | `podcast` | `podcast_id`, `title`, `description`, `tags`, `category`, `owner_user_id`, `publish_time` | 节目搜索、过滤、聚合热榜 |
| **episode_idx** | `episode` | `episode_id`, `podcast_id`, `title`, `description`, `tags`, `publish_time` | 集搜索、自动补全 |
| **comment_idx** (可选) | `comment` | `comment_id`, `episode_id`, `content` | 评论全文搜索 |

- **分片**：根据 **doc_id hash** 自动分片，**副本数 2** 保障搜索容灾。  
- **同步方式**：业务服务写入 MySQL 后，发送 **Kafka** 消息，消费者负责 **异步同步到 ES**，保证 **强一致性需求不高**（搜索可以稍后一致）。

### 3.3 对象存储（S3）  

- **目录结构**（伪路径）  
  ```
  /raw/{user_id}/{upload_id}/{original_file}
  /transcoded/{podcast_id}/{episode_id}/{bitrate}/{segment_{index}.ts}
  /cover/{podcast_id}/cover.jpg
  ```
- **多 AZ 冗余**：开启 **跨区域复制**（CRR）实现容灾。  
- **加密**：使用 **SSE‑S3** 或 **SSE‑KMS**，下载时通过 **签名 URL**（短时有效）防止盗链。  

### 3.4 大数据统计（ClickHouse）  

| 表名 | 主键 | 主要字段 | 用途 |
|------|------|----------|------|
| **play_log** | `event_time` (DateTime) | user_id, episode_id, duration_sec, client_ip | 播放时长、活跃用户统计 |
| **subscribe_log** | `event_time` | user_id, podcast_id, action (subscribe/unsubscribe) | 订阅增长趋势 |
| **comment_log** | `event_time` | user_id, episode_id, comment_id, action | 评论活跃度 |

- **数据摄入**：Kafka → Flink → ClickHouse（实时 ETL）。  

---

## 第四步：核心 API 设计  

> **原则**：**REST** 用于 CRUD 场景，**gRPC** 用于高频、二进制交互（如播放进度同步）。所有 API 必须 **统一返回结构**、**错误码**、**限流**。

### 4.1 统一返回模型  

```json
{
  "code": 0,                // 0 表示成功，非 0 为业务错误码
  "message": "OK",
  "data": {...}             // 成功时返回的业务对象
}
```

### 4.2 关键接口（REST）  

| 方法 | 路径 | 功能 | 请求体/参数 | 响应 |
|------|------|------|-------------|------|
| `POST` | `/api/v1/auth/register` | 注册 | `{email, password, phone}` | `user_id, token` |
| `POST` | `/api/v1/auth/login` | 登录 | `{email|phone, password}` | `token` |
| `POST` | `/api/v1/auth/oauth` | 第三方登录 | `{provider, code}` | `token` |
| `GET` | `/api/v1/podcasts/{podcast_id}` | 查询节目详情 | - | 节目对象 |
| `GET` | `/api/v1/podcasts/search?q=xxx&page=1&size=20` | 关键字搜索 | query 参数 | `hits[]` |
| `GET` | `/api/v1/podcasts/hot?category=tech` | 热门榜单 | - | `list[]` |
| `POST` | `/api/v1/podcasts/{podcast_id}/episodes` | 上传集（元数据） | `{title, description, tags}` | `episode_id` |
| `POST` | `/api/v1/podcasts/{podcast_id}/episodes/{episode_id}/upload` | **分片上传**（前端直传 S3） | `multipart/form-data` | `upload_id` |
| `GET` | `/api/v1/episodes/{episode_id}/stream?bitrate=128k` | 取得播放 URL（CDN 签名） | - | `url` |
| `POST` | `/api/v1/playback/progress` (gRPC) | 同步播放进度 | `{user_id, episode_id, position_sec}` | `ack` |
| `POST` | `/api/v1/subscriptions/{podcast_id}` | 订阅节目 | - | `success` |
| `GET` | `/api/v1/subscriptions` | 获取我的订阅列表 | - | `list[]` |
| `POST` | `/api/v1/comments` | 发表评论 | `{episode_id, content, parent_id?}` | `comment_id` |
| `POST` | `/api/v1/comments/{comment_id}/like` | 点赞 | - | `new_like_count` |
| `GET` | `/api/v1/notifications` | 拉取系统通知（新集、回复） | - | `list[]` |

### 4.3 高频接口（gRPC）  

```proto
service PlaybackService {
  rpc SyncProgress (ProgressRequest) returns (ProgressResponse);
  rpc GetProgress (ProgressQuery) returns (ProgressResponse);
}
message ProgressRequest {
  int64 user_id = 1;
  int64 episode_id = 2;
  int64 position_sec = 3;
}
message ProgressResponse { bool ok = 1; }
```

- **为什么 gRPC**：二进制协议体积小、支持流式调用，适合移动端频繁的 **位置上报**（每 5 s 一次），可以显著降低网络开销。

### 4.4 API 安全  

- **JWT**：登录后返回 `access_token`（15 min）+ `refresh_token`（7 days）。  
- **HTTPS**：所有入口强制 TLS。  
- **Rate Limiting**：基于 **IP+User** 的令牌桶，防止爬虫刷接口。  
- **权限校验**：微服务内部使用 **OPA（Open Policy Agent）** 或 **Istio RBAC**，确保用户只能操作自己的资源。  

---

## 第五步：详细组件设计  

### 5.1 用户认证与授权  

1. **注册** → 写入 MySQL `users` → 发送 **邮件/短信验证码** → 成功返回 JWT。  
2. **第三方 OAuth** → 使用 **Authorization Code Flow** → 通过 **Google/Apple** 换取 `id_token` → 在 **Auth Service** 验证后生成本平台 JWT。  
3. **Token 校验** → API Gateway 通过 **JWT 公钥**（JWK）快速验证，无需回源。  

> **不使用 JWT** 而是每次查询 DB 验证，会导致 **每次请求 DB**，吞吐大幅下降。  

### 5.2 大文件上传 & 转码  

#### 5.2.1 分片直传（S3 Multipart Upload）  

- 前端先向 **Upload Service** 请求 `upload_id`（包含目标 bucket、key、分片数）。  
- 前端分片（例如 10 MB/片）并 **并行上传** 至 S3。  
- 上传完成后前端调用 **CompleteMultipartUpload**，S3 返回 **ETag**。  
- **Upload Service** 收到完成回调后写入 `episodes` 表的 `status=uploaded`，并向 **Kafka** 发送 `episode_uploaded` 事件。  

> **不走直传**（先经后端转发）会让后端成为 **带宽瓶颈**，并且 **CPU/内存** 受限。  

#### 5.2.2 转码流水线  

- **Kafka** 消费 `episode_uploaded` → **Transcode Service** 拉取原始文件 → 使用 **FFmpeg**（或云转码服务）生成 **多码率（64k, 128k, 256k）**、**HLS/DASH** 切片（5 s/片）。  
- 转码后文件放到 **对象存储的 /transcoded/** 目录，生成 **M3U8/MPD** 播放清单。  
- 成功后更新 `episodes.status=available` 并发送 `episode_ready` 事件，供搜索、推荐系统同步。  

### 5.3 播放流控 & CDN  

1. **用户请求播放** → API Gateway 返回 **签名的 CDN URL**（包含时间戳、IP 哈希），防止盗链。  
2. **CDN Edge** 按 **HLS/DASH** 切片缓存，**首片**（~5 s）在 **边缘节点** 已有，确保 **<150 ms** 首帧。  
3. **分段预取**：客户端依据 **带宽自适应**（ABR），在播放第 N 段时提前请求 N+1、N+2 段。  
4. **限流**：在 Edge 通过 **Token Bucket** 防止单 IP 暴刷。  

> **如果不使用 CDN**，所有播放流量都会回源到对象存储 → **带宽成本爆炸**，且 **首帧延迟** 受跨洲网络影响。  

### 5.4 搜索与推荐  

- **写入路径**：业务服务写 MySQL → 发送 Kafka → **ES Sync Service**（消费） → **Elasticsearch** 索引。  
- **搜索 API**：使用 **multi_match**、**term**、**bool** 组合，实现 **关键字 + 标签 + 分类** 过滤。  
- **热榜**：每分钟使用 **ClickHouse** 对 `play_log` 做 **TOP N** 统计，结果写回 Redis 缓存，搜索 API 直接查询缓存。  
- **推荐**：提供 **推荐服务**（基于协同过滤或内容相似度），仅返回 **episode_id 列表**，前端自行调用 **episode/detail**。  

### 5.5 评论、点赞与审核  

1. **写入**：评论 → MySQL `comments`（写入后状态 `pending`） → 发送 `comment_created` 到 Kafka。  
2. **审核**：消费 `comment_created` → 调用 **文本审查**（如阿里云内容安全） → 结果 `approved`/`rejected`，更新 `comments.status`。  
3. **展示**：前端查询 `comments` 时只返回 `status=approved`，**点赞**直接写入 `likes` 表并同步 `like_count` 到 `comments`（使用 **MySQL 触发器** 或 **异步计数**）。  

> **不做异步审查** 而是同步阻塞，会导致 **评论延迟 >5 s**，用户体验极差。  

### 5.6 监控、日志、报警  

| 维度 | 工具 | 关键指标 |
|------|------|----------|
| **指标** | Prometheus + Grafana | QPS、RT、错误率、CPU/内存、磁盘 I/O |
| **链路追踪** | OpenTelemetry → Jaeger | 每条请求的微服务耗时、错误点 |
| **日志** | ELK (Filebeat → Logstash → Elasticsearch) | 接口访问日志、业务异常日志 |
| **告警** | Alertmanager + PagerDuty | 响应时间 >200 ms、错误率 >1% 等 |
| **容量** | Thanos / Cortex | 长期存储监控数据，做容量趋势预测 |  

### 5.7 灰度发布 & 蓝绿部署  

- **Kubernetes** + **Argo Rollouts**：支持 **Canary**（5%→50%→100%）或 **Blue/Green** 切换。  
- **Feature Flag**（LaunchDarkly / Unleash）：新功能（如评论审核）可以随时打开/关闭，降低风险。  

---

## 第六步：扩展性与高可用设计  

### 6.1 横向扩展（Scale‑out）  

| 组件 | 扩容方式 | 关键指标 |
|------|----------|----------|
| API Gateway | 增加实例 + **Anycast** DNS | 并发请求数 |
| Auth Service | 多副本 + Session‑less JWT | 登录 QPS |
| MySQL | **分库分表**（user_id、podcast_id）+ 主从复制 | 写入 TPS |
| Elasticsearch | 增加 **primary shards**，设置 **replica=2** | 搜索并发 |
| Redis | **Cluster**（分片）+ 主从复制 | 缓存命中率 |
| Kafka | 增加 **partition**，每个 consumer group 负载均衡 | 事件吞吐 |
| 对象存储 | 自动弹性（S3 本身） | 存储容量、带宽 |
| CDN | 扩容 Edge 节点（云厂商已自动） | 首帧延迟、带宽 |  

> **不做分片**（例如只在单库）会导致 **写入热点**，CPU/IO 很快到达瓶颈。  

### 6.2 高可用（HA）与容灾  

| 场景 | 方案 | RPO / RTO |
|------|------|-----------|
| **单点故障（服务实例）** | **K8s Deployment** + **Pod Auto‑restart**，Pod 失效自动调度到其他节点 | < 30 s |
| **数据中心故障** | **跨地域复制**：MySQL 多活（使用 **Vitess** 或 **TiDB**），对象存储 **CRR**，Elasticsearch **跨 AZ** 副本 | RPO 5 min（同步复制） |
| **网络分区** | **Client‑side重试** + **熔断**（Istio），自动切换到最近的可用区域 | RTO 1 min |
| **CDN 故障** | **多 CDN 供应商**（双线）+ **回源到对象存储** | RPO 0，RTO 1 min |
| **Kafka 分区失效** | **副本 ISR**（最小副本 3），自动 Leader 迁移 | RPO < 1 min |
| **搜索不可用** | **副本路由**（ES）+ **缓存热榜**（Redis）做降级 | RTO < 30 s |  

### 6.3 缓存与预取策略  

1. **热点节目/集** → 预热至 **Redis**（元数据）+ **CDN Edge**（音频切片）。  
2. **播放进度** → 存储在 **Redis**（TTL 24 h），定时刷写到 MySQL 防止数据丢失。  
3. **用户订阅列表** → 缓存 5 min，订阅变化时主动 **Cache‑Invalidation**。  

### 6.4 限流与防刷  

- **全局限流**：API Gateway 基于 **IP+User** 的令牌桶（如 10 QPS/用户）。  
- **业务层熔断**：Istio 对后端服务设置 **熔断阈值**（错误率 > 5% → 熔断 30 s）。  
- **验证码**：登录、注册、评论等高危操作使用 **CAPTCHA**。  

### 6.5 灾备演练  

- **每日**：模拟单 AZ 故障，验证自动切换。  
- **每周**：全链路压测（k6、Locust），验证 120k QPS、首帧 <150 ms。  
- **每月**：恢复演练（从备份恢复 MySQL、ES），检查 RPO/RTO。  

---

## 第七步：常见面试追问与回答  

### Q1️⃣ “如果我们要在 6 个月内把 DAU 提升到 50 M，存储和带宽需要如何扩容？”  

- **存储**：  
  - 现有 25 PB（含冗余）对应 30 M DAU。  
  - 按 **线性增长**，50 M → 约 **42 PB**（30 M → 25 PB, 1 M ≈ 0.83 PB）。  
  - 采用 **对象存储分层**：冷热分层（标准 + 低频）降低成本。  
  - **自动扩容**：S3/OSS 本身弹性，需提前预估 **计费预算**。  

- **带宽**：  
  - 峰值 QPS 从 120k → 200k（假设同等活跃比例）。  
  - 带宽 ≈ 200k × 250 kbps × 1.5 ≈ **75 Gbps ≈ 9.4 TB/s ≈ 15 Tbps**。  
  - **CDN** 按流量付费，需与 CDN 供应商协商 **峰值峰值带宽预留**。  
  - 在 **核心网络**（公网）使用 **多运营商 BGP 多线**，提升抗压。  

### Q2️⃣ “播放服务的容灾方案是怎样的？单点故障会怎样影响可用性？”  

- **服务层**：部署在 **Kubernetes** 多节点，Pod 自动恢复。  
- **数据层**：  
  - **对象存储** 跨 AZ 同步，任意单 AZ 故障仍可从其他 AZ 拉取音频。  
  - **Redis** 使用 **Cluster** + **哨兵**，主从切换时间 < 5 s。  
- **CDN**：若某 Edge 节点失效，流量自动路由到最近可用节点，首帧延迟可能略升但仍在 200 ms 内。  
- **故障影响**：若 **核心 API**（播放 URL 生成）单点故障，用户将得到 **5xx**，可用性下降。为防止，使用 **多副本**、**负载均衡**、**熔断降级**（返回缓存 URL），保证 **99.95%**。  

### Q3️⃣ “音频播放如何利用边缘缓存、分片下载、预取降低首帧延迟？”  

1. **分片（HLS/DASH）**：每段 5 s，首段在 CDN Edge 预热。  
2. **Edge Cache**：CDN 在 POP（点）缓存首段，用户请求后直接返回，避免回源。  
3. **预取**：客户端根据 **ABR** 逻辑提前请求第 N+1、N+2 段，确保播放时无需等待。  
4. **签名 URL + 失效时间**：防盗链的同时，让 CDN 能够缓存更长时间。  
5. **TCP + QUIC**：使用 **HTTPS/2** 或 **QUIC**（HTTP/3）降低握手时延，进一步压缩首帧时间。  

### Q4️⃣ “如果不使用消息队列，直接在业务服务里同步写 MySQL、ES、ClickHouse，会出现什么问题？”  

- **同步阻塞**：写入 MySQL 后立即调用 ES/ClickHouse，若任一服务卡顿，整个请求响应时间激增（>1 s），用户体验差。  
- **吞吐受限**：单请求必须等所有下游完成，导致 **QPS** 大幅下降。  
- **可靠性降低**：任何下游异常都会导致业务回滚，影响业务可用性。  
- **解耦缺失**：后续想新增统计、审计等功能需要改动业务代码，维护成本高。  

### Q5️⃣ “监控和报警体系怎么设计，才能快速定位故障？”  

- **指标收集**：每个微服务暴露 **Prometheus** 指标（请求数、成功率、延迟、错误码）。  
- **链路追踪**：使用 **OpenTelemetry** 在每个请求生成 **Trace ID**，在 Jaeger 中可视化调用链。  
- **日志统一**：所有服务通过 **Filebeat** 推送到 **ELK**，日志中包含 **trace_id**，方便关联。  
- **仪表盘**：Grafana 看板展示 **关键 KPI**（播放 QPS、首帧延迟、搜索 RT、错误率）。  
- **告警规则**：如 **RT > 200 ms**、**5xx 占比 > 0.5%**，通过 **Alertmanager** 推送到 Slack/DingTalk。  
- **故障定位流程**：告警 → 查看 Grafana → 查 Trace → 定位到具体服务 → 查看日志 → 迅速定位根因。  

---

## 心得与反思  

### 🎯 本题最难的 1–2 个设计决策  

| 决策 | 难点 | 思考过程 |
|------|------|----------|
| **大文件上传与转码** | 30 GB 单文件极大，若走后端会造成 **带宽、磁盘 I/O** 瓶颈；转码耗时长，需要 **异步** 处理。 | 先列出上传路径：<br>1️⃣ 前端直传 → S3 Multipart <br>2️⃣ 后端接收 → 需要巨额带宽 <br>最终选 **直传 + 事件驱动转码**，并通过 **Kafka** 解耦。 |
| **播放首帧延迟 <150 ms** | 音频文件体积大，网络跨洲，如何在用户感知层面做到毫秒级响应。 | 通过 **分片 (HLS/DASH)**、**CDN Edge 缓存**、**签名 URL**、**QUIC** 四层叠加：<br>① 把首段预热至 POP；② 客户端直连最近 POP；③ 使用二进制协议降低握手；④ 预取后续片段。 |

### 🚩 新手最容易犯的错误  

1. **忽视流量模型**：直接把所有请求都假设可以走单机，导致 **容量严重不足**。  
   - 纠正方式：先算 DAU、并发、QPS、带宽，再决定 **是否需要分库、分片、CDN**。  

2. **把所有业务都写进单体服务**：代码耦合、部署风险大、水平扩展困难。  
   - 纠正方式：从 **MVP** 起就划分 **核心业务微服务**（Auth、Podcast、Playback、Comment），并使用 **API Gateway** 统一入口。  

### 📚 学习建议与可延伸方向  

| 方向 | 推荐学习资源 | 关键点 |
|------|--------------|--------|
| **系统容量预估** | 《Designing Data‑Intensive Applications》章节、AWS Well‑Architected | 如何从业务指标推导存储、网络、CPU 需求。 |
| **微服务治理** | Istio 官方文档、Martin Fowler《Microservices》 | 服务网格、熔断、流量治理的实践。 |
| **流媒体协议** | Apple HLS、MPEG‑DASH 规范、Netflix Open‑Source “Open Connect” | 分片、ABR、CDN 边缘缓存原理。 |
| **大文件上传** | AWS S3 Multipart Upload、Google Cloud Storage Resumable Upload | 分块上传、断点续传、签名 URL。 |
| **实时统计** | ClickHouse 官方教程、Kafka + Flink 实战 | 高吞吐 ETL、实时 OLAP。 |
| **监控/可观测性** | Prometheus + Grafana、OpenTelemetry、Jaeger | 指标、日志、链路追踪的完整闭环。 |

> **核心思路**：先 **需求 → 流量模型 → MVP → 高可用**，每一步都要 **写出“为什么这样”，不这样会怎样**，面试官会看到你系统化的思考方式。  

祝你在面试中自信从容，设计出让面试官拍案叫好的播客平台！ 🎧🚀  
