import sys
from config import DAYS
from systems import get_system_for_day
from generator import generate_full
from file_writer import write_day_file, write_placeholder
from commiter import ensure_git_init, commit_day


def run(start_day: int = 1, end_day: int = DAYS):
    ensure_git_init()

    # 从最远的过去往今天提交，保证 git log 时间线正确
    for day in range(end_day, start_day - 1, -1):
        system = get_system_for_day(day)
        print(f"[{end_day - day + 1}/{end_day - start_day + 1}] 正在生成第 {day} 天：{system}")

        try:
            content = generate_full(system, day)
            filepath = write_day_file(day, system, content)
        except Exception as e:
            print(f"    ✗ 生成失败：{e}，写入占位文件")
            filepath = write_placeholder(day, system, str(e))

        try:
            commit_day(day, system, filepath)
            print(f"    ✓ 已提交：{filepath}")
        except Exception as e:
            print(f"    ✗ 提交失败：{e}")

    print("\n全部完成！")


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else DAYS
    run(start, end)
