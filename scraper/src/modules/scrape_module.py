import asyncio
import os
import time

from aiotieba.api.get_posts._classdef import ShareThread_pt

from api.aiotieba_client import get_posts
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

    pre_post = await get_posts(tid, 1)
    if pre_post is None:
        counter.send((0, 1))
        MsgPrinter.print_tip(
            "\n".join(
                [
                    "\nPreload error. Possible causes:",
                    f"{next(counter)}. Connection error, please retry.",
                    f"{next(counter)}. Network failure, please check your network.",
                    f"{next(counter)}. Invalid tid, please verify the input.",
                    f"{next(counter)}. The thread may have been blocked or deleted.",
                    f"{next(counter)}. BDUSS expired, please reconfigure.",
                ]
            ),
        )
        return

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
    await scrape_thread(main_thread_id)

    share_origin_id = pre_post.thread.share_origin.tid
    if share_origin_id != 0:
        MsgPrinter.print_step_mark("Processing share_origin")
        await scrape_thread(share_origin_id, is_share_origin=True, share_origin=pre_post.thread.share_origin)

    scrape_end_time = time.time()
    scrape_duration = scrape_end_time - scrape_start_time

    MsgPrinter.print_step_mark("Task completed")
    MsgPrinter.print_tip(f"Elapsed {int(scrape_duration // 60)} min {round(scrape_duration % 60, 2)} sec")
    MsgPrinter.print_tip(f"Thread data saved to: {scrape_data_path_builder.get_item_dir()}")


async def scrape_thread(tid: int, *, is_share_origin: bool = False, share_origin: ShareThread_pt | None = None):
    if tid <= 0:
        return

    Container.set_tid(tid)
    scrape_data_path_builder = Container.get_scrape_data_path_builder()
    os.makedirs(scrape_data_path_builder.get_thread_dir(tid), exist_ok=True)
    content_db = Container.get_content_db()
    scrape_logger = Container.get_scrape_logger()

    def final_treatment():
        content_db.close()

    MsgPrinter.print_step_mark("Starting thread scrape", ["tid", tid])
    scrape_logger.info(generate_scrape_logger_msg("Starting thread scrape", "StepMark", ["tid", tid]))

    pre_fetch_posts = await get_posts(tid)

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
        return

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
        return

    await post_service.scrape_post(pre_fetch_posts.page.total_page)

    MsgPrinter.print_step_mark("Completing user data", ["tid", tid])
    scrape_logger.info(generate_scrape_logger_msg("Completing user data", "StepMark", ["tid", tid]))
    await user_service.complete_user_info()

    final_treatment()
    MsgPrinter.print_step_mark("Thread scrape completed", ["tid", tid])
    scrape_logger.info(generate_scrape_logger_msg("Thread scrape completed", "StepMark", ["tid", tid]))
