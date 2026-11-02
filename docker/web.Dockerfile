# フロント（HTML/CSS/JS）を配り、/api/ を api のコンテナへ中継する nginx。
# root 以外（uid 101）で動く公式の nginx-unprivileged を使う。版とダイジェストで固定する（T-04、C-09）
FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e

# CVE-2026-111497（brotli の範囲外への書き込み。CRITICAL、CISA KEV に 2026-10-27 追加）の修正版（1.2.1-r0 以降）に上げる。
# 2026-10-29 の時点で、上流のイメージはまだ作り直されていない（10/19 のまま）。
# 上流が直ったら、この3行を消して、上の FROM のダイジェストを新しいものにする
USER root
RUN apk upgrade --no-cache brotli-libs
USER 101

# ファイルの持ち主は root のまま。nginx ユーザーは読めるが、書き換えられない
COPY server/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/
