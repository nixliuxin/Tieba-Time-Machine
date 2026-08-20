r"""
rebuild_index.py - Rebuild data_index.json from the actual tar files in an archive.

Usage:
    python rebuild_index.py --archive ./archives/<forum_dir>
    python rebuild_index.py --root ./archives            # every subdirectory

Why this exists:
    The original index carried a single top-level "tar_file" field, but an archive
    can accumulate more than one tar (e.g. media.tar from an early pipeline plus
    data.tar from a later one). A single field cannot describe members that live
    in different tars, so entries belonging to the other tar became unreachable.
    Offsets could also go stale when a tar was repacked while the index was kept.

    This tool reads every tar in the archive, records where each member actually
    is, and writes a v2 index that names the owning tar per entry. Tars are never
    modified. The previous index is preserved as data_index.json.bak.

Index format (v2):
    {
      "version": 2,
      "tars": ["data.tar", "media.tar"],
      "tar_file": "data.tar",              # legacy readers: tar holding most entries
      "files": {"<path>": {"tar": "data.tar", "offset": 1234, "size": 567}, ...}
    }
"""

import argparse
import json
import os
import random
import tarfile
import time


INDEX_NAME = "data_index.json"
LEGACY_INDEX_NAME = "media_index.json"


def find_index(archive_dir: str):
    for name in (INDEX_NAME, LEGACY_INDEX_NAME):
        path = os.path.join(archive_dir, name)
        if os.path.exists(path):
            return path
    return None


def list_tars(archive_dir: str):
    return sorted(f for f in os.listdir(archive_dir) if f.endswith(".tar"))


def scan_tar(tar_path: str):
    """Yield (name, offset, size) for every regular member, in file order."""
    with tarfile.open(tar_path, "r:") as tf:
        for member in tf:
            if member.isreg():
                yield member.name, member.offset, member.size


def build_files_map(archive_dir: str, tar_names, verbose: bool = True):
    """Scan every tar and map each member name to its owning tar and offset.

    When the same name appears in more than one tar the later scan wins, since
    the newer tar holds the more recently written copy.
    """
    files = {}
    collisions = 0
    for tar_name in tar_names:
        tar_path = os.path.join(archive_dir, tar_name)
        count = 0
        t0 = time.time()
        for name, offset, size in scan_tar(tar_path):
            if name in files:
                collisions += 1
            files[name] = {"tar": tar_name, "offset": offset, "size": size}
            count += 1
        if verbose:
            gib = os.path.getsize(tar_path) / 1024 ** 3
            print(f"    {tar_name}: {count} members, {gib:.2f} GiB, "
                  f"scanned in {time.time() - t0:.0f}s", flush=True)
    return files, collisions


def compare_with_old(old_index: dict, files: dict):
    """Report how the rebuilt map differs from the index being replaced."""
    old_files = old_index.get("files", {}) if old_index else {}
    declared = old_index.get("tar_file") if old_index else None
    missing_now = [k for k in old_files if k not in files]
    added_now = [k for k in files if k not in old_files]
    moved = wrong_offset = 0
    for name, info in old_files.items():
        new = files.get(name)
        if not new:
            continue
        if new["offset"] != info.get("offset"):
            wrong_offset += 1
        elif declared and new["tar"] != declared:
            moved += 1
    return {
        "old_entries": len(old_files),
        "new_entries": len(files),
        "in_old_but_not_in_tars": len(missing_now),
        "in_tars_but_not_in_old": len(added_now),
        "offset_was_stale": wrong_offset,
        "belonged_to_another_tar": moved,
    }


def verify(archive_dir: str, index: dict, sample: int = 40) -> bool:
    """Read a random sample straight from the recorded offsets."""
    files = index["files"]
    if not files:
        return True
    keys = random.Random(0).sample(list(files), min(sample, len(files)))
    ok = 0
    for key in keys:
        info = files[key]
        tar_path = os.path.join(archive_dir, info["tar"])
        try:
            with open(tar_path, "rb") as fh:
                fh.seek(info["offset"])
                with tarfile.open(fileobj=fh, mode="r:") as tf:
                    member = tf.next()
                    if member is None or member.name != key:
                        continue
                    data = tf.extractfile(member).read()
            if len(data) == info["size"]:
                ok += 1
        except Exception as e:
            print(f"    [ERROR] {key}: {e}")
    print(f"    verify: {ok}/{len(keys)} entries read correctly from their offset")
    return ok == len(keys)


def rebuild(archive_dir: str, dry_run: bool = False) -> bool:
    name = os.path.basename(os.path.normpath(archive_dir))
    print(f"=== {name}", flush=True)
    tar_names = list_tars(archive_dir)
    if not tar_names:
        print("    no tar file, skipped")
        return True

    old_path = find_index(archive_dir)
    old_index = None
    if old_path:
        with open(old_path, "r", encoding="utf-8") as f:
            old_index = json.load(f)

    files, collisions = build_files_map(archive_dir, tar_names)
    if collisions:
        print(f"    note: {collisions} member names appeared in more than one tar; "
              f"kept the copy from the tar scanned last")

    per_tar = {}
    for info in files.values():
        per_tar[info["tar"]] = per_tar.get(info["tar"], 0) + 1
    primary = max(per_tar, key=per_tar.get)

    index = {
        "version": 2,
        "tars": tar_names,
        "tar_file": primary,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": files,
    }

    if old_index is not None:
        diff = compare_with_old(old_index, files)
        for key, value in diff.items():
            print(f"    {key}: {value}")

    if dry_run:
        print("    dry run, nothing written")
        return True

    if not verify(archive_dir, index):
        print("    [ABORT] verification failed, index not written")
        return False

    target = os.path.join(archive_dir, INDEX_NAME)
    if old_path:
        backup = old_path + ".bak"
        if not os.path.exists(backup):
            os.replace(old_path, backup)
            print(f"    previous index kept as {os.path.basename(backup)}")
        elif old_path != target:
            os.remove(old_path)

    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    os.replace(tmp, target)
    print(f"    written: {INDEX_NAME}  ({len(files)} entries, tars={tar_names})")
    return True


def main():
    p = argparse.ArgumentParser(
        description="Rebuild data_index.json by scanning the tars of an archive")
    p.add_argument("--archive", action="append", default=[],
                   help="archive directory (repeatable)")
    p.add_argument("--root", help="rebuild every subdirectory of this directory")
    p.add_argument("--dry-run", action="store_true",
                   help="report differences without writing")
    args = p.parse_args()

    targets = list(args.archive)
    if args.root:
        targets += [os.path.join(args.root, d) for d in sorted(os.listdir(args.root))
                    if os.path.isdir(os.path.join(args.root, d))]
    if not targets:
        raise SystemExit("[ERROR] pass --archive or --root")

    failed = []
    for target in targets:
        if not rebuild(target, args.dry_run):
            failed.append(target)
    if failed:
        raise SystemExit(f"[ERROR] {len(failed)} archive(s) failed: {failed}")


if __name__ == "__main__":
    main()
