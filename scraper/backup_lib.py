"""
Tieba batch backup — shared library.
Provides logging, process locking, integrity checks, monkey-patch, and batch download loop.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import orjson
from modules.scrape_module import scrape
from scrape_config import ScrapeConfig
from tieba_auth import TiebaAuth
from config.path_config import ScrapeDataPathBuilder, sanitize_filename
from api.aiotieba_client import ThreadUnavailable, FetchIncomplete

BACKOFF_INITIAL = 30
BACKOFF_MAX = 300
MAX_RETRIES_PER_TID = 3
# Intra-thread resume retries: when a thread comes back FetchIncomplete, retry it
# within the same pass (each round resumes from the page checkpoint). Keep going
# while new posts are still being saved; give up only after this many consecutive
# rounds add nothing (i.e. the remaining pages are genuinely gone, not throttled).
INCOMPLETE_STALE_LIMIT = 3
INCOMPLETE_MAX_ROUNDS = 300  # absolute safety cap on resume rounds per pass
IDLE_TIMEOUT = 360  # seconds: cancel task if no file writes. Must stay above
                    # BACKOFF_MAX (300s) so a single huge thread sitting in a long
                    # 429 backoff is not killed mid-flight by the watchdog.


# ── Logging (one file per session, captures all stdout/stderr) ──
class _TeeWriter:
    """Writes to both the original stream and a log file, capturing print output from TiebaArchiver."""

    def __init__(self, original_stream, log_file):
        self.original = original_stream
        self.log_file = log_file

    def write(self, msg):
        if msg and msg.strip():
            clean = _strip_ansi(msg)
            self.log_file.write(clean)
            if not clean.endswith("\n"):
                self.log_file.write("\n")
            self.log_file.flush()
        self.original.write(msg)
        self.original.flush()

    def flush(self):
        self.original.flush()
        self.log_file.flush()

    def fileno(self):
        return self.original.fileno()

    def isatty(self):
        return self.original.isatty()


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


_log_file_handle = None


def setup_logging(output_dir: str, prefix: str = "backup") -> str:
    global _log_file_handle

    log_dir = os.path.join(output_dir, "_logs")
    os.makedirs(log_dir, exist_ok=True)
    session_ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"{prefix}_{session_ts}.log")

    _log_file_handle = open(log_path, "a", encoding="utf-8")
    sys.stdout = _TeeWriter(sys.__stdout__, _log_file_handle)
    sys.stderr = _TeeWriter(sys.__stderr__, _log_file_handle)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Log file: {log_path}", flush=True)
    return log_path


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── Process lock ──────────────────────────────────────────────
def acquire_lock(output_dir: str):
    lock_file = os.path.join(output_dir, "_backup.lock")
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(old_pid):
                log(f"[ABORT] Another backup process is already running (PID {old_pid}), exiting.")
                sys.exit(1)
        except (ImportError, ValueError):
            pass
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))
    return lock_file


def release_lock(lock_file: str):
    try:
        os.remove(lock_file)
    except OSError:
        pass


# ── Read BDUSS ────────────────────────────────────────────────
def read_bduss() -> str:
    auth_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tieba_auth.json")
    if not os.path.exists(auth_path):
        log(f"[ERROR] {auth_path} not found")
        log("Please create tieba_auth.json with content: {\"BDUSS\": \"your_BDUSS\"}")
        sys.exit(1)
    with open(auth_path, "r", encoding="utf-8") as f:
        data = orjson.loads(f.read())
    bduss = data.get("BDUSS", "")
    if not bduss:
        log("[ERROR] BDUSS is empty in tieba_auth.json")
        sys.exit(1)
    return bduss


# ── Monkey-patch: idempotent folder names (no timestamp) ─────
def _make_idempotent_builder(cls, forum_name: str, tid: int, title: str):
    safe_title = re.sub(r'[\x00-\x1f\x7f]', '', title)
    safe_title = sanitize_filename(safe_title)[:80]
    if not safe_title:
        safe_title = "untitled"
    folder_name = f"[{forum_name}吧][{tid}]{safe_title}"
    item_dir = os.path.join(cls.DATA_FOLDER_NAME, folder_name)
    os.makedirs(item_dir, exist_ok=True)
    return ScrapeDataPathBuilder(item_dir)


def apply_patches(output_dir: str):
    ScrapeDataPathBuilder.DATA_FOLDER_NAME = output_dir
    ScrapeDataPathBuilder.get_instance_scrape = classmethod(_make_idempotent_builder)


# ── Initialize TiebaArchiver ──────────────────────────────────
def init_archiver(output_dir: str, bduss: str | None = None):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if bduss:
        TiebaAuth.from_dict({"BDUSS": bduss})
    else:
        auth_path = os.path.join(os.path.dirname(__file__), "tieba_auth.json")
        if not os.path.exists(auth_path):
            log(f"[ERROR] {auth_path} not found and no BDUSS provided")
            sys.exit(1)
        with open(auth_path, "r", encoding="utf-8") as f:
            TiebaAuth.from_dict(orjson.loads(f.read()))

    config_path = os.path.join(os.path.dirname(__file__), "scrape_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            ScrapeConfig.from_dict(orjson.loads(f.read()))

    apply_patches(output_dir)
    log(f"[OK] Initialization complete, output dir: {output_dir}")


async def verify_bduss():
    """Quick BDUSS validity check — fetch a known forum. Exit if invalid."""
    import aiotieba as tb
    log("[CHECK] Verifying BDUSS ...")
    try:
        async with tb.Client(TiebaAuth.BDUSS) as client:
            forum = await client.get_forum("贴吧")
            if forum and forum.fid != 0:
                log(f"[OK] BDUSS valid (test forum fid={forum.fid})")
                return
    except Exception as e:
        log(f"[ERROR] BDUSS check failed: {e}")
    log("[ERROR] BDUSS is invalid or expired. Please update tieba_auth.json")
    sys.exit(1)


# ── Integrity check ───────────────────────────────────────────
def _load_done_tids(output_dir: str) -> set[int]:
    """Load confirmed-done tids from _done_tids.json (authoritative source)."""
    done_file = os.path.join(output_dir, "_done_tids.json")
    if os.path.exists(done_file):
        with open(done_file, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_done_tids(output_dir: str, done_set: set[int]):
    done_file = os.path.join(output_dir, "_done_tids.json")
    with open(done_file, "w", encoding="utf-8") as f:
        json.dump(sorted(done_set), f)


def scan_completed_tids(output_dir: str) -> set[int]:
    """
    Fast path: load _done_tids.json as the authoritative record.
    First-run migration (no _done_tids.json): scan folders to build the set.
    """
    done_file = os.path.join(output_dir, "_done_tids.json")
    done_set = _load_done_tids(output_dir)

    if not os.path.exists(output_dir):
        return done_set

    if os.path.exists(done_file):
        log(f"[OK] Loaded {len(done_set)} confirmed done from _done_tids.json")
        return done_set

    # First-run migration: scan folders to build _done_tids.json
    tid_re = re.compile(r"\[(\d+)\]")
    log(f"[MIGRATE] No _done_tids.json — scanning folders to build it ...")
    all_dirs = [n for n in os.listdir(output_dir)
                if os.path.isdir(os.path.join(output_dir, n)) and not n.startswith("_")]
    total_dirs = len(all_dirs)

    for idx, name in enumerate(all_dirs):
        full_path = os.path.join(output_dir, name)
        m = tid_re.search(name)
        if not m:
            continue
        tid = int(m.group(1))
        db_path = os.path.join(full_path, "threads", str(tid), "content.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                count = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
                conn.close()
                if count > 0:
                    done_set.add(tid)
            except Exception:
                pass
        if (idx + 1) % 500 == 0:
            log(f"  ... checked {idx+1}/{total_dirs}, confirmed {len(done_set)} done")

    _save_done_tids(output_dir, done_set)
    log(f"[MIGRATE] Done: {len(done_set)} confirmed tids")

    return done_set


def cleanup_incomplete_tid(output_dir: str, tid: int):
    """Remove leftover folder for a single tid before re-scraping it."""
    marker = f"[{tid}]"
    try:
        for name in os.listdir(output_dir):
            if marker in name and os.path.isdir(os.path.join(output_dir, name)):
                shutil.rmtree(os.path.join(output_dir, name), ignore_errors=True)
                return True
    except OSError:
        pass
    return False


# ── Progress file ─────────────────────────────────────────────
def load_progress_sets(output_dir: str) -> tuple[set[int], dict[int, str]]:
    """Return (deleted_set, failed_dict)."""
    progress_file = os.path.join(output_dir, "_progress.json")
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        deleted = set(data.get("deleted", []))
        failed = {int(k): v for k, v in data.get("failed_details", {}).items()}
        return deleted, failed
    return set(), {}


def save_progress(output_dir: str, deleted_set: set[int], failed_dict: dict[int, str], stats: dict):
    progress_file = os.path.join(output_dir, "_progress.json")
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "deleted": sorted(deleted_set),
                "failed_details": {str(k): v for k, v in sorted(failed_dict.items())},
                "stats": stats,
            },
            f, ensure_ascii=False, indent=2,
        )


# ── Load tids from _all_tids.json ─────────────────────────────
def load_tids_from_cache(output_dir: str) -> list[int] | None:
    cache_file = os.path.join(output_dir, "_all_tids.json")
    if not os.path.exists(cache_file):
        return None
    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], dict):
            if "all_tids" in data[0]:
                return data[0]["all_tids"]
            return [item["tid"] for item in data]
        return data
    if isinstance(data, dict) and "all_tids" in data:
        return data["all_tids"]
    return None


def save_tids_cache(output_dir: str, all_tids: list[int], extra: dict | None = None):
    cache_file = os.path.join(output_dir, "_all_tids.json")
    payload = {"all_tids": all_tids, "collected_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if extra:
        payload.update(extra)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ── Idle-timeout watchdog ─────────────────────────────────────
def _latest_mtime_for_tid(output_dir: str, tid: int) -> float:
    """Return newest mtime of any file inside this tid's scrape folder, or 0."""
    marker = f"[{tid}]"
    try:
        entries = os.listdir(output_dir)
    except OSError:
        return 0.0
    for name in entries:
        if marker not in name:
            continue
        tid_dir = os.path.join(output_dir, name)
        if not os.path.isdir(tid_dir):
            continue
        best = 0.0
        for root, _, files in os.walk(tid_dir):
            for f in files:
                try:
                    mt = os.path.getmtime(os.path.join(root, f))
                    if mt > best:
                        best = mt
                except OSError:
                    pass
        return best
    return 0.0


async def _scrape_with_watchdog(tid: int, output_dir: str):
    """Run scrape(tid); cancel only if no file-system activity for IDLE_TIMEOUT seconds.
    Large threads can run arbitrarily long as long as files keep being written."""
    task = asyncio.create_task(scrape(tid))
    last_activity = time.time()

    while not task.done():
        done, _ = await asyncio.wait({task}, timeout=20)
        if done:
            break

        mt = _latest_mtime_for_tid(output_dir, tid)
        if mt > last_activity:
            last_activity = mt
        elif time.time() - last_activity > IDLE_TIMEOUT:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise asyncio.TimeoutError(f"no file activity for {IDLE_TIMEOUT}s")

    return task.result()


# ── Batch download main loop (concurrent + throughput-seeking autotune) ──
DEFAULT_CONCURRENCY = 10
# Throughput-seeking concurrency controller (hill climbing on goodput).
# Goal: maximize completed-threads-per-second, NOT minimize 429s. Running a bit
# "over the water line" (tolerating some 429s) is fine as long as the net
# completion rate is higher. The controller nudges concurrency up while that
# helps and only backs off when more concurrency clearly hurts throughput.
CONTROL_WINDOW = 90      # seconds between concurrency decisions
EWMA_ALPHA = 0.5         # smoothing on measured goodput (dampens thread-size noise)
GOODPUT_MARGIN = 0.10    # only step down when goodput clearly drops (>10%)
PAUSE_ON_429 = 8         # short coordinated cool-down to avoid a 429 thundering herd
MIN_CONCURRENCY_DIVISOR = 3  # never autotune below ~max/3: the goodput signal goes
                             # blind on giant threads (one thread > one window), and
                             # collapsing to 1 would serialize the whole tail behind
                             # a single mega-thread. Keep enough parallelism to overlap.


class DynamicSemaphore:
    """A semaphore whose limit can change at runtime.

    Unlike swapping out an ``asyncio.Semaphore`` object, this keeps a single
    shared counter, so lowering the limit after a 429 actually throttles new
    acquisitions while in-flight holders are allowed to finish (never preempted).
    """

    def __init__(self, limit: int):
        self._limit = max(1, limit)
        self._active = 0
        self._cond = asyncio.Condition()

    @property
    def limit(self) -> int:
        return self._limit

    async def acquire(self):
        async with self._cond:
            while self._active >= self._limit:
                await self._cond.wait()
            self._active += 1

    async def release(self):
        async with self._cond:
            self._active = max(0, self._active - 1)
            self._cond.notify_all()

    async def set_limit(self, new_limit: int):
        new_limit = max(1, new_limit)
        async with self._cond:
            self._limit = new_limit
            self._cond.notify_all()  # wake waiters in case the limit increased

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *exc):
        await self.release()


async def batch_download(all_tids: list[int], output_dir: str, max_concurrency: int = DEFAULT_CONCURRENCY):
    completed_set = scan_completed_tids(output_dir)
    deleted_set, failed_dict = load_progress_sets(output_dir)
    skip_set = completed_set | deleted_set

    failed_set = set(failed_dict.keys())
    fresh = [tid for tid in all_tids if tid not in skip_set and tid not in failed_set]
    retries = [tid for tid in all_tids if tid in failed_set and tid not in skip_set]
    remaining = fresh + retries
    total = len(all_tids)

    log(f"{'='*60}")
    log(f"Total: {total} | Done: {len(completed_set)} | Deleted: {len(deleted_set)} | Failed(retry): {len(retries)} | Fresh: {len(fresh)}")
    log(f"Concurrency: {max_concurrency} | Output: {output_dir}")
    log(f"{'='*60}")

    if not remaining:
        log("No pending threads to process, exiting.")
        return

    # shared state
    success_count = 0
    fail_count = 0
    processed_count = 0
    start_time = time.time()

    # ── throughput-seeking concurrency controller (hill climbing) ──
    # current_concurrency: effective in-flight limit right now.
    # The autotuner measures completed-threads-per-second each window and walks
    # concurrency toward the throughput peak. A 429 no longer caps concurrency;
    # it only triggers a brief coordinated pause. Concurrency is driven purely
    # by measured goodput, so the system happily runs over the water line when
    # that is genuinely faster, and backs off only when it stops paying off.
    # Start at full concurrency and let the autotuner pull back only if more
    # concurrency demonstrably hurts throughput. A hard floor keeps the tail
    # (giant threads) overlapping instead of serializing down to 1.
    min_concurrency = max(2, max_concurrency // MIN_CONCURRENCY_DIVISOR)
    current_concurrency = max_concurrency
    semaphore = DynamicSemaphore(current_concurrency)
    throttle_lock = asyncio.Lock()
    progress_lock = asyncio.Lock()
    last_429_time = 0.0
    global_paused = asyncio.Event()
    global_paused.set()  # initially not paused

    # hill-climbing state
    hc_last_success = 0
    hc_last_time = time.time()
    hc_prev_goodput = None   # previous (smoothed) goodput, threads/sec
    hc_direction = 1         # start by exploring upward

    async def adjust_concurrency(new_n: int, reason: str = ""):
        nonlocal current_concurrency
        new_n = max(min_concurrency, min(max_concurrency, new_n))
        if new_n == current_concurrency:
            return
        old = current_concurrency
        current_concurrency = new_n
        await semaphore.set_limit(new_n)
        log(f"  [AUTOTUNE] concurrency {old} -> {new_n} {reason}")

    async def handle_429(backoff_time: float):
        nonlocal last_429_time
        async with throttle_lock:
            now = time.time()
            if now - last_429_time < 5:
                return  # another worker already reacted to this burst
            last_429_time = now
            global_paused.clear()
        # Brief coordinated cool-down only; the autotuner owns concurrency.
        await asyncio.sleep(min(backoff_time, PAUSE_ON_429))
        global_paused.set()

    async def autotune():
        # Called periodically by the progress reporter; acts once per window.
        nonlocal hc_last_success, hc_last_time, hc_prev_goodput, hc_direction
        now = time.time()
        win = now - hc_last_time
        if win < CONTROL_WINDOW:
            return

        goodput = max(0.0, (success_count - hc_last_success) / win)  # threads/sec
        hc_last_success = success_count
        hc_last_time = now

        if hc_prev_goodput is None:
            smoothed = goodput
        else:
            smoothed = EWMA_ALPHA * goodput + (1 - EWMA_ALPHA) * hc_prev_goodput

        async with throttle_lock:
            if hc_prev_goodput is not None and hc_prev_goodput > 0:
                rel = (smoothed - hc_prev_goodput) / hc_prev_goodput
                # Push up while it helps or is roughly flat (over-the-line is OK);
                # step down only when more concurrency clearly hurt throughput.
                hc_direction = -1 if rel < -GOODPUT_MARGIN else 1
            else:
                hc_direction = 1
            await adjust_concurrency(
                current_concurrency + hc_direction,
                reason=f"[goodput {smoothed*3600:.0f}/h dir{hc_direction:+d}]",
            )
        hc_prev_goodput = smoothed

    def _count_posts(tid: int) -> int:
        """Number of posts stored so far for a tid (0 if none). Used as a
        progress signal to decide whether resume retries are still paying off."""
        tid_pattern = f"[{tid}]"
        try:
            for name in os.listdir(output_dir):
                if tid_pattern in name and os.path.isdir(os.path.join(output_dir, name)):
                    db_path = os.path.join(output_dir, name, "threads", str(tid), "content.db")
                    if os.path.exists(db_path):
                        conn = sqlite3.connect(db_path)
                        count = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
                        conn.close()
                        return count
        except Exception:
            pass
        return 0

    def _verify_scrape(tid: int) -> bool:
        """Check if scrape() actually completed (content.db exists and has data)."""
        return _count_posts(tid) > 0

    async def process_tid(tid: int):
        nonlocal success_count, fail_count, processed_count

        await global_paused.wait()
        async with semaphore:
            await global_paused.wait()

            # NOTE: do NOT wipe a partially-scraped thread here. The scraper now
            # resumes intra-thread from a per-page checkpoint, so keeping the
            # existing content.db lets a retry fetch only the missing pages
            # instead of re-downloading a huge thread from scratch.
            retries = 0
            backoff = BACKOFF_INITIAL
            incomplete_stale = 0       # consecutive resume rounds that added no posts
            incomplete_rounds = 0      # total resume rounds (absolute safety cap)
            last_post_count = _count_posts(tid)
            while retries < MAX_RETRIES_PER_TID:
                try:
                    await _scrape_with_watchdog(tid, output_dir)
                    if not _verify_scrape(tid):
                        # scrape() returned without raising but wrote no data.
                        # Treat as transient/incomplete (retryable) — NEVER as deleted.
                        raise FetchIncomplete(f"no data produced for tid={tid}")
                    async with progress_lock:
                        completed_set.add(tid)
                        _save_done_tids(output_dir, completed_set)
                        success_count += 1
                        failed_dict.pop(tid, None)
                    break
                except ThreadUnavailable as ua:
                    # Server positively confirmed the thread is gone. Only THIS
                    # marks a thread as deleted (permanent skip).
                    async with progress_lock:
                        deleted_set.add(tid)
                        failed_dict.pop(tid, None)
                    log(f"  [DELETED] tid={tid}: {str(ua)[:120]}")
                    break
                except FetchIncomplete as fi:
                    # Some pages were lost to rate limit / network. With intra-thread
                    # resume we retry right here: each round continues from the page
                    # checkpoint, so we only re-fetch the pages still missing. Keep
                    # going while new posts keep landing (a "fake" miss that just
                    # needs more passes); give up only when several rounds in a row
                    # add nothing — those pages are genuinely gone.
                    now_count = _count_posts(tid)
                    incomplete_rounds += 1
                    if now_count > last_post_count:
                        incomplete_stale = 0
                    else:
                        incomplete_stale += 1
                    last_post_count = now_count
                    if (incomplete_stale >= INCOMPLETE_STALE_LIMIT
                            or incomplete_rounds >= INCOMPLETE_MAX_ROUNDS):
                        async with progress_lock:
                            fail_count += 1
                            failed_dict[tid] = f"incomplete: {str(fi)[:180]}"
                        log(f"  [INCOMPLETE] tid={tid}: no new data after "
                            f"{incomplete_stale} resume rounds ({now_count} posts): "
                            f"{str(fi)[:90]} (giving up this pass)")
                        break
                    log(f"  [RESUME] tid={tid}: {str(fi)[:80]} -> continue from "
                        f"checkpoint (round {incomplete_rounds}, {now_count} posts)")
                    await asyncio.sleep(2)
                    continue
                except asyncio.TimeoutError as te:
                    elapsed = int(time.time() - start_time)
                    log(f"  [IDLE TIMEOUT] tid={tid}: {te} (wall {elapsed}s), will retry later")
                    async with progress_lock:
                        fail_count += 1
                        failed_dict[tid] = str(te)
                    break
                except Exception as e:
                    err = str(e)
                    if "429" in err or "Too Many Requests" in err:
                        retries += 1
                        await handle_429(backoff)
                        backoff = min(backoff * 2, BACKOFF_MAX)
                    else:
                        async with progress_lock:
                            fail_count += 1
                            failed_dict[tid] = err[:200]
                        log(f"  [FAILED] tid={tid}: {err[:100]} (will retry later)")
                        break
            else:
                async with progress_lock:
                    fail_count += 1
                    failed_dict[tid] = "max retries exceeded"
                log(f"  [GAVE UP] tid={tid}: max retries exceeded")

            async with progress_lock:
                processed_count += 1

    # progress reporter coroutine
    async def progress_reporter():
        while processed_count < len(remaining):
            await asyncio.sleep(10)
            elapsed = time.time() - start_time
            rate = success_count / elapsed * 3600 if elapsed > 0 and success_count > 0 else 0
            left = len(remaining) - processed_count
            eta_hrs = left / (rate / 3600) / 3600 if rate > 0 else 0
            done_total = len(completed_set) + len(deleted_set)
            log(
                f"[{done_total}/{total}] "
                f"ok:{success_count} fail:{fail_count} "
                f"speed:{rate:.0f}/h eta:{eta_hrs:.1f}h "
                f"concurrency:{current_concurrency}"
            )
            save_progress(output_dir, deleted_set, failed_dict, {
                "success": success_count,
                "failed": fail_count,
                "deleted": len(deleted_set),
                "completed_total": len(completed_set),
                "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            await autotune()

    # launch concurrent downloads
    reporter_task = asyncio.create_task(progress_reporter())

    # Continuously-refilled sliding window: keep a little more than the hard cap
    # in flight so the DynamicSemaphore is the *only* throttle. This avoids the
    # batch-boundary stalls of fixed gather() batches, where one slow (huge)
    # thread would idle every other worker until the whole batch finished.
    window = max_concurrency + 4
    it = iter(remaining)
    pending: set[asyncio.Task] = set()
    for _ in range(window):
        tid = next(it, None)
        if tid is None:
            break
        pending.add(asyncio.create_task(process_tid(tid)))

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for _ in done:
            tid = next(it, None)
            if tid is not None:
                pending.add(asyncio.create_task(process_tid(tid)))

    reporter_task.cancel()
    try:
        await reporter_task
    except asyncio.CancelledError:
        pass

    # final save
    save_progress(output_dir, deleted_set, failed_dict, {
        "success": success_count,
        "failed": fail_count,
        "deleted": len(deleted_set),
        "completed_total": len(completed_set),
        "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    total_time = time.time() - start_time
    log(f"{'='*60}")
    log(f"Backup complete!")
    log(f"  Succeeded: {success_count}")
    log(f"  Deleted: {len(deleted_set)}")
    log(f"  Failed: {len(failed_dict)}")
    log(f"  Total time: {total_time/3600:.1f} hours")
    log(f"  Data: {output_dir}")
    log(f"{'='*60}")
