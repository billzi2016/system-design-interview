# 第 56 天：设计 Jira 项目管理

> 生成日期：2026-03-31

---

## 题目背景
Jira 是一款面向软件开发团队的项目管理与 Issue 跟踪系统，帮助团队进行需求规划、任务分配、进度跟踪和缺陷管理。面试官希望你设计一个 **可水平扩展、支持全球大型企业使用的 Jira 核心服务**。

---

## 面试场景设定
> **面试官**：  
> “我们公司计划在现有的 Jira 产品上进行一次大规模的架构升级，需要支撑数十万活跃用户、跨地域的实时协作以及海量历史数据。请你从零开始设计一个核心的 Jira 项目管理系统，重点关注高可用、低延迟和水平扩展能力。请先阐述整体思路，然后我们会逐步深入细节。”

---

## 功能性需求
1. **创建 / 编辑 / 删除 Issue**  
   - 支持自定义字段、附件、评论、子任务等。  
2. **工作流引擎**  
   - 支持可配置的状态流转（如 “待办 → 进行中 → 完成”），并触发相应的通知和钩子。  
3. **看板 / Sprint 管理**  
   - 实时展示 Board、Backlog、Sprint 进度，支持拖拽修改 Issue 所在列。  
4. **搜索与过滤**  
   - 基于 JQL（Jira Query Language）实现全文检索、过滤、排序，返回实时结果。  
5. **通知与实时协作**  
   - 通过 WebSocket / Server‑Sent Events 推送评论、状态变更等实时事件；邮件/Slack 等渠道的离线通知。  
6. **权限与角色管理**  
   - 项目、看板、Issue 级别的细粒度权限控制（阅读、编辑、转移、删除等）。

---

## 非功能性需求（估算）

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **日活跃用户 (DAU)** | 300,000 人 | 包括企业内部用户和外部协作者 |
| **每秒请求数 (QPS)** | 15,000 QPS 峰值 | 主要集中在 Issue 创建、状态更新、搜索等热点操作 |
| **平均响应时延** | ≤ 200 ms（99% 请求） | 对编辑、搜索等交互操作的响应 |
| **可用性** | ≥ 99.95%（月均累计不可用 ≤ 22 分钟） | 支持多可用区容灾 |
| **存储容量** | 200 TB 有效数据（包括 Issue 元数据、附件、审计日志） | 预计每年增长 30% |
| **数据一致性** | 最终一致性 + 关键业务（状态流转）强一致性 | 采用事务或幂等设计保证关键路径一致性 |

---

## 系统边界

**本题范围内需要设计的部分**  
- Issue/工作流核心数据模型与存储方案  
- API 网关、业务层、搜索服务、实时推送服务的整体架构  
- 数据分片、缓存、负载均衡、容灾方案  
- 权限校验、审计日志的基本实现  
- 监控、日志、报警等运维支撑

**本题范围外（不必深入）**  
- UI 前端实现细节（仅需说明前后端交互接口）  
- 第三方插件生态（如 Marketplace）  
- 企业级 SSO、LDAP、OAuth2 集成细节  
- 费用模型与计费系统  
- 离线导入/导出（CSV、XML）的大规模实现  

---

## 提示与追问

1. **数据一致性**：  
   - “在高并发状态流转时，如何保证同一个 Issue 不会出现冲突的状态更新？”  
2. **搜索实现**：  
   - “如果使用 Elasticsearch，如何处理实时性与一致性之间的权衡？”  
3. **扩展性**：  
   - “当用户量从 30 万增长到 300 万时，哪些模块最先需要水平扩容，如何做到无缝迁移？”  

---

# 题解

## 解题思路总览

本答案把 **“从 0 开始、一步步把一个最小可用的 Jira 核心服务”** 当作一次“建房子”的过程来讲解。  
- **先搭地基**：弄清业务需求、用户规模、性能目标。  
- **再画蓝图**：划分系统边界、画出高层架构。  
- **接着铺砖**：选数据库、设计表结构、决定事务模型。  
- **再装门窗**：定义对外 API（REST、WebSocket），明确请求/响应格式。  
- **随后装饰**：实现搜索、实时推送、权限校验、审计日志等关键组件。  
- **最后加固**：讨论分片、缓存、负载均衡、容灾、监控等高可用/可扩展手段。  

每一步都会 **解释“为什么这样做”，以及如果不这么做会出现什么问题**，帮助完全没有系统设计经验的同学建立完整的思考框架。

---

## 第一步：理解需求与规模估算

### 1. 功能性需求要点

| 功能 | 关键点 | 关联的核心资源 |
|------|--------|----------------|
| Issue CRUD | 自定义字段、附件、子任务、版本历史 | Issue 表、Attachment 存储、Audit Log |
| 工作流引擎 | 状态流转、条件/触发器、事务一致性 | Workflow 表、State Machine、事件总线 |
| 看板 / Sprint | 实时排序、拖拽修改列 | Board、Sprint、Issue‑Board 关联表 |
| 搜索 & 过滤 | JQL → 全文检索、排序、分页 | Elasticsearch (或 OpenSearch) |
| 实时协作 | 评论/状态变更即时推送 | WebSocket / SSE、Message Queue |
| 权限/角色 | 项目/看板/Issue 细粒度 ACL | Role、Permission、Project‑User 表 |

> **为什么先列出这些**：在后面的数据库、缓存、分片设计里，需要知道哪些数据是**热点**（如 Issue 状态、评论）以及哪些是**只读/检索**（如全文搜索）。  

### 2. 非功能性需求（数值化）

| 指标 | 目标值 | 计算方式 / 业务意义 |
|------|--------|----------------------|
| DAU | 300 k | 影响并发、缓存容量、连接数 |
| 峰值 QPS | 15 k | 设计每个服务的水平扩容基准 |
| 响应时延 ≤ 200 ms（99%） | 交互式编辑/搜索必须快 | 决定是否使用缓存、同步/异步路径 |
| 可用性 ≥ 99.95% | 月均 ≤ 22 min downtime | 需要多 AZ、自动故障转移 |
| 存储 200 TB（+30%/年） | 大量 Issue、附件、审计日志 | 决定冷热分层、对象存储方案 |
| 强一致性（状态流转）+最终一致性（搜索） | 业务正确性 + 高吞吐 | 需要混合事务模型、异步索引 |

> **为什么要把这些数字写下来**：它们是后面所有容量/性能/成本计算的“种子”。如果没有明确的数字，设计很容易“漂移”——要么过度设计浪费资源，要么不足导致性能瓶颈。

### 3. 关键业务流程（简化版）

1. **创建 Issue** → 写入 Issue DB → 生成审计日志 → 发送事件到 MQ → 异步写入搜索索引 → 返回成功。
2. **状态流转** → 检查工作流规则 → 在事务内更新 Issue 状态（强一致） → 写审计日志 → 通过 MQ 推送实时通知 → 异步更新搜索索引。
3. **搜索** → 用户发送 JQL → API 层将 JQL 转换为 ES DSL → 查询 Elasticsearch → 结果返回（最终一致）。
4. **实时协作** → 评论或状态变更 → 写入 DB → 通过 MQ 推送 WebSocket 消息 → 前端实时展示。

> **为什么画流程图**：帮助我们找出 **同步路径（必须强一致）** 与 **异步路径（可最终一致）**，从而决定哪些操作走事务、哪些走消息队列。

---

## 第二步：高层架构设计

### 1. 先画最小可用系统（MVP）

```
+-------------------+      +-------------------+      +-------------------+
|   前端 (Web)      | <--->|   API Gateway    | <--->|   Issue Service   |
+-------------------+      +-------------------+      +-------------------+
                                   |                     |
                                   v                     v
                           +----------------+   +----------------+
                           |   MySQL (RDB)  |   |   Elasticsearch|
                           +----------------+   +----------------+
```

- **API Gateway**：统一入口、做路由、限流、鉴权、监控。
- **Issue Service**：单体业务服务，负责 Issue CRUD、工作流、权限校验。
- **MySQL**：事务强一致存储 Issue 主数据、工作流、权限等。
- **Elasticsearch**：搜索索引，使用 **异步同步**（写入 MySQL 后通过 MQ 触发同步）。

> **为什么先从单体做起**：  
> - 逻辑最清晰，易于实现和演示。  
> - 能快速验证业务模型（表结构、事务）。  
> - 在面试中，面试官往往先看你是否能把系统拆解成“最小可运行的单元”。  

### 2. 向分布式、可扩展演进的完整蓝图

```
                               +-------------------+
                               |   CDN / WAF       |
                               +-------------------+
                                         |
                               +-------------------+
                               |   API Gateway     |
                               +-------------------+
        +------------+-----------+-----------+-------------+-----------+
        |            |                       |                         |
+-------v-----+ +----v----+            +-----v------+            +-------v------+
| Auth Service| |Rate Lim.|            |  Config   |            |  Logging   |
+-------------+ +---------+            +------------+            +------------+

        |                                                    |
        v                                                    v
+-------------------+    +--------------------+    +-------------------+
|  Load Balancer    |----|  Issue Service 1   |----|  MySQL Primary   |
+-------------------+    +--------------------+    +-------------------+
        |                     |  (stateless)    |    |  Replicas (read) |
        |                     v                 |    +-------------------+
        |                +--------------------+ |
        |                |  Issue Service N   | |
        |                +--------------------+ |
        |                     |  (stateless)    |
        v                     v                 v
+-------------------+   +-------------------+  +-------------------+
|  Search Service   |---|  MQ (Kafka)       |--|  Elasticsearch   |
+-------------------+   +-------------------+  +-------------------+

        |                     |
        v                     v
+-------------------+   +-------------------+
|  Notification    |   |  Attachment Store |
|  Service (WS)    |   |  (Object Storage) |
+-------------------+   +-------------------+

        |
        v
+-------------------+
|  Audit Log Service|
+-------------------+
```

#### 关键组件解释

| 组件 | 作用 | 为什么需要 |
|------|------|------------|
| **CDN / WAF** | 静态资源、基本安全防护 | 防止 DDoS、SQLi、XSS 等攻击；降低入口负载 |
| **API Gateway** | 统一入口、路由、鉴权、限流、灰度发布 | 避免每个微服务重复实现这些公共功能 |
| **Auth Service** | 统一的 token 生成/校验（JWT/OIDC） | 解耦业务服务的鉴权逻辑 |
| **Rate Limiting** | 防止单用户刷接口 | 保护后端免受突发流量冲击 |
| **Config Service** | 动态读取业务配置（工作流、字段） | 支持热更新、避免重启 |
| **Logging / Tracing** | 集中日志、分布式链路追踪（OpenTelemetry） | 故障定位、性能分析 |
| **Load Balancer** | 将请求均衡到多实例 | 实现水平扩容 |
| **Issue Service**（多实例） | 核心业务，**无状态**，所有状态保存在 DB | 便于水平扩容 |
| **MySQL 集群** | 主从复制或 Galera / TiDB，提供强一致事务 | 关键业务（状态流转）必须强一致 |
| **Message Queue (Kafka)** | 业务事件解耦、可靠异步 | 实现 **写‑读分离**、搜索索引异步更新、通知 |
| **Search Service + Elasticsearch** | JQL 解析、全文检索 | 读多写少的场景，使用最终一致 |
| **Notification Service (WebSocket)** | 实时推送评论、状态变更 | 低延迟、保持长连接 |
| **Attachment Store** | 大文件对象存储（S3 / OSS） | 直接使用对象存储的高可用、分片能力 |
| **Audit Log Service** | 记录所有操作（谁、何时、何事） | 合规审计、回滚依据 |

> **为什么要把这些组件拆分**  
> - **单体 → 微服务**：随着 QPS 增大，单体的 CPU/内存会成为瓶颈，拆分后可以针对热点（搜索、通知）单独扩容。  
> - **强一致 vs 最终一致**：通过 **事务 + MQ** 把强一致操作与最终一致的搜索解耦，既保证业务正确性，又提升整体吞吐。  
> - **无状态服务**：让每个实例可以随时加入/剔除，配合 **容器编排（K8s）** 实现弹性伸缩。

---

## 第三步：数据库设计

### 1. 选型决策

| 数据类型 | 推荐存储 | 解释 |
|----------|----------|------|
| 结构化业务核心（Issue、Workflow、Permission） | **关系型数据库**（MySQL 8.x + InnoDB） | 支持 ACID、强事务、复杂 JOIN，满足状态流转的强一致需求。 |
| 大文件附件 | **对象存储**（Amazon S3 / MinIO） | 直接按对象键访问，具备高可用、冷热分层、CDN 加速。 |
| 搜索索引 | **Elasticsearch**（或 OpenSearch） | 倒排索引、聚合、全文检索，天然支持分片、复制。 |
| 事件日志/审计 | **时序/宽列**（ClickHouse / Cassandra） | 高写入吞吐、压缩率好，适合分析查询。 |
| 缓存 | **Redis Cluster** | 读热点缓存、会话、分布式锁。 |

> **不使用 NoSQL 直接存 Issue**：虽然 NoSQL（如 MongoDB）可以水平扩展，但它缺少跨表事务，**状态流转**需要保证“一致性+唯一性”，使用关系型 DB 更安全。

### 2. 核心表结构（MySQL）

> 为了让新手更易读，下面用 **Markdown 表格** 给出每张表的关键字段、索引、说明。

#### 2.1 `project` 表（项目）

| 字段 | 类型 | 主键/索引 | 备注 |
|------|------|-----------|------|
| `id` | BIGINT UNSIGNED | PK | 自动递增 |
| `key` | VARCHAR(10) | UNIQUE | 项目唯一标识（如 `JRA`） |
| `name` | VARCHAR(255) |  | 项目名称 |
| `owner_user_id` | BIGINT |  | 项目所有者 |
| `created_at` | DATETIME |  | 创建时间 |
| `updated_at` | DATETIME |  | 最近一次更新 |

#### 2.2 `issue` 表（核心 Issue）

| 字段 | 类型 | 主键/索引 | 备注 |
|------|------|-----------|------|
| `id` | BIGINT UNSIGNED | PK | 自动递增 |
| `project_id` | BIGINT UNSIGNED | IDX (`project_id`) | 所属项目 |
| `issue_key` | VARCHAR(20) | UNIQUE (`project_id`,`issue_key`) | 如 `JRA-123` |
| `summary` | VARCHAR(512) |  | 简短描述 |
| `description` | TEXT |  | 详细描述（Markdown） |
| `status` | VARCHAR(32) | IDX (`status`) | 当前工作流状态 |
| `type` | VARCHAR(32) |  | Bug / Task / Story … |
| `priority` | VARCHAR(32) |  | 高/中/低 |
| `assignee_user_id` | BIGINT | IDX (`assignee_user_id`) | 当前负责人 |
| `reporter_user_id` | BIGINT |  | 报告人 |
| `created_at` | DATETIME |  | 创建时间 |
| `updated_at` | DATETIME |  | 最近一次更新 |
| `version` | BIGINT |  | 乐观锁字段（防并发） |

> **乐观锁 (`version`)**：在高并发状态流转时，用 `UPDATE ... WHERE version = ?` 确保只有最新版本能成功提交，避免“脏写”。如果更新返回 0 行，则前端提示冲突并让用户重新加载。

#### 2.3 `issue_custom_field` 表（EAV 模式）

| 字段 | 类型 | 主键/索引 | 备注 |
|------|------|-----------|------|
| `issue_id` | BIGINT UNSIGNED | PK (复合) | 对应 Issue |
| `field_id` | BIGINT UNSIGNED | PK (复合) | 自定义字段定义 |
| `value_string` | VARCHAR(1024) |  | 字符串/数字/枚举 |
| `value_number` | DOUBLE |  | 若是数值 |
| `value_date` | DATETIME |  | 若是日期 |
| `value_json` | JSON |  | 若是复杂结构 |

> **为什么采用 EAV**：自定义字段在不同项目可能不同，使用 **宽表**（每列对应一个字段）会导致表结构频繁变动。EAV 让字段元数据独立存储，查询时通过 **JOIN** 或 **子查询** 聚合。

#### 2.4 `workflow`、`workflow_state`、`workflow_transition` 表

| 表名 | 关键字段 | 说明 |
|------|----------|------|
| `workflow` | `id, name, description` | 工作流定义 |
| `workflow_state` | `id, workflow_id, name, is_initial, is_terminal` | 状态节点 |
| `workflow_transition` | `id, workflow_id, from_state_id, to_state_id, condition_json, post_action_json` | 状态流转规则，`condition_json` 可存储 JQL 条件，`post_action_json` 用来配置钩子（如发送通知） |

> **事务一致性**：状态变更时，只更新 `issue.status`，并在同一事务内写入 `audit_log`。如果工作流规则检查失败，事务回滚，确保 **“状态永远合法”**。

#### 2.5 `permission` 表（细粒度 ACL）

| 字段 | 类型 | 主键/索引 | 备注 |
|------|------|-----------|------|
| `id` | BIGINT UNSIGNED | PK | 自动递增 |
| `project_id` | BIGINT UNSIGNED | IDX (`project_id`) | 所属项目 |
| `role_id` | BIGINT UNSIGNED |  | 角色（如 Developer、Reporter） |
| `resource_type` | VARCHAR(32) |  | `project` / `board` / `issue` |
| `resource_id` | BIGINT UNSIGNED |  | 对应资源主键 |
| `action` | VARCHAR(32) |  | `read` / `edit` / `transition` / `delete` |
| `allow` | BOOLEAN |  | true = 允许, false = 拒绝 |

> **权限检查**：在 Issue Service 的每个业务入口，先 **读取用户所属角色** → **聚合对应的 Permission** → **匹配资源** → **决定是否放行**。为提升性能，可把 **角色‑权限映射** 缓存到 Redis。

#### 2.6 `audit_log` 表（审计）

| 字段 | 类型 | 主键/索引 | 备注 |
|------|------|-----------|------|
| `id` | BIGINT UNSIGNED | PK | 自动递增 |
| `issue_id` | BIGINT UNSIGNED | IDX (`issue_id`) | 关联 Issue |
| `user_id` | BIGINT UNSIGNED |  | 操作人 |
| `action` | VARCHAR(64) |  | `create`, `update`, `transition` … |
| `detail` | JSON |  | 具体变更内容（旧值/新值） |
| `created_at` | DATETIME |  | 记录时间 |

> **为什么单独建表而不是写入 Issue 表**：审计日志是 **写多读少**，且需要保留历史。单表可以 **分区**（按日期）以降低查询成本。

### 3. 分片与扩容策略

| 数据 | 分片方式 | 说明 |
|------|----------|------|
| `issue`、`project`、`workflow` | **水平分片（Hash）** 按 `project_id` | 同一项目的 Issue 均落在同一分片，便于跨表事务（使用 **分布式事务框架** 如 Seata） |
| `audit_log` | **时间分区**（月/季） | 老数据归档到冷存储（如 S3） |
| `custom_field` | 与 `issue` 同分片 | 保持 Join 本地化 |
| `search index` | Elasticsearch 自带分片 | 按 `issue_id` hash 自动路由 |
| `attachment` | 对象存储 **键名** 包含 `project_id/issue_id` 前缀 | 便于生命周期管理（如项目删除时批量清理） |

> **不进行分片的风险**：单库写入量会在 QPS 高峰时触发 **锁竞争**，导致 **响应时延 > 200 ms**，甚至出现 **死锁**。分片后每个分片的并发降低，CPU、I/O、锁竞争都能保持在安全范围。

---

## 第四步：核心 API 设计

下面以 **RESTful** 为主，配合 **WebSocket** 推送实时事件。每个 API 都标明 **请求路径、方法、主要参数、返回结构**，并说明 **安全/事务/幂等** 要点。

### 1. 通用约定

| 项目 | 说明 |
|------|------|
| **身份认证** | 使用 **JWT**（签发自 Auth Service），在 `Authorization: Bearer <token>` 里携带。 |
| **错误码** | 采用统一错误响应 `{ "code": "ERR_XXX", "message": "...", "detail": {...} }`。 |
| **分页** | `GET /issues?start=0&size=20`，默认 `size ≤ 100`，返回 `total` 与 `nextStart`。 |
| **幂等性** | 对 **写操作**（POST/PUT/DELETE）必须支持幂等，使用 **Idempotency-Key** Header。 |
| **速率限制** | `X-RateLimit-Limit/Remaining/Reset` Header，由 API Gateway 返回。 |

### 2. Issue 相关 API

| 方法 | 路径 | 说明 | 关键请求体/参数 | 返回示例 |
|------|------|------|----------------|----------|
| **POST** | `/api/v1/projects/{projectKey}/issues` | 创建 Issue（强事务） | ```json { "summary":"...", "description":"...", "type":"Bug", "priority":"High", "assigneeId":123, "customFields": { "cf_1":"value1" } }``` | `201 Created`<br>`{ "id": 987654, "issueKey":"JRA-123", "status":"Open", "createdAt":"..." }` |
| **GET** | `/api/v1/issues/{issueId}` | 查询 Issue 细节（包括自定义字段） | Path 参数 `issueId` | `{ "id":..., "summary":..., "customFields":{...}, "attachments":[...] }` |
| **PUT** | `/api/v1/issues/{issueId}` | 更新 Issue（乐观锁） | ```json { "summary":"...", "version": 3, "customFields": {...} }``` | `200 OK`<br>`{ "id":..., "version":4 }` |
| **POST** | `/api/v1/issues/{issueId}/transitions` | 状态流转（工作流校验） | ```json { "toStatus":"In Progress", "comment":"开始开发", "version":5 }``` | `200 OK`<br>`{ "status":"In Progress", "version":6 }` |
| **DELETE** | `/api/v1/issues/{issueId}` | 删除 Issue（软删 + 审计） | Path `issueId` | `204 No Content` |
| **GET** | `/api/v1/issues/search?jql=project=JRA%20AND%20status=Open` | JQL 搜索（调用 Search Service） | Query 参数 `jql`, `start`, `size` | `{ "total": 4321, "issues":[{...}] }` |

> **为什么在 `PUT`/`POST /transitions` 中加入 `version`**：防止 **“脏写冲突”**。如果两个用户几乎同时把同一 Issue 从 `Open` → `In Progress`，只有 `version` 匹配的请求会成功，另一方收到 **409 Conflict** 并可重新拉取最新数据。

### 3. 工作流相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| **GET** | `/api/v1/workflows/{workflowId}` | 获取工作流定义 |
| **POST** | `/api/v1/workflows` | 创建工作流（管理员） |
| **PUT** | `/api/v1/workflows/{workflowId}/states/{stateId}` | 更新状态属性（如名称、是否终止） |
| **POST** | `/api/v1/workflows/{workflowId}/transitions` | 添加/修改状态流转规则 |

### 4. 看板（Board）/ Sprint API

| 方法 | 路径 | 说明 |
|------|------|------|
| **GET** | `/api/v1/boards/{boardId}` | 看板元数据 |
| **GET** | `/api/v1/boards/{boardId}/issues?status=In%20Progress` | 看板上按列获取 Issue（内部使用 `status` 过滤） |
| **POST** | `/api/v1/boards/{boardId}/issues/{issueId}/move` | 将 Issue 拖拽到另一列（实质是状态流转） |
| **POST** | `/api/v1/sprints` | 创建 Sprint |
| **PUT** | `/api/v1/sprints/{sprintId}` | 更新 Sprint（开始/结束） |
| **GET** | `/api/v1/sprints/{sprintId}/burndown` | 返回燃尽图数据（聚合） |

### 5. 实时推送（WebSocket）

| 事件类型 | 说明 | 推送内容 |
|----------|------|----------|
| `issue_created` | 新 Issue 被创建 | `{ "issueId":..., "issueKey":..., "summary":... }` |
| `issue_updated` | Issue 内容或自定义字段被修改 | 同上 + `changedFields` |
| `issue_transitioned` | 状态流转 | `{ "issueId":..., "from":"Open", "to":"In Progress", "byUserId":... }` |
| `comment_added` | 新增评论 | `{ "issueId":..., "commentId":..., "authorId":..., "content":... }` |
| `attachment_added` | 附件上传完成 | `{ "issueId":..., "attachmentId":..., "url":... }` |

> **推送实现**：Notification Service 订阅 **Kafka** 中的 `issue-event` 主题，收到消息后通过 **WebSocket** 连接（或 **SSE**）推送给对应用户。**离线用户** 会收到 **邮件/Slack** 通过 **Notification Service** 的二次分发。

### 6. 权限校验示例（伪代码）

```java
// IssueService.updateIssue(...)
public Issue updateIssue(Long issueId, IssueUpdateDTO dto, User user) {
    // 1. 读取 Issue（只读）
    Issue issue = issueDao.findById(issueId);
    // 2. 权限检查（缓存+DB）
    if (!permissionService.canEditIssue(user, issue)) {
        throw new AccessDeniedException("无编辑权限");
    }
    // 3. 乐观锁检查
    int updated = issueDao.updateIfVersionMatch(issueId,
        dto.getSummary(),
        dto.getVersion());   // UPDATE ... WHERE id=? AND version=?
    if (updated == 0) {
        throw new ConflictException("版本冲突，请刷新后重试");
    }
    // 4. 记录审计日志
    auditLogService.logUpdate(user, issueId, dto);
    // 5. 发送事件（异步）
    eventProducer.publishIssueUpdated(issueId);
    // 6. 返回最新对象
    return issueDao.findById(issueId);
}
```

> **为什么要把权限、乐观锁、审计、事件发布都写在业务方法里**：保持 **业务原子性**，即使服务被水平拆分，每一次请求仍然只会产生 **一次 DB 事务**，其它异步行为（日志、通知）不影响事务提交。

---

## 第五步：详细组件设计

下面把高层图中的每个关键组件拆解，解释 **内部技术选型、交互协议、容错机制**，并给出 **关键的实现要点**。

### 1. API Gateway

- **技术选型**：Kong / NGINX + Lua 插件，或 **AWS API Gateway**（如果使用云）。
- **功能**：
  - **路由**：根据 URL 前缀转发到对应微服务（Issue、Search、Notification）。
  - **鉴权**：调用 Auth Service 验证 JWT，提取 `userId`、`roles` 放入 Header `X-User-Id`。
  - **限流**：基于 `userId` + `IP` 的 Token Bucket，实现 **每秒 100 请求** 上限。
  - **熔断**：对下游服务的错误率/延迟监控，快速返回 503。
- **监控**：统计 QPS、错误率、延迟；导出 Prometheus 指标。

> **如果不使用网关**：每个服务都要自行实现鉴权、限流、熔断，代码重复且难以统一治理。

### 2. Auth Service

- **实现**：基于 **OAuth2 Authorization Server**（Keycloak、Auth0）或自研 JWT 发放服务。
- **流程**：
  1. 前端使用 **OAuth2 Authorization Code**（配合 SSO）获取 `access_token`。
  2. `access_token` 包含 `sub`（用户ID）和 `role`（全局角色），使用 **HS256** 或 **RS256** 签名。
  3. API Gateway 通过 **公钥** 验证签名，解析出 `userId`、`tenantId`。
- **刷新 Token**：使用 **Refresh Token**，保证长会话安全。

### 3. Issue Service（核心业务）

- **部署**：容器化（Docker）+ Kubernetes Deployment，水平复制 `replicas: N`。
- **无状态化**：所有业务状态保存在 MySQL；仅在本地持有 **缓存（Redis）** 读取的权限/配置。
- **事务**：
  - **单库事务**：Issue、Audit、Permission 在同一库（或同一分片）使用 **InnoDB** 的 **ACID**。
  - **分布式事务**：若跨库（如 Issue 与 Attachment Metadata），使用 **Saga** 或 **Seata**（基于 AT 模式）。
- **幂等性**：对 **创建** 操作使用 `Idempotency-Key`，在 Redis 中保存 `key -> issueId`，重复请求直接返回已创建的 Issue。
- **异常处理**：捕获 DB 死锁/超时，返回 **503**，并在监控告警。

### 4. Search Service + Elasticsearch

- **架构**：单独的微服务，负责 **JQL 解析 → ES DSL 生成 → 查询 ES**，并返回统一的 Issue DTO。
- **实时性**：
  - **写路径**：Issue Service 在事务提交后 **发送 Kafka 事件** `issue-changed`。
  - **消费者**（Search Service）批量消费（默认 5s）并 **更新 ES 索引**（使用 **bulk API**）。
  - **延迟**：约 **5‑10 秒**（可调），满足 **最终一致** 要求。
- **索引设计**：
  - **主键**：`issue_id`（Long） + `project_key`（keyword）作为路由字段。
  - **字段**：`summary`、`description`（text + analyzer）、`status`、`assignee`、`custom_fields`（nested）。
- **分片**：根据业务规模，默认 **5 主分片 + 1 副本**，后期根据 **节点容量** 调整。
- **备份恢复**：快照（Snapshot）至对象存储，每日增量。

> **如果直接在 MySQL 上做全文搜索**：会导致 **查询性能极差**（尤其是大数据量），并且 **无法满足复杂聚合/排序**，因此必须单独使用搜索引擎。

### 5. Notification Service（WebSocket）

- **协议**：WebSocket（或 SSE 兼容），使用 **STOMP** 或自定义 JSON 消息。
- **实现**：基于 **Spring WebFlux** 或 **Node.js + socket.io**，部署在 **K8s**，支持 **水平扩容**。
- **消息分发**：
  1. Notification Service 订阅 **Kafka** `issue-event`。
  2. 收到事件后，查询 **用户-连接映射**（Redis `userId -> connectionId`）。
  3. 通过 **WebSocket** 把消息推送到对应客户端。
- **离线处理**：如果用户未在线，事件写入 **Redis Stream** 或 **邮件任务队列**，由 **Email Service** 异步发送。
- **心跳/连接管理**：每 30 秒发送 ping，超时关闭并清理映射。

### 6. Attachment 存储

- **对象存储**：Amazon S3、Alibaba OSS、MinIO（自建）。
- **文件元数据**：`attachment` 表（id, issue_id, bucket, key, size, mime, created_at）。
- **上传流程**：
  1. 前端请求 **预签名 URL**（GET `/attachments/presign?filename=...`）。
  2. 后端生成 **PUT** 预签名，返回给前端。
  3. 前端直接 PUT 到对象存储（跨区域 CDN 加速）。
  4. 成功后前端通知 Issue Service，后者写入 `attachment` 表并发布 `attachment_added` 事件。
- **安全**：对象键包含 **随机 UUID**，防止猜测；通过 **IAM policy** 限制只能在预签名时间窗口写入。

### 7. Permission Service（可选独立微服务）

- **职责**：集中管理 **角色‑权限映射**、**项目‑用户关联**，提供 **REST** 接口 `GET /permissions/effective?userId=&resource=issue&resourceId=`。
- **缓存**：把 **用户的有效权限** 缓存到 **Redis**，TTL 5 分钟；权限变更时主动 **Cache Invalidate**。
- **细粒度**：在 **Issue Service** 中调用 `permissionService.check(user, action, issue)`，返回布尔。

### 8. Audit Log Service

- **写入**：业务服务通过 **Kafka** `audit-log` 主题发送审计事件，Log Service 异步写入 **ClickHouse**（高压缩、快速查询）或 **MySQL 分区表**。
- **查询**：提供 API `/audit?issueId=&userId=&action=`，支持分页、时间范围过滤。
- **合规**：保留 **7 年**（冷热分层存储），可通过 **归档任务** 将旧分区移动到对象存储。

### 9. 监控、日志、报警

| 维度 | 工具 |
|------|------|
| **指标** | Prometheus 抓取微服务 `/metrics`（CPU、GC、QPS、延迟） |
| **日志** | EFK（Elasticsearch + Fluentd + Kibana）或 Loki + Grafana |
| **分布式追踪** | OpenTelemetry + Jaeger |
| **告警** | Alertmanager → Slack / Email |
| **容量规划** | Grafana 仪表盘监控磁盘、对象存储使用率、Kafka lag |

> **不做监控的风险**：在流量突增或节点故障时无法快速定位根因，导致 SLA 违约。

---

## 第六步：扩展性与高可用设计

### 1. 水平扩容路径

| 业务热点 | 扩容方式 | 何时触发 |
|----------|----------|----------|
| API 请求 | 增加 **Gateway + Service 实例**（K8s HPA） | CPU/内存 ≥ 70% 或 QPS > 80% 目标 |
| Issue DB 写入 | **分库分表**（按 `project_id` hash）或 **MySQL Cluster**（TiDB） | 单库 TPS 持续 > 2k 写/秒 |
| Search 查询 | **Elasticsearch 扩容**（添加节点） | 查询 latency > 150 ms 或 CPU ≥ 80% |
| 实时推送 | **Notification Service** 多副本 + **Kafka 分区** 增加 | 并发 WebSocket 连接数 > 10k |
| 附件存储 | **对象存储** 自动扩容，使用 **多 AZ** 桶 | 存储容量接近 80% 上限 |
| 审计日志 | **ClickHouse** 分区扩容 + 冷数据归档 | 写入速率 > 5k 行/秒 |

> **为什么要先关注这些热点**：系统的 **瓶颈往往在写入 DB、搜索、实时推送**，而非前端渲染。先把这些关键路径做到弹性伸缩，整体可用性自然提升。

### 2. 多可用区（AZ）容灾

- **跨 AZ 部署**：每个微服务在 **至少 3 个 AZ** 里运行，使用 **负载均衡器**（L7）做跨 AZ 调度。
- **数据库**：MySQL 主从采用 **半同步复制**（Primary 在 AZ1，两个 Sync Replica 分别在 AZ2、AZ3）。故障时 **自动故障转移**（使用 Orchestrator / MHA）。
- **Kafka**：使用 **跨 AZ Replication**（复制因子 3），每个分区有 leader 在不同 AZ，保证写可用性。
- **Elasticsearch**：每个分片有 **primary + 2 replicas**，分布在不同 AZ。
- **对象存储**：使用 **多 AZ Bucket**（自动同步），即使某个 AZ 故障也能读取。

> **不做跨 AZ**：单点故障导致整个服务不可用，无法满足 **99.95%** 的可用性目标。

### 3. 数据一致性策略

| 场景 | 一致性要求 | 实现方式 |
|------|------------|----------|
| Issue 状态流转、权限变更 | **强一致**（必须立即对后续请求可见） | **单库事务**（MySQL） + 乐观锁 |
| 搜索索引更新、统计报表 | **最终一致**（几秒延迟可接受） | **Kafka → Search Service → Elasticsearch**（异步） |
| 附件上传 | **强一致**（文件必须成功存储后才返回） | **预签名 + S3 直接写**，成功后回调 DB |
| 审计日志 | **强一致**（业务必须记录） | **写入同事务** 或 **事务后立即发布 Kafka**（确保不丢失） |

> **如果所有数据都走强一致**：会导致 **写入延迟高**，影响 QPS，且跨地域同步成本大。合理划分强/最终一致可以兼顾性能和正确性。

### 4. 灾难恢复（DR）演练

1. **备份**：MySQL 每日全备+增量 binlog；Elasticsearch 每日 Snapshot；对象存储本身多副本。
2. **故障切换**：使用 **自动化脚本**（Terraform + Ansible）在另一 region 拉起 **只读副本**，切换 DNS。
3. **演练频率**：每季度一次完整 DR 演练，验证 RTO ≤ 30 min，RPO ≤ 5 min。

### 5. 性能调优要点

| 维度 | 调优手段 |
|------|----------|
| DB 读 | **读写分离**：Primary + 多个 Read Replica；热点 Issue 使用 **Redis Cache**（`issue:{id}`） |
| DB 写 | **批量写**：批量插入附件元数据；使用 **prepared statement**；**连接池**（HikariCP）|
| 查询 | **索引**：对 `project_id、status、assignee_user_id` 建二级索引；避免 `SELECT *` |
| 搜索 | **刷新间隔**：Elasticsearch `refresh_interval` 设置为 `5s`；使用 **doc values** 优化聚合 |
| 网络 | **gRPC**（内部微服务间）比 HTTP 更低延迟；开启 **TLS 会话复用** |
| GC | 对 Java 微服务使用 **ZGC** 或 **G1**，调大堆内存避免频繁 Full GC |

---

## 第七步：常见面试追问与回答

### Q1. 在高并发状态流转时，如何保证同一个 Issue 不会出现冲突的状态更新？

**回答要点**：

1. **乐观锁（Version）**  
   - 每条 Issue 记录带 `version` 字段。更新时 `UPDATE issue SET status=?, version=version+1 WHERE id=? AND version=?`。如果返回受影响行数为 0，说明已经被其他请求更新，返回 `409 Conflict`，前端需要重新拉取最新状态并重试。  
2. **业务层幂等键**（可选）  
   - 对外提供 `Idempotency-Key`，在 Redis 中记录 `key -> last_successful_version`，防止同一次业务被重复提交导致多次状态变更。  
3. **事务**  
   - 状态变更、审计日志写入、权限检查全部放在同一个 **MySQL 事务** 中，确保原子性。  
4. **分布式锁**（极端情况）  
   - 若业务要求强排他（如同一时间只能有一个人编辑同一 Issue），可使用 **Redis RedLock** 或 **Zookeeper** 锁，锁定 `issue:{id}`，业务完成后立即释放。  
5. **事件溯源**（进阶）  
   - 所有状态变更写入 **Kafka** 作为事件流，消费端可做 **幂等消费**（使用 `eventId` 去重），即使出现重复消费，也不会导致状态二次变更。

> **如果只用数据库唯一约束**（如 `status` 唯一），会导致业务逻辑受限，且无法捕获并发冲突的业务细节。乐观锁是最常用且代价最低的方案。

---

### Q2. 使用 Elasticsearch 实现搜索时，如何处理实时性与一致性之间的权衡？

**回答要点**：

| 维度 | 需求 | 方案 |
|------|------|------|
| **实时性** | 用户编辑后希望几秒内搜索到新内容 | - **Kafka → Search Service** 使用 **微批（5 s）** 方式 `bulk` 写入 ES，延迟可调。<br>- 对于极端实时需求（如立即展示新 Issue），可以 **写入 MySQL 后直接返回**，并在前端**短暂缓存**（5 s）结果。 |
| **一致性** | 搜索结果不应出现“幻读”或“脏数据” | - **最终一致**：搜索结果可以稍微滞后，业务容忍 5‑10 s 延迟。<br>- 对关键业务（如权限过滤），在查询 ES 前先 **在业务层进行 ACL 检查**，确保即使索引滞后也不泄露数据。 |
| **数据同步** | 保证 DB ↔ ES 双向一致 | - **单向同步**：只从 MySQL → ES，所有写操作只能走 DB。<br>- **幂等消费**：Kafka 消费时使用 `issueId` 作为唯一键，使用 `update` + `doc_as_upsert:true`，保证重复消费不产生副本。 |
| **故障恢复** | ES 节点宕机不影响主业务 | - **写路径不依赖 ES**：写完 DB 并成功返回后，即使 ES 暂时不可用也不影响业务。<br>- 监控 **Kafka lag**，若出现积压，自动扩容 ES 或启用 **备份搜索服务**（如 OpenSearch）进行降级。 |

> **不做异步同步**：同步写入 ES 会让事务变慢，导致 QPS 达不到目标，而且跨服务事务的实现非常复杂。采用 **Kafka + 最终一致** 能在保证业务响应速度的同时，提供可观测的同步延迟。

---

### Q3. 当用户量从 30 万增长到 300 万时，哪些模块最先需要水平扩容？如何做到无缝迁移？

**回答要点**：

1. **最先扩容的模块**  
   - **API Gateway & Load Balancer**：处理入口流量直接随 QPS 成长。  
   - **Issue Service**：写入量（Issue 创建、状态流转）会线性增长，需 **增加实例** 并 **扩容 MySQL**（分库或使用分布式 SQL 如 TiDB）。  
   - **Search Service & Elasticsearch**：查询量激增，需要 **增加 ES 节点**，并可能 **提升分片数**。  
   - **Notification Service**：实时推送的 WebSocket 连接数会随活跃用户数呈指数增长，需要 **横向扩容** 并 **使用分区的 Kafka** 进行消费负载均衡。  

2. **无缝迁移方案**  
   - **蓝绿部署**：在新集群上部署新版服务，先把 **10%** 流量切到新集群做灰度，监控指标后逐步提升至 100%。  
   - **数据库分库分表**：使用 **一致性哈希** 按 `project_id` 将 Issue 数据划分到多个 MySQL 实例。迁移时可以 **双写**（写入旧库 + 新库），逐步将旧库的读请求切换到新库，最后停掉旧库。  
   - **Elasticsearch Reindex**：创建新索引（更高的分片数），使用 **Reindex API** 将旧索引数据搬迁，期间保持原索引对外服务，迁移完成后切换 alias。  
   - **Kafka 分区扩容**：先在新 topic 上创建更多分区，使用 **MirrorMaker** 将旧 topic 数据复制过去，切换消费者组。  
   - **监控与回滚**：每一步都要配合 **Prometheus + Alertmanager**，若出现异常立即回滚至旧集群。  

> **如果直接一次性扩容**（比如一次性把 MySQL 换成更大实例），会导致 **大幅停机**，业务不可用，违背 **99.95%** 的 SLA。渐进式、双写、灰度是业界成熟的做法。

---

### Q4. 怎样实现细粒度的权限控制而不把所有权限查询都打到数据库？

**回答要点**：

1. **角色‑权限矩阵**  
   - 在 `role_permission` 表中预先把 **每个角色对应的 Action‑Resource** 列表写好（一次性加载）。  
2. **缓存**  
   - 把 **用户的有效角色列表**（`userId -> [roleId]`）和 **角色的权限集合**（`roleId -> Set<Permission>`）缓存到 **Redis**，TTL 5 min。  
3. **权限校验流程**（伪代码）  

```java
boolean can(User user, Action act, Resource res) {
    Set<Permission> perms = redisCache.getPermissions(user.id);
    if (perms == null) {
        perms = permissionDao.loadEffectivePermissions(user.id);
        redisCache.setPermissions(user.id, perms);
    }
    return perms.contains(new Permission(act, res.type, res.id));
}
```

4. **细粒度**：Permission 对象中可以携带 **资源 ID**（如具体 Issue ID），在缓存中用 **Bloom Filter** 或 **Trie** 结构快速判断是否拥有该 ID。  
5. **动态刷新**：当管理员修改权限时，直接 **发布 Redis Pub/Sub** 消息，让所有服务 **失效对应用户缓存**。  

> **不使用缓存**：每次业务请求都要 **JOIN 多张表**（user‑role、role‑permission、project‑user），在高并发下会导致 **SQL 复杂度 O(N)**，响应时间超标。缓存能把 **读路径** 从 **毫秒级 DB** 降到 **微秒级 Redis**。

---

### Q5. 如何保证系统在单个可用区故障时仍然可以正常提供服务？

**回答要点**：

- **跨 AZ 部署**：所有微服务（API Gateway、Issue Service、Search Service、Notification Service）在 **至少 3 个 AZ** 部署，使用 **云负载均衡（L7）** 将流量分发到健康的 AZ。  
- **数据库**：MySQL **主‑同步副本** 分布在不同 AZ，使用 **半同步** 保证写入成功后有至少一个副本确认。故障时 **自动提升** 最近的同步副本为新主。  
- **Kafka**：复制因子 3，分区的 Leader 分布在不同 AZ，确保即使一个 AZ 挂掉仍有 **ISR**（In‑Sync Replicas）继续提供服务。  
- **Elasticsearch**：每个分片拥有 **primary + 2 replicas**，跨 AZ 分布，查询时自动路由到可用副本。  
- **对象存储**：使用 **多 AZ Bucket**，读取自动路由到最近的副本。  
- **健康检查 & 自动故障转移**：K8s 的 **PodDisruptionBudget**、**Service** 的 **readiness/liveness** 探针确保不健康实例被剔除。  

> **不做跨 AZ**：一个 AZ 故障会导致全部实例不可达，业务瞬间不可用，违背 **99.95%** 的可用性要求。

---

## 心得与反思

### 1. 本题最难的 1‑2 个设计决策及思考过程

| 决策 | 为什么难 | 思考路径 |
|------|----------|----------|
| **强一致 vs 最终一致的边界划分** | 需要在 **业务正确性** 与 **系统性能** 之间找到平衡点。错误的划分会导致 **数据不一致**（安全风险）或 **写入延迟过高**（影响 QPS）。 | 1) 列出所有业务操作。<br>2) 标记哪些对业务结果**必须立即可见**（如状态流转、权限变更）。<br>3) 其余（搜索、统计）可接受几秒延迟。<br>4) 采用 **单库事务** 处理强一致路径，**Kafka+ES** 处理最终一致路径。 |
| **细粒度权限的缓存实现** | 权限检查是每一次业务请求的必经步骤，若每次都查询 DB 会成为**性能瓶颈**。但缓存失效或不一致会产生 **安全漏洞**。 | 1) 先把权限模型抽象为 **角色‑资源‑动作**。<br>2) 评估缓存粒度（用户‑角色‑权限集合）。<br>3) 设计 **TTL + Pub/Sub 刷新** 机制，确保变更即时生效。<br>4) 加入 **幂等校验** 防止缓存穿透。 |

### 2. 新手最容易犯的错误（至少 2 条）

| 错误 | 影响 | 正确做法 |
|------|------|----------|
| **把所有业务写都直接落到 Elasticsearch**（把搜索当成主库） | 写入延迟大、事务不可靠、搜索结果不一致，难以实现 ACID。 | 使用 **关系型 DB** 处理事务，ES 只作 **异步索引**。 |
| **在权限校验时直接查询多表 JOIN**，而不做任何缓存 | 在 QPS 高峰时 DB 连接耗尽、查询慢，导致整体响应超时。 | 把 **角色‑权限映射** 与 **用户‑角色** 缓存到 **Redis**，并在变更时主动失效。 |
| **把所有微服务都部署在同一个可用区** | 单 AZ 故障导致整套系统不可用，违背高可用目标。 | 跨 AZ 多实例部署，使用负载均衡和数据复制。 |
| **忽视幂等性，直接把请求写入 DB** | 重复请求会产生脏数据（如重复创建 Issue）。 | 为 **POST**/PUT 操作加入 **Idempotency-Key**，或使用 **乐观锁**。 |

### 3. 学习建议和可延伸的方向

1. **系统设计基本功**  
   - 熟悉 **CAP 定理、BASE、ACID**，理解它们在实际业务中的取舍。  
   - 多练习 **需求拆解 → 数据模型 → 接口设计 → 架构选型** 的闭环。  

2. **深入了解关键组件**  
   - **MySQL / TiDB**：事务实现、分片、复制、读写分离。  
   - **Kafka**：消息语义（at‑least‑once、exactly‑once）、分区策略、消费者组。  
   - **Elasticsearch**：倒排索引原理、分片/副本、刷新策略。  
   - **Redis**：缓存失效、分布式锁、Pub/Sub。  

3. **实践项目**  
   - 用 **Docker‑Compose** 搭建一个简化版的 Jira（Issue Service + MySQL + ES + Kafka），实现 Issue CRUD、搜索、WebSocket 推送。  
   - 通过 **K6 / Locust** 进行压测，观察 QPS、延迟，调优索引、连接池、缓存。  

4. **关注可观测性**  
   - 学习 **OpenTelemetry**，把链路追踪、指标、日志统一上报。  
   - 了解 **SLO / SLA** 的定义与监控报警的实现。  

5. **面试技巧**  
   - **先说思路**：先给出系统全局图，再逐层细化。  
   - **量化回答**：每提一个设计点，都尽量给出 **容量/性能估算**（如每秒写 5k 条到 ES）。  
   - **主动补充**：在回答完问题后，主动说明 **备份、灾备、运维**，显示你对完整系统有全局视角。  

---

**祝你在面试中能够条理清晰、从需求到实现一步步展开，展示出对系统全局把控和细节实现的能力！** 🎉
