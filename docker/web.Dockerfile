# フロント（HTML/CSS/JS）を配り、/api/ を api のコンテナへ中継する nginx。
# root 以外（uid 101）で動く公式の nginx-unprivileged を使う。版とダイジェストで固定する（T-04、C-09）
FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

# CVE-2026-111497（brotli の範囲外への書き込み。CRITICAL、CISA KEV に 2026-10-27 追加）の修正版（1.2.1-r0 以降）に上げる。
# 2026-10-29 の時点で、上流のイメージはまだ作り直されていない（10/19 のまま）。
# 上流が直ったら、この3行を消して、上の FROM のダイジェストを新しいものにする
USER root
RUN apk upgrade --no-cache brotli-libs
USER 101

# ファイルの持ち主は root のまま。nginx ユーザーは読めるが、書き換えられない
COPY server/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/
