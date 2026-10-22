# わたしのえほんの API（FastAPI）。サーバー保存は既定で無効のまま動く（T-08、C-12）。
# ベースイメージは版とダイジェストの両方で固定する。更新は Dependabot が PR で知らせる（T-04、C-09）

# uv（部品を入れる道具）。FROM の行に書くと、Dependabot が新しい版を知らせる
FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

# ---- 1段目：部品を入れる（uv はここだけで使い、動かす側のイメージには入れない）----
FROM python:3.14.9-alpine3.24@sha256:d55673c233e28839c1c0c69766428cb6d50174a2ecfdcf915b6f58a0b0991562 AS build
COPY --from=uv /uv /bin/uv

# 起動を速くするため .pyc を先に作る。Python 本体はベースイメージのものを使い、別にダウンロードしない
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# uv.lock のとおりの版だけを入れる（--locked：lock と食い違えば失敗させる）。テスト用の部品は入れない
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/app ./app

# ---- 2段目：動かす ----
FROM python:3.14.9-alpine3.24@sha256:d55673c233e28839c1c0c69766428cb6d50174a2ecfdcf915b6f58a0b0991562

# 動かすときに使わない pip は消す（使わない部品を残さない）。root 以外の専用ユーザーを作る
RUN python -m pip uninstall -y pip \
  && addgroup -S -g 10001 app \
  && adduser -S -D -H -u 10001 -G app app

# ファイルの持ち主は root のまま。app ユーザーは読んで動かせるが、書き換えられない
COPY --from=build /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001

# コンテナの中では、compose の内側の通信だけを受けるために 0.0.0.0 で待ち受ける。
# PC の外には公開しない（compose で ports を書かない）。外から届くのは nginx だけ
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
