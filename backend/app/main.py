"""わたしのえほんのサーバー保存 API と、フロントの配信。

PC の中だけで使う。起動は backend/ で次のとおり（127.0.0.1 だけで待ち受け、ほかの機器からは届かない）：

    $env:KIDS_SERVER_STORAGE = "enabled"
    uv run uvicorn app.main:create_app_from_env --factory --host 127.0.0.1 --port 8000

環境変数がなければ、保存の API はすべて拒否し、フロントは IndexedDB に保存する（脅威分析 T-08、対策 C-12）。
"""

import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Body, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry.sdk.metrics.export import MetricReader
from opentelemetry.sdk.trace.export import SpanExporter
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import MAX_REQUEST_BYTES, MAX_VOICE_MS, Settings
from app.errors import ApiError
from app.media import read_picture, read_voice
from app.store import PageContent, PageLimitError, PageMeta, PageStore
from app.telemetry import setup_telemetry
from app.zerotrust import AUTH_PREFIX, ZeroTrust

# ブラウザが PC の中のサーバーを開くときの名前だけを受け付ける
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
PAGES_PATH = "/api/pages"
# 読むだけの要求。ほかのサイトからは応答を読めない（CORS の許可を出していない）ので、Origin を求めない
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class StorageStatus(BaseModel):
    enabled: bool


class SetupCode(BaseModel):
    # 名前の違う項目や欠けた項目は「合言葉なし」として 403 にする（理由を細かく返さない）
    model_config = ConfigDict(populate_by_name=True)
    setup_code: str | None = Field(default=None, alias="setupCode", max_length=64)


class ParentSummary(BaseModel):
    """おとなのページに返す値。子どもの絵と声は含めない（A1 を新しい経路に乗せない）。"""

    model_config = ConfigDict(serialize_by_alias=True)
    storage_enabled: bool = Field(alias="storageEnabled")
    page_count: int | None = Field(alias="pageCount")
    subject: str


# ログインの窓口が受け取る中身の上限。パスキーの応答は数KB
MAX_AUTH_BYTES = 16 * 1024


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"code": code}, status_code=status)


def _length_problem(request: Request, limit: int) -> JSONResponse | None:
    # 大きさは Content-Length で先に見る。uvicorn は宣言より多い中身を受け取らないので、
    # Content-Length を必須にすれば、上限を超えるデータを読み込まずに済む
    length = request.headers.get("content-length")
    if length is None or not length.isdigit():
        return _error(411, "length-required")
    if int(length) > limit:
        return _error(413, "too-large")
    return None


def create_app(
    settings: Settings,
    clock: Callable[[], float] = time.time,
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
) -> FastAPI:
    # API の説明の画面（/docs）は外部の CDN からスクリプトを読むので出さない（外部通信なしのルール）
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    # テレメトリーは既定で無効。exporter が渡されても、設定が無効なら計装しない（C-37）。
    # exporter を渡すのはテストだけ（メモリに記録する）
    app.state.telemetry = (
        setup_telemetry(app, span_exporter=span_exporter, metric_reader=metric_reader)
        if settings.telemetry_enabled
        else None
    )
    # 無効のときは DB を作らない。受け取らないだけでなく、置き場所も作らない
    store = PageStore(settings.db_path) if settings.server_storage_enabled else None
    # 無効のときは、ログインの窓口もおとなの API も作らない（既定は無効）
    zero_trust = ZeroTrust(settings.zero_trust_origin, clock) if settings.zero_trust_enabled else None
    app.state.zero_trust = zero_trust

    def reject(request: Request) -> JSONResponse | None:
        """中身（絵と声）を読む前に断る理由があれば、その応答を返す。
        順番は、偽の要求 → （ゼロトラストのとき）トークンと権限 → 無効 → 大きさ。"""
        path = request.url.path
        if request.method not in SAFE_METHODS:
            # ほかのサイトから書き込ませる攻撃（CSRF）を、ほかの理由より先に断る。
            # multipart の POST は事前の問い合わせなしで送られるので、CORS では止まらない。
            # Origin が自分自身（確認済みの Host）のときだけ受け付ける。
            # ブラウザは書き込みの要求に必ず Origin を付けるので、ないものも断る（T-18、C-22）
            if request.headers.get("origin") != f"http://{request.headers.get('host')}":
                return _error(403, "cross-origin")
        if zero_trust is not None:
            if path.startswith(AUTH_PREFIX):
                # ログインの窓口だけはトークンなしで通す。そのかわり、中身の大きさを先に絞る
                return _length_problem(request, MAX_AUTH_BYTES) if request.method == "POST" else None
            # 「内側から来たから通す」をしない。/api/ への要求は、毎回トークンと権限を確かめる（C-32 (4)）
            denied, subject = zero_trust.authorize(request.method, path, request.headers.get("authorization"))
            if denied is not None:
                return denied
            request.state.subject = subject
        if path != PAGES_PATH and not path.startswith(PAGES_PATH + "/"):
            return None
        # 無効なら、中身を読む前に断る。一時ファイルにも残さない
        if store is None:
            return _error(403, "server-storage-disabled")
        if request.method in ("POST", "PUT"):
            return _length_problem(request, MAX_REQUEST_BYTES)
        return None

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        is_api = request.url.path.startswith("/api/")
        rejected = reject(request) if is_api else None
        response = rejected or await call_next(request)
        if is_api:
            # 子どもの絵と声を、ブラウザや途中の仕組みに写しとして残させない。種類の決め打ちも止める
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # 最後に足したものが一番外側で動く。よその Host の要求は、ほかの処理より先に断る
    # （DNS リバインディング対策）
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.exception_handler(ApiError)
    async def on_api_error(_request: Request, error: ApiError) -> JSONResponse:
        return _error(error.status, error.code)

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_request: Request, _error_: RequestValidationError) -> JSONResponse:
        # 何が違ったかの詳細は返さない。フロントは理由の名前だけで扱う
        return _error(422, "invalid-page")

    def pages() -> PageStore:
        # guard で無効のときは断っているので、ここに来るときは必ず有効
        if store is None:
            raise ApiError(403, "server-storage-disabled")
        return store

    async def read_content(
        picture: UploadFile | None, voice: UploadFile | None, voice_ms: int
    ) -> PageContent:
        if voice_ms > MAX_VOICE_MS:
            raise ApiError(422, "voice-too-long")
        picture_data, picture_type = await read_picture(picture)
        voice_data, voice_type = await read_voice(voice)
        return PageContent(picture_data, picture_type, voice_data, voice_type, voice_ms)

    # 受け取る項目は、この3つだけ。名前や日時などほかの項目は、送られても読まない
    PictureFile = Annotated[UploadFile | None, File()]
    VoiceFile = Annotated[UploadFile | None, File()]
    VoiceMs = Annotated[int, Form(alias="voiceMs", ge=0, strict=False)]

    @app.get("/api/storage/status")
    def status() -> StorageStatus:
        return StorageStatus(enabled=store is not None)

    @app.get(PAGES_PATH, response_model=list[PageMeta], response_model_by_alias=True)
    def list_pages() -> list[PageMeta]:
        return pages().list_pages()

    @app.post(PAGES_PATH, status_code=201, response_model=PageMeta, response_model_by_alias=True)
    async def add_page(voice_ms: VoiceMs, picture: PictureFile = None, voice: VoiceFile = None) -> PageMeta:
        content = await read_content(picture, voice, voice_ms)
        try:
            return pages().add(content)
        except PageLimitError:
            raise ApiError(409, "page-limit") from None

    @app.put(PAGES_PATH + "/{page_id}", response_model=PageMeta, response_model_by_alias=True)
    async def replace_page(
        page_id: UUID, voice_ms: VoiceMs, picture: PictureFile = None, voice: VoiceFile = None
    ) -> Response:
        content = await read_content(picture, voice, voice_ms)
        replaced = pages().replace(str(page_id), content)
        if replaced is not None:
            return JSONResponse(replaced.model_dump(by_alias=True))
        # ないページなら、メモリ版・IndexedDB 版と同じく、新しいページとして最後に足す
        try:
            added = pages().add(content)
        except PageLimitError:
            raise ApiError(409, "page-limit") from None
        return JSONResponse(added.model_dump(by_alias=True), status_code=201)

    def media(page_id: UUID, kind: str) -> Response:
        found = pages().get_media(str(page_id), kind)
        if found is None:
            return Response(status_code=404)
        data, content_type = found
        return Response(content=data, media_type=content_type)

    @app.get(PAGES_PATH + "/{page_id}/picture")
    def get_picture(page_id: UUID) -> Response:
        return media(page_id, "picture")

    @app.get(PAGES_PATH + "/{page_id}/voice")
    def get_voice(page_id: UUID) -> Response:
        return media(page_id, "voice")

    @app.delete(PAGES_PATH + "/{page_id}", status_code=204)
    def delete_page(page_id: UUID) -> None:
        pages().delete(str(page_id))

    @app.delete(PAGES_PATH, status_code=204)
    def delete_all() -> None:
        pages().delete_all()

    if zero_trust is not None:
        zt = zero_trust
        zt.announce()

        @app.post(AUTH_PREFIX + "register/options")
        def register_options(body: SetupCode) -> dict[str, Any]:
            return zt.registration_options(body.setup_code)

        @app.post(AUTH_PREFIX + "register/verify", status_code=201)
        def register_verify(credential: Annotated[dict[str, Any], Body()]) -> dict[str, bool]:
            zt.register(credential)
            return {"registered": True}

        @app.post(AUTH_PREFIX + "login/options")
        def login_options() -> dict[str, Any]:
            return zt.login_options()

        @app.post(AUTH_PREFIX + "login/verify")
        def login_verify(credential: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
            return zt.login(credential)

        @app.get("/api/parent/summary")
        def parent_summary(request: Request) -> ParentSummary:
            # ページの数だけを返す。絵と声は読まない
            count = len(store.list_pages()) if store is not None else None
            return ParentSummary(
                storageEnabled=store is not None, pageCount=count, subject=request.state.subject
            )

    # フロントを同じオリジンで配る。通信先が自分のオリジンだけになり、
    # CSP を connect-src 'self' にとどめられる。
    # API の経路より後に置く（先に置くと、/api/... もファイルとして探してしまう）。
    # コンテナでは nginx がフロントを配り、api のイメージにはフロントを入れないので、ないときは配らない
    if settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")

    return app


def create_app_from_env() -> FastAPI:
    """uvicorn の --factory で呼ぶ入口。import しただけでは DB を作らないように、関数にしてある。"""
    return create_app(Settings.from_env())
