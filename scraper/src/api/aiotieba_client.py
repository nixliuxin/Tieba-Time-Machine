import asyncio

import aiotieba as tb
from aiotieba.exception import TiebaServerError

from scrape_config import ScrapeConfig, PostFilterType
from tieba_auth import TiebaAuth
from utils.msg_printer import MsgPrinter


class ThreadUnavailable(Exception):
    """Server positively reports the thread is deleted / blocked / nonexistent.

    This is a PERMANENT condition (TiebaServerError). The caller should mark the
    thread as deleted and never retry it.
    """


class FetchIncomplete(Exception):
    """A transient failure (rate limit / network) prevented a complete fetch.

    The caller should mark the thread as failed-but-retryable so a later run can
    pick it up again. NEVER treat this as a deletion.
    """


# Exponential backoff between retries (seconds). Real backoff, not spin-retry,
# so that 429 rate limits actually get a chance to clear.
_BACKOFF_BASE = 3
_BACKOFF_MAX = 60


def _is_permanent_error(err) -> bool:
    """True only when the server explicitly rejected the request (errorno set).

    A TiebaServerError means Baidu answered "this does not exist / is blocked".
    Everything else (HTTPStatusError 429, timeouts, connection errors, or an
    empty body with no error) is treated as transient and therefore retryable.
    """
    return isinstance(err, TiebaServerError)


async def get_forum(fname_or_fid: str | int, retry=3):
    failures = 0
    while failures < retry:
        async with tb.Client(TiebaAuth.BDUSS) as client:
            forum = await client.get_forum(fname_or_fid)
            if forum and forum.fid != 0:
                return forum
            else:
                failures += 1
                MsgPrinter.print_error(
                    f"Request failed ({failures}/{retry})", "FetchForum", ["fname_or_fid", fname_or_fid]
                )

    return None


async def get_forum_detail(fname_or_fid: str | int, retry=3):
    failures = 0
    while failures < retry:
        async with tb.Client(TiebaAuth.BDUSS) as client:
            forum_detail = await client.get_forum_detail(fname_or_fid)
            if forum_detail and forum_detail.fid != 0:
                return forum_detail
            else:
                failures += 1
                MsgPrinter.print_error(
                    f"Request failed ({failures}/{retry})", "FetchForumDetail", ["fname_or_fid", fname_or_fid]
                )

    return None


async def get_posts(tid: int, pn=1, retry=4):
    """Fetch one page of posts.

    Returns the Posts object on success. Raises ThreadUnavailable if the server
    positively reports the thread is gone (permanent). Returns None when all
    retries are exhausted on transient errors (rate limit / network) so the
    caller can treat the thread as incomplete-and-retryable.
    """
    only_thread_author = False
    if PostFilterType.AUTHOR_POSTS_WITH_SUBPOSTS == ScrapeConfig.POST_FILTER_TYPE:
        only_thread_author = True
    elif PostFilterType.AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS == ScrapeConfig.POST_FILTER_TYPE:
        only_thread_author = True

    backoff = _BACKOFF_BASE
    for attempt in range(1, retry + 1):
        async with tb.Client(TiebaAuth.BDUSS) as client:
            posts = await client.get_posts(tid, pn, with_comments=True, only_thread_author=only_thread_author)

        err = getattr(posts, "err", None)
        if err is None and posts.thread.tid != 0:
            return posts

        if _is_permanent_error(err):
            MsgPrinter.print_error(
                f"Thread unavailable (server error): {err}", "FetchPosts", ["tid", tid, "pn", pn]
            )
            raise ThreadUnavailable(f"tid={tid} pn={pn}: {err}")

        MsgPrinter.print_error(
            f"Request failed ({attempt}/{retry}){f' {err}' if err else ''}",
            "FetchPosts",
            ["tid", tid, "pn", pn],
        )
        if attempt < retry:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

    return None


async def get_comments(tid: int, pid: int, floor: int, pn=1, retry=4):
    """Fetch one page of comments (sub-posts / 楼中楼).

    Returns the Comments object on success. Returns None when the server
    positively reports the parent post is gone (permanent — nothing to recover).
    Raises FetchIncomplete when all retries are exhausted on a transient failure
    (rate limit / network), so the caller can refuse to mark the thread done and
    retry later — the same truthfulness rule as reply pages: a 楼中楼 we failed to
    fetch must NOT be silently dropped, and must never be treated as a deletion.
    """
    backoff = _BACKOFF_BASE
    for attempt in range(1, retry + 1):
        async with tb.Client(TiebaAuth.BDUSS) as client:
            comments = await client.get_comments(tid, pid, pn)

        err = getattr(comments, "err", None)
        if err is None and comments.post.pid != 0:
            return comments

        if _is_permanent_error(err):
            return None  # parent post gone; nothing to retry

        MsgPrinter.print_error(
            f"Request failed ({attempt}/{retry}){f' {err}' if err else ''}",
            "FetchComments",
            ["tid", tid, "floor", floor, "pid", pid, "pn", pn],
        )
        if attempt < retry:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

    raise FetchIncomplete(f"comments tid={tid} ppid={pid} floor={floor} pn={pn}")


async def get_user_info(user_id: str | int, portrait: str | None, retry=3):
    """Fetch a user's profile. Best-effort: returns None on permanent or
    exhausted-transient failure (user enrichment doesn't gate thread done)."""
    backoff = _BACKOFF_BASE
    for attempt in range(1, retry + 1):
        async with tb.Client(TiebaAuth.BDUSS) as client:
            user_info = await client.get_user_info(user_id)

        err = getattr(user_info, "err", None)
        if err is None and user_info.user_id != 0:
            return user_info

        if _is_permanent_error(err):
            return None

        MsgPrinter.print_error(
            f"Request failed ({attempt}/{retry}){f' {err}' if err else ''}",
            "FetchUserInfo",
            ["user_id", user_id, "portrait", portrait],
        )
        if attempt < retry:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

    return None
