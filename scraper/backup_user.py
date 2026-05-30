"""
Back up all content (threads + reply-related threads) for a given user across all forums.

Usage:
  python -u backup_user.py <output_dir> --uid <UID> --portrait <PORTRAIT>

Example:
  python -u backup_user.py ./output/my_user --uid 12345678 --portrait "tb.1.xxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxx"

BDUSS is read from tieba_auth.json (same as backup_forum.py).
On the first run, all tids are collected via the API and cached to _all_tids.json.
Subsequent runs load from cache for checkpoint-based resumption.
"""

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import orjson
import aiotieba as tb
from aiotieba.api.get_user_contents.protobuf import (
    UserPostReqIdl_pb2,
    UserPostResIdl_pb2,
)
from aiotieba.const import APP_BASE_HOST, LATEST_VERSION
from aiotieba.api.get_user_contents._const import CMD
import yarl

from backup_lib import (
    init_archiver,
    setup_logging,
    acquire_lock,
    release_lock,
    load_tids_from_cache,
    save_tids_cache,
    batch_download,
    log,
    read_bduss,
)


async def collect_user_tids(bduss: str, uid: int, portrait: str) -> dict:
    """Collect all tids for a user via the API (replies + threads)."""
    log("Collecting all user tids ...")

    async with tb.Client(bduss) as client:
        reply_tids = set()
        pn = 1
        while True:
            posts = await client.get_user_posts(portrait, pn=pn)
            if len(posts) == 0:
                break
            for p in posts:
                reply_tids.add(p.tid)
            if pn % 50 == 0:
                log(f"  Replies: page {pn} ...")
            pn += 1
        log(f"  Replies involve {len(reply_tids)} threads")

        # Threads (workaround for aiotieba bug: manually inject BDUSS)
        thread_tids = set()
        pn = 1
        while True:
            req = UserPostReqIdl_pb2.UserPostReqIdl()
            req.data.common.BDUSS = client._http_core.account.BDUSS
            req.data.common._client_version = LATEST_VERSION
            req.data.uid = uid
            req.data.is_thread = 1
            req.data.need_content = 1
            req.data.pn = pn
            req.data.is_view_card = 1
            data = req.SerializeToString()
            request = client._http_core.pack_proto_request(
                yarl.URL.build(
                    scheme="https",
                    host=APP_BASE_HOST,
                    path="/c/u/feed/userpost",
                    query_string=f"cmd={CMD}",
                ),
                data,
            )
            body = await client._http_core.net_core.send_request(
                request, read_bufsize=64 * 1024
            )
            res = UserPostResIdl_pb2.UserPostResIdl()
            res.ParseFromString(body)
            items = res.data.post_list
            if len(items) == 0:
                break
            for item in items:
                thread_tids.add(item.thread_id)
            pn += 1
        log(f"  Threads: {len(thread_tids)}")

        all_tids = sorted(reply_tids | thread_tids)
        log(f"  Total: {len(all_tids)} unique threads")

        return {
            "all_tids": all_tids,
            "reply_tids": sorted(reply_tids),
            "thread_tids": sorted(thread_tids),
        }


async def main_async(args):
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    setup_logging(output_dir, prefix="user")

    bduss = read_bduss()
    init_archiver(output_dir, bduss=bduss)

    tids = load_tids_from_cache(output_dir)
    if tids is None:
        if not args.uid or not args.portrait:
            log("[ERROR] First run requires --uid and --portrait to collect tids")
            sys.exit(1)
        result = await collect_user_tids(bduss, args.uid, args.portrait)
        save_tids_cache(output_dir, result["all_tids"], {
            "reply_tids": result["reply_tids"],
            "thread_tids": result["thread_tids"],
        })
        tids = result["all_tids"]
    else:
        log(f"[cache] Loaded {len(tids)} tids")

    lock_file = acquire_lock(output_dir)
    try:
        await batch_download(tids, output_dir, max_concurrency=args.concurrency)
    finally:
        release_lock(lock_file)


def main():
    parser = argparse.ArgumentParser(description="Back up all content for a user across all forums")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--uid", type=int, help="User UID (required on first run to collect tids)")
    parser.add_argument("--portrait", help="User portrait (required on first run to collect tids)")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrency (default 10, adaptive throttling)")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
