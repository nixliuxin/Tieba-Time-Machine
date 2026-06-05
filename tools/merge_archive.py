r"""
merge_archive.py - Merge all per-thread data + assets into a single archive folder.

Usage:
    python merge_archive.py --source ./scraped_data --output ./archives

Produces per-forum: master.db (all structured data) + data.tar + data_index.json (media + logs).
Supports resume: processed tids are tracked in master.db merge_progress table.
"""

import argparse
import json
import os
import re
import sqlite3
import tarfile
import time
from pathlib import Path


FOLDER_PATTERN = re.compile(r"^\[(.+?)吧\]\[(\d+)\](.*)$")

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DB_MERGED_FILES = {"thread.json", "forum.json", "content.db", "scrape_info.json",
                    "content.db-wal", "content.db-shm"}


def parse_folder_name(name: str):
    """Parse forum_name and tid from folder name pattern [forum][tid]title."""
    m = FOLDER_PATTERN.match(name)
    if m:
        return m.group(1), int(m.group(2)), m.group(3)
    return None, None, None


def init_master_db(db_path: str, *, bulk_import: bool = False) -> sqlite3.Connection:
    """Create or open master.db and initialize the schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    if bulk_import:
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA cache_size = -256000")  # 256MB cache
        conn.execute("PRAGMA temp_store = MEMORY")
    else:
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")
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
    """Merge content.db into master.db via ATTACH + cross-db INSERT...SELECT.

    Far faster than row-by-row Python transfer: SQLite copies internally.
    The per-thread `tid` is injected as a literal since content.db tables lack it.
    """
    if not os.path.exists(content_db_path):
        return

    # ATTACH/DETACH cannot run inside an active transaction. Python's sqlite3
    # implicitly opens a transaction on the preceding INSERTs, so commit first
    # to ensure both ATTACH (here) and DETACH (in finally) execute cleanly.
    conn.commit()
    conn.execute("ATTACH DATABASE ? AS src", (content_db_path,))
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM src.sqlite_master WHERE type='table'").fetchall()}

        # posts
        if "post" in tables:
            cols = {r[1] for r in conn.execute("PRAGMA src.table_info(post)").fetchall()}
            batch_sel = "scrape_batch_id" if "scrape_batch_id" in cols else "0"
            conn.execute(
                f"""INSERT OR IGNORE INTO post (id, tid, contents, floor, user_id, agree, disagree,
                       create_time, is_thread_author, sign, reply_num, parent_id, reply_to_id, scrape_batch_id)
                    SELECT id, {tid}, contents, floor, user_id, agree, disagree,
                       create_time, is_thread_author, sign, reply_num, parent_id, reply_to_id, {batch_sel}
                    FROM src.post"""
            )

        # users
        if "user" in tables:
            cols = {r[1] for r in conn.execute("PRAGMA src.table_info(user)").fetchall()}
            id_sel = "id" if "id" in cols else "0"
            completed_sel = "completed" if "completed" in cols else "0"
            scrape_time_sel = "scrape_time" if "scrape_time" in cols else "0"
            conn.execute(
                f"""INSERT OR IGNORE INTO user (portrait, tid, user_id, username, nickname, tieba_uid, avatar,
                       glevel, gender, ip, is_vip, is_god, age, sign, post_num, agree_num,
                       fan_num, follow_num, forum_num, level, is_bawu, status, completed, scrape_time)
                    SELECT portrait, {tid}, {id_sel}, username, nickname, tieba_uid, avatar,
                       glevel, gender, ip, is_vip, is_god, age, sign, post_num, agree_num,
                       fan_num, follow_num, forum_num, level, is_bawu, status, {completed_sel}, {scrape_time_sel}
                    FROM src.user WHERE portrait IS NOT NULL"""
            )

        # tieba_origin_src
        if "tieba_origin_src" in tables:
            conn.execute(
                f"""INSERT OR IGNORE INTO tieba_origin_src (id, tid, filename, content_frag_type, origin_src)
                    SELECT id, {tid}, filename, content_frag_type, origin_src FROM src.tieba_origin_src"""
            )

        # scrape_batch
        if "scrape_batch" in tables:
            conn.execute(
                f"""INSERT OR IGNORE INTO scrape_batch (id, tid, scraper_version, scrape_config, scrape_time)
                    SELECT id, {tid}, scraper_version, scrape_config, scrape_time FROM src.scrape_batch"""
            )

        # user_info_history
        if "user_info_history" in tables:
            conn.execute(
                f"""INSERT INTO user_info_history (tid, portrait, username, tieba_uid, field_name, field_value, scrape_time)
                    SELECT {tid}, portrait, username, tieba_uid, field_name, field_value, scrape_time FROM src.user_info_history"""
            )
        # Commit the inserts so `src` is no longer bound to an active transaction.
        conn.commit()
    except Exception:
        # Roll back so the failed thread's partial writes don't block DETACH.
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        # Defensive DETACH: never let a single thread leave `src` attached and
        # cascade "database src is already in use" into every later thread.
        try:
            conn.execute("DETACH DATABASE src")
        except Exception:
            pass


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
    print(f"  Scanning thread folders ...", flush=True)
    results = []
    all_entries = os.listdir(forum_dir)
    for i, name in enumerate(all_entries):
        if name.startswith("_"):
            continue
        full = os.path.join(forum_dir, name)
        if not os.path.isdir(full):
            continue
        forum_name, tid, title = parse_folder_name(name)
        if tid is not None:
            results.append((full, forum_name, tid, name))
        if (i + 1) % 5000 == 0:
            print(f"    ... listed {i+1}/{len(all_entries)}, found {len(results)} threads", flush=True)
    return results


def merge_stub_threads(conn: sqlite3.Connection, source_forum_dir: str, forum_name: str, merged_tids: set):
    """Merge deleted/failed threads from _all_tids.json + _progress.json as stub records."""
    tids_file = os.path.join(source_forum_dir, "_all_tids.json")
    progress_file = os.path.join(source_forum_dir, "_progress.json")

    if not os.path.exists(tids_file):
        return 0, 0

    with open(tids_file, "r", encoding="utf-8") as f:
        all_items = json.load(f)
    tid_meta = {}
    for item in all_items:
        if isinstance(item, dict) and "tid" in item:
            tid_meta[item["tid"]] = item

    deleted_tids = set()
    failed_tids = set()
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            progress = json.load(f)
        deleted_tids = set(progress.get("deleted", []))
        failed_tids = set(int(k) for k in progress.get("failed_details", {}).keys())

    stub_tids = (deleted_tids | failed_tids) - merged_tids
    if not stub_tids:
        return 0, 0

    deleted_count = 0
    failed_count = 0
    for tid in stub_tids:
        meta = tid_meta.get(tid, {})
        scrape_status = 1 if tid in deleted_tids else 2
        title = meta.get("title", f"[tid={tid}]")
        create_time = meta.get("create_time", 0)
        reply_num = meta.get("reply_num", 0)
        author_user_id = meta.get("author_id", 0)

        conn.execute(
            """INSERT OR IGNORE INTO thread
            (tid, title, forum_id, forum_name, author_user_id, reply_num, create_time, scrape_status)
            VALUES (?, ?, 0, ?, ?, ?, ?, ?)""",
            (tid, title, forum_name, author_user_id, reply_num, create_time, scrape_status),
        )
        conn.execute(
            "INSERT OR IGNORE INTO merge_progress (tid, forum_name, merged_at) VALUES (?, ?, ?)",
            (tid, forum_name, int(time.time())),
        )

        if tid in deleted_tids:
            deleted_count += 1
        else:
            failed_count += 1

    conn.commit()
    return deleted_count, failed_count


def _resolve_output_name(source_forum_dir: str, forum_dir_name: str) -> str:
    """Generate standardized output dir name: Ba_<forum>_<YYMMDD> or User_<name>_<YYMMDD>.

    Uses _meta.json for the scrape date. Falls back to source dir mtime if unavailable.
    If the source dir already follows the convention, preserves it as-is.
    """
    import re as _re

    if _re.match(r"^(Ba|User)_.+_\d{6}$", forum_dir_name):
        return forum_dir_name

    meta_path = os.path.join(source_forum_dir, "_meta.json")
    date_str = None
    backup_type = "Ba"

    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        created = meta.get("created_at", "")
        if created:
            date_str = created[:10].replace("-", "")[2:]  # "2026-05-30" -> "260530"
        if meta.get("type") == "user":
            backup_type = "User"

    if not date_str:
        mtime = os.path.getmtime(source_forum_dir)
        from datetime import datetime
        date_str = datetime.fromtimestamp(mtime).strftime("%y%m%d")

    return f"{backup_type}_{forum_dir_name}_{date_str}"


def build_fts_index(conn: sqlite3.Connection, total_posts: int, *, force: bool = False):
    """Rebuild the FTS5 index in batches with progress, avoiding a giant single transaction.

    Idempotent: skips rebuild if the index already covers all posts (unless force=True).
    """
    if not force:
        try:
            fts_count = conn.execute("SELECT COUNT(*) FROM post_fts").fetchone()[0]
            if fts_count == total_posts and total_posts > 0:
                print(f"  FTS index already up-to-date ({fts_count} posts), skipping", flush=True)
                return
        except sqlite3.OperationalError:
            pass

    print(f"  Building FTS5 full-text index ({total_posts} posts) ...", flush=True)
    fts_start = time.time()

    conn.execute("DROP TABLE IF EXISTS post_fts")
    conn.commit()
    conn.execute(
        "CREATE VIRTUAL TABLE post_fts USING fts5(tid UNINDEXED, post_id UNINDEXED, floor UNINDEXED, contents)"
    )
    conn.commit()

    BATCH = 50000
    offset = 0
    while offset < total_posts:
        conn.execute(
            "INSERT INTO post_fts(tid, post_id, floor, contents) "
            "SELECT tid, id, floor, contents FROM post LIMIT ? OFFSET ?",
            (BATCH, offset),
        )
        conn.commit()
        offset += BATCH
        done = min(offset, total_posts)
        elapsed = time.time() - fts_start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total_posts - done) / rate if rate > 0 else 0
        print(f"    FTS [{done}/{total_posts}] {done*100//max(total_posts,1)}% {rate:.0f} rows/s ETA {eta:.0f}s", flush=True)

    print(f"  FTS index built in {time.time() - fts_start:.0f}s", flush=True)


def merge_one_forum(source_forum_dir: str, forum_dir_name: str, output_dir: str):
    """Merge all threads from a single forum into its own master.db."""
    canonical_name = _resolve_output_name(source_forum_dir, forum_dir_name)
    out_forum_dir = os.path.join(output_dir, canonical_name)
    os.makedirs(out_forum_dir, exist_ok=True)
    output_path = os.path.join(out_forum_dir, "master.db")

    print(f"\n{'='*50}")
    print(f"  Forum: {forum_dir_name} -> {canonical_name}")
    print(f"  Output: {output_path}")
    print(f"{'='*50}")

    conn = init_master_db(output_path, bulk_import=True)

    # Ensure scrape_status column exists (for DBs created before this change)
    try:
        conn.execute("SELECT scrape_status FROM thread LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE thread ADD COLUMN scrape_status INTEGER DEFAULT 0")
        conn.commit()

    merged_tids = get_merged_tids(conn)
    print(f"  Already merged {len(merged_tids)} threads")

    threads = find_thread_dirs(source_forum_dir)
    print(f"  Found {len(threads)} thread folders")

    # ── Open data.tar + load asset index for single-pass packing ──
    index_path = os.path.join(out_forum_dir, "data_index.json")
    index_data = {"tar_file": "data.tar", "files": {}}
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
            index_data.setdefault("tar_file", "data.tar")
            index_data.setdefault("files", {})
    packed_tids = set()
    for p in index_data["files"]:
        tid_str = p.split("/")[0]
        if tid_str.isdigit():
            packed_tids.add(int(tid_str))

    def flush_index():
        tmp = index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False)
        os.replace(tmp, index_path)

    tar_full = os.path.join(out_forum_dir, "data.tar")
    tar_mode = "a" if os.path.exists(tar_full) else "w"
    tf = tarfile.open(tar_full, f"{tar_mode}:")

    # A thread needs work if it isn't fully merged OR isn't packed yet.
    pending = [(p, fn, tid, name) for p, fn, tid, name in threads
               if tid not in merged_tids or tid not in packed_tids]
    print(f"  Pending: {len(pending)} threads (merge + asset pack, single pass)")

    start_time = time.time()
    errors = 0
    total_files = 0

    try:
        for i, (folder_path, forum_name, tid, folder_name) in enumerate(pending):
            thread_dir = os.path.join(folder_path, "threads", str(tid))
            if not os.path.isdir(thread_dir):
                thread_dir = folder_path

            try:
                # 1. Merge structured data (skip if already merged)
                if tid not in merged_tids:
                    thread_json = os.path.join(thread_dir, "thread.json")
                    forum_json = os.path.join(thread_dir, "forum.json")
                    content_db = os.path.join(thread_dir, "content.db")
                    scrape_info_file = os.path.join(folder_path, "scrape_info.json")
                    if not os.path.exists(scrape_info_file):
                        scrape_info_file = os.path.join(thread_dir, "scrape_info.json")

                    merge_forum_json(conn, forum_json, forum_name)
                    merge_thread_json(conn, thread_json, tid, forum_name, folder_name)
                    merge_content_db(conn, content_db, tid)
                    merge_scrape_info(conn, scrape_info_file, tid)
                    conn.execute(
                        "INSERT OR IGNORE INTO merge_progress (tid, forum_name, merged_at) VALUES (?, ?, ?)",
                        (tid, forum_name, int(time.time())),
                    )

                # 2. Pack assets in the same pass (skip if already packed)
                if tid not in packed_tids:
                    for disk_path, internal_path in _collect_asset_files(folder_path, tid):
                        if internal_path in index_data["files"]:
                            continue
                        try:
                            info = tf.gettarinfo(disk_path, arcname=internal_path)
                            offset = tf.offset
                            with open(disk_path, "rb") as fh:
                                tf.addfile(info, fh)
                            index_data["files"][internal_path] = {"offset": offset, "size": info.size}
                            total_files += 1
                        except (PermissionError, OSError):
                            pass
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  [ERROR] tid={tid}: {e}")
                elif errors == 6:
                    print(f"  ... additional errors suppressed")
                continue

            if (i + 1) % 500 == 0 or (i + 1) == len(pending):
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(pending) - i - 1) / rate if rate > 0 else 0
                print(f"  [{i+1}/{len(pending)}] {rate:.1f} threads/s, {total_files} assets, ETA {eta:.0f}s", flush=True)
                # Periodically persist progress so an interruption never loses work.
                conn.commit()
                tf.fileobj.flush()
                flush_index()
    finally:
        tf.close()

    conn.commit()

    # Persist asset index
    flush_index()

    # Merge stub records for deleted/failed threads
    merged_tids = get_merged_tids(conn)
    forum_name_for_stubs = forum_dir_name
    if threads:
        forum_name_for_stubs = threads[0][1] or forum_dir_name
    deleted_count, failed_count = merge_stub_threads(
        conn, source_forum_dir, forum_name_for_stubs, merged_tids
    )
    if deleted_count or failed_count:
        print(f"  Stub records: {deleted_count} deleted + {failed_count} failed threads")

    # Build FTS index (batched, with progress)
    total_posts = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
    build_fts_index(conn, total_posts)

    # Summary stats
    print("  Computing stats ...", flush=True)
    total_threads = conn.execute("SELECT COUNT(*) FROM thread").fetchone()[0]
    full_threads = conn.execute("SELECT COUNT(*) FROM thread WHERE scrape_status = 0").fetchone()[0]
    deleted_threads = conn.execute("SELECT COUNT(*) FROM thread WHERE scrape_status = 1").fetchone()[0]
    failed_threads = conn.execute("SELECT COUNT(*) FROM thread WHERE scrape_status = 2").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
    db_size = os.path.getsize(output_path) / 1024 / 1024
    tar_size = os.path.getsize(tar_full) / 1024 / 1024 if os.path.exists(tar_full) else 0
    total_time = time.time() - start_time
    print(f"  Done! {total_threads} threads ({full_threads} full, {deleted_threads} deleted, {failed_threads} failed)")
    print(f"        {total_posts} posts, {total_users} users, {total_files} new assets")
    print(f"        master.db={db_size:.1f}MB, data.tar={tar_size:.1f}MB | {total_time:.0f}s total")
    if errors:
        print(f"  ({errors} merge errors)")

    conn.close()


def _collect_asset_files(thread_folder: str, tid: int):
    """Collect all files NOT already merged into master.db."""
    results = []
    thread_dir = os.path.join(thread_folder, "threads", str(tid))
    if not os.path.isdir(thread_dir):
        thread_dir = thread_folder

    for root, _, files in os.walk(thread_dir):
        rel_root = os.path.relpath(root, thread_dir)
        for f in files:
            if f in DB_MERGED_FILES:
                continue
            disk_path = os.path.join(root, f)
            if rel_root == ".":
                tar_path = f"{tid}/{f}"
            else:
                simplified = rel_root.replace("post_assets" + os.sep, "").replace("post_assets", "")
                tar_path = f"{tid}/{simplified}/{f}" if simplified else f"{tid}/{f}"
            results.append((disk_path, tar_path.replace("\\", "/")))
    return results


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
            tar_file = os.path.join(sub, "data.tar")
            parts = []
            if os.path.exists(db_file):
                parts.append(f"db={os.path.getsize(db_file)/1024/1024:.1f}MB")
            if os.path.exists(tar_file):
                parts.append(f"data={os.path.getsize(tar_file)/1024/1024:.1f}MB")
            if parts:
                print(f"  {name}/  ({', '.join(parts)})")


if __name__ == "__main__":
    main()
