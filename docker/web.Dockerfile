# フロント（HTML/CSS/JS）を配り、/api/ を api のコンテナへ中継する nginx。
# root 以外（uid 101）で動く公式の nginx-unprivileged を使う。版とダイジェストで固定する（T-04、C-09）
FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

# CVE-2026-111497（brotli の範囲外への書き込み。CRITICAL、CISA KEV に 2026-10-27 追加）の修正版（1.2.1-r0 以降）に上げる。
# 2026-10-29 の時点で、上流のイメージはまだ作り直されていない（10/19 のまま）。
# nginx も、11/18 に発表された脆弱性（CVE-2026-121810、CVE-2026-123007、CVE-2026-123633 など。CRITICAL）の修正版 1.30.7 に上げる。
# 2026-11-19 の時点で、上流の 1.30 系のイメージはまだ 1.30.6 のまま（10/19）。
# 元のイメージは nginx.org の nginx を版で固定して入れている。Alpine の nginx（別物）に替わらないよう、
# nginx.org の置き場所をこのときだけ指定し、追加の部品も同じ版にそろえる。署名は元のイメージにある nginx.org の鍵で確かめられる
# 上流が直ったら、この RUN と前後の USER を消して、上の FROM の版とダイジェストを新しいものにする
USER root
RUN apk upgrade --no-cache brotli-libs \
 && apk add --no-cache --repository https://nginx.org/packages/alpine/v3.24/main \
      nginx=1.30.7-r1 \
      nginx-module-geoip=1.30.7-r1 \
      nginx-module-image-filter=1.30.7-r1 \
      nginx-module-njs=1.30.7.1.0.2-r1 \
      nginx-module-xslt=1.30.7-r1
USER 101

# ファイルの持ち主は root のまま。nginx ユーザーは読めるが、書き換えられない
COPY server/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/
