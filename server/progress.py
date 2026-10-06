"""生成任务的剩余时间估算:用最近完成任务的耗时中位数,结合当前进度。纯函数,便于测试。"""
import datetime as _dt
import statistics

# 没有历史时的保守估计:本机 turbo + 0.6B LM 稳态一首约 4–7 分钟
DEFAULT_JOB_SECONDS = 360


def typical_seconds(durations: list[float]) -> float:
    return statistics.median(durations) if durations else DEFAULT_JOB_SECONDS


def _elapsed(started_at: str | None, now: _dt.datetime) -> float:
    if not started_at:
        return 0.0
    try:
        return max(0.0, (now - _dt.datetime.fromisoformat(started_at)).total_seconds())
    except ValueError:
        return 0.0


def with_eta(jobs: list[dict], *, typical: float, now: _dt.datetime | None = None) -> list[dict]:
    """给按提交顺序排列的活跃任务加 eta_seconds。队列是串行的,排队任务要等前面的跑完。"""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    ahead = 0.0          # 前面所有任务还需要的秒数
    out = []
    for job in jobs:
        if job.get("status") == "running":
            p = job.get("progress")
            remain = (typical * (1 - p) if p
                      else typical - _elapsed(job.get("started_at"), now))
        else:
            remain = typical
        remain = max(0.0, remain)
        ahead += remain
        out.append({**job, "eta_seconds": int(round(ahead))})
    return out
