import requests
import time
from config import OLLAMA_HOST, MODEL, REQUEST_TIMEOUT, MAX_RETRIES

QUESTION_PROMPT = """你是一位资深系统设计面试官，请为以下系统出一道完整的系统设计面试题：

系统：{system_name}

要求：
1. **题目背景**：简要介绍该系统是什么、用途是什么（2-3句话）
2. **面试场景设定**：模拟真实面试开场白，面试官提出核心问题
3. **功能性需求**：列出 4-6 个核心功能需求（用户能做什么）
4. **非功能性需求**：列出 4-5 个关键指标（如 DAU、QPS、延迟、可用性、存储量），给出具体数字估算
5. **系统边界**：明确说明哪些功能在本题范围内，哪些不考虑
6. **提示与追问**：给出 2-3 个面试官可能深入追问的问题

请用 Markdown 格式输出，语言为中文，结构清晰，适合贴入 GitHub 的 .md 文件。
只输出题目内容本身，不要加任何前言或解释。"""

SOLUTION_PROMPT = """你是一位耐心的系统设计导师，正在辅导一位刚入行的后端初学者。
请针对以下系统设计题目，给出一份极其详细、由浅入深、完整的解题过程。

---题目开始---
{question_markdown}
---题目结束---

解答要求：
1. **面向读者**：假设读者是完全没做过系统设计的新手，不要跳步骤，每个决策都要解释原因
2. **结构层次**：从最小可用系统出发，逐步演进到高可用分布式架构
3. **每一步都要解释为什么**：不只说做什么，要说为什么这样做，以及不这样做会有什么问题
4. **必须包含以下章节**（使用 Markdown ## 二级标题）：
   - ## 解题思路总览
   - ## 第一步：理解需求与规模估算
   - ## 第二步：高层架构设计
   - ## 第三步：数据库设计
   - ## 第四步：核心 API 设计
   - ## 第五步：详细组件设计
   - ## 第六步：扩展性与高可用设计
   - ## 第七步：常见面试追问与回答
   - ## 心得与反思
5. **心得与反思章节**必须包含：
   - 本题最难的 1-2 个设计决策及思考过程
   - 新手最容易犯的错误（至少2个）
   - 学习建议和可延伸的方向
6. 语言：全中文，语气亲切，像在手把手教学
7. 格式：完整 Markdown，标题层次清晰，重要概念加粗，代码/表格/列表灵活运用

请开始解答，只输出解答内容本身："""


def _call_ollama(prompt: str) -> str:
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"    重试 {attempt + 1}/{MAX_RETRIES}：{e}")
                time.sleep(5)
            else:
                raise RuntimeError(f"Ollama 调用失败：{e}")


def generate_question(system_name: str) -> str:
    prompt = QUESTION_PROMPT.format(system_name=system_name)
    return _call_ollama(prompt)


def generate_solution(question_md: str) -> str:
    prompt = SOLUTION_PROMPT.format(question_markdown=question_md)
    return _call_ollama(prompt)


def generate_full(system_name: str, day_index: int) -> str:
    print(f"    → 第一轮：生成题目...")
    question = generate_question(system_name)

    print(f"    → 第二轮：生成题解...")
    solution = generate_solution(question)

    from datetime import date, timedelta
    today = date(2026, 5, 25)
    day_date = today - timedelta(days=day_index - 1)

    content = f"""# 第 {day_index} 天：设计 {system_name}

> 生成日期：{day_date.strftime('%Y-%m-%d')}

---

{question}

---

# 题解

{solution}
"""
    return content
