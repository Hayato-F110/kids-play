"""kids-play の docs/ にある公開文書を読むだけの MCP サーバー（stdio）。

守り（C-28、T-26）：
- 道具は一覧と読み出しの2つだけ。書き込み・削除・実行・通信の道具は作らない
- Claude Code の deny（.env を読まない など）は、MCP の道具の中で開くファイルには効かない。
  そのため、docs/ の外を断る処理は、このファイルが唯一の歯止めになる
"""

from pathlib import Path, PurePosixPath, PureWindowsPath

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
# 大きなファイルで AI の文脈を埋めないための上限。いまの最大の文書（学習ログ、約 140KB）より余裕を持たせた
MAX_BYTES = 200_000


class DocAccessError(ToolError):
    """範囲の外、または読めない文書を求められた。メッセージに文書の中身を入れない。

    ToolError の仲間にすると、理由の文が AI に返る。それ以外の例外は、SDK が中身を隠して返す。
    """


def resolve_doc_path(root: Path, path: str) -> Path:
    # Windows の区切り（\）で渡されても同じに扱う。絶対パスとドライブ名は、直す前の形で断る
    win = PureWindowsPath(path)
    if win.drive or win.root or PurePosixPath(path).is_absolute():
        raise DocAccessError("docs/ からの相対パスで指定してください")
    root = root.resolve()
    # resolve で .. とシンボリックリンクを解いてから、docs/ の中かを確かめる（文字列の比較では抜けられる）
    target = (root / path.replace("\\", "/")).resolve()
    if not target.is_relative_to(root):
        raise DocAccessError("docs/ の外は読めません")
    if target.suffix.lower() != ".md":
        raise DocAccessError(".md の文書だけを読めます")
    if not target.is_file():
        raise DocAccessError("その文書はありません")
    return target


def read_doc_text(root: Path, path: str) -> str:
    target = resolve_doc_path(root, path)
    if target.stat().st_size > MAX_BYTES:
        raise DocAccessError(f"文書が大きすぎます（上限 {MAX_BYTES} バイト）")
    return target.read_text(encoding="utf-8")


def list_doc_paths(root: Path) -> list[str]:
    root = root.resolve()
    paths = []
    for p in root.rglob("*.md"):
        # 一覧にも、リンクで docs/ の外を指すものは出さない
        if p.is_file() and p.resolve().is_relative_to(root):
            paths.append(p.relative_to(root).as_posix())
    return sorted(paths)


mcp = MCPServer("kids-docs")
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


@mcp.tool(annotations=READ_ONLY)
def list_docs() -> list[str]:
    """kids-play の docs/ にある Markdown の文書の一覧を、docs/ からの相対パスで返す。"""
    return list_doc_paths(DOCS_ROOT)


@mcp.tool(annotations=READ_ONLY)
def read_doc(path: str) -> str:
    """docs/ にある Markdown の文書を1つ読む。path は list_docs が返す相対パス（例：plan.md）。"""
    return read_doc_text(DOCS_ROOT, path)


if __name__ == "__main__":
    mcp.run()
