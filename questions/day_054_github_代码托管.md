# 第 54 天：设计 GitHub 代码托管

> 生成日期：2026-04-02

---

# GitHub 代码托管系统设计题

## 1. 题目背景
GitHub 是全球最大的 Git 代码托管平台，提供仓库管理、协作、CI/CD、代码审查等服务。面试官希望你从零开始设计一个具备核心功能的代码托管系统，能够支撑大规模的开发者社区。

## 2. 面试场景设定
> **面试官**：  
> “我们现在要设计一个类似 GitHub 的代码托管平台，核心是支持 Git 仓库的创建、克隆、推送、合并以及协作流程。请先从系统的整体架构出发，说明你会怎样划分模块、选择技术栈，并重点阐述高并发读写、数据一致性和存储扩展的方案。”

## 3. 功能性需求
| 编号 | 需求描述 |
|------|----------|
| F1 | **仓库管理**：用户能够创建、删除、重命名公开或私有仓库，支持多分支和标签。 |
| F2 | **Git 操作**：实现 `git clone`、`git push`、`git fetch`、`git pull`、`git merge` 等基本协议（HTTPS/SSH）。 |
| F3 | **权限控制**：基于组织、团队和个人的细粒度权限（读/写/管理员），支持邀请、审核、撤销。 |
| F4 | **代码审查 & Pull Request**：发起 PR、审查、评论、CI 检查、合并冲突解决，支持线下合并策略（squash、rebase、merge）。 |
| F5 | **持续集成 (CI) 集成**：提供 webhook 接口，能够在每次 push/PR 触发外部 CI 系统并返回构建状态。 |
| F6 | **搜索 & 统计**：全文搜索代码、issue、PR，提供仓库流量、贡献者统计等可视化数据。 |

## 4. 非功能性需求
| 编号 | 指标 | 估算值 | 备注 |
|------|------|--------|------|
| N1 | **活跃用户 (DAU)** | 2,000,000 | 包含个人开发者、企业团队等 |
| N2 | **请求吞吐量 (QPS)** | 10,000 req/s（峰值） | 主要来自 `git clone`、`git push`、网页浏览等 |
| N3 | **读写延迟** | < 150 ms（95% 请求） | `git clone` 首次下载时间受网络影响，内部元数据查询需保持低延迟 |
| N4 | **可用性** | 99.95%（年均） | 单点故障容忍，数据中心跨区灾备 |
| N5 | **存储容量** | 150 PB（3 年累计） | 按每个仓库平均 500 MB 计算，需支持弹性扩容 |
| N6 | **安全合规** | 支持 GDPR、SOC2，数据传输 TLS 1.2+，私有仓库加密存储 | 可选 |

## 5. 系统边界
**本题范围内（需要设计）**  
- Git 协议服务层（HTTPS/SSH）以及元数据管理  
- 仓库权限与组织结构模型  
- Pull Request 工作流、审查与合并策略  
- 基础的 CI webhook 机制  
- 存储层（对象存储 + 元数据 DB）与扩展方案  
- 高可用、容错、监控与报警框架

**本题范围外（不必详细设计）**  
- 完整的网页 UI/前端渲染（只需提供 API 接口层）  
- 具体的 CI 运行器实现（仅需 webhook 接口）  
- 代码搜索引擎的全文检索细节（只需提供调用接口）  
- 计费、订阅、商业化模块  
- 第三方登录（OAuth）细节，只需说明需要支持即可  

## 6. 提示与追问
1. **数据一致性**：  
   - “在高并发 `git push` 场景下，你如何保证仓库对象（blob、tree、commit）的强一致性？”  
2. **存储扩容**：  
   - “面对 PB 级别的对象存储，你会选用哪种分层存储方案，如何实现冷热数据自动迁移？”  
3. **灾备与故障恢复**：  
   - “如果某个数据中心突然不可用，系统如何保证正在进行的 `git clone` 不会出现错误？”  

---  
> **请在 45 分钟内完成系统整体设计，阐述你的关键技术选型、数据流与关键模块交互。**  

---

# 题解

# GitHub 代码托管系统设计完整解答  

> **写给新人**：本答案把每一次「我为什么要这么做」都写得很清楚，先从最小可跑通的系统开始，逐步加上高可用、扩容、容灾等特性，帮助你在面试里把「需求 → 架构 → 细节」的思路完整展示出来。  

---  

## ## 解题思路总览  

1. **先把需求拆成「必须实现」和「可选/后期扩展」**，确保最小可用系统（MVP）能跑通。  
2. **估算规模**（用户、QPS、存储），把数字转化成「每台机器要承受多少流量」的指标，指导后面的容量规划。  
3. **画出高层框图**：前端入口 → API 网关 → 业务服务层 → 存储层（对象存储 + 元数据 DB） → 监控/日志。  
4. **逐层细化**：  
   - **网络层**：CDN、负载均衡、TLS 终端。  
   - **协议层**：Git HTTP/SSH，独立的 Git Server（`git-http-backend` / `git-ssh`）。  
   - **业务层**：用户/组织/仓库服务、权限服务、PR/CI 服务、Webhook 服务。  
   - **数据层**：对象存储（Blob、Tree、Pack）、关系数据库（元数据、权限、审计）。  
5. **围绕「高并发读写」和「强一致性」** 设计：  
   - **写路径**（push）采用 **单写** + **分布式锁** + **原子对象写入**。  
   - **读路径**（clone、fetch）走 **CDN + 只读副本**，保证 99.95% 可用。  
6. **扩展性**：分层对象存储 + 热/冷分层、自动迁移；业务服务水平扩容；数据中心多活。  
7. **灾备**：跨区同步、只读副本、读写分离、故障转移（Fail‑over）流程。  

下面按 **7 大章节** 逐步展开。  

---  

## ## 第一步：理解需求与规模估算  

### 1️⃣ 功能需求拆解  

| 编号 | 关键子功能 | 是否 MVP 必要 | 备注 |
|------|-----------|--------------|------|
| F1 | 仓库 CRUD（公开/私有）+ 分支/标签 | ✅ | 后续可以把组织/团队放在同一服务里 |
| F2 | Git 协议（HTTPS/SSH）基本操作：clone、push、fetch、pull | ✅ | 只实现 **裸仓库**（bare repo） |
| F3 | 权限模型（Owner / Write / Read） | ✅ | 先实现基于 **仓库‑用户** 的 ACL，后续再细化组织/团队 |
| F4 | Pull Request 工作流（创建、评论、合并） | ✅ | CI 只做 webhook，合并策略可以先实现 **merge commit** |
| F5 | CI webhook 触发 + 状态回写 | ✅ | 支持 POST 到外部 URL |
| F6 | 简易搜索（Repo 名、Owner）+ 基础统计（star、fork、traffic） | 可选 | 先提供 **ElasticSearch** 只读索引，后面再做全文搜索 |

> **最小可用系统（MVP）**：只实现 F1~F5，F6 以后再加。这样可以在 1‑2 天内部署一个可用的原型。  

### 2️⃣ 非功能需求转化为指标  

| 编号 | 指标 | 计算方式 | 对系统的影响 |
|------|------|----------|--------------|
| N1 | DAU 2M | 假设 10% 同时在线 → 200k 并发用户 | 需要足够的 **前端入口**、**负载均衡**、**会话缓存** |
| N2 | 峰值 QPS 10k | 70% 为 clone/push，30% 为 API | 读请求（clone）可以走 **CDN + 只读副本**；写请求（push）需要 **强一致** |
| N3 | 95% 延迟 <150 ms | 主要是元数据查询（DB）和对象读取（对象存储） | DB 必须是 **读写分离**、对象存储要有 **低延迟缓存** |
| N4 | 可用性 99.95% → 每年约 4.38 h 故障窗口 | 必须实现 **多活**、**自动故障转移** |
| N5 | 150 PB 3 年 | 500 MB/仓库 × 300 M 仓库 ≈ 150 PB | 需要 **分层对象存储**（热/冷）以及 **弹性扩容** |
| N6 | 安全合规 | TLS、私有仓库加密、审计日志 | **网关层 TLS 终端**、对象加密、**审计 DB** |

> **容量估算示例**（写入流量）：  
- 每次 `git push` 平均 5 MB（增量），峰值 10k QPS 中 30% 为 push → 3 k push/s → 15 GB/s ≈ 540 TB/h。  
- 对象存储必须支撑 **突发写入**，采用 **分布式对象存储 + 多写副本**（如 Ceph、MinIO、或云厂商的 S3）来分摊。  

---  

## ## 第二步：高层架构设计  

下面先给出 **MVP 架构**，随后在「扩展性与高可用」章节再加入多活、跨区等细节。  

```
+-------------------+      +--------------------+      +-------------------+
|   CDN / Edge      | ---> |   API Gateway      | ---> |   Auth Service    |
+-------------------+      +--------------------+      +-------------------+
                                   |                     |
                                   v                     v
                     +---------------------------+   +-------------------+
                     |  Load Balancer (L7)       |   |  Rate Limiter /   |
                     +---------------------------+   |  WAF (Security)   |
                                   |                     |
        +--------------------------+---------------------+-------------------+
        |                          |                     |                   |
        v                          v                     v                   v
+---------------+   +--------------------+   +----------------+   +-----------------+
| Git HTTP/SSH  |   | Repo Service (CRUD)|   | PR Service     |   | Webhook Service |
|  Server       |   | (Repo Metadata)   |   | (PR lifecycle)|   | (CI trigger)    |
+---------------+   +--------------------+   +----------------+   +-----------------+
        |                          |                     |
        v                          v                     v
+-------------------+   +-------------------+   +-------------------+
| Object Storage    |   | Relational DB    |   | Relational DB    |
| (Blob, Pack)     |   | (Repo, Branch)   |   | (PR, Review)     |
+-------------------+   +-------------------+   +-------------------+
```

### 关键模块解释  

| 模块 | 负责的职责 | 技术选型（推荐） | 为什么选它 |
|------|------------|------------------|------------|
| **CDN / Edge** | 静态资源、Git Packfile 的全局加速 | Cloudflare / Akamai / 自建 CDN | 大量 clone 请求跨地域，CDN 能把对象缓存到离用户最近的节点，降低延迟 |
| **API Gateway** | 统一入口、协议转换、鉴权、限流、日志 | Kong / Ambassador / Spring Cloud Gateway | 统一管理所有 HTTP API，便于后期灰度发布 |
| **Auth Service** | 用户登录、OAuth、Token 发放 | Keycloak / Auth0（自建） | 支持 SSO、OAuth2、JWT，安全可靠 |
| **Load Balancer** | TCP/HTTP 负载均衡，提供健康检查 | Nginx/HAProxy + L4 (MetalLB) | 高性能、支持 SSL 终止 |
| **Git Server** | 实际处理 Git 协议（clone、push） | `git-http-backend` + `git-shell`（SSH） | 直接使用 Git 官方实现，兼容所有客户端 |
| **Repo Service** | 仓库元数据 CRUD、分支/标签管理 | Java Spring Boot / Go + gRPC | 业务逻辑相对独立，支持水平扩容 |
| **PR Service** | Pull Request 生命周期、审查、合并策略 | Go 微服务 + Event Bus (Kafka) | 需要高并发、可靠的事件驱动 |
| **Webhook Service** | 调用外部 CI、回写状态 | Node.js / Python Flask + Queue (RabbitMQ) | 简单的 HTTP POST，异步处理避免阻塞 |
| **Object Storage** | Git 对象（blob、tree、pack）持久化 | Ceph / MinIO / 商业 S3 (AWS, GCP, Azure) | 支持 PB 级别、分层冷热、强一致写入 |
| **Relational DB** | 元数据、权限、审计、PR 数据 | PostgreSQL (读写分离 + Patroni) | 强一致、复杂查询、事务需求 |
| **Message Queue** | 事件异步化、解耦 PR 与 CI | Kafka / Pulsar | 高吞吐、持久化、可回溯 |

> **为什么不直接把 Git 对象放进关系库？**  
对象大小千兆级别、写入频繁，关系库的行锁和磁盘 IO 成本太高，使用 **对象存储** 更合适；而元数据（分支、提交关系）需要事务，放在 **关系库**。  

---  

## ## 第三步：数据库设计  

### 1️⃣ 关系型数据库（PostgreSQL）模型  

| 表名 | 主键 | 关键字段 | 说明 |
|------|------|----------|------|
| **users** | user_id (UUID) | username, email, password_hash, created_at | 用户基本信息 |
| **organizations** | org_id (UUID) | name, owner_id, created_at | 企业/团队组织 |
| **teams** | team_id (UUID) | org_id, name, created_at | 组织内部的团队 |
| **team_members** | (team_id, user_id) | role (maintainer/member) | 多对多关联 |
| **repos** | repo_id (UUID) | owner_type (USER/ORG), owner_id, name, visibility (PUBLIC/PRIVATE), default_branch, created_at | 仓库信息 |
| **repo_collaborators** | (repo_id, user_id) | permission (READ/WRITE/ADMIN) | 仓库细粒度权限 |
| **branches** | (repo_id, branch_name) | commit_sha, protected (bool) | 分支指向的最新 commit |
| **tags** | (repo_id, tag_name) | commit_sha, created_at | 轻量标签 |
| **commits** (可选) | commit_sha (PK) | repo_id, author_id, message, parent_shas, tree_sha, created_at | 只保存 **metadata**，实际对象在对象存储 |
| **pull_requests** | pr_id (UUID) | repo_id, source_branch, target_branch, author_id, state (OPEN/MERGED/ CLOSED), created_at, merged_at | PR 主表 |
| **pr_reviews** | (pr_id, reviewer_id) | state (APPROVED/CHANGES_REQUESTED), comment, created_at | 审查记录 |
| **pr_comments** | comment_id (UUID) | pr_id, author_id, line, file_path, content, created_at | PR 代码评论 |
| **webhooks** | webhook_id (UUID) | repo_id, url, events (push, pr, etc.), secret, enabled, created_at | Webhook 配置 |
| **audit_logs** | log_id (UUID) | user_id, action, target_type, target_id, ip, timestamp | 合规审计 |

> **索引建议**  
- `users.username` 唯一索引（登录）  
- `repos.owner_type+owner_id+name` 唯一索引（唯一仓库路径）  
- `branches.repo_id+branch_name` 主键索引（快速查找）  
- `pull_requests.repo_id+state` 用于 PR 列表过滤  

### 2️⃣ 对象存储目录结构（基于 SHA‑1/256）  

```
/objects/
   aa/
      aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa   <-- 2‑hex 前缀做目录分片
   bb/
      bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
   pack/
      pack-<hash>.pack
      pack-<hash>.idx
```

- **写入**：`git push` 生成的对象先写入 **临时上传区**，完成校验后原子移动到正式路径。  
- **读取**：`git clone` 直接通过对象 URL（CDN 缓存）下载。  

### 3️⃣ 强一致性实现  

| 场景 | 关键点 | 解决方案 |
|------|--------|----------|
| **Push**（写对象 + 更新 refs） | 1️⃣ 对象写入必须是 **原子**；2️⃣ `refs/heads/<branch>` 必须在 **单写点** 防止冲突 | - 使用 **对象存储的多副本写**（如 Ceph 的 **RADOS**）保证对象写入成功后返回 **ACK**。<br>- **Git Server** 在处理 `push` 时，先获取 **分布式锁**（基于 **Redis RedLock** 或 **etcd**），锁住对应 **ref**，防止并发写同一分支。<br>- 完成对象上传后，**Git Server** 更新 `ref`（写入 `packed-refs`），再释放锁。 |
| **Read (clone/fetch)** | 读取的对象必须是 **最新** 的提交，且不受写入中间状态影响 | - 读取只访问 **已提交的对象**（对象写入成功后才会被引用），因此 **只读副本** 永远是 **强一致**。<br>- 使用 **Git packfile**（一次性打包），在 `push` 完成后立即生成新的 pack 并推送到 CDN。 |
| **PR 合并** | 合并时需要 **创建新的 commit** 并 **更新目标分支** | - 合并操作同样走 **分布式锁**，确保一次只能有一个合并写入目标分支。<br>- 合并完成后触发 **event**（Kafka）通知 **Webhook Service** 与 **CI**。 |

---  

## ## 第四步：核心 API 设计  

> 只列出 **HTTP/REST**（也可提供 gRPC）最常用的几组接口，实际实现时会把业务细化成微服务内部调用。  

### 1️⃣ 统一返回结构  

```json
{
  "code": 0,               // 0=成功，非0=错误码
  "message": "OK",
  "data": { … }            // 业务数据，若无则省略
}
```

### 2️⃣ 用户/鉴权  

| 方法 | 路径 | 功能 | 备注 |
|------|------|------|------|
| `POST /api/v1/auth/login` | 登录，返回 JWT | 支持用户名/密码、OAuth2 |  |
| `POST /api/v1/auth/logout` | 退出 | JWT 加入黑名单（Redis） |  |
| `GET /api/v1/users/me` | 查询当前用户信息 | 需要 `Authorization: Bearer <jwt>` |  |

### 3️⃣ 仓库管理（Repo Service）  

| 方法 | 路径 | 功能 | 关键参数 |
|------|------|------|----------|
| `POST /api/v1/repos` | 创建仓库 | body: `{name, visibility, description}` | 需要登录 |
| `GET /api/v1/repos/{owner}/{name}` | 获取仓库元数据 |  |  |
| `PATCH /api/v1/repos/{owner}/{name}` | 更新（改名、可见性） | body: `{new_name?, visibility?}` | 权限校验 |
| `DELETE /api/v1/repos/{owner}/{name}` | 删除仓库 |  | 仅 Owner/Admin |
| `GET /api/v1/repos/{owner}/{name}/branches` | 列出分支 |  |  |
| `POST /api/v1/repos/{owner}/{name}/branches` | 创建分支 | body: `{branch_name, from_commit_sha}` |  |
| `DELETE /api/v1/repos/{owner}/{name}/branches/{branch}` | 删除分支 |  |  |
| `GET /api/v1/repos/{owner}/{name}/tags` | 列出标签 |  |  |

### 4️⃣ 权限管理  

| 方法 | 路径 | 功能 | 备注 |
|------|------|------|------|
| `PUT /api/v1/repos/{owner}/{name}/collaborators/{username}` | 添加/修改协作者 | body: `{permission}` | 只能 Admin |
| `GET /api/v1/repos/{owner}/{name}/collaborators` | 列出协作者 |  |  |
| `DELETE /api/v1/repos/{owner}/{name}/collaborators/{username}` | 移除协作者 |  |  |

### 5️⃣ Pull Request（PR Service）  

| 方法 | 路径 | 功能 | 备注 |
|------|------|------|------|
| `POST /api/v1/repos/{owner}/{name}/pulls` | 创建 PR | body: `{title, body, head, base}` | `head` 为 source branch |
| `GET /api/v1/repos/{owner}/{name}/pulls` | 列出 PR | query: `state=open|closed|merged` |  |
| `GET /api/v1/repos/{owner}/{name}/pulls/{pr_id}` | 详情 |  |  |
| `POST /api/v1/repos/{owner}/{name}/pulls/{pr_id}/reviews` | 添加审查 | body: `{state, comment}` |  |
| `POST /api/v1/repos/{owner}/{name}/pulls/{pr_id}/merge` | 合并 PR | body: `{method: merge|squash|rebase}` | 需要锁定目标分支 |
| `POST /api/v1/repos/{owner}/{name}/pulls/{pr_id}/comments` | PR 代码评论 | body: `{file_path, line, body}` |  |

### 6️⃣ Webhook（CI 集成）  

| 方法 | 路径 | 功能 | 备注 |
|------|------|------|------|
| `POST /api/v1/repos/{owner}/{name}/hooks` | 新建 webhook | body: `{url, events[], secret}` |  |
| `GET /api/v1/repos/{owner}/{name}/hooks` | 列出 webhook |  |  |
| `DELETE /api/v1/repos/{owner}/{name}/hooks/{hook_id}` | 删除 |  |  |
| `POST /api/v1/webhooks/{hook_id}/deliveries` | 手动触发（调试） |  |  |

### 7️⃣ Git 协议（不走 REST）  

- **HTTPS**：`GET /{owner}/{repo}.git/info/refs?service=git-upload-pack`  
- **SSH**：`ssh git@host` → `git-shell` 执行 `git-receive-pack`、`git-upload-pack`  
- **鉴权**：HTTPS 使用 **Basic Auth**（用户名+Token）或 **OAuth2 Bearer**；SSH 使用 **SSH 公钥**，存放在 `users.ssh_keys` 表中。  

---  

## ## 第五步：详细组件设计  

### 1️⃣ Git Server（HTTPS/SSH）  

| 子组件 | 说明 | 关键实现细节 |
|--------|------|--------------|
| **git-http-backend** | 处理 HTTP Git 协议（upload‑pack、receive‑pack） | - 通过 Nginx `fastcgi_pass` 调用 `git-http-backend` <br>- 在 Nginx 配置 `auth_basic` → 调用 **Auth Service** 验证 Token <br>- 只读路径走 CDN 缓存，写入路径（push）走 **对象存储直写** |
| **git-shell (SSH)** | 处理 SSH Git 命令 | - 每个用户的 SSH 公钥在 **users_ssh_keys** 表，登录后 `authorized_keys` 指向统一脚本，脚本内部调用 **Auth Service** 验证 token 并执行对应 git 命令 <br>- 同样在 push 前获取 **分布式锁** |
| **Lock Service** | 防止并发写同一 `ref` | 基于 **etcd** 维护 `/locks/repo/{repo_id}/refs/{ref}` 键，TTL 30 s，push 完成后删除。<br>如果获取锁失败返回 `409 Conflict` 给客户端，客户端可自动重试。 |
| **Packfile Generator** | `git push` 完成后触发 packfile 重建 | 使用 **git-repack**，生成 `.pack`、`.idx`，放入对象存储 `objects/pack/`，随后向 CDN 发送 **purge**，让新 pack 生效。 |
| **Metrics Exporter** | 暴露 Prometheus 指标 | `git_push_total`, `git_clone_latency_seconds`, `lock_acquire_seconds` 等，供监控告警使用。 |

### 2️⃣ Repo Service（业务层）  

- **语言**：Go（高并发、原生协程）或 Java（成熟生态）。  
- **结构**：RESTful API + gRPC 对内部服务（PR、Webhook）调用。  
- **关键业务**：  
  1. **创建仓库** → 生成 `repo_id`、在对象存储创建根目录、写入 `HEAD` 指向 `refs/heads/main`。  
  2. **分支/标签操作** → 直接更新 **PostgreSQL** `branches`/`tags` 表，随后写入对应 `ref` 文件（`refs/heads/<branch>`）到对象存储，保持 Git 与 DB 同步。  
  3. **权限校验** → 每个 API 调用在入口统一拦截器里检查 **repo_collaborators** 或 **team** 权限，返回 403。  

### 3️⃣ PR Service（工作流）  

- **事件驱动**：所有 PR 相关操作（创建、审查、合并）先写入 DB，然后 **publish** 到 **Kafka** 主题 `pr-events`。  
- **消费者**：  
  - **Merge Worker**：监听 `pr-merge` 事件，获取锁、生成合并 commit、更新目标分支。  
  - **CI Notifier**：监听 `pr-created`、`push` 事件，遍历对应仓库的 **webhooks**，向外部 CI 发送 POST。  
- **状态机**（简化版）：`OPEN -> (APPROVED) -> MERGED` / `OPEN -> CLOSED`。  
- **冲突检测**：在 Merge Worker 中使用 `git merge-base`、`git diff` 检查是否冲突；若冲突返回错误给前端，提示手动解决。  

### 4️⃣ Webhook Service  

- **入库**：每次触发 webhook 前把请求写入 **Kafka** `webhook-deliveries`，保证 **至少一次** 投递。  
- **消费者**：读取消息后进行 HTTP POST，使用 **HMAC SHA256** 对 payload 进行签名（secret），返回成功后更新 `webhook_deliveries` 状态。  
- **重试策略**：指数回退（1s、5s、30s、5m），最多 5 次后标记为 **failed**，发送告警。  

### 5️⃣ 监控、日志、告警  

| 组件 | 监控指标 | 采集方式 |
|------|----------|----------|
| Git Server | `git_clone_qps`, `git_push_qps`, `push_latency_ms` | Exporter → Prometheus |
| API Gateway | `req_rate`, `error_rate`, `latency_p95` | Nginx/Envoy stats |
| DB | `pg_connections`, `replication_lag` | pg_exporter |
| Object Storage | `read_iops`, `write_iops`, `error_rate` | Ceph/Metrics |
| Kafka | `message_lag`, `consumer_offsets` | JMX Exporter |
| 系统 | CPU、内存、磁盘、网络 | node_exporter |

告警规则示例：  
- `push_latency_ms > 500` 持续 1 min → 警报。  
- `replication_lag > 5s` → 警报。  
- `webhook_failed_rate > 2%` → 警报。  

---  

## ## 第六步：扩展性与高可用设计  

### 1️⃣ 读写分离 & 多副本  

| 层级 | 方案 | 目的 |
|------|------|------|
| **API** | 多实例 + **负载均衡**（L7） | 横向扩容 |
| **Git Server** | **只读副本**（对象存储 + CDN） + **写入专用**（单主） | 读写冲突最小化 |
| **对象存储** | **Erasure Coding + 3‑way replication**（Ceph） | 数据可靠性、跨机房容错 |
| **PostgreSQL** | **主‑从（Patroni）** + **读写分离**（PgBouncer） | 高并发读 |
| **Kafka** | **多副本（replication.factor=3）** + **跨可用区** | 消息不丢失 |
| **Etcd/Redis**（锁） | **集群模式**（3‑node） | 分布式锁的容错 |

### 2️⃣ 冷/热分层对象存储  

- **热层**：SSD/NVMe-backed 存储（如 Ceph 的 **bluestore**），放置最近 30 天的对象（活跃仓库的最近 commit、pack）。  
- **冷层**：对象归档到 **对象桶**（如 AWS S3 Glacier、阿里云归档），存放 90 天以上的历史对象。  
- **迁移机制**：  
  1. **元数据 DB** 中的 `objects.last_accessed_at`（由 Git Server 在每次访问时更新）。  
  2. **后台定时任务**（每天）扫描，若 `last_accessed_at` 超过阈值则 **移动**：  
     - 从热层复制到冷层 → 删除热层副本。  
     - 在热层写入 **指向冷层的软链接**（或在对象元数据里记录 `storage_class=ARCHIVE`），后续请求触发 **自动回迁**（读取不到时回源）。  
  3. **CDN** 自动缓存热层对象，冷层对象不缓存。  

### 3️⃣ 跨地域灾备  

| 组件 | 跨地域方案 | 故障转移流程 |
|------|------------|--------------|
| **API Gateway** | **Anycast DNS** + 多 Region LB | DNS 将流量切换到可用 Region |
| **Git Server** | **双活**：每个 Region 部署完整 Git Server + 同步对象存储（CRR） | 某 Region 故障后，客户端自动请求最近的 Region，已有对象副本可直接 clone |
| **PostgreSQL** | **Logical Replication**（主‑主）| 写入任意 Region，冲突采用 **row‑based** 冲突解决（基于 timestamp） |
| **Kafka** | **MirrorMaker 2** 实现跨集群复制 | 消费者自动切换到备份集群 |
| **Etcd/Redis** | **跨可用区复制** | 使用 **sentinel**/**raft** 选举新 leader |

> **为什么不只在一个中心做灾备？**  
单中心故障（电力、网络、自然灾害）会导致所有用户不可用，违背 99.95% SLA。跨地域提供 **geo‑redundancy**，并且可以把用户流量路由到最近的节点，降低延迟。  

### 4️⃣ 业务容错  

- **Git Push**：如果写入对象存储的某一副本不可用，客户端会收到错误并自动 **重试**；对象存储内部会在后台完成副本恢复。  
- **Clone**：如果某个 CDN 节点失效，CDN 自动回源到对象存储的另一个副本，用户几乎感受不到中断。  
- **PR 合并冲突**：合并操作在 **Merge Worker** 中捕获冲突后返回错误，业务不阻塞。  

### 5️⃣ 自动扩容  

- **Kubernetes**：把所有微服务（API、Repo Service、PR Service、Webhook Worker）容器化，使用 **Horizontal Pod Autoscaler (HPA)** 基于 CPU、QPS 自动伸缩。  
- **对象存储**：使用 **Ceph 的 OSD 自动扩容** 或云厂商的 **S3 自动扩容**（按需付费）。  
- **数据库**：PostgreSQL 使用 **Citus**（分片）或 **CockroachDB**（分布式）实现水平扩展；如果业务增长到上百亿对象，考虑 **分库分表**（按 org_id 划分）。  

---  

## ## 第七步：常见面试追问与回答  

### Q1️⃣ 在高并发 `git push` 场景下，你如何保证仓库对象的强一致性？  

**回答要点**：  
1. **对象写入原子性**：Git 客户端在 `push` 前会把对象上传到临时区域，服务器在接收完全部对象后执行 **SHA‑1/256 校验**，只有校验通过才会把对象移动到正式路径（对象存储的 `rename` 是原子操作）。  
2. **分布式锁**：在更新 `ref`（如 `refs/heads/main`）前，先在 **etcd/Redis** 上获取基于 `repo_id+ref` 的锁，保证同一时刻只有一个 `push` 能修改该分支。  
3. **事务写入**：更新 `ref` 与写入 **PostgreSQL** `branches` 表在同一事务里提交，若任一步失败回滚，保持 DB 与 Git 对象的一致性。  
4. **多副本写入确认**：对象存储（Ceph）采用 **R=3**（3 副本）并返回 **QUORUM** ACK，确保至少两副本成功后才算成功。  

> **不使用锁会导致什么？**  
两个 `push` 同时更新同一分支，可能出现“后写覆盖前写”的情况，导致历史提交丢失，破坏 Git 的不可变性。  

### Q2️⃣ 面对 PB 级别的对象存储，你会选用哪种分层存储方案，如何实现冷热数据自动迁移？  

**回答要点**：  
- **冷热分层**：  
  - **热层**：使用 SSD/NVMe（Ceph bluestore）或云厂商的 **Standard S3**，保存最近 30 天活跃对象。  
  - **冷层**：使用低成本的 **对象归档**（如 S3 Glacier、阿里云冷存）存放 90 天以上的对象。  
- **自动迁移**：  
  1. 在 **Git Server** 每次对象读取时，记录 `last_accessed_at`（写入 DB）。  
  2. 定时任务（如每日）扫描 `objects` 表，依据访问时间判断冷热。  
  3. 使用 **对象存储的复制 API**（S3 CopyObject）把冷数据迁移到归档层，随后在热层写入 **指向冷层的元数据**（`storage_class=ARCHIVE`）。  
  4. 当用户再次访问归档对象时，后端检测到 `ARCHIVE`，触发 **回迁**（从冷层复制回热层），并在后台完成。  

- **优势**：成本随时间线性增长，且 **读热点**（clone、fetch）始终命中热层，满足 150 ms 延迟目标。  

### Q3️⃣ 如果某个数据中心突然不可用，系统如何保证正在进行的 `git clone` 不会出现错误？  

**回答要点**：  
1. **CDN 多节点**：`git clone` 的对象文件（`.pack`、`.idx`）首先在 CDN 缓存，客户端请求的都是 CDN 节点，不直接依赖源数据中心。  
2. **只读副本同步**：对象存储使用 **跨区域复制**（CRR），每个 Region 都有完整对象副本。即使源 Region 故障，CDN 会回源到另一个 Region。  
3. **负载均衡 & DNS**：使用 **Anycast DNS** + **健康检查**，当某 Region 健康检查失败，DNS 立即把流量切换到可用 Region，客户端不感知。  
4. **幂等恢复**：如果 `git clone` 正在下载中途断掉，Git 客户端会 **自动重试**（断点续传），因为对象是分块的（`packfile`），重新指向新的 CDN 节点即可。  

> **如果只是对象存储单点故障**：Ceph 的 **Erasure Coding** 能在失去部分 OSD 的情况下仍然提供完整数据，客户端仍能成功读取。  

### Q4️⃣ 代码审查（PR）与 CI 触发的可靠性怎么保证？  

- **事件总线**：所有 PR 操作写入 DB 后 **publish** 到 Kafka `pr-events`。Kafka 提供 **持久化** 与 **至少一次** 投递，确保即使 PR Service 崩溃，事件仍在队列中。  
- **Webhook 重试**：Webhook Service 消费 `pr-events`，发送 HTTP POST，记录 `delivery_id` 与状态。失败后进行指数回退，最多 5 次。  
- **幂等设计**：CI 系统在接收 webhook 时使用 `X-GitHub-Delivery`（唯一 ID）进行去重，防止重复构建。  

### Q5️⃣ 为什么不把所有业务（Git、PR、CI）都放在同一个单体服务？  

- **可维护性**：Git 协议对 IO、网络有极高要求，PR 工作流需要事务、异步消息，混在一起会导致 **资源争用**（CPU、内存）和 **部署复杂**。  
- **弹性伸缩**：Clone/Push 流量呈现 **突发性**（如开源项目发布），而 PR、CI 业务相对平稳。分离后可以 **针对性扩容**（Git Server 横向扩容，PR Service 按业务峰值扩容）。  
- **故障隔离**：如果 PR Service 出现 bug，Git 服务仍可正常提供 clone/push，保持核心功能可用。  

---  

## ## 心得与反思  

### 1️⃣ 本题最难的 1‑2 个设计决策  

| 决策 | 难点 | 思考过程 |
|------|------|----------|
| **Git 对象的强一致性 + 分布式锁** | Git 本身是 **无中心** 的分布式版本控制系统，传统的 DB 锁不适用于对象层。需要在高并发 `push` 场景下防止分支冲突，同时保证写入对象的原子性。 | - 先确认 Git 客户端的工作流程：先上传对象 → 再更新 refs。<br>- 设计两段式提交：① **对象写入**（对象存储原子 rename）② **ref 更新**（分布式锁 + DB 事务）。<br>- 评估锁实现：Redis RedLock vs etcd vs Zookeeper。最终选 **etcd** 因为它天然支持强一致的 KV 操作，且可以在多 Region 跨机房部署。 |
| **冷热对象分层 + 自动迁移** | 150 PB 数据量，单一存储成本极高，且访问热点极不均匀（少数活跃仓库占多数请求）。需要在不影响读写性能的前提下实现自动冷热分层。 | - 调研对象存储的 **生命周期策略**（S3 Lifecycle） vs 自建迁移任务。<br>- 结合 Git 的访问特性：每次 fetch/clone 都会读取 **对象的 SHA**，所以在 DB 中记录 `last_accessed_at` 能精确定位热点。<br>- 设计 **后台调度**（CronJob）每 24h 计算冷热阈值并执行 **对象复制 + 元数据更新**。<br>- 考虑回迁延迟对用户体验的影响，决定在 **读不到对象** 时同步回迁并返回 **202 Accepted** 给客户端，让 Git 客户端自行重试。 |

### 2️⃣ 新手最容易犯的错误（至少 2 条）  

1. **把 Git 协议和业务逻辑混在同一个服务**  
   - 结果：**性能瓶颈**（clone/push 大流量）会拖慢 PR、CI 的响应，导致整体可用性下降。  
   - 正确做法：**Git Server**（纯粹处理 `git-upload-pack`/`git-receive-pack`）独立部署，业务层通过 **API** 调用元数据服务。  

2. **忽视对象存储的写入一致性**  
   - 只在代码里写 `object.save()`，却没有检查 **写入成功** 或 **副本同步**，一旦出现网络抖动会导致对象缺失或损坏。  
   - 正确做法：使用 **对象存储的强一致写入**（S3 `PUT` + `HEAD` 校验），或在 **Ceph** 中使用 **R=3, Quorum**，并在写入后立即 **校验 SHA**。  

### 3️⃣ 学习建议和可延伸的方向  

| 方向 | 推荐学习资源 | 说明 |
|------|--------------|------|
| **Git 协议内部实现** | 《Pro Git》章节 9、Git 官方源码 (`git-http-backend`) | 理解对象模型、packfile、ref 更新的细节，有助于面试时解释一致性方案。 |
| **分布式锁 & 共识算法** | 《Designing Data-Intensive Applications》、etcd 官方文档 | 掌握强一致 KV、租约、选举机制，能在面试中自信讨论锁实现。 |
| **对象存储 & Ceph** | Ceph 官方手册、AWS S3 文档、腾讯云 COS 生命周期 | 了解 erasure coding、分层存储、跨地域复制的实现原理。 |
| **事件驱动架构** | Kafka 官方教程、Kubernetes 中的 Event‑Driven Design | 能把 PR、CI、Webhook 设计成解耦的可靠系统。 |
| **高可用与灾备** | 《Site Reliability Engineering》、Google Cloud Architecture Framework | 系统可用性、跨地域容灾的最佳实践。 |
| **监控与可观测性** | Prometheus + Grafana 实战、OpenTelemetry | 实际搭建指标、日志、追踪，面试时能说出具体的告警指标。 |

---  

**祝你面试顺利** 🚀  
把本答案当作「思路模板」记下来，面试时先把需求快速拆解成「核心功能 + 非核心功能」，再按「从 MVP → HA → 扩容」的顺序阐述，你的答案会显得结构清晰、层次分明，面试官也会很容易跟随你的思路。加油！
