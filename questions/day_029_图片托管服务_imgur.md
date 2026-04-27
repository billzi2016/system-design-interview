# 第 29 天：设计 图片托管服务（Imgur）

> 生成日期：2026-04-27

---

# 系统设计面试题 – 图片托管服务（Imgur）

## 1️⃣ 题目背景
Imgur 是一个面向大众的图片托管平台，用户可以上传、浏览、分享和管理图片。系统需要支撑海量图片的存储与高并发访问，同时提供快速、可靠的浏览体验。

## 2️⃣ 面试场景设定
> **面试官**：*“我们现在要设计一个类似 Imgur 的图片托管服务。请你从零开始构思系统的整体架构，重点说明如何满足高并发的图片上传/下载、海量存储以及高可用性。我们可以先从核心功能和关键指标开始讨论。”*

## 3️⃣ 功能性需求（Core Functional Requirements）

| 编号 | 功能描述 |
|------|----------|
| **F1** | **图片上传**：用户可以通过网页或 API 上传单张或多张图片，支持常见图片格式（JPEG、PNG、GIF、WEBP），单张图片大小 ≤ 20 MB。 |
| **F2** | **图片浏览/下载**：提供公开链接（短链）供任意用户访问图片，支持原图和多种压缩/缩放后的尺寸（如 thumbnail、medium、large）。 |
| **F3** | **图片管理**：用户可以对自己上传的图片进行删除、重命名、添加/编辑标签、设置公开/私有。 |
| **F4** | **分享与嵌入**：生成可直接在外部站点嵌入的 Markdown/HTML 链接，并提供短链/二维码。 |
| **F5** | **搜索/过滤**：基于标签、上传时间、热门度等维度搜索图片。 |
| **F6** | **用户鉴权**：注册/登录（邮箱+密码、OAuth 第三方），以及基于 token 的 API 访问控制。 |

> **可选**：如果时间充裕，可讨论 **图片批量编辑**（如添加水印）或 **内容审核**（敏感图检测）等扩展功能。

## 4️⃣ 非功能性需求（Key Non‑Functional Requirements）

| 编号 | 指标 | 估算值（目标） |
|------|------|----------------|
| **N1** | **日活跃用户（DAU）** | 2 M（峰值） |
| **N2** | **图片上传 QPS** | 1 500 req/s（峰值） |
| **N3** | **图片下载 QPS** | 30 000 req/s（峰值） |
| **N4** | **平均响应延迟** | 读取 < 150 ms（95% 请求），写入 < 300 ms |
| **N5** | **可用性** | 99.9% 月可用率（MTTR ≤ 10 min） |
| **N6** | **存储规模** | 100 PB（5 年增长，假设 50 B 图片/日，平均 2 MB/图） |
| **N7** | **数据一致性** | 最终一致性对图片元数据，强一致性对用户鉴权信息。 |

## 5️⃣ 系统边界（Scope & Out‑of‑Scope）

**本题范围内**（需考虑设计）：  
- 图片的上传、存储、分发、访问控制与 CDN 加速。  
- 元数据管理（标签、状态、权限）。  
- 基础的用户鉴权与配额（如每日上传上限）。  
- 高可用架构（多活、灾备、自动扩容）。  

**本题范围外**（可不必深入）：  
- 细粒度的内容审核（机器学习模型训练、审计）。  
- 复杂的社交功能（点赞、评论、关注）。  
- 高级图像处理（实时滤镜、AI 生成）。  
- 计费/付费会员体系。  
- 多语言国际化 UI。

## 6️⃣ 提示与追问（Possible Follow‑up Questions）

1. **“如果要把图片分布到全球用户，你会怎样设计 CDN 与存储层的协同工作？”**  
   - 期待讨论多层缓存、边缘节点选址、热点图片分层存储等。

2. **“在高并发上传场景下，如何避免热点写入导致的磁盘/网络瓶颈？”**  
   - 可引导到分片上传、写入队列、分布式对象存储（如 S3/MinIO）和限流策略。

3. **“当用户请求删除图片时，如何保证在 CDN、对象存储以及数据库之间的数据一致性？”**  
   - 关注软删/硬删、异步失效、TTL、消息队列驱动的删除流水线等。

---

# 题解

# 系统设计面试题 – 图片托管服务（Imgur）

> **写给新手的手把手指南**  
> 本文从 **最小可用系统（MVP）** 出发，层层递进到 **高可用、全球化分布式架构**，每一步都解释「为什么要这么做」以及「不这么做会有什么后果」。希望能帮助你在面试中条理清晰、思路完整地阐述方案。

---

## ## 解题思路总览

| 步骤 | 目标 | 关键输出 |
|------|------|----------|
| 1️⃣ | **理解需求**：梳理功能、非功能、约束，做流量/存储预估 | 需求清单、指标表、流量模型 |
| 2️⃣ | **高层架构**：画出系统的主要组件及交互 | 高层图、组件职责说明 |
| 3️⃣ | **数据库设计**：选择合适的数据模型，划分读写 | ER 图、表结构、分区/索引方案 |
| 4️⃣ | **核心 API**：定义上传、下载、管理等入口 | API 接口文档（REST/HTTPS） |
| 5️⃣ | **详细组件设计**：深入每个模块（API Server、对象存储、CDN、缓存、队列等） | 时序图、技术选型、实现细节 |
| 6️⃣ | **扩展性 & 高可用**：横向扩容、容灾、监控、限流 | 多活部署、灾备、弹性伸缩方案 |
| 7️⃣ | **面试追问**：准备常见的细化问题 | Q&A 列表 |
| 8️⃣ | **心得与反思**：总结难点、常见错误、学习路线 | 经验总结 |

> **思路提示**：先把 **「能跑通最基本功能」** 的系统搭好（单机 + 本地磁盘），再一步步 **拆分瓶颈**、**加缓存**、**加分片**、**加多活**。每一次拆分都对应一个非功能指标的提升。

---

## ## 第一步：理解需求与规模估算

### 1️⃣ 功能性需求（Core Functional Requirements）

| 编号 | 关键点 | 实现要点 |
|------|--------|----------|
| **F1** | 图片上传（单/多、≤20 MB） | 支持 multipart/form-data、分块上传、速率限制 |
| **F2** | 浏览/下载（原图+多尺寸） | 生成多分辨率的衍生图，返回短链 |
| **F3** | 图片管理（删/改/标签/权限） | 软删 + 任务队列异步硬删 |
| **F4** | 分享嵌入（Markdown/HTML、二维码） | 短链服务、QR 生成微服务 |
| **F5** | 搜索/过滤 | 基于标签/时间/热度的倒排索引 |
| **F6** | 用户鉴权 | 注册/登录、OAuth、JWT/Session、RBAC |

> **为什么要列出要点**：面试官会追问每个功能的实现细节，提前准备能帮助你快速切入。

### 2️⃣ 非功能性需求（Key Non‑Functional Requirements）

| 编号 | 指标 | 目标 | 可能的瓶颈 |
|------|------|------|------------|
| **N1** | DAU | 2 M 峰值 | Web 服务器并发、会话存储 |
| **N2** | 上传 QPS | 1 500 req/s | 网络入口、对象存储写入、病毒/内容检测 |
| **N3** | 下载 QPS | 30 000 req/s | CDN、对象存储读、缓存命中率 |
| **N4** | 延迟 | 读取 <150 ms (95%)、写入 <300 ms | 缓存层、磁盘 I/O、跨区网络 |
| **N5** | 可用性 | 99.9% 月可用 (MTTR ≤10 min) | 单点故障、部署/升级 |
| **N6** | 存储规模 | 100 PB (5 年) | 存储扩容、冷热分层 |
| **N7** | 数据一致性 | 最终一致（元数据），强一致（鉴权） | 数据库复制延迟、缓存失效 |

### 3️⃣ 粗略流量 & 存储估算

| 项目 | 计算方式 | 结果 |
|------|----------|------|
| **每日上传图片数** | 2 M DAU × 0.5 上传率 × 2 张/用户 ≈ 2 M 张/日 | 2 M |
| **每日产生数据量** | 2 M 张 × 2 MB ≈ 4 TB | 4 TB/日 |
| **5 年累计** | 4 TB × 365 × 5 ≈ 7.3 PB（实际因压缩、删除等 ~5 PB） | 与 N6 接近 |
| **下载请求** | 30 k QPS × 86 400 s ≈ 2.6 B 次/日 | 需要 CDN 缓解 |
| **上传峰值** | 1 500 req/s × 20 MB ≈ 30 GB/s 上传流量（网络入口） | 需要负载均衡 + 限流 |

> **不做估算的后果**：在面试中容易被认为“只会写代码”，缺乏系统思考。估算帮助你说明 **为什么要使用 CDN、分片存储、水平扩容**。

---

## ## 第二步：高层架构设计

### 1️⃣ 最小可用系统（MVP）结构

```
[Client] -> (HTTPS) -> [Load Balancer] -> [API Server] -> [Object Storage (本地磁盘)]
                                          |
                                          -> [Metadata DB (单实例 MySQL)]
```

- **API Server** 负责上传/下载/管理接口。  
- **Object Storage** 直接使用文件系统或 MinIO（S3 兼容）保存原图与衍生图。  
- **Metadata DB** 保存用户、图片元信息、标签等。  

> **为什么这样**：  
- 只用一套技术栈，快速实现 **可跑通**。  
- 可以在本地机器上演示完整流程，面试官可以直接看到思路。  

> **不这样** 的问题：  
- 单点故障、无法支撑高并发、缺乏缓存导致延迟大。

### 2️⃣ 扩展到生产级别的高层架构

```
                           +-------------------+
                           |   Global CDN      |
                           +--------+----------+
                                    |
          +-----------+   HTTPS   +-----------+   HTTPS   +-----------+
          |   DNS/   +----------->|  LB (Any)  +----------->|  API GW   |
          |   GeoDNS |            +-----+-----+            +-----+-----+
          +----+------+                  |                        |
               |                       |                        |
      +--------v--------+      +-------v------+        +--------v--------+
      |  Edge Cache (Varnish/Redis) |  Auth Service |   |  Rate Limiter   |
      +--------+--------+      +-------+------+        +--------+--------+
               |                       |                        |
   +-----------v-----------+   +-------v------+   +-------------v--------------+
   |   Upload Service      |   |  User Service|   |  Image Processing Service |
   +-----------+-----------+   +------+-------+   +-------------+------------+
               |                      |                         |
   +-----------v-----------+  +-------v------+        +----------v-----------+
   |  Object Store (S3)    |  |  Metadata DB |        |  Search Index (ES)  |
   +-----------+-----------+  +-------+------+        +---------------------+
               |                      |
   +-----------v-----------+  +-------v------+
   |  Message Queue (Kafka)|  |  Cache (Redis)|
   +-----------------------+  +---------------+
```

#### 关键组件解释

| 组件 | 作用 | 为什么要加 |
|------|------|------------|
| **DNS/GeoDNS** | 将用户请求路由到最近的入口 | 降低网络 RTT，提升可用性 |
| **Load Balancer (L4/L7)** | 分发流量、做健康检查、TLS 终止 | 防止单点、实现弹性伸缩 |
| **CDN** | 静态图片（原图、衍生图）边缘缓存 | 大幅降低下载 QPS 对后端的压力，满足 N3 |
| **API Gateway** | 统一入口、统一鉴权、限流、日志 | 简化后端服务，统一治理 |
| **Auth Service** | 用户注册/登录、Token 发放、RBAC | 强一致性需求（N7） |
| **Rate Limiter** | 防止恶意刷流、保护后端 | 保障系统稳定性 |
| **Upload Service** | 处理 multipart、分块上传、病毒/敏感内容检查 | 分担 API Server 业务，提升写入吞吐 |
| **Object Store (S3/MinIO)** | 海量对象存储，提供分片、冗余、版本控制 | 满足 N6 大规模存储需求 |
| **Metadata DB** | 关系型存储图片元信息、用户信息 | 强一致性需求 |
| **Cache (Redis)** | 热门图片元数据、短链映射、鉴权缓存 | 降低 DB 读延迟，满足 N4 |
| **Message Queue (Kafka)** | 异步任务（图片压缩、删除、索引） | 解耦写入路径、实现最终一致性 |
| **Image Processing Service** | 生成 thumbnail、medium、large，添加水印 | 业务必需的后台处理 |
| **Search Index (Elasticsearch)** | 支持标签、时间、热度的搜索 | 高效全文/倒排查询 |
| **Edge Cache (Varnish/Redis)** | 对短链的 302 重定向结果做缓存 | 再次提升下载命中率 |

> **不做这些组件** 的后果：  
- 直接从对象存储读取会导致 **30k QPS** 时出现 **网络瓶颈**、**磁盘 I/O** 饱和。  
- 没有缓存会导致 **元数据查询** 频繁打到 MySQL，出现 **读写竞争**。  
- 没有 CDN，用户跨地域访问延迟可能高达 **300 ms+**，不满足 N4。

---

## ## 第三步：数据库设计

### 1️⃣ 选型原则

| 数据类型 | 推荐存储 | 理由 |
|----------|----------|------|
| **用户信息、鉴权** | **关系型数据库 (MySQL / Aurora)** | 需要 **强一致性**、事务支持（注册、登录、配额） |
| **图片元数据（ID、URL、尺寸、标签、状态）** | **关系型 + Elasticsearch** | 结构化查询 + 搜索（倒排） |
| **短链映射** | **Key‑Value (Redis)** | 高读、低延迟，TTL 支持 |
| **大规模对象** | **对象存储 (S3/MinIO)** | 支持 **PB 级**、分区、冗余、全球复制 |

> **不统一使用 NoSQL**：虽然 NoSQL 能水平扩展，但在用户鉴权、配额等强一致场景下会增加实现复杂度。

### 2️⃣ 关系型数据库（MySQL）表结构

#### a) `users` 表（强一致）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `user_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 全局唯一 |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | 登录凭证 |
| `password_hash` | CHAR(60) | NOT NULL | bcrypt |
| `oauth_provider` | VARCHAR(50) | NULL | 第三方登录 |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 注册时间 |
| `quota_used` | BIGINT UNSIGNED | DEFAULT 0 | 已使用字节数 |
| `quota_limit` | BIGINT UNSIGNED | DEFAULT 10\*1024\*1024\*1024 (10 GB) | 配额上限 |

#### b) `images` 表（元数据）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `image_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 全局唯一 |
| `user_id` | BIGINT UNSIGNED | FK → users(user_id) | 所属用户 |
| `object_key` | VARCHAR(255) | NOT NULL | S3 中的路径 |
| `size_original` | INT UNSIGNED | NOT NULL | 字节 |
| `width_original` | SMALLINT UNSIGNED | NOT NULL | 像素 |
| `height_original` | SMALLINT UNSIGNED | NOT NULL | 像素 |
| `visibility` | ENUM('public','private') | DEFAULT 'public' | 访问控制 |
| `status` | ENUM('active','deleting','deleted') | DEFAULT 'active' | 软删标记 |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP |
| `tags` | JSON | NULL | `["cat","funny"]` |

- **分区**：按 `created_at`（月份）做 RANGE 分区，便于归档、清理。  
- **索引**：  
  - `IDX_user_id` (user_id) – 用于用户管理列表  
  - `IDX_visibility_status` (visibility, status) – 用于公共图片查询  
  - `IDX_tags` (JSON_EXTRACT(tags, '$[*]')) – 结合全文索引实现标签搜索（或在 ES 中做）

#### c) `image_links` 表（短链映射）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `short_code` | CHAR(8) | PK | Base62 编码 |
| `image_id` | BIGINT UNSIGNED | FK → images(image_id) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `expire_at` | TIMESTAMP | NULL | 可选过期时间 |

> **为什么把短链放在关系库**：短链数量与图片相同级别（≈ 2 M/日），写入频率不高，且需要事务保证唯一性。也可以使用 Redis 持久化，但在失效时会有一致性问题。

### 3️⃣ Elasticsearch（搜索）

- **索引**：`images_idx`  
- **文档结构**（示例）  

```json
{
  "image_id": 123456,
  "user_id": 7890,
  "tags": ["cat","funny"],
  "created_at": "2026-05-01T12:34:56Z",
  "visibility": "public",
  "hot_score": 1245   // 根据下载次数、点赞等计算
}
```

- **更新策略**：新增/修改时发送 Kafka 消息，消费者异步写入 ES，实现 **最终一致**（满足 N7）。

### 4️⃣ Redis（缓存）

| 键名 | 类型 | 说明 |
|-----|------|------|
| `user:{user_id}:profile` | Hash | 用户信息缓存（不包括密码） |
| `image:{image_id}:meta` | Hash | 图片元数据（size、status、visibility） |
| `short:{code}` | String | `image_id` 映射，TTL 30 days |
| `rate_limit:{ip}` | String | 令牌桶计数，1 min 过期 |
| `hot:{image_id}` | ZSET | 热度排行榜，定时刷新 |

> **不加缓存**：每次下载都会查询 MySQL + S3，导致 **读延迟 >300 ms**，不符合 N4。

---

## ## 第四步：核心 API 设计

> **约定**：采用 **RESTful + HTTPS**，返回 JSON；鉴权使用 **JWT**（短期）+ **Refresh Token**（长期）。

### 1️⃣ 通用返回结构

```json
{
  "code": 0,               // 0=成功，非0=错误码
  "message": "OK",
  "data": { ... }          // 业务数据
}
```

### 2️⃣ API 列表

| 方法 | 路径 | 鉴权 | 说明 | 示例请求/响应 |
|------|------|------|------|---------------|
| **POST** | `/api/v1/auth/register` | ❌ | 注册 | `{email, password}` → `user_id` |
| **POST** | `/api/v1/auth/login` | ❌ | 登录，返回 JWT | `{email, password}` → `{access_token, refresh_token}` |
| **POST** | `/api/v1/images` | ✅ | 单张上传（multipart） | `file` + `visibility` → `{image_id, short_url}` |
| **POST** | `/api/v1/images/batch` | ✅ | 批量上传（JSON 列表） | `[{"url": "..."}]` → `[{image_id, short_url}]` |
| **GET** | `/api/v1/images/{image_id}` | ✅（可选）| 获取图片元数据 | → `{image_id, urls{original, thumb, medium}}` |
| **GET** | `/s/{short_code}` | ❌ | 短链重定向（302）| → `Location: https://cdn.example.com/…` |
| **GET** | `/api/v1/images/{image_id}/download?size=thumb` | ✅（public 可免）| 下载指定尺寸 | → 302 到 CDN 或直接流 |
| **DELETE** | `/api/v1/images/{image_id}` | ✅ | 软删 + 异步硬删 | → `{code:0}` |
| **PATCH** | `/api/v1/images/{image_id}` | ✅ | 更新标签、可见性 | `{tags:["new"], visibility:"private"}` |
| **GET** | `/api/v1/search` | ✅（public 可免）| 根据 `q`, `tags`, `sort` 查询 | → `[{image_id, thumb_url}]` |
| **GET** | `/api/v1/users/{user_id}/quota` | ✅ | 查看已用/配额 | → `{used: 4.2GB, limit:10GB}` |

### 3️⃣ 关键 API 实现要点

#### 3.1 图片上传流程（时序图）

```
Client -> API GW (Auth+RateLimit) -> Upload Service
Upload Service -> Object Store: multipart upload (分块)
Upload Service -> Kafka: "image_uploaded" event (包含 object_key, user_id)
Upload Service -> MySQL: INSERT INTO images (metadata) (transaction)
Kafka Consumer (Image Processor) -> read event
Image Processor -> Object Store: generate thumbnail/medium/large
Image Processor -> Elasticsearch: index document
Image Processor -> Redis: warm cache (short_code -> image_id)
```

- **事务**：先写 MySQL 再返回短链，保证 **强一致**（用户立即可看到）。
- **异步**：图片压缩、索引放在后台，保证 **写入延迟 <300 ms**（N4）。

#### 3.2 图片下载（短链）流程

```
Client -> CDN Edge (缓存) -> miss -> Edge -> API GW -> Redis (short:{code})
   -> hit? return image_id -> Redis (image:{id}:meta) -> hit? -> MySQL fallback
   -> object_key -> S3 (GET) -> CDN caches response -> 返回给用户
```

- **Cache 层级**：Edge CDN → Redis → MySQL。  
- **命中率**：热门图片 >80% 在 CDN，进一步降低回源请求。

#### 3.3 删除流程（软删 + 异步硬删）

1. **API** 标记 `status='deleting'`（MySQL）并返回成功。  
2. 发送 **Kafka** 消息 `image_delete`。  
3. **Delete Worker** 读取消息：  
   - 从 CDN **Purge**（清除缓存）  
   - 从对象存储 **Delete Object**（或标记为归档）  
   - 从 Elasticsearch **Delete Document**  
   - 最终 **hard delete** MySQL 记录（或保留审计日志）  

> **为什么软删**：立即返回给用户，避免因后端清理慢导致感知延迟；同时可以实现 **最终一致**（N7）。

---

## ## 第五步：详细组件设计

### 1️⃣ 负载均衡层（L4/L7）

- **技术选型**：AWS ELB / GCP Cloud Load Balancer / Nginx+Keepalived（自建）。  
- **功能**：TLS 终止、健康检查、IP 绑定、跨可用区（AZ）分发。  
- **为什么要用**：单点故障、流量突发会导致 **服务不可用**，而负载均衡提供 **弹性伸缩入口**。

### 2️⃣ API Gateway

- **职责**：统一入口、统一鉴权、流量治理、日志/审计。  
- **实现**：Kong、Amazon API Gateway、或者自研基于 Spring Cloud Gateway。  
- **关键点**：  
  - **JWT 验证**：每个请求都在网关层校验 token，避免下游服务重复鉴权。  
  - **限流**：IP+用户维度的令牌桶（Token Bucket）防刷。  
  - **灰度发布**：Canary、蓝绿部署，快速回滚。

### 3️⃣ 鉴权服务（Auth Service）

- **数据库**：MySQL（主从） + **密码 Hash（bcrypt）**。  
- **OAuth**：集成 Google、GitHub 登录，使用 **Authorization Code Flow**。  
- **Token**：短期 Access Token (15 min) + Refresh Token (30 days) 存在 Redis（可撤销）。  
- **为什么要单独服务**：鉴权涉及 **强一致**、密码安全、OAuth 回调等，拆分后可以独立水平扩容。

### 4️⃣ 上传服务（Upload Service)

| 子模块 | 说明 | 关键技术 |
|--------|------|----------|
| **入口** | 接收 multipart / 分块请求 | Nginx + FastAPI / Spring Boot |
| **分块上传** | 前端先切片（例如 5 MB/块），服务支持 **PUT /multipart/{uploadId}/{partNumber}** | S3 Multipart API |
| **病毒/敏感内容检查** | 调用第三方安全扫描（ClamAV、AWS Rekognition） | 异步回调，失败返回错误 |
| **写入 MySQL** | 事务：`INSERT images` → 返回 `image_id` | InnoDB，READ COMMITTED |
| **写入对象存储** | 完成后调用 `CompleteMultipartUpload` | S3 或 MinIO |
| **事件发布** | 发送 Kafka `image_uploaded` | 可靠性：Exactly‑once 语义（事务+Kafka） |

### 5️⃣ 对象存储（Object Store）

- **选型**：公有云 S3（亚马逊、阿里云 OSS）或自建 MinIO 集群（K8s）  
- **特性**：  
  - **分区/分片**：自动水平扩展  
  - **多 AZ 同步复制**（跨区域灾备）  
  - **生命周期规则**：如 30 天未访问转归档（Glacier）降低成本  
- **为什么不使用本地文件系统**：单机磁盘容量、可靠性、扩容成本都无法满足 **100 PB** 规模。

### 6️⃣ CDN（内容分发网络）

- **选型**：CloudFront、Akamai、腾讯云 CDN、或自建 OpenResty+Edge 节点。  
- **缓存策略**：  
  - **Cache‑Control: public, max‑age=31536000**（一年）对不变的图片  
  - **ETag + If‑None‑Match** 用于更新后的缓存失效  
  - **Purge API**：删除图片时主动刷新（在 Delete Worker 中调用）  
- **热点分层**：  
  - **热图** → 放在 **Edge**（SSD）  
  - **冷图** → 只在 **Origin（S3）** 中保留，CDN 按需回源  

### 7️⃣ 缓存层（Redis）

| 场景 | Key 示例 | 失效策略 |
|------|----------|----------|
| 短链映射 | `short:{code}` | TTL 30 days |
| 图片元数据 | `image:{id}:meta` | TTL 5 min（热点） |
| 鉴权 Session | `session:{token}` | TTL 15 min |
| 热度排行榜 | `hot:daily` (ZSET) | 每天清除、重新计算 |

- **读写分离**：写入时直接写 MySQL，随后 **异步写 Redis**，保证 **最终一致**。  
- **防止缓存雪崩**：使用 **随机过期时间**，并在热点时 **预热**。

### 8️⃣ 消息队列（Kafka）

- **主题**：`image_uploaded`, `image_deleted`, `image_tag_updated`  
- **消费者**：  
  - **Image Processor**：生成衍生图、写 ES、写 Redis。  
  - **Delete Worker**：Purge CDN、删除 S3、删除 ES。  
  - **Search Indexer**：同步标签变更。  
- **为什么用 Kafka**：高吞吐、持久化、可以 **回放**，适合 **异步任务**，保证不丢数据。

### 9️⃣ 搜索服务（Elasticsearch）

- **分片**：按照 `created_at`（月份）做时间分片，查询热点时间段快速定位。  
- **倒排索引**：对 `tags`、`description` 建立。  
- **热度排序**：使用 `function_score`，结合 `download_count`（从 Redis）和 `likes`（可选）计算。  
- **同步**：Kafka 消费 `image_uploaded`、`image_tag_updated`，使用 **Bulk API** 批量写入。

### 🔟 监控、日志、告警

| 维度 | 工具 | 关键指标 |
|------|------|----------|
| **指标** | Prometheus + Grafana | QPS、CPU、内存、网络、Cache Hit Rate、S3 读写延迟 |
| **日志** | ELK (Filebeat → Logstash → Kibana) | API 请求日志、错误堆栈、审计日志 |
| **告警** | Alertmanager | CPU>80% 连续 5min、S3 错误率>1%、CDN 404 占比异常 |
| **链路追踪** | Jaeger / OpenTelemetry | 请求跨服务耗时分布（API → Auth → Upload → S3） |

> **不做监控**：系统出现瓶颈时难以及时定位，面试官会认为缺乏 **运维思维**。

---

## ## 第六步：扩展性与高可用设计

### 1️⃣ 横向扩容（Scale‑out）

| 层级 | 扩容方式 | 关键指标 |
|------|----------|----------|
| **入口** | 增加 LB + 多 AZ | 并发连接数 |
| **API GW** | 多实例 + 自动伸缩（K8s HPA） | QPS |
| **Auth Service** | 主从复制 + 读写分离 | 登录 QPS |
| **Upload Service** | 分区上传 ID（基于用户 ID 哈希） → 负载均衡到不同实例 | 上传 QPS |
| **Object Store** | 多 Region Bucket + 跨 Region Replication | 存储容量、写入吞吐 |
| **Redis** | 主从+Cluster（分片） | 缓存容量、并发 |
| **Kafka** | 增加 Partition → 多 Consumer Group | 消费并行度 |
| **Elasticsearch** | 增加 Shard/Replica | 搜索吞吐 |

> **为什么要分区**：单实例的 **CPU/内存** 有上限，水平扩容是处理 **1 500 QPS 上传**、**30 k QPS 下载**的根本手段。

### 2️⃣ 容灾（Disaster Recovery）

| 场景 | 方案 |
|------|------|
| **跨地域故障** | 使用 **多 Region Bucket**（如 S3 跨区复制） + **Anycast DNS** 将流量切换到最近 Region |
| **数据库灾备** | MySQL 主从复制 + **GTID** + 自动故障转移（MHA、ProxySQL） |
| **缓存灾备** | Redis Sentinel / Cluster 自动故障转移 |
| **消息队列** | Kafka MirrorMaker 将数据同步到备份集群 |
| **CDN** | 多 CDN 供应商混合使用（双活） |

- **RTO / RPO**：目标 **RTO ≤ 5 min**, **RPO ≤ 1 min**（符合 99.9% 可用性要求）。

### 3️⃣ 数据一致性策略

| 数据 | 一致性模型 | 解释 |
|------|------------|------|
| **用户鉴权** | **强一致**（主库写，读从延迟 < 100 ms） | 登录、配额必须实时 |
| **图片元数据** | **最终一致**（写 MySQL → 异步同步到 Redis/ES） | 浏览时稍有延迟可接受 |
| **短链映射** | **强一致**（写入 MySQL + Redis 同步事务） | 防止短链冲突 |
| **热点计数（下载次数）** | **弱一致**（Redis 原子 INCR） | 计数误差在可接受范围内 |

> **不区分一致性**：会导致 **用户配额错误**（强一致）或 **缓存雪崩**（强一致的缓存更新频繁）。

### 4️⃣ 限流与防刷

- **全局限流**：API GW 使用 **令牌桶**，每个 IP 每秒不超过 100 请求。  
- **用户级配额**：每日上传大小 ≤ 10 GB，上传前检查 Redis 中的 `quota_used`。  
- **热点保护**：对热门图片的下载请求采用 **热点缓存**（CDN+Redis）并在 Edge 设置 **速率限制**，防止 DDoS。

### 5️⃣ 异步任务的可靠性

- **幂等性**：所有 Kafka 消费者对同一事件 **幂等**（使用 `image_id` 作为唯一键写入对象存储或 ES）。  
- **重试机制**：消费失败后进入 **Dead Letter Queue (DLQ)**，后台运维可手动补偿。  
- **事务日志**：上传成功后在 MySQL 记录 `upload_status='completed'`，若中途失败可在后台清理。

### 6️⃣ 成本控制

| 手段 | 说明 |
|------|------|
| **对象存储生命周期** | 30 天未访问 → 归档（Glacier） |
| **CDN 缓存** | 热点图片 1 年 TTL，减少回源 |
| **冷热分区** | 老图片迁移到 **低成本 Region** |
| **按需弹性实例** | 高峰时使用 Spot 实例，非高峰时关闭 |

---

## ## 第七步：常见面试追问与回答

| 追问 | 参考答案要点 |
|------|--------------|
| **1. 把图片分布到全球用户，CDN 与存储如何协同？** | - **对象存储多 Region**：上传写入最近的 Region，异步复制到其他 Region。<br>- **CDN Edge**：Cache 原图和衍生图，TTL 长。<br>- **路由**：DNS/Anycast 将用户请求导向最近的 Edge，Edge 再回源最近的 Region。<br>- **热点分层**：热点图片在 Edge 持久化（SSD），冷图仅在 Origin。 |
| **2. 高并发上传导致磁盘/网络瓶颈怎么办？** | - **分块上传 + 多 Region**：每块写入最近 Region，避免单点磁盘写放大。<br>- **限流 + Token Bucket**：在 API GW 层限制每用户/IP QPS。<br>- **使用对象存储的 Multipart API**：直接把数据写入 S3，不经过业务服务器磁盘。<br>- **写入队列**：上传成功后立即返回，后续压缩、索引放到异步队列。 |
| **3. 删除图片时如何保证 CDN、对象存储、数据库一致？** | - **软删**：先在 MySQL 标记 `status='deleting'`，立即返回。<br>- **发送 Kafka 删除事件**。<br>- **Delete Worker**：① 调用 CDN **Purge** 接口清除 Edge 缓存；② 删除 S3 对象；③ 删除 ES 文档；④ 最后硬删 MySQL（或保留审计）。<br>- **最终一致**：因为删除是异步的，短时间内可能出现「已删除但仍能访问」的情况，属于可接受的业务容忍。 |
| **4. 为什么要把图片的衍生图（thumb/medium）放在对象存储而不是实时生成？** | - **性能**：实时生成会把 CPU/内存压力转到上传路径，导致写延迟 >300 ms。<br>- **可缓存**：衍生图是 **只读**，适合放在 CDN 缓存。<br>- **成本**：对象存储按使用付费，生成一次后可复用。 |
| **5. 怎样实现图片的“热门排行”并保持实时？** | - **Redis ZSET**：每次下载成功 `ZINCRBY hot:daily image_id 1`。<br>- **定时任务**（每分钟）将 ZSET 前 N 名同步到 MySQL/ES，供搜索排序使用。<br>- **TTL**：ZSET 设 24 h 自动过期，保持每日热点。 |
| **6. 如果要支持“限时私密链接”，怎么实现？** | - 生成带有 **签名+过期时间** 的 URL（如 `https://cdn.example.com/abc123?exp=1700000000&sig=xxxx`）。<br>- CDN Edge 在接收请求时校验签名和时间戳，合法则放行，否则 403。 |
| **7. 如何监控并快速定位“上传慢”问题？** | - 在 **Prometheus** 监控 `upload_service_latency_seconds`（分布式直方图）。<br>- 配合 **Jaeger** 链路追踪查看每一步耗时（API GW → Upload Service → S3 → MySQL）。<br>- 设定阈值报警（如 95% 延迟 > 300 ms），触发 PagerDuty。 |
| **8. 为什么不直接把图片元数据存到 NoSQL（如 DynamoDB）？** | - **强一致需求**：用户配额、登录必须强一致，DynamoDB 最终一致（除强读外）会带来复杂性。<br>- **事务需求**：上传需要一次写入 `images` 与 `user.quota_used`，关系型 DB 能保证原子事务。<br>- **查询灵活**：需要联合查询（用户+时间+标签），SQL 更易实现。 |

---

## ## 心得与反思

### 1️⃣ 本题最难的 1‑2 个设计决策及思考过程

| 决策 | 难点 | 思考路径 |
|------|------|----------|
| **① 是否采用强一致 vs 最终一致** | 需要在 **用户鉴权**（强一致）和 **图片元数据**（最终一致）之间做权衡，错误的选择会导致配额不准或热点缓存不刷新。 | 1. 列出所有数据的业务需求。<br>2. 区分哪些必须实时（登录、配额），哪些可以延迟（浏览）。<br>3. 选用 **MySQL + Redis** 组合实现强一致的关键路径，其他用 **异步 Kafka + ES** 实现最终一致。 |
| **② 全局缓存层的层次设计** | 直接在 CDN 前加一层缓存还是在业务层使用 Redis，如何避免 **缓存雪崩** 与 **热点穿透**。 | 1. 计算下载 QPS（30k）与对象存储成本，发现直接回源不可行。<br>2. 采用 **三层缓存**（Edge CDN → Redis → MySQL）实现逐级降级。<br>3. 为防雪崩，给每个键加 **随机 TTL**，热点时 **预热**。 |

### 2️⃣ 新手最容易犯的错误（至少 2 条）

| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把所有数据都放在单机 MySQL** | 随着用户/图片增长，写入、查询、备份都成为瓶颈，导致 **不可用**。 | 根据访问热点进行 **分库分表**（按用户 ID 哈希），并使用 **对象存储** 保存二进制文件。 |
| **忽视 CDN 与缓存层** | 下载 QPS 直接击穿后端，网络和存储会瞬间耗尽，响应时间 > 1 s，违背 N4。 | 在架构图中明确 **CDN + Edge Cache**，并说明 **缓存失效/预热** 机制。 |
| **把业务逻辑写进前端**（如压缩、生成短链） | 前端不可靠、跨域、资源浪费，难保证一致性。 | 将所有核心业务（上传、短链生成、图片处理）放在 **后端服务**，前端只负责 UI 与调用。 |
| **没有考虑异常/容错**（单点故障、网络分区） | 系统一旦某节点挂掉即全部不可用，无法满足 99.9% SLA。 | 为每个关键组件（LB、DB、Cache、对象存储）设计 **冗余 + 自动故障转移**。 |

### 3️⃣ 学习建议和可延伸的方向

| 学习方向 | 推荐资源 |
|----------|----------|
| **分布式系统基础**（CAP、BASE、分区） | 《Designing Data‑Intensive Applications》, 《分布式系统概念与设计》 |
| **云原生存储**（S3、MinIO、对象分层） | AWS 官方文档、MinIO 官方教程 |
| **缓存策略 & CDN** | 《高性能网站建设指南》、Cloudflare CDN 白皮书 |
| **消息队列 & 异步架构** | Kafka 官方文档、Confluent 在线课程 |
| **搜索引擎**（Elasticsearch） | Elastic 官方入门、Elastic Stack 实战 |
| **监控/可观测性** | Prometheus + Grafana 实战、OpenTelemetry 教程 |
| **系统容量规划** | 通过真实流量模型练习 QPS、存储、网络估算 |
| **安全与合规** | OWASP Top 10、GDPR 简介（如果涉及用户隐私） |

> **实战建议**：在本地或云上搭建一个简化版「Imgur」原型，使用 **MinIO**（对象存储）+ **PostgreSQL** + **Redis** + **FastAPI**，一步步加入 **Kafka**、**Elasticsearch**、**CDN**（如 Cloudflare Workers）并记录每次扩容的瓶颈与解决方案。这样在面试时能够把「理论」转化为「实战经验」说得更有说服力。

---

### 🎉 小结

- **从需求出发** → **估算** → **分层架构** → **选技术** → **细化每个组件** → **高可用/扩展** → **监控/运维**，形成完整闭环。  
- 关键点在于 **把系统拆成独立可扩展的模块**，并针对每个非功能指标（QPS、延迟、可用性、存储）给出 **具体技术实现** 与 **为什么要这么做**。  
- 面试时，**先说整体思路**，**再逐层展开**，**随时关注面试官的追问**，并准备好 **权衡取舍** 的解释。

祝你在系统设计面试中 **思路清晰、条理完整**，拿到满意的 offer! 🚀
