"""SQLite に置く保存先。動きはフロントの IndexedDB 版と同じ（docs/storage-interface.md）。

SQL の値はすべてプレースホルダ（?）で渡し、文字列をつなげて SQL を作らない（SQL インジェクション対策）。
"""

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.config import MAX_PAGES

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    picture BLOB,
    picture_type TEXT,
    voice BLOB,
    voice_type TEXT,
    voice_ms INTEGER NOT NULL
)
"""

# 絵と声で列だけが違う。列の名前を文字列でつながず、決まった SQL から選ぶ
_MEDIA_SQL = {
    "picture": "SELECT picture, picture_type FROM pages WHERE id = ?",
    "voice": "SELECT voice, voice_type FROM pages WHERE id = ?",
}


class PageMeta(BaseModel):
    """一覧で返す項目。絵と声の中身は含めない（別の URL で読む）。名前・日時などは持たない。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    picture_type: str | None
    voice_type: str | None
    voice_ms: int


@dataclass(frozen=True)
class PageContent:
    """保存する中身。確認（media.py と voiceMs の範囲）を通ったものだけを渡す。"""

    picture: bytes | None
    picture_type: str | None
    voice: bytes | None
    voice_type: str | None
    voice_ms: int


class PageLimitError(Exception):
    pass


class PageStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # isolation_level=None で自動の取引を止め、取引の範囲を自分で決める
        db = sqlite3.connect(self._path, isolation_level=None)
        try:
            yield db
        finally:
            db.close()

    def list_pages(self) -> list[PageMeta]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, picture_type, voice_type, voice_ms FROM pages ORDER BY position"
            ).fetchall()
        return [PageMeta(id=r[0], picture_type=r[1], voice_type=r[2], voice_ms=r[3]) for r in rows]

    def get_media(self, page_id: str, kind: str) -> tuple[bytes, str] | None:
        with self._connect() as db:
            row = db.execute(_MEDIA_SQL[kind], (page_id,)).fetchone()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]

    def add(self, content: PageContent) -> PageMeta:
        page_id = str(uuid.uuid4())
        with self._connect() as db:
            # 数える・番号を決める・書くを1つの取引にまとめ、同時に保存されても上限を超えないようにする。
            # IMMEDIATE は、取引の最初に書き込みの鍵を取る指定
            db.execute("BEGIN IMMEDIATE")
            try:
                count, last = db.execute("SELECT COUNT(*), COALESCE(MAX(position), 0) FROM pages").fetchone()
                if count >= MAX_PAGES:
                    raise PageLimitError
                db.execute(
                    "INSERT INTO pages (id, position, picture, picture_type, voice, voice_type, voice_ms)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (page_id, last + 1, *_values(content)),
                )
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return _meta(page_id, content)

    def replace(self, page_id: str, content: PageContent) -> PageMeta | None:
        """上書きする。順番は変えない。ないページなら None。"""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE pages SET picture = ?, picture_type = ?, voice = ?, voice_type = ?, voice_ms = ?"
                " WHERE id = ?",
                (*_values(content), page_id),
            )
        return _meta(page_id, content) if cursor.rowcount else None

    def delete(self, page_id: str) -> None:
        # 順番は position の並びで決まるので、消すだけで残りは詰まって見える
        with self._connect() as db:
            db.execute("DELETE FROM pages WHERE id = ?", (page_id,))

    def delete_all(self) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM pages")


def _values(content: PageContent) -> tuple:
    return (content.picture, content.picture_type, content.voice, content.voice_type, content.voice_ms)


def _meta(page_id: str, content: PageContent) -> PageMeta:
    return PageMeta(
        id=page_id,
        picture_type=content.picture_type,
        voice_type=content.voice_type,
        voice_ms=content.voice_ms,
    )
