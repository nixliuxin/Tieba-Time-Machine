"""Runtime patches for known aiotieba bugs.

aiotieba 4.7.1: ``get_posts._classdef.Thread_p.from_proto`` logs an
"Unknown thread type" debug line that reads ``data_proto.thread_type`` -- but
that attribute only exists on ``thread_proto`` (``data_proto`` is the page-level
message and has no ``thread_type`` field). So for any thread whose ``thread_type``
is not one of the values defined in the ``ThreadType`` enum (special/unknown
post types), parsing raises ``AttributeError('thread_type')``. aiotieba's
``@handle_exception`` decorator swallows that into an empty result with ``.err``
set, which our client then sees as a generic "Request failed". The thread can
therefore NEVER be fetched, even though its data is perfectly fine on the server
-- a false "missing" that silently strands otherwise-archivable threads.

We replace ``from_proto`` with an identical copy that reads ``thread_type`` from
the correct proto message. Applied at import time of the API client so every
scraping process gets the fix.
"""

from aiotieba.api.get_posts import _classdef as _cd

_patched = False


def _thread_from_proto(data_proto):
    thread_proto = data_proto.thread
    title = thread_proto.title
    tid = thread_proto.id
    pid = thread_proto.post_id
    user = _cd.UserInfo_pt.from_proto(thread_proto.author)

    type_ = _cd.ThreadType(thread_proto.thread_type)
    if type_ == _cd.ThreadType.UNKNOWN:
        # FIX: was ``data_proto.thread_type`` (nonexistent) -> AttributeError.
        _cd.LOG().debug("Unknown thread type. tid=%d, type=%s", tid, thread_proto.thread_type)

    is_share = bool(thread_proto.is_share_thread)
    view_num = data_proto.thread_freq_num
    reply_num = thread_proto.reply_num
    share_num = thread_proto.share_num
    agree = thread_proto.agree.agree_num
    disagree = thread_proto.agree.disagree_num
    create_time = thread_proto.create_time

    if not is_share:
        real_thread_proto = thread_proto.origin_thread_info
        contents = _cd.Contents_pt.from_proto(real_thread_proto)
        vote_info = _cd.VoteInfo.from_proto(real_thread_proto.poll_info)
        share_origin = _cd.ShareThread_pt()
    else:
        contents = _cd.Contents_pt()
        vote_info = _cd.VoteInfo()
        share_origin = _cd.ShareThread_pt.from_proto(thread_proto.origin_thread_info)

    return _cd.Thread_p(
        contents,
        title,
        0,
        "",
        tid,
        pid,
        user,
        type_,
        is_share,
        vote_info,
        share_origin,
        view_num,
        reply_num,
        share_num,
        agree,
        disagree,
        create_time,
    )


def apply_patches() -> None:
    """Idempotently install the aiotieba runtime patches."""
    global _patched
    if _patched:
        return
    _cd.Thread_p.from_proto = staticmethod(_thread_from_proto)
    _patched = True
