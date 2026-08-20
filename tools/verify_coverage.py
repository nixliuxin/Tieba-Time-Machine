r"""
verify_coverage.py - Check an archive against a freshly collected thread list.

Usage:
    python verify_coverage.py --archive ./archives/<dir> --forum <forum-name>
    python verify_coverage.py --archive ./archives/<dir> --uid <UID> --portrait <PORTRAIT>

Why this exists:
    An archive can only prove what it contains, not what it missed. Whenever the
    raw scrape directory is gone, its `_all_tids.json` -- the list of thread ids
    that existed when the scrape ran -- is gone with it, and nothing is left to
    check the archive against.

    This re-collects the thread list from Tieba and compares it with the archive.
    It reads listings only: no thread content is fetched and the archive is never
    modified. The collected list is written to `<archive>/_scrape_meta/` so the
    check can be repeated later without another collection pass.

    Threads created after the cutoff are reported separately -- they appeared
    after the scrape and are outside what the archive ever claimed to hold.
"""

import argparse
import asyncio
import datetime
import json
import os
import re
import sqlite3
import sys

SCRAPER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scraper")
sys.path.insert(0, SCRAPER_DIR)

DIR_DATE_RE = re.compile(r"_(\d{2})(\d{2})(\d{2})$")


def infer_cutoff(archive_dir: str):
    """Read the YYMMDD suffix an archive directory carries, e.g. Ba_<forum>_260530."""
    m = DIR_DATE_RE.search(os.path.basename(os.path.normpath(archive_dir)))
    if not m:
        return None
    year, month, day = 2000 + int(m.group(1)), int(m.group(2)), int(m.group(3))
    # End of that day: the scrape ran during it, so same-day threads were in scope.
    return datetime.datetime(year, month, day, 23, 59, 59)


async def collect(forum: str, uid: int, portrait: str):
    import backup_lib
    bduss = backup_lib.read_bduss()
    if forum:
        import backup_forum
        return await backup_forum.collect_forum_tids(bduss, forum)
    import backup_user
    result = await backup_user.collect_user_tids(bduss, uid, portrait)
    # A user collection yields bare tids: the listing carries no title or
    # creation time, so entries are normalised to the forum shape with the
    # date left unknown and filled in from the archive where possible.
    tids = result["all_tids"] if isinstance(result, dict) else result
    return [{"tid": t, "title": None, "reply_num": None, "create_time": 0}
            if not isinstance(t, dict) else t for t in tids]


def main():
    p = argparse.ArgumentParser(
        description="Compare an archive with a freshly collected thread list")
    p.add_argument("--archive", required=True)
    p.add_argument("--forum", help="forum name (forum archives)")
    p.add_argument("--uid", type=int, help="user id (user collections)")
    p.add_argument("--portrait", help="user portrait (user collections)")
    p.add_argument("--cutoff", help="YYYY-MM-DD; default: the archive's date suffix")
    args = p.parse_args()

    if not args.forum and not args.uid:
        raise SystemExit("[ERROR] pass --forum, or --uid with --portrait")

    cutoff = (datetime.datetime.strptime(args.cutoff, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
              if args.cutoff else infer_cutoff(args.archive))
    if cutoff is None:
        raise SystemExit("[ERROR] cannot infer the cutoff, pass --cutoff")

    label = os.path.basename(os.path.normpath(args.archive))
    print(f"=== {label}  cutoff={cutoff:%Y-%m-%d}", flush=True)

    items = asyncio.run(collect(args.forum, args.uid, args.portrait))
    listed = {int(it["tid"]): it for it in items}

    db = os.path.join(args.archive, "master.db")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    archived = {r[0] for r in conn.execute("SELECT tid FROM thread")}
    # Fill in creation times the listing did not carry, so a user collection can
    # still be scoped for every thread the archive already knows about.
    for tid, created in conn.execute("SELECT tid, create_time FROM thread"):
        it = listed.get(tid)
        if it is not None and not it.get("create_time") and created:
            it["create_time"] = created
    conn.close()

    in_scope = {t: it for t, it in listed.items()
                if 0 < it.get("create_time", 0) <= cutoff.timestamp()}
    undated = [t for t, it in listed.items() if not it.get("create_time")]
    # An undated entry the archive never saw cannot be scoped by date, so it is
    # reported as missing rather than quietly dropped.
    for tid in undated:
        if tid not in archived:
            in_scope[tid] = listed[tid]
    missing = sorted(set(in_scope) - archived)
    after = [t for t, it in listed.items() if it.get("create_time", 0) > cutoff.timestamp()]
    gone = archived - set(listed)

    print(f"  listed now: {len(listed)} | created on or before cutoff: {len(in_scope)}"
          + (f" | undated: {len(undated)}" if undated else ""))
    print(f"  archive holds: {len(archived)}")
    print(f"  MISSING from archive (in scope): {len(missing)}")
    print(f"  created after cutoff (out of scope): {len(after)}")
    print(f"  in archive but no longer listed (deleted since / not listed): {len(gone)}")
    for tid in missing[:20]:
        it = in_scope[tid]
        when = datetime.datetime.fromtimestamp(it["create_time"]).date()
        print(f"    {tid}  {when}  replies={it.get('reply_num')}  {str(it.get('title'))[:40]}")
    if len(missing) > 20:
        print(f"    ... and {len(missing) - 20} more")

    meta_dir = os.path.join(args.archive, "_scrape_meta")
    os.makedirs(meta_dir, exist_ok=True)
    stamp = datetime.date.today().strftime("%y%m%d")
    out = os.path.join(meta_dir, f"_listed_tids_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"collected_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "source": args.forum or f"uid:{args.uid}",
                   "cutoff": cutoff.strftime("%Y-%m-%d"),
                   "count": len(items),
                   "items": items}, f, ensure_ascii=False)
    print(f"  baseline written: _scrape_meta/{os.path.basename(out)}")


if __name__ == "__main__":
    main()
