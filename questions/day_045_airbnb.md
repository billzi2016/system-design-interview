# 第 45 天：设计 Airbnb

> 生成日期：2026-04-11

---

# 系统设计面试题 – Airbnb

## 题目背景
Airbnb 是一个全球性的短租平台，帮助房东将闲置的住宿资源发布给旅行者，旅行者可以在线搜索、预订并完成支付。系统需要支撑海量房源、用户和交易，同时保证良好的用户体验与安全性。

## 面试场景设定
> **面试官**：  
> “我们现在要设计一个类似 Airbnb 的短租平台，请先从高层次上描述系统的核心目标，然后围绕**房源搜索与预订**这块功能展开讨论。你可以先从需求出发，逐步拆解出主要的子系统、数据模型和技术选型。”

## 功能性需求
1. **房源发布**：房东能够创建、编辑、下线房源，上传图片、描述、价格、日历可用性等信息。  
2. **房源搜索**：旅行者可以根据地点、入住/离店日期、人数、价格区间、房型等过滤条件搜索房源，返回排序列表（推荐、价格、评分等）。  
3. **预订流程**：旅行者选定房源后，进行即时预订或请求预订（需房东确认），完成支付并生成订单。  
4. **订单管理**：用户（房东/旅行者）能够查看、修改、取消订单，系统需要处理退款、违约金等业务规则。  
5. **评价系统**：入住结束后，双方可以给对方留下文字评价、星级评分，评价会影响房源的展示排名。  
6. **通知/消息**：通过站内信、邮件、短信或推送通知相关事件（新预订请求、订单状态变化、评价等）。

## 非功能性需求（估算值）

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **DAU（活跃用户）** | 5 M（其中 2 M 房东） | 全球主要市场的日活用户数 |
| **QPS（查询峰值）** | 12 k QPS（搜索）<br>3 k QPS（下单） | 高峰期（美国东部周末） |
| **平均响应时延** | 搜索 ≤ 300 ms<br>下单 ≤ 200 ms | 99% 请求在此时限内完成 |
| **可用性** | 99.95%（月度） | 关键业务（搜索、下单、支付）不可宕机 |
| **存储容量** | 200 TB（图片、日志、备份）<br>10 TB（结构化业务数据） | 预计 2 年增长后仍在可接受范围 |
| **支付安全** | PCI‑DSS 兼容，交易成功率 ≥ 99.9% | 必须满足金融合规要求 |

> 注：以上数值基于 **2024 年** 的公开数据进行粗略估算，面试中可根据讨论动态调整。

## 系统边界
**本题范围内需要考虑的功能**  
- 房源的 CRUD、搜索、排序与过滤  
- 预订（即时/请求）流程、支付、订单生命周期管理  
- 基础的评价与评分体系  
- 通知（站内消息）以及基本的缓存与负载均衡设计  

**本题范围外（不必实现或细化）**  
- 复杂的支付渠道对接（如多币种、分账）  
- 线下客服、纠纷仲裁系统  
- 推荐系统的机器学习模型（仅需简单排序示例）  
- 大规模数据分析、BI 报表与离线计算  
- 法律合规、税务计算细节  

## 提示与追问
1. **高并发搜索如何保证低延迟？**  
   - 讨论索引选型、地理空间查询、缓存层（Redis / CDN）以及查询路由策略。

2. **预订冲突（同一房源同时间被多用户抢订）如何防止？**  
   - 需要说明乐观锁/分布式锁、库存预扣、事务一致性方案。

3. **评价系统对搜索排序的影响如何设计？**  
   - 讨论评分聚合、权重计算、实时 vs 离线更新、如何防刷评价。

---  
> 请基于以上需求，完整地进行系统拆解、数据建模、技术选型、容量规划以及高可用/容灾方案设计。祝你面试顺利！

---

# 题解

# Airbnb 类短租平台系统设计详解  
> **面向零经验的后端新人**，一步步手把手拆解设计过程，帮助你在面试中从 **需求 → 架构 → 细节** 逐层展开，理清每一次技术选型背后的原因。

---

## 解题思路总览
1. **先把需求说清楚**：功能点、非功能性指标、业务边界。  
2. **估算规模**：用户量、流量、存储，得到对系统容量的直观感受。  
3. **画出最小可运行系统（MVP）**：只保留最核心的组件，先验证业务可行性。  
4. **逐步演进**：在 MVP 基础上加入缓存、分布式存储、容灾、监控等，让系统满足 **高并发、低延迟、高可用**。  
5. **每一步都写出“为什么”**：如果不这么做会出现什么问题，帮助面试官看到你的思考深度。  

下面按 **七个章节** 逐一展开。

---

## 第一步：理解需求与规模估算

### 1️⃣ 功能需求梳理
| 编号 | 功能 | 关键点 |
|------|------|--------|
| 1 | 房源发布 | CRUD、图片上传、日历可用性、价格、属性（床数、房型） |
| 2 | 房源搜索 | 多维过滤（地点、日期、人数、价格、房型），排序（推荐/价格/评分） |
| 3 | 预订流程 | 即时预订 / 请求预订 → 支付 → 订单生成 |
| 4 | 订单管理 | 查看、修改、取消 → 退款/违约金 |
| 5 | 评价系统 | 双向评价、星级、影响搜索排序 |
| 6 | 通知/消息 | 站内信、邮件、短信、推送（预订、状态变化、评价） |

> **非功能需求**（已在题目表格中给出）是我们后面容量、性能、可用性设计的依据。

### 2️⃣ 规模估算（基于题目给出的指标）

| 指标 | 计算过程 | 结果 |
|------|----------|------|
| **活跃用户** | DAU = 5 M，其中 2 M 为房东 | 5 M |
| **搜索 QPS 峰值** | 假设 20% 活跃用户在高峰期搜索 → 5 M × 20% / 60 ≈ 16.6 k /s；题目保守给 12 k QPS | 12 k QPS |
| **下单 QPS 峰值** | 10% 活跃用户产生下单 → 5 M × 10% / 60 ≈ 8.3 k /s；题目给 3 k QPS | 3 k QPS |
| **图片存储** | 200 TB（已给）≈ 200 000 GB，平均 5 MB/张 → 40 M 张图片 |
| **结构化业务数据** | 10 TB ≈ 10 000 GB，主要是 MySQL/NoSQL 表 | 10 TB |
| **读写比例** | 搜索占大头（≈ 80% 读），下单占 20%（写） | 读取密集型 |

> **如果不做这些估算**，后面选型会盲目，可能导致容量不足或资源浪费，面试官会直接追问。

---

## 第二步：高层架构设计

### 1️⃣ MVP（最小可用系统）  
只需要以下几块：

```
[客户端] → [API Gateway] → [业务服务层] → [单体 MySQL]  
                       ↘→ [对象存储(图片)]  
                       ↘→ [消息队列(邮件/短信)]
```

- **API Gateway**：统一入口，做路由、限流、鉴权。  
- **业务服务层**（RESTful）：房源、搜索、订单、评价。  
- **单体 MySQL**：存放所有结构化数据，快速开发。  
- **对象存储**（如 AWS S3 /阿里云 OSS）：图片、视频等大文件。  
- **消息队列**（Kafka / RabbitMQ）：异步发送邮件、短信，防止同步调用阻塞。

> **为什么先做单体**：  
- 简化开发、部署成本。  
- 面试官想看你先把业务跑通，再讨论拆分。

### 2️⃣ 进阶分布式架构（满足非功能指标）

```
                +-------------------+
                |   CDN (图片、静态) |
                +----------+--------+
                           |
        +------------------+------------------+
        |                 Load Balancer       |
        +--------+-------------------+--------+
                 |                   |
        +--------v----+      +-------v-------+
        | API Gateway |      | API Gateway   |
        +--------+----+      +-------+-------+
                 |                   |
   +-------------v-------------+-----v-------------------+
   |   Search Service (ES)    |  Booking Service (Tx)   |
   +-------------+-------------+-----------+------------+
                 |                         |
   +-------------v-------------+-----------v------------+
   |   Cache (Redis)           |   MySQL Cluster (InnoDB)|
   +-------------+-------------+-----------+------------+
                 |                         |
   +-------------v-------------+-----------v------------+
   |   Message Queue (Kafka)   |   Object Storage (OSS) |
   +---------------------------+------------------------+
```

**关键组件解释**：

| 组件 | 作用 | 为什么要加入 |
|------|------|--------------|
| **CDN** | 加速图片、CSS、JS 的全局访问 | 否则图片直接回源导致带宽、响应时间爆炸 |
| **Load Balancer** | 分发请求到多台网关/业务服务器 | 单点故障、流量突发时会挂掉 |
| **API Gateway** | 鉴权、限流、灰度发布、统一入口 | 把安全、监控、限流抽离，业务服务专注业务 |
| **Search Service (Elasticsearch)** | 支持地理位置、过滤、排序的全文/向量搜索 | MySQL 直接做复杂搜索无法满足 300 ms 响应 |
| **Booking Service** | 负责预订事务、库存预扣、支付调用 | 与搜索解耦，专注一致性 |
| **Redis Cache** | 缓存热点房源、搜索结果、房东信息 | 减少 DB/ES 读取压力，提升响应速度 |
| **MySQL Cluster** | 主业务数据（用户、房源、订单、评价） | 支持 ACID，业务强一致性需求 |
| **Kafka** | 异步消息（邮件、短信、审计日志） | 防止同步调用导致下单慢，天然支持重放 |
| **对象存储** | 大文件（图片、视频） | 分离大对象，降低数据库存储成本 |

> **不加搜索引擎**：在 MySQL 上做多维过滤会导致全表扫描，查询延迟几秒甚至分钟，直接违背 300 ms 的 SLA。  
> **不使用缓存**：在高峰期每秒 12 k 搜索直接打到 ES，ES 仍能承受，但热点房源的重复计算会浪费大量 CPU、IO，导致节点频繁重启。

---

## 第三步：数据库设计

### 1️⃣ 关系型数据（MySQL）  
> 采用 **垂直拆分**：核心业务（用户、房源、订单、评价）放在同一个集群，后期可按业务再拆分。

#### 1.1 表结构（简化版）

```sql
-- 用户表（房东 & 旅客共用）
CREATE TABLE users (
    user_id        BIGINT PRIMARY KEY AUTO_INCREMENT,
    email          VARCHAR(255) UNIQUE NOT NULL,
    password_hash  VARBINARY(64) NOT NULL,
    role           ENUM('HOST','GUEST') NOT NULL,
    name           VARCHAR(100),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 房源表
CREATE TABLE listings (
    listing_id     BIGINT PRIMARY KEY AUTO_INCREMENT,
    host_id        BIGINT NOT NULL,
    title          VARCHAR(255) NOT NULL,
    description    TEXT,
    address        VARCHAR(255) NOT NULL,
    city           VARCHAR(100),
    country        VARCHAR(100),
    latitude       DOUBLE NOT NULL,
    longitude      DOUBLE NOT NULL,
    price_per_night DECIMAL(10,2) NOT NULL,
    max_guests     INT NOT NULL,
    room_type      ENUM('ENTIRE','PRIVATE','SHARED') NOT NULL,
    status         ENUM('ACTIVE','INACTIVE','DELETED') DEFAULT 'ACTIVE',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_location (latitude, longitude),
    INDEX idx_price (price_per_night)
) ENGINE=InnoDB;

-- 房源日历（可用性）
CREATE TABLE calendar (
    listing_id BIGINT NOT NULL,
    date       DATE NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    price      DECIMAL(10,2) NULL,
    PRIMARY KEY (listing_id, date)
) ENGINE=InnoDB;

-- 订单表
CREATE TABLE bookings (
    booking_id   BIGINT PRIMARY KEY AUTO_INCREMENT,
    listing_id   BIGINT NOT NULL,
    guest_id     BIGINT NOT NULL,
    check_in     DATE NOT NULL,
    check_out    DATE NOT NULL,
    total_price  DECIMAL(12,2) NOT NULL,
    status       ENUM('PENDING','CONFIRMED','CANCELLED','COMPLETED','REFUNDED') DEFAULT 'PENDING',
    payment_id   VARCHAR(64),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_listing (listing_id),
    INDEX idx_guest   (guest_id)
) ENGINE=InnoDB;

-- 评价表
CREATE TABLE reviews (
    review_id    BIGINT PRIMARY KEY AUTO_INCREMENT,
    booking_id   BIGINT NOT NULL,
    reviewer_id  BIGINT NOT NULL,  -- 评价者（guest 或 host）
    reviewee_id  BIGINT NOT NULL,  -- 被评价者
    rating       TINYINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment      TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_booking (booking_id, reviewer_id)
) ENGINE=InnoDB;
```

#### 1.2 关键设计点

| 设计点 | 目的 | 不这么做的后果 |
|--------|------|----------------|
| **主键使用 BIGINT AUTO_INCREMENT** | 支持海量数据且避免热点 | 使用 UUID 作为 PK 会导致索引碎片，写放大 |
| **`calendar` 按天存** | 快速判断时间冲突 | 用 JSON 存储会导致查询难以使用索引 |
| **`price` 放在 `calendar`** | 支持特殊日期调价 | 只在 `listings` 中存价格会导致每次查询都要算折扣 |
| **地理坐标索引 (`latitude, longitude`)** | 为后面的 ES 同步提供基础 | 没有索引，批量同步慢，搜索慢 |
| **唯一约束 `uq_booking`** | 防止同一订单被重复评价 | 重复评价会影响评分体系 |

### 2️⃣ 搜索引擎（Elasticsearch）

| 索引 | 主键 | 关键字段 | 分析器/映射 |
|------|------|----------|-------------|
| `listings` | `listing_id` | `title`、`description`、`city`、`country`、`price_per_night`、`max_guests`、`room_type`、`location`（geo_point） | `standard` 分词 + `ngram` 用于模糊搜索，`geo_distance` 用于位置过滤 |

- **同步方式**：MySQL **Binlog** → **Canal** → **Kafka** → **ES Consumer**，实现 **近实时**（秒级）同步。  
- **写入路径**：业务服务写 MySQL，成功提交事务后发送 **Kafka** 消息，ES 消费后更新索引。  
- **读路径**：搜索请求直接走 **ES** → **Redis 缓存**（热点查询） → 返回给前端。

> **不使用 ES**，只能靠 MySQL + GeoHash 实现地理查询，性能难以满足 12 k QPS，且难以实现模糊、权重排序。

### 3️⃣ 缓存（Redis)

| Key  | 示例 | 失效策略 | 用途 |
|------|------|----------|------|
| `listing:{id}` | `listing:12345` | 永不过期（TTL=30d） | 缓存单条房源详情，热点房源直接命中 |
| `search:{query_hash}` | `search:ab12c3` | 5 min → 30 min（热点自适应） | 缓存搜索结果分页 |
| `listing_availability:{id}` | `listing_availability:12345` | 1 min | 缓存最近 30 天的可用日期，快速冲突检测 |
| `rate_limit:user:{id}` | `rate_limit:user:9876` | 1 min | 限流，防止恶意刷请求 |

> **不加缓存**：每次搜索都要走 ES，热点查询会导致 ES 节点 CPU 飙升，影响整体延迟。

---

## 第四步：核心 API 设计

> 按 **RESTful** 风格，统一返回结构 `{code, message, data}`，使用 **JSON**。下面列出最关键的几组接口（仅示例，实际会有分页、错误码等细节）。

### 1️⃣ 房源相关

| 方法 | 路径 | 功能 | 关键参数 | 典型返回 |
|------|------|------|----------|----------|
| `POST` | `/api/v1/listings` | 创建房源 | `title, description, address, latitude, longitude, price_per_night, max_guests, room_type, images[]` | `{code:0, data:{listing_id:123}}` |
| `GET` | `/api/v1/listings/{id}` | 获取单个房源详情 | `id` | `{code:0, data:{...}}` |
| `PUT` | `/api/v1/listings/{id}` | 更新房源（仅 host 可） | 同创建的可选字段 | `{code:0}` |
| `DELETE` | `/api/v1/listings/{id}` | 下线/删除房源 | `id` | `{code:0}` |
| `POST` | `/api/v1/listings/{id}/availability` | 批量设置可用日期 | `dates:[{date, is_available, price}]` | `{code:0}` |

### 2️⃣ 搜索

| 方法 | 路径 | 功能 | 关键参数 | 说明 |
|------|------|------|----------|------|
| `GET` | `/api/v1/search` | 综合搜索 | `city, lat, lng, radius(km), check_in, check_out, guests, price_min, price_max, room_type, sort_by (relevance/price/rating)` | 参数 `lat/lng` 与 `radius` 为地理过滤；若提供 `city` 先转成坐标。 |
| 返回 | - | - | - | `{code:0, data:{total, listings:[{listing_id, title, price, rating, distance}]}}` |

**实现要点**：

1. **先查询 Redis 缓存**：`search:{hash}`，命中直接返回。  
2. **未命中 → ES 查询**：使用 **bool + filter + function_score**，实现过滤 + 排序（评分权重）。  
3. **返回前**：把热点房源写回 Redis（写穿透），并异步记录日志用于后续分析。

### 3️⃣ 预订（即时预订示例）

| 方法 | 路径 | 功能 | 关键参数 | 流程概要 |
|------|------|------|----------|----------|
| `POST` | `/api/v1/bookings` | 创建预订（即时） | `listing_id, guest_id, check_in, check_out, payment_token` | 1. **库存预扣**（Redis 锁）<br>2. 调用支付（外部）<br>3. 事务写入 MySQL（booking + payment）<br>4. 发送 Kafka 事件（order_created）<br>5. 释放锁 |
| `GET` | `/api/v1/bookings/{id}` | 查看订单详情 | `id` | - |
| `POST` | `/api/v1/bookings/{id}/cancel` | 取消订单 | `id, reason` | 校验状态 → 退款 → 更新 MySQL → 发 Kafka 事件（order_cancelled） |

**冲突防止**（后面章节会展开）：

- **分布式锁**（Redis `SETNX` + TTL）在 `check_in ~ check_out` 这段时间内 **原子** 标记为 “已预订”。  
- 若锁获取失败，直接返回 **房源已被抢订**。

### 4️⃣ 评价

| 方法 | 路径 | 功能 | 关键参数 |
|------|------|------|----------|
| `POST` | `/api/v1/reviews` | 提交评价 | `booking_id, reviewer_id, rating, comment` |
| `GET` | `/api/v1/listings/{id}/reviews` | 查看房源评价列表 | `listing_id, page, size` |
| `GET` | `/api/v1/users/{id}/reviews` | 查看用户（房东/旅客）评价 | `user_id` |

> **评价写入后**，发送 Kafka 消息 → **实时计算**（Spark Streaming）更新 **ES** 中的 `rating` 字段，搜索时即能使用最新评分。

### 5️⃣ 通知（站内消息）

| 方法 | 路径 | 功能 | 关键参数 |
|------|------|------|----------|
| `GET` | `/api/v1/notifications` | 拉取未读消息 | `user_id, page, size` |
| `POST` | `/api/v1/notifications/mark_read` | 标记已读 | `notification_ids[]` |

> 业务服务通过 **Kafka** 生产通知事件，**消费者**（Message Service）负责写入 MySQL + 推送到 **WebSocket** / **APNs / FCM**。

---

## 第五步：详细组件设计

### 1️⃣ 负载均衡 & 流量入口

- **层级**：  
  - **DNS 轮询 + Anycast** → **Global Load Balancer（如 Cloudflare/阿里云 Global Accelerator）** → **Region‑level L4/L7 LB**。  
- **目的**：实现 **跨地域容灾**，把流量分到最近的数据中心，降低 RTT。  
- **不做**：直接把流量打到单机，会导致单点瓶颈和网络延迟。

### 2️⃣ API Gateway

| 功能 | 技术选型 | 解释 |
|------|----------|------|
| 鉴权（JWT / OAuth2） | Kong / Spring Cloud Gateway | 统一校验 token，避免业务服务重复实现 |
| 限流 | Redis Token Bucket / Nginx limit_req | 防止恶意流量冲垮后端 |
| 灰度/AB 测试 | Header/Weight 路由 | 逐步上线新功能，降低风险 |
| 日志采集 | Fluentd + ELK | 集中化追踪请求链路，方便排障 |

### 3️⃣ 搜索服务（Elasticsearch）

- **集群规模**：起始 **3 节点**（主‑副‑副），每节点 8 vCPU、32 GB RAM、SSD。  
- **分片/副本**：`index.listings` → **5 主分片**，每主分片 **1 副本**（后期根据流量水平横向扩容）。  
- **冷热数据分层**：最近 90 天的房源放在 **热节点**（SSD），历史数据放在 **温/冷节点**（HDD），降低成本。  
- **写入路径**：业务服务写 MySQL → 通过 **Canal** 捕获 binlog → 推送到 **Kafka topic listings_change** → **ES Consumer** 更新索引。

### 4️⃣ 预订事务处理

#### 4.1 库存预扣（防冲突）

```text
1. 客户端请求下单 → Booking Service
2. Booking Service 通过 Redis Lua 脚本一次性检查 & 锁定日期区间
   (key: "listing:12345:2026-06-01~2026-06-05")
3. 若锁定成功，继续调用支付网关；若失败返回 “已被预订”
4. 支付成功后，写入 MySQL（booking）并发布 Kafka 事件
5. 异步任务监听事件，更新 Elasticsearch rating、发送站内信
6. 最后删除 Redis 锁（TTL 防止死锁）
```

- **Lua 脚本**保证 **原子** 检查+写入，避免并发竞争。  
- **TTL**（如 30 s）防止业务异常导致锁永久占用。

#### 4.2 支付安全

- 使用 **PCI‑DSS** 兼容的第三方支付（Stripe、PayPal）。  
- **不在本系统存储卡号**，只保存 **payment_token**（一次性）和 **payment_id**。  
- 支付成功后 **回调**（Webhook）由 **Payment Service** 验证签名后写入订单状态。

### 5️⃣ 评价防刷

- **业务规则**：同一订单只能评价一次，且只能在入住结束后 30 天内提交。  
- **技术实现**：在 `reviews` 表上建立 **唯一键** `uq_booking (booking_id, reviewer_id)`，业务层再校验 **订单状态 = COMPLETED**。  
- **异常监控**：Kafka 中的 `review_created` 事件流向 **实时风控系统**（基于 Flink），检测同一 IP、同一设备的高频评价，若异常直接标记为 **待审**。

### 6️⃣ 消息系统（Kafka）

| Topic | 生产者 | 消费者 | 业务意义 |
|-------|--------|--------|----------|
| `listing_change` | MySQL Canal | ES Consumer、Cache Refresh Service | 保持搜索索引与缓存同步 |
| `order_created` | Booking Service | Payment Service、Notification Service | 触发支付、发送预订成功站内信 |
| `order_cancelled` | Booking Service | Refund Service、Notification Service | 退款、通知房东 |
| `review_created` | Review Service | Rating Update Service、Audit Service | 实时更新房源评分、审计日志 |

- **分区数**：依据 QPS 预估，**order_created** 设 12 分区，**listing_change** 设 6 分区，保证并行消费。  
- **可靠性**：开启 **acks=all**，**replication.factor=3**，确保不丢失关键业务事件。

### 7️⃣ 缓存失效策略

| 场景 | 失效方式 |
|------|----------|
| 房源详情更新 | **写穿**：业务服务更新 MySQL 后，直接 **DELETE** 对应 `listing:{id}` 缓存，下一次读取重新加载。 |
| 搜索结果排序变化（评分、价格） | **TTL**：搜索结果缓存 5 min → 30 min，根据热点自动延长。 |
| 可用日期变更（预订成功/取消） | **写穿**：在预订成功后，调用 `DEL listing_availability:{id}`，让下次查询重新计算。 |
| 评价提交后评分变更 | **异步**：Review Service 发送 `review_created` → Rating Update Service 计算新评分 → **更新 ES** 中 `rating` 字段，搜索自动使用最新评分。 |

---

## 第六步：扩展性与高可用设计

### 1️⃣ 横向扩展（Scaling Out）

| 组件 | 扩容方式 | 监控指标 |
|------|----------|----------|
| API Gateway / LB | 增加实例，使用 **自动伸缩组**（ASG） | CPU、请求 QPS、错误率 |
| Search Service (ES) | 增加节点，重新分配分片 | 索引写入速率、查询延迟、节点磁盘利用率 |
| Booking Service | 水平扩容容器（K8s Deployment） | CPU、锁冲突率、支付回调延迟 |
| MySQL | **读写分离**：主库负责写，多个从库负责读；通过 **ProxySQL** 动态路由 | 主库 CPU、复制延迟、从库查询 QPS |
| Redis | **Cluster** 分片，每个分片 3 主/1 从 | QPS、命中率、内存占用 |
| Kafka | 增加 Broker，提升分区数 | 生产者/消费者延迟、ISR（In‑Sync Replicas）比例 |

> **不做读写分离**：写热点会把主库压垮，导致所有请求卡死。  

### 2️⃣ 高可用 & 容灾

| 维度 | 方案 |
|------|------|
| **跨地域容灾** | 在 **美国东部**、**欧洲**、**亚太** 部署同构集群；使用 **DNS 负载均衡 + GeoIP** 把用户请求路由到最近的 Region。 |
| **数据备份** | MySQL **全量快照 + binlog**（每 5 min），对象存储 **多 AZ 冗余**；Redis 持久化使用 **RDB + AOF**，并同步到备份中心。 |
| **故障自动切换** | MySQL 主库故障 → **MHA** 自动选举新主库；Kafka Broker 故障 → **Controller** 自动重新选举 ISR；ES 主分片故障 → 副本自动升为主。 |
| **监控 & 报警** | **Prometheus + Grafana** 监控 CPU、内存、QPS、延迟；**Alertmanager** 按 SLA（99.95%）设置报警阈值。 |
| **灰度发布** | 使用 **Canary** 或 **Blue‑Green** 部署新版本 API，逐步提升流量比例，发现异常立即回滚。 |

### 3️⃣ 安全与合规

- **身份认证**：JWT + HTTPS（TLS1.3），Token 失效时间 1 h，Refresh Token 7 d。  
- **授权**：基于 **RBAC**（HOST、GUEST），细粒度检查（仅房东能编辑自己房源）。  
- **审计日志**：所有关键操作（创建房源、下单、支付、退款）写入 **ELK**，满足合规审计。  
- **数据脱敏**：日志中对 **手机号、邮箱** 做掩码。  
- **PCI‑DSS**：支付只走第三方，不在本系统存储卡号，使用 **HTTPS** + **HSM** 进行敏感信息加密。

---

## 第七步：常见面试追问与回答

### Q1. 高并发搜索如何保证低延迟？
**回答要点**：
1. **Elasticsearch** 为倒排索引+地理空间索引，单节点查询 < 50 ms。  
2. **分片**+**副本**保证查询并行化，热点查询走 **Redis 缓存**（5 min TTL），命中率 > 80%。  
3. **查询路由**：API Gateway → Search Service → 先查 Redis → 未命中走 ES。  
4. **热点数据预热**：每日凌晨使用 **Spark** 计算热门城市的前 1000 条房源，提前写入 Redis。  
5. **限流**：对同一 IP/用户的搜索频率做 Token Bucket 限制，防止刷接口导致节点瞬时爆炸。

### Q2. 预订冲突（同一房源同时间被多用户抢订）如何防止？
**回答要点**：
- 使用 **Redis 分布式锁**（Lua 脚本）对 `listing:{id}:date_range` 原子检查并标记为 “已锁”。  
- 锁的 **TTL**（30 s）防止因业务异常导致死锁。  
- **乐观锁**：在 MySQL `calendar` 表加入 `version` 字段，写入时 `WHERE version = old_version`，若受影响行数为 0 则说明冲突。  
- **事务**：在 Booking Service 中，先预扣库存 → 调用支付 → 成功后提交 MySQL 事务；若任一步失败，立即回滚并释放锁。  
- **幂等**：对外部支付回调使用 **唯一业务 ID** 防止重复写入。

### Q3. 评价系统对搜索排序的影响如何设计？
**回答要点**：
1. **评分聚合**：在 MySQL 中维护 `listing_id → rating_sum, rating_cnt`，实时更新。  
2. **权重公式**：`final_score = α * rating_avg + β * review_count + γ * recent_booking_rate`（可调）。  
3. **写入路径**：用户提交评价 → `review_created` 事件 → **Streaming**（Flink）聚合 → 更新 MySQL 汇总表 & **ES** 中 `rating` 字段。  
4. **防刷**：唯一键 + 业务规则（只能在订单完成后评价）+ 风控系统检测异常频率。  
5. **搜索时**：ES 使用 `function_score` 将 `rating` 作为 **boost**，结合 **price**、**distance** 实现复合排序。

### Q4. 为什么不直接把图片存到 MySQL？
**回答**：  
- **体积大**：图片平均 5 MB，200 TB 数据会让 MySQL 磁盘 IO、备份时间成指数级增长。  
- **查询性能**：每次查询房源时不需要把二进制图片拉进来，导致网络带宽浪费。  
- **扩展性**：对象存储（OSS/S3）天然支持 **CDN 加速**、**分层存储**，成本更低。  

### Q5. 如果流量在某一天瞬间翻倍，系统如何自救？
**回答**：  
- **自动伸缩**：K8s HPA 基于 CPU/QPS 自动扩容 API、Booking、Search Service 实例。  
- **熔断/降级**：对非关键业务（如推荐、热门房源排行榜）使用 **Circuit Breaker**，在流量高峰时返回简化结果，保证核心下单不受影响。  
- **缓存预热**：提前将热点城市的房源列表写入 Redis，减轻 ES 查询压力。  
- **限流**：对同一 IP/用户的搜索/下单进行 Token Bucket 限流，防止恶意刷单导致资源耗尽。

---

## 心得与反思

### 1️⃣ 本题最难的 1‑2 个设计决策

| 决策 | 为什么难 | 我的思考过程 |
|------|----------|--------------|
| **预订冲突的强一致性** | 预订是 **金钱交易**，必须做到“**先到先得**”。在分布式环境下，如何在毫秒级完成库存检查、锁定、支付、写库的原子操作极具挑战。 | 先列出常见方案：**分布式锁**、**乐观锁**、**事务**。比较它们的 **性能**、**可靠性**、**实现复杂度**。最终决定 **Redis Lua 脚本+TTL** 进行快速检查，再配合 **MySQL 乐观锁** 做最终持久化，兼顾速度与持久性。 |
| **搜索性能与排序** | 需要在 **300 ms** 内完成 **地理、价格、评分、多维过滤**，并且支持 **热点缓存**、**实时评分**。单纯用 MySQL 难以满足。 | 先分析查询模式：**地点+时间+价格** → 必须有 **倒排+地理空间索引**。选了 **Elasticsearch**，并设计 **缓存层**（Redis）+ **异步评分更新**。随后评估 **分片数**、**副本数**、**冷热节点**，确保在峰值 QPS 时仍能保持低延迟。 |

### 2️⃣ 新手最容易犯的错误（至少 2 条）

| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把所有业务都塞进单体 MySQL**，没有搜索引擎或缓存。 | 查询慢、扩展难、容易出现 **“读写冲突”**，导致 SLA 失效。 | 按业务拆分：搜索 → ES；热点数据 → Redis；事务关键 → MySQL。 |
| **忽视幂等性和事务回滚**，尤其在支付回调和预订锁定时。 | 重复扣款、库存不一致、用户体验差。 | 为每个业务动作设计 **全局唯一业务 ID**，在所有外部回调中检查 **是否已处理**；使用 **分布式事务** 或 **两阶段提交**（如 TCC）保证一致性。 |
| **没有限流或熔断**，直接让所有请求打到后端。 | 瞬时流量高峰会导致服务崩溃，影响关键业务。 | 在 API Gateway 引入 **Token Bucket** 或 **Leaky Bucket** 限流；对非关键接口使用 **Circuit Breaker** 降级。 |

### 3️⃣ 学习建议和可延伸的方向

1. **掌握搜索引擎原理**：阅读 Elasticsearch 官方文档，实践 **倒排索引、分片、聚合**，并用 **Kibana** 可视化查询性能。  
2. **分布式事务与锁**：深入了解 **Redis Lua 脚本、RedLock**，以及 **TCC、Saga** 模式，动手实现一个 **秒杀/抢购** 示例。  
3. **消息系统与流处理**：学习 **Kafka** 的 **分区、ISR、Exactly‑Once**，配合 **Flink/Spark Streaming** 实现 **实时评分、风控**。  
4. **性能压测**：使用 **Locust / JMeter** 对搜索、下单进行压测，熟悉 **CPU、IO、网络** 监控指标，练习 **自动伸缩策略**。  
5. **系统可靠性工程（SRE）**：阅读 Google SRE 书籍，掌握 **SLI/SLO/SLAs** 的定义、**错误预算**的使用，能够在面试中谈论 **可观测性** 与 **灾备演练**。  

> **记住**：系统设计面试不只看你写了多少代码，而是看你 **如何拆解需求、权衡取舍、保障关键业务** 的能力。逐步练习上述方向，你会在面试中脱颖而出。  

---  
