r"""
pack_media.py - Pack per-forum media files into uncompressed tar with offset index.

Usage:
    python pack_media.py --source ./scraped_data --output ./archives

Features:
- No compression (JPEG etc. are already compressed; tar preserves them as-is)
- Generates media_index.json with offset/size for random access from reader
- Incremental: already-packed tids are skipped on re-run
"""

import argparse
import json
import os
import re
import tarfile
import time
from pathlib import Path


FOLDER_PATTERN = re.compile(r"^\[(.+?)吧\]\[(\d+)\](.*)$")

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".mp4", ".avi", ".flv", ".mkv", ".mov",
    ".mp3", ".wav", ".m4a", ".ogg", ".aac",
}

MEDIA_DIRS = {"forum_avatar", "user_avatar", "images", "videos", "voices"}


def parse_folder_name(name: str):
    m = FOLDER_PATTERN.match(name)
    if m:
        return m.group(1), int(m.group(2)), m.group(3)
    return None, None, None


def collect_media_files(thread_folder: str, tid: int):
    """Collect all media files in a thread folder; return list of (disk_path, tar_internal_path)."""
    results = []
    thread_dir = os.path.join(thread_folder, "threads", str(tid))
    if not os.path.isdir(thread_dir):
        thread_dir = thread_folder

    for root, dirs, files in os.walk(thread_dir):
        rel_root = os.path.relpath(root, thread_dir)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                disk_path = os.path.join(root, f)
                # tar internal path: <tid>/<relative_path>
                if rel_root == ".":
                    tar_path = f"{tid}/{f}"
                else:
                    # Simplify path: strip the post_assets intermediate directory
                    simplified = rel_root.replace("post_assets" + os.sep, "").replace("post_assets", "")
                    if simplified:
                        tar_path = f"{tid}/{simplified}/{f}"
                    else:
                        tar_path = f"{tid}/{f}"
                tar_path = tar_path.replace("\\", "/")
                results.append((disk_path, tar_path))

    return results


def load_index(index_path: str) -> dict:
    """Load existing index.json from disk."""
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_index(index_path: str, index_data: dict):
    """Save index.json to disk."""
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False)


def get_packed_tids(index_data: dict, files_key: str) -> set:
    """Return the set of tids already packed, extracted from the index."""
    tids = set()
    files = index_data.get(files_key, index_data.get("files", {}))
    for tar_path in files:
        tid_str = tar_path.split("/")[0]
        if tid_str.isdigit():
            tids.add(int(tid_str))
    return tids


def pack_forum(source_dir: str, forum_dir_name: str, forum_path: str, output_dir: str):
    """Pack all media for a single forum into its own output directory."""
    # Output to output_dir/<forum_dir_name>/
    out_forum_dir = os.path.join(output_dir, forum_dir_name)
    os.makedirs(out_forum_dir, exist_ok=True)

    index_path = os.path.join(out_forum_dir, "media_index.json")
    index_data = load_index(index_path)

    # Parse all thread folders
    threads = []
    for name in os.listdir(forum_path):
        if name.startswith("_"):
            continue
        full = os.path.join(forum_path, name)
        if not os.path.isdir(full):
            continue
        forum_name, tid, title = parse_folder_name(name)
        if tid is not None:
            threads.append((full, forum_name, tid))

    if not threads:
        return

    tar_filename = "media.tar"
    tar_path = os.path.join(out_forum_dir, tar_filename)

    # Already-packed tids
    packed_tids = get_packed_tids(index_data, "files")
    pending = [(f, fn, tid) for f, fn, tid in threads if tid not in packed_tids]

    if not pending:
        print(f"  [{forum_dir_name}] All {len(threads)} threads already packed, skipping")
        return

    print(f"  [{forum_dir_name}] {len(threads)} threads total, {len(pending)} to pack")

    # Initialize index
    if "files" not in index_data:
        index_data["tar_file"] = tar_filename
        index_data["files"] = {}

    # Open tar (append if exists, create otherwise)
    mode = "a" if os.path.exists(tar_path) else "w"
    tf = tarfile.open(tar_path, f"{mode}:")

    total_files = 0
    start_time = time.time()

    try:
        for i, (folder_path, fn, tid) in enumerate(pending):
            media_files = collect_media_files(folder_path, tid)

            for disk_path, internal_path in media_files:
                try:
                    info = tf.gettarinfo(disk_path, arcname=internal_path)
                    offset = tf.offset
                    tf.addfile(info, open(disk_path, "rb"))

                    index_data["files"][internal_path] = {
                        "offset": offset,
                        "size": info.size,
                    }
                    total_files += 1
                except (PermissionError, OSError) as e:
                    print(f"    [WARN] Skipping {disk_path}: {e}")

            if (i + 1) % 200 == 0:
                elapsed = time.time() - start_time
                print(f"    Progress {i+1}/{len(pending)}, {total_files} files, {elapsed:.0f}s", flush=True)

    finally:
        tf.close()

    save_index(index_path, index_data)

    elapsed = time.time() - start_time
    tar_size_mb = os.path.getsize(tar_path) / 1024 / 1024
    print(f"  [{forum_dir_name}] Done: {total_files} files, tar={tar_size_mb:.1f}MB, {elapsed:.0f}s elapsed")


def main():
    parser = argparse.ArgumentParser(description="Pack per-forum media files into uncompressed tar archives")
    parser.add_argument("--source", required=True, help="Source data directory (e.g. ./scraped_data)")
    parser.add_argument("--output", required=True, help="Output directory (e.g. ./archives)")
    parser.add_argument("--forum", default=None, help="Only process the specified forum (directory name)")
    args = parser.parse_args()

    source_dir = args.source
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    index_path = os.path.join(output_dir, "index.json")
    index_data = load_index(index_path)

    # Iterate over all forum directories
    forum_dirs = []
    for name in os.listdir(source_dir):
        full = os.path.join(source_dir, name)
        if os.path.isdir(full) and not name.startswith("_"):
            if args.forum is None or name == args.forum:
                forum_dirs.append((name, full))

    print(f"Found {len(forum_dirs)} forum directories")

    for forum_dir_name, forum_path in forum_dirs:
        pack_forum(source_dir, forum_dir_name, forum_path, output_dir)

    print(f"\nAll done!")
    for name in sorted(os.listdir(output_dir)):
        idx_file = os.path.join(output_dir, name, "media_index.json")
        if os.path.exists(idx_file):
            idx = load_index(idx_file)
            count = len(idx.get("files", {}))
            print(f"  {name}: {count} media files indexed")


if __name__ == "__main__":
    main()
