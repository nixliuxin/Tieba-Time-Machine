import contextvars
from config.path_config import ScrapeDataPathBuilder
from db.content_db import ContentDB
from utils.logger import ScrapeLogger

_ctx_path_builder = contextvars.ContextVar('scrape_data_path_builder', default=None)
_ctx_tid = contextvars.ContextVar('tid', default=0)
_ctx_timestamp = contextvars.ContextVar('scrape_timestamp', default=0)
_ctx_logger = contextvars.ContextVar('scrape_logger', default=None)
_ctx_content_db = contextvars.ContextVar('content_db', default=None)


class Container:
    @classmethod
    def get_scrape_data_path_builder(cls) -> ScrapeDataPathBuilder:
        val = _ctx_path_builder.get()
        if val is None:
            raise Exception("ScrapeDataPathBuilder is not set")
        return val

    @classmethod
    def set_scrape_data_path_builder(cls, scrape_data_path_builder: ScrapeDataPathBuilder) -> None:
        _ctx_path_builder.set(scrape_data_path_builder)

    @classmethod
    def get_tid(cls) -> int:
        val = _ctx_tid.get()
        if val == 0:
            raise Exception("tid is not set")
        return val

    @classmethod
    def set_tid(cls, tid: int) -> None:
        _ctx_tid.set(tid)
        _ctx_logger.set(None)
        _ctx_content_db.set(None)

    @classmethod
    def set_scrape_timestamp(cls, timestamp: int) -> None:
        _ctx_timestamp.set(timestamp)

    @classmethod
    def get_scrape_timestamp(cls) -> int:
        val = _ctx_timestamp.get()
        if val == 0:
            raise Exception("scrape_timestamp is not set")
        return val

    @classmethod
    def get_scrape_logger(cls):
        val = _ctx_logger.get()
        if val is None:
            val = ScrapeLogger(
                cls.get_scrape_data_path_builder().get_scrape_log_path(
                    _ctx_tid.get(), _ctx_timestamp.get()))
            _ctx_logger.set(val)
        return val

    @classmethod
    def get_content_db(cls) -> ContentDB:
        val = _ctx_content_db.get()
        if val is None:
            tid = _ctx_tid.get()
            val = ContentDB(
                cls.get_scrape_data_path_builder().get_content_db_path(tid),
                tid,
            )
            _ctx_content_db.set(val)
        return val
