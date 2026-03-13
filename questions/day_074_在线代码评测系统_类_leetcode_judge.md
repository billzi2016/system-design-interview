# 第 74 天：设计 在线代码评测系统（类 LeetCode Judge）

> 生成日期：2026-03-13

---

# 在线代码评测系统（类 LeetCode Judge）系统设计面试题

## 1. 题目背景
在线代码评测系统是一套面向海量用户的编程练习平台，用户可以提交源码，系统在隔离的执行环境中编译、运行并对比输出，以判断答案是否正确。该平台常用于算法练习、面试准备以及编程比赛。

## 2. 面试场景设定
> **面试官**：  
> “我们想打造一套类似 LeetCode 的在线代码评测系统，请你从零开始设计整个后端架构。包括从用户提交代码到返回评测结果的完整流程，并考虑高并发、可靠性以及成本等因素。先从整体思路说起，然后我们会逐步深入细节。”

## 3. 功能性需求
| 编号 | 需求描述 |
|------|----------|
| **F1** | **用户提交代码**：支持多语言（如 C++, Java, Python, Go），提交代码、题目 ID、输入/输出文件或自定义测试用例。 |
| **F2** | **代码编译与执行**：在安全、资源受限的沙箱环境中完成编译、运行，捕获标准输出、错误信息、运行时异常、超时等。 |
| **F3** | **评测结果对比**：将用户程序输出与题目官方答案进行对比，支持严格匹配、近似匹配（浮点误差容忍、排序忽略）以及自定义评测器。 |
| **F4** | **结果返回与展示**：实时返回评测状态（排队、编译中、运行中、完成），最终返回通过/失败、错误类型、执行时间、内存峰值等。 |
| **F5** | **题目与用例管理**：后台提供题目 CRUD 接口，包含描述、样例、隐藏测试用例、评测器代码等。 |
| **F6** | **统计与排行榜**：记录用户提交历史、通过率、最快解答时间等，支持按题目/用户维度的排行榜查询。 |

## 4. 非功能性需求（带具体估算）

| 编号 | 指标 | 目标值 | 说明 |
|------|------|--------|------|
| **N1** | **日活跃用户（DAU）** | 200,000 人 | 包含学生、职场人士、竞赛选手等。 |
| **N2** | **提交 QPS（Peak）** | 5,000 QPS | 高峰时段（如周末、比赛期间）峰值。 |
| **N3** | **评测延迟** | ≤ 3 秒（95% 请求） | 包括排队、编译、运行、对比全过程。 |
| **N4** | **系统可用性** | 99.9%（月均） | 包括评测服务、存储、API 网关等。 |
| **N5** | **存储容量** | 30 TB | 代码提交、题目描述、测试用例、评测日志等累计 3 个月的存储需求。 |
| **N6** | **资源隔离安全** | 每个沙箱 CPU ≤ 2 核、内存 ≤ 2 GB、执行时限 ≤ 5 秒 | 防止恶意代码影响其他任务或底层系统。 |

> **备注**：以上数值为 **估算**，面试中可根据候选人的假设进行微调。

## 5. 系统边界
### ✅ 本题范围（需要设计）
- **核心评测流程**：提交 → 排队 → 沙箱编译运行 → 结果对比 → 返回。
- **沙箱实现**：容器化（Docker/Kata）或轻量级 VM，资源配额、网络隔离、文件系统只读。
- **调度与弹性伸缩**：任务调度器、负载均衡、自动扩容/缩容策略。
- **持久化**：代码、题目、测试用例、评测日志的存储方案（对象存储 + 数据库）。
- **监控告警**：延迟、错误率、资源使用的实时监控。

### ❌ 不考虑的范围（可在面试中说明不必细化）
- **前端 UI/交互细节**（页面布局、编辑器实现）。
- **代码编辑器的语法高亮、智能提示**。
- **全文搜索、标签系统、社区讨论区**。
- **用户身份验证的细粒度（OAuth、单点登录）**（只需要“用户已登录”假设）。
- **跨语言评测器的实现细节**（只需说明可插拔机制）。

## 6. 提示与追问
1. **调度策略**  
   - “如果提交量突发到 10 倍，如何保证评测延迟仍在 3 秒以内？请说明调度器的设计和伸缩机制。”  

2. **安全隔离**  
   - “用户可能提交恶意代码（如 fork 炸弹、网络攻击），你会采用哪些技术手段在沙箱层面防御？”  

3. **评测结果一致性**  
   - “同一道题在不同语言的实现可能有细微差别（如浮点误差），请设计一种评测对比框架，能够统一处理严格匹配与宽松匹配的需求。”  

--- 

**请根据上述需求，完成系统的整体架构设计，包括但不限于：**  
- 高层组件划分与交互流程图  
- 数据模型（核心表/对象）  
- 关键技术选型与理由（如容器/VM、消息队列、缓存）  
- 伸缩与容错方案  
- 监控、日志、告警的实现要点  

祝你设计顺利！

---

# 题解

# 在线代码评测系统（类 LeetCode Judge）系统设计完整解答  

> **写给对象**：刚入行的后端小伙伴，假设你从未做过系统设计。本答案会把每一步 **“为什么这么做”** 说清楚，先搭最小可用系统（MVP），再逐层演进到生产级的高可用分布式架构。  

> **阅读建议**：先通读一遍了解全局，再回到每个章节细细体会。遇到不懂的技术点（比如 **Kata Containers**、**CQRS**），可以先在网上搜关键词，等把整体思路抓住后再去深入。

---

## ## 解题思路总览  

1. **从业务出发**：先把「用户提交代码 → 评测结果」的完整业务流拆成**原子步骤**（接收、持久化、排队、调度、沙箱执行、比对、返回）。  
2. **估算规模**：用需求里给的 DAU、QPS、延迟等指标，算出**并发度、存储容量、资源需求**。  
3. **MVP（最小可用系统）**：只用几块核心组件（API Gateway、提交服务、调度队列、执行节点、持久化）快速跑通。  
4. **逐步扩展**：在 MVP 基础上加入**负载均衡、弹性伸缩、缓存、监控、容错**，形成完整的高可用架构。  
5. **技术选型解释**：每个关键点（容器/VM、消息队列、数据库、缓存）都给出**优缺点**和**为什么最终选它**。  
6. **细化实现**：从 **数据模型**、**API**、**组件内部流程**、**安全隔离**、**对比框架** 逐一展开。  
7. **面试追问**：准备好调度、弹性、隔离、对比一致性等常见提问的答案。  

> **核心思路**：**先把系统做到能跑通**（正确性），再**让它跑得快、跑得稳、跑得安全**（性能 + 可用性 + 安全）。

---

## ## 第一步：理解需求与规模估算  

| 需求 | 关键点 | 需要实现的功能 |
|------|--------|----------------|
| **F1** | 多语言提交、题目 ID、测试用例 | 接收 JSON/Multipart 请求，保存源码、语言、题目、用例 |
| **F2** | 沙箱编译/运行，捕获日志、超时 | 资源受限的容器/VM，返回 stdout、stderr、exitCode |
| **F3** | 多种对比方式（严格、近似、定制） | 可插拔评测器（Python/JS 脚本） |
| **F4** | 实时状态、最终结果 | WebSocket/轮询 + 结果持久化 |
| **F5** | 题目 CRUD、隐藏测试用例 | 后台管理 API |
| **F6** | 统计、排行榜 | 按用户/题目聚合计数、Top‑K 查询 |

### 1️⃣ 非功能需求关键数值  

| 编号 | 指标 | 目标值 | 业务含义 |
|------|------|--------|----------|
| **N1** | DAU | 200 k | 同时在线用户 ≈ 5 % → 10 k 同时活跃 |
| **N2** | 峰值提交 QPS | 5 k | 高峰期 5 000 次提交/秒 |
| **N3** | 95% 延迟 ≤ 3 s | 包括排队、编译、运行、比对 | 体验要求 |
| **N4** | 可用性 99.9% | 月均故障 ≤ 43 min | 必须做到自动容错 |
| **N5** | 存储 30 TB (3 个月) | 代码、题目、日志、快照 | 需要冷热分层 |
| **N6** | 沙箱配额 CPU≤2、MEM≤2 GB、时限≤5 s | 防止恶意资源占用 | 资源隔离安全 |

### 2️⃣ 估算关键资源  

1. **并发执行数**  
   - 每次评测最长 5 s，若要保持 5 k QPS，理论上需要 `5k * 5s = 25k` 并发**执行槽**。  
   - 为保证 95% 延迟 ≤ 3 s，实际并发需求约 `5k * 3s = 15k`。  
   - 每台机器（假设 32 核、64 GB）可跑 **8‑10** 个沙箱（每个 ≤2 CPU、2 GB），所以 **≈ 1 600–2 000 台**（仅作上限估算，实际会通过弹性伸缩和峰谷分离降低成本）。

2. **存储**  
   - 代码提交（平均 30 KB）× 5 k QPS × 3600 s × 24 h × 30 d ≈ **12 TB**。  
   - 题目、用例、日志等约 5 TB，预留 13 TB 为冗余（对象存储 + 多 AZ 复制）。

3. **网络**  
   - 单次提交约 100 KB（代码+元数据），5 k QPS → 0.5 GB/s 入站。  
   - 评测结果（JSON）约 2 KB，出站约 0.01 GB/s，压力主要在 **入站** 与 **调度系统**。

> **如果不做这些估算**，在面试时很容易被面试官问“系统能否支撑峰值？”而答不上来。先把数字写出来，后面再根据实际选型进行“容量预留”。

---

## ## 第二步：高层架构设计  

下面给出 **从 0 到 1** 的演进路线图，先是 MVP，后是完整 HA（高可用）架构。

### 2.1 MVP（最小可用系统）  

```mermaid
graph LR
    A[API Gateway] --> B[Submit Service]
    B --> C[Message Queue (Kafka/Rabbit)]
    C --> D[Worker (Sandbox Runner)]
    D --> E[Result Store (PostgreSQL)]
    E --> F[Result Service]
    F --> G[Client (Web/CLI)]
```

- **API Gateway**：统一入口，做鉴权、限流、流量监控。  
- **Submit Service**：接收提交，落库（提交表），把任务写入队列。  
- **Message Queue**：解耦高并发写入与执行，提供 **至少一次** 投递保证。  
- **Worker (Sandbox Runner)**：拉任务、启动沙箱、编译/运行、比对、写结果。  
- **Result Store**：关系型库存放提交记录、评测状态、最终结果。  
- **Result Service**：提供查询接口，轮询或 WebSocket 推送。  

> **为什么先这样**  
> - 只用 **单实例** 的 API、Worker、DB，就能验证业务流程是否正确。  
> - 通过 **队列** 把高峰的写入和执行解耦，最小化系统耦合度。  

### 2.2 完整 HA 架构（满足 N2‑N4）  

```mermaid
graph TB
    subgraph Internet
        U[用户] -->|HTTPS| GW[API Gateway + CDN]
    end

    subgraph Edge
        GW --> LB1[Load Balancer (L7)]
        LB1 -->|HTTP| AS[Auth Service]
        AS -->|JWT| LB2[LB (RoundRobin)]
    end

    subgraph Backend
        LB2 -->|REST| SVC[Submit Service] 
        LB2 -->|REST| PROB[Problem Service] 
        LB2 -->|REST| STAT[Statistics Service]

        SVC -->|写入| DB_SUB[PostgreSQL (sharding)]
        SVC -->|写入| OBJ[Object Store (S3)]

        SVC -->|Publish| MQ[Kafka Topic: submissions]
        PROB -->|Read/Write| DB_PROB[PostgreSQL]

        subgraph WorkersPool
            W1[Worker]:::worker
            W2[Worker]:::worker
            W3[Worker]:::worker
        end
        MQ -->|Consume| W1
        MQ -->|Consume| W2
        MQ -->|Consume| W3

        W1 -->|Exec| SANDBOX[Container / Kata VM]
        W2 -->|Exec| SANDBOX
        W3 -->|Exec| SANDBOX

        SANDBOX -->|Result| DB_RES[PostgreSQL (partitioned)]
        SANDBOX -->|Log| OBJ_LOG[Object Store (logs)]

        STAT -->|Read| DB_RES
        STAT -->|Read| DB_SUB
    end

    subgraph Monitoring
        MON[Prometheus] -->|Scrape| SVC
        MON -->|Scrape| WorkersPool
        MON -->|Alert| ALERTMANAGER
        LOG[ELK] -->|Collect| OBJ_LOG
    end

    classDef worker fill:#E3F2FD,stroke:#1976D2;
```

#### 关键组件解释  

| 组件 | 作用 | 关键技术选型 | 选型理由 |
|------|------|--------------|----------|
| **API Gateway + CDN** | 统一入口、TLS、限流、全局缓存（题目描述） | **Kong / AWS API GW** | 插件生态丰富，天然支持跨区域部署 |
| **Load Balancer (L7)** | HTTP/HTTPS 负载均衡，做会话保持（WebSocket） | **NGINX + Consul** 或云 ALB | 支持 7 层路由，可对不同业务流做独立权重 |
| **Auth Service** | 简单 JWT 鉴权、限流 | **Spring Boot / Go‑chi** | 轻量、易水平扩展 |
| **Submit / Problem / Statistics Service** | 微服务拆分，业务职责单一 | **Spring Boot / Go / Node**（任选） | 与语言无关，后续可以按流量独立扩容 |
| **PostgreSQL** (主库) | 事务性强、关系查询（提交、结果、统计） | **分区+读写分离** | 支持复杂查询、聚合，易做水平分片 |
| **Object Store** | 代码、测试用例、日志的二进制对象 | **S3 / MinIO** | 大文件存储成本低，天生高可用 |
| **Kafka** | 高吞吐、持久化的消息队列 | **Kafka** | 通过分区实现水平扩展，提供 **Exactly‑Once**（开启事务） |
| **Worker** | 拉任务、调度沙箱、写结果 | **Go**（高并发）+ **gRPC** 通信 | 低延迟、易与容器/VM API 对接 |
| **Sandbox** | 代码编译运行的隔离环境 | **Docker + cgroup + seccomp** 或 **Kata Containers** | Docker 易用、Kata 更强隔离（轻量 VM） |
| **Prometheus + Alertmanager** | 时序监控、告警 | **Prometheus** | 拉取模型适合容器化部署 |
| **ELK (Elasticsearch‑Logstash‑Kibana)** | 日志集中、搜索、可视化 | **ELK** | 便于故障排查、审计 |

> **不使用这些组件的后果**  
> - 直接在 API 进程里执行评测会导致 **阻塞**、**资源泄露**、**安全风险**。  
> - 只用单实例 DB 会在 5 k QPS 下出现 **写入瓶颈**，并且 **单点故障** 难以容忍。  
> - 没有监控系统，**延迟、错误率** 只能靠人工观察，难以满足 99.9% 可用性。

---

## ## 第三步：数据库设计  

### 3.1 主要业务实体  

| 表名 | 说明 | 关键字段 | 备注 |
|------|------|----------|------|
| **users** | 用户信息（登录后已有） | id (PK), username, email, created_at | 只做关联，不存密码 |
| **problems** | 题目元数据 | id (PK), title, description, difficulty, created_at, updated_at | 题目描述、示例等存对象存储，字段里存 URL |
| **test_cases** | 每道题的公开/隐藏用例 | id (PK), problem_id (FK), input_path, output_path, is_hidden, time_limit, memory_limit | input/output 为对象存储路径 |
| **submissions** | 用户一次提交记录 | id (PK), user_id, problem_id, language, code_path, status, created_at, updated_at | status: QUEUED/COMPILING/RUNNING/FINISHED/ERROR |
| **submission_results** | 评测结果（可拆分为多行） | id (PK), submission_id (FK), test_case_id (FK), verdict (AC/WA/TLE/MLE/RE), exec_time_ms, memory_kb, stdout_path, stderr_path | 细粒度对比结果 |
| **statistics** | 统计聚合（可用物化视图） | problem_id (PK), total_submissions, accepted_submissions, fastest_time_ms, last_updated | 用于排行榜 |
| **judge_logs** | 沙箱执行日志（大对象） | id (PK), submission_id (FK), log_path, created_at | 存对象存储路径 |

### 3.2 分区 & 索引策略  

- **submissions** 按 `created_at` **时间分区**（每日或每小时），方便归档和清理。  
- **submission_results** 按 `submission_id` 分区，查询单次提交时只扫描少量分区。  
- **主键** 为 **UUID**（或 ULID）确保全局唯一且有时间序列性。  
- **索引**：  
  - `submissions(status)` → 快速拉取待评测任务。  
  - `submission_results(verdict)` → 统计通过率。  
  - `statistics(problem_id)` → 排行榜查询。  

### 3.3 读写分离 & 缓存  

- **读库**：采用 PostgreSQL **Streaming Replication**，多副本提供查询服务（题目、排行榜）。  
- **写库**：主库负责事务写入（提交、结果），确保 **强一致**。  
- **缓存层**：  
  - **Redis** 用作 **热点题目描述、排行榜**（Sorted Set）以及 **验证码/限流**。  
  - **Cache‑Aside** 模式：查询不到时回源 DB，写完后主动 **del**/**set**。  

> **为什么需要读写分离**：在高并发的查询（排行榜、题目列表）场景下，单库会成为瓶颈；复制可以横向扩展读取能力，且对业务一致性影响不大（因为排行榜可以接受几秒的延迟）。

---

## ## 第四步：核心 API 设计  

以下 API 均采用 **RESTful + JSON**，必要时使用 **gRPC**（Worker 与 Sandbox 通信）或 **WebSocket**（实时状态推送）。

### 4.1 提交代码  

```http
POST /api/v1/submissions
Content-Type: multipart/form-data
Authorization: Bearer <jwt>

---boundary
Content-Disposition: form-data; name="code"; filename="solution.py"
Content-Type: text/x-python

print("Hello")
---boundary
Content-Disposition: form-data; name="language"
Content-Type: text/plain

python3
---boundary
Content-Disposition: form-data; name="problem_id"
Content-Type: text/plain

12345
---boundary
Content-Disposition: form-data; name="custom_input"
Content-Type: text/plain

1 2 3
---boundary--
```

**响应**  

```json
{
  "submission_id": "c3b1f9a0-5d4e-11ee-b5c5-0242ac120002",
  "status": "QUEUED",
  "estimated_wait_seconds": 2
}
```

> **实现要点**  
> - **鉴权**：解析 JWT，获取 `user_id`。  
> - **限流**：同用户 1 秒最多 2 次提交（Redis 计数器）。  
> - **持久化**：代码文件写入对象存储，路径存入 `submissions.code_path`。  
> - **写入 DB**：`status = QUEUED`，`created_at = now()`。  
> - **写入 Kafka**：topic `submissions`，payload 包含 `submission_id`、`language`、`code_path`、`problem_id`、`custom_input`。

### 4.2 查询提交状态  

```http
GET /api/v1/submissions/{submission_id}
Authorization: Bearer <jwt>
Accept: application/json
```

**响应**（状态轮询）  

```json
{
  "submission_id": "...",
  "status": "RUNNING",
  "progress": "COMPILING",   // optional
  "created_at": "...",
  "updated_at": "...",
  "result": null
}
```

- 当 `status = FINISHED` 时，`result` 字段返回 **评测概要**（通过率、耗时、错误类型等）。

### 4.3 实时推送（可选）  

```http
GET /ws/v1/submissions/{submission_id}
Sec-WebSocket-Protocol: jwt
```

- Server 通过 **WebSocket** 发送 `status` 变更事件，前端展示即时进度。

### 4.4 题目管理（后台）  

```http
POST /admin/api/v1/problems
{
  "title": "Two Sum",
  "description_url": "s3://leet/problems/12345/desc.md",
  "difficulty": "Easy",
  "test_cases": [
    {"input_url":"s3://leet/.../in1.txt","output_url":"s3://leet/.../out1.txt","is_hidden":false},
    ...
  ]
}
```

- **RBAC**：仅管理员可访问 `/admin/**`。  
- **事务**：题目、测试用例一次性写入 DB 与对象存储。

### 4.5 排行榜查询  

```http
GET /api/v1/rankings?type=problem&problem_id=12345&limit=10
```

**响应**  

```json
{
  "problem_id": "12345",
  "rankings": [
    {"rank":1,"user_id":"u123","username":"alice","time_ms": 12},
    {"rank":2,"user_id":"u456","username":"bob","time_ms": 15}
  ]
}
```

- 实现：Redis Sorted Set (`ZADD problem:12345:user_id score=time_ms`) + 定期同步至 DB。

---

## ## 第五步：详细组件设计  

### 5.1 API Gateway & 认证  

- **技术**：Kong + OpenID Connect 插件（或自研 Go‑chi 中间件）。  
- **功能**：  
  - TLS 终端，统一 **HTTPS**。  
  - **Rate‑Limit**：全局 QPS 5 k、单用户/IP 限流。  
  - **IP 黑名单**、**User‑Agent 检测**（防爬虫）。  
  - **请求日志**（ELK）和 **监控指标**（Prometheus `http_requests_total`）。  

> **为什么不直接在业务服务做限流**：网关在边缘层过滤，能在流量进入内部集群前削峰，保护内部服务。

### 5.2 提交服务（Submit Service）  

- **语言**：Go（天然高并发、低内存）。  
- **核心流程**：  
  1. **解析请求** → 验证字段、代码大小限制（≤ 1 MB）。  
  2. **写入对象存储**：`PUT /code/{submission_id}`，返回 **S3 URL**。  
  3. **事务写入 DB**：`INSERT INTO submissions (...)`. 使用 **SERIALIZABLE** 隔离级别防止重复提交。  
  4. **生产 Kafka 消息**：使用 **Kafka Producer Transaction**，确保 **Exactly‑Once**（写库成功后才投递）。  
  5. **返回提交 ID** 给前端。  

- **错误处理**：  
  - 代码存储失败 → 立即返回 500，回滚 DB。  
  - Kafka 投递失败 → 重试（指数退避），若仍失败返回 503（系统繁忙）。  

### 5.3 调度队列（Kafka）  

| 参数 | 说明 |
|------|------|
| **Topic** | `submissions` |
| **Partitions** | 12（依据 CPU 核数） |
| **Replication Factor** | 3（跨 AZ） |
| **Message Key** | `submission_id`（保证同一提交落同一分区） |
| **Consumer Group** | `judge-workers`（所有 Worker 共享） |

- **背压**：消费者消费速率低于生产速率时，Kafka 自动积压，**不会丢失**。监控 `lag`，若超阈值触发 **自动扩容**（增加 Worker 实例）。  

### 5.4 Worker（Judge Runner）  

#### 5.4.1 结构概览  

```go
type Worker struct {
    consumer  *kafka.Consumer
    sandbox   *SandboxManager   // Docker/Kata API client
    resultDAO *ResultDAO        // PostgreSQL writer
    logger    *zap.Logger
}
```

#### 5.4.2 工作流（伪代码）  

```go
func (w *Worker) Run() {
    for msg := range w.consumer.Messages() {
        sub := parseSubmission(msg.Value)
        w.updateStatus(sub.ID, "COMPILING")
        // 1. 拉取代码、测试用例（对象存储）
        codeFile := download(sub.CodePath)
        testCases := loadTestCases(sub.ProblemID)

        // 2. 创建沙箱
        containerID := w.sandbox.Create(
            image=runtimeImage(sub.Language),
            limits=ResourceLimit{CPU:2, Mem:2GB, Time:5s},
            mounts=[codeFile, testCases...],
        )
        // 3. 编译（若需要）+ 运行
        compileRes := w.sandbox.Exec(containerID, compileCmd(sub.Language))
        if compileRes.ExitCode != 0 { // 编译错误
            w.saveResult(sub.ID, verdict="CE", logs=compileRes.Stderr)
            continue
        }
        // 4. 对每个用例执行
        for _, tc := range testCases {
            execRes := w.sandbox.Exec(containerID, runCmd, stdin=tc.Input)
            // 超时、内存超限、运行时错误统一转化为 verdict
            verdict := judgeComparator(execRes, tc.ExpectedOutput)
            w.saveResultDetail(sub.ID, tc.ID, verdict, execRes)
        }
        // 5. 汇总整体 verdict（AC / WA / ...）
        overall := aggregateVerdicts(...)
        w.updateStatus(sub.ID, "FINISHED", overall)
        w.consumer.CommitMessage(msg)
    }
}
```

#### 5.4.3 沙箱实现细节  

| 技术 | 说明 | 安全措施 |
|------|------|----------|
| **Docker** + **cgroup** + **seccomp** + **AppArmor** | 轻量、启动快（≈ 0.5 s） | 1. `--memory=2g --cpus=2` <br>2. `--security-opt seccomp=profile.json` <br>3. `--read-only` 文件系统 <br>4. 禁止网络 `--network=none` |
| **Kata Containers**（可选） | 使用轻量化 VM，隔离更强 | 与 Docker 类似的资源配额，但在 VM 级别防止 **kernel exploit** |

- **文件系统**：挂载只读的题目/测试用例，只给代码目录读写权限。  
- **网络**：默认 **禁用**，仅在需要联网（如自定义评测器）时打开 **特定白名单**。  
- **系统调用过滤**：seccomp 只允许 `read/write/open/close/execve` 等必要调用，防止 **fork 炸弹**。  

#### 5.4.4 评测对比框架  

```go
func judgeComparator(execRes ExecResult, expected string) Verdict {
    if execRes.TimedOut { return "TLE" }
    if execRes.MemExceeded { return "MLE" }
    if execRes.ExitCode != 0 { return "RE" }

    // 1. 标准化输出（去掉末尾空白行）
    out := strings.TrimSpace(execRes.Stdout)

    // 2. 判题器选择
    switch problem.JudgeMode {
    case "strict":
        return if out == expected { "AC" } else { "WA" }
    case "float":
        return floatCompare(out, expected, eps=1e-6)
    case "unordered":
        return unorderedCompare(out, expected)
    case "custom":
        // 调用用户自定义的 Python 脚本，传入 out, expected
        return runCustomJudge(out, expected, problem.CustomJudgePath)
    }
}
```

- **自定义评测器**：平台提供 **安全的 Python 沙箱**（只读文件系统、时间/内存限制），用户上传的脚本只能访问 `stdout`、`expected` 两个字符串。  
- **统一返回**：`Verdict`（AC/WA/TLE/MLE/RE/CE）以及 **耗时、内存**，便于后端聚合统计。  

### 5.5 结果存储与查询  

- **写入**：Worker 调用 `ResultDAO.SaveDetail()` 将每个用例的 `verdict`、`exec_time_ms`、`memory_kb` 写入 `submission_results` 表。  
- **聚合**：提交完成后，`statistics` 表通过 **触发器**或 **后台任务**（每分钟一次）更新 `accepted_submissions`、`fastest_time_ms`。  
- **查询**：Result Service 从 **读库**读取 `submission_results`，返回给前端。  

### 5.6 监控、日志、告警  

| 维度 | 指标 | 采集方式 | 告警阈值 |
|------|------|----------|----------|
| **API** | `http_requests_total`, `latency_seconds` | Prometheus `client_golang` | QPS < 4.5k? 报警；95% latency > 2.5s |
| **Queue** | `kafka_consumer_lag` | Prometheus JMX Exporter | Lag > 10k |
| **Worker** | `worker_running_tasks`, `sandbox_creation_time`, `sandbox_cpu_usage` | Prometheus Node Exporter + custom exporter | 任务排队 > 30s |
| **Sandbox** | `container_exit_code`, `oom_killed` | cAdvisor + Prometheus | 出现 OOM > 5 次/分钟 |
| **DB** | `pg_stat_activity`, `replication_lag` | pg_exporter | 复制延迟 > 5s |
| **Storage** | `s3_bucket_size`, `s3_request_errors` | CloudWatch (AWS) | 错误率 > 1% |

- **日志**：  
  - **业务日志**（Submit/Result Service）写入 **ELK**，结构化 JSON。  
  - **沙箱日志**（stdout、stderr）保存至对象存储，路径写入 `judge_logs` 表，供审计/二次分析。  
- **告警**：Prometheus Alertmanager 通过 **PagerDuty** 或 **企业微信** 推送。  

---

## ## 第六步：扩展性与高可用设计  

### 6.1 弹性伸缩（Autoscaling）  

| 维度 | 触发指标 | 扩容动作 |
|------|----------|----------|
| **API 层** | `http_requests_total` 5 min avg > 4.5k | 增加 API GW 实例（K8s HPA） |
| **Worker** | `consumer_lag` per partition > 5000 | 增加 Worker Pod（K8s HPA） |
| **DB** | `pg_stat_activity` > 80% 连接数 | 启动 **读副本**（云 RDS 自动扩容） |
| **对象存储** | `s3_request_latency` > 200 ms | 开启 **跨区复制**，使用 CDN 加速读取 |

- **实现**：Kubernetes **Horizontal Pod Autoscaler (HPA)** + **Custom Metrics Adapter**（Prometheus）。  
- **防止“雪崩”**：使用 **二级阈值**（软阈值+硬阈值）和 **速率限制**（Ramp‑up 速率）避免瞬时激增导致资源争抢。  

### 6.2 高可用（HA）  

| 组件 | HA 方案 |
|------|----------|
| **API Gateway** | 多可用区部署 + **Anycast DNS**（Route53） |
| **Load Balancer** | 双层 L7 + **Health Check**，不健康实例自动下线 |
| **Auth / Submit Service** | **Stateless**，多副本，使用 **Redis Session Store**（可选） |
| **Kafka** | **3‑node** 集群 + **ISR**（In‑Sync Replicas） |
| **PostgreSQL** | 主‑从（同步复制）+ **Patroni** 自动故障转移 |
| **Redis** | 主从复制 + **Sentinel** 或 **Redis Cluster** |
| **Worker** | **无状态**，容器化部署，使用 **PodDisruptionBudget** 防止滚动更新导致全部下线 |
| **Sandbox** | **节点隔离**：每台机器跑 8‑10 个容器，若节点失效，仅影响局部任务，Kafka 再次投递即可重试 |

### 6.3 数据持久化与备份  

- **对象存储**：跨 AZ **版本化**（S3 Versioning）+ **生命周期策略**（90 天后转归档 Glacier）  
- **数据库**：每日全量快照 + PITR（Point‑In‑Time Recovery）  
- **Kafka**：Log Retention 7 天，开启 **MirrorMaker** 同步到备份集群  

### 6.4 灾备演练  

- 每月执行一次 **Chaos Engineering**（例如使用 **Chaos Mesh**）模拟节点失效、网络分区，验证自动恢复时间 < 30 s。  

### 6.5 成本控制  

| 资源 | 成本因素 | 优化措施 |
|------|----------|----------|
| **计算** | VM 实例、容器节点 | **弹性伸缩**、**按需/预留实例混合** |
| **存储** | 对象存储（标准） | **冷热分层**（最近 30 天标准，30 天后归档） |
| **网络** | 出站流量 | **CDN** 缓存题目描述，降低对象存储带宽 |
| **监控** | Prometheus 长期存储 | **Thanos** 或 **Cortex** 分层存储，历史数据压缩 |

> **关键点**：先把 **业务正确** 做好（MVP），再在 **成本、可用性、弹性** 上逐层加装 “保险”。面试时可以用 **“先有鸡还是先有蛋”** 的思路，说明自己会先交付可用系统，再迭代提升。  

---

## ## 第七步：常见面试追问与回答  

### 7.1 调度策略 & 突发流量  

**问**：如果提交量突发到 10 倍，如何保证评测延迟仍在 3 秒以内？  

**答**：  
1. **队列缓冲**：Kafka 本身可以无限积压，只要磁盘够大就不会丢失。  
2. **弹性伸缩**：监控 `consumer_lag`，当 lag 超过阈值（如 5 k）触发 **Worker** 实例水平扩容（K8s HPA），快速补齐执行槽。  
3. **冷热任务分离**：对 **高优先级**（如实时练习）和 **低优先级**（如离线批量评测）使用不同的 Topic / Consumer Group，防止互相抢占。  
4. **预热容器**：使用 **容器池**（预先创建一定数量的空闲沙箱容器），启动新任务时直接复用，减少 **容器启动时间**（从 1 s 降到 < 200 ms）。  
5. **限流 & 退避**：在 API 层对单用户/IP 进行 **速率限制**，超过阈值返回 429，客户端可实现 **指数退避**，从根本上削峰。  

> **效果**：在 10 倍突发时，系统会先通过 **限流** 把流量平滑到后端可接受的水平；若仍有剩余，则 **自动扩容 Worker**，在 30 秒内完成扩容（云实例启动 + 容器 warm‑up），整体评测延迟保持在 3 秒以内。

### 7.2 安全隔离  

**问**：用户可能提交恶意代码（如 fork 炸弹、网络攻击），你会采用哪些技术手段在沙箱层面防御？  

**答**：  
| 防御层面 | 技术手段 | 作用 |
|----------|----------|------|
| **系统调用** | **seccomp** 配置白名单（仅 `read/write/open/close/execve`） | 防止 `fork`, `clone`, `ptrace` 等危险调用 |
| **资源配额** | **cgroup** CPU/Memory 限制（2 CPU, 2 GB） + **ulimit**（进程数 64） | 过多子进程会被 OOM/KILL，防止 fork 炸弹 |
| **文件系统** | **只读根文件系统**，仅挂载 `/tmp` 为 **tmpfs**（大小 64 MB） | 防止写入系统关键路径 |
| **网络** | **--network=none**（Docker）或 **Kata** 默认禁用网络 | 阻止外部请求、端口扫描 |
| **用户命名空间** | **Docker userns-remap**，把容器内 UID 映射到宿主机的低权限 UID | 即使逃逸，也只能在受限用户下运行 |
| **沙箱类型** | **Kata Containers**（轻量 VM）或 **gVisor** | 更强的内核隔离，防止内核漏洞利用 |
| **监控/审计** | 实时捕获 `container_exit_code`、`oom_killed`，异常立即上报 | 便于事后取证、快速封禁恶意用户 |

> **如果只用 Docker 而不加 seccomp、cgroup、network=none**，恶意代码可能 **fork 炸弹** 把宿主机 CPU 用光、或尝试 **curl** 外部服务器进行 DDoS，导致整个平台不可用。  

### 7.3 评测结果一致性  

**问**：同一道题在不同语言实现可能有细微差别（如浮点误差），请设计一种评测对比框架，能够统一处理严格匹配与宽松匹配的需求。  

**答**：采用 **分层判题器（Judge Mode）** 与 **可插拔自定义评测脚本**。  

1. **统一输出规范**：在每个语言的 **模板代码**里，强制把所有输出写入 **stdout**，并在末尾统一加 **`\n`**，避免换行差异。  
2. **判题模式**（存于 `problems` 表）：  
   - `STRICT`：逐字符完全相等（`strings.TrimSpace` 后比较）。  
   - `FLOAT`：对每个数值使用相对/绝对误差阈值（`abs(a-b) < eps`），支持 **科学计数法**。  
   - `UNORDERED`：把输出按行/空格切分后排序再比较（适用于集合题）。  
   - `CUSTOM`：用户上传 **Python/JS** 脚本，系统在隔离沙箱中执行，脚本接受 `stdout` 与 `expected` 两个参数返回 `True/False`。  
3. **实现流程**：Worker 调用统一的 **Judge Service**（内部库），该库根据 `problem.JudgeMode` 选择对应的对比函数；若为 `CUSTOM`，则使用 **安全的 Python 沙箱**（同前面的安全措施）执行脚本。  
4. **结果统一**：每个对比函数返回统一结构 `{verdict:string, details:string}`，再写入 `submission_results`。  

> **优势**：  
- **可扩展**：新增判题模式只需实现一个函数或上传脚本，无需改核心代码。  
- **统一错误处理**：所有模式都在同一个入口捕获异常，保证 **AC/WA/RE** 的统一定义。  

### 7.4 其他常见追问  

| 追问 | 简要回答 |
|------|----------|
| **如何保证提交的代码不被泄露** | 代码只在 **短暂的沙箱** 内存在，写入对象存储时使用 **加密（SSE‑S3）**，并在 DB 中只保存 **URL**。访问对象存储需要 **IAM** 权限，普通用户无法直接下载他人代码。 |
| **排行榜的实时性如何做到** | 用 **Redis Sorted Set** 维护 `problem:{id}:ranking`，每次提交完成后 **ZADD**（score 为执行时间），并设置 **TTL**。后台定时把 Top‑N 持久化到 DB，防止 Redis 故障导致数据丢失。 |
| **如何处理语言版本升级** | 每种语言对应 **Docker 镜像**，如 `python:3.10-slim`、`openjdk:11-jdk`. 通过 **CI/CD** 自动构建新镜像并推送到镜像仓库，Worker 在启动容器时拉取最新镜像即可。 |
| **如果评测机器宕机，任务怎么办** | Kafka **至少一次投递** + **消费者提交位点**（`commit`）在任务成功写入 DB 后才提交。机器宕机导致容器未完成，消息未提交位点，其他 Worker 会重新消费该任务。 |

---

## ## 心得与反思  

### 1️⃣ 本题最难的设计决策  

| 决策 | 考虑因素 | 最终方案 | 关键思考 |
|------|----------|----------|----------|
| **沙箱技术选型**（Docker vs Kata vs gVisor） | ① 启动时延 ② 隔离强度 ③ 资源占用 ④ 生态成熟度 | **Docker + seccomp + cgroup** 为主，**Kata** 作为可选的 **高安全** 模式 | 先满足 **性能**（5 k QPS）再考虑 **安全**，通过组合安全配置实现 “足够安全 + 高并发”。 |
| **队列 vs 直接调用**（同步调度 vs 异步消息） | ① 峰值突发 ② 业务解耦 ③ 错误重试 ④ 可观测性 | **Kafka**（持久化、分区、Exactly‑Once） | 队列是 **天然的缓冲池**，可以让评测系统在高峰时“排队”，同时提供可靠的重试机制。 |

### 2️⃣ 新手最容易犯的错误  

1. **一次性把所有功能都堆进单体服务**  
   - 症状：代码量爆炸、部署困难、扩展受限。  
   - 正确做法：先划分 **提交、评测、查询** 三个 **业务微服务**，每个服务保持 **单一职责**，并使用 **接口协议**（REST/gRPC）解耦。  

2. **忽视安全隔离直接在裸机上跑代码**  
   - 症状：恶意代码导致宿主机宕机、数据泄露。  
   - 正确做法：把所有用户代码 **强制放进容器/轻量 VM**，并通过 **cgroup、seccomp、网络禁用** 进行多维度限制。  

3. **只关注功能不做监控**  
   - 症状：线上故障定位困难，难以满足 99.9% 可用性。  
   - 正确做法：从一开始就埋点 **Prometheus 指标**、**ELK 日志**，并定义 **SLA/SLO**。  

### 3️⃣ 学习建议与可延伸方向  

| 学习方向 | 推荐资源 | 关键收益 |
|----------|----------|----------|
| **容器安全** | 《Docker Security》、Kubernetes 官方安全白皮书 | 掌握 seccomp、AppArmor、user‑ns、Kata 等技术细节 |
| **分布式消息系统** | 《Designing Data‑Intensive Applications》章节 Kafka | 理解事务、Exactly‑Once、Consumer Lag 监控 |
| **高并发系统设计** | 《系统架构：从 0 到 1》、High‑Performance Browser Networking | 学会估算 QPS、并发数、瓶颈定位 |
| **监控与可观测性** | Prometheus 官方文档、Grafana 实战 | 实战指标设计、告警策略、可视化 |
| **分布式事务 & 幂等** | 《微服务设计》、SAGA/Outbox Pattern | 防止“提交成功但消息丢失”或“重复评测”问题 |
| **代码评测平台实现** | 开源项目 **Judge0**, **Codeforces Polygon**, **OpenJudge** | 参考真实实现细节，快速迭代自己的原型 |

> **实践 Tip**：  
> 1️⃣ 用 **Docker Compose** 搭建一个最小版的 **Submit → Kafka → Worker → PostgreSQL** 流程，跑通后再逐步迁移到 **K8s**。  
> 2️⃣ 写 **自动化测试**（单元 + 集成），尤其是 **沙箱启动/超时** 场景，防止回归。  

---

**至此，完整的在线代码评测系统设计已经呈现。**  
从 **需求拆解 → MVP → 关键技术选型 → 细化实现 → 高可用扩展 → 面试追问**，每一步都有 **原因说明**，帮助你在面试中有条理地表达设计思路，也能直接落地实现一个可用的原型。祝你面试顺利，后端成长加速 🚀！
