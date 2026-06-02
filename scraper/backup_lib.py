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

BACKOFF_INITIAL = 30
BACKOFF_MAX = 300
MAX_RETRIES_PER_TID = 3
IDLE_TIMEOUT = 180  # seconds: cancel task if no file writes for 3 min


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
    safe_title = sanitize_filename(title)[:80]
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


# ── Batch download main loop (concurrent + adaptive throttling) ──
DEFAULT_CONCURRENCY = 10
RAMP_UP_INTERVAL = 300  # attempt to ramp up concurrency after 5 min of stability


async def batch_download(all_tids: list[int], output_dir: str, max_concurrency: int = DEFAULT_CONCURRENCY):
    completed_set = scan_completed_tids(output_dir)
    deleted_set, failed_dict = load_progress_sets(output_dir)
    skip_set = completed_set | deleted_set

    remaining = [tid for tid in all_tids if tid not in skip_set]
    total = len(all_tids)

    log(f"{'='*60}")
    log(f"Total: {total} | Done: {len(completed_set)} | Deleted: {len(deleted_set)} | Failed: {len(failed_dict)} | Pending: {len(remaining)}")
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

    # adaptive throttling state
    current_concurrency = max_concurrency
    semaphore = asyncio.Semaphore(current_concurrency)
    throttle_lock = asyncio.Lock()
    progress_lock = asyncio.Lock()
    last_429_time = 0.0
    last_ramp_up_time = time.time()
    global_paused = asyncio.Event()
    global_paused.set()  # initially not paused

    async def adjust_concurrency(new_n: int):
        nonlocal current_concurrency, semaphore, last_ramp_up_time
        if new_n == current_concurrency:
            return
        old = current_concurrency
        current_concurrency = new_n
        semaphore = asyncio.Semaphore(new_n)
        last_ramp_up_time = time.time()
        log(f"  [THROTTLE] Concurrency adjusted: {old} -> {new_n}")

    async def handle_429(backoff_time: float):
        nonlocal last_429_time
        async with throttle_lock:
            now = time.time()
            if now - last_429_time < 5:
                return  # another worker is already handling this
            last_429_time = now
            global_paused.clear()
            new_n = max(current_concurrency // 2, 1)
            await adjust_concurrency(new_n)
            log(f"  [429] Global pause {backoff_time:.0f}s ...")
        await asyncio.sleep(backoff_time)
        global_paused.set()

    async def maybe_ramp_up():
        nonlocal last_ramp_up_time
        if current_concurrency >= max_concurrency:
            return
        if time.time() - last_ramp_up_time < RAMP_UP_INTERVAL:
            return
        if time.time() - last_429_time < RAMP_UP_INTERVAL:
            return
        async with throttle_lock:
            if current_concurrency < max_concurrency:
                await adjust_concurrency(current_concurrency + 1)

    def _verify_scrape(tid: int) -> bool:
        """Check if scrape() actually completed (content.db exists and has data)."""
        tid_pattern = f"[{tid}]"
        for name in os.listdir(output_dir):
            if tid_pattern in name and os.path.isdir(os.path.join(output_dir, name)):
                db_path = os.path.join(output_dir, name, "threads", str(tid), "content.db")
                if os.path.exists(db_path):
                    try:
                        conn = sqlite3.connect(db_path)
                        count = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
                        conn.close()
                        return count > 0
                    except Exception:
                        return False
        return False

    async def process_tid(tid: int):
        nonlocal success_count, fail_count, processed_count

        await global_paused.wait()
        async with semaphore:
            await global_paused.wait()

            cleanup_incomplete_tid(output_dir, tid)
            retries = 0
            backoff = BACKOFF_INITIAL
            while retries < MAX_RETRIES_PER_TID:
                try:
                    await _scrape_with_watchdog(tid, output_dir)
                    if not _verify_scrape(tid):
                        raise RuntimeError(f"scrape() returned but produced no valid data (tid={tid})")
                    async with progress_lock:
                        completed_set.add(tid)
                        _save_done_tids(output_dir, completed_set)
                        success_count += 1
                        failed_dict.pop(tid, None)
                    break
                except asyncio.TimeoutError as te:
                    elapsed = int(time.time() - start_time)
                    log(f"  [IDLE TIMEOUT] tid={tid}: {te} (wall {elapsed}s), skipping")
                    async with progress_lock:
                        fail_count += 1
                        failed_dict[tid] = str(te)
                    break
                except Exception as e:
                    err = str(e)
                    if "429" in err or "Too Many Requests" in err or "no valid data" in err:
                        retries += 1
                        await handle_429(backoff)
                        backoff = min(backoff * 2, BACKOFF_MAX)
                    elif "已被删除" in err or "可能已被删除" in err or "该贴已被删除" in err:
                        async with progress_lock:
                            deleted_set.add(tid)
                        log(f"  [DELETED] tid={tid}")
                        break
                    else:
                        async with progress_lock:
                            fail_count += 1
                            failed_dict[tid] = err[:200]
                        log(f"  [FAILED] tid={tid}: {err[:100]}")
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
            await maybe_ramp_up()

    # launch concurrent downloads
    reporter_task = asyncio.create_task(progress_reporter())

    batch_size = 50
    for batch_start in range(0, len(remaining), batch_size):
        batch = remaining[batch_start:batch_start + batch_size]
        tasks = [asyncio.create_task(process_tid(tid)) for tid in batch]
        await asyncio.gather(*tasks)

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
