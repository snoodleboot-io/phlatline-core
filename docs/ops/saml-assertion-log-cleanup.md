# SAML assertion log cleanup

## What the job does and why it exists

Every SAML assertion Phlatline processes is recorded in the `saml_assertion_log` table with an `expires_at` timestamp. This is replay prevention: if an attacker replays a captured SAML response, Phlatline detects the duplicate assertion ID and rejects it. Assertions are logged for the duration of their validity window (typically a few minutes) plus a safety buffer.

Without cleanup, `saml_assertion_log` grows indefinitely. The rows are worthless once `expires_at` has passed — a replay of an expired assertion would be rejected by the SAML library's `NotOnOrAfter` check before the log is consulted.

The cleanup job runs `DELETE FROM saml_assertion_log WHERE expires_at < now()` on a scheduled interval using APScheduler's `AsyncIOScheduler`. It runs inside the existing asyncio event loop and requires no external infrastructure.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SAML_LOG_CLEANUP_INTERVAL_MINUTES` | `15` | How often the cleanup job runs, in minutes. |

Set a lower value (e.g. `1`) in development or load-testing environments where you want faster cleanup. The minimum effective value is `1`.

---

## Verifying the job is running

APScheduler logs at `INFO` level when the scheduler starts and when a job executes. In your log stream, look for:

```
INFO  apscheduler.scheduler - Added job "clean_expired_assertion_logs" to job store "default"
INFO  apscheduler.scheduler - Scheduler started
INFO  apscheduler.executors.default - Running job "clean_expired_assertion_logs" (scheduled at ...)
```

The first two lines appear at application startup. The third line appears every `SAML_LOG_CLEANUP_INTERVAL_MINUTES` minutes as long as SSO is configured.

The job function also logs the number of rows deleted:

```
[SAML_CLEANUP] deleted <n> expired assertion log rows
```

If `n` is consistently zero after the first few intervals, the table is staying clean. If `n` is large and growing, either the interval is too long or SAML traffic volume is unusually high.

---

## Multi-worker deployments

!!! warning "MVP recommendation: run with `--workers 1`"
    APScheduler's `AsyncIOScheduler` is in-process. If the app runs with multiple Uvicorn workers (`uvicorn --workers N`), each worker starts its own scheduler instance. The cleanup job will run N times per interval — one delete per worker.

    This is **safe** (the DELETE is idempotent — rows deleted by worker 1 are simply not found by workers 2 through N), but it wastes database connections and produces redundant log lines.

    At MVP, run with `--workers 1`. If you need horizontal scale, either move to a dedicated job runner in a future story or add a distributed lock (e.g. Postgres advisory lock) around the cleanup function.

---

## How replay prevention still works after cleanup

Cleanup removes only **expired** assertions — rows where `expires_at < now()`. An assertion is expired only after its SAML validity window has passed. Within that window, the row remains in the log and any replay is detected and rejected.

Timeline:

1. Assertion issued with `NotOnOrAfter = T+5m`.
2. Phlatline records the assertion ID with `expires_at = T+5m`.
3. At `T+3m`, an attacker replays the assertion. Phlatline finds the ID in `saml_assertion_log` and rejects it.
4. At `T+6m`, the assertion ID is expired. The next cleanup run deletes it.
5. At `T+7m`, an attacker replays the same assertion. The SAML library rejects it at `NotOnOrAfter` validation — the assertion is temporally invalid regardless of the log state.

Cleanup does not create a replay window. The SAML `NotOnOrAfter` check is the first line of defense; the assertion log is a defense-in-depth measure for assertions that are temporally valid but have already been consumed.
