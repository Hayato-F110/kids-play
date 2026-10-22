# フロント（HTML/CSS/JS）を配り、/api/ を api のコンテナへ中継する nginx。
# root 以外（uid 101）で動く公式の nginx-unprivileged を使う。版とダイジェストで固定する（T-04、C-09）
FROM nginxinc/nginx-unprivileged:1.31.6-alpine3.24@sha256:884e0b7f42f303641b0f4e78755aea647521dca0b89ca3be7992ad78b5c07434

# ファイルの持ち主は root のまま。nginx ユーザーは読めるが、書き換えられない
COPY server/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/
