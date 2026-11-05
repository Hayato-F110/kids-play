"""テレメトリー（OpenTelemetry）。脅威分析 T-34、対策 C-37。

KIDS_OTEL=enabled のときだけ main.create_app から呼ばれる（既定は無効）。
記録するのは「どの処理が、何回、どれだけ時間がかかったか」だけ。
ヘッダー、クエリ、要求の本文（えほんの絵と声）は記録しない。

- トレース：OTLP（http）で、クラスターの中の Jaeger へ送る。送り先は標準の環境変数
  OTEL_EXPORTER_OTLP_ENDPOINT で決める（k8s/api.yaml）。外部のサービスには送らない
- メトリクス：Prometheus の形式で、api の Pod の中の 9464 番から読ませる（port-forward で見る）
"""

from dataclasses import dataclass

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Span, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

SERVICE_NAME = "kids-play-api"
METRICS_PORT = 9464
# URL の中で、記録してよいのは「どの道か」だけ。クエリ（? のあと）は値を含みうるので消す
_QUERY_ATTRIBUTES = ("url.query", "http.target", "http.url", "url.full")


@dataclass(frozen=True)
class Telemetry:
    tracer_provider: TracerProvider
    meter_provider: MeterProvider


def _drop_query(span: Span, _scope: dict[str, object]) -> None:
    """要求を受けた直後に、クエリを含みうる属性を「道だけ」に置き換える。

    計装の部品は、版によってクエリを url.query や http.target に入れる。
    部品の既定に頼らず、ここで上書きして、値が残らないようにする（C-37 (4)）。
    """
    if not span.is_recording():
        return
    attributes = span.attributes or {}
    for key in _QUERY_ATTRIBUTES:
        value = attributes.get(key)
        if isinstance(value, str) and "?" in value:
            span.set_attribute(key, value.split("?", 1)[0])
        elif key == "url.query" and value is not None:
            span.set_attribute(key, "")


def setup_telemetry(
    app: FastAPI,
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
) -> Telemetry:
    """アプリを計装する。exporter を渡さないときは、本番の送り先（OTLP と Prometheus）を作る。"""
    resource = Resource.create({"service.name": SERVICE_NAME})

    tracer_provider = TracerProvider(resource=resource)
    if span_exporter is None:
        # import をここに置き、無効のとき（既定）は送り先の部品を読み込みもしない
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    else:
        # テストではすぐに見えるよう、まとめずに1件ずつ渡す
        tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    if metric_reader is None:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        from prometheus_client import start_http_server

        # Pod の中だけで待つ。Pod の外からは NetworkPolicy で届かず、見るときは port-forward を使う
        start_http_server(port=METRICS_PORT, addr="0.0.0.0")  # noqa: S104
        metric_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])

    # グローバルの provider は使わない（テストで何度もアプリを作れるように、アプリごとに渡す）
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        # ASGI の受け取り・送り出しの細かいスパンは出さない（数が多く、読む助けにならない）
        exclude_spans=["receive", "send"],
        server_request_hook=_drop_query,
        # ヘッダーを記録する設定（http_capture_headers_*）は、わざと渡さない（既定は記録しない）
    )
    return Telemetry(tracer_provider=tracer_provider, meter_provider=meter_provider)
