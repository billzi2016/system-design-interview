# System Design Interview — 每日一题生成器

用本地大模型（`gpt-oss:120b` via Ollama）自动生成系统设计面试题 + 完整题解，并通过 Git 历史时间戳模拟 100 天连续刷题记录。

## 效果

- `questions/` 目录下 100 个 Markdown 文件，每个对应一个独立系统（Discord、Kafka、BitTorrent……共 100 个，零重复）
- 每题包含：题目背景、需求分析、高层架构、数据库设计、API 设计、扩展方案、追问回答、**心得与反思**
- `git log` 呈现过去 100 天的提交记录，每天随机时间点，贡献图全绿

## 快速开始

**前提**：远程机器 `10.54.79.119` 已运行 Ollama 并加载 `gpt-oss:120b`。

```bash
# 测试连通性
python test_remote_ollama.py

# 生成全部 100 天（约 6-10 小时）
python main.py

# 只生成指定区间（断点续跑）
python main.py 1 10    # 生成第 1 到第 10 天
python main.py 50 60   # 生成第 50 到第 60 天
```

## 文件结构

```
.
├── main.py              # 入口
├── generator.py         # 两轮 Ollama API 调用
├── systems.py           # 100 个系统列表
├── file_writer.py       # 写入 questions/*.md
├── commiter.py          # Git 历史时间戳提交
├── config.py            # Ollama 地址、模型、超时等配置
├── test_remote_ollama.py
├── pyproject.toml
├── Dockerfile
└── questions/           # 自动生成
    ├── day_001_discord.md
    ├── day_002_whatsapp.md
    └── ...
```

## 配置

编辑 `config.py`：

```python
OLLAMA_HOST = "http://10.54.79.119:11434"  # 远程 Ollama 地址
MODEL       = "gpt-oss:120b"               # 模型名
DAYS        = 100
REQUEST_TIMEOUT = 300                       # 单次请求超时（秒）
MAX_RETRIES     = 2
```

## Docker 运行

```bash
docker build -t sd-interview .
docker run --rm -v $(pwd)/questions:/app/questions sd-interview
```

## 题目涵盖系统

社交通讯 · 视频音频 · 云存储 · 搜索 · 电商支付 · 出行地图 · 协同办公 · 分布式基础设施 · P2P/去中心化 · 游戏 · 数据分析 · IoT · 更多场景

完整列表见 [systems.py](systems.py) 或 [PRD.md](PRD.md)。

## 依赖

- Python 3.10+
- `requests`
- Git
