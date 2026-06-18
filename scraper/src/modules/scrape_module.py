import asyncio
import os
import time

from aiotieba.api.get_posts._classdef import ShareThread_pt

from api.aiotieba_client import get_posts, ThreadUnavailable, FetchIncomplete, EMPTY_PAGE
from config.path_config import ScrapeDataPathBuilder
from container.container import Container
from pojo.scrape_info import ScrapeInfo
from scrape_config import ScrapeConfig
from services.post_service import PostService
from services.thread_service import ThreadService
from services.user_service import UserService
from utils.common import counter_gen, json_dumps
from utils.logger import generate_scrape_logger_msg
from utils.msg_printer import MsgPrinter

counter = counter_gen()
next(counter)


async def scrape(tid: int):
    scrape_start_time = time.time()
    Container.set_scrape_timestamp(int(scrape_start_time))

    # Preload page 1. ThreadUnavailable (server says gone) propagates to the
    # caller as a confirmed deletion. A None here is a transient failure, so we
    # raise FetchIncomplete to force a retry instead of silently giving up.
    pre_post = await get_posts(tid, 1)
    if pre_post is None or pre_post is EMPTY_PAGE:
        counter.send((0, 1))
        MsgPrinter.print_tip(
            "\n".join(
                [
                    "\nPreload failed after retries (transient). Will retry later. Possible causes:",
                    f"{next(counter)}. Rate limited (429), too many requests.",
                    f"{next(counter)}. Connection / network failure.",
                    f"{next(counter)}. BDUSS expired, please reconfigure.",
                ]
            ),
        )
        raise FetchIncomplete(f"preload failed for tid={tid}")

    scrape_data_path_builder = ScrapeDataPathBuilder.get_instance_scrape(
        pre_post.forum.fname, tid, pre_post.thread.title
    )
    Container.set_scrape_data_path_builder(scrape_data_path_builder)

    with open(scrape_data_path_builder.get_scrape_info_path(), "w", encoding="utf-8") as file:
        file.write(
            json_dumps(
                ScrapeInfo(
                    tid,
                    Container.get_scrape_timestamp(),
                    {
                        "scrape_time": Container.get_scrape_timestamp(),
                        "scrape_config": ScrapeConfig.to_dict(),
                    },
                )
            )
        )

    main_thread_id = tid
    incomplete = await scrape_thread(main_thread_id)

    share_origin_id = pre_post.thread.share_origin.tid
    if share_origin_id != 0:
        MsgPrinter.print_step_mark("Processing share_origin")
        # share_origin completeness is secondary; it does not gate the main thread.
        await scrape_thread(share_origin_id, is_share_origin=True, share_origin=pre_post.thread.share_origin)

    # If any reply page of the main thread was lost to rate limit / network,
    # signal incomplete so the thread is retried (and not marked done). The
    # per-page checkpoint is kept so the retry resumes instead of restarting.
    if incomplete:
        raise FetchIncomplete(f"some reply pages missing for tid={tid}")

    # Fully complete -> the resume checkpoint is no longer needed.
    checkpoint = os.path.join(scrape_data_path_builder.get_thread_dir(tid), "_pages_done.json")
    try:
        os.remove(checkpoint)
    except OSError:
        pass

    scrape_end_time = time.time()
    scrape_duration = scrape_end_time - scrape_start_time

    MsgPrinter.print_step_mark("Task completed")
    MsgPrinter.print_tip(f"Elapsed {int(scrape_duration // 60)} min {round(scrape_duration % 60, 2)} sec")
    MsgPrinter.print_tip(f"Thread data saved to: {scrape_data_path_builder.get_item_dir()}")


async def scrape_thread(tid: int, *, is_share_origin: bool = False, share_origin: ShareThread_pt | None = None) -> bool:
    """Scrape one thread. Returns True if the scrape was incomplete (some reply
    pages were lost to transient failures). Raises ThreadUnavailable if the
    server reports the main thread is deleted/blocked."""
    if tid <= 0:
        return False

    Container.set_tid(tid)
    scrape_data_path_builder = Container.get_scrape_data_path_builder()
    os.makedirs(scrape_data_path_builder.get_thread_dir(tid), exist_ok=True)
    content_db = Container.get_content_db()
    scrape_logger = Container.get_scrape_logger()

    def final_treatment():
        content_db.close()

    MsgPrinter.print_step_mark("Starting thread scrape", ["tid", tid])
    scrape_logger.info(generate_scrape_logger_msg("Starting thread scrape", "StepMark", ["tid", tid]))

    try:
        pre_fetch_posts = await get_posts(tid)
    except ThreadUnavailable:
        # Main thread is gone -> propagate so it is marked deleted.
        # A gone share_origin is non-fatal: fall through to save what we have.
        if not is_share_origin:
            final_treatment()
            raise
        pre_fetch_posts = None

    # An empty page 1 is not usable thread data; treat it like a transient miss
    # (retry later) rather than a deletion or a parseable thread.
    if pre_fetch_posts is EMPTY_PAGE:
        pre_fetch_posts = None

    thread_service = ThreadService()
    user_service = UserService()
    post_service = PostService()

    if pre_fetch_posts is None:
        if is_share_origin and (share_origin is not None):
            MsgPrinter.print_step_mark(f"share_origin may be blocked or deleted, saving available data", ["tid", tid])
            await asyncio.gather(
                thread_service.save_forum_info(share_origin.fid),
                thread_service.save_thread_from_share_origin(share_origin),
                user_service.register_user_from_id(share_origin.author_id),
                user_service.complete_user_info(),
            )
            final_treatment()
            return False
        # Main thread: transient failure fetching page 1 -> incomplete, retry later.
        final_treatment()
        return True

    await asyncio.gather(
        thread_service.save_forum_info(pre_fetch_posts.forum.fid),
        thread_service.save_thread_info(pre_fetch_posts.thread),
    )

    if is_share_origin and (not ScrapeConfig.SCRAPE_SHARE_ORIGIN):
        MsgPrinter.print_tip(
            "Config set to skip share_origin; only saving the first floor of share_origin.",
            ["tid", tid],
        )
        await post_service.save_post_from_floor1(pre_fetch_posts.objs[0])

        final_treatment()
        return False

    await post_service.scrape_post(pre_fetch_posts.page.total_page)

    MsgPrinter.print_step_mark("Completing user data", ["tid", tid])
    scrape_logger.info(generate_scrape_logger_msg("Completing user data", "StepMark", ["tid", tid]))
    await user_service.complete_user_info()

    final_treatment()
    MsgPrinter.print_step_mark("Thread scrape completed", ["tid", tid])
    scrape_logger.info(generate_scrape_logger_msg("Thread scrape completed", "StepMark", ["tid", tid]))
    # True if any reply page was lost to transient failure.
    return post_service.incomplete
