"""
TiebaReader backend - FastAPI local reader server.

Start:
    cd server
    uvicorn main:app --reload --port 8900
"""

import json
import os
import sqlite3
import tarfile
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="TiebaReader", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVER_DIR = Path(__file__).parent
SOURCES_FILE = SERVER_DIR / "sources.json"

_sources: list[str] = []
_forums: dict = {}


def _load_sources() -> list[str]:
    """Load saved source paths from sources.json."""
    if SOURCES_FILE.exists():
        try:
            data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [s for s in data if isinstance(s, str)]
        except (json.JSONDecodeError, OSError):
            pass
    fallback = os.environ.get("TIEBA_DATA_DIR")
    return [fallback] if fallback else []


def _save_sources():
    """Persist current source list to sources.json."""
    SOURCES_FILE.write_text(json.dumps(_sources, ensure_ascii=False, indent=2), encoding="utf-8")


_collections: dict = {}  # collection_name -> {source_path, forums: [keys into _forums]}


def _load_forum_from_dir(forum_dir: str, name: str, collection: str = None):
    """Load a single forum directory into _forums.

    Args:
        forum_dir: Path to the forum directory containing master.db
        name: Display name for the forum
        collection: If this forum belongs to a collection, its name
    """
    db_path = os.path.join(forum_dir, "master.db")
    if not os.path.exists(db_path):
        return False
    media_index = {}
    idx_path = os.path.join(forum_dir, "media_index.json")
    if os.path.exists(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            media_index = json.load(f)
    tar_path = os.path.join(forum_dir, "media.tar")

    key = f"{collection}/{name}" if collection else name
    if key in _forums:
        key = f"{collection or 'default'}/{name}_{hash(forum_dir) % 10000}"

    _forums[key] = {
        "db_path": db_path,
        "media_index": media_index,
        "tar_path": tar_path if os.path.exists(tar_path) else None,
        "source_path": os.path.dirname(forum_dir),
        "collection": collection,
        "display_name": name,
    }
    return key


def _is_collection(dir_path: str) -> bool:
    """Determine if a directory is a collection (contains sub-forum dirs but no master.db itself).

    A collection is a directory where:
    - It does NOT have master.db directly
    - At least one of its subdirectories has master.db
    - It doesn't look like a forum name (heuristic: contains no Chinese chars or
      the subdirectories themselves contain master.db at multiple levels)
    """
    if os.path.exists(os.path.join(dir_path, "master.db")):
        return False
    sub_forum_count = 0
    try:
        for sub in os.listdir(dir_path):
            sub_path = os.path.join(dir_path, sub)
            if os.path.isdir(sub_path) and os.path.exists(os.path.join(sub_path, "master.db")):
                sub_forum_count += 1
                if sub_forum_count >= 2:
                    return True
    except OSError:
        pass
    return sub_forum_count >= 1


def discover_forums():
    """Scan all source directories for subdirectories containing master.db.

    Handles two structures:
    - Single forum: source_dir/forum_name/master.db
    - Collection: source_dir/collection_name/forum_a/master.db
                                             /forum_b/master.db
    """
    global _forums, _collections
    _forums = {}
    _collections = {}

    for source_dir in _sources:
        if not os.path.isdir(source_dir):
            continue

        db_direct = os.path.join(source_dir, "master.db")
        if os.path.exists(db_direct):
            name = os.path.basename(source_dir)
            _load_forum_from_dir(source_dir, name)
            continue

        for name in os.listdir(source_dir):
            if name.startswith("_"):
                continue
            sub_dir = os.path.join(source_dir, name)
            if not os.path.isdir(sub_dir):
                continue

            if os.path.exists(os.path.join(sub_dir, "master.db")):
                _load_forum_from_dir(sub_dir, name)
            elif _is_collection(sub_dir):
                collection_forums = []
                for forum_name in os.listdir(sub_dir):
                    forum_dir = os.path.join(sub_dir, forum_name)
                    if os.path.isdir(forum_dir) and not forum_name.startswith("_"):
                        key = _load_forum_from_dir(forum_dir, forum_name, collection=name)
                        if key:
                            collection_forums.append(key)
                if collection_forums:
                    _collections[name] = {
                        "source_path": source_dir,
                        "forums": collection_forums,
                    }

    print(f"Loaded {len(_forums)} forum(s) in {len(_collections)} collection(s): "
          f"standalone={[k for k, v in _forums.items() if not v.get('collection')]}, "
          f"collections={list(_collections.keys())}")


def _resolve_forum(forum: str = None):
    """Resolve a forum identifier (key, display_name, or db forum_name) to its info dict."""
    if not forum:
        return list(_forums.values())[0] if _forums else None

    if forum in _forums:
        return _forums[forum]

    for v in _forums.values():
        if v.get("display_name") == forum:
            return v

    for v in _forums.values():
        try:
            conn = sqlite3.connect(v["db_path"], check_same_thread=False)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT forum_name FROM forum LIMIT 1").fetchone()
            conn.close()
            if row and row["forum_name"] == forum:
                return v
        except Exception:
            pass

    return None


@contextmanager
def get_db(forum: str = None):
    """Get DB connection for a forum. Supports lookup by forum_key, display_name, or db forum_name."""
    info = _resolve_forum(forum)
    if not info:
        if _forums:
            info = list(_forums.values())[0]
        else:
            raise HTTPException(500, "No forum databases loaded")
    conn = sqlite3.connect(info["db_path"], check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    global _sources
    _sources = _load_sources()
    discover_forums()


# --- Source Management ---


class SourceRequest(BaseModel):
    path: str


@app.get("/api/sources")
def list_sources():
    """List all configured archive source directories."""
    return {"sources": _sources, "forums_loaded": len(_forums)}


@app.post("/api/sources")
def add_source(req: SourceRequest):
    """Add a new archive source directory. Validates and loads forums from it."""
    path = req.path.strip()
    if not path:
        raise HTTPException(400, "Path cannot be empty")
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise HTTPException(400, f"Directory does not exist: {path}")

    has_db = os.path.exists(os.path.join(path, "master.db"))
    has_sub = any(
        os.path.exists(os.path.join(path, d, "master.db"))
        for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d))
    ) if not has_db else False

    if not has_db and not has_sub:
        raise HTTPException(400, "No master.db found in directory or its subdirectories")

    if path not in _sources:
        _sources.append(path)
        _save_sources()

    discover_forums()
    return {"sources": _sources, "forums_loaded": len(_forums)}


@app.delete("/api/sources")
def remove_source(req: SourceRequest):
    """Remove an archive source directory."""
    path = os.path.abspath(req.path.strip())
    _sources[:] = [s for s in _sources if os.path.abspath(s) != path]
    _save_sources()
    discover_forums()
    return {"sources": _sources, "forums_loaded": len(_forums)}


# --- API Routes ---


@app.get("/api/forums")
def list_forums():
    results = []
    for forum_key, info in _forums.items():
        try:
            conn = sqlite3.connect(info["db_path"], check_same_thread=False)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT f.forum_id, f.forum_name, f.member_num, f.post_num, f.thread_num, f.slogan
                   FROM forum f LIMIT 1"""
            ).fetchone()
            thread_count = conn.execute("SELECT COUNT(*) FROM thread").fetchone()[0]
            conn.close()

            db_forum_name = row["forum_name"] if row and row["forum_name"] else info.get("display_name", forum_key)
            results.append({
                "forum_id": row["forum_id"] if row else 0,
                "forum_key": forum_key,
                "forum_name": db_forum_name,
                "collection": info.get("collection"),
                "member_num": row["member_num"] if row else 0,
                "post_num": row["post_num"] if row else 0,
                "thread_num": row["thread_num"] if row else 0,
                "slogan": row["slogan"] if row else "",
                "archived_threads": thread_count,
                "media_files": len(info["media_index"].get("files", {})),
            })
        except Exception:
            results.append({
                "forum_key": forum_key,
                "forum_name": info.get("display_name", forum_key),
                "collection": info.get("collection"),
                "archived_threads": 0,
            })

    return sorted(results, key=lambda x: x.get("archived_threads", 0), reverse=True)


@app.get("/api/collections")
def list_collections():
    """List all detected collections and their contained forums."""
    result = []
    for name, coll in _collections.items():
        result.append({
            "name": name,
            "forum_count": len(coll["forums"]),
            "forums": coll["forums"],
        })
    return result


@app.get("/api/stats")
def get_stats():
    total_threads = 0
    total_posts = 0
    total_users = 0
    earliest = None
    latest = None

    for info in _forums.values():
        try:
            conn = sqlite3.connect(info["db_path"], check_same_thread=False)
            total_threads += conn.execute("SELECT COUNT(*) FROM thread").fetchone()[0]
            total_posts += conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
            total_users += conn.execute("SELECT COUNT(DISTINCT portrait) FROM user").fetchone()[0]
            e = conn.execute("SELECT MIN(create_time) FROM thread WHERE create_time > 0").fetchone()[0]
            l = conn.execute("SELECT MAX(create_time) FROM thread").fetchone()[0]
            if e and (earliest is None or e < earliest):
                earliest = e
            if l and (latest is None or l > latest):
                latest = l
            conn.close()
        except Exception:
            pass

    media_count = sum(len(v["media_index"].get("files", {})) for v in _forums.values())

    return {
        "forums": len(_forums),
        "threads": total_threads,
        "posts": total_posts,
        "users": total_users,
        "earliest_time": earliest,
        "latest_time": latest,
        "media_files": media_count,
    }


@app.get("/api/threads")
def list_threads(
    forum: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: Optional[str] = None,
    sort: str = Query("create_time", pattern="^(create_time|reply_num|view_num|agree)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    offset = (page - 1) * page_size

    with get_db(forum) as db:
        if q:
            count_row = db.execute(
                "SELECT COUNT(*) FROM post_fts WHERE contents MATCH ?",
                (q,),
            ).fetchone()
            total = count_row[0]

            rows = db.execute(
                """SELECT DISTINCT pf.tid, t.title, t.forum_name, t.view_num, t.reply_num,
                          t.agree, t.create_time, t.status,
                          snippet(post_fts, 3, '<mark>', '</mark>', '...', 32) as snippet
                   FROM post_fts pf
                   JOIN thread t ON t.tid = pf.tid
                   WHERE pf.contents MATCH ?
                   ORDER BY rank
                   LIMIT ? OFFSET ?""",
                (q, page_size, offset),
            ).fetchall()
        else:
            count_row = db.execute("SELECT COUNT(*) FROM thread").fetchone()
            total = count_row[0]

            rows = db.execute(
                f"""SELECT tid, title, forum_name, view_num, reply_num,
                           agree, create_time, status
                    FROM thread
                    ORDER BY {sort} {order}
                    LIMIT ? OFFSET ?""",
                [page_size, offset],
            ).fetchall()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [dict(r) for r in rows],
        }


@app.get("/api/thread/{tid}")
def get_thread(tid: int, forum: Optional[str] = None):
    # Find which forum this tid belongs to
    target_forum = forum
    if not target_forum:
        for fname, info in _forums.items():
            conn = sqlite3.connect(info["db_path"], check_same_thread=False)
            exists = conn.execute("SELECT 1 FROM thread WHERE tid = ?", (tid,)).fetchone()
            conn.close()
            if exists:
                target_forum = fname
                break

    if not target_forum:
        raise HTTPException(404, "Thread not found in any forum")

    with get_db(target_forum) as db:
        thread = db.execute("SELECT * FROM thread WHERE tid = ?", (tid,)).fetchone()
        if not thread:
            raise HTTPException(404, "Thread not found")

        posts = db.execute(
            """SELECT id, floor, contents, user_id, agree, disagree,
                      create_time, is_thread_author, sign, reply_num, parent_id, reply_to_id
               FROM post WHERE tid = ? AND parent_id = 0
               ORDER BY floor ASC""",
            (tid,),
        ).fetchall()

        sub_posts = db.execute(
            """SELECT id, floor, contents, user_id, agree, disagree,
                      create_time, is_thread_author, sign, parent_id, reply_to_id
               FROM post WHERE tid = ? AND parent_id != 0
               ORDER BY id ASC""",
            (tid,),
        ).fetchall()

        # Check if user_id column exists (older merged DBs may lack it)
        user_cols = {r[1] for r in db.execute("PRAGMA table_info('user')").fetchall()}
        if "user_id" in user_cols:
            users = db.execute(
                """SELECT portrait, nickname, username, avatar, level, gender, ip, is_vip, user_id
                   FROM user WHERE tid = ?""",
                (tid,),
            ).fetchall()
        else:
            users = db.execute(
                """SELECT portrait, nickname, username, avatar, level, gender, ip, is_vip
                   FROM user WHERE tid = ?""",
                (tid,),
            ).fetchall()

    # Media file list
    media_files = []
    forum_info = _forums.get(target_forum, {})
    for path in forum_info.get("media_index", {}).get("files", {}):
        if path.startswith(f"{tid}/"):
            media_files.append(path)

    # Build users dict keyed by user_id for direct post.user_id lookup
    users_dict = {}
    for r in users:
        u = dict(r)
        uid = u.get("user_id", 0)
        if uid:
            users_dict[str(uid)] = u
        users_dict[u["portrait"]] = u

    return {
        "thread": dict(thread),
        "forum_dir": target_forum,
        "posts": [dict(p) for p in posts],
        "sub_posts": [dict(p) for p in sub_posts],
        "users": users_dict,
        "media_files": media_files,
    }


@app.get("/api/media/{forum}/{path:path}")
def get_media(forum: str, path: str):
    """Read media file on demand from tar archive."""
    if forum not in _forums:
        raise HTTPException(404, f"Forum '{forum}' not found")

    forum_info = _forums[forum]
    file_info = forum_info["media_index"].get("files", {}).get(path)

    if not file_info:
        raise HTTPException(404, f"Media file '{path}' not found")

    tar_path = forum_info["tar_path"]
    if not tar_path or not os.path.exists(tar_path):
        raise HTTPException(500, "Tar file not found")

    try:
        with tarfile.open(tar_path, "r:") as tf:
            member = None
            for m in tf:
                if m.name == path:
                    member = m
                    break

            if member is None:
                raise HTTPException(404, "File not found in tar")

            f = tf.extractfile(member)
            if f is None:
                raise HTTPException(500, "Cannot extract file")

            data = f.read()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error reading media: {e}")

    ext = os.path.splitext(path)[1].lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    return Response(content=data, media_type=content_type, headers={
        "Cache-Control": "public, max-age=31536000",
    })


@app.get("/api/search/suggest")
def search_suggest(q: str = Query(..., min_length=1)):
    """Search suggestions across all forums by thread title."""
    results = []
    for forum_name, info in _forums.items():
        try:
            conn = sqlite3.connect(info["db_path"], check_same_thread=False)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT tid, title, forum_name FROM thread WHERE title LIKE ? LIMIT 5",
                (f"%{q}%",),
            ).fetchall()
            results.extend(dict(r) for r in rows)
            conn.close()
        except Exception:
            pass
    return results[:10]


@app.get("/api/thread/{tid}/timeline")
def get_thread_timeline(tid: int, forum: Optional[str] = None):
    """Get thread timeline."""
    target_forum = forum
    if not target_forum:
        for fname, info in _forums.items():
            conn = sqlite3.connect(info["db_path"], check_same_thread=False)
            if conn.execute("SELECT 1 FROM thread WHERE tid = ?", (tid,)).fetchone():
                target_forum = fname
            conn.close()
            if target_forum:
                break

    if not target_forum:
        raise HTTPException(404, "Thread not found")

    with get_db(target_forum) as db:
        rows = db.execute(
            """SELECT id, floor, contents, user_id, create_time,
                      is_thread_author, parent_id
               FROM post WHERE tid = ?
               ORDER BY create_time ASC""",
            (tid,),
        ).fetchall()
        return [dict(r) for r in rows]
