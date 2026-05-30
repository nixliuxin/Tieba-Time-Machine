-- master.db 统一 Schema
-- 合并所有贴吧归档的 content.db + json 到单一数据库

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 贴吧信息
CREATE TABLE IF NOT EXISTS forum (
    forum_id    INTEGER PRIMARY KEY,
    forum_name  TEXT NOT NULL UNIQUE,
    member_num  INTEGER DEFAULT 0,
    post_num    INTEGER DEFAULT 0,
    thread_num  INTEGER DEFAULT 0,
    slogan      TEXT DEFAULT '',
    avatar_url  TEXT DEFAULT '',
    scraped_at  INTEGER DEFAULT 0
);

-- 帖子(主题)元信息
CREATE TABLE IF NOT EXISTS thread (
    tid             INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    forum_id        INTEGER NOT NULL,
    forum_name      TEXT NOT NULL,
    post_id         INTEGER DEFAULT 0,
    author_user_id  INTEGER DEFAULT 0,
    type            INTEGER DEFAULT 0,
    is_share        BOOLEAN DEFAULT 0,
    is_help         BOOLEAN DEFAULT 0,
    vote_info       TEXT DEFAULT '',
    share_origin    INTEGER DEFAULT 0,
    view_num        INTEGER DEFAULT 0,
    reply_num       INTEGER DEFAULT 0,
    share_num       INTEGER DEFAULT 0,
    agree           INTEGER DEFAULT 0,
    disagree        INTEGER DEFAULT 0,
    create_time     INTEGER DEFAULT 0,
    status          INTEGER DEFAULT 0,
    folder_name     TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_thread_forum ON thread(forum_name);
CREATE INDEX IF NOT EXISTS idx_thread_create_time ON thread(create_time);
CREATE INDEX IF NOT EXISTS idx_thread_reply_num ON thread(reply_num);
CREATE INDEX IF NOT EXISTS idx_thread_view_num ON thread(view_num);

-- 楼层/回复
CREATE TABLE IF NOT EXISTS post (
    id               INTEGER NOT NULL,
    tid              INTEGER NOT NULL,
    contents         TEXT NOT NULL,
    floor            INTEGER NOT NULL,
    user_id          INTEGER NOT NULL,
    agree            INTEGER DEFAULT 0,
    disagree         INTEGER DEFAULT 0,
    create_time      INTEGER NOT NULL,
    is_thread_author BOOLEAN DEFAULT 0,
    sign             TEXT DEFAULT '',
    reply_num        INTEGER DEFAULT 0,
    parent_id        INTEGER DEFAULT 0,
    reply_to_id      INTEGER DEFAULT 0,
    scrape_batch_id  INTEGER DEFAULT 0,
    PRIMARY KEY (tid, id)
);
CREATE INDEX IF NOT EXISTS idx_post_floor ON post(tid, floor);
CREATE INDEX IF NOT EXISTS idx_post_user ON post(user_id);
CREATE INDEX IF NOT EXISTS idx_post_create_time ON post(create_time);
CREATE INDEX IF NOT EXISTS idx_post_parent ON post(tid, parent_id);

-- 用户信息
CREATE TABLE IF NOT EXISTS user (
    portrait    TEXT NOT NULL,
    tid         INTEGER NOT NULL,
    user_id     INTEGER DEFAULT 0,
    username    TEXT,
    nickname    TEXT NOT NULL,
    tieba_uid   INTEGER,
    avatar      TEXT,
    glevel      INTEGER DEFAULT 0,
    gender      INTEGER DEFAULT 0,
    ip          TEXT DEFAULT '',
    is_vip      BOOLEAN DEFAULT 0,
    is_god      BOOLEAN DEFAULT 0,
    age         REAL DEFAULT 0,
    sign        TEXT DEFAULT '',
    post_num    INTEGER DEFAULT 0,
    agree_num   INTEGER DEFAULT 0,
    fan_num     INTEGER DEFAULT 0,
    follow_num  INTEGER DEFAULT 0,
    forum_num   INTEGER DEFAULT 0,
    level       INTEGER DEFAULT 0,
    is_bawu     BOOLEAN DEFAULT 0,
    status      INTEGER DEFAULT 0,
    completed   BOOLEAN DEFAULT 0,
    scrape_time INTEGER DEFAULT 0,
    PRIMARY KEY (tid, portrait)
);
CREATE INDEX IF NOT EXISTS idx_user_nickname ON user(nickname);
CREATE INDEX IF NOT EXISTS idx_user_uid ON user(tieba_uid);
CREATE INDEX IF NOT EXISTS idx_user_user_id ON user(tid, user_id);

-- 用户信息变更历史
CREATE TABLE IF NOT EXISTS user_info_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tid         INTEGER NOT NULL,
    portrait    TEXT,
    username    TEXT,
    tieba_uid   INTEGER,
    field_name  TEXT NOT NULL,
    field_value TEXT NOT NULL,
    scrape_time INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_uih_portrait ON user_info_history(portrait);
CREATE INDEX IF NOT EXISTS idx_uih_tid ON user_info_history(tid);

-- 媒体原始来源记录
CREATE TABLE IF NOT EXISTS tieba_origin_src (
    id                INTEGER NOT NULL,
    tid               INTEGER NOT NULL,
    filename          TEXT NOT NULL,
    content_frag_type INTEGER NOT NULL,
    origin_src        TEXT NOT NULL,
    PRIMARY KEY (tid, id)
);
CREATE INDEX IF NOT EXISTS idx_tos_filename ON tieba_origin_src(filename);

-- 抓取批次记录
CREATE TABLE IF NOT EXISTS scrape_batch (
    id              INTEGER NOT NULL,
    tid             INTEGER NOT NULL,
    scraper_version TEXT NOT NULL,
    scrape_config   TEXT NOT NULL,
    scrape_time     INTEGER NOT NULL,
    PRIMARY KEY (tid, id)
);

-- 抓取信息 (来自 scrape_info.json)
CREATE TABLE IF NOT EXISTS scrape_info (
    tid             INTEGER PRIMARY KEY,
    scraper_version TEXT DEFAULT '',
    scrape_time     INTEGER DEFAULT 0,
    config          TEXT DEFAULT '',
    raw_json        TEXT DEFAULT ''
);

-- FTS5 全文搜索索引 (独立表，合并完成后手动 rebuild)
CREATE VIRTUAL TABLE IF NOT EXISTS post_fts USING fts5(
    tid UNINDEXED,
    post_id UNINDEXED,
    floor UNINDEXED,
    contents
);

-- 合并进度跟踪
CREATE TABLE IF NOT EXISTS merge_progress (
    tid         INTEGER PRIMARY KEY,
    forum_name  TEXT NOT NULL,
    merged_at   INTEGER NOT NULL
);
