"""Gemini API への接続をここに集める（C-27 (5)）。

API キーは tools/ai の .env（Git の外）から、このプロセスの中だけに読み込む。
画面・ログ・例外のメッセージにキーを出さない。PC 全体の環境変数（GOOGLE_API_KEY など）は使わない。
"""

from pathlib import Path

from google import genai

KEY_FILE = Path(__file__).resolve().parent / ".env"
KEY_NAME = "GEMINI_API_KEY"


def load_api_key(path: Path = KEY_FILE) -> str:
    if not path.is_file():
        raise RuntimeError(f"{path.name} がありません。{KEY_NAME}=... の1行を書いてください")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == KEY_NAME and value.strip():
            return value.strip().strip('"').strip("'")
    raise RuntimeError(f"{path.name} に {KEY_NAME} が見つかりません")


def make_client() -> genai.Client:
    # api_key を明示して、PC の環境変数（GOOGLE_API_KEY が優先される）に左右されないようにする
    return genai.Client(api_key=load_api_key())
