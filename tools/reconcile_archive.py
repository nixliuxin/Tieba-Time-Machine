r"""
reconcile_archive.py - 对账并增量修复归档中"已完成但其实缺页"的帖子。

背景
----
旧版抓取器在回复分页被限流/网络失败时会静默跳过，并仍把帖子标记为 done。
这些帖子进入 master.db 后，楼层数会明显少于 reply_num（末尾整页缺失或中间整页缺失）。
本工具负责：
  1. audit  : 只读扫描 master.db（必要时核对 data.tar 内的抓取日志），找出可疑 tid。
  2. prepare: 把可疑 tid 准备成一次"只抓这些帖子"的重抓任务（生成/修改 raw 目录）。
  3. heal   : 把重抓得到的 raw 数据增量并回已存在的归档（master.db + data.tar）。

整个流程是幂等的、仅追加的、可断点续跑的：
  - post 主键 (tid, id) + INSERT OR IGNORE → 缺失楼层被补入，已存在的被忽略，绝不重复。
  - 媒体按 data_index.json 内的 internal_path 去重 → 只追加恢复出来的新文件。

用法
----
  # 1) 对账（只读，快）
  python reconcile_archive.py audit --archive "<...>/Ba_xxx_YYMMDD"

  # 2) 把可疑帖子准备成重抓任务
  #    (a) 归档对应的 raw 目录还在：直接把可疑 tid 从 _done_tids.json 移除
  python reconcile_archive.py prepare --suspects "<archive>/_reconcile.json" --raw "./data/<forum-name>"
  #    (b) raw 已删除：在一个新目录里生成只含可疑 tid 的抓取任务
  python reconcile_archive.py prepare --suspects "<archive>/_reconcile.json" --new-raw "./data/_rescrape_<forum-name>" --forum "<forum-name>"

  # 3) 跑抓取器把缺失帖子补齐（只会抓 prepare 出来的那些 tid）
  python ..\scraper\backup_forum.py "<forum-name>" "./data/_rescrape_<forum-name>" --concurrency 5

  # 4) 把重抓结果增量并回原归档
  python reconcile_archive.py heal --archive "<...>/Ba_<forum>_YYMMDD" --raw "./data/_rescrape_<forum-name>" --suspects "<archive>/_reconcile.json"
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import merge_archive as ma  # 复用结构化合并 / 资源打包逻辑


DEFAULT_GAP = 20          # 末尾/中间缺失楼层数达到该阈值才视为"缺页"
RECONCILE_FILE = "_reconcile.json"


# ────────────────────────── 对账 (audit) ──────────────────────────
def _find_master_db(archive_dir: str) -> str:
    db = os.path.join(archive_dir, "master.db")
    if not os.path.exists(db):
        raise SystemExit(f"[ERROR] master.db 不存在: {db}")
    return db


def _load_data_index(archive_dir: str) -> dict:
    for name in ("data_index.json", "media_index.json"):
        p = os.path.join(archive_dir, name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return {"files": {}}


def _read_tar_member_at(tar_path: str, offset: int) -> bytes | None:
    """直接 seek 到 tar 内某成员的偏移并只解析这一个成员（避免全表扫描）。"""
    try:
        with open(tar_path, "rb") as f:
            f.seek(offset)
            with tarfile.open(fileobj=f, mode="r:") as tf:
                m = tf.next()
                if m is None:
                    return None
                ef = tf.extractfile(m)
                return ef.read() if ef else None
    except Exception:
        return None


def _log_says_page_lost(archive_dir: str, index: dict, tid: int) -> bool:
    """检查 data.tar 内该 tid 的抓取日志是否记录了丢页（确定性信号，旧日志可能没有）。"""
    files = index.get("files", {})
    tar_path = os.path.join(archive_dir, index.get("tar_file", "data.tar"))
    if not os.path.exists(tar_path):
        return False
    prefix = f"{tid}/scrape."
    for internal_path, info in files.items():
        if not (internal_path.startswith(prefix) and internal_path.endswith(".log")):
            continue
        data = _read_tar_member_at(tar_path, info.get("offset", -1))
        if not data:
            continue
        text = data.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            if "FetchPosts" in line and ("Request failed" in line or "Thread unavailable" in line):
                return True
    return False


def _compute_stats(conn: sqlite3.Connection) -> dict:
    """一次性拿到每个 tid 的：楼数(parent_id=0)、楼中楼数(parent_id!=0)、
    最大楼层号、楼层号序列中的最大连续缺口。

    注意区分"楼"和"楼中楼"：
      - 楼(parent_id=0)   有连续楼层号 1..N
      - 楼中楼(parent_id!=0) 挂在某楼下，不计入楼层号序列
    百度的 thread.reply_num = 楼 + 楼中楼（实测，不含楼主），所以"应有回复数"用 reply_num，
    "实存回复数"用 楼数+楼中楼数，同口径比较才准确。
    """
    stats = {}
    cur = conn.execute(
        """SELECT tid,
                  SUM(CASE WHEN parent_id=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN parent_id!=0 THEN 1 ELSE 0 END),
                  MAX(CASE WHEN parent_id=0 THEN floor ELSE 0 END)
           FROM post GROUP BY tid"""
    )
    for tid, fs, cm, mf in cur:
        stats[tid] = {"floors": fs or 0, "comments": cm or 0, "max_floor": mf or 0, "max_gap": 0}

    # 楼层号序列里的最大连续缺口（窗口函数一次算完所有 tid）——只看"楼"。
    # 完全不依赖 reply_num，是"丢了中间整页"的最可靠信号。
    try:
        gcur = conn.execute(
            """SELECT tid, MAX(gap) FROM (
                   SELECT tid,
                          floor - LAG(floor) OVER (PARTITION BY tid ORDER BY floor) - 1 AS gap
                   FROM post WHERE parent_id=0
               ) GROUP BY tid"""
        )
        for tid, g in gcur:
            if tid in stats and g:
                stats[tid]["max_gap"] = g
    except sqlite3.OperationalError:
        pass  # 旧版 SQLite 无窗口函数则跳过缺口分析
    return stats


def cmd_audit(args):
    archive_dir = args.archive
    db_path = _find_master_db(archive_dir)
    gap = args.gap_threshold

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA query_only = ON")

    total = conn.execute("SELECT COUNT(*) FROM thread").fetchone()[0]
    status0 = conn.execute("SELECT COUNT(*) FROM thread WHERE scrape_status=0").fetchone()[0]
    print(f"  归档: {os.path.basename(archive_dir)}")
    print(f"  thread 总数 {total} | 完整抓取(status=0) {status0} | gap 阈值 {gap}")

    stats = _compute_stats(conn)
    index = _load_data_index(archive_dir) if args.check_logs else {"files": {}}

    suspects = []
    # 1) status=0 完整抓取：按 missing(楼+楼中楼 同口径) 找缺页
    for tid, reply_num, title in conn.execute(
        "SELECT tid, reply_num, title FROM thread WHERE scrape_status=0"
    ):
        reply_num = reply_num or 0
        st = stats.get(tid, {"floors": 0, "comments": 0, "max_floor": 0, "max_gap": 0})
        fs, cm, mf, mg = st["floors"], st["comments"], st["max_floor"], st["max_gap"]
        saved_total = fs + cm                 # 实存回复(楼+楼中楼)
        missing = reply_num - saved_total     # 与 reply_num 同口径，唯一可靠的"少了多少"

        # 判定（以 missing 为准）：
        #  - empty   : reply_num>0 却一个楼都没有
        #  - 否则 missing<阈值 → 不算可疑（楼层号缺口若 missing≈0，是删帖跳号，帖子其实完整）
        #  reason 标签:
        #    page-gap(N) : missing 大 且 楼层号有 ≥阈值的连续缺口 → 更像丢了中间整页
        #    short       : missing 大 但楼层号连续 → 末尾截断 / 楼中楼丢失 / 历史删除(重抓最终区分)
        reason = None
        if fs == 0 and reply_num > 0:
            reason = "empty"
        elif missing >= gap:
            reason = f"page-gap({mg})" if mg >= gap else "short"
            if args.check_logs and _log_says_page_lost(archive_dir, index, tid):
                reason = "log-confirmed"
        if reason:
            suspects.append({
                "tid": tid, "title": (title or "")[:60], "reply_num": reply_num,
                "floors_saved": fs, "comments_saved": cm, "max_floor": mf,
                "max_gap": mg, "missing": missing, "reason": reason,
            })

    # 2) status=1 历史"已删除"：旧版抓取器会把限流误判为删除，全部重新核实
    #    （真删除重抓时百度会回 TiebaServerError → 仍记 deleted；假删除会救回并改 status=0）
    if not args.skip_deleted:
        for tid, reply_num, title in conn.execute(
            "SELECT tid, reply_num, title FROM thread WHERE scrape_status=1"
        ):
            suspects.append({
                "tid": tid, "title": (title or "")[:60], "reply_num": reply_num or 0,
                "floors_saved": 0, "comments_saved": 0, "max_floor": 0,
                "max_gap": 0, "missing": reply_num or 0, "reason": "verify-del",
            })

    # 3) status=2 失败/不完整：重试补齐
    for tid, reply_num, title in conn.execute(
        "SELECT tid, reply_num, title FROM thread WHERE scrape_status=2"
    ):
        st = stats.get(tid, {"floors": 0, "comments": 0})
        saved_total = st["floors"] + st["comments"]
        suspects.append({
            "tid": tid, "title": (title or "")[:60], "reply_num": reply_num or 0,
            "floors_saved": st["floors"], "comments_saved": st["comments"], "max_floor": 0,
            "max_gap": 0, "missing": (reply_num or 0) - saved_total, "reason": "retry-failed",
        })

    suspects.sort(key=lambda s: s["missing"], reverse=True)

    def _n(pred):
        return sum(1 for s in suspects if pred(s["reason"]))
    n_pagegap = _n(lambda r: r.startswith("page-gap"))
    n_short = _n(lambda r: r == "short")
    n_empty = _n(lambda r: r == "empty")
    n_vdel = _n(lambda r: r == "verify-del")
    n_fail = _n(lambda r: r == "retry-failed")
    print(f"  可疑帖子: {len(suspects)}  (page-gap={n_pagegap} 丢页 | short={n_short} | empty={n_empty} | "
          f"verify-del={n_vdel} 核实删除 | retry-failed={n_fail})")
    for s in suspects[:25]:
        print(f"    tid={s['tid']:>12}  reply={s['reply_num']:>6}  楼={s['floors_saved']:>5}  "
              f"楼中楼={s['comments_saved']:>5}  缺={s['missing']:>6}  "
              f"[{s['reason']}]  {s['title']}")
    if len(suspects) > 25:
        print(f"    ... 其余 {len(suspects)-25} 条见 {RECONCILE_FILE}")

    # 确定重抓标签：单吧备份用真实吧名；User 合集（帖子跨多个吧）用归档目录名，
    # 避免拿其中某个子吧（如 108_步的距离）当整个合集的标签造成歧义。
    forums = [r[0] for r in conn.execute(
        "SELECT DISTINCT forum_name FROM thread WHERE forum_name != ''")]
    conn.close()
    archive_label = os.path.basename(os.path.normpath(archive_dir))
    is_collection = len(forums) > 1
    if is_collection:
        forum_name = archive_label          # e.g. User_<name>_YYMMDD
    elif len(forums) == 1:
        forum_name = forums[0]
    else:
        forum_name = archive_label

    out = {
        "archive": archive_label,
        "forum": forum_name,
        "is_collection": is_collection,
        "sub_forums": forums if is_collection else None,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gap_threshold": gap,
        "checked_logs": bool(args.check_logs),
        "count": len(suspects),
        "tids": [s["tid"] for s in suspects],
        "suspects": suspects,
    }
    out_path = os.path.join(archive_dir, RECONCILE_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  已写入: {out_path}")
    if is_collection:
        print(f"  合集标签: {forum_name}  (跨 {len(forums)} 个吧，按 tid 逐帖重抓)")
    elif forum_name:
        print(f"  吧名: {forum_name}")


# ────────────────────────── 准备重抓 (prepare) ──────────────────────────
def _load_suspect_tids(suspects_path: str) -> list[int]:
    with open(suspects_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return list(data.get("tids", []))
    if isinstance(data, list):
        return [int(x) for x in data]
    raise SystemExit(f"[ERROR] 无法解析可疑列表: {suspects_path}")


def cmd_prepare(args):
    tids = _load_suspect_tids(args.suspects)
    if not tids:
        print("  没有可疑 tid，无需重抓。")
        return

    if args.raw:
        # 情况 a：raw 目录还在，把可疑 tid 从 _done_tids.json 移除并清理残留文件夹，
        # 下次抓取器循环会把它们当作 fresh 重新抓。
        raw = args.raw
        done_file = os.path.join(raw, "_done_tids.json")
        if not os.path.exists(done_file):
            raise SystemExit(f"[ERROR] {done_file} 不存在；若 raw 已删除请用 --new-raw")
        with open(done_file, "r", encoding="utf-8") as f:
            done = set(json.load(f))
        removed = [t for t in tids if t in done]
        done.difference_update(removed)
        with open(done_file, "w", encoding="utf-8") as f:
            json.dump(sorted(done), f)
        # 同时从 _progress.json 的 deleted 集合移除（以防误判为已删除而被跳过）
        prog_file = os.path.join(raw, "_progress.json")
        if os.path.exists(prog_file):
            with open(prog_file, "r", encoding="utf-8") as f:
                prog = json.load(f)
            before = len(prog.get("deleted", []))
            prog["deleted"] = sorted(set(prog.get("deleted", [])) - set(tids))
            for t in tids:
                prog.get("failed_details", {}).pop(str(t), None)
            with open(prog_file, "w", encoding="utf-8") as f:
                json.dump(prog, f, ensure_ascii=False, indent=2)
            if before != len(prog["deleted"]):
                print(f"  从 deleted 集合移除 {before - len(prog['deleted'])} 个")
        # 清理残留文件夹，保证重抓是干净的全量
        cleaned = 0
        for name in os.listdir(raw):
            for t in removed:
                if f"[{t}]" in name and os.path.isdir(os.path.join(raw, name)):
                    import shutil
                    shutil.rmtree(os.path.join(raw, name), ignore_errors=True)
                    cleaned += 1
        print(f"  raw={raw}")
        print(f"  从 _done_tids.json 移除 {len(removed)} / {len(tids)} 个；清理残留文件夹 {cleaned} 个")
        print(f"  → 让正在跑的抓取器自然重抓，或运行:")
        print(f"    python ..\\scraper\\backup_forum.py {args.forum or '<吧名>'} \"{raw}\" --concurrency 5")
    else:
        # 情况 b：raw 已删，新建一个"只抓这些 tid"的任务目录
        new_raw = args.new_raw
        if not new_raw or not args.forum:
            raise SystemExit("[ERROR] --new-raw 模式需要同时提供 --forum <吧名>")
        os.makedirs(new_raw, exist_ok=True)
        with open(os.path.join(new_raw, "_meta.json"), "w", encoding="utf-8") as f:
            json.dump({"forum": args.forum, "type": "forum",
                       "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "note": "reconcile re-scrape (subset)"}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(new_raw, "_all_tids.json"), "w", encoding="utf-8") as f:
            json.dump({"all_tids": sorted(tids),
                       "collected_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f,
                      ensure_ascii=False, indent=2)
        print(f"  new-raw={new_raw} (吧={args.forum}, {len(tids)} 个 tid)")
        print(f"  → 运行抓取器只抓这些帖子:")
        print(f"    python ..\\scraper\\backup_forum.py {args.forum} \"{new_raw}\" --concurrency 5")


# ────────────────────────── 增量修复 (heal) ──────────────────────────
def cmd_heal(args):
    archive_dir = args.archive
    raw = args.raw
    db_path = _find_master_db(archive_dir)
    tids = set(_load_suspect_tids(args.suspects)) if args.suspects else None

    # 找到 raw 里重抓出来的帖子文件夹
    threads = ma.find_thread_dirs(raw)
    if tids is not None:
        threads = [t for t in threads if t[2] in tids]
    if not threads:
        print("  raw 中没有匹配的重抓帖子，结束。")
        return
    print(f"  待并回 {len(threads)} 个帖子 → {os.path.basename(archive_dir)}")

    conn = ma.init_master_db(db_path, bulk_import=True)
    try:
        conn.execute("SELECT scrape_status FROM thread LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE thread ADD COLUMN scrape_status INTEGER DEFAULT 0")
        conn.commit()

    # 清除这些 tid 的合并守卫，让结构化数据重新并入（INSERT OR IGNORE 只补缺）
    heal_tids = {t[2] for t in threads}
    for tid in heal_tids:
        conn.execute("DELETE FROM merge_progress WHERE tid=?", (tid,))
    conn.commit()

    # data.tar：保留已有 index，按 internal_path 去重，只追加恢复出来的新文件
    index_path = os.path.join(archive_dir, "data_index.json")
    index_data = {"tar_file": "data.tar", "files": {}}
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
            index_data.setdefault("tar_file", "data.tar")
            index_data.setdefault("files", {})

    tar_full = os.path.join(archive_dir, index_data.get("tar_file", "data.tar"))
    tar_mode = "a" if os.path.exists(tar_full) else "w"
    tf = tarfile.open(tar_full, f"{tar_mode}:")

    new_posts_before = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
    new_assets = 0
    errors = 0
    try:
        for folder_path, forum_name, tid, folder_name in threads:
            thread_dir = os.path.join(folder_path, "threads", str(tid))
            if not os.path.isdir(thread_dir):
                thread_dir = folder_path
            try:
                thread_json = os.path.join(thread_dir, "thread.json")
                forum_json = os.path.join(thread_dir, "forum.json")
                content_db = os.path.join(thread_dir, "content.db")
                scrape_info_file = os.path.join(folder_path, "scrape_info.json")
                if not os.path.exists(scrape_info_file):
                    scrape_info_file = os.path.join(thread_dir, "scrape_info.json")

                ma.merge_forum_json(conn, forum_json, forum_name)
                ma.merge_thread_json(conn, thread_json, tid, forum_name, folder_name)
                ma.merge_content_db(conn, content_db, tid)
                ma.merge_scrape_info(conn, scrape_info_file, tid)
                conn.execute(
                    "INSERT OR IGNORE INTO merge_progress (tid, forum_name, merged_at) VALUES (?, ?, ?)",
                    (tid, forum_name, int(time.time())),
                )

                for disk_path, internal_path in ma._collect_asset_files(folder_path, tid):
                    if internal_path in index_data["files"]:
                        continue  # 已有，跳过（去重）
                    try:
                        info = tf.gettarinfo(disk_path, arcname=internal_path)
                        offset = tf.offset
                        with open(disk_path, "rb") as fh:
                            tf.addfile(info, fh)
                        index_data["files"][internal_path] = {"offset": offset, "size": info.size}
                        new_assets += 1
                    except (PermissionError, OSError):
                        pass
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  [ERROR] tid={tid}: {e}")
                continue
    finally:
        tf.close()
    conn.commit()

    tmp = index_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False)
    os.replace(tmp, index_path)

    # 按真相回写 scrape_status：救回来(现在有楼)的历史删除/失败帖 → 改为 0(完整抓取)。
    # 百度确认删除的帖子重抓时会抛 ThreadUnavailable、raw 里没有它的文件夹，因此不会进
    # heal_tids，scrape_status 维持 1(deleted) 不变——真实记录。
    revived = 0
    for tid in heal_tids:
        row = conn.execute("SELECT scrape_status FROM thread WHERE tid=?", (tid,)).fetchone()
        if row is None or row[0] == 0:
            continue
        has_posts = conn.execute("SELECT 1 FROM post WHERE tid=? LIMIT 1", (tid,)).fetchone()
        if has_posts:
            conn.execute("UPDATE thread SET scrape_status=0 WHERE tid=?", (tid,))
            revived += 1
    if revived:
        conn.commit()

    new_posts_after = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
    added = new_posts_after - new_posts_before
    print(f"  新增楼层/回复 {added} 条，新增媒体 {new_assets} 个，复活(误删/失败→完整) {revived} 帖"
          + (f"，错误 {errors}" if errors else ""))

    # 楼层补齐后重建 FTS（幂等：数量一致则跳过）
    total_posts = new_posts_after
    ma.build_fts_index(conn, total_posts)
    conn.close()
    print(f"  heal 完成: {os.path.basename(archive_dir)}")


# ────────────────────────── 一条龙 (run) ──────────────────────────
def _count_failed(work_dir: str) -> int:
    pf = os.path.join(work_dir, "_progress.json")
    if not os.path.exists(pf):
        return -1
    with open(pf, "r", encoding="utf-8") as f:
        return len(json.load(f).get("failed_details", {}))


def cmd_run(args):
    """audit → prepare → 循环重抓到收敛 → heal → 复核，一条命令跑完一个吧。"""
    me = [sys.executable, os.path.abspath(__file__)]
    scraper_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scraper")
    scraper = os.path.join(scraper_dir, "backup_forum.py")
    recon = os.path.join(args.archive, RECONCILE_FILE)

    print(f"\n########## RUN {os.path.basename(args.archive)} ##########", flush=True)
    audit_cmd = me + ["audit", "--archive", args.archive]
    if getattr(args, "skip_deleted", False):
        audit_cmd.append("--skip-deleted")
    subprocess.run(audit_cmd, check=True)
    with open(recon, "r", encoding="utf-8") as f:
        j = json.load(f)
    forum = args.forum or j.get("forum")
    if j.get("count", 0) == 0:
        print("  无可疑帖，跳过。", flush=True)
        return
    if not forum:
        raise SystemExit("[ERROR] 无法确定吧名，请用 --forum 指定")

    subprocess.run(me + ["prepare", "--suspects", recon, "--new-raw", args.work, "--forum", forum], check=True)

    # 循环重抓直到 failed_details 为空（或达到 max_rounds）。
    # 轮次间冷却让真限流有时间恢复；第 2 轮起若"冷却后重抓仍未减少失败数"，
    # 说明剩下的是顽固失败页（持续限流/该页本身取不到），停止以免空转。
    for r in range(1, args.max_rounds + 1):
        nf = _count_failed(args.work)
        if nf == 0:
            print(f"  [收敛] 已无失败项", flush=True)
            break
        if r > 1:
            print(f"  [冷却] {args.cooldown}s 让限流恢复 ...", flush=True)
            time.sleep(args.cooldown)
        print(f"  [Round {r}/{args.max_rounds}] failed={nf}，开始重抓 (concurrency={args.concurrency})", flush=True)
        subprocess.run([sys.executable, "-u", scraper, forum, args.work,
                        "--concurrency", str(args.concurrency)], cwd=scraper_dir)
        nf_after = _count_failed(args.work)
        if nf_after == 0:
            print(f"  [收敛] 第 {r} 轮后无失败项", flush=True)
            break
        if r >= 2 and nf_after >= nf:
            print(f"  [停止] 冷却后重抓仍未减少失败（{nf}→{nf_after}），剩余为顽固失败页", flush=True)
            break

    nf = _count_failed(args.work)
    if nf > 0:
        print(f"  [注意] 仍有 {nf} 个帖子重抓后失败（持续限流/顽固页），先 heal 已得到的部分", flush=True)

    subprocess.run(me + ["heal", "--archive", args.archive, "--raw", args.work, "--suspects", recon], check=True)
    print(f"  --- 复核 ---", flush=True)
    recheck = me + ["audit", "--archive", args.archive]
    if getattr(args, "skip_deleted", False):
        recheck.append("--skip-deleted")
    subprocess.run(recheck, check=True)


def main():
    p = argparse.ArgumentParser(description="对账并增量修复归档中缺页的帖子")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("audit", help="只读扫描 master.db，找出可疑帖子")
    pa.add_argument("--archive", required=True, help="归档目录（含 master.db）")
    pa.add_argument("--gap-threshold", type=int, default=DEFAULT_GAP,
                    help=f"末尾/中间缺失楼层达到该值才算缺页（默认 {DEFAULT_GAP}）")
    pa.add_argument("--check-logs", action="store_true",
                    help="对不确定的帖子核对 data.tar 内抓取日志（较慢）")
    pa.add_argument("--skip-deleted", action="store_true",
                    help="不重新核实历史 status=1（已删除）帖子")
    pa.set_defaults(func=cmd_audit)

    pp = sub.add_parser("prepare", help="把可疑 tid 准备成一次重抓任务")
    pp.add_argument("--suspects", required=True, help="audit 生成的 _reconcile.json")
    pp.add_argument("--raw", help="已存在的 raw 目录（从 _done_tids.json 移除可疑 tid）")
    pp.add_argument("--new-raw", help="raw 已删时，新建只含可疑 tid 的任务目录")
    pp.add_argument("--forum", help="吧名（--new-raw 模式必填）")
    pp.set_defaults(func=cmd_prepare)

    ph = sub.add_parser("heal", help="把重抓得到的 raw 数据增量并回归档")
    ph.add_argument("--archive", required=True, help="已存在的归档目录（含 master.db）")
    ph.add_argument("--raw", required=True, help="重抓产出的 raw 目录")
    ph.add_argument("--suspects", help="只并回这些 tid（默认并回 raw 中全部）")
    ph.set_defaults(func=cmd_heal)

    pr = sub.add_parser("run", help="一条龙: audit→prepare→循环重抓到收敛→heal→复核")
    pr.add_argument("--archive", required=True, help="已存在的归档目录（含 master.db）")
    pr.add_argument("--work", required=True, help="重抓用的临时 raw 目录")
    pr.add_argument("--forum", help="吧名（默认从归档读取）")
    pr.add_argument("--concurrency", type=int, default=3, help="重抓并发（默认 3，偏保守以减少限流）")
    pr.add_argument("--max-rounds", type=int, default=4, help="最多重抓轮数（默认 4）")
    pr.add_argument("--cooldown", type=int, default=60, help="轮次间冷却秒数（默认 60，让限流恢复）")
    pr.add_argument("--skip-deleted", action="store_true",
                    help="不重新核实历史 status=1（已删除）帖子")
    pr.set_defaults(func=cmd_run)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
