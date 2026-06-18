import asyncio
import json
import math
import os

from aiotieba.typing import Posts, Comments, Post

from api.aiotieba_client import get_posts, get_comments, ThreadUnavailable, FetchIncomplete, EMPTY_PAGE
from config.scraper_config import SCRAPER_VERSION
from container.container import Container
from db.post_dao import PostDao
from db.scrape_batch_dao import ScrapeBatchDao
from db.tieba_origin_src_dao import TiebaOriginSrcDao
from db.user_dao import UserDao
from pojo.post_entity import PostEntity
from pojo.producer_consumer_contact import ProducerConsumerContact
from scrape_config import PostFilterType, ScrapeConfig
from services.content_service import ContentService, ContentsAffiliation
from services.user_service import UserService
from utils.common import json_dumps
from utils.fs import delete_matching_files
from utils.logger import generate_scrape_logger_msg
from utils.msg_printer import MsgPrinter


class PostService:
    def __init__(self):
        self.scrape_data_path_builder = Container.get_scrape_data_path_builder()
        self.tid = Container.get_tid()
        self.scrape_batch_id = 0
        self.scrape_logger = Container.get_scrape_logger()
        self.post_dao = PostDao()
        self.user_dao = UserDao()
        self.tieba_origin_src_dao = TiebaOriginSrcDao()
        self.scrape_batch_dao = ScrapeBatchDao()
        self.content_service = ContentService()
        self.user_service = UserService()
        # Set True if any reply page could not be fetched (rate limit / network).
        # Used by the caller to refuse marking the thread as fully done.
        self.incomplete = False
        # Intra-thread resume: page numbers whose main posts (and their comments)
        # are fully saved. Persisted to a sidecar so a re-scrape only fetches the
        # pages still missing, instead of throwing away the whole thread.
        self.done_pages: set[int] = set()
        self._checkpoint_path: str | None = None

    def _load_done_pages(self) -> None:
        self._checkpoint_path = os.path.join(
            self.scrape_data_path_builder.get_thread_dir(self.tid), "_pages_done.json"
        )
        try:
            with open(self._checkpoint_path, "r", encoding="utf-8") as f:
                self.done_pages = set(json.load(f))
        except (OSError, ValueError):
            self.done_pages = set()

    def _mark_page_done(self, pn: int) -> None:
        if pn <= 0 or pn in self.done_pages:
            return
        self.done_pages.add(pn)
        if not self._checkpoint_path:
            return
        # Atomic write so a crash mid-write never corrupts the checkpoint.
        tmp = f"{self._checkpoint_path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sorted(self.done_pages), f)
            os.replace(tmp, self._checkpoint_path)
        except OSError:
            pass

    async def scrape_post(self, total_page: int, *, is_update: bool = False) -> None:
        self.scrape_batch_id = self.scrape_batch_dao.insert(
            SCRAPER_VERSION, json_dumps(ScrapeConfig.to_dict(), False), Container.get_scrape_timestamp()
        )

        # Remember the reported page count so fetch_post can tell a legitimate
        # trailing empty page (total_page over-counts) from a mid-thread gap.
        self._total_page = total_page

        # On a resume, skip pages already fully archived in a previous attempt.
        self._load_done_pages()
        if self.done_pages:
            already = len([p for p in self.done_pages if p <= total_page])
            MsgPrinter.print_tip(
                f"Resuming thread: {already}/{total_page} reply pages already saved, fetching the rest.",
                ["tid", self.tid],
            )

        queue_maxsize = 10
        max_producers_num = 3
        producers_num = min(max_producers_num, total_page)
        consumers_num = 8
        consumer_await_timeout = 8
        contact = ProducerConsumerContact(queue_maxsize, producers_num, consumers_num, consumer_await_timeout)

        pages_per_producer = math.ceil(total_page / producers_num)

        tasks = []
        start_pn = 1
        for i in range(producers_num):
            end_pn = start_pn + pages_per_producer - 1
            if i == producers_num - 1:
                end_pn = total_page
            tasks.append(self.fetch_post(contact, start_pn, end_pn))
            start_pn = end_pn + 1

        for _ in range(consumers_num):
            tasks.append(self.save_post(contact, is_update))

        await asyncio.gather(*tasks)

        if (
            PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_SUBPOSTS == ScrapeConfig.POST_FILTER_TYPE
            or PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_AUTHOR_SUBPOSTS == ScrapeConfig.POST_FILTER_TYPE
        ):
            self.user_dao.delete_user_without_post()

    async def fetch_post(
        self,
        contact: ProducerConsumerContact,
        start_pn: int,
        end_pn: int,
    ) -> None:
        pn = start_pn

        while pn <= end_pn:
            # Resume: page already fully saved in a prior attempt -> don't refetch.
            if pn in self.done_pages:
                pn += 1
                continue
            try:
                posts = await get_posts(self.tid, pn)
            except ThreadUnavailable:
                # Thread became unavailable mid-scrape. Treat as incomplete (so it
                # is retried) rather than aborting and risking a false deletion.
                self.incomplete = True
                self.scrape_logger.error(
                    generate_scrape_logger_msg("Thread unavailable", "FetchPosts", ["pn", pn])
                )
                pn += 1
                continue
            fetched_pn = pn
            pn += 1
            if posts is EMPTY_PAGE:
                # Server returned a valid-but-empty page. If it's at/after the
                # reported last page, total_page simply over-counted (trailing
                # replies deleted) -> this page is legitimately empty, so mark it
                # done and let the thread complete. An empty page *before* the
                # last one is a real gap -> keep the thread incomplete.
                if fetched_pn >= self._total_page:
                    self._mark_page_done(fetched_pn)
                else:
                    self.incomplete = True
                    self.scrape_logger.error(
                        generate_scrape_logger_msg("Empty page mid-thread", "FetchPosts", ["pn", fetched_pn])
                    )
                continue
            if posts is None:
                # A reply page was lost to rate limit / network after all retries.
                # Flag the whole thread incomplete: it must not be marked done.
                self.incomplete = True
                self.scrape_logger.error(generate_scrape_logger_msg("Request failed", "FetchPosts", ["pn", fetched_pn]))
                continue

            await contact.tasks_queue.put(posts)

        contact.running_producers -= 1
        if contact.running_producers == 0:
            for _ in range(contact.consumers_num):
                await contact.tasks_queue.put(None)

    async def save_post(self, contact: ProducerConsumerContact, is_update: bool = False) -> None:
        while True:
            try:
                posts: Posts = await asyncio.wait_for(
                    contact.tasks_queue.get(), contact.consumer_await_timeout
                )

                if posts is None:
                    return

                # Track completeness of this single page so it can be checkpointed
                # for intra-thread resume. A page is "done" only if every post and
                # every comment page on it was saved without a transient failure.
                page_pn = posts.page.current_page
                page_failed = False

                for post in posts.objs:
                    try:
                        # Comment 1
                        if post.pid <= 0:
                            continue

                        if is_update and self.post_dao.is_existing_post(post.pid):
                            self.post_dao.update_post_traffic_by_id(
                                post.pid, post.agree, post.disagree, post.reply_num
                            )

                            if len(post.comments) != 0:
                                if await self.scrape_comments(
                                    post.pid,
                                    post.floor,
                                    posts.page.current_page,
                                    post.reply_num,
                                    is_update=True,
                                ):
                                    page_failed = True
                            continue

                        if (
                            PostFilterType.AUTHOR_POSTS_WITH_SUBPOSTS == ScrapeConfig.POST_FILTER_TYPE
                            or PostFilterType.AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS
                            == ScrapeConfig.POST_FILTER_TYPE
                        ) and (not post.is_thread_author):
                            continue

                        await self.user_service.register_user_from_post_user(post.user)
                        post_contents = await self.content_service.process_contents(
                            post.contents.objs,
                            ContentsAffiliation(posts.page.current_page, post.pid, post.floor),
                        )
                        self.post_dao.insert(
                            PostEntity(
                                post.pid,
                                post_contents,
                                post.floor,
                                post.author_id,
                                post.agree,
                                post.disagree,
                                post.create_time,
                                post.is_thread_author,
                                post.sign,
                                post.reply_num,
                                0,
                                0,
                                self.scrape_batch_id,
                            )
                        )
                        MsgPrinter.print_success("", "SavePost", ["floor", post.floor, "pid", post.pid])

                        if len(post.comments) > 0:
                            if await self.scrape_comments(
                                post.pid,
                                post.floor,
                                posts.page.current_page,
                                post.reply_num,
                            ):
                                page_failed = True

                        if (not post.is_thread_author) and (
                            PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_SUBPOSTS
                            == ScrapeConfig.POST_FILTER_TYPE
                            or PostFilterType.AUTHOR_AND_REPLIED_POSTS_WITH_AUTHOR_SUBPOSTS
                            == ScrapeConfig.POST_FILTER_TYPE
                        ):
                            if len(post.comments) == 0 or (
                                not self.post_dao.is_author_replied_post(post.pid, self.scrape_batch_id)
                            ):
                                self.post_dao.delete(post.pid)
                                await self.delete_post_assets(post.pid)

                                subposts_cursor = self.post_dao.query_subposts_by_pid_and_batch_id(
                                    post.pid, self.scrape_batch_id
                                )
                                while row := subposts_cursor.fetchone():
                                    if row is None:
                                        break
                                    self.post_dao.delete(row[0])
                                    await self.delete_post_assets(row[0])

                    except Exception as e:
                        page_failed = True
                        MsgPrinter.print_error(
                            str(e),
                            "SavePost",
                            [
                                "floor",
                                post.floor,
                                "pid",
                                post.pid,
                                "pn",
                                posts.page.current_page,
                            ],
                        )
                        self.scrape_logger.error(
                            generate_scrape_logger_msg(
                                str(e),
                                "SavePost",
                                [
                                    "floor",
                                    post.floor,
                                    "pid",
                                    post.pid,
                                    "pn",
                                    posts.page.current_page,
                                ],
                            )
                        )

                # Whole page (and its comments) saved cleanly -> checkpoint it.
                if not page_failed:
                    self._mark_page_done(page_pn)
            except asyncio.TimeoutError:
                if contact.running_producers == 0:
                    return

    async def delete_post_assets(self, pid: int) -> None:
        filename_pattern = self.scrape_data_path_builder.get_post_assets_filename_pattern(pid)
        deleted_files = await delete_matching_files(
            self.scrape_data_path_builder.get_post_assets_dir(self.tid), filename_pattern
        )

        for file in deleted_files:
            self.tieba_origin_src_dao.delete_by_filename(file)

    async def save_post_from_floor1(self, post: Post):
        if post.pid <= 0:
            return

        await self.user_service.register_user_from_post_user(post.user)

        post_contents = await self.content_service.process_contents(
            post.contents.objs,
            ContentsAffiliation(),
        )
        self.post_dao.insert(
            PostEntity(
                post.pid,
                post_contents,
                post.floor,
                post.author_id,
                post.agree,
                post.disagree,
                post.create_time,
                post.is_thread_author,
                post.sign,
                post.reply_num,
                0,
                0,
                self.scrape_batch_id,
            )
        )
        MsgPrinter.print_success("", "SavePost", ["floor", post.floor, "pid", post.pid])

    async def scrape_comments(
        self,
        ppid: int,
        floor: int,
        ppn: int,
        reply_num: int,
        *,
        is_update: bool = False,
    ) -> bool:
        """Returns True if any comment page was lost to a transient failure
        (so the enclosing reply page must not be checkpointed as done)."""
        queue_maxsize = 8 if reply_num > 8 else reply_num
        producers_num = 1
        consumers_num = queue_maxsize
        consumer_await_timeout = 8
        contact = ProducerConsumerContact(queue_maxsize, producers_num, consumers_num, consumer_await_timeout)

        results = await asyncio.gather(
            self.fetch_comments(contact, ppid, floor),
            *[self.save_comments(contact, ppn, is_update) for _ in range(consumers_num)],
        )
        # results[0] is fetch_comments' return value (incomplete flag).
        return bool(results[0])

    async def fetch_comments(self, contact: ProducerConsumerContact, ppid: int, floor: int) -> bool:
        pn = 1
        total_page = pn
        incomplete = False

        while total_page >= pn:
            try:
                comments = await get_comments(self.tid, ppid, floor, pn)
            except FetchIncomplete:
                # 楼中楼某页被限流/网络丢失 → 整帖不算完整，留待重抓（绝不当作删除）
                self.incomplete = True
                incomplete = True
                self.scrape_logger.error(
                    generate_scrape_logger_msg(
                        "Request failed (incomplete)",
                        "FetchComments",
                        ["floor", floor, "ppid", ppid, "pn", pn],
                    )
                )
                pn += 1
                continue
            pn += 1
            if comments is None:
                # 父帖被百度判定已删除 → 无可恢复，跳过（不标记 incomplete）
                self.scrape_logger.error(
                    generate_scrape_logger_msg(
                        "Parent gone",
                        "FetchComments",
                        ["floor", floor, "ppid", ppid, "pn", pn],
                    )
                )
                continue

            await contact.tasks_queue.put(comments)

            new_total_page = comments.page.total_page
            if new_total_page > total_page:
                total_page = new_total_page

        contact.running_producers -= 1
        if contact.running_producers == 0:
            for _ in range(contact.consumers_num):
                await contact.tasks_queue.put(None)

        return incomplete

    async def save_comments(self, contact: ProducerConsumerContact, ppn: int, is_update: bool = False):
        while True:
            try:
                comments: Comments = await asyncio.wait_for(
                    contact.tasks_queue.get(), contact.consumer_await_timeout
                )

                if comments is None:
                    return

                for comment in comments.objs:
                    comment_affiliations = [
                        "floor",
                        comment.floor,
                        "pid",
                        comment.pid,
                        "pn",
                        comments.page.current_page,
                        "ppid",
                        comment.ppid,
                        "ppn",
                        ppn,
                    ]

                    try:
                        if is_update and self.post_dao.is_existing_post(comment.pid):
                            self.post_dao.update_post_traffic_by_id(
                                comment.pid, comment.agree, comment.disagree, 0
                            )
                            continue

                        if (
                            PostFilterType.AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS == ScrapeConfig.POST_FILTER_TYPE
                            or PostFilterType.AUTHOR_POSTS_WITH_AUTHOR_SUBPOSTS
                            == ScrapeConfig.POST_FILTER_TYPE
                        ) and (not comment.is_thread_author):
                            continue

                        await self.user_service.register_user_from_comment_user(comment.user)
                        if comment.reply_to_id != 0:
                            await self.user_service.register_user_from_id(comment.reply_to_id)

                        comment_contents = await self.content_service.process_contents(
                            comment.contents.objs,
                            ContentsAffiliation(
                                ppn,
                                comment.ppid,
                                comment.floor,
                                comments.page.current_page,
                                comment.pid,
                            ),
                        )

                        self.post_dao.insert(
                            PostEntity(
                                comment.pid,
                                comment_contents,
                                comment.floor,
                                comment.author_id,
                                comment.agree,
                                comment.disagree,
                                comment.create_time,
                                comment.is_thread_author,
                                "",
                                0,
                                comment.ppid,
                                comment.reply_to_id,
                                self.scrape_batch_id,
                            )
                        )

                        MsgPrinter.print_success(
                            "",
                            "SaveComment",
                            comment_affiliations,
                        )
                    except Exception as e:
                        MsgPrinter.print_error(
                            str(e),
                            "SaveComment",
                            comment_affiliations,
                        )
                        self.scrape_logger.error(
                            generate_scrape_logger_msg(
                                "Save failed",
                                "SaveComment",
                                comment_affiliations,
                            )
                        )
            except asyncio.TimeoutError:
                if contact.running_producers == 0:
                    return


# Comment 1: Check whether pid <= 0.
# https://github.com/Starry-OvO/aiotieba/issues/210 - resolved.
# The wrapped get_posts may return spurious entries with pid=0, floor=0.
