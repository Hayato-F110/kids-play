"""docs を読むだけの MCP の、読める範囲の試験（C-28、T-26）。

道具の中で開くファイルには Claude Code の deny が効かないので、範囲の外を断るのはこのコードだけになる。
"""

import os
from pathlib import Path

import pytest

from docs_mcp import DocAccessError, list_doc_paths, read_doc_text, resolve_doc_path


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    (root / "security").mkdir(parents=True)
    (root / "plan.md").write_text("# 計画", encoding="utf-8")
    (root / "security" / "threat-model.md").write_text("# 脅威", encoding="utf-8")
    (root / "notes.txt").write_text("md ではない", encoding="utf-8")
    # docs の外に、秘密の値のつもりのファイルを置く
    (tmp_path / "secret.md").write_text("SECRET", encoding="utf-8")
    return root


def test_reads_md_inside_docs(docs: Path) -> None:
    assert read_doc_text(docs, "plan.md") == "# 計画"
    assert read_doc_text(docs, "security/threat-model.md") == "# 脅威"


def test_accepts_backslash_separator(docs: Path) -> None:
    assert read_doc_text(docs, "security\\threat-model.md") == "# 脅威"


@pytest.mark.parametrize(
    "path",
    [
        "../secret.md",
        "security/../../secret.md",
        "..\\secret.md",
    ],
)
def test_rejects_parent_traversal(docs: Path, path: str) -> None:
    with pytest.raises(DocAccessError):
        resolve_doc_path(docs, path)


def test_rejects_absolute_path(docs: Path) -> None:
    with pytest.raises(DocAccessError):
        resolve_doc_path(docs, str(docs.parent / "secret.md"))


def test_rejects_non_md(docs: Path) -> None:
    with pytest.raises(DocAccessError):
        resolve_doc_path(docs, "notes.txt")


def test_rejects_missing_file(docs: Path) -> None:
    with pytest.raises(DocAccessError):
        resolve_doc_path(docs, "nothing.md")


def test_rejects_directory_named_md(docs: Path) -> None:
    (docs / "folder.md").mkdir()
    with pytest.raises(DocAccessError):
        resolve_doc_path(docs, "folder.md")


def test_rejects_symlink_to_outside(docs: Path) -> None:
    link = docs / "link.md"
    try:
        os.symlink(docs.parent / "secret.md", link)
    except OSError:
        pytest.skip("この環境ではシンボリックリンクを作れない（Windows の開発者モードがオフなど）")
    with pytest.raises(DocAccessError):
        resolve_doc_path(docs, "link.md")


def test_rejects_junction_to_outside(docs: Path) -> None:
    # ジャンクション（Windows のフォルダーのリンク）は管理者の権限なしで作れる。
    # リンクを解いてから範囲を確かめる
    _winapi = pytest.importorskip("_winapi")
    outside = docs.parent / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("SECRET", encoding="utf-8")
    _winapi.CreateJunction(str(outside), str(docs / "j"))
    with pytest.raises(DocAccessError):
        resolve_doc_path(docs, "j/secret.md")
    assert "j/secret.md" not in list_doc_paths(docs)


def test_rejects_too_large_file(docs: Path) -> None:
    (docs / "big.md").write_text("a" * 300_000, encoding="utf-8")
    with pytest.raises(DocAccessError):
        read_doc_text(docs, "big.md")


def test_list_returns_only_md_inside_docs(docs: Path) -> None:
    assert list_doc_paths(docs) == ["plan.md", "security/threat-model.md"]


def test_error_message_does_not_echo_outside_content(docs: Path) -> None:
    with pytest.raises(DocAccessError) as excinfo:
        read_doc_text(docs, "../secret.md")
    assert "SECRET" not in str(excinfo.value)
