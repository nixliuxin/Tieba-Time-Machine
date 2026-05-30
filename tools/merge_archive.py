r"""
merge_archive.py - Merge all per-thread content.db + JSON into unified master.db.

Usage:
    python merge_archive.py --source ./scraped_data --output ./archives

Supports resume: processed tids are tracked in master.db merge_progress table.
"""

import argparse
import json
import os
import re
import sqlite3
import time
from pathlib import Path


FOLDER_PATTERN = re.compile(r"^\[(.+?)吧\]\[(\d+)\](.*)$")

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def parse_folder_name(name: str):
    """Parse forum_name and tid from folder name pattern [forum][tid]title."""
    m = FOLDER_PATTERN.match(name)
    if m:
        return m.group(1), int(m.group(2)), m.group(3)
    return None, None, None


def init_master_db(db_path: str) -> sqlite3.Connection:
    """Create or open master.db and initialize the schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
    conn.execute("PRAGMA foreign_keys = ON")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    return conn


def get_merged_tids(conn: sqlite3.Connection) -> set:
    """Return the set of already-merged tids."""
    cur = conn.execute("SELECT tid FROM merge_progress")
    return {row[0] for row in cur.fetchall()}


def merge_thread_json(conn: sqlite3.Connection, thread_json_path: str, tid: int, forum_name: str, folder_name: str):
    """Read thread.json and insert into the thread table."""
    if not os.path.exists(thread_json_path):
        conn.execute(
            "INSERT OR IGNORE INTO thread (tid, title, forum_id, forum_name, folder_name) VALUES (?, ?, 0, ?, ?)",
            (tid, folder_name, forum_name, folder_name),
        )
        return

    with open(thread_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    t = data.get("thread", data) if "thread" in data else data

    vote_info_str = ""
    if "vote_info" in t and t["vote_info"]:
        vote_info_str = json.dumps(t["vote_info"], ensure_ascii=False)

    conn.execute(
        """INSERT OR IGNORE INTO thread
        (tid, title, forum_id, forum_name, post_id, author_user_id, type,
         is_share, is_help, vote_info, share_origin, view_num, reply_num,
         share_num, agree, disagree, create_time, status, folder_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            t.get("id", tid),
            t.get("title", folder_name),
            t.get("forum_id", 0),
            t.get("forum_name", forum_name),
            t.get("post_id", 0),
            t.get("user_id", 0),
            t.get("type", 0),
            t.get("is_share", False),
            t.get("is_help", False),
            vote_info_str,
            t.get("share_origin", 0),
            t.get("view_num", 0),
            t.get("reply_num", 0),
            t.get("share_num", 0),
            t.get("agree", 0),
            t.get("disagree", 0),
            t.get("create_time", 0),
            t.get("status", 0),
            folder_name,
        ),
    )


def merge_forum_json(conn: sqlite3.Connection, forum_json_path: str, forum_name: str):
    """Read forum.json and insert/update the forum table."""
    if not os.path.exists(forum_json_path):
        conn.execute(
            "INSERT OR IGNORE INTO forum (forum_id, forum_name) VALUES (0, ?)",
            (forum_name,),
        )
        return

    with open(forum_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    f_data = data.get("forum", data) if "forum" in data else data

    conn.execute(
        """INSERT INTO forum (forum_id, forum_name, member_num, post_num, thread_num, slogan)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(forum_name) DO UPDATE SET
            forum_id = CASE WHEN excluded.forum_id != 0 THEN excluded.forum_id ELSE forum.forum_id END,
            member_num = MAX(forum.member_num, excluded.member_num),
            post_num = MAX(forum.post_num, excluded.post_num),
            thread_num = MAX(forum.thread_num, excluded.thread_num),
            slogan = CASE WHEN excluded.slogan != '' THEN excluded.slogan ELSE forum.slogan END""",
        (
            f_data.get("id", f_data.get("forum_id", 0)),
            f_data.get("name", f_data.get("forum_name", forum_name)),
            f_data.get("member_num", 0),
            f_data.get("post_num", 0),
            f_data.get("thread_num", 0),
            f_data.get("slogan", ""),
        ),
    )


def merge_content_db(conn: sqlite3.Connection, content_db_path: str, tid: int):
    """Open content.db, read its data, and insert into master.db."""
    if not os.path.exists(content_db_path):
        return

    src = sqlite3.connect(content_db_path)
    src.execute("PRAGMA journal_mode = WAL")
    src.execute("PRAGMA query_only = ON")

    try:
        tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        # posts
        if "post" in tables:
            # Check if scrape_batch_id column exists
            cols = {r[1] for r in src.execute("PRAGMA table_info(post)").fetchall()}
            has_batch = "scrape_batch_id" in cols

            rows = src.execute(
                f"SELECT id, contents, floor, user_id, agree, disagree, create_time, is_thread_author, sign, reply_num, parent_id, reply_to_id{', scrape_batch_id' if has_batch else ''} FROM post"
            ).fetchall()
            for r in rows:
                batch_id = r[12] if has_batch and len(r) > 12 else 0
                conn.execute(
                    """INSERT OR IGNORE INTO post (id, tid, contents, floor, user_id, agree, disagree,
                       create_time, is_thread_author, sign, reply_num, parent_id, reply_to_id, scrape_batch_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (r[0], tid, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], batch_id),
                )

        # users
        if "user" in tables:
            cols = {r[1] for r in src.execute("PRAGMA table_info(user)").fetchall()}
            has_id = "id" in cols
            has_completed = "completed" in cols
            has_scrape_time = "scrape_time" in cols

            select_cols = "portrait, username, nickname, tieba_uid, avatar, glevel, gender, ip, is_vip, is_god, age, sign, post_num, agree_num, fan_num, follow_num, forum_num, level, is_bawu, status"
            if has_completed:
                select_cols += ", completed"
            if has_scrape_time:
                select_cols += ", scrape_time"
            if has_id:
                select_cols += ", id"

            rows = src.execute(f"SELECT {select_cols} FROM user WHERE portrait IS NOT NULL").fetchall()
            for r in rows:
                base_len = 20
                idx = base_len
                completed = 0
                scrape_time = 0
                user_id_val = 0

                if has_completed:
                    completed = r[idx] if len(r) > idx else 0
                    idx += 1
                if has_scrape_time:
                    scrape_time = r[idx] if len(r) > idx else 0
                    idx += 1
                if has_id:
                    user_id_val = r[idx] if len(r) > idx else 0
                    idx += 1

                conn.execute(
                    """INSERT OR IGNORE INTO user (portrait, tid, user_id, username, nickname, tieba_uid, avatar,
                       glevel, gender, ip, is_vip, is_god, age, sign, post_num, agree_num,
                       fan_num, follow_num, forum_num, level, is_bawu, status, completed, scrape_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (r[0], tid, user_id_val, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11],
                     r[12], r[13], r[14], r[15], r[16], r[17], r[18], r[19], completed, scrape_time),
                )

        # tieba_origin_src
        if "tieba_origin_src" in tables:
            rows = src.execute("SELECT id, filename, content_frag_type, origin_src FROM tieba_origin_src").fetchall()
            for r in rows:
                conn.execute(
                    "INSERT OR IGNORE INTO tieba_origin_src (id, tid, filename, content_frag_type, origin_src) VALUES (?, ?, ?, ?, ?)",
                    (r[0], tid, r[1], r[2], r[3]),
                )

        # scrape_batch
        if "scrape_batch" in tables:
            rows = src.execute("SELECT id, scraper_version, scrape_config, scrape_time FROM scrape_batch").fetchall()
            for r in rows:
                conn.execute(
                    "INSERT OR IGNORE INTO scrape_batch (id, tid, scraper_version, scrape_config, scrape_time) VALUES (?, ?, ?, ?, ?)",
                    (r[0], tid, r[1], r[2], r[3]),
                )

        # user_info_history
        if "user_info_history" in tables:
            rows = src.execute("SELECT portrait, username, tieba_uid, field_name, field_value, scrape_time FROM user_info_history").fetchall()
            for r in rows:
                conn.execute(
                    "INSERT INTO user_info_history (tid, portrait, username, tieba_uid, field_name, field_value, scrape_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tid, r[0], r[1], r[2], r[3], r[4], r[5]),
                )

    finally:
        src.close()


def merge_scrape_info(conn: sqlite3.Connection, scrape_info_path: str, tid: int):
    """Read scrape_info.json and insert into the scrape_info table."""
    if not os.path.exists(scrape_info_path):
        return

    with open(scrape_info_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_json = json.dumps(data, ensure_ascii=False)
    conn.execute(
        """INSERT OR IGNORE INTO scrape_info (tid, scraper_version, scrape_time, config, raw_json)
        VALUES (?, ?, ?, ?, ?)""",
        (
            tid,
            data.get("scraper_version", ""),
            data.get("scrape_time", 0),
            json.dumps(data.get("config", {}), ensure_ascii=False),
            raw_json,
        ),
    )


def find_thread_dirs(forum_dir: str):
    """Scan a forum directory and find all thread folders."""
    results = []
    for name in os.listdir(forum_dir):
        if name.startswith("_"):
            continue
        full = os.path.join(forum_dir, name)
        if not os.path.isdir(full):
            continue
        forum_name, tid, title = parse_folder_name(name)
        if tid is not None:
            results.append((full, forum_name, tid, name))
    return results


def merge_one_forum(source_forum_dir: str, forum_dir_name: str, output_dir: str):
    """Merge all threads from a single forum into its own master.db."""
    out_forum_dir = os.path.join(output_dir, forum_dir_name)
    os.makedirs(out_forum_dir, exist_ok=True)
    output_path = os.path.join(out_forum_dir, "master.db")

    print(f"\n{'='*50}")
    print(f"  Forum: {forum_dir_name}")
    print(f"  Output: {output_path}")
    print(f"{'='*50}")

    conn = init_master_db(output_path)
    merged_tids = get_merged_tids(conn)
    print(f"  Already merged {len(merged_tids)} threads")

    threads = find_thread_dirs(source_forum_dir)
    print(f"  Found {len(threads)} thread folders")

    pending = [(p, fn, tid, name) for p, fn, tid, name in threads if tid not in merged_tids]
    print(f"  Pending: {len(pending)} threads")

    if not pending:
        conn.close()
        return

    start_time = time.time()
    errors = 0
    for i, (folder_path, forum_name, tid, folder_name) in enumerate(pending):
        thread_dir = os.path.join(folder_path, "threads", str(tid))
        if not os.path.isdir(thread_dir):
            thread_dir = folder_path

        thread_json = os.path.join(thread_dir, "thread.json")
        forum_json = os.path.join(thread_dir, "forum.json")
        content_db = os.path.join(thread_dir, "content.db")
        scrape_info_file = os.path.join(folder_path, "scrape_info.json")
        if not os.path.exists(scrape_info_file):
            scrape_info_file = os.path.join(thread_dir, "scrape_info.json")

        conn.execute("BEGIN")
        try:
            merge_forum_json(conn, forum_json, forum_name)
            merge_thread_json(conn, thread_json, tid, forum_name, folder_name)
            merge_content_db(conn, content_db, tid)
            merge_scrape_info(conn, scrape_info_file, tid)

            conn.execute(
                "INSERT OR IGNORE INTO merge_progress (tid, forum_name, merged_at) VALUES (?, ?, ?)",
                (tid, forum_name, int(time.time())),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            errors += 1
            if errors <= 5:
                print(f"  [ERROR] tid={tid}: {e}")
            elif errors == 6:
                print(f"  ... additional errors suppressed")
            continue

        if (i + 1) % 100 == 0 or (i + 1) == len(pending):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(pending) - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{len(pending)}] {rate:.1f} threads/s, ETA {eta:.0f}s", flush=True)

    # Populate FTS index
    print("  Building FTS5 full-text index...")
    conn.execute("DELETE FROM post_fts")
    conn.execute(
        "INSERT INTO post_fts(tid, post_id, floor, contents) "
        "SELECT tid, id, floor, contents FROM post"
    )
    conn.commit()

    # Summary stats
    total_posts = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
    total_merged = conn.execute("SELECT COUNT(*) FROM merge_progress").fetchone()[0]
    db_size = os.path.getsize(output_path) / 1024 / 1024
    print(f"  Done! {total_merged} threads, {total_posts} posts, {total_users} users | {db_size:.1f} MB")
    if errors:
        print(f"  ({errors} errors)")

    conn.close()


def remove_source_dir(source_forum_dir: str, forum_dir_name: str):
    """Remove the source forum directory after successful merge."""
    import shutil
    print(f"  Cleaning up source: {source_forum_dir}")
    shutil.rmtree(source_forum_dir)
    print(f"  Removed: {forum_dir_name}/")


def main():
    parser = argparse.ArgumentParser(description="Merge Tieba archives into per-forum master.db files")
    parser.add_argument("--source", required=True, help="Source data directory (e.g. ./scraped_data)")
    parser.add_argument("--output", required=True, help="Output root directory (e.g. ./archives)")
    parser.add_argument("--forum", default=None, help="Only process the specified forum (directory name)")
    parser.add_argument(
        "--keep-raw", action="store_true", default=False,
        help="Keep raw source files after merge (default: delete after successful merge)",
    )
    args = parser.parse_args()

    source_dir = args.source
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    # Discover all forum directories
    forum_dirs = []
    for name in os.listdir(source_dir):
        full = os.path.join(source_dir, name)
        if os.path.isdir(full) and not name.startswith("_"):
            if args.forum is None or name == args.forum:
                forum_dirs.append((name, full))

    print(f"Found {len(forum_dirs)} forum directories")
    if not args.keep_raw:
        print("  (raw source will be deleted after successful merge; use --keep-raw to retain)")

    for forum_dir_name, forum_path in forum_dirs:
        merge_one_forum(forum_path, forum_dir_name, output_dir)
        if not args.keep_raw:
            remove_source_dir(forum_path, forum_dir_name)

    print(f"\nAll done! Output directory: {output_dir}")
    for name in sorted(os.listdir(output_dir)):
        sub = os.path.join(output_dir, name)
        if os.path.isdir(sub):
            db_file = os.path.join(sub, "master.db")
            if os.path.exists(db_file):
                size = os.path.getsize(db_file) / 1024 / 1024
                print(f"  {name}/master.db  ({size:.1f} MB)")


if __name__ == "__main__":
    main()
