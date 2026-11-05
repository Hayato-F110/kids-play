"""テレメトリー（OpenTelemetry）の試験。脅威分析 T-34、対策 C-37。

送り先はメモリの exporter だけにし、外へは送らない。
確かめること：既定は無効（fail-safe）、有効なら要求の流れと時間が記録される、
そして、ヘッダー・クエリ・本文の中身がテレメトリーに入らない。
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from app.config import ENV_OTEL, Settings
from app.main import PAGES_PATH, create_app
from tests.conftest import PNG, WEBM

# 漏れたら見つけられるように、ほかに出てこない目印の文字列を使う
SECRET_MARKERS = {
    "authorization": "Bearer marker-token-1234",
    "cookie": "sid=marker-cookie-5678",
    "x-kids-note": "marker-header-9012",
    # 計装の部品は既定で User-Agent を記録する。家の中の端末の見分けに使えるので、これも残さない
    "user-agent": "marker-agent-2468",
}
QUERY_MARKER = "marker-query-3456"
BODY_MARKER = b"marker-body-7890"


class Recorder:
    """アプリと、記録を受け取るメモリの exporter の組。"""

    def __init__(self, settings: Settings) -> None:
        self.spans = InMemorySpanExporter()
        self.metrics = InMemoryMetricReader()
        app = create_app(settings, span_exporter=self.spans, metric_reader=self.metrics)
        self.client = TestClient(app, base_url="http://localhost", headers={"origin": "http://localhost"})

    def finished(self) -> tuple[ReadableSpan, ...]:
        return self.spans.get_finished_spans()

    def metric_names(self) -> set[str]:
        data = self.metrics.get_metrics_data()
        if data is None:
            return set()
        return {
            metric.name
            for resource in data.resource_metrics
            for scope in resource.scope_metrics
            for metric in scope.metrics
        }


def _settings(tmp_path: Path, telemetry: bool, storage: bool = False) -> Settings:
    return Settings(
        server_storage_enabled=storage,
        db_path=tmp_path / "kids.sqlite3",
        frontend_dir=tmp_path / "no-frontend",
        telemetry_enabled=telemetry,
    )


@pytest.fixture
def recorder(tmp_path: Path) -> Iterator[Recorder]:
    rec = Recorder(_settings(tmp_path, telemetry=True))
    yield rec
    rec.client.close()


def _all_attribute_text(spans: tuple[ReadableSpan, ...]) -> str:
    """すべてのスパンの名前と属性の値を、1つの文字列にまとめる（漏れの検索用）。"""
    parts: list[str] = []
    for span in spans:
        parts.append(span.name)
        for key, value in (span.attributes or {}).items():
            parts.append(f"{key}={value}")
        for event in span.events:
            for key, value in (event.attributes or {}).items():
                parts.append(f"{key}={value}")
    return "\n".join(parts)


# 1. 既定は無効
@pytest.mark.parametrize("value", [None, "", "true", "1", "Enabled", "enabled "])
def test_from_env_enables_only_exact_word(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv(ENV_OTEL, raising=False)
    else:
        monkeypatch.setenv(ENV_OTEL, value)
    assert Settings.from_env().telemetry_enabled is False


def test_from_env_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_OTEL, "enabled")
    assert Settings.from_env().telemetry_enabled is True


def test_disabled_records_nothing(tmp_path: Path) -> None:
    # exporter を渡しても、設定が無効なら計装しない
    rec = Recorder(_settings(tmp_path, telemetry=False))
    response = rec.client.get("/api/storage/status")
    assert response.status_code == 200
    assert rec.finished() == ()
    assert rec.metric_names() == set()
    assert rec.client.app.state.telemetry is None  # type: ignore[attr-defined]


# 2. 有効なら、要求ごとにサーバーのスパンが1件
def test_server_span_has_route_and_status(recorder: Recorder) -> None:
    response = recorder.client.get("/api/storage/status")
    assert response.status_code == 200
    servers = [s for s in recorder.finished() if s.kind == SpanKind.SERVER]
    assert len(servers) == 1
    attrs = servers[0].attributes or {}
    assert attrs.get("http.route") == "/api/storage/status"
    status = attrs.get("http.response.status_code", attrs.get("http.status_code"))
    assert status == 200
    assert servers[0].resource.attributes.get("service.name") == "kids-play-api"


def test_no_asgi_receive_send_spans(recorder: Recorder) -> None:
    # ASGI の細かいスパン（receive / send）は雑音になるので出さない
    recorder.client.get("/api/storage/status")
    assert all(s.kind == SpanKind.SERVER for s in recorder.finished())


# 3. ヘッダーとクエリの中身が入らない
def test_headers_and_query_not_recorded(recorder: Recorder) -> None:
    recorder.client.get(f"/api/storage/status?secret={QUERY_MARKER}", headers=SECRET_MARKERS)
    text = _all_attribute_text(recorder.finished())
    assert text  # 何かは記録されている（空で「漏れなし」にならないように）
    for marker in [*SECRET_MARKERS.values(), QUERY_MARKER]:
        assert marker not in text


# 4. 本文（えほんのページ）の中身が入らない
def test_body_not_recorded(tmp_path: Path) -> None:
    rec = Recorder(_settings(tmp_path, telemetry=True, storage=True))
    files = {
        "picture": ("picture", PNG + BODY_MARKER, "image/png"),
        "voice": ("voice", WEBM + BODY_MARKER, "audio/webm"),
    }
    response = rec.client.post(PAGES_PATH, data={"voiceMs": "1000"}, files=files)
    assert response.status_code == 201
    text = _all_attribute_text(rec.finished())
    assert text
    assert BODY_MARKER.decode() not in text


# 5. 時間のメトリクスが記録される
def test_duration_metric_recorded(recorder: Recorder) -> None:
    recorder.client.get("/api/storage/status")
    names = recorder.metric_names()
    assert names & {"http.server.request.duration", "http.server.duration"}
