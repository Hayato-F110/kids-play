# フロント（HTML/CSS/JS）を配り、/api/ を api のコンテナへ中継する nginx。
# root 以外（uid 101）で動く公式の nginx-unprivileged を使う。版とダイジェストで固定する（T-04、C-09）
FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

# ファイルの持ち主は root のまま。nginx ユーザーは読めるが、書き換えられない
COPY server/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/
