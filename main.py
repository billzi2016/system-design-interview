import sys
import time
from datetime import timedelta
from config import DAYS
from systems import get_system_for_day
from generator import generate_full
from file_writer import write_day_file, write_placeholder
from commiter import ensure_git_init, commit_day


def fmt_duration(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds + td.days * 86400, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def run(start_day: int = 1, end_day: int = DAYS):
    ensure_git_init()

    total = end_day - start_day + 1
    done = 0
    durations = []
    session_start = time.time()

    for day in range(start_day, end_day + 1):
        done += 1
        system = get_system_for_day(day)

        avg = (sum(durations) / len(durations)) if durations else 0
        eta_str = fmt_duration(avg * (total - done + 1)) if durations else "计算中..."
        elapsed_str = fmt_duration(time.time() - session_start)

        print(f"\n[{done}/{total}] 第 {day} 天：{system}")
        print(f"  已用 {elapsed_str}  |  ETA {eta_str}")

        t0 = time.time()
        try:
            content = generate_full(system, day)
            filepath = write_day_file(day, system, content)
        except Exception as e:
            print(f"  ✗ 生成失败：{e}，写入占位文件")
            filepath = write_placeholder(day, system, str(e))

        try:
            commit_day(day, system, filepath)
        except Exception as e:
            print(f"  ✗ 提交失败：{e}")

        elapsed = time.time() - t0
        durations.append(elapsed)
        avg = sum(durations) / len(durations)
        remaining = total - done
        print(f"  ✓ 完成，耗时 {fmt_duration(elapsed)}  |  均值 {fmt_duration(avg)}  |  剩余 {remaining} 题，预计还需 {fmt_duration(avg * remaining)}")

    total_time = time.time() - session_start
    print(f"\n全部完成！总耗时 {fmt_duration(total_time)}，共 {total} 题，均值 {fmt_duration(sum(durations)/len(durations))}/题")


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else DAYS
    run(start, end)
