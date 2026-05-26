import os
import re
from config import QUESTIONS_DIR


def _slugify(name: str) -> str:
    name = re.sub(r"[（()）/、，。\s]+", "_", name)
    name = re.sub(r"[^\w一-鿿-]", "", name)
    return name.strip("_").lower()


def ensure_dir():
    os.makedirs(QUESTIONS_DIR, exist_ok=True)


def write_day_file(day_index: int, system_name: str, content: str) -> str:
    ensure_dir()
    slug = _slugify(system_name)
    filename = f"day_{day_index:03d}_{slug}.md"
    filepath = os.path.join(QUESTIONS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def write_placeholder(day_index: int, system_name: str, error: str) -> str:
    content = f"""# 第 {day_index} 天：设计 {system_name}

> 生成失败，错误信息：{error}

待补充。
"""
    return write_day_file(day_index, system_name, content)
