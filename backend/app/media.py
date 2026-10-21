"""絵と声のファイルの確認。申告された種類と、中身の先頭のバイトの両方を見る。

種類（Content-Type）は送る側が自由に書けるので、それだけを信じない。
SVG や HTML のように中にスクリプトを書ける形式は、許可リストに入れない。
"""

from fastapi import UploadFile

from app.config import MAX_PICTURE_BYTES, MAX_VOICE_BYTES
from app.errors import ApiError


def _is_png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def _is_webm(data: bytes) -> bool:
    # WebM（Matroska）の先頭の印（EBML ヘッダー）
    return data.startswith(b"\x1a\x45\xdf\xa3")


def _is_ogg(data: bytes) -> bool:
    return data.startswith(b"OggS")


def _is_mp4(data: bytes) -> bool:
    # MP4 は先頭4バイトが箱の大きさで、その次が "ftyp"
    return data[4:8] == b"ftyp"


# 種類ごとの、中身の確かめ方。キャンバスの toBlob は PNG、MediaRecorder はブラウザにより webm / ogg / mp4
PICTURE_TYPES = {"image/png": _is_png}
VOICE_TYPES = {"audio/webm": _is_webm, "audio/ogg": _is_ogg, "audio/mp4": _is_mp4}


def _base_type(content_type: str | None) -> str:
    # "audio/webm;codecs=opus" の後ろの指定は捨てる。保存して返すのは種類の名前だけにする
    return (content_type or "").split(";", 1)[0].strip().lower()


async def _read_checked(
    file: UploadFile | None, allowed: dict, max_bytes: int
) -> tuple[bytes, str] | tuple[None, None]:
    if file is None:
        return None, None
    content_type = _base_type(file.content_type)
    check = allowed.get(content_type)
    if check is None:
        raise ApiError(422, "invalid-page")
    # 上限より1バイトだけ多く読み、超えているかを見分ける（全部を読み込まない）
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ApiError(413, "too-large")
    if not data or not check(data):
        raise ApiError(422, "invalid-page")
    return data, content_type


async def read_picture(file: UploadFile | None) -> tuple[bytes, str] | tuple[None, None]:
    return await _read_checked(file, PICTURE_TYPES, MAX_PICTURE_BYTES)


async def read_voice(file: UploadFile | None) -> tuple[bytes, str] | tuple[None, None]:
    return await _read_checked(file, VOICE_TYPES, MAX_VOICE_BYTES)
