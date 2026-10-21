"""設定と上限。上限の値はフロントの frontend/js/storage/validate.js とそろえる。"""

import os
from dataclasses import dataclass
from pathlib import Path

MAX_PAGES = 8
MAX_VOICE_MS = 30_000

# 絵（キャンバスの PNG）と声（30秒の録音は数百KB）の大きさの上限。
# 子どもの絵と声より大きなものを受け取る理由がないので、余裕を持たせつつ小さくする
MAX_PICTURE_BYTES = 2 * 1024 * 1024
MAX_VOICE_BYTES = 1 * 1024 * 1024
# 1回に送られる全体の上限（絵と声と、multipart の区切りの分）。超えたら中身を読む前に断る
MAX_REQUEST_BYTES = MAX_PICTURE_BYTES + MAX_VOICE_BYTES + 64 * 1024

# サーバー保存を有効にする環境変数と、有効にする値。これ以外の値はすべて無効として扱う
ENV_SERVER_STORAGE = "KIDS_SERVER_STORAGE"
ENABLED_VALUE = "enabled"

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # 既定は無効（fail-safe）。設定を忘れても、絵と声を受け取らない側に倒れる（脅威分析 T-08、対策 C-12）
    server_storage_enabled: bool = False
    # backend/data/ は .gitignore 済み。Claude Code の deny でも読めないようにしてある
    db_path: Path = BACKEND_DIR / "data" / "kids.sqlite3"
    frontend_dir: Path = BACKEND_DIR.parent / "frontend"

    @classmethod
    def from_env(cls) -> Settings:
        # "true" や "1" などの「それらしい値」では有効にしない。有効にするには、決めた1語を正確に書く
        enabled = os.environ.get(ENV_SERVER_STORAGE) == ENABLED_VALUE
        return cls(server_storage_enabled=enabled)
