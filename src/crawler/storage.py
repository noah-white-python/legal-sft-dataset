"""sqlite 存储层 —— 爬虫的"记忆"。

为什么用 sqlite 不用 CSV?因为我们需要三件 CSV 干不了的事:
  1. 去重         —— 按"问答内容"去重(同一条问答出现两次只存一份)
  2. 断点续爬     —— 按"页 URL"记录爬过没有,重启时跳过,不从头再来
  3. 死信(dead letter) —— 反复失败的 url 单独记一张表,不让它卡住整个程序

★ 关键设计:一个列表页 URL 往往解析出"多条"问答。所以
  - 断点续爬的单位是 "页 URL"      -> visited 表
  - 去重的单位是 "问答内容"        -> records 表的 content_hash 唯一
  这两件事用途不同,必须分开,否则一页里只会存进一条记录(踩过的坑)。
"""

import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "crawl.sqlite"


def _hash(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()


class Storage:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        # 已访问的页 URL —— 断点续爬看这张表(ok=1 成功,ok=0 进了死信)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS visited (
                url  TEXT PRIMARY KEY,
                ok   INTEGER,
                at   TEXT
            )
            """
        )
        # 正式数据 —— content_hash UNIQUE 实现"按内容去重"
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                question     TEXT NOT NULL,
                answer       TEXT NOT NULL,
                source       TEXT,
                url          TEXT,
                created_at   TEXT
            )
            """
        )
        # 死信:重试到底还失败的 url,人工事后再看,绝不阻塞主流程
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dead_letters (
                url       TEXT PRIMARY KEY,
                error     TEXT,
                failed_at TEXT
            )
            """
        )
        self.conn.commit()

    # ---- 断点续爬:访问过的页(成功或死信)都算"做过",下次跳过 ----
    def seen_urls(self) -> set[str]:
        cur = self.conn.cursor()
        return {row[0] for row in cur.execute("SELECT url FROM visited")}

    def _mark_visited(self, url: str, ok: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO visited (url, ok, at) VALUES (?, ?, ?)",
            (url, ok, datetime.now().isoformat(timespec="seconds")),
        )

    # ---- 保存一页解析出的多条问答;按内容去重;并把该页标记为已访问 ----
    def save_records(self, url: str, records: list[dict], source: str) -> int:
        cur = self.conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        n = 0
        for r in records:
            q, a = r.get("question", ""), r.get("answer", "")
            if not q or not a:
                continue
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO records "
                    "(content_hash, question, answer, source, url, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (_hash(q + a), q, a, source, url, now),
                )
                n += cur.rowcount  # rowcount=0 表示内容重复,被去重忽略
            except sqlite3.Error:
                continue
        self._mark_visited(url, ok=1)
        self.conn.commit()
        return n

    # ---- 写死信,并把该页标记为已访问(下次别再爬) ----
    def save_dead(self, url: str, error: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO dead_letters (url, error, failed_at) VALUES (?, ?, ?)",
            (url, error[:500], datetime.now().isoformat(timespec="seconds")),
        )
        self._mark_visited(url, ok=0)
        self.conn.commit()

    def stats(self) -> dict:
        cur = self.conn.cursor()
        n_rec = cur.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        n_dead = cur.execute("SELECT COUNT(*) FROM dead_letters").fetchone()[0]
        return {"records": n_rec, "dead_letters": n_dead}

    def close(self):
        self.conn.close()
