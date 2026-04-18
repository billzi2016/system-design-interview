# 第 38 天：设计 Stripe 支付系统

> 生成日期：2026-04-18

---

# Stripe 支付系统设计面试题

## 题目背景
Stripe 是一家面向全球商户提供在线支付、结算、风控和财务报表等服务的 SaaS 平台。面试者需要设计一个核心的 **支付处理系统**，能够安全、可靠地完成跨境交易并对外提供统一的 API。

## 面试场景设定
> **面试官**：  
> “假设我们要为一家快速增长的电商平台实现一套类似 Stripe 的支付系统，请你从零开始设计其核心支付处理服务。请先说明系统的主要职责，然后我们一起讨论架构、数据流和关键技术点。”

---

## 功能性需求
1. **创建支付意图（Payment Intent）**  
   - 接收前端提交的订单金额、币种、支付方式等信息，返回唯一的 `payment_intent_id`。
2. **支付确认与扣款**  
   - 根据 `payment_intent_id` 调用第三方收单机构（如 Visa、MasterCard、支付宝、微信支付）完成授权并扣款。
3. **支付状态回调 & 幂等处理**  
   - 接收收单机构的异步回调（成功、失败、风控），更新支付状态并保证幂等性。
4. **退款与部分退款**  
   - 根据原支付记录发起全额或部分退款，支持跨币种退款。
5. **风控 & 欺诈检测**  
   - 在支付前后对交易进行规则校验（频率、IP、卡号风险等），并支持人工审查的回流机制。
6. **对外统一 API 与 SDK**  
   - 提供 RESTful API（CreateIntent、ConfirmPayment、Refund 等）以及常见语言（Java、Node、Python）的 SDK。

---

## 非功能性需求
| 指标 | 估算值 | 说明 |
|------|--------|------|
| **DAU（日活跃商户）** | 30,000 | 每家商户平均一天发起 2 笔支付 |
| **QPS（峰值请求）** | 12,000 QPS | 高峰期 10 秒钟内 120,000 次 API 调用（创建/确认/查询） |
| **平均延迟** | ≤ 150 ms（99% 请求） | 包括网络、业务校验、调用第三方支付网关的时间 |
| **可用性** | 99.99%（每月累计宕机 < 5 分钟） | 支付业务必须具备极高可靠性 |
| **存储量** | 30 TB（交易日志、审计日志） | 交易数据保留 7 年，日志保留 90 天 |
| **一致性要求** | 强一致性（支付状态必须是唯一的真相） | 防止重复扣款或错误退款 |

---

## 系统边界
**本题范围（需要设计）**  
- 支付意图创建、确认、状态回调、退款、风控规则引擎、幂等机制、对外 API 与 SDK。  
- 数据持久化（交易表、日志表）、高可用架构（多活、容灾）、监控告警。  

**不在本题范围（可以略过）**  
- 第三方收单机构的内部实现与协议细节（仅视为黑盒）。  
- 商户结算到银行账户的批处理（可作为扩展讨论）。  
- 国际税务合规（如 VAT、GST）的计算与申报。  
- UI 前端页面（仅关注后端服务）。  

---

## 提示与追问
1. **幂等设计**：如果同一个 `payment_intent_id` 的确认请求被重复发送，系统如何保证不产生二次扣款？请说明幂等键的选取与实现方式。  
2. **跨地域容灾**：在北美、欧洲和亚太分别部署数据中心时，如何处理跨区的交易一致性与延迟？请讨论使用哪种分布式事务或最终一致性方案。  
3. **风控扩展**：如果需要在支付流程中加入机器学习模型进行实时欺诈评分，如何在不影响主链路性能的前提下进行集成？请说明模型部署、特征获取与降级策略。

---

# 题解

## 解题思路总览  

> **目标**：从「只要能跑通最基本的创建‑确认‑回调」出发，逐层补齐 **可靠性、可扩展性、可观测性、跨地域容灾**，让面试官看到你 **先把核心业务弄对，再考虑非功能需求** 的系统化思考过程。  

**整体思路**  

| 步骤 | 关注点 | 为什么先做这一步 |
|------|--------|-------------------|
| 1️⃣ 理解需求 & 规模估算 | 功能点、QPS、延迟、可用性、数据量 | 防止“功能太多、容量盲目估计”导致后面频繁回头重构 |
| 2️⃣ 高层架构 | API Gateway、业务服务、支付网关适配层、风控、日志/审计、监控 | 把系统划分成 **职责单一** 的子系统，明确边界，后面可以独立扩容 |
| 3️⃣ 数据库设计 | 事务强一致、幂等、审计日志 | 支付最核心的 **“一次只能成功一次”** 需求必须在模型层保证 |
| 4️⃣ 核心 API 设计 | RESTful 接口、错误码、幂等键 | 好的 API 能帮助 SDK/前端正确使用，也是后面安全、幂等实现的入口 |
| 5️⃣ 详细组件设计 | 具体的 **创建、确认、回调、退款、风控、幂等** 实现细节 | 把抽象的职责落地到代码/消息流上，展示技术选型依据 |
| 6️⃣ 扩展性 & 高可用 | 多活、跨地域、异步、限流、降级、监控 | 让系统满足 **99.99% 可用、12k QPS** 的 SLA |
| 7️⃣ 常见追问 & 心得 | 幂等、跨区一致性、ML 风控、错误处理 | 预演面试官可能的深挖，展示你的 **前瞻性** 与 **系统化思考** |

> **提示**：在面试中可以先把 **最小可用系统（MVP）** 画出来（单机+同步调用），等面试官点到非功能需求时再逐层扩展，这样能保持节奏而不至于“一口气全说完”。下面我们一步一步展开。

---

## 第一步：理解需求与规模估算  

### 1️⃣ 功能需求拆解  

| 功能 | 输入 | 输出 | 关键业务点 |
|------|------|------|------------|
| **创建支付意图** | 金额、币种、支付方式、商户ID、幂等键（可选） | `payment_intent_id`、client_secret（前端后续确认使用） | **校验**（金额合法、币种支持）<br>**幂等**（防止前端重复请求） |
| **确认支付** | `payment_intent_id`、支付凭证（如卡号 token） | 支付状态（`succeeded` / `requires_action` / `failed`） | **调用第三方网关**、**风控**、**事务**（防止重复扣款） |
| **回调处理** | 第三方异步通知（order_id、状态、签名） | 更新本地支付状态、触发业务事件（通知商户、发送邮件） | **幂等**（同一回调多次到达）<br>**安全校验**（签名、IP） |
| **退款** | `payment_intent_id`、退款金额、币种 | 退款状态（`succeeded` / `pending`） | **校验退款合法性**、**跨币种换算** |
| **风控** | 交易信息流（IP、卡号、设备指纹、历史行为） | 风控分数、阻断/放行决策 | **规则引擎**、**机器学习模型**、**人工审查回流** |
| **对外 API & SDK** | REST/HTTPS 请求 | JSON 响应、错误码 | **统一错误模型**、**版本化**、**安全（HTTPS、OAuth）** |

> **注意**：所有业务必须满足 **强一致**（支付状态唯一），所以涉及多步骤的业务（创建 → 确认 → 回调）必须使用 **事务或幂等** 手段保证状态唯一。

### 2️⃣ 规模估算（依据题目给的指标）  

| 指标 | 计算过程 | 结果 |
|------|----------|------|
| **日活跃商户** | 30,000 商户 × 2 笔/商户 = 60,000 笔/天 | 60k TPS（*日*） |
| **峰值 QPS** | 12,000 QPS（已给） | 12k 请求/秒 |
| **每秒请求拆分**（近似） | 创建 40%<br>确认 30%<br>查询/查询状态 20%<br>退款 10% | 创建 4.8k/s，确认 3.6k/s，退款 1.2k/s |
| **单笔平均耗时** | 150 ms ≤ 99% | 需要 **并发 ≥ 12k * 150ms / 1000 ≈ 1800** 个工作线程/实例 |
| **存储** | 30 TB 交易日志（7 年）<br>日志 90 天 ≈ 5 TB | 需要 **分区 + 冷/热分层** |
| **可用性** | 99.99% ⇒ 1 min/月不可用 | 需要 **多活、自动故障转移** |

> **容量预估**（粗略）  
- **CPU**：假设每次调用占 30 ms CPU（含网络+业务），12k QPS → 360 k ms CPU/s ≈ 360 core‑seconds/s → **约 400 vCPU**（保守）。  
- **网络**：每次请求/响应约 2 KB → 12k × 2 KB × 2（请求+响应）≈ 48 MB/s ≈ 400 Mbps。  
- **磁盘 I/O**：每笔交易写入主表 + 审计表 ≈ 4 KB → 12k × 4 KB = 48 MB/s。

> **结论**：系统至少需要 **4 × CPU、4 × 网络、4 × 磁盘** 的冗余（每层 2 个实例），才能满足 **99.99%** 的容错需求。

---

## 第二步：高层架构设计  

### 1️⃣ MVP（最小可用系统）  

```
+-----------+      +-------------------+      +-------------------+
|   Client  | ---> |   API Gateway     | ---> |   Payment Service |
+-----------+      +-------------------+      +-------------------+
                                 |
                                 v
                         +-------------------+
                         |  Third‑Party GW   |
                         +-------------------+
```

- **API Gateway**：统一入口，做鉴权、限流、路由、TLS 终端。  
- **Payment Service**（单体）：同步调用第三方网关，使用本地 DB（MySQL）事务完成「创建 → 确认」的全链路。  
- **第三方网关**：黑盒，提供同步/异步授权接口。  

> **为什么先这样**：  
- 业务流程最清晰，**可以在 30 分钟画完**，面试官可以快速检查业务完整性。  
- 通过 **单体事务** 能直接保证 **强一致**，不需要分布式事务的复杂性。

### 2️⃣ 向可扩展系统演进  

```
                         +-------------------+
                         |   API Gateway     |
                         +-------------------+
                                 |
          +----------------------+----------------------+
          |                      |                      |
   +--------------+      +--------------+      +--------------+
   |  Auth Service|      |  RateLimiter |      |  Logging svc|
   +--------------+      +--------------+      +--------------+

          |                      |                      |
          v                      v                      v
   +----------------------------------------------------------+
   |          Service Mesh / RPC (gRPC / Thrift)              |
   +----------------------------------------------------------+
          |                      |                      |
          v                      v                      v
+----------------+   +----------------+   +----------------+
| Payment Core   |   |  Refund Service|   |  Risk Engine   |
+----------------+   +----------------+   +----------------+
          |                      |                      |
          v                      v                      v
+----------------+   +----------------+   +----------------+
|  Message Queue |   |  Message Queue |   |  Message Queue |
+----------------+   +----------------+   +----------------+
          |                      |                      |
          v                      v                      v
+----------------+   +----------------+   +----------------+
|  Payment Store |   |  Refund Store  |   |  Risk Store    |
+----------------+   +----------------+   +----------------+
```

**关键组件解释**  

| 组件 | 负责什么 | 为什么需要 |
|------|----------|------------|
| **API Gateway** | 统一入口、HTTPS、OAuth、限流、IP 白名单 | 统一安全、可独立扩容 |
| **Auth Service** | Token 验证、商户权限校验 | 业务解耦，后续支持多租户 |
| **RateLimiter** | QPS 控制、商户/IP 防刷 | 防止突发流量导致后端崩溃 |
| **Logging Service** | 结构化审计日志（ELK） | 合规要求、故障排查 |
| **Service Mesh / RPC** | gRPC、统一流量治理、重试、熔断 | 高效二进制协议、跨语言 |
| **Payment Core** | 创建、确认、回调的业务核心（幂等、事务） | 业务聚合点 |
| **Refund Service** | 退款业务（全额/部分） | 业务解耦，单独水平扩容 |
| **Risk Engine** | 规则引擎 + ML 评分 | 低耦合，支持热更新 |
| **Message Queue** (Kafka / Pulsar) | 业务事件异步化（回调、风控、通知） | 解耦、削峰、持久化 |
| **Data Stores** | 主库（MySQL/PostgreSQL）+ 只读副本 + 冷热分层 | 强一致 + 读写分离 + 长期归档 |
| **Cache** (Redis) | 幂等键、支付状态快速查询、限流计数 | 减少 DB 压力、提升响应 |

> **为何采用**：  
- **读写分离 + 缓存** → 满足 12k QPS 的读请求。  
- **消息队列** → 将 **回调、风控、通知** 异步化，防止第三方回调阻塞主业务链路。  
- **微服务拆分** → **单独扩容**（如风控流量突增时只加 Risk Engine 实例）。  
- **Service Mesh** → 统一监控、熔断、流量加密，降低跨服务调用的复杂度。

### 3️⃣ 跨地域部署（北美、欧洲、亚太）  

```
+-------------------+      +-------------------+      +-------------------+
|  Region NA        |      |  Region EU        |      |  Region APAC      |
|  (Active‑Active) |<---->|  (Active‑Active)  |<---->|  (Active‑Active)  |
+-------------------+      +-------------------+      +-------------------+
        |                         |                         |
        |   Global Load Balancer (Anycast DNS)                |
        +-----------------------------------------------------+
                                 |
                         +-------------------+
                         |  Distributed DB   |
                         |  (CockroachDB)    |
                         +-------------------+
```

- **全局负载均衡**（Anycast + Geo‑DNS）将用户请求路由到最近的 Region。  
- **数据层**采用 **分布式强一致数据库**（如 CockroachDB、TiDB）或 **两段提交 + 读写分离** 的方案，以保证 **跨区强一致**（支付状态唯一）。  
- **异步复制**（Kafka MirrorMaker）用于 **日志、审计** 的跨区备份，满足 7 年归档。  

> **不这样做的后果**：  
- 若使用 **单主多从**（MySQL 主库在 NA），跨区请求会因网络 RTT（>150 ms）导致支付确认超时，违背 150 ms SLA。  
- 若仅依赖 **最终一致**（如只读副本），会出现 **重复扣款** 或 **退款状态错乱**，破坏强一致性要求。

---

## 第三步：数据库设计  

### 1️⃣ 选型原则  

| 需求 | 推荐 DB | 理由 |
|------|----------|------|
| **强事务**（创建 → 确认） | **MySQL 8.x（InnoDB）** 或 **PostgreSQL** | 成熟、支持 ACID，易于水平分片 |
| **跨区强一致** | **CockroachDB** / **TiDB**（分布式 SQL） | 自动复制、分布式事务、兼容 MySQL 协议 |
| **审计/日志** | **ClickHouse**（列式）或 **Elasticsearch** | 高写入吞吐、支持快速查询 |
| **缓存** | **Redis**（Cluster） | 幂等键、状态快速查询、限流计数 |

> **初始实现**：使用 **单机 MySQL + 主从**（读写分离）满足 MVP，后期迁移到 **CockroachDB** 解决跨区强一致。

### 2️⃣ 核心表结构（简化版）  

```sql
-- 支付意图表（PaymentIntent）
CREATE TABLE payment_intent (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_intent_id CHAR(36) NOT NULL UNIQUE,   -- UUID
    merchant_id      BIGINT NOT NULL,
    amount           BIGINT NOT NULL,            -- 最小货币单位（cents）
    currency         CHAR(3) NOT NULL,
    payment_method   VARCHAR(32) NOT NULL,       -- card/alipay/wechat
    status           ENUM('requires_payment_method',
                         'requires_confirmation',
                         'processing',
                         'succeeded',
                         'canceled',
                         'requires_action',
                         'failed') NOT NULL DEFAULT 'requires_payment_method',
    client_secret    CHAR(64) NOT NULL,          -- 前端后续确认使用
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 幂等键（可选，由客户端提供）
    idempotency_key  VARCHAR(128) NULL,
    UNIQUE KEY uq_intent_idempotency (merchant_id, idempotency_key)
) ENGINE=InnoDB;

-- 支付记录表（Payment）
CREATE TABLE payment (
    id                BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_intent_id CHAR(36) NOT NULL,
    gateway_txn_id    VARCHAR(128) NOT NULL,  -- 第三方返回的交易号
    amount            BIGINT NOT NULL,
    currency          CHAR(3) NOT NULL,
    status            ENUM('authorized','captured','failed','refunded') NOT NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_intent_id) REFERENCES payment_intent(payment_intent_id)
) ENGINE=InnoDB;

-- 退款表（Refund）
CREATE TABLE refund (
    id                BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_intent_id CHAR(36) NOT NULL,
    amount            BIGINT NOT NULL,
    currency          CHAR(3) NOT NULL,
    status            ENUM('pending','succeeded','failed') NOT NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_intent_id) REFERENCES payment_intent(payment_intent_id)
) ENGINE=InnoDB;

-- 风控日志表（RiskLog）
CREATE TABLE risk_log (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_intent_id CHAR(36) NOT NULL,
    score         SMALLINT NOT NULL,
    rule_hit      VARCHAR(256) NULL,
    decision      ENUM('allow','review','block') NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_intent (payment_intent_id)
) ENGINE=InnoDB;
```

### 3️⃣ 幂等实现细节  

1. **创建意图**：客户端可以带 `Idempotency-Key`（如订单号）。在 `payment_intent` 表上建立 **唯一索引** (`merchant_id`, `idempotency_key`)。  
2. **确认支付**：同样在 `payment` 表上使用 `gateway_txn_id` 作为唯一键，防止同一笔第三方交易被多次写入。  
3. **回调**：使用第三方提供的 `gateway_txn_id` + `timestamp` 组合做 **幂等键**，写入 `payment` 表前先 `SELECT FOR UPDATE` 检查是否已存在同状态记录。  

> **不加唯一索引的后果**：在网络抖动或客户端重试时，可能出现 **重复扣款**，导致财务纠纷和合规风险。

### 4️⃣ 事务与锁  

- **创建 → 确认**：在 `payment_intent` 表上 **行级锁**（`SELECT ... FOR UPDATE`），确保同一意图在同一时间只能进入确认流程。  
- **回调**：同样 **行级锁**，并在 `payment` 表插入后 **更新 payment_intent.status**。  
- **退款**：在 `payment` 表上加锁，确保 **同一笔支付只能一次成功退款**（或部分退款累计不超过原金额）。

---

## 第四步：核心 API 设计  

### 1️⃣ 统一错误模型  

| HTTP 状态码 | 错误码 | 含义 | 示例 |
|------------|--------|------|------|
| 400 | `invalid_parameter` | 参数缺失或非法 | `{ "code":"invalid_parameter","message":"amount must be >0" }` |
| 401 | `unauthorized` | Token 无效/过期 | `...` |
| 404 | `not_found` | 资源不存在（payment_intent_id） | `...` |
| 409 | `idempotent_conflict` | 幂等键冲突（已存在不同状态） | `...` |
| 422 | `risk_blocked` | 风控阻断 | `...` |
| 500 | `internal_error` | 系统异常 | `...` |
| 502 | `gateway_error` | 第三方支付网关不可达 | `...` |

### 2️⃣ API 列表（RESTful）  

| 方法 | 路径 | 功能 | 关键字段 |
|------|------|------|----------|
| `POST /v1/payment_intents` | 创建支付意图 | `amount, currency, payment_method, idempotency_key` | 返回 `payment_intent_id, client_secret` |
| `POST /v1/payment_intents/{id}/confirm` | 确认支付 | `payment_method_token`（前端加密后） | 返回 `status`（`succeeded`/`requires_action`） |
| `GET /v1/payment_intents/{id}` | 查询状态 | - | 返回完整支付意图对象 |
| `POST /v1/refunds` | 发起退款 | `payment_intent_id, amount` | 返回 `refund_id, status` |
| `GET /v1/refunds/{id}` | 查询退款 | - | 返回退款详情 |
| `POST /v1/webhook` | 第三方回调入口 | 验签后异步更新状态 | 业务内部使用，不对外公开 |

### 3️⃣ 示例：创建支付意图  

```http
POST /v1/payment_intents HTTP/1.1
Host: api.payment.myshop.com
Authorization: Bearer <access_token>
Idempotency-Key: order_20230815_12345
Content-Type: application/json

{
  "amount": 1999,
  "currency": "USD",
  "payment_method": "card"
}
```

**响应**  

```json
{
  "payment_intent_id": "pi_1Gq2xJ2eZvKYlo2C9k8tXyZL",
  "client_secret": "secret_7b2e0c3f0a1d...",
  "status": "requires_confirmation",
  "created": 1693312000
}
```

> **为什么使用 `Idempotency-Key` 放在 Header**：符合 Stripe、PayPal 的惯例，便于网关统一拦截，避免业务层重复判断。

### 4️⃣ 示例：确认支付（同步）  

```http
POST /v1/payment_intents/pi_1Gq2xJ2eZvKYlo2C9k8tXyZL/confirm HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "payment_method_token": "tok_visa_123456"
}
```

**响应（成功）**  

```json
{
  "payment_intent_id": "pi_1Gq2xJ2eZvKYlo2C9k8tXyZL",
  "status": "succeeded",
  "charge_id": "ch_1Gq3aJ2eZvKYlo2C9gB5Tn2V",
  "created": 1693312010
}
```

> **如果需要 3D Secure**：返回 `requires_action`，前端再调用 `/v1/3ds/handle`（这里省略）。

---

## 第五步：详细组件设计  

### 1️⃣ API Gateway  

- **技术选型**：Nginx + Lua（OpenResty） 或 **Kong**（插件化）  
- **功能**：TLS 终止、OAuth2/JWT 鉴权、IP 白名单、请求体大小限制、**Rate Limiting**（基于商户 ID + IP）  
- **实现幂等**：在网关层先检查 `Idempotency-Key` 是否已存在于 **Redis**（TTL = 24h），若存在直接返回缓存的响应，避免进入业务层重复处理。

### 2️⃣ Auth Service  

- **JWT**（签名使用 RSA-256，密钥轮换）  
- **商户角色**：`read`, `write`, `admin`，通过 **ABAC**（属性）控制每个 API 能否访问。  

### 3️⃣ Payment Core Service  

#### 3.1 工作流（时序图）  

```
Client -> API GW -> Payment Core
   1. CreateIntent
      - 检查幂等键 (Redis)
      - DB: INSERT payment_intent (status=requires_confirmation)
      - 返回 client_secret

   2. ConfirmIntent
      - DB: SELECT FOR UPDATE payment_intent
      - 调用 Risk Engine (同步)
          * 若 block -> 返回 422
      - 调用 Third‑Party GW (同步)
          * 成功返回 gateway_txn_id
      - DB: INSERT payment (gateway_txn_id, status=authorized)
      - DB: UPDATE payment_intent.status = succeeded
      - 发送 Kafka 事件: PaymentSucceeded
      - 返回 success

   3. Async Callback (Webhook)
      - API GW -> Payment Core (Webhook endpoint)
      - 校验签名
      - DB: SELECT FOR UPDATE payment_intent
      - 幂等判断：如果状态已经是 final，则直接 ACK
      - UPDATE status (e.g., requires_action → succeeded)
      - 发送 Kafka 事件: PaymentUpdated
```

#### 3.2 幂等关键点  

| 场景 | 幂等键 | 实现方式 |
|------|--------|----------|
| 创建 Intent | `Idempotency-Key` (Header) + `merchant_id` | Redis + DB 唯一索引 |
| 确认支付 | `payment_intent_id` + `gateway_txn_id` | DB `UNIQUE(gateway_txn_id)`，若冲突返回已存在状态 |
| 第三方回调 | `gateway_txn_id` + `callback_timestamp` | `SELECT FOR UPDATE` 检查状态，若已是终态直接 ACK |

#### 3.3 错误处理 & 重试  

- **第三方网关超时**：使用 **Hystrix/Resilience4j** 超时 5 s，返回 `gateway_error`，前端可自行重试。  
- **数据库死锁**：捕获 `SQLTransactionRollbackException`，**指数退避**重试最多 3 次。  
- **Kafka 发送失败**：本地事务提交后立即 **回退到本地表**（补偿表 `payment_event_retry`），后台 **重试任务**负责重新投递。

### 4️⃣ Refund Service  

- **流程**：  
  1. **检查原支付**是否为 `succeeded`。  
  2. **计算可退款金额**（已退款累计 ≤ 原金额）。  
  3. **调用第三方网关退款接口**（同步）。  
  4. **事务写入 `refund` 表**，状态 `pending` → `succeeded`（回调）  
  5. **发送 Kafka 事件** `RefundCompleted`。  

- **幂等**：`refund_idempotency_key`（如原订单号+refund_seq） + `UNIQUE` 约束。

### 5️⃣ 风控引擎（Risk Engine）  

#### 5.1 规则引擎  

- 使用 **Drools** 或 **Open Policy Agent (OPA)** 实现 **基于规则的实时判定**。  
- 规则示例：  
  - 同一 IP 5 分钟内 > 10 笔支付 → `review`  
  - 卡号首次出现，且金额 > 1000 USD → `review`  

#### 5.2 ML 实时评分  

| 步骤 | 说明 |
|------|------|
| **特征获取** | 通过 **Kafka** 实时流收集：IP、User‑Agent、设备指纹、历史交易频率、地理位置等。 |
| **模型部署** | 使用 **TensorFlow Serving** 或 **Seldon**，提供 **REST/gRPC** 推理接口。 |
| **调用方式** | **同步**：Payment Core 在确认前调用 `/score`，设定 **超时 30 ms**，若超时直接返回 **默认分数**（降级）。 |
| **降级策略** | - 超时或模型不可用 → 使用 **规则引擎** 的最低风险分数。<br>- 高风险分数 → 返回 `review`，需要人工审查（后置任务）。 |

#### 5.3 人工审查回流  

- 将 `review` 状态写入 **Kafka topic `risk_review`**。  
- **后台审查系统**（Web UI）人工判定后，通过 **REST** 调用 **Payment Core** 的 `/review/decision` 接口，将状态改为 `allow` 或 `block`。

### 6️⃣ 第三方支付网关适配层  

- **统一抽象接口**：`PaymentGatewayAdapter`，实现 **Visa**, **MasterCard**, **Alipay**, **WeChat**。  
- **策略模式**：运行时根据 `payment_method` 动态选取实现。  
- **安全**：所有敏感数据（卡号、CVV）在前端加密后只传 **token**（PCI‑DSS 合规），网关适配层只持有 token，不保存明文。  

### 7️⃣ 监控、告警、日志  

| 维度 | 采集方式 | 关键指标 |
|------|----------|----------|
| **业务** | Prometheus + Exporter（每个服务） | QPS、成功率、错误码分布、平均延迟、幂等冲突率 |
| **链路追踪** | OpenTelemetry → Jaeger | 请求全链路时延、异常节点 |
| **日志** | FluentBit → Elasticsearch + Kibana | 结构化日志（request_id、merchant_id、status） |
| **告警** | Alertmanager | 延迟 > 200 ms、错误率 > 1%、第三方网关不可达、Kafka 消费积压 > 5 min |
| **审计** | 写入 ClickHouse（只读） | 所有支付状态变更、退款操作、风控决策 |


---

## 第六步：扩展性与高可用设计  

### 1️⃣ 多活部署（同城/跨城）  

- **同城多活**：在每个 Region 部署 **N 个实例**（API GW、Payment Core、Refund、Risk）并通过 **内部负载均衡（LVS/Envoy）** 实现**无共享状态**。  
- **跨城容灾**：  
  - **数据层**使用 **CockroachDB** 的多活复制（每个 Region 一个 replica），写入自动在多数节点提交（Quorum = 2/3）。  
  - **异步日志**（Kafka）使用 **MirrorMaker** 把每个 Region 的 Topic 同步到其它 Region，保证 **审计** 与 **补偿** 能在任意 Region 完成。  
  - **故障切换**：Global DNS（AWS Route53）健康检查失效后，将流量切换到剩余 Region。  

### 2️⃣ 分布式事务方案  

| 场景 | 方案 | 说明 |
|------|------|------|
| 支付确认（写 `payment_intent` + `payment`） | **单库事务**（MySQL） + **行锁**（在单 Region） | 简单、性能好。跨 Region 使用 **分布式事务** 只在极少数跨区场景（如 EU → NA 迁移）才会触发。 |
| 跨区强一致（如同一笔支付在 NA 与 EU 同时到达） | **两阶段提交 (2PC) + Paxos**（CockroachDB 自带） | 自动保证全局唯一状态，开发者只需使用 **SQL**，底层实现 2PC。 |
| 补偿事务（退款失败后回滚） | **Saga 模式**（基于 Kafka 事件） | 每一步都有对应的补偿操作，避免长事务锁表。 |

### 3️⃣ 缓存 & 读写分离  

- **读写分离**：主库负责写，**副本**提供查询（如 `GET /payment_intents/{id}`），副本延迟 ≤ 100 ms。  
- **Redis 缓存**：  
  - `payment_intent:{id}` → JSON（TTL 30 min）  
  - `idempotency:{merchant_id}:{key}` → `payment_intent_id`（TTL 24h）  
- **缓存失效策略**：写成功后 **同步删除/更新**，避免脏读。  

### 4️⃣ 限流与熔断  

- **限流**：在 API GW 使用 **Token Bucket**，每个商户配额（如 20 QPS），全局限流 12k QPS。  
- **熔断**：对第三方网关调用使用 **Resilience4j**，错误率 > 50%（5s窗口）则熔断 30s，返回 `gateway_error`，防止雪崩。  

### 5️⃣ 数据备份 & 合规  

| 数据 | 备份方式 | 保留时长 |
|------|----------|----------|
| 主库（交易表） | 每日全量快照 + 增量日志（PITR） | 7 年 |
| 审计日志 | ClickHouse 按天分区 → S3 冷存 | 7 年 |
| Kafka 事件 | Mirror + 主题保留 30 天 | 30 天 |
| 配置（风控规则） | GitOps + ConfigMap（K8s） | 版本化 |  

### 6️⃣ 灰度发布 & 回滚  

- **Canary Deploy**：使用 **Kubernetes** 的 **Deployment** + **Service Mesh**（Istio）实现 5% 流量灰度。  
- **回滚**：若新版本出现异常，立即 **Istio** 关闭新版本流量，回滚 Deployment。  

---

## 第七步：常见面试追问与回答  

### 1️⃣ 幂等设计细节  

**问**：如果同一个 `payment_intent_id` 的确认请求被重复发送，系统如何保证不产生二次扣款？  

**答**：  

1. **业务层幂等键**：使用 `payment_intent_id + gateway_txn_id` 作为唯一约束，`payment` 表的 `gateway_txn_id` 建唯一索引。  
2. **先锁后检查**：在确认入口对 `payment_intent` 做 `SELECT ... FOR UPDATE`，如果状态已经是 `succeeded`，直接返回已成功的响应，不再调用第三方。  
3. **幂等缓存**：在 Redis 中保存 `confirm:{payment_intent_id}` → `status`，TTL 与交易生命周期相同，防止 DB 锁争用导致的热点。  
4. **回调幂等**：第三方回调会带 `gateway_txn_id`，在处理回调时同样先 `SELECT FOR UPDATE` 并检查 `payment.status` 是否已是最终状态。  

> **若不做这些**，网络抖动导致客户端重试会导致 **重复扣款**，进而产生退款、财务纠纷，违背支付系统的 **强一致** 与 **高可靠** 要求。

---

### 2️⃣ 跨地域一致性  

**问**：在北美、欧洲、亚太分别部署数据中心时，如何处理跨区的交易一致性与延迟？  

**答**：  

1. **使用分布式强一致数据库**（CockroachDB / TiDB）：
   - 每个 Region 部署一个 replica，写入时采用 **Quorum (N/2+1)** 提交，确保即使一个 Region 故障，其他 Region 仍可提供最新数据。  
   - 由于内部采用 **Raft** 协议，写入延迟约 30‑50 ms（同城）+ 额外网络 RTT（跨区 80‑120 ms），仍在 150 ms SLA 范围。  

2. **读写分离 + 本地缓存**：
   - 大部分查询（如查询支付状态）走 **本地副本** 或 **Redis**，避免跨区网络导致延迟。  
   - 只在 **创建/确认** 时走 **全局事务**，降低跨区流量。  

3. **异步复制**：
   - 业务日志（审计、风控）采用 **Kafka MirrorMaker** 进行跨区复制，保证 **最终一致**，不影响核心支付路径。  

4. **容错切换**：
   - 当某 Region 网络分区导致写入超时，系统会 **降级为本地读写**（只在本地 Region 完成），并在网络恢复后 **补偿同步**（使用 Saga 补偿日志）。  

> **不采用强一致**（如只用单主多从）会导致 **读到旧状态**（比如确认后查询仍是 `processing`），前端可能重复发起确认，进而产生 **重复扣款**。  

---

### 3️⃣ 风控与机器学习模型的集成  

**问**：如果需要在支付流程中加入机器学习模型进行实时欺诈评分，如何在不影响主链路性能的前提下进行集成？  

**答**：  

1. **模型部署**：使用 **TensorFlow Serving** 或 **Seldon** 部署为 **独立的预测服务**，提供 **REST/gRPC** 接口，支持 **水平扩展**。  
2. **特征采集**：在 **Payment Core** 收到确认请求时，从 **Redis**、**MySQL**、**Kafka** 中快速拉取最近 30 天的行为特征（IP、设备指纹、历史交易频次），这些特征已预先 **缓存**，获取耗时 < 5 ms。  
3. **同步调用 + 超时降级**：在确认路径中同步调用模型服务，**设置 30 ms 超时**（通过 Resilience4j），若超时或模型不可用，直接使用 **规则引擎** 给出的最低风险分数。  
4. **异步回流**：若模型返回 **高风险**（score > 0.9），将交易标记为 `review`，并 **异步写入 Kafka topic `risk_review`**，后台人工审查后通过 **/review/decision** 接口更新状态。  
5. **模型热更新**：模型文件存放在 **对象存储（S3）**，预测服务通过 **watcher** 自动 reload，**不需要重启**。  

> **如果直接在主链路做大量特征计算或同步调用**，会把 **网络 + 计算** 的耗时推到 200‑300 ms，破坏 150 ms SLA。采用 **缓存 + 超时降级** 能保证 **性能可控**，同时仍能获得实时风险判断。

---

### 4️⃣ 其他可能的追问  

| 追问 | 简要回答 |
|------|----------|
| **如何保证 PCI‑DSS 合规？** | 前端使用 **Stripe.js‑style tokenization**，后端仅持有 **token**，不保存卡号、CVV；敏感数据在 **HTTPS** 端到端加密；审计日志脱敏；仅使用 **合规的第三方收单机构**。 |
| **如何防止重放攻击的回调？** | 回调使用 **签名+时间戳**，服务器校验签名后检查 **timestamp 与当前时间差 ≤ 5 min**，并在 **Redis** 中记录已处理的 `gateway_txn_id`，幂等过滤。 |
| **如果第三方网关返回 202（处理中）怎么办？** | 将 `payment_intent.status` 设为 `processing`，并把 `gateway_txn_id` 放入 **Kafka**，后台 **轮询**（或 webhook）获取最终结果，完成状态更新。 |
| **如何做灰度发布防止新规则导致误拦截？** | 在 **OPA** 中使用 **versioned policy**，新规则先在 **canary** 流量（5%）中生效，监控 `review` 率和错误率，若无异常再全量推送。 |
| **如何处理跨币种退款的汇率问题？** | 在 `refund` 表记录 **原币种、目标币种、汇率快照**（从内部汇率服务获取），退款金额 = 原币种退款额 × 汇率，确保审计可追溯。 |

---

## 心得与反思  

### 1️⃣ 本题最难的 1‑2 个设计决策  

| 决策 | 关键难点 | 思考过程 |
|------|----------|----------|
| **跨区强一致 vs. 延迟** | 需要在 **99.99% 可用** 与 **150 ms 延迟** 之间找到平衡。若采用传统 **主‑从**，跨区读取会慢且可能产生脏读；若采用 **最终一致**，会导致重复扣款风险。 | 先列出 **业务核心**（支付状态唯一）必须强一致，后调研分布式 SQL（CockroachDB）提供 **强一致、自动多活** 的能力。通过 **Quorum** 写入、**本地读副本** 读取，既满足强一致，又把大多数查询放在本地，控制延迟。 |
| **幂等实现的粒度** | 支付系统中每一步（创建、确认、回调、退款）都可能被重试，必须保证 **全链路幂等**，否则会产生 **重复扣款** 或 **错误退款**。 | 将 **幂等键** 明确为 **业务唯一标识 + 外部唯一标识**（如 `gateway_txn_id`），在 **数据库唯一约束** + **Redis 缓存** 双保险。随后在每个入口都加入 **SELECT FOR UPDATE**，确保在高并发下仍然只能执行一次业务。 |

### 2️⃣ 新手最容易犯的错误  

| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把所有业务都放在同一个单体服务** | 随着 QPS 增长，单体容易成为性能瓶颈，扩容困难，故障影响全链路。 | 按职责拆分为 **Payment Core、Refund、Risk、Webhook** 等微服务，使用 **轻量 RPC**（gRPC）或 **消息队列** 解耦。 |
| **忽视幂等/重复请求的处理** | 网络抖动或客户端重试会导致 **二次扣款**，产生财务纠纷和合规风险。 | 在每个写操作前 **加唯一索引**，并在业务入口实现 **幂等键** 检查（Redis + DB）。 |
| **直接同步调用第三方回调** | 第三方回调慢会阻塞主业务，导致 **响应超时**，影响用户体验。 | 将回调处理 **异步化**（Kafka），主业务只返回成功/处理中状态，回调完成后更新状态并发送事件。 |
| **只考虑单机容量，忽略跨区网络** | 跨区部署后出现 **高延迟** 或 **数据不一致**，违背 SLA。 | 采用 **分布式强一致 DB** 或 **两阶段提交**，并把读请求本地化。 |
| **把风控规则写死在代码里** | 业务需要快速迭代时无法灵活调整，导致 **上线风险**。 | 使用 **规则引擎（Drools/OPA）** + **可热更新的配置**，把风控策略抽离为数据/脚本。 |

### 3️⃣ 学习建议和可延伸的方向  

| 方向 | 推荐资源 | 学习要点 |
|------|----------|----------|
| **分布式事务与强一致数据库** | 《Designing Data‑Intensive Applications》, CockroachDB 官方文档 | 理解 **Raft、Paxos、Quorum**，实践 **事务模型**（2PC、Saga）。 |
| **支付行业合规** | PCI‑DSS 官方指南、Stripe/PayPal 开发者文档 | 学习 **敏感数据处理、Tokenization、审计要求**。 |
| **微服务通信** | 《Building Microservices》, Istio 官方教程 | 掌握 **gRPC、Envoy、Service Mesh** 的流量治理、熔断、限流。 |
| **高可用架构** | 《Site Reliability Engineering》, AWS Well‑Architected Framework | 了解 **跨地域灾备、自动故障转移、监控告警** 实践。 |
| **机器学习在风控中的落地** | 《Real‑Time Machine Learning》, Seldon 文档 | 认识 **特征工程、模型部署、在线推理延迟、降级策略**。 |
| **系统设计面试技巧** | 《系统设计面试》、Tech interview 公开课 | 练习 **从需求 → 估算 → 架构 → 细化** 的完整流程，学会 **结构化表达**。 |

> **最关键的学习路径**：先把 **业务核心**（支付状态、幂等）在 **单体 + 强一致 DB** 中实现；再逐步引入 **微服务、异步化、跨区复制**，每一步都要 **写单元测试 + 监控指标**，这样既能满足面试深度，又能让你在真实项目中落地。  

---  

**祝你在面试中把 Stripe 这套支付系统讲得条理清晰、技术扎实，拿到满意的 Offer！** 🚀  
