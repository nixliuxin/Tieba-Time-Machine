"""
Back up all threads from a Tieba forum.

Usage:
  python -u backup_forum.py <forum_name> <output_dir>

Examples:
  python -u backup_forum.py my-forum ./output/my-forum

BDUSS is read from tieba_auth.json.
On first run, all thread IDs are collected via API pagination and saved to _all_tids.json.
Subsequent runs detect _all_tids.json and resume from the last checkpoint.
"""

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import aiotieba as tb

from backup_lib import (
    init_archiver,
    setup_logging,
    acquire_lock,
    release_lock,
    batch_download,
    read_bduss,
    log,
)

META_FILE = "_meta.json"


def load_meta(output_dir: str) -> dict | None:
    path = os.path.join(output_dir, META_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_meta(output_dir: str, forum_name: str):
    path = os.path.join(output_dir, META_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"forum": forum_name, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                  f, ensure_ascii=False, indent=2)


def load_tids(output_dir: str) -> list[int] | None:
    cache_file = os.path.join(output_dir, "_all_tids.json")
    if not os.path.exists(cache_file):
        return None
    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], dict):
            return [item["tid"] for item in data]
        return data
    if isinstance(data, dict) and "all_tids" in data:
        return data["all_tids"]
    return None


async def collect_forum_tids(bduss: str, forum_name: str) -> list[dict]:
    """Paginate through a forum to collect all thread IDs."""
    log(f"Collecting all threads from [{forum_name}吧] ...")
    all_items = []
    seen_tids = set()

    async with tb.Client(bduss) as client:
        pn = 1
        empty_streak = 0
        while True:
            try:
                threads = await client.get_threads(forum_name, pn=pn)
            except Exception as e:
                if "429" in str(e):
                    log(f"  [429] Rate limited, waiting 30s ...")
                    await asyncio.sleep(30)
                    continue
                log(f"  [ERROR] Page {pn} failed: {e}")
                break

            new_count = 0
            for t in threads:
                if t.tid not in seen_tids:
                    seen_tids.add(t.tid)
                    all_items.append({
                        "tid": t.tid,
                        "title": t.title,
                        "author_id": t.author_id,
                        "reply_num": t.reply_num,
                        "create_time": int(t.create_time) if hasattr(t, 'create_time') else 0,
                    })
                    new_count += 1

            if new_count == 0:
                empty_streak += 1
                if empty_streak >= 3:
                    break
            else:
                empty_streak = 0

            if pn % 50 == 0:
                log(f"  Page {pn}, collected {len(all_items)} threads so far ...")

            pn += 1

    log(f"  Collection complete: {len(all_items)} threads")
    return all_items


async def main_async(forum_name: str, output_dir: str, concurrency: int = 10):
    os.makedirs(output_dir, exist_ok=True)
    setup_logging(output_dir, prefix="forum")

    # Check metadata consistency
    meta = load_meta(output_dir)
    if meta and meta.get("forum") != forum_name:
        log(f"[WARNING] Directory is bound to [{meta['forum']}吧], but you specified [{forum_name}吧]")
        log(f"To switch forums, use a new directory or delete {output_dir}\\{META_FILE}")
        sys.exit(1)

    bduss = read_bduss()
    init_archiver(output_dir, bduss=bduss)
    log(f"[OK] Target: {forum_name}吧 → {output_dir}")

    tids = load_tids(output_dir)

    if tids is None:
        items = await collect_forum_tids(bduss, forum_name)
        if not items:
            log("[ERROR] No threads collected, please verify the forum name")
            sys.exit(1)

        tids = [item["tid"] for item in items]

        cache_file = os.path.join(output_dir, "_all_tids.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        log(f"[OK] Thread list saved ({len(tids)} threads)")

    save_meta(output_dir, forum_name)

    log(f"[OK] {len(tids)} threads to process")

    lock_file = acquire_lock(output_dir)
    try:
        await batch_download(tids, output_dir, max_concurrency=concurrency)
    finally:
        release_lock(lock_file)


def main():
    parser = argparse.ArgumentParser(description="Back up all threads from a Tieba forum")
    parser.add_argument("forum", help="Forum name (without the trailing '吧')")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrency (default 10, adaptive throttling)")
    args = parser.parse_args()

    asyncio.run(main_async(args.forum, args.output_dir, args.concurrency))


if __name__ == "__main__":
    main()
