# 第 98 天：设计 在线教育平台（类 Coursera）

> 生成日期：2026-02-17

---

## 在线教育平台系统设计面试题（类 Coursera）

### 1. 题目背景
构建一个面向全球用户的在线教育平台，提供海量课程视频、作业、讨论区以及证书发放。用户可以在平台上自主学习、完成考核并获取认证。

### 2. 面试场景设定
> **面试官**：  
> “我们打算实现一个类似 Coursera 的在线教育平台，请你从零开始设计系统的整体架构。请先说明核心功能、预估规模以及你会关注的关键指标，然后逐步展开你的设计思路。”

### 3. 功能性需求（核心 4‑6 项）
| 编号 | 功能描述 | 关键点 |
|------|----------|--------|
| 1 | **用户注册/登录**（支持邮箱、第三方 OAuth） | 多地区、密码安全、验证码防刷 |
| 2 | **课程浏览与搜索**（分类、标签、推荐） | 高并发查询、全文检索、个性化排序 |
| 3 | **视频播放与进度同步**（支持分片、字幕、倍速） | CDN 加速、断点续传、播放记录持久化 |
| 4 | **作业提交与自动评测**（代码、选择题、报告） | 作业隔离、评测队列、结果回调 |
| 5 | **讨论区/问答**（帖子、回复、点赞、通知） | 实时推送、层级结构、内容审核 |
| 6 | **证书颁发与验证**（PDF 证书、二维码、第三方验证 API） | 防伪、防篡改、查询接口 |

### 4. 非功能性需求（关键指标与估算）

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **DAU（活跃日用户）** | 500 万 | 全球用户，峰值集中在欧美和亚洲 |
| **QPS（查询/请求峰值）** | 30,000 QPS | 包括课程搜索、视频播放请求、作业提交等 |
| **平均响应时延** | < 200 ms（除视频流）<br/>视频首帧加载 < 1 s | 对交互式页面要求低延迟，对视频使用 CDN |
| **可用性** | 99.9%（月度） | 关键业务（登录、播放、作业）故障恢复时间 ≤ 5 min |
| **存储量** | 30 PB（原始视频+转码）<br/>+ 5 PB（作业、日志） | 视频采用多码率存储，冷热分层 |
| **扩展性** | 支持横向扩容至 10×峰值流量 | 采用微服务、容器化、弹性伸缩 |

### 5. 系统边界
| 包含在本题范围 | 不在本题范围（可忽略） |
|----------------|------------------------|
| • 用户管理、课程管理、视频点播、作业评测、讨论区、证书生成与查询<br>• 搜索/推荐、CDN 加速、监控报警、灾备切换 | • 直播课堂（实时音视频）<br>• 移动端离线下载（DRM 版权）<br>• 第三方内容合作与版权结算<br>• 付费结算、营销活动、优惠券系统 |

### 6. 提示与追问
1. **如果 DAU 突然增长到 800 万，哪些模块最先需要水平扩容？请说明你的扩容策略。**  
2. **作业自动评测涉及代码执行沙箱，你会如何设计安全隔离与资源调度？**  
3. **针对视频播放的低延迟需求，CDN 与边缘计算该如何协同工作？请描述数据流向与缓存层级。**  

---

# 题解

## 解题思路总览
> **目标**：从「最小可用系统」出发，逐层补全功能、可靠性、扩展性，最终得到一个能够支撑 **500 万 DAU、30 k QPS**、**30 PB 视频存储** 的在线教育平台雏形。  
> **思路**：  
> 1. **先弄清需求**——功能、非功能、业务边界。  
> 2. **估算规模**，把抽象的「500 万活跃用户」转化为「每天登录次数、搜索请求、视频播放并发」等可量化指标。  
> 3. **画出高层框图**：前端 → API 网关 → 微服务 → 数据层/对象存储 → CDN。  
> 4. **针对每个核心功能拆分微服务**，并决定其状态性（有状态/无状态）。  
> 5. **选型**（关系型/NoSQL、缓存、消息队列、容器编排、监控等），并解释每个选型背后的权衡。  
> 6. **从最小可用 MVP**（单机 + 单库）逐步演进到 **高可用、弹性伸缩** 的分布式实现。  
> 7. **最后准备面试常见追问**：扩容、沙箱安全、CDN‑Edge 协同。  

下面我们一步步展开。

---

## 第一步：理解需求与规模估算

| 维度 | 需求 | 估算方法 | 结果（峰值） |
|------|------|----------|--------------|
| **用户** | DAU 500 万，峰值 20% 同时在线（登录后会浏览/观看） | 500w × 0.2 = 1,000,000 并发用户 | 同时在线 ≈ **1M** |
| **登录** | 假设 10% 的在线用户每秒一次登录请求 | 1M × 10% = 100,000 QPS 登录 | **100 k QPS**（峰值） |
| **搜索/浏览** | 每位活跃用户平均 5 次搜索/分钟 | 500w × 5 / 60 ≈ 416,667 QPS | **≈ 400 k QPS**（但实际热点集中在 30 k QPS 范围，考虑缓存） |
| **视频播放** | 平均每位用户观看 30 分钟，1 分钟 1 次分片请求（2 s 一个片段） | 1M × (30/1) = 30 M 片段/分钟 ≈ 500 k QPS | **≈ 500 k QPS**（CDN 直接命中，后端仅处理签名、统计） |
| **作业提交** | 10% 的用户每天提交作业一次，峰值 5 min 内 30 % 提交 | 500w × 0.1 × 0.3 / 300 s ≈ 5,000 QPS | **5 k QPS** |
| **讨论区** | 5% 的用户每分钟发帖/回复一次 | 500w × 0.05 / 60 ≈ 416 QPS | **≈ 500 QPS** |
| **证书查询** | 每完成一次课程平均 1 次证书生成/查询 | 500w × 0.02 / 60 ≈ 166 QPS | **≈ 200 QPS** |

> **注意**：以上是保守估算，真实业务中峰值往往会比平均值高 2‑3 倍，设计时要留有 **余量**（比如 2×‑3×）。

### 非功能指标拆解
| 指标 | 对应模块 | 关键技术点 |
|------|----------|-----------|
| **响应时延 <200 ms** | 登录、搜索、作业、讨论 | **缓存**（Redis）、**读写分离**、**异步化**（消息队列） |
| **视频首帧 <1 s** | 视频服务 + CDN | **对象存储 + CDN**，提前生成 **Signed URL**，边缘缓存 |
| **可用性 99.9%** | 全系统 | **多 AZ 部署、健康检查、自动故障转移** |
| **存储 30 PB 视频** | 媒体服务 | **分层对象存储（热/冷/归档）** + **多码率转码** |
| **横向扩容 10×** | 所有微服务 | **容器化 + K8s 自动伸缩**、**无状态设计** |

---

## 第二步：高层架构设计

### 1. 高层组件划分
```
+-------------------+      +-------------------+      +-------------------+
|   前端（Web/APP） | <--->|   API Gateway     | <--->|   负载均衡（L7）   |
+-------------------+      +-------------------+      +-------------------+
                                   |
            +------------------------------------------------------+
            |                      Service Mesh                    |
            +------------------------------------------------------+
      +-----------+   +-----------+   +-----------+   +-----------+
      | Auth Svc  |   | Course Svc|   | Video Svc |   |  Quiz Svc |
      +-----------+   +-----------+   +-----------+   +-----------+
      +-----------+   +-----------+   +-----------+   +-----------+
      |  Discuss  |   | Cert Svc  |   |  Search   |   |  Notify   |
      +-----------+   +-----------+   +-----------+   +-----------+
                                   |
                         +-------------------+
                         |   数据层（DB+Cache)|
                         +-------------------+
                                   |
                         +-------------------+
                         |   对象存储（S3）   |
                         +-------------------+
                                   |
                         +-------------------+
                         |   CDN / Edge      |
                         +-------------------+
```

### 2. 关键设计决策解释
| 决策 | 为什么这样做 | 不这么做的风险 |
|------|--------------|----------------|
| **API Gateway + Service Mesh** | 统一入口、鉴权、流量治理、灰度发布、跨语言 RPC（gRPC） | 每个服务自行实现鉴权、流控，代码重复且难以统一监控 |
| **微服务化（按业务域拆分）** | 每个业务可以独立扩容、部署、使用最适合的存储 | 单体服务会导致 **资源竞争**、**部署风险**、**难以水平扩容** |
| **无状态服务 + Redis 缓存** | 横向扩容只需增机器，故障恢复快 | 有状态服务需要 session 迁移，复杂度激增 |
| **对象存储 + CDN** | 视频文件大、跨地域访问，CDN 能把热点内容放在离用户最近的边缘节点，降低回源压力 | 直接从单机或 NAS 提供视频，网络带宽瓶颈、延迟高、单点故障 |
| **消息队列（Kafka/RabbitMQ）** | 作业评测、通知、日志等异步流程，削峰填谷，保证业务解耦 | 同步调用会导致 **链路阻塞**，在高并发时容易超时 |
| **容器化 + K8s** | 自动弹性伸缩、滚动升级、资源配额、故障自愈 | 手动部署/VM 方式弹性差，运维成本高 |

---

## 第三步：数据库设计

### 1. 数据库选型原则
| 业务 | 访问模式 | 推荐 DB | 说明 |
|------|----------|----------|------|
| 用户、登录、会话 | 读写比例约 5:1，事务一致性要求高 | **PostgreSQL**（或 MySQL） | 支持 ACID，水平读分片 + 主从复制 |
| 课程元数据（课程、章节、标签） | 多读少写，关系查询频繁 | **PostgreSQL** + **全文检索（Elasticsearch）** | 结构化+搜索 |
| 作业提交、评测结果 | 大量写入、后续分析 | **MongoDB**（文档）或 **Cassandra** | 高写入吞吐、灵活 schema |
| 讨论区、点赞、通知 | 高并发写、时序查询 | **Cassandra** 或 **ScyllaDB** | 写放大友好，水平扩展 |
| 视频播放日志、学习进度 | 以用户为主键的时序数据 | **ClickHouse** 或 **Druid** | 列式存储，快速聚合分析 |
| 证书信息 | 需要防篡改、查询频繁 | **PostgreSQL** + **唯一索引** | 事务一致性，配合签名机制 |

> **分库分表**：用户表按 **region_id**（或 user_id hash）水平分片，课程表按 **category_id** 分片，作业表按 **course_id** 分片。这样可以在每个分片上独立扩容。

### 2. 示例表结构（简化版）

```sql
-- 用户表
CREATE TABLE users (
    user_id        BIGSERIAL PRIMARY KEY,
    email          VARCHAR(255) UNIQUE NOT NULL,
    password_hash  CHAR(60) NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW(),
    status         SMALLINT DEFAULT 0, -- 0 正常 1 禁用
    region_id      SMALLINT NOT NULL   -- 用于分片
);

-- 课程表
CREATE TABLE courses (
    course_id      BIGSERIAL PRIMARY KEY,
    title          VARCHAR(255) NOT NULL,
    description    TEXT,
    instructor_id  BIGINT NOT NULL,
    category_id    BIGINT,
    created_at     TIMESTAMP DEFAULT NOW(),
    is_published   BOOLEAN DEFAULT FALSE,
    tags           TEXT[]   -- PostgreSQL array，用于搜索
);

-- 章节（视频）表
CREATE TABLE lessons (
    lesson_id      BIGSERIAL PRIMARY KEY,
    course_id      BIGINT REFERENCES courses(course_id),
    title          VARCHAR(255),
    duration_sec   INT,
    video_key      VARCHAR(512),      -- 对象存储路径
    order_index    INT,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- 作业提交表（MongoDB 示例）
{
    "_id": ObjectId,
    "user_id": 12345,
    "course_id": 987,
    "lesson_id": 54321,
    "type": "code",          // code / mcq / report
    "payload": {...},       // 代码或答案
    "status": "pending",    // pending / running / success / failed
    "score": null,
    "created_at": ISODate,
    "updated_at": ISODate
}
```

### 3. 缓存层
| 数据 | 缓存方式 | 失效策略 |
|------|----------|----------|
| 登录 token / Session | Redis（String） | TTL 30 min，主动刷新 |
| 课程列表、热门课程、标签 | Redis（Sorted Set） | 定时全量刷新（每 5 min） |
| 课程详情、章节信息 | Redis（Hash） | 读写穿透，TTL 1 h |
| 视频播放签名 URL | Redis（String） | TTL 与签名有效期相同（5 min） |
| 作业评测状态（实时） | Redis（Pub/Sub） | 实时推送后过期 |

---

## 第四步：核心 API 设计

> **原则**：RESTful + gRPC（内部高频调用），统一返回结构 `{code, message, data}`，错误码统一划分（1xx、2xx、4xx、5xx）。

| 功能 | HTTP Method | URL | 请求体（JSON） | 响应体 | 备注 |
|------|-------------|-----|----------------|--------|------|
| **注册** | POST | /api/v1/auth/register | `{email, password, captcha}` | `{user_id, token}` | 验证码防刷 |
| **登录** | POST | /api/v1/auth/login | `{email, password}` | `{token, expires_in}` | 返回 JWT + Refresh Token |
| **获取课程列表** | GET | /api/v1/courses | `?category=&tag=&page=&size=` | `{list:[], total}` | 支持分页、缓存 |
| **搜索课程** | POST | /api/v1/search/courses | `{query, filters, page, size}` | 同上 | 调用 Elasticsearch |
| **获取章节详情（含视频签名）** | GET | /api/v1/courses/{courseId}/lessons/{lessonId} | – | `{title, duration, video_url}` | video_url 为 **signed URL** |
| **提交作业** | POST | /api/v1/assignments/{assignmentId}/submit | `{type, payload}` | `{submission_id, status}` | 异步返回，后续轮询 |
| **查询作业结果** | GET | /api/v1/submissions/{submissionId} | – | `{status, score, feedback}` | 支持 WebSocket 推送 |
| **发帖** | POST | /api/v1/discussions | `{course_id, title, content}` | `{post_id}` | 需要防刷（限速） |
| **获取讨论列表** | GET | /api/v1/discussions?course_id=&page=&size= | – | `{list, total}` | 支持层级结构 |
| **生成证书** | POST | /api/v1/certificates | `{user_id, course_id}` | `{certificate_id, pdf_url}` | PDF 通过对象存储生成 |
| **验证证书** | GET | /api/v1/certificates/{certificateId}/verify | – | `{valid, user, course, issue_date}` | 对外开放 API |

> **安全**：所有除登录/注册外的 API 必须携带 **Bearer JWT**，在网关统一校验。  
> **限流**：登录、作业提交、发帖等高危接口在网关做 **IP+用户** 双重限流（例如 5 req/s），并使用 **验证码** 防止暴力。

---

## 第五步：详细组件设计

### 1. **认证中心（Auth Service）**
- **职责**：注册、登录、密码重置、Token 发放、刷新、撤销。  
- **实现**：使用 **Spring Boot / Go Gin**，后端调用 **PostgreSQL**（用户表）+ **Redis**（Session）+ **Argon2**（密码哈希）。  
- **安全**：  
  - **密码**：Argon2id + 随机盐，存储 hash。  
  - **验证码**：Google reCAPTCHA + 自建图片验证码（Redis 计数）。  
  - **Token**：JWT（HS256）+ Refresh Token（单独存 Redis，支持撤销）。  

### 2. **课程服务（Course Service）**
- **职责**：课程 CRUD、章节管理、标签、上架、下架。  
- **数据**：元数据在 **PostgreSQL**，全文检索使用 **Elasticsearch**。  
- **缓存**：热门课程、课程列表（Redis）+ **Cache Aside** 模式。  

### 3. **视频服务（Video Service）**
- **职责**：上传、转码、存储、生成签名 URL、播放统计。  
- **流程**：  
  1. **上传**：前端直传对象存储（S3） → 返回 `object_key`。  
  2. **转码**：上传触发 **S3 Event → Lambda/Function**，调用 **FFmpeg** 转多码率（1080p、720p、480p）。  
  3. **存储**：多码率文件存入 **Cold Tier（Glacier）**，热数据保留 30 天在 **Standard**。  
  4. **CDN**：对象存储配置 **Origin**，自动同步到 CDN。  
  5. **签名**：Video Service 根据用户、IP、有效期生成 **HMAC-SHA256** URL，缓存到 Redis。  

### 4. **作业评测服务（Quiz / Evaluation Service）**
- **架构**：  
  - **提交 API** → 写入 **MongoDB** + **Kafka**（topic: `submission-events`）。  
  - **评测 Worker**（容器化）从 Kafka 拉取任务，放入 **Sandbox**（Docker + seccomp + cgroup）执行。  
  - **结果**写回 **MongoDB**，同时推送 **Redis Pub/Sub** 给前端。  
- **安全隔离**：  
  - **User Namespace**、**PID Namespace**、**Network Namespace**（禁网）  
  - **资源配额**：CPU 0.5 核、Memory 256 MiB、执行超时 30 s。  
  - **镜像只读**，只挂载 `/tmp` 目录。  
- **调度**：使用 **Kubernetes Job** + **Custom Scheduler**，根据代码语言（Python、Java、C++）分配不同的 Sandbox 镜像。

### 5. **讨论区服务（Discussion Service）**
- **数据模型**：采用 **Cassandra** 表 `posts (post_id PK, parent_id, course_id, user_id, content, created_at)`，**轻量级事务**保证唯一 `post_id`。  
- **层级查询**：前端递归请求，或在 **ElasticSearch** 建立 **nested** 索引实现一次性查询。  
- **实时推送**：WebSocket 服务器（基于 **NestJS** + **Socket.io**）订阅 **Redis Pub/Sub** 主题 `post:new`.  

### 6. **证书服务（Certificate Service）**
- **生成**：使用 **Apache PDFBox**/ **iText** 动态生成 PDF，嵌入 **QR Code**（指向验证 API）。  
- **防伪**：  
  - **数字签名**：对 PDF 内容使用 **RSA-2048** 私钥签名，公钥发布给第三方验证。  
  - **唯一编号**：UUID + 哈希校验。  
- **存储**：生成后直接写入对象存储（S3），返回 **HTTPS** URL（带时效签名）。  
- **查询 API**：公开的 `/verify` 接口，返回 JSON，便于外部平台嵌入。

### 7. **搜索/推荐服务**
- **Elasticsearch**：索引课程、标签、标题、简介，实现 **全文检索**、**模糊匹配**。  
- **推荐**：基于 **协同过滤**（用户‑课程交互矩阵）+ **内容相似度**（TF‑IDF），离线训练后结果写入 **Redis**（用户‑推荐列表）供实时读取。  

### 8. **监控、日志、告警**
| 组件 | 监控指标 | 工具 |
|------|----------|------|
| API 网关/服务 | QPS、错误率、RT、CPU、内存 | **Prometheus + Grafana** |
| 消息队列 | Lag、吞吐、消费者状态 | **Kafka Manager** |
| 作业评测 | Sandbox CPU/内存、任务排队时长 | **Kube-state-metrics** |
| 视频 CDN | 命中率、带宽、错误码 | **CDN 自带监控 + CloudWatch** |
| 日志 | Access、Error、业务日志 | **ELK (Filebeat → Logstash → Kibana)** |

---

## 第六步：扩展性与高可用设计

### 1. 横向扩容关键模块
| 模块 | 触发扩容信号 | 扩容方式 |
|------|--------------|----------|
| API Gateway / L7 负载均衡 | QPS > 80% 预设阈值 | **水平扩容**（增加实例，自动注册到 Service Mesh） |
| Auth Service | 登录/注册 TPS 突增 | **自动伸缩**（K8s HPA，基于 CPU/RT） |
| Course / Discussion Service | DB 读写延迟上升 | **读写分离**（主库写，多个从库读）+ **分库**（按 region） |
| Video Service（签名生成） | Redis 命中率下降 | **Redis Cluster** 横向扩容 |
| 作业评测 Worker | 队列积压 > 10 min | **扩容 Worker Pods**（K8s HPA）|
| CDN 边缘节点 | 视频播放热点区域集中 | **动态调度**（在热点地区新增 Edge 节点） |

### 2. 高可用实现细节
1. **多可用区（AZ）部署**：每个微服务至少部署在 **3 个 AZ**，使用 **Service Mesh（Istio）** 实现跨 AZ 负载均衡和故障转移。  
2. **数据库高可用**：  
   - **PostgreSQL**：使用 **Patroni + Etcd** 实现自动主从切换。  
   - **MongoDB**：副本集（3 副本）+ 自动选举。  
   - **Cassandra**：每个节点都有副本，RF=3。  
3. **无状态容器**：所有业务容器不持本地磁盘，状态保存在外部 DB/Redis，容器故障可以快速重新调度。  
4. **灾备**：  
   - **跨地域复制**：对象存储启用 **跨区域复制**（CRR）到另一云区域。  
   - **冷备份**：每日全量快照（PostgreSQL、MongoDB）到对象存储，保留 30 天。  
5. **灰度发布**：使用 **Canary Deployment**（K8s）+ **Feature Flag**（LaunchDarkly）逐步打开新功能，监控错误率。  
6. **限流 & 熔断**：在 **API Gateway** 加入 **Token Bucket** 限流，后端微服务使用 **Hystrix/Resilience4j** 实现熔断，防止雪崩。  

### 3. 具体的扩容案例（对应提示 1）

> **DAU 突然增长到 800 万**（+60%）：  
> - **首先观察瓶颈**：登录、搜索、视频签名是最容易被压垮的入口。  
> - **扩容顺序**：  
> 1. **API Gateway + L7**：增加实例数，确保流量能够均衡分发。  
> 2. **Auth Service**：水平扩容，提升 Redis 节点数量以支撑更高的 Session/Token 读写。  
> 3. **Search Service（Elasticsearch）**：扩容节点，调高 **shard** 数量，保持查询延迟 <200 ms。  
> 4. **Video Service**（签名生成）：若 Redis 命中率下降，横向扩展 **Redis Cluster**，或在热点区域部署 **Edge Cache**（如 Cloudflare Workers）缓存签名。  
> - **自动化**：K8s **Horizontal Pod Autoscaler**（基于 CPU+自定义 QPS 指标） + **Cluster Autoscaler** 自动伸缩节点池。  

---

## 第七步：常见面试追问与回答

### 1️⃣ **如果 DAU 突然增长到 800 万，哪些模块最先需要水平扩容？请说明你的扩容策略。**  
（已在上节回答，这里再简要概括）

- **入口层**：API Gateway、负载均衡器 → 增加实例，使用 **云厂商的自动弹性伸缩**。  
- **鉴权层**：Auth Service + Redis → 增加 Redis 节点（Cluster），Auth Service Pod 横向扩容。  
- **搜索/推荐层**：Elasticsearch 集群 → 增加数据节点、提升 shard 数。  
- **视频签名层**：Video Service + Redis → 扩容 Redis Cluster，必要时在热点地区部署 **Edge Compute** 缓存签名。  
- **作业评测层**：若评测量激增，增加 **Worker Pods** 并调高 **Kafka 分区** 数量，保证消费并行度。  

**扩容策略**：  
- **监控驱动**：Prometheus 报警阈值（CPU>70%、RT>200ms、队列长度）触发 HPA。  
- **预热**：提前在非高峰时段做 **capacity planning**，在预计增长前手动预增实例。  
- **灰度验证**：新实例上线后通过 **canary** 检测错误率，确保不会出现回滚。  

---

### 2️⃣ **作业自动评测涉及代码执行沙箱，你会如何设计安全隔离与资源调度？**  

| 需求 | 设计要点 |
|------|----------|
| **安全隔离** | - 使用 **Docker** + **Linux Namespaces**（PID、UTS、IPC、Network、Mount）。<br>- **seccomp** 配置仅允许必要的系统调用（execve、read、write 等）。<br>- **cgroup** 限制 CPU（0.5‑1 核）和 Memory（256 MiB）。<br>- **AppArmor/SELinux** 强制只读文件系统，挂载 **/tmp** 为唯一可写目录。 |
| **网络隔离** | - **Network Namespace** 中不连接外部网络，禁止 `curl`、`wget` 等网络访问，防止信息泄露或爬取内部资源。 |
| **文件系统隔离** | - 采用 **OverlayFS**，底层镜像只读，业务代码挂载到 `/workspace`，评测完成后删除容器。 |
| **资源调度** | - **Kafka** 主题 `submission-events` 按 **语言**（python、java、cpp）分区，确保不同语言的评测使用不同镜像。<br>- **Kubernetes Job** + **Custom Scheduler**：读取消息后创建对应 **Pod**（使用 `nodeSelector` 指定专用评测节点），并设置 **Pod Priority**（高优先级作业先执行）。 |
| **超时控制** | - 在容器入口脚本使用 `timeout` 命令，强制在 **30 s** 后 kill 进程。<br>- 监控容器状态，若异常退出立即写回 `failed` 状态并记录日志。 |
| **审计 & 日志** | - 所有容器 stdout/stderr 收集至 **ELK**，并在 **MongoDB** 中保存作业运行的 **metadata**（start/stop 时间、资源使用）。 |
| **防止 DoS** | - 每个用户同一时间只能有 **N**（如 2）个评测任务在排队，超过则返回 `429 Too Many Requests`。 |
| **回滚** | - 若发现沙箱镜像被破坏，使用 **CI/CD** 自动重新构建并推送至 **私有镜像仓库**，K8s 自动拉取最新镜像。 |

---

### 3️⃣ **针对视频播放的低延迟需求，CDN 与边缘计算该如何协同工作？请描述数据流向与缓存层级。**  

1. **上传与转码**  
   - 前端 **直传** 视频至对象存储（S3）。  
   - S3 触发 **Lambda**（或 **K8s Job**）进行 **多码率转码**，生成 `1080p, 720p, 480p` 等文件。  
   - 转码完成后把文件写回 **对象存储**，并在 **元数据表**（PostgreSQL）记录 `video_key`、`duration`、`available_bitrates`。

2. **CDN 拉取 & 缓存层级**  
   - **一级缓存（Edge POP）**：CDN 节点（如 CloudFront、Akamai）根据用户请求的 **URL**（签名 URL）直接从对象存储拉取视频片段（TS/MP4），缓存到本地磁盘。  
   - **二级缓存（区域节点）**：若 Edge POP 命中率不足，CDN 会向 **区域缓存**（如中国大陆的电信节点）回源，形成层级缓存。  
   - **三层缓存（Origin）**：最终回源到 **对象存储**。  

3. **边缘计算（Edge Functions）**  
   - **用途**：在 Edge 节点进行 **动态签名校验**、**防盗链**、**字幕合并**、**码率自适应**（ABR）等轻量处理。  
   - **流程**：  
     1. 用户请求 `https://cdn.example.com/video/lesson123/720p.m3u8?token=xxxx`。  
     2. Edge Function 先验证 **HMAC**（防止 URL 被篡改），若合法则放行。  
     3. 若请求 **字幕**或 **水印**，Edge Function 在返回前对片段进行 **实时拼接**（使用 **FFmpeg‑wasm** 或 **Media Processing Service**）。  

4. **数据流向示例**  

```
[浏览器] --HTTPS--> [CDN Edge POP] --Cache Miss?--> (若 miss)
    |
    |---> [Edge Function] (签名校验) 
    |
    |---> [对象存储 (S3)] --GET--> [转码服务 (Lambda)] --生成--> [对象存储] (存放多码率文件)
    |
    |<--- 返回视频片段 (TS/MP4) ---|
    |
    |<--- 缓存到 Edge POP ---|
    |
[浏览器] <--播放流--- (分段请求)
```

5. **低延迟保障措施**  
   - **预热热点视频**：使用 CDN API 将新上线的热门课程提前 **push** 到各 POP。  
   - **分片大小**：采用 **2‑4 s** 的 TS 分片，平衡 **首帧加载** 与 **缓存命中率**。  
   - **多协议**：支持 **HLS**（HTTPS）和 **DASH**（HTTPS），根据客户端网络自动切换。  
   - **带宽控制**：在 Edge 根据用户网络状态动态选择码率（ABR），降低卡顿。  

---

## 心得与反思

### 1. 本题最难的 1‑2 个设计决策及思考过程
| 决策 | 难点 | 思考路径 |
|------|------|----------|
| **视频存储与 CDN 协同** | - 视频体积大（TB‑PB 级）<br>- 多码率、全球分发、版权保护 | 1️⃣ 先确定对象存储为**唯一真源**（避免多副本同步成本）<br>2️⃣ 再选 CDN 负责**边缘缓存**，通过 **签名 URL** 实现防盗链<br>3️⃣ 为降低首帧延迟，设计 **2‑4 s 分片 + Edge Function** 检查签名，兼顾安全与性能 |
| **作业自动评测的安全沙箱** | - 代码执行可能导致系统被攻击<br>- 资源竞争导致评测延迟 | 1️⃣ 采用 **容器 + Linux Namespaces + seccomp** 实现多层隔离<br>2️⃣ 用 **cgroup** 限制 CPU/Memory，防止资源耗尽<br>3️⃣ 将评测任务放入 **Kafka**，Worker 按语言分区，实现 **水平扩容** 与 **资源调度** |

### 2. 新手最容易犯的错误（至少 2 个）
| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把所有业务都塞进单体服务** | 难以横向扩容、部署风险高、单点故障 | 按业务域拆分 **微服务**，保持 **无状态**，使用 **API Gateway** 统一入口 |
| **忽视缓存与读写分离** | 数据库请求量爆炸，导致 QPS 达不到 30 k，响应时延飙升 | 对热点数据（课程列表、用户 Session、视频签名）使用 **Redis**，对读多写少的业务采用 **读写分离** 与 **从库** |
| **没有做好容量预估** | 现场演示时出现性能瓶颈、系统崩溃 | 基于 **DAU、并发** 做 **数学模型** 估算，留出 **2‑3 倍冗余**，并在设计中预留 **水平扩容** 的入口 |
| **安全只考虑登录** | 作业评测、视频防盗链等业务易被攻击 | 对 **代码执行**、**视频签名**、**API 限流** 全链路进行安全加固（沙箱、HMAC、验证码、限流） |

### 3. 学习建议和可延伸的方向
1. **系统设计的基本功**  
   - 熟悉 **CAP 定理、BASE、事务隔离级别**。  
   - 练习 **从需求到容量预估 → 高层图 → 细化组件** 的完整闭环。  
2. **掌握关键技术栈**  
   - **容器 & K8s**（部署、弹性伸缩、服务网格）  
   - **分布式缓存（Redis Cluster）** 与 **消息队列（Kafka）**  
   - **对象存储 + CDN**（S3、CloudFront、阿里云 OSS）  
   - **全文检索（Elasticsearch）** 与 **推荐算法**（协同过滤）  
3. **深入安全与隔离**  
   - 学习 **Docker Seccomp、AppArmor、cgroup**，动手搭建代码沙箱。  
   - 了解 **OAuth2、JWT、Refresh Token** 的完整流程。  
4. **性能调优实战**  
   - 用 **Locust / JMeter** 进行 QPS、延迟压测。  
   - 通过 **Prometheus + Grafana** 实时监控关键指标，练习 **自动伸缩**。  
5. **阅读优秀案例**  
   - Coursera、Udacity、edX、YouTube、Netflix 的架构博客。  
   - 《Designing Data-Intensive Applications》、High Scalability 网站。  

> **一句话总结**：系统设计不是一次性画完图，而是 **“需求 → 估算 → 划分 → 选型 → 演进”** 的循环迭代。把每一步都写清楚、解释原因，面试官最看重的往往是 **思考过程** 与 **权衡取舍**，而不是记忆具体的技术细节。祝你面试顺利，设计出自己的 Coursera！ 🚀
