# 第 81 天：设计 去中心化交易所（DEX）

> 生成日期：2026-03-06

---

## 题目背景  
去中心化交易所（DEX）是基于区块链智能合约实现的点对点数字资产交易平台，用户无需将资产托管在中心化服务器上即可进行买卖、做市和流动性提供。

## 面试场景设定  
> **面试官**： “我们现在要设计一套面向全球用户的去中心化交易所（DEX）核心撮合系统。请你从零开始梳理整体架构，重点说明高并发撮合、链上交互和用户体验是如何保证的。”  

（面试官随后会让你逐步展开功能、扩展性、容灾等细节。）

## 功能性需求  

| 编号 | 功能描述 |
|------|----------|
| 1 | **资产充值/提现**：用户可以把支持的 ERC‑20（或其他链上代币）转入智能合约做市池，或从合约中提取资产。 |
| 2 | **限价/市价订单下单**：支持单笔限价单、止盈止损限价单以及市价单，用户可指定买/卖方向、数量、价格等。 |
| 3 | **订单撮合与成交**：撮合引擎实时匹配买卖订单，生成链上成交事件，确保撮合结果在区块链上可验证且不可篡改。 |
| 4 | **流动性提供与撤回**：用户可向指定交易对的流动性池添加/移除流动性，并实时查看其 LP 份额、累计手续费收益。 |
| 5 | **行情查询 & 账户查询**：提供实时深度、最新成交、K 线等行情数据，以及用户资产、订单、持仓的查询接口。 |
| 6 | **安全/风控**：包括交易前的资产余额检查、重放攻击防护、速率限制（防刷单）以及合约升级治理机制。 |

## 非功能性需求  

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **日活跃用户（DAU）** | 100,000+ | 全球加密用户，峰值集中在欧美与东亚。 |
| **每秒请求数（QPS）** | 5,000 QPS（峰值） | 包括下单、查询、撤单等；撮合核心约 1,500 QPS。 |
| **撮合延迟** | < 200 ms（链下） | 从收到订单到撮合完成的时间，链上结算需再加上区块出块时间（≈12 s）。 |
| **系统可用性** | 99.9%（月可用） | 包括 API、撮合引擎、行情推送服务的可用性。 |
| **存储容量** | 30 TB（年） | 订单日志、成交记录、链上事件索引等，采用冷热分离存储。 |
| **扩展性** | 支持水平扩展至 10×峰值 QPS | 通过分区、无状态服务和分布式缓存实现。 |

## 系统边界  

**本题范围内需要设计的内容**  
- 交易撮合引擎（链下撮合、订单簿结构、冲突处理）  
- 与区块链的交互层（发送/监听智能合约事件、链上结算）  
- API 网关、身份鉴权、速率限制等前端入口  
- 数据存储方案（订单持久化、行情缓存、链上历史）  
- 高可用、容灾、水平扩展的基本方案  

**本题范围外（不必详细实现）**  
- 智能合约的具体 Solidity 代码实现（只需说明接口）  
- 钱包/私钥管理、链上加密签名细节  
- 跨链桥、衍生品、期权等高级金融功能  
- 监管合规（KYC/AML）以及法币入口  
- 前端 UI/UX 细节与移动端适配  

## 提示与追问  

1. **撮合引擎的状态同步**  
   - “如果撮合节点宕机，已经接受的订单该如何恢复？你会选用哪种持久化/日志方案保证零丢单？”  

2. **链上结算的延迟与用户体验**  
   - “考虑到区块出块时间，你如何在链下给用户展示‘已成交’的即时状态，同时又保证最终结算在链上不可篡改？”  

3. **扩展到多链或跨链交易**  
   - “如果以后要支持以太坊、BSC、Polygon 等多条 EVM 链，你的系统设计需要做哪些抽象或改动才能平滑扩展？”  

---

# 题解

## 解题思路总览
> **目标**：从「只有一台机器」的最小可用系统出发，逐层加上 **高并发撮合、链上交互、容灾、水平扩展** 等能力，帮助零经验的同学把“需求 → 设计 → 细节”这条完整链路理清楚。  
> **思考路径**  
> 1. **先把业务拆解**：把 DEX 的核心功能（充值/下单/撮合/结算/查询）分别抽象成独立的子系统。  
> 2. **估算流量 & 数据规模**：用需求表里的 QPS、DAU、存储等指标，算出对 CPU、网络、磁盘的粗略需求。  
> 3. **画出高层架构**：确定 **API 网关 → 业务服务层 → 撮合引擎 → 区块链交互层 → 持久化层** 的数据流向。  
> 4. **细化每个组件**：选技术栈、接口、缓存、日志、容错方案。  
> 5. **在每一步问自己“如果不这么做会怎样？”**，从而解释每个设计决策的必要性。  

下面按章节一步步展开。

---

## 第一步：理解需求与规模估算

| 需求维度 | 关键指标 | 估算方法 | 初步结论 |
|----------|----------|----------|----------|
| **用户规模** | DAU 100k，峰值活跃 30% ≈ 30k 同时在线 | 30k × 2（每用户平均 2 次并发请求）≈ 60k 并发连接 | 单机难以支撑，需要 **水平扩展** |
| **请求量** | 峰值 QPS 5,000（其中撮合 1,500） | - | 需要 **API 网关** 做流量入口、限流、鉴权 |
| **撮合时延** | <200 ms（链下） | 计算每笔撮合 CPU、内存占用 → 1500 QPS × 0.2 s = 300 并发撮合任务 | 单节点 **CPU ≥ 8核、内存 32 GB** 才能满足，实际仍建议 **多节点** |
| **链上结算** | 区块时间 ≈12 s（以太坊） | 需要 **异步上链**，链下先给用户“已成交”反馈 | 需要 **事件监听** 与 **状态回写** 机制 |
| **存储** | 30 TB/年 ≈ 2.5 TB/月 | 订单日志 + 成交记录 + 链上事件索引 | 采用 **冷热分离**：SSD + 对象存储（如 S3） |

**非功能需求映射**  
- **高可用 99.9%** → 多 AZ 部署、健康检查、自动切换。  
- **水平扩展 10×峰值** → **无状态服务 + 分区（sharding）**。  
- **安全/风控** → 鉴权、签名校验、速率限制、重放防护、合约治理。

> **小结**：从需求可以得到：系统必须 **拆分为多个相对独立的服务**（API、撮合、链交互、查询），每个服务都要做到 **无状态**（或通过外部存储实现状态持久化），才能实现后面的扩展与容灾。

---

## 第二步：高层架构设计

```
+-------------------+          +-------------------+          +-------------------+
|   前端 / SDK      |  HTTPS   |   API Gateway    |  gRPC /  |   Auth Service    |
+-------------------+--------->+-------------------+--------->+-------------------+
                                            |
                                            |  (限流、鉴权、路由)
                                            v
+-------------------+      +-------------------+      +-------------------+
|   Order Service   |<---->|   Matching Engine |<---->|   Settlement Service|
+-------------------+      +-------------------+      +-------------------+
        |                          |                         |
        | (写入)                    | (撮合结果)               | (上链交易)
        v                          v                         v
+-------------------+      +-------------------+      +-------------------+
|   Order DB (RDB) |      |   Order Book (In-  |      |   Blockchain Node |
|   (PostgreSQL)   |      |   memory / Redis) |      |   (Infura/Alchemy)|
+-------------------+      +-------------------+      +-------------------+
        |                          |                         |
        | (查询)                   | (实时深度推送)           | (事件监听)
        v                          v                         v
+-------------------+      +-------------------+      +-------------------+
|   Query Service   |<---->|   Market Data    |<---->|   Event Listener   |
+-------------------+      +-------------------+      +-------------------+
        |                          |                         |
        |  HTTP / WS               |  WS / Kafka              |  Kafka
        v                          v                         v
+-------------------+      +-------------------+      +-------------------+
|   Cache (Redis)   |      |   Message Queue   |      |   Archive Store   |
+-------------------+      +-------------------+      +-------------------+
```

### 关键模块解释

| 模块 | 主要职责 | 为什么要单独拆出来 |
|------|----------|--------------------|
| **API Gateway** | 统一入口、TLS 终止、限流、路由、灰度发布 | 防止业务服务直接暴露，便于 **统一治理** 与 **流量控制** |
| **Auth Service** | 基于钱包地址的签名验证、API Key、速率限制 | DEX 主要靠 **链上签名**，但仍需要 **防刷** 与 **防重放** |
| **Order Service** | 接收、校验、持久化订单；提供撤单、查询 API | **写入路径** 需要强一致性，使用 **事务** 保证零丢单 |
| **Matching Engine** | 内存订单簿、撮合算法（价格‑时间优先）、冲突处理 | 撮合对 **时延** 极其敏感，必须 **在内存** 完成 |
| **Settlement Service** | 将撮合结果打包成链上交易、发送、监听确认 | 链下撮合 + 链上结算的 **桥梁**，解耦两者的时延 |
| **Event Listener** | 监听智能合约的 `Trade`、`LiquidityAdded` 等事件，回写数据库 | 确保 **链上状态** 与 **链下缓存** 最终一致 |
| **Query Service** | 提供深度、K 线、订单/持仓查询，支持 **WebSocket** 实时推送 | 为前端/SDK提供 **低延迟** 的行情和账户信息 |
| **Cache / Message Queue** | Redis 做热点缓存，Kafka 做异步解耦 | 缓解数据库压力、实现 **高并发** 与 **可靠传输** |
| **Archive Store** | S3/OSS 存储订单日志、历史成交、审计数据 | 冷数据的 **低成本** 长期保存，满足合规审计需求 |

> **如果把所有功能都塞进同一个服务**，会导致：
> - 单点故障影响全部功能（下单、查询、撮合都不可用）  
> - 难以水平扩容（CPU、IO 竞争）  
> - 难以满足 **200 ms** 的撮合时延（数据库查询/网络往返拖慢）  

---

## 第三步：数据库设计

### 1. 关系型数据库（RDB）— 订单与持仓（PostgreSQL）

| 表名 | 主键 | 关键字段 | 索引建议 | 说明 |
|------|------|----------|----------|------|
| **users** | address (PK) | created_at | - | 钱包地址，唯一 |
| **orders** | order_id (PK) | user_address, pair, side, price, status, created_at | (user_address), (pair, side, price) | 记录原始下单信息及状态（NEW, PARTIAL, FILLED, CANCELED） |
| **trades** | trade_id (PK) | order_id, maker_order_id, pair, price, qty, tx_hash, block_number, created_at | (pair, block_number) | 撮合产生的成交记录，链上 tx_hash 用于审计 |
| **liquidity_positions** | lp_id (PK) | user_address, pair, liquidity, fee_earned, created_at | (user_address, pair) | LP 份额与累计手续费 |
| **account_balances** | address (PK) | token, amount, updated_at | (address, token) | 用于 **链下预估**，与链上余额最终对账 |

**事务保证**  
- **下单**：`INSERT INTO orders ...` + **余额检查**（在 `account_balances` 表里锁行 `FOR UPDATE`） → 保证 **零丢单** 与 **余额不负**。  
- **撤单**：`UPDATE orders SET status='CANCELED' WHERE order_id=? AND status='NEW'` → 原子化，防止并发撤单/撮合冲突。

### 2. 内存数据库（Redis）— 实时订单簿 & 缓存

- **订单簿**：使用 **Sorted Set**（ZSET）  
  - `orderbook:{pair}:bid` 价格从高到低（score = price）  
  - `orderbook:{pair}:ask` 价格从低到高（score = price）  
  - 每个 price 对应一个 **List**（FIFO）存放 order_id，保证 **价格‑时间优先**。  
- **用户资产缓存**：`balance:{address}:{token}` → 读取/写入速度毫秒级，定时同步回 PostgreSQL。  
- **行情快照**：`depth:{pair}`、`ticker:{pair}` 用于 WebSocket 推送。

> **为什么不把订单簿直接放在 DB？**  
> - DB 的读写延迟在毫秒级以上，无法满足 **200 ms** 撮合时延。  
> - 内存结构天然支持 **排序** 与 **快速弹出**（撮合）操作。

### 3. 消息队列（Kafka）— 可靠异步

| Topic | 生产者 | 消费者 | 作用 |
|------|--------|--------|------|
| `order_created` | Order Service | Matching Engine | 解耦下单与撮合，支持 **水平扩容** |
| `order_filled` | Matching Engine | Settlement Service, Event Listener | 将撮合结果写入链上 |
| `trade_onchain` | Settlement Service | Event Listener | 记录链上交易回执 |
| `liquidity_event` | Settlement Service | Query Service | 实时推送 LP 变化 |

> **如果直接同步调用**（如 Order Service 调用 Matching Engine RPC），会导致 **单点阻塞**，并且 **扩容难度大**。Kafka 的 **持久化+分区** 能保证 **至少一次** 投递，配合 **幂等** 处理即可实现 **零丢单**。

### 4. 冷存储（对象存储）— 历史审计

- 每日/每小时 **订单日志**（JSON）压缩后写入 S3。  
- 成交历史归档（Parquet）供离线分析（BI、风控）。  

---

## 第四步：核心 API 设计

> **统一使用 RESTful + WebSocket**，所有请求均需 **签名**（EIP‑191）或 **API Key**（限速）。

### 1. 鉴权模型

| 场景 | 鉴权方式 | 说明 |
|------|----------|------|
| **下单 / 撤单 / 充值** | 钱包地址 + **EIP‑712** 签名 | 防止伪造请求，且无需服务器保存私钥 |
| **查询 / 行情** | 可选 API Key + IP 限流 | 为公共数据提供轻量级访问控制 |
| **内部服务** | mTLS + JWT | 微服务之间的安全通信 |

### 2. API 列表（示例）

| 方法 | 路径 | 参数 | 返回 | 关键业务逻辑 |
|------|------|------|------|--------------|
| `POST /api/v1/orders` | 创建订单 | `{pair, side, type, price?, amount, deadline, signature}` | `{order_id, status}` | - 验证签名<br>- 检查余额（锁定）<br>- 写入 `orders` 表<br>- 发送 `order_created` 至 Kafka |
| `DELETE /api/v1/orders/{id}` | 撤单 | `signature` | `{order_id, status}` | - 检查订单状态<br>- 原子更新为 CANCELED<br>- 解锁资产 |
| `GET /api/v1/orders/{id}` | 查询单个订单 | - | 订单详情 | - 读取 DB + Redis 缓存 |
| `GET /api/v1/market/depth?pair=ETH/USDT` | 深度行情 | - | `{bids:[{price, qty}], asks:[...]}` | - 从 Redis 快速读取 |
| `GET /api/v1/market/kline?pair=...&interval=1m` | K 线 | - | K 线数组 | - 从 ClickHouse/TimescaleDB 读取 |
| `GET /api/v1/account/balance` | 账户余额 | `signature` | `{token: amount}` | - 读取 Redis，若缓存失效回源 DB |
| `GET /api/v1/account/orders` | 订单列表 | `signature` | 订单数组 | - 分页查询 |
| `GET /api/v1/liquidity/position?pair=...` | LP 信息 | `signature` | LP 详情 | - 读取 `liquidity_positions` 表 |
| **WebSocket** `/ws/market` | 实时推送深度、成交、K 线 | 订阅 `pair` | 事件流 | - 通过 Redis Pub/Sub → WS Server 推送 |

### 3. 错误码约定

| Code | 含义 |
|------|------|
| 0 | 成功 |
| 1001 | 鉴权失败（签名错误） |
| 1002 | 余额不足 |
| 1003 | 订单已存在/已撤销 |
| 2001 | 撮合冲突（订单已被撮合） |
| 3001 | 链上交易发送失败 |
| 5000 | 系统内部错误 |

> **为什么要把错误码写在响应体而不是 HTTP 状态码？**  
> - 前端/SDK 更关注业务错误（如余额不足）而不是网络层错误，统一结构便于解析。  
> - HTTP 状态码仍保留 200/4xx/5xx 语义，配合业务码实现 **更细粒度** 的错误处理。

---

## 第五步：详细组件设计

### 5.1 API 网关 & 鉴权

- **技术选型**：Nginx + Lua（OpenResty） 或 **Kong**（插件化）。  
- **功能**：TLS 终止、IP 限流、请求体大小校验、路由到内部微服务、统一日志收集（ELK）。  
- **实现签名校验**：在 Lua 脚本中调用 `secp256k1` 库，对 `EIP‑712` 消息体进行恢复地址并比对。

### 5.2 Order Service（写入路径）

```go
// 伪代码：创建订单
func CreateOrder(req CreateOrderReq) (Order, error) {
    // 1. 鉴权 & 签名恢复
    addr, err := VerifySignature(req.Signature, req.Payload)
    if err != nil { return nil, ErrAuth }

    // 2. 检查并锁定资产（行锁）
    tx, err := db.Begin()
    defer tx.Rollback()
    bal, err := tx.QueryRow("SELECT amount FROM account_balances WHERE address=$1 AND token=$2 FOR UPDATE", addr, req.Token)
    if bal < req.Amount { return nil, ErrInsufficient }

    // 3. 写入订单
    orderID := uuid.New()
    _, err = tx.Exec(`INSERT INTO orders (order_id,user_address, ...) VALUES (...)`)
    if err != nil { return nil, err }

    // 4. 提交事务
    if err = tx.Commit(); err != nil { return nil, err }

    // 5. 发送 Kafka 事件（异步）
    kafka.Produce("order_created", OrderCreatedEvent{orderID, ...})

    return order, nil
}
```

- **持久化保证**：使用 **事务** + **行锁** 防止并发冲突，**Kafka** 作为日志，确保 **“写入成功 → 事件一定能被消费”**（至少一次投递，幂等消费）。

### 5.3 Matching Engine（核心）

#### 5.3.1 数据结构

```go
type Order struct {
    ID       string
    Side     string // "buy" or "sell"
    Price    int64  // price * 1e8
    Qty      int64
    Timestamp int64 // Unix nano, 用于时间优先
}
type PriceLevel struct {
    price int64
    queue *list.List // FIFO of *Order
}
type OrderBook struct {
    bids map[int64]*PriceLevel // price -> level (max-heap)
    asks map[int64]*PriceLevel // price -> level (min-heap)
}
```

- **价格层** 用 `map` + **二叉堆**（或 `skiplist`）实现 **O(log N)** 的最高/最低价获取。  
- **订单队列** 用 `list.List` 保证 **时间优先**（FIFO）。

#### 5.3.2 撮合算法（价格‑时间优先）

```go
func Match(order *Order) []Trade {
    var trades []Trade
    if order.Side == "buy" {
        // 只匹配 price <= order.Price
        for price, level := range ob.asks {
            if price > order.Price { break }
            for level.queue.Len() > 0 && order.Qty > 0 {
                head := level.queue.Front().Value.(*Order)
                tradeQty := min(order.Qty, head.Qty)
                trades = append(trades, Trade{Maker:head.ID, Taker:order.ID, Price:price, Qty:tradeQty})
                // 更新数量
                order.Qty -= tradeQty
                head.Qty -= tradeQty
                if head.Qty == 0 {
                    level.queue.Remove(level.queue.Front())
                }
                if order.Qty == 0 { break }
            }
            if order.Qty == 0 { break }
        }
    } else {
        // sell side 对称
    }
    // 剩余未成交的挂单写回 OrderBook
    if order.Qty > 0 {
        ob.addOrder(order) // 按价格/时间插入
    }
    return trades
}
```

- **并发模型**：每个 **交易对**（pair）独立一个 **匹配协程**（Go routine / Akka actor），通过 **channel** 接收 `order_created` 事件。这样天然实现 **水平分区**，互不干扰。

#### 5.3.3 冲突与幂等

- **幂等键**：`order_id` + `trade_seq`。Settlement Service 在生成链上交易时，使用同一 `order_id` 保证即使因网络重试产生重复交易，智能合约内部会检查 `order_id` 是否已执行（`mapping(bytes32=>bool) processed`），防止 **双花**。

### 5.4 Settlement Service（链上结算）

1. **批量上链**：将同一区块高度的多笔成交聚合成 **单笔批处理交易**（如 Uniswap 的 `swapExactTokensForTokens`），降低 gas 成本。  
2. **发送**：使用 **Infura / Alchemy** 或自建 **Parity / Geth** 节点的 **JSON‑RPC** `eth_sendRawTransaction`。  
3. **回执监听**：通过 `eth_getTransactionReceipt` 或 **WebSocket** 订阅 `newHeads`，确认 `status=1` 后写入 `trades` 表并标记 `order.status=FILLED`。  
4. **回滚机制**：若链上交易失败（回滚），系统会 **补偿**：重新生成交易、解锁资产、发送 `order_failed` 事件。

> **用户体验**：链下撮合完成后，API 立即返回 `order_filled`，前端展示“已成交”。随后 Settlement Service 将交易上链，链上事件到达后再发送 **“已确认”** 的推送，前端用两种状态区分（`filled` vs `settled`）。

### 5.5 Event Listener（链上同步）

- **实现方式**：使用 **WebSocket** 订阅智能合约的 **Event Logs**（`Trade`, `LiquidityAdded`, `LiquidityRemoved`）。  
- **可靠性**：每条日志写入 Kafka `trade_onchain`，消费者（Query Service）从 Kafka 重放，保证 **即使节点掉线也能恢复**。  
- **幂等**：在消费时检查 `tx_hash` 是否已存在于 DB，已存在则跳过。

### 5.6 Query Service & 实时行情推送

- **行情缓存**：Redis 中的 `depth:{pair}` 每次撮合后 **增量更新**（price‑level 增删）。  
- **K 线**：使用 **ClickHouse** 进行高效聚合（每秒写入，支持毫秒级查询）。  
- **WebSocket 推送**：采用 **gorilla/websocket** 或 **NestJS + socket.io**，后端从 Redis Pub/Sub 拉取更新并广播。  
- **查询路径**：  
  - **热点**（深度、最新成交） → 直接读 Redis（**<5 ms**）  
  - **历史**（K 线、历史订单） → ClickHouse / PostgreSQL（**<100 ms**）  

---

## 第六步：扩展性与高可用设计

### 6.1 水平扩容（10×峰值）

| 维度 | 扩容手段 |
|------|----------|
| **API 网关** | 增加实例，使用 **L4/7 负载均衡**（AWS ALB、NGINX） |
| **Order Service** | **无状态** → 任意实例均可处理请求；数据库使用 **读写分离**（主从） |
| **Matching Engine** | **分区**：每个交易对独立一个匹配实例；Kafka 按 `pair` 分区，确保同一对的订单只落在同一实例 |
| **Settlement Service** | 按链或批次分区；使用 **任务队列**（Celery / Go workers）并行上链 |
| **Redis** | 集群模式（分片），每个分片 4‑8 GB，支持 **自动分片** |
| **Kafka** | 多分区 + 多副本（replication factor ≥ 3），保证吞吐与容错 |
| **数据库** | PostgreSQL 主从 + **逻辑分区**（按时间或用户 hash） |
| **对象存储** | S3 多 AZ 自动复制 |

### 6.2 高可用（99.9%）

- **多可用区（AZ）部署**：同一服务的实例跨 2‑3 个 AZ，负载均衡器做健康检查。  
- **自动故障转移**：  
  - **数据库**：使用 **Patroni** + **Etcd** 实现自动主从切换。  
  - **Redis**：采用 **Redis Sentinel** 或 **Redis Cluster** 自动故障转移。  
  - **Kafka**：分区副本 > 1，Leader 失效时自动切换。  
- **熔断 & 限流**：在网关层使用 **令牌桶**（token bucket）实现速率限制，防止刷单攻击。  
- **监控 & 报警**：Prometheus + Grafana 监控 QPS、延迟、CPU、内存、Kafka lag；PagerDuty / OpsGenie 报警。  
- **灾备**：每日快照 + 增量备份到异地对象存储，必要时可在另一云厂商恢复。

### 6.3 多链或跨链扩展

| 改动点 | 设计方案 |
|--------|----------|
| **链层抽象** | 定义统一的 **BlockchainAdapter** 接口：`SendTx(rawTx)`, `Subscribe(event)`, `GetBlockNumber()`；实现以太坊、BSC、Polygon 等具体适配器。 |
| **合约地址映射** | `chain_id -> contract_address_map`（JSON/DB），服务启动时加载。 |
| **资产模型** | 把 **token** 视为 `(chain_id, contract_address, decimals)`，在 `account_balances` 表中加入 `chain_id` 字段。 |
| **跨链桥**（后期） | 使用 **Message Bus**（Kafka）转发跨链事件，统一在 **Settlement Service** 中处理。 |
| **统一 API** | 在请求体加入 `chainId` 参数，网关验证链是否受支持；内部服务根据 `chainId` 选取对应 Adapter。 |
| **监控** | 每条链单独监控出块时间、gas price，以便动态调节 **上链批次大小**。 |

> **不做抽象的后果**：每新增一条链都要改业务代码、重新部署，容易产生 **业务耦合** 与 **故障蔓延**。

---

## 第七步：常见面试追问与回答

### Q1️⃣ “如果撮合节点宕机，已经接受的订单该如何恢复？你会选用哪种持久化/日志方案保证零丢单？”

**回答要点**  
1. **订单写入采用两阶段提交**：  
   - **第一阶段**：在 `Order Service` 中 **事务性写入** `orders` 表并 **锁定资产**。  
   - **第二阶段**：事务提交成功后 **立即**向 Kafka `order_created` 主题发送 **不可变事件**（order_id、完整订单信息）。  
2. **Kafka 持久化**：Kafka 默认把消息写到磁盘并复制到多个副本（`replication.factor >= 3`），即使匹配引擎宕机，事件仍保留。  
3. **匹配引擎恢复流程**：  
   - 启动时读取 **Kafka 最后已提交 offset**。  
   - 从该 offset 继续消费未处理的 `order_created`，重新进入撮合流程。  
   - 因为订单已在 DB 中持久化，且资产已锁定，重新撮合不会产生冲突（幂等检查 `order.status`）。  
4. **幂等保障**：在撮合时先检查 `order.status` 是否已是 `FILLED`，若是直接跳过。  

> **如果不使用 Kafka**，而是直接调用内部 RPC，宕机后已接受的订单会丢失，导致 **用户资产锁定但无撮合**，这在金融系统是不可接受的。

---

### Q2️⃣ “考虑到区块出块时间，你如何在链下给用户展示‘已成交’的即时状态，同时又保证最终结算在链上不可篡改？”

**回答要点**  
1. **链下撮合**：订单匹配后，Matching Engine 立即生成 **内部成交记录**（`trade_id`）并写入 **PostgreSQL + Kafka**。此时 API 已返回 `order_filled`，前端显示 “已成交”。  
2. **链上结算**：Settlement Service 把这些内部成交 **批量打包**，生成 **链上交易**并发送。  
3. **双状态模型**：  
   - `FILLED`（链下） → 表示撮合成功，用户已看到成交。  
   - `SETTLED`（链上） → 交易被区块确认，状态不可篡改。  
4. **前端 UI**：使用两种颜色或标记区分（如“已成交（待确认）” → “已完成”。）  
5. **回滚机制**：如果链上交易因 gas 不足、nonce 冲突等失败，Settlement Service 会 **重新打包**，并在 UI 中显示 “结算失败，正在重试”。  

> **不这样做的后果**：只能等区块确认后才返回结果，用户体验极差（≥12 s 延迟），会导致 **订单撤单率飙升**。  

---

### Q3️⃣ “如果以后要支持以太坊、BSC、Polygon 等多条 EVM 链，你的系统设计需要做哪些抽象或改动才能平滑扩展？”

**回答要点**  
1. **链抽象层**：定义 `BlockchainAdapter` 接口（发送交易、查询状态、订阅事件），每条链实现对应的适配器。  
2. **配置化合约地址**：使用 `chainId -> contractAddress` 映射表，业务代码通过 `chainId` 动态读取。  
3. **资产模型扩展**：在 `account_balances` 与 `orders` 表中加入 `chain_id`，保证同一 token 在不同链上是独立记录。  
4. **服务实例分片**：Kafka 主题按 `chainId` 分区，Matching Engine 按 `pair+chainId` 分配实例，防止跨链数据混淆。  
5. **统一 API**：在所有请求中加入 `chainId` 参数，网关做路由校验，后端统一走同一套业务流程。  
6. **监控 & 参数调优**：每条链的出块时间、gas price 不同，需要 **动态调节** 上链批次大小与费用上报策略。  

> **若不做抽象**，每新增一条链都要复制一套业务代码、部署新服务，导致 **维护成本指数级增长**，且容易出现 **链间状态不一致** 的严重错误。

---

## 心得与反思

### 1️⃣ 本题最难的 1‑2 个设计决策及思考过程  

| 决策 | 挑战 | 思考路径 |
|------|------|----------|
| **撮合引擎的状态持久化 vs. 完全内存** | 撮合必须 **毫秒级**，但又不能因节点宕机丢单。 | - 先把撮合逻辑放在 **内存**（Redis + Go 协程）保证时延。<br>- 为了防止宕机丢单，引入 **Kafka** 事件日志，实现 **写前日志（WAL）**。<br>- 采用 **两阶段提交**：先写 DB + 事务锁定资产 → 再发 Kafka。这样即使撮合进程挂掉，事件仍在队列中，可恢复。 |
| **链下成交与链上结算的双状态模型** | 用户期望即时成交反馈，但链上确认需要秒级延迟。 | - 将撮合结果立即返回给用户（`FILLED`），并在后台 **异步上链**。<br>- 引入 **Settlement Service** 负责批量上链，使用 **事件监听** 确认后再标记 `SETTLED`。<br>- 前端 UI 通过两种状态区分，提升体验又不牺牲不可篡改性。 |

### 2️⃣ 新手最容易犯的错误（至少 2 条）

| 错误 | 可能的后果 | 正确做法 |
|------|------------|----------|
| **把撮合逻辑直接写在单体服务里，使用关系型数据库做订单簿** | 读写延迟高，撮合慢，难以达标 200 ms；单点故障导致全平台不可用。 | 使用 **内存订单簿（Redis/自实现）**，撮合引擎独立 **无状态**，通过 **Kafka** 解耦。 |
| **只依赖链上事件实时返回用户成交** | 区块时间 12 s，用户体验极差，导致撤单/刷单。 | 实现 **链下撮合 + 链上结算** 双状态模型，前端即时展示 `FILLED`，后端异步上链。 |
| **忽视幂等与重放防护** | 重复交易导致资产双扣、撮合冲突。 | 在所有外部调用（订单、撮合、上链）加入 **唯一标识**（order_id、nonce），合约层也做 **已处理校验**。 |

### 3️⃣ 学习建议和可延伸的方向

1. **系统设计基本功**  
   - 熟悉 **CAP 定理、CAP vs. BASE**，理解 **一致性 vs. 可用性** 的取舍。  
   - 练习 **高并发** 场景下的 **幂等、限流、熔断**（如 Netflix Hystrix、Envoy）。  

2. **金融/交易系统专属**  
   - 学习 **订单簿实现**（price‑time、size‑priority），阅读开源项目如 **Hummingbot、0x Match**。  
   - 了解 **区块链交易生命周期**：签名 → 发送 → 打包 → 确认 → 事件。  

3. **技术栈深耕**  
   - **Go / Rust**：高性能网络服务，原生协程/异步。  
   - **Kafka / Pulsar**：分布式日志，熟悉 **Exactly‑Once** 语义。  
   - **Redis Cluster / RediSearch**：内存排序、实时查询。  

4. **可观测性**  
   - 掌握 **OpenTelemetry**、**Prometheus**、**Grafana**，建立 **端到端** 监控链路（从 API 请求到链上交易）。  

5. **跨链与 Layer‑2**  
   - 关注 **Optimism、Arbitrum、zkRollup** 的上链模型，思考 **如何在 L2 上实现高频撮合**。  

---

**祝你在面试中能把这套思路完整地阐述出来，展现对业务、技术、可靠性全方位的把握！** 🎉
