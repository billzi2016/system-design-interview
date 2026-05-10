# 第 17 天：设计 Netflix

> 生成日期：2026-05-09

---

## 题目背景  
Netflix 是全球领先的在线视频流媒体平台，提供海量电影、电视剧、纪录片等内容的点播与推荐服务。用户通过网页、移动端或电视设备随时随地观看高清或超高清视频。

## 面试场景设定  
> **面试官**：  
> “我们现在要设计一个能够支撑全球数亿用户同时观看的 Netflix 系统。请你从高层次出发，说明系统的核心架构，并重点阐述以下几个方面：用户登录、内容目录查询、视频播放、个性化推荐以及离线下载。我们先从功能需求开始，你觉得最关键的功能有哪些？”  

（面试者开始回答后，面试官根据回答继续追问细节。）

## 功能性需求  

| 编号 | 功能描述 | 关键点 |
|------|----------|--------|
| 1 | **用户注册/登录** | 支持邮箱、手机号、第三方 OAuth 登录；多设备登录状态同步；安全防护（验证码、登录异常检测）。 |
| 2 | **内容浏览与搜索** | 电影/剧集的分类浏览、关键词搜索、过滤（类型、语言、分级）；返回带分页的元数据（封面、简介、评分、时长）。 |
| 3 | **视频点播 & 自适应流** | 支持 HTTP Live Streaming（HLS）/DASH；依据网络带宽动态切换码率（240p‑4K）；播放进度同步到云端。 |
| 4 | **个性化推荐** | 基于用户观看历史、评分、收藏、相似用户行为进行实时推荐；推荐列表实时刷新。 |
| 5 | **离线下载** | 允许在移动端下载加密视频文件，设定下载期限；支持断点续传、下载任务管理。 |
| 6 | **账户与计费** | 订阅套餐管理、计费周期提醒、自动续费、家庭成员共享。 |

## 非功能性需求  

| 指标 | 估算值 | 说明 |
|------|--------|------|
| **日活跃用户 (DAU)** | 2.5 亿 | 以全球市场为基准的高峰日。 |
| **每秒请求数 (QPS)** | 150,000 QPS | 包括登录、目录查询、播放清单、推荐等混合请求。 |
| **平均响应时延** | < 120 ms（查询/登录）<br/> < 300 ms（推荐） | 关键交互需在 200 ms 以内，播放请求（获取 m3u8）需在 300 ms 以内。 |
| **系统可用性** | 99.99%（每月累计停机 < 5 分钟） | 对用户体验极其关键，需多活灾备。 |
| **存储容量** | 100 PB 视频原始/转码文件 + 10 PB 元数据/日志 | 包含多码率转码、备份与 CDN 缓存。 |
| **带宽需求** | 峰值 20 Tbps（全球并发播放） | 假设 30% 的用户在高峰期观看 4K 视频（25 Mbps）。 |

## 系统边界  

**本题范围（需要设计）**  
- 用户身份认证与会话管理  
- 内容元数据服务（Catalog）  
- 视频分发与自适应流（包括 CDN 接入层）  
- 推荐系统的接口与缓存层（不要求实现完整机器学习模型）  
- 离线下载的授权、加密与下载管理  
- 计费与订阅状态的基本流程  

**不在本题范围（可忽略）**  
- 视频的版权采购、内容制作与编辑流程  
- 完整的机器学习模型训练与特征工程细节  
- 具体的硬件实现（如 GPU 编码集群）  
- 第三方广告业务、营销活动系统  
- 客服、工单系统、用户行为分析报表等后台运营功能  

## 提示与追问  

1. **缓存策略**：  
   - “在目录查询和推荐结果中，你会如何设计缓存层？请说明缓存粒度、失效策略以及如何保证缓存一致性。”  

2. **容错与灾备**：  
   - “面对单个数据中心故障，系统如何保证 99.99% 的可用性？请列出关键的冗余设计和故障转移流程。”  

3. **带宽优化**：  
   - “考虑到全球用户网络条件差异，你会如何在 CDN 与自适应流层面进一步降低播放卡顿率？”  

（面试官可以根据候选人回答，进一步追问数据分片、CAP 取舍、异步处理、监控告警等细节。）

---

# 题解

## 解题思路总览
> **目标**：帮助一位刚入行的后端同学，从需求拆解、容量估算、系统分层、数据库选型、接口设计、关键组件实现，到高可用与扩展性，完整地构建 **Netflix** 这样的大型点播系统的雏形。  
> **思路**：先搭建 **最小可用系统（MVP）**——只实现登录、目录查询、播放 URL 返回；再逐步加入 **推荐、离线下载、计费** 等业务，并在每一步说明 **为什么** 这样做、**不这样做** 会出现哪些问题。这样层层递进，读者能清晰看到每个决策背后的动机与权衡。

---

## 第一步：理解需求与规模估算

| 维度 | 关键点 | 初步估算 | 备注 |
|------|--------|----------|------|
| **用户** | DAU ≈ 2.5 亿，峰值并发 30% 同时观看 | 同时观看用户 ≈ 75 万 | 直接决定后端 QPS、缓存命中、CDN 带宽 |
| **业务请求** | 登录、目录查询、获取播放清单（m3u8）、推荐、下载授权 | QPS 150k（≈ 10% 登录、30% 目录、40% 播放、15% 推荐、5% 下载） | 先把最频繁的请求（目录、播放）做成 **读密集**，写操作相对少 |
| **存储** | 视频原始 + 多码率转码 ≈ 100 PB；元数据 ≈ 10 PB | 视频主要放对象存储 + CDN；元数据放关系/文档库 | 需要 **冷热分离**、**分片** |
| **时延要求** | 登录/查询 <120 ms，推荐 <300 ms，获取 m3u8 <300 ms | 需要 **缓存**、**局部性**（就近访问） | 设计时把热点数据放在内存层（Redis / CDN Edge） |
| **可用性** | 99.99%（月累计停机 <5 min） | 必须 **多活多地域**、**自动故障转移** | 关键服务（Auth、Catalog、Play）都要双活 |
| **安全** | OAuth、验证码、异常登录检测、下载文件加密 | 采用 **JWT + Refresh Token**，下载采用 **AES‑CTR + License Server** | 防止盗链、账号被劫持 |

> **容量估算公式**（供参考）  
> - **播放带宽** = 并发播放数 × 平均码率  
>   - 30% 4K (25 Mbps) + 50% 1080p (5 Mbps) + 20% 720p (2.5 Mbps) ≈ 20 Tbps 峰值  
> - **目录查询 QPS** ≈ 45k（30%） → 每次返回 ~ 10 KB → 450 MB/s ≈ 3.6 Gbps  
> - **登录 QPS** ≈ 15k → 1 KB/次 → 15 MB/s  

---

## 第二步：高层架构设计

### 1. 典型分层（从上到下）

```
┌─────────────────────────────┐
│   前端（Web / iOS / Android │
│   / TV）                     │
└───────▲───────▲───────▲───────┘
        │       │       │
   CDN Edge   API GW   DNS
        │       │       │
┌───────▼───────▼───────▼───────┐
│   业务层（微服务）            │
│  ├─ Auth Service              │
│  ├─ Catalog Service           │
│  ├─ Playback Service          │
│  ├─ Recommendation Service    │
│  ├─ Download Service          │
│  └─ Billing Service           │
└───────▲───────▲───────▲───────┘
        │       │       │
   Cache（Redis）   Message Queue（Kafka）
        │               │
┌───────▼───────▼───────▼───────┐
│   存储层                       │
│  ├─ Object Store (S3/OSS)      │
│  ├─ CDN（Akamai/CloudFront）    │
│  ├─ Relational DB (MySQL)      │
│  ├─ NoSQL DB (Cassandra)       │
│  └─ Search Engine (Elasticsearch)│
└─────────────────────────────┘
```

### 2. 为何采用微服务？

| 需求 | 微服务优势 | 不采用的风险 |
|------|-----------|-------------|
| **业务解耦**（登录、目录、播放） | 每个业务可以独立扩容、部署、升级 | 单体代码库膨胀，改动互相影响，部署风险大 |
| **团队协作** | 按业务划分团队，职责清晰 | 整体耦合导致团队冲突 |
| **弹性伸缩** | 热点业务（播放）单独扩容，目录查询只加缓存即可 | 资源浪费或热点压垮单点 |

### 3. 关键流路说明

| 场景 | 请求路径 | 关键组件 |
|------|----------|----------|
| **登录** | 前端 → API GW → Auth Service → DB/Cache → JWT 返回 | Auth Service、MySQL、Redis |
| **目录查询** | 前端 → API GW → Catalog Service → Cache → Search Engine → DB | Catalog Service、Redis、Elasticsearch |
| **获取播放清单** | 前端 → API GW → Playback Service → License Server → Object Store + CDN | Playback Service、Redis、License Server、S3/CDN |
| **推荐** | 前端 → API GW → Recommendation Service → Cache → DB/Message Queue | Rec Service、Redis、Cassandra、Kafka |
| **离线下载** | 前端 → API GW → Download Service → License Server → Object Store (加密) | Download Service、Redis、License Server、S3 |

---

## 第三步：数据库设计

### 1. 关系型数据库（MySQL）—— **用户、订阅、登录审计**

| 表名 | 主键 | 关键字段 | 说明 |
|------|------|----------|------|
| `users` | `user_id` (UUID) | `email`, `phone`, `password_hash`, `created_at` | 基本身份信息 |
| `auth_tokens` | `token_id` | `user_id`, `jwt_refresh_token`, `expires_at` | 存储 refresh token，便于失效 |
| `subscriptions` | `sub_id` | `user_id`, `plan_id`, `status`, `renewal_date` | 计费套餐 |
| `login_attempts` | `(user_id, ts)` | `ip`, `device`, `success` | 防暴力登录、异常检测 |

- **读写比例**：登录/计费写少、查询多 → **主从复制**（读从）  
- **分库**：按地区或用户 ID 前缀做水平分片，避免单库热点。

### 2. 文档/列式数据库（Cassandra）—— **视频元数据、观看历史**

| 表名 | 主键 | 关键列 | 说明 |
|------|------|--------|------|
| `videos` | `video_id` | `title`, `type`, `genres`, `duration`, `release_year`, `available_regions` | 只读、全局热点，适合宽列存储 |
| `video_assets` | `(video_id, bitrate)` | `cdn_url`, `size`, `codec` | 多码率映射 |
| `watch_history` | `(user_id, ts)` | `video_id`, `position`, `device` | 需要按用户查询，写频繁 |

- **写放大**：Cassandra 天然支持 **高写吞吐**，且 **线性扩展**。
- **一致性**：使用 **QUORUM** 读取，确保 2/3 副本同步，兼顾性能与可靠性。

### 3. 搜索引擎（Elasticsearch）—— **目录搜索 & 过滤**

- **索引字段**：`title`, `description`, `actors`, `genres`, `language`, `rating`, `release_year` 等。  
- **分片**：根据业务量（约 5 M 条视频）设 30 ~ 50 个主分片，每个副本 1 ~ 2。  
- **刷新频率**：新影片上线后 **实时**（5 s）刷新，老影片更新（元数据）采用 **批量更新**。

### 4. 缓存层（Redis Cluster）

| 缓存键 | 示例 | TTL | 用途 |
|--------|------|-----|------|
| `auth:session:{user_id}` | `auth:session:1234` | 30 min | 保存 JWT 解析后信息，快速鉴权 |
| `catalog:page:{region}:{page}` | `catalog:page:US:5` | 5 min | 目录分页结果 |
| `recommend:user:{user_id}` | `recommend:user:1234` | 1 min | 推荐列表，热点用户短暂缓存 |
| `playback:url:{video_id}:{profile}` | `playback:url:vid567:1080p` | 10 min | 已签名的 CDN URL（带 token） |

- **失效策略**：热点目录 5 min，推荐 1 min，避免 **缓存雪崩**（使用 **随机过期**）。
- **一致性**：写后 **Cache‑Aside**：先写库，再删除对应缓存键，下一次读自动回填。

---

## 第四步：核心 API 设计

> **原则**：RESTful + JSON，统一返回结构，所有写操作必须通过 **POST/PUT**，读操作使用 **GET**，分页采用 **cursor** 或 **page token**。

| 方法 | 路径 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| `POST` | `/api/v1/auth/login` | 邮箱/手机号/第三方登录 | `{type:"email", identifier:"a@b.com", password:"***", device:"iPhone13"}` | `{access_token, refresh_token, expires_in}` |
| `POST` | `/api/v1/auth/refresh` | 刷新 JWT | `{refresh_token}` | `{access_token, expires_in}` |
| `GET` | `/api/v1/catalog/videos` | 列表/搜索，支持 `q`, `genre`, `lang`, `page_token` | - | `{videos:[...], next_page_token}` |
| `GET` | `/api/v1/catalog/video/{video_id}` | 单条视频元数据 | - | `{video_id, title, description, ...}` |
| `GET` | `/api/v1/playback/{video_id}` | 获取自适应流 m3u8（带签名） | `?profile=auto&device=web` | `{m3u8_url, expires_at}` |
| `GET` | `/api/v1/recommendations` | 获取个性化推荐 | `?page=1&size=20` | `{items:[...], next}` |
| `POST` | `/api/v1/downloads` | 发起离线下载任务 | `{video_id, profile, device_id}` | `{task_id, status, expires_at}` |
| `GET` | `/api/v1/downloads/{task_id}` | 查询下载进度 | - | `{status, progress, url}` |
| `POST` | `/api/v1/billing/subscribe` | 订阅套餐 | `{plan_id, payment_method}` | `{sub_id, status, next_billing}` |

**鉴权**：所有除 `/login`、`/refresh` 外的 API 必须在 **HTTP Header** 中携带 `Authorization: Bearer <access_token>`，网关统一校验 JWT（签名、过期）并写入 `user_id` 到请求上下文。

---

## 第五步：详细组件设计

### 1. Auth Service（登录、会话）

- **技术栈**：Spring Boot / Go + gRPC，部署在容器（K8s）。
- **流程**：
  1. 接收登录请求 → 根据 `type` 调用对应 **OAuth Provider**（Google、Apple）或内部密码校验。
  2. 通过 **验证码/风控**（Redis 计数器 + 机器学习模型）阻止暴力登录。
  3. 登录成功后生成 **JWT**（HS256）+ **Refresh Token**（随机 UUID），写入 `auth_tokens` 表。
  4. 将 JWT 解析信息写入 **Redis** `auth:session:{user_id}`，TTL 30 min，便于后续快速鉴权。
- **防止会话劫持**：在 JWT 中加入 `device_id`、`ip_hash`，每次请求对比。

### 2. Catalog Service（目录查询）

- **读写分离**：写操作（新增影片）走 **MySQL → Elasticsearch** 同步；读操作全走 **Redis + ES**。
- **缓存策略**：
  - **热点地区/分类**（如美国‑动作片）预热到 Redis。
  - **分页缓存**：`catalog:page:{region}:{genre}:{page}`，TTL 5 min。
- **实现要点**：
  - **Search API** 调用 ES，返回 **doc_id** 列表 → 再批量从 **Cassandra** (`videos`) 拉取完整元数据，避免 ES 存储大字段。
  - **过滤**（地区版权）在 DB 层完成，确保不返回未授权内容。

### 3. Playback Service（自适应流）

- **核心职责**：
  - 根据用户的网络带宽、设备能力返回 **适配的 m3u8**。
  - 生成 **带时效签名的 CDN URL**（防盗链）。
  - 同步播放进度至 `watch_history`。
- **自适应码率**（HLS/DASH）：
  - 视频在 **对象存储** 中已转码为多码率 **segment**（.ts / .m4s）。
  - **Manifest** (`master.m3u8`) 存放在 CDN，内部引用 **signed URLs**。
- **实现步骤**：
  1. 前端请求 `/playback/{video_id}`，携带 **access_token**。
  2. Service 根据 **User-Agent** 与 **历史带宽**（Redis `user:bandwidth:{user_id}`）选取默认 profile。
  3. 调用 **License Server** 生成 **token**（AES‑CTR 加密的播放许可证），写入 **Redis** `playback:token:{video_id}:{user_id}`（TTL 10 min）。
  4. 拼装 **m3u8 URL**：`https://cdn.example.com/{video_id}/master.m3u8?token=xxxx` 返回给前端。
  5. 前端播放时，播放器每次请求 segment 时会携带 `token`，CDN Edge 验证后返回对应片段。

### 4. Recommendation Service（个性化推荐）

- **架构**：**离线模型 + 实时召回**  
  - 离线：每天跑 **Spark** / **Flink** 生成用户‑物品相似度向量，写入 **Cassandra** `user_recs` 表（每用户 100 条推荐）。
  - 实时：使用 **Kafka** 收集用户点击/播放事件，更新 **Redis** `user:recent:{user_id}`（最近 20 条），在 API 层做 **热点混排**（推荐 + 实时）。
- **缓存**：`recommend:user:{user_id}`，TTL 1 min。若缓存未命中，后端直接查询 `user_recs` 表 + `watch_history` 做排序。
- **降级策略**：若模型服务不可用，直接返回 **热门榜单**（从 Redis `global:hot`）。

### 5. Download Service（离线下载）

- **安全模型**：
  - 下载文件在对象存储中 **加密**（AES‑CTR）且 **只能通过 License Server** 获取解密密钥。
  - 客户端发起下载请求后，后端返回 **一次性签名 URL**（有效期 10 min），并记录下载任务状态。
- **断点续传**：
  - 使用 **HTTP Range** 头部；对象存储（S3）天然支持。
  - 前端保存 `task_id` 与已下载的 `byte_range`，下次启动继续请求。
- **下载期限**：License Server 为每个 `task_id` 生成 **DRM license**，有效期 48 h，过期自动失效。

### 6. Billing Service（计费与订阅）

- **核心流程**：
  1. 前端提交订阅请求 → 调用 **Payment Provider**（Stripe、PayPal）进行授权。
  2. 支付成功回调 → 在 **MySQL** `subscriptions` 创建记录，状态 `ACTIVE`。
  3. 生成 **账单事件** 写入 **Kafka** `billing_events`，供后续 **计费统计** 与 **邮件通知** 消费。
- **容错**：支付回调 **幂等**（使用 `order_id` 唯一键），防止重复计费。

---

## 第六步：扩展性与高可用设计

### 1. 多活多地域部署（99.99% 可用性）

| 层级 | 冗余方案 | 故障转移机制 |
|------|----------|--------------|
| **DNS** | 多地区 Anycast DNS（Route53、Cloudflare） | 健康检查失效后自动切到其他节点 |
| **CDN Edge** | 多 CDN 供应商（Akamai + CloudFront） | 边缘节点故障自动回源至最近节点 |
| **API Gateway** | 部署在每个地域的 **NGINX/Envoy** + **Global Load Balancer** | 健康检查不通过则把流量切到别的地域 |
| **服务实例** | K8s **Region‑wide** 集群 + **Cluster‑wide** Federation | Pod 死亡自动重调度；跨地域使用 **Istio**/**Linkerd** 的 **failover** |
| **数据库** | **MySQL** 主主复制（双活） + **Cassandra** 多DC（跨地域） | 故障时切换读写到存活 DC，使用 **Paxos** 保证一致性 |
| **缓存** | **Redis Cluster** 多 AZ 部署，采用 **CRDT**（如 Redis‑Raft） | 单节点失效不影响整体读写 |
| **消息队列** | **Kafka** 多集群（每个地域），使用 **MirrorMaker** 复制 | 生产者写到本地集群，消费者可跨地域消费 |

### 2. 容错策略

- **超时/熔断**：在服务间调用使用 **Hystrix/Resilience4j**，超时 100 ms，连续错误 > 5 次自动熔断，返回 **降级数据**（如热门榜单）。
- **幂等写**：所有写入（登录、订阅、下载任务）都使用 **唯一业务键**（如 `order_id`、`task_id`）作幂等控制，防止网络重试导致重复数据。
- **回滚/补偿**：使用 **Saga** 模式管理跨服务事务（例如：订阅 → 支付 → 生成 License），一旦任一步骤失败执行补偿（撤销支付、关闭订阅）。

### 3. 带宽与卡顿优化

| 优化点 | 具体实现 |
|--------|----------|
| **自适应码率** | 客户端实时上报下载速度 → Playback Service 动态切换 `profile`（ABR）。 |
| **多 CDN** | 根据用户 IP 与 ISP 匹配最近 Edge；在 Edge 节点启用 **TCP Fast Open**、**QUIC**（HTTP/3）降低握手时延。 |
| **预取** | 当用户暂停或快进时，客户端提前请求后续 segment；在 Playback Service 为 **热点片段** 加 **Warm Cache**（Edge 缓存）。 |
| **压缩/编码** | 对 240p‑480p 使用 **AV1**，对 4K 使用 **HEVC/H.265**，降低带宽占用。 |
| **网络探测** | 首次播放前通过小文件测 RTT、丢包率，决定初始码率，避免首帧卡顿。 |

### 4. 监控、日志与告警

- **指标**（Prometheus）：`auth_success_qps`, `catalog_latency_ms`, `playback_404_rate`, `cdn_hit_ratio`, `cpu_mem_usage`。
- **日志**（ELK）：统一结构化日志，关键字段 `user_id`, `request_id`, `trace_id`，便于 **Trace**（Jaeger）定位跨服务延迟。
- **告警**（PagerDuty）：阈值如 **99% latency > 200 ms**、**CPU > 80%（5min）**、**CDN miss ratio > 10%**。

---

## 第七步：常见面试追问与回答

### Q1️⃣ 缓存策略——目录查询与推荐结果的缓存怎么设计？

**答案要点**：

1. **目录查询**  
   - **粒度**：分页 + 地区 + 过滤条件（`catalog:page:{region}:{genre}:{page}`）。  
   - **TTL**：5 min（热门页面）+ **随机抖动**（10 %）防止雪崩。  
   - **失效**：新增/下架影片时，主动 **删除对应 region** 的缓存键 → **Cache‑Aside**。  
   - **一致性**：因为目录对业务影响不大（短暂的 5 min 旧数据可接受），采用 **最终一致**。

2. **推荐结果**  
   - **粒度**：用户级别（`recommend:user:{user_id}`）+ **全局热点**（`global:hot`）。  
   - **TTL**：1 min（实时性要求），热点推荐每分钟刷新一次。  
   - **失效**：用户行为（观看、评分）写入后 **主动删除** 对应缓存。  
   - **一致性**：推荐系统本身有 **离线批处理 + 实时增量**，所以缓存失效后马上会重新计算。

3. **防止缓存击穿**  
   - **热点键**使用 **互斥锁**（Redis `SETNX`）或 **双写**（先返回空结果，再异步回填）。  
   - **热点预热**：在每日高峰前，利用 **Cron** 将热门页面/推荐写入缓存。

---

### Q2️⃣ 容灾方案——单个数据中心故障时如何保证 99.99% 可用？

**答案要点**：

| 关键组件 | 冗余方式 | 故障检测 & 自动切换 |
|----------|----------|---------------------|
| **DNS / Global Load Balancer** | Anycast + 多地区 IP | 健康检查失效后立即把流量路由到其它地区 |
| **API Gateway** | 同步部署在每个地域的 Envoy | K8s **Readiness Probe** 失效后 Service 自动剔除 |
| **Auth / Catalog / Playback Service** | 多副本、跨 AZ、跨地域的 K8s 部署 | Pod 死亡 → 自动重调度；节点失效 → Service 重新负载均衡 |
| **MySQL** | 主‑主双活（Region A ↔ Region B） + 自动复制 | 当 Region A 无法写入，自动把写流切到 Region B（使用 HAProxy） |
| **Cassandra** | 多 DC（每个 Region 一个 DC），采用 **NetworkTopologyStrategy** | 读取采用 **LOCAL_QUORUM**，只要本地 DC 仍有多数副本即可 |
| **Redis** | 多 AZ Cluster + **Redis‑Raft**（CRDT） | 单节点挂掉，其他节点继续提供读写 |
| **Kafka** | 多集群 MirrorMaker 同步 | 消费者自动切换到可用集群 |
| **CDN** | 多供应商 + Edge 冗余 | 边缘节点失效时自动回源至最近可用节点 |

- **RTO（恢复时间目标）**：< 30 s（自动路由），**RPO（数据丢失）**：0（双写同步）。
- **演练**：每月进行一次 **Chaos Engineering**（如使用 Gremlin）模拟数据中心失效，验证切换时间。

---

### Q3️⃣ 带宽优化——如何降低不同网络条件下的卡顿？

**答案要点**：

1. **多码率自适应**（HLS/DASH） + **ABR**（客户端实时切换）。
2. **Edge Cache Warmup**：在 CDN Edge 预先缓存每部影片的 **首 2 min**，因为用户常在开头卡顿。
3. **TCP/QUIC 优化**：在 CDN Edge 开启 **HTTP/3 (QUIC)**，减少握手次数；对移动网络启用 **TLS Session Resumption**。
4. **网络探测**：客户端在播放前下载 **probe** 文件（10 KB），测 RTT 与丢包率，返回给 Playback Service 设定 **初始码率**。
5. **动态分片大小**：低带宽下使用 **2 s** 小片段，快速切换；高带宽下使用 **6 s** 大片段，降低请求次数。
6. **区域带宽调度**：在热点地区（如印度）部署 **本地对象存储**（Edge S3），降低跨境链路耗时。

---

### Q4️⃣ 数据一致性——为什么用户的观看历史会使用 **Cassandra** 而不是 MySQL？

**答案要点**：

- **写吞吐**：观看历史是 **高频写**（每播放一次都会写进度），Cassandra 能做到每秒几万写，且写延迟毫秒级。
- **水平扩展**：用户量达数亿，单库 MySQL 难以水平分片并保持低延迟；Cassandra 天然 **无中心节点**，可以随时添加节点。
- **查询模式**：主要是 **按用户查询最近 N 条**，使用 **主键 (user_id, ts)** 即可高效检索，适合宽列模型。
- **一致性需求**：观看进度只要求 **最终一致**（几秒内同步即可），不需要强事务，Cassandra 的 **QUORUM** 已足够。

---

### Q5️⃣ 如何防止缓存雪崩与击穿？

**答案要点**：

- **随机失效**：TTL 加随机数（如 `TTL = base + random(0, 30)`），防止大量键同一时刻失效。
- **互斥锁**：当缓存未命中且后端查询耗时较长，使用 **Redis 分布式锁**（`SETNX`）让只有一个请求去查询 DB，其他请求返回 **降级数据** 或 **短暂等待**。
- **热点预热**：利用 **定时任务**（Cron）在高峰前把热点目录、推荐写入缓存。
- **多级缓存**：本地（nginx/edge） + 集群（Redis） + DB，多层次命中提升整体命中率。

---

## 心得与反思

### 1. 本题最难的设计决策

| 决策 | 为什么难 | 思考过程 |
|------|----------|----------|
| **全局多活 vs. 数据一致性** | 需要在 **可用性 99.99%** 与 **跨地域数据强一致** 之间做权衡。强一致会导致跨洲同步延迟（>200 ms），影响用户登录/计费；而放宽一致性又可能出现 **订阅状态不同步** 的风险。 | 先明确业务哪块必须强一致（计费、登录 token），这些放在 **双活 MySQL**（同步复制 + 自动故障转移）。其余（观看历史、推荐）使用 **最终一致**（Cassandra、Kafka）。通过 **CAP** 取舍，把强一致性限制在最关键业务上。 |
| **自适应流与 DRM 的统一设计** | 需要兼顾 **低延迟**、**防盗链**、**跨平台**（Web、iOS、Android、TV）以及 **离线下载**（加密存储）四大需求。 | 先拆解为三层：① **License Server**（生成短期 token、加密密钥），② **CDN Edge**（校验 token，返回加密 segment），③ **客户端 DRM**（解密播放或下载）。在此基础上，统一使用 **AES‑CTR + HLS/DASH**，把不同平台的差异抽象成 **License API**，这样既保证安全，又不影响 ABR 逻辑。 |

### 2. 新手最容易犯的错误（至少两条）

| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把所有业务都放在单体服务** | 难以水平扩容，单点故障导致全站不可用；代码维护成本爆炸。 | 按业务拆分为 **微服务**（Auth、Catalog、Playback 等），每个服务独立部署、独立扩容。 |
| **忽视缓存失效导致的数据不一致** | 用户新加片段或下架影片仍能在列表中出现，影响用户体验和版权合规。 | 采用 **Cache‑Aside** 模式：写库后 **立即删除/更新对应缓存键**，并使用 **TTL + 随机抖动** 防止雪崩。 |
| **只考虑单地域部署，忽略 CDN 与边缘优化** | 全球用户访问延迟高，播放卡顿，业务 QPS 受限。 | 在 **CDN Edge** 部署 HLS/DASH Manifest，使用 **就近节点**、**HTTP/3**，并在 Edge 做 **token 验证**。 |
| **对计费采用弱一致模型** | 可能出现重复扣费或漏费，法律风险。 | 计费业务必须使用 **强一致**（双活 MySQL + 事务），并对外提供 **幂等 API**。 |

### 3. 学习建议和可延伸方向

1. **系统设计基础**  
   - 阅读《系统架构：从概念到实践》《Designing Data‑Intensive Applications》了解 **CAP、分区、事务** 的基本概念。  
   - 做 **CAP 取舍** 的练习：列举业务场景，判断是 **CP** 还是 **AP** 更合适。

2. **微服务实战**  
   - 学习 **Spring Cloud**、**Go‑kit**、**Kubernetes**，练习 **服务注册/发现、熔断、链路追踪**。  
   - 在本地搭建 **Docker‑Compose** 环境，分别实现 **Auth**、**Catalog**、**Playback**，体会 **接口契约** 与 **版本演进**。

3. **大数据与推荐**  
   - 了解 **Spark/Flink** 批/流处理，尝试在 **Kaggle** 上实现一个 **协同过滤** 推荐模型。  
   - 学习 **Kafka** 的 **Exactly‑Once** 语义，掌握 **消费者组** 与 **分区** 的概念。

4. **CDN 与媒体传输**  
   - 熟悉 **HLS、DASH** 协议细节（manifest、segment、AES‑128 加密）。  
   - 实践 **FFmpeg** 转码、**Apple Media Services**（FairPlay）或 **Widevine**（Google） DRM 流程。

5. **容灾演练**  
   - 使用 **Chaos Monkey**、**Gremlin** 做 **故障注入**，验证 **自动故障转移** 与 **监控告警**。  
   - 学习 **SLA/SLO/SLI** 的定义与监控实现，确保系统可观测。

> **一句话总结**：系统设计的核心是 **先抽象业务边界、再划分服务、最后围绕可用性、扩展性、性能、成本四大维度进行权衡**。只要把每一步的“为什么”说清楚，面试官会看到你对系统整体的把控能力，而不是单纯的技术堆砌。

祝你在面试中 **从容应对**，把思路条理化、决策理性化，成功拿下高质量的 Netflix 设计题！ 🎉
