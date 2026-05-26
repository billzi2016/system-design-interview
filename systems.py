SYSTEMS = [
    # 社交 / 通讯
    "Discord",
    "WhatsApp",
    "Twitter/X",
    "Instagram",
    "Facebook Feed",
    "TikTok（抖音）",
    "Snapchat",
    "LinkedIn",
    "Reddit",
    "Telegram",
    "微信（WeChat）",
    "微博（Weibo）",
    "小红书",
    "Slack",
    "Zoom",

    # 视频 / 音频 / 直播
    "YouTube",
    "Netflix",
    "Spotify",
    "Twitch 直播平台",
    "Bilibili",
    "爱奇艺",
    "播客平台（Podcast）",
    "直播带货系统",
    "短视频推荐系统",

    # 存储 / 文件
    "Dropbox",
    "Google Drive",
    "iCloud",
    "Pastebin 文本分享",
    "图片托管服务（Imgur）",

    # 搜索 / 发现
    "Google 搜索引擎",
    "Elasticsearch 全文检索系统",
    "图片搜索引擎",
    "今日头条（信息流推荐）",
    "商品搜索系统（电商）",

    # 电商 / 支付
    "Amazon 购物车与结算",
    "支付宝",
    "微信支付",
    "Stripe 支付系统",
    "淘宝 / 天猫",
    "拼多多秒杀系统",
    "eBay 竞价拍卖系统",
    "闲鱼二手交易平台",
    "优惠券 / 红包系统",

    # 出行 / 地图 / 配送
    "Uber 打车系统",
    "Airbnb",
    "Google Maps 导航",
    "滴滴出行",
    "12306 高铁购票系统",
    "美团外卖配送系统",
    "共享单车系统",
    "快递物流追踪系统",

    # 生产力 / 协同
    "Notion",
    "Figma 实时协同编辑",
    "GitHub 代码托管",
    "Google Docs 协同文档",
    "Jira 项目管理",
    "在线 Excel（多人实时）",
    "腾讯文档",

    # 基础设施 / 分布式组件（中心化）
    "分布式缓存系统（类 Redis Cluster）",
    "消息队列系统（类 Kafka）",
    "API 网关",
    "分布式限流器（Rate Limiter）",
    "短链接服务（TinyURL）",
    "分布式 ID 生成器（Snowflake）",
    "分布式锁服务",
    "分布式定时任务调度器",
    "CDN 内容分发网络",
    "负载均衡器",
    "服务注册与发现（类 Consul）",
    "分布式事务协调系统",
    "日志收集与分析系统（类 ELK）",
    "监控告警系统（类 Prometheus + Grafana）",
    "配置中心（类 Apollo）",
    "在线代码评测系统（类 LeetCode Judge）",
    "云函数 / Serverless 平台",
    "对象存储系统（类 S3）",

    # P2P / 去中心化
    "BitTorrent P2P 文件共享",
    "比特币区块链网络",
    "去中心化存储（IPFS）",
    "P2P 视频通话（WebRTC 信令系统）",
    "去中心化交易所（DEX）",
    "区块链智能合约平台（类 Ethereum）",

    # 游戏
    "多人在线游戏匹配系统（类王者荣耀）",
    "游戏排行榜系统",
    "游戏道具交易市场",
    "实时多人同步引擎（帧同步）",

    # 数据 / 分析 / AI
    "数据仓库系统（类 Snowflake）",
    "实时流处理系统（类 Flink）",
    "推荐系统",
    "广告投放系统（RTB 实时竞价）",
    "A/B 测试平台",
    "用户行为埋点分析系统",
    "机器学习特征平台（Feature Store）",

    # IoT / 特殊场景
    "智能家居控制系统",
    "物联网数据采集平台",
    "车联网（V2X）系统",

    # 其他高频场景
    "知乎问答平台",
    "在线教育平台（类 Coursera）",
    "医疗预约挂号系统",
    "Gmail 电子邮件系统",
    "Google Calendar 日历系统",
    "密码管理器（类 1Password）",
    "网络爬虫系统",
]


def get_system_for_day(day_index: int) -> str:
    """day_index 从 1 开始，直接映射到 SYSTEMS 列表，100 天内完全无重复"""
    return SYSTEMS[day_index - 1]
