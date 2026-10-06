import datetime as dt

from server.progress import DEFAULT_JOB_SECONDS, typical_seconds, with_eta

NOW = dt.datetime(2026, 10, 6, 12, 0, 0, tzinfo=dt.timezone.utc)


def _ago(sec):
    return (NOW - dt.timedelta(seconds=sec)).isoformat()


def test_typical_seconds_is_median_or_default():
    assert typical_seconds([]) == DEFAULT_JOB_SECONDS
    assert typical_seconds([100, 300, 200]) == 200


def test_running_eta_uses_progress_and_queued_stack_behind():
    jobs = [
        {"job_id": "r", "status": "running", "progress": 0.75, "started_at": _ago(90)},
        {"job_id": "q1", "status": "queued", "progress": None, "started_at": None},
        {"job_id": "q2", "status": "queued", "progress": None, "started_at": None},
    ]
    out = with_eta(jobs, typical=400, now=NOW)
    assert out[0]["eta_seconds"] == 100                 # 400 × (1 − 0.75)
    assert out[1]["eta_seconds"] == 100 + 400           # 等前一首跑完,再跑自己
    assert out[2]["eta_seconds"] == 100 + 800


def test_running_without_progress_falls_back_to_elapsed():
    jobs = [{"job_id": "r", "status": "running", "progress": None, "started_at": _ago(150)}]
    assert with_eta(jobs, typical=400, now=NOW)[0]["eta_seconds"] == 250


def test_overrun_job_never_negative():
    jobs = [{"job_id": "r", "status": "running", "progress": None, "started_at": _ago(900)}]
    assert with_eta(jobs, typical=400, now=NOW)[0]["eta_seconds"] == 0
