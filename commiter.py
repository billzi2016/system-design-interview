import subprocess
import random
import os
from datetime import date, timedelta

TODAY = date(2026, 5, 25)


def _random_time() -> str:
    hour = random.randint(9, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    if hour == 23:
        minute = random.randint(0, 30)
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def get_commit_date(day_index: int) -> date:
    return TODAY - timedelta(days=day_index - 1)


def commit_day(day_index: int, system_name: str, filepath: str):
    commit_date = get_commit_date(day_index)
    time_str = _random_time()
    datetime_str = f"{commit_date.isoformat()}T{time_str}"

    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = datetime_str
    env["GIT_COMMITTER_DATE"] = datetime_str

    subprocess.run(["git", "add", filepath], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"day {day_index}: 系统设计 - {system_name}"],
        check=True,
        env=env,
    )


def ensure_git_init():
    if not os.path.exists(".git"):
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "checkout", "-b", "main"], check=True)
