"""gVisor sandbox runner with a Redis-locked slot pool.

Untrusted student code runs inside ``--runtime=runsc`` containers on the
gVisor-enabled engine (WSL2 Ubuntu native docker here; plain docker on Linux).
Hard limits regardless of runtime: no network, 256MB memory, 1 CPU, 64 pids,
read-only rootfs with tmpfs /tmp, non-root user, and an external wall-clock
kill. The host never executes student code directly: files are staged into an
exchange directory, the in-container harness does the running.

Every run persists a ``grading.sandbox_runs`` row with stdout/stderr in MinIO
``sandbox-logs/<run_id>/``.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import structlog

from autograde_core.config import get_settings

log = structlog.get_logger()

_RESULT_MARKER = "RESULTS_JSON:"

# Runs inside the container. Reads /work/tests.json, execs /work/student.py in
# a namespace (with the rubric's prelude), evaluates each case expression, and
# prints one marker line of results JSON.
HARNESS = r'''
import json, sys, traceback

spec = json.load(open("/work/tests.json"))
ns = {}
try:
    exec(spec.get("prelude", ""), ns)
    exec(open("/work/student.py").read(), ns)
except Exception:
    print(json.dumps({"fatal": traceback.format_exc(limit=3)}))
    sys.exit(3)

results = []
for case in spec["cases"]:
    entry = {"id": case["id"], "ok": False, "result": None, "error": None}
    try:
        value = eval(case["expr"], ns)  # noqa: S307 - sandboxed by design
        entry["result"] = repr(value)
        entry["ok"] = value == case["expected"]
    except Exception as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
    results.append(entry)

print("RESULTS_JSON:" + json.dumps(results))
'''


@dataclass
class SandboxResult:
    run_id: uuid.UUID
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    case_results: list[dict]
    fatal_error: str | None
    stdout_ref: str
    stderr_ref: str


class SandboxPool:
    """Redis-locked slots capping concurrent sandbox containers."""

    def __init__(self, size: int | None = None) -> None:
        self.size = size or get_settings().sandbox_pool_size

    def acquire(self, timeout_s: float = 60.0) -> tuple[str, object]:
        from autograde_rag.cache import get_redis

        redis = get_redis()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for slot in range(self.size):
                key = f"sandbox_lock:{slot}"
                token = str(uuid.uuid4())
                if redis.set(key, token, nx=True, ex=120):
                    return key, token
            time.sleep(0.25)
        raise TimeoutError("no sandbox slot available")

    def release(self, key: str, token: object) -> None:
        from autograde_rag.cache import get_redis

        redis = get_redis()
        if redis.get(key) == token:  # only the holder releases
            redis.delete(key)


def _stage(run_id: uuid.UUID, student_source: str, tests: dict) -> str:
    """Write student.py/tests.json/harness.py into the exchange dir. Returns linux path."""
    settings = get_settings()
    win_dir = Path(settings.sandbox_exchange_win) / str(run_id)
    win_dir.mkdir(parents=True, exist_ok=True)
    (win_dir / "student.py").write_text(student_source, encoding="utf-8", newline="\n")
    (win_dir / "tests.json").write_text(json.dumps(tests), encoding="utf-8", newline="\n")
    (win_dir / "harness.py").write_text(HARNESS, encoding="utf-8", newline="\n")
    return f"{settings.sandbox_exchange_linux}/{run_id}"


def run_sandboxed(
    *,
    submission_id: uuid.UUID,
    test_case_id: str,
    student_source: str,
    tests: dict,
    timeout_s: int | None = None,
) -> SandboxResult:
    """Execute one sandbox run (all cases of one question) under the pool."""
    settings = get_settings()
    run_id = uuid.uuid4()
    timeout_s = timeout_s or settings.sandbox_timeout_s
    linux_dir = _stage(run_id, student_source, tests)
    container = f"autograde-sbx-{run_id.hex[:12]}"

    cmd = [
        *shlex.split(settings.sandbox_docker_cmd),
        "run",
        "--rm",
        "--name", container,
        f"--runtime={settings.sandbox_runtime}",
        "--network", "none",
        "--memory", "256m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--read-only",
        "--tmpfs", "/tmp:size=16m",
        "--user", "65534:65534",  # nobody
        "-v", f"{linux_dir}:/work:ro",
        settings.sandbox_image,
        "python", "/work/harness.py",
    ]

    pool = SandboxPool()
    slot, token = pool.acquire()
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s + 20  # +container startup
        )
        exit_code: int | None = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        subprocess.run(
            [*shlex.split(settings.sandbox_docker_cmd), "kill", container],
            capture_output=True, timeout=30,
        )
    finally:
        pool.release(slot, token)
    duration_ms = int((time.monotonic() - started) * 1000)

    case_results: list[dict] = []
    fatal_error: str | None = None
    for line in stdout.splitlines():
        if line.startswith(_RESULT_MARKER):
            case_results = json.loads(line[len(_RESULT_MARKER):])
        elif line.startswith('{"fatal"'):
            fatal_error = json.loads(line)["fatal"]
    if timed_out:
        fatal_error = fatal_error or f"wall-clock timeout after {timeout_s}s (container killed)"

    stdout_ref, stderr_ref = _persist(
        run_id, submission_id, test_case_id, exit_code, timed_out, duration_ms, stdout, stderr
    )
    log.info(
        "sandbox_run",
        run_id=str(run_id),
        exit_code=exit_code,
        timed_out=timed_out,
        cases=len(case_results),
        duration_ms=duration_ms,
    )
    return SandboxResult(
        run_id=run_id,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        case_results=case_results,
        fatal_error=fatal_error,
        stdout_ref=stdout_ref,
        stderr_ref=stderr_ref,
    )


def _persist(
    run_id: uuid.UUID,
    submission_id: uuid.UUID,
    test_case_id: str,
    exit_code: int | None,
    timed_out: bool,
    duration_ms: int,
    stdout: str,
    stderr: str,
) -> tuple[str, str]:
    from autograde_core import storage
    from autograde_db.models import SandboxRun
    from autograde_db.session import session_scope

    stdout_ref = f"{run_id}/stdout.log"
    stderr_ref = f"{run_id}/stderr.log"
    storage.put_bytes("sandbox-logs", stdout_ref, stdout.encode(), "text/plain")
    storage.put_bytes("sandbox-logs", stderr_ref, stderr.encode(), "text/plain")
    with session_scope() as session:
        session.add(
            SandboxRun(
                id=run_id,
                submission_id=submission_id,
                test_case_id=test_case_id,
                exit_code=exit_code,
                stdout_ref=stdout_ref,
                stderr_ref=stderr_ref,
                duration_ms=duration_ms,
                timed_out=timed_out,
            )
        )
    return stdout_ref, stderr_ref
