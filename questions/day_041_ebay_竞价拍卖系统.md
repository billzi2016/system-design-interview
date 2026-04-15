# 第 41 天：设计 eBay 竞价拍卖系统

> 生成日期：2026-04-15

---

# eBay 竞价拍卖系统 设计题

## 1. 题目背景
eBay 竞价拍卖系统为买卖双方提供线上拍卖服务，用户可以在拍卖期间对商品出价，系统在拍卖结束时将商品授予最高有效出价者。系统需要支撑海量并发出价、实时计时与结算，并保证公平、可靠的交易流程。

## 2. 面试场景设定
> **面试官**：  
> “假设我们要在全球范围内重新设计一个高可用的 eBay 竞价拍卖系统，核心需求是支持实时出价、拍卖倒计时以及拍卖结束后的结算。请你从需求分析、架构设计、关键技术选型和扩展性考虑，给出一个完整的系统设计方案。我们先从功能需求开始，你觉得这套系统至少需要哪些核心功能？”

## 3. 功能性需求
| 编号 | 功能描述 |
|------|----------|
| F1 | **商品上架 & 拍卖创建**：卖家创建拍卖（设置起始价、底价、加价幅度、拍卖时长、可选的保留价、自动延期规则等）。 |
| F2 | **实时出价**：买家在拍卖期间可以随时出价，系统立即校验合法性（是否高于当前最高价 + 加价幅度），并实时更新最高出价。 |
| F3 | **倒计时与抢拍保护**：在拍卖结束前 10 分钟内若有新出价，自动延长拍卖 2 分钟（防止“狙击”。）系统需实时推送倒计时和出价变动给前端。 |
| F4 | **拍卖结束结算**：拍卖结束后，系统自动确定获胜者，生成订单、冻结买家支付额度、发送通知并触发支付流程。 |
| F5 | **出价历史与查询**：买家可以查看某个拍卖的完整出价历史、当前最高价、剩余时间等信息；卖家可以查询自己商品的出价统计。 |
| F6 | **通知 & 消息中心**：出价成功、被超出、拍卖即将结束、获胜/未获胜等关键事件通过站内信、邮件或短信实时通知用户。 |

## 4. 非功能性需求
| 指标 | 估算值 | 说明 |
|------|--------|------|
| **DAU** | 30 Million | 全球活跃买家 + 卖家（约 1/3 为活跃出价用户）。 |
| **峰值 QPS（出价）** | 150 k QPS | 假设 5% 的 DAU 同时在拍卖高峰期（如双十一）进行出价。 |
| **平均响应延迟** | ≤ 200 ms（出价请求）<br>≤ 100 ms（查询倒计时/历史） | 需要实时感知出价结果，延迟直接影响用户体验。 |
| **可用性** | ≥ 99.95%（年可用） | 拍卖期间系统不可用会导致交易流失。 |
| **数据存储** | 约 200 TB（出价日志 + 商品元数据 + 订单） | 每笔出价约 200 B，假设 1 B 出价/秒 × 365 天 ≈ 6.3 PB，实际通过冷热分层和压缩后约 200 TB 热数据。 |
| **灾备恢复时间（RTO）** | ≤ 5 分钟 | 跨地域多活部署，单点故障快速切换。 |

## 5. 系统边界
**本题范围（需要设计）**  
- 竞拍核心流程：商品上架、实时出价、倒计时、拍卖结束结算。  
- 高并发出价的可靠性与一致性（防止超卖、竞价冲突）。  
- 实时推送与通知机制（WebSocket/Server‑Sent Events）。  
- 数据持久化（出价日志、商品状态、订单）以及冷热分层存储。  
- 基础的监控、告警与灾备设计。

**不考虑（可以略过）**  
- 支付网关的细节实现（只需要触发支付流程的接口）。  
- 商品搜索、推荐、图片存储等与拍卖无直接关系的业务。  
- 具体的前端 UI/交互实现（只需要说明前端如何获取实时数据）。  
- 法律合规、税务、跨境结算等业务规则。  
- 第三方物流、退货等后置流程。

## 6. 提示与追问
1. **一致性策略**：如果使用分布式缓存（Redis）加数据库，如何保证“最高出价”在并发情况下不出现脏读或超卖？  
2. **倒计时与自动延期**：在拍卖结束前 10 分钟内出现新出价时，系统如何高效、无竞争冲突地延长拍卖时间？请说明涉及的锁或乐观并发控制方案。  
3. **扩容与热点治理**：在大型促销活动（如黑五）期间，某些热门商品的出价 QPS 会激增，如何在不影响整体系统的前提下对热点商品进行流量分流或限流？  

---  
**请基于上述信息，进行系统设计并与面试官进行深入讨论。**

---

# 题解

# eBay 竞价拍卖系统设计全解答  

> **适用人群**：系统设计零经验的后端小白。  
> **目标**：从需求出发，一步步搭建最小可用系统（MVP），再逐层演进到满足千亿级并发、全局容灾的生产级架构。每一步都解释 *为什么* 要这么做， *不这么做* 会出现什么风险。  

> **阅读提示**：  
> - 章节顺序即为面试官可能的提问顺序。  
> - 关键技术点用 **粗体** 标记，后面会在「常见面试追问」章节专门解释。  
> - 文中出现的 **伪代码 / SQL / 表结构** 仅作概念说明，实际实现可根据语言/框架自行调整。  

---  

## ## 解题思路总览  

1. **先把核心业务抽象出来**：商品上架 → 拍卖进行中 → 出价 → 倒计时/自动延期 → 拍卖结束 → 结算。  
2. **估算规模**：算出 **DAU、QPS、存储量**，为后面的容量规划提供依据。  
3. **从最小可用系统（单机）出发**：先实现 **功能完整、正确**，再考虑 **性能、可用性、扩展性**。  
4. **划分系统边界**：把 **读写分离、实时推送、持久化、监控** 各自抽象为独立组件，便于后期拆分、扩容。  
5. **一致性 vs 可用性** 的取舍：出价操作必须强一致（防止超卖），查询可以弱一致（允许读到稍旧的最高价）。  
6. **技术选型**：  
   - **缓存/分布式锁**：Redis（单机多线程安全、支持 Lua 脚本）  
   - **持久化**：关系型数据库（MySQL）+ 时序日志（Kafka + HDFS）  
   - **实时推送**：WebSocket + 消息队列（Kafka）  
   - **流量治理**：限流/热点分片 + 熔断（Sentinel）  
7. **逐层演进**：从单体 → 主从复制 → 多活多地域 → 灾备。  

下面按照「从需求到实现」的顺序展开。  

---  

## ## 第一步：理解需求与规模估算  

| 需求 | 关键点 | 业务影响 |
|------|--------|----------|
| **F1 商品上架 & 拍卖创建** | 起始价、加价幅度、时长、保留价、自动延期规则 | 决定后端需要保存的元数据结构 |
| **F2 实时出价** | 合法性校验、实时最高价更新 | 高并发写入，必须强一致 |
| **F3 倒计时 & 抢拍保护** | 结束前 10 min 触发延长 2 min，实时推送 | 需要计时服务 + 低延迟广播 |
| **F4 拍卖结束结算** | 生成订单、冻结额度、触发支付 | 写入订单库，必须事务化 |
| **F5 出价历史查询** | 分页、过滤、统计 | 读业务，可使用缓存/冷热分层 |
| **F6 通知 & 消息中心** | 多渠道（站内、邮件、短信） | 需要异步消息推送系统 |

### 1.1 规模估算  

| 指标 | 计算方式 | 结果 | 备注 |
|------|----------|------|------|
| **活跃用户** | DAU ≈ 30 M | 30 M | 全球范围 |
| **峰值出价并发** | 5% 同时出价 × 30 M / 60 s ≈ 150 k QPS | 150 k QPS | 双十一等高峰 |
| **单笔出价大小** | 结构化 JSON ≈ 200 B | — | 包含用户ID、拍卖ID、出价、时间戳 |
| **每日出价总量** | 150 k QPS × 3600 s × 8 h ≈ 4.3 B 条 | 约 860 GB（压缩前） | 仅高峰时段估算 |
| **一年出价日志** | 4.3 B × 365 ≈ 1.6 T 条 | 约 200 TB（冷热压缩后） | 符合题目给出的存储需求 |
| **延迟要求** | 出价返回 ≤ 200 ms，查询 ≤ 100 ms | — | 需要低延迟路径（缓存+异步落库） |

### 1.2 非功能约束  

- **可用性 ≥ 99.95%** → 年宕机时间 ≤ 4.38 h，单点故障必须消除。  
- **RTO ≤ 5 min** → 跨地域多活 + 自动故障转移。  
- **数据安全**：出价日志必须 **不可篡改**（使用 Append‑Only、签名或区块链方式存储）。  

---  

## ## 第二步：高层架构设计  

下面给出 **从最小可用到生产级** 的演进路线图。  

### 2.1 最小可用（MVP）  

```
+-------------------+      +-------------------+
|   前端 (Web/APP)  |<---->|   API Gateway     |
+-------------------+      +-------------------+
                               |
                               v
                       +-----------------+
                       |  Auction Service|
                       +-----------------+
                               |
                               v
                       +-----------------+
                       |   MySQL (单库)  |
                       +-----------------+
```

- **API Gateway**：统一入口，做基础鉴权、限流。  
- **Auction Service**：业务核心（出价、计时、结算）。  
- **MySQL**：存放商品、出价、订单。  

> **问题**：单库在 150 k QPS 时会成为瓶颈，且无容灾。  

### 2.2 基础扩展（读写分离 + 缓存)  

```
+-------------------+      +-------------------+      +-------------------+
|   前端 (Web/APP)  |<---->|   API Gateway     |<---->|   Load Balancer   |
+-------------------+      +-------------------+      +-------------------+
                                                               |
                         +-------------------+   +-----------+-----------+
                         |   Auction Service|   |   Notification Service|
                         +-------------------+   +-----------------------+
                                 |                         |
                 +----------------+----------------+   +----+----+
                 |                                 |   |   Kafka |
            +----v----+                        +----v----v----+   |
            | Redis   |                        |   MySQL 主从  |<--+
            +----+----+                        +----+----+----+
                 |                                 |
          +------v------+                  +-------v-------+
          |   WebSocket |                  |   HDFS / S3   |
          +-------------+                  +---------------+
```

- **Redis**：热点拍卖的 **最高价**、**倒计时**、**出价计数** 等放入缓存，**读**走缓存，**写**走 Lua 脚本 + MySQL 异步持久化。  
- **MySQL 主从**：写入主库，读从库（查询历史、统计）。  
- **Kafka**：出价事件、通知事件的可靠异步消息。  
- **WebSocket**：实时推送最高价、倒计时给用户。  

### 2.3 生产级全局多活（跨地域）  

```
+-----------------------------------------------------------+
|                     全球 CDN / DNS                       |
+-----------------------------------------------------------+
            |                     |                     |
    +-------v-------+   +--------v--------+   +--------v--------+
    |  Region A     |   |  Region B      |   |  Region C      |
    +-------+-------+   +--------+-------+   +--------+-------+
            |                    |                     |
   +--------v--------+  +--------v--------+   +--------v--------+
   |  Global LoadBal |  |  Global LoadBal |   |  Global LoadBal |
   +--------+--------+  +--------+--------+   +--------+--------+
            |                    |                     |
   +--------v--------+  +--------v--------+   +--------v--------+
   |  API GW (多活)  |  |  API GW (多活)  |   |  API GW (多活)  |
   +--------+--------+  +--------+--------+   +--------+--------+
            |                    |                     |
   +--------v-------------------v----------------------v--------+
   |                     Service Mesh (Istio)                |
   +--------+-------------------+---------------------------+---+
            |                   |                           |
   +--------v--------+  +-------v--------+   +--------------v--------+
   | Auction Service |  | Notification  |   |   Search/Analytics   |
   +--------+--------+  +-------+--------+   +-----------+----------+
            |                   |                           |
   +--------v--------+  +-------v--------+   +--------------v--------+
   |  Redis Cluster  |  |  Kafka Cluster |   |   MySQL Cluster      |
   +--------+--------+  +-------+--------+   +-----------+----------+
            |                   |                           |
   +--------v-------------------v---------------------------v----+
   |                     多活 MySQL（Galera / TiDB）            |
   +-----------------------------------------------------------+
```

- **全局负载均衡 + DNS**：根据用户 IP 进行最近路由，故障时自动切换。  
- **Service Mesh**：统一流量控制、熔断、限流、可观测性。  
- **Redis Cluster + Kafka Cluster**：跨地域同步热点数据（使用 **Redis Replication + Kafka MirrorMaker**）。  
- **多活 MySQL**：使用 **Galera**（同步复制）或 **TiDB**（分布式事务）实现跨地域强一致写。  
- **灾备**：任意 Region 故障，流量自动切到其他 Region，RTO < 5 min。  

> **核心难点**：**跨地域强一致**（写入延迟） vs **低延迟出价**。后面章节会详细解释如何在 **出价路径** 采用 **本地缓存 + 乐观锁**，在 **结算阶段** 再做全局一致性校验。  

---  

## ## 第三步：数据库设计  

### 3.1 业务实体概览  

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 买卖双方信息（简化） | `user_id PK`, `username`, `email`, `phone`, `balance` |
| `auctions` | 拍卖元数据 | `auction_id PK`, `seller_id FK`, `item_name`, `start_price`, `min_increment`, `reserve_price`, `start_time`, `end_time`, `status` |
| `bids` | 出价日志（每笔出价） | `bid_id PK`, `auction_id FK`, `bidder_id FK`, `price`, `bid_time`, `is_winning` |
| `auction_state` | **热点缓存表**（也在 Redis） | `auction_id PK`, `current_price`, `current_winner_id`, `remaining_time`, `version` |
| `orders` | 拍卖结束后生成的订单 | `order_id PK`, `auction_id FK`, `buyer_id FK`, `price`, `status`, `created_at` |
| `notifications` | 消息中心（异步） | `notif_id PK`, `user_id FK`, `type`, `content`, `status`, `created_at` |

> **为什么单独拆出 `auction_state` 表**：  
> - 用来 **持久化** Redis 中的热点状态，防止机器重启丢失。  
> - 在 **结算** 时可直接读取，避免跨库事务。  

### 3.2 主键 & 索引设计  

- `auctions(auction_id)` 为 **PK**，自动递增或 UUID。  
- `bids`：  
  - **PK** = `bid_id`（自增）。  
  - **唯一索引** `(auction_id, price DESC)` 用于快速获取最高价。  
  - **普通索引** `auction_id`、`bidder_id` 用于查询历史。  
- `auction_state`：  
  - **PK** = `auction_id`。  
  - **唯一索引** `current_price`（非必需，只用于极端查询）。  
- `orders`：  
  - **唯一索引** `(auction_id)` 防止同一拍卖生成多笔订单。  

### 3.3 事务与一致性  

| 场景 | 需要的事务特性 | 解决方案 |
|------|----------------|----------|
| **出价** | **强一致**（防止超卖） | 采用 **Redis Lua 脚本 + 乐观锁**（版本号）+ **MySQL 异步落库**。|
| **倒计时延长** | **原子更新** | 在 Redis 中使用 **CAS**（compare‑and‑set）或 **RedLock** 进行竞争控制。|
| **拍卖结束结算** | **跨表事务**（更新 `auction_state`、`orders`、`users.balance`） | 使用 **两阶段提交（2PC）** 或 **分布式事务（TCC）**，在多活 MySQL 中可直接依赖 **XA**。|
| **查询历史** | **最终一致** | 读从库或离线冷数据（Hive/Presto），允许略微滞后。|

### 3.4 冷/热数据分层  

| 层级 | 存储 | 目的 |
|------|------|------|
| **热层** | Redis（内存） + MySQL 主库 | 实时最高价、倒计时、当前状态 |
| **温层** | MySQL 从库 + Kafka 持久化 | 出价日志查询、统计报表 |
| **冷层** | HDFS / S3 + Hive/Presto | 大规模历史分析、合规归档（≥ 1 年） |

---  

## ## 第四步：核心 API 设计  

下面给出 **RESTful**（亦可改为 gRPC）接口，配合 **WebSocket** 推送。每个接口都标明 **输入/输出、时序图、关键校验**。  

### 4.1 商品上架 / 创建拍卖  

```
POST /api/v1/auctions
Header: Authorization: Bearer <token>
Body:
{
  "seller_id": 12345,
  "item_name": "Apple iPhone 15",
  "description": "...",
  "start_price": 5000,
  "min_increment": 100,
  "reserve_price": 8000,          // optional
  "duration_seconds": 86400,      // 24h
  "auto_extend_seconds": 120,     // 2min
  "extend_threshold_seconds": 600 // 10min
}
```

**处理流程**  

1. **API Gateway** 校验 token → 获取 `seller_id`。  
2. **Auction Service** 检查商品合法性（是否已在售、是否违规）。  
3. **MySQL** 插入 `auctions`，生成 `auction_id`。  
4. **Redis** 写入 `auction_state`（`current_price = start_price`，`remaining_time = duration`）。  
5. 返回 `201 Created`，`Location: /auctions/{auction_id}`。  

> **为什么同步写入 Redis**：用户查询倒计时/最高价时必须马上可见，避免一次 DB 查询导致的 50‑100 ms 延迟。  

### 4.2 实时出价  

```
POST /api/v1/auctions/{auction_id}/bids
Header: Authorization: Bearer <token>
Body:
{
  "bidder_id": 98765,
  "price": 5300
}
```

**核心时序（伪代码）**  

```
# 1. API Gateway -> Auction Service
service.handleBid(auctionId, bidderId, price):
    # 2. 读取热点状态（原子）+ 版本号
    luaScript = """
    local state = redis.call('HMGET', KEYS[1], 'current_price','current_winner','version','end_time')
    local curPrice = tonumber(state[1])
    local version = tonumber(state[3])
    local endTime = tonumber(state[4])
    if tonumber(ARGV[1]) <= curPrice + tonumber(ARGV[2]) then
        return {err='price too low'}
    end
    if tonumber(ARGV[1]) > curPrice then
        redis.call('HMSET', KEYS[1],
            'current_price', ARGV[1],
            'current_winner', ARGV[3],
            'version', version+1)
        -- 延长倒计时（如果在阈值内）
        if endTime - tonumber(ARGV[4]) <= tonumber(ARGV[5]) then
            redis.call('HINCRBY', KEYS[1], 'end_time', tonumber(ARGV[6]))
        end
        return {ok='bid accepted', newVersion=version+1}
    end
    """
    result = redis.eval(luaScript,
        keys=[f"auction:{auctionId}:state"],
        args=[price, minIncrement, bidderId, now, extendThreshold, autoExtendSec])
    if result.err: raise BadRequest(result.err)

    # 3. 异步写入 MySQL（Kafka 生产者）
    kafka.produce('bid_topic', {
        'auction_id': auctionId,
        'bidder_id': bidderId,
        'price': price,
        'bid_time': now,
        'version': result.newVersion
    })
    # 4. 推送实时更新
    websocket.broadcast(auctionId, {
        'current_price': price,
        'current_winner': bidderId,
        'remaining_time': computeRemaining()
    })
    return 200 OK
```

**关键点解释**  

- **Lua 脚本**：在 Redis 中一次性完成 **读‑改‑写**，避免并发导致的 “脏读/超卖”。  
- **版本号（optimistic lock）**：防止网络抖动导致的 **写覆盖**。  
- **异步落库**：把出价写入 Kafka → MySQL Consumer，保证 **高吞吐**，同时不阻塞用户返回。  
- **延长倒计时**：脚本内部判断是否在阈值内（`extend_threshold_seconds`），如果是则 `end_time += auto_extend_seconds`。  

> **如果不使用 Lua 脚本**，会出现 **“读‑改‑写”** 的竞态窗口：两个请求几乎同时读取相同的 `current_price`，都认为自己合法，导致后面写入的价格不符合最小加价规则，产生 **超卖**。  

### 4.3 倒计时查询（实时）  

```
GET /api/v1/auctions/{auction_id}/state
```

- **实现**：直接从 **Redis** 读取 `current_price`、`current_winner`、`remaining_time`。  
- **响应时间**：< 5 ms（内存命中）。  
- **补充**：前端可建立 **WebSocket** 长连接，订阅 `auction:{auction_id}` 频道，服务器每次出价或倒计时变化后 **push** 消息。  

### 4.4 拍卖结束结算（内部触发）  

- **触发方式**：**定时任务**（Quartz/Elastic‑Job）在 `end_time` 到达时执行，或 **Redis keyspace notifications**（`EXPIRE`）触发。  

**伪代码**  

```
def settleAuction(auctionId):
    # 1. 加分布式锁，防止多节点重复结算
    lock = redlock.lock(f"settle:{auctionId}", ttl=30000)
    if not lock:
        return  # 已被其他节点处理

    # 2. 读取最终状态
    state = redis.hgetall(f"auction:{auctionId}:state")
    winner = state['current_winner']
    price  = state['current_price']

    # 3. 开启分布式事务（TCC）
    try:
        # Try phase
        orderId = db.insert('orders', {..., status='PENDING'})
        db.update('users', {'balance': balance - price}, where={'user_id': winner})
        # Confirm phase
        db.update('orders', {'status':'WAIT_PAY'}, where={'order_id': orderId})
        # 4. 发送通知
        kafka.produce('notification_topic', {...})
    except Exception as e:
        # Cancel phase
        db.rollback()
        raise
    finally:
        lock.release()
```

**要点**  

- **RedLock**：防止同一拍卖在多活环境被多次结算。  
- **TCC（Try‑Confirm‑Cancel）**：在高并发跨库更新时，比 **2PC** 更轻量，适用于 **订单、余额** 两张表的原子操作。  
- **状态机**：`order.status` 由 `PENDING → WAIT_PAY → PAID/FAILED`，保证 **幂等**。  

### 4.5 查询出价历史  

```
GET /api/v1/auctions/{auction_id}/bids?limit=20&offset=0
```

- **实现**：直接查询 **MySQL 从库**（或 ElasticSearch 建立二级索引），返回分页数据。  
- **缓存**：最近 100 条出价可以放在 **Redis List**，读取更快。  

### 4.6 通知中心  

- **内部**：`notification_topic` 消费后写入 `notifications` 表，同时调用 **邮件/短信** 供应商的异步 API。  
- **前端**：WebSocket 同步推送 **站内信**，移动端可通过 **FCM/APNs** 推送。  

---  

## ## 第五步：详细组件设计  

### 5.1 API Gateway  

- **职责**：统一入口、鉴权、流量控制、灰度发布。  
- **技术**：Kong / Nginx + Lua / Spring Cloud Gateway。  
- **关键配置**：  
  - **IP/用户 QPS 限流**（Sentinel） → 防止单用户刷接口。  
  - **路由分组**：`/auctions/**` → Auction Service，`/notifications/**` → Notification Service。  

### 5.2 Auction Service（核心业务）  

| 子模块 | 说明 | 关键技术 |
|--------|------|----------|
| **BidProcessor** | 处理出价请求，调用 Redis Lua 脚本，生产 Kafka 事件 | Java + Jedis / Lettuce + Redisson |
| **TimerManager** | 管理倒计时、自动延期、触发结算 | Quartz + Redis `EXPIRE` + ZSET（score = end_time） |
| **SettlementEngine** | 结算业务、分布式事务、状态机 | Spring Transaction + Seata / TCC-Framework |
| **CacheSynchronizer** | 将 Redis 状态定期持久化到 MySQL（防止失效） | ScheduledTask + MyBatis |
| **MetricsCollector** | 统计 QPS、延迟、错误率 | Prometheus client + Grafana dashboards |

#### 5.2.1 出价高并发实现细节  

1. **热点商品分片**：把热点 `auction_id` 按 **hash slot** 分布到不同 Redis 节点，避免单节点 CPU/网络瓶颈。  
2. **Lua 脚本**：保证 **原子性**，所有业务校验（价格、倒计时、自动延期）一次性完成。  
3. **写入 Kafka**：使用 **producer batch**（`linger.ms=5`、`batch.size=64KB`）提升吞吐。  
4. **幂等消费**：Kafka 消费端使用 `bid_id`（UUID）做 **去重**，防止因重试导致重复写库。  

#### 5.2.2 倒计时实现  

- **Redis ZSET**：键 `auction:deadline`，成员 `auctionId`，分值 `endTimestamp`。  
- **Timer Worker**：每秒轮询 ZSET，取出已到期的拍卖 ID，发送 **结算任务**（异步消息）。  

> **优势**：无需在每个拍卖实例维护独立计时器，统一调度，水平扩展。  

### 5.3 Notification Service  

- **消费**：Kafka `notification_topic`。  
- **处理**：根据 `type`（出价成功、被超出、即将结束、结算结果）写入 `notifications` 表 + 调用外部推送 API。  
- **幂等**：使用 `notif_id`（业务唯一键）做 **upsert**。  

### 5.4 数据持久化层  

| 层级 | 选型 | 读写特性 | 备注 |
|------|------|----------|------|
| **热** | Redis Cluster (主从) | **写** → 主节点；**读** → 任意节点（读写分离） | 采用 **Hash Slot** 分片 |
| **持久化** | MySQL 主从 (GTID) + TiDB/PolarDB（可选） | **写** → 主库；**读** → 从库 | 主库采用 **InnoDB** 行级锁 |
| **日志** | Kafka (3 副本) | **写** → Producer；**读** → Consumer | 用于出价、通知、审计 |
| **归档** | HDFS + Hive/Presto | **批处理** → Spark/Flink | 7 天热数据后冷归档 |

#### 5.4.1 防止写入冲突的技巧  

- **MySQL**：`INSERT ... ON DUPLICATE KEY UPDATE` 用于 **幂等写**（如订单创建）。  
- **TiDB**：天然支持 **分布式事务**，可以直接在结算时跨表操作。  

### 5.5 监控、告警、日志  

| 维度 | 监控工具 | 关键指标 |
|------|----------|----------|
| **系统** | Prometheus + Node Exporter | CPU、Memory、Network、Disk I/O |
| **业务** | Prometheus + Spring Boot Actuator | QPS、Latency、Bid Success Rate、延时结算数 |
| **链路追踪** | OpenTelemetry + Jaeger | 请求链路、Redis 脚本耗时、Kafka 生产/消费延迟 |
| **告警** | Alertmanager + PagerDuty | QPS 峰值、错误率 > 0.5%、Redis 节点宕机 |
| **日志** | ELK (Filebeat → Logstash → Kibana) | 出价日志、异常堆栈、审计日志 |

---  

## ## 第六步：扩展性与高可用设计  

### 6.1 横向扩容  

1. **API 层**：Stateless，使用 **容器化（Docker）+ K8s** 自动伸缩（HPA）  
2. **Auction Service**：每个实例只负责 **无状态业务**（业务规则），状态保存在 Redis/Kafka。  
3. **Redis Cluster**：通过 **水平分片**（hash slot）增加节点，自动迁移槽位。  
4. **Kafka**：分区数（topic partitions） = 3 × 预计并发热点商品数（如 5000），确保 **每个分区单线程** 顺序写入。  

### 6.2 热点治理  

| 场景 | 方案 | 说明 |
|------|------|------|
| **热点商品 QPS 爆炸** | **分片锁**（Auction ID → Redis 分区） + **局部限流**（Sentinel 对单商品） | 将热点分配到不同 Redis 节点，单商品限流防止瞬时冲击 |
| **全局突增** | **熔断 + 限流**（入口层） | 当整体 QPS 超过阈值，返回 `429 Too Many Requests`，并在前端提示排队 |
| **写放大** | **写入合并**（批量写入 Kafka） | 多个出价在 5 ms 内合并为一个 batch，降低网络 IO |

### 6.3 容灾与灾备  

1. **多活 Region**：每个 Region 部署完整业务栈（API、Service、Redis、Kafka、MySQL）。  
2. **全局流量调度**：使用 **Anycast DNS + GSLB**（如 Alibaba Cloud SLB Global）实现最近路由。  
3. **数据复制**：  
   - **Redis**：主从跨 Region（异步）+ **Redis Global Replication**（RDB+AOF）  
   - **MySQL**：基于 **Binlog** 的异步复制到备份 Region，关键表（`auctions`、`orders`）使用 **双写**（TCC）确保一致性。  
4. **故障切换**：  
   - **自动化脚本**：检测 Region 心跳，若失效自动将 DNS TTL 切换到健康 Region。  
   - **RTO ≤ 5 min**：切换后 Redis 缓存失效，业务自动回退到 **读写 MySQL**（略慢但可用）。  

### 6.4 数据一致性策略  

| 操作 | 强一致需求 | 采用方案 |
|------|------------|----------|
| **出价** | 必须 | Redis Lua + 版本号 + Kafka 异步落库（最终一致） |
| **倒计时延长** | 必须 | 原子更新 Redis ZSET，结算时再次校验 |
| **查询最高价** | 可接受轻度延迟 | 读 Redis（强一致）或读 MySQL（最终一致） |
| **订单生成** | 必须 | 分布式事务（TCC） + 幂等 `order_id` |
| **历史出价** | 最终一致 | MySQL 从库或离线大数据平台 |

---  

## ## 第七步：常见面试追问与回答  

### 7.1 “如果使用 Redis 加数据库，如何保证最高出价不出现脏读或超卖？”  

**回答要点**  

1. **Redis Lua 脚本**：在同一条脚本里完成 **读取‑校验‑更新**，保证原子性。  
2. **版本号（乐观锁）**：每次更新 `version` 字段，返回新版本给业务层，防止并发写覆盖。  
3. **持久化顺序**：脚本成功后立即 **生产 Kafka 事件**，异步写入 MySQL，**落库顺序**与 **Redis 更新顺序** 一致（Kafka 分区键为 `auction_id`）。  
4. **幂等消费**：Kafka 消费端使用 `bid_id` 去重，防止因网络重试导致的重复写入。  

> **不使用 Lua** 时，业务会出现 “先读后写” 的窗口期，两个请求可能同时看到相同的 `current_price`，都认为合法，导致 **超卖**。  

### 7.2 “倒计时自动延期怎么做到无竞争冲突？”  

**关键思路**  

- **单点更新**：把 **倒计时结束时间**（`end_time`）放在 Redis **ZSET**，成员是 `auction_id`，分值是时间戳。  
- **延长逻辑**：在出价 Lua 脚本里检查 `end_time - now <= extend_threshold`，若满足则 `ZINCRBY`（或 `HINCRBY`）把时间延长固定秒数。此操作同样在脚本中完成，**原子**。  
- **防止重复延长**：在脚本里加入 `if not already_extended then` 判断（使用 `extend_flag`），确保同一出价只能触发一次延长。  
- **结算触发**：Timer Worker 通过 `ZRANGEBYSCORE` 取出已到期的 `auction_id`，再尝试获取 **分布式锁**（RedLock）进行结算，保证同一拍卖只被结算一次。  

### 7.3 “热点商品流量激增时如何分流或限流？”  

**方案**  

1. **热点分片**：将热点 `auction_id` 映射到不同 Redis 分区，避免单节点成为瓶颈。  
2. **局部限流**：在 API Gateway 使用 **Sentinel** 对每个 `auction_id` 设置 **QPS 上限**（如 5k QPS），超出返回 `429`，前端可做排队或降级展示。  
3. **请求合并**：在同一毫秒内的出价请求可在网关层 **批量写入 Kafka**，减少对 Redis 的写入次数。  
4. **降级策略**：在极端峰值时，可以 **关闭自动延期**（只保留原有倒计时），降低写放大。  

### 7.4 “为什么不直接把所有出价写入 MySQL？”  

- **性能瓶颈**：MySQL 单实例写入 150 k QPS 需要大量连接、锁竞争、磁盘 I/O，难以满足 200 ms 延迟。  
- **事务开销**：每次出价都需要行级锁（`SELECT … FOR UPDATE`）导致锁等待，影响并发。  
- **扩展困难**：水平拆分（sharding）在强一致要求下实现复杂，且跨分片事务成本高。  

### 7.5 “如果 Redis 宕机，系统还能正常工作吗？”  

- **Redis 主从集群**：至少 3 主节点 + 3 从节点，故障自动迁移。  
- **缓存失效回退**：若全部节点不可用，业务可以 **降级**：直接查询 MySQL（读从库），仍能保证功能，只是响应时间上升到 100‑200 ms。  
- **持久化**：Redis 开启 **AOF**（Append Only File）+ **RDB** 快照，重启后可快速恢复。  

---  

## ## 心得与反思  

### 8.1 本题最难的 1‑2 个设计决策  

| 决策 | 难点 | 思考过程 |
|------|------|----------|
| **实时出价的强一致实现** | 需要在 **毫秒级** 完成并发控制、合法性校验、倒计时延长，同时保证高吞吐。 | - 先考虑直接 DB 锁，发现性能不达标。 <br> - 再尝试 **乐观锁** + **消息队列**，但仍有写入顺序风险。 <br> - 最终选用 **Redis Lua 脚本 + 版本号**，在内存层完成原子校验，随后异步落库，兼顾一致性与性能。 |
| **跨地域多活的结算一致性** | 多个 Region 同时可能收到同一拍卖的结束事件，若不统一处理会产生 **双单订单、重复扣款**。 | - 评估 **2PC**、**TCC**、**基于全局唯一事务 ID** 三种方案。 <br> - 2PC 受网络抖动影响，易超时。 <br> - TCC 业务代码相对清晰，支持 **幂等**，在结算阶段只需要 **Try** 阶段锁定库存/余额，**Confirm** 完成扣款，**Cancel** 回滚。 <br> - 结合 **RedLock** 进行 **单实例锁**，确保同一拍卖只被处理一次。 |

### 8.2 新手最容易犯的错误（至少 2 条）

1. **把所有业务都放在单体服务里**  
   - **后果**：无法水平扩容，单点故障直接导致全局不可用。  
   - **正确做法**：把 **无状态 API** 与 **有状态业务**（出价、计时、结算）拆分为独立微服务，状态统一放在外部缓存/数据库。  

2. **在出价路径直接写 MySQL 并使用 `SELECT … FOR UPDATE`**  
   - **后果**：锁竞争导致 QPS 下降到几千，延迟飙升。  
   - **正确做法**：使用 **内存缓存（Redis）+ 原子脚本** 完成校验与更新，再异步落库。  

### 8.3 学习建议和可延伸方向  

| 方向 | 推荐学习资源 | 关键点 |
|------|--------------|--------|
| **分布式缓存 & 原子脚本** | 《Redis Design and Implementation》, 官方 Lua 脚本文档 | 脚本的事务特性、性能调优、热点分片 |
| **消息队列与幂等消费** | 《Designing Data-Intensive Applications》, Kafka 官方教程 | 消费者组、分区键、事务性生产 |
| **分布式事务（TCC / Saga）** | 文章《TCC in microservices》, Seata 官方手册 | 业务拆分、补偿操作、幂等性 |
| **容器化与 K8s 自动伸缩** | 《Kubernetes Up & Running》 | HPA、PodDisruptionBudget、滚动升级 |
| **监控 & 链路追踪** | Prometheus + Grafana 官方指南, OpenTelemetry 入门 | 指标设计、告警阈值、端到端时延分析 |
| **高可用设计（多活）** | 《Site Reliability Engineering》, 云厂商多活案例 | DNS/GLB、跨地域复制、故障切换演练 |

> **实践建议**：先在本地或小型云环境实现 **出价 → Redis Lua → Kafka → MySQL** 的完整链路，验证 **吞吐 + 延迟**，再逐步加入 **计时 ZSET**、**RedLock**、**TCC 结算**。每加入一个新组件，都要写 **单元测试 + 集成测试**，并在监控中加入对应的 **SLO**（如 99.9% 出价成功率）。  

---  

**至此，完整的 eBay 竞价拍卖系统设计已经从需求、规模、架构、数据库、API、关键组件、高可用与面试追问全部阐述完毕。**  
祝你在面试中阐述自如、思路清晰，拿下高分！ 🎉  
